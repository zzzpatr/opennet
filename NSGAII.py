import csv
import math
import random
from pathlib import Path

from ga_common import (
    GENERATIONS,
    MUTATION_RATE,
    PAIR_MUTATION_RATE,
    POPULATION_SIZE,
    PRINT_INTERVAL,
    RANDOM_SEED,
    SWAP_MUTATION_RATE,
    clear_metrics_cache,
    crossover,
    create_evaluation_executor,
    evaluate_metrics,
    evaluate_population,
    mutate,
    save_best_solution,
    save_history,
)
from ga_plot import save_ga_charts
from GA_weighted_game_design import (
    BALANCED_INITIALIZATION_RATIO,
    calculate_objective_penalties,
    create_initial_population,
    repair_missing_jackpot,
)
from slot_game import (
    calculate_winning_payout_statistics,
    print_winning_payout_statistics,
)


RESULTS_DIRECTORY = Path("nsga2_results")

OBJECTIVE_NAMES = (
    "rtp_violation_penalty",
    "win_rate_shortfall_penalty",
    "symbol_concentration_penalty",
    "missing_jackpot_penalty",
)
ALGORITHM_NAME = "NSGA-II"
FINAL_SOLUTION_NUMBER = 95


def evaluate_reels(reels, metrics=None):
    """Build objectives from the same four penalties used by Weighted GA."""
    if metrics is None:
        metrics = evaluate_metrics(reels)
    objectives = calculate_objective_penalties(metrics)

    return {
        "reels": [reel[:] for reel in reels],
        **metrics,
        "objectives": objectives,
        "weighted_score": sum(objectives),
        "rank": None,
        "crowding_distance": 0.0,
    }


def dominates(individual_a, individual_b):
    """Check standard Pareto dominance across all four objectives."""
    objectives_a = individual_a["objectives"]
    objectives_b = individual_b["objectives"]
    no_worse = all(
        value_a <= value_b
        for value_a, value_b in zip(objectives_a, objectives_b)
    )
    strictly_better = any(
        value_a < value_b
        for value_a, value_b in zip(objectives_a, objectives_b)
    )
    return no_worse and strictly_better


def non_dominated_sort(population):
    """Split the population into Pareto fronts with fast non-dominated sorting."""
    domination_counts = [0] * len(population)
    dominated_indices = [[] for _ in population]
    first_front = []

    for index_a, individual_a in enumerate(population):
        for index_b in range(index_a + 1, len(population)):
            individual_b = population[index_b]
            if dominates(individual_a, individual_b):
                dominated_indices[index_a].append(index_b)
                domination_counts[index_b] += 1
            elif dominates(individual_b, individual_a):
                dominated_indices[index_b].append(index_a)
                domination_counts[index_a] += 1

    for index, domination_count in enumerate(domination_counts):
        if domination_count == 0:
            population[index]["rank"] = 0
            first_front.append(index)

    front_indices = [first_front]
    current_front = 0
    while front_indices[current_front]:
        next_front = []
        for index_a in front_indices[current_front]:
            for index_b in dominated_indices[index_a]:
                domination_counts[index_b] -= 1
                if domination_counts[index_b] == 0:
                    population[index_b]["rank"] = current_front + 1
                    next_front.append(index_b)
        current_front += 1
        front_indices.append(next_front)

    front_indices.pop()
    return [
        [population[index] for index in indices]
        for indices in front_indices
    ]


def assign_crowding_distance(front):
    """Calculate crowding distance within one Pareto front."""
    if not front:
        return
    for individual in front:
        individual["crowding_distance"] = 0.0
    if len(front) <= 2:
        for individual in front:
            individual["crowding_distance"] = float("inf")
        return

    for objective_index in range(len(OBJECTIVE_NAMES)):
        ordered = sorted(
            front,
            key=lambda item: item["objectives"][objective_index],
        )
        ordered[0]["crowding_distance"] = float("inf")
        ordered[-1]["crowding_distance"] = float("inf")
        minimum = ordered[0]["objectives"][objective_index]
        maximum = ordered[-1]["objectives"][objective_index]
        if maximum == minimum:
            continue

        for index in range(1, len(ordered) - 1):
            if math.isinf(ordered[index]["crowding_distance"]):
                continue
            previous_value = ordered[index - 1]["objectives"][
                objective_index
            ]
            next_value = ordered[index + 1]["objectives"][
                objective_index
            ]
            ordered[index]["crowding_distance"] += (
                (next_value - previous_value)
                / (maximum - minimum)
            )


def rank_and_assign_crowding(population):
    """Rank the population and assign all crowding distances."""
    fronts = non_dominated_sort(population)
    for front in fronts:
        assign_crowding_distance(front)
    return fronts


def tournament_select(population):
    """Run a binary tournament using rank and crowding distance."""
    individual_a, individual_b = random.sample(population, 2)
    if individual_a["rank"] != individual_b["rank"]:
        return min(
            (individual_a, individual_b),
            key=lambda item: item["rank"],
        )
    if (
        individual_a["crowding_distance"]
        != individual_b["crowding_distance"]
    ):
        return max(
            (individual_a, individual_b),
            key=lambda item: item["crowding_distance"],
        )
    return random.choice((individual_a, individual_b))


def create_offspring(population, executor=None):
    """Create offspring with tournament selection, crossover, and mutation."""
    offspring_reels = []
    while len(offspring_reels) < POPULATION_SIZE:
        parent_a = tournament_select(population)
        parent_b = tournament_select(population)
        child_reels = crossover(
            parent_a["reels"],
            parent_b["reels"],
        )
        mutate(
            child_reels,
            mutation_rate=MUTATION_RATE,
            pair_rate=PAIR_MUTATION_RATE,
            swap_rate=SWAP_MUTATION_RATE,
        )
        repair_missing_jackpot(child_reels)
        offspring_reels.append(child_reels)
    metrics_list = evaluate_population(offspring_reels, executor)
    return [
        evaluate_reels(reels, metrics)
        for reels, metrics in zip(offspring_reels, metrics_list)
    ]


def environmental_selection(combined_population):
    """Pick a fixed-size next generation from parents and offspring."""
    fronts = rank_and_assign_crowding(combined_population)
    next_population = []
    for front in fronts:
        remaining = POPULATION_SIZE - len(next_population)
        if len(front) <= remaining:
            next_population.extend(front)
            continue
        front.sort(
            key=lambda item: item["crowding_distance"],
            reverse=True,
        )
        next_population.extend(front[:remaining])
        break
    return next_population


def select_recommended_solution(pareto_front):
    """Use the lowest penalty sum as each generation's chart representative."""
    return min(pareto_front, key=lambda item: item["weighted_score"])


def select_final_plot_solution(pareto_front):
    """Pick the requested Pareto solution for the final output and charts."""
    solution_index = FINAL_SOLUTION_NUMBER - 1
    if not 0 <= solution_index < len(pareto_front):
        raise ValueError(
            f"Pareto front does not have solution {FINAL_SOLUTION_NUMBER}; "
            f"it only contains {len(pareto_front)} solutions."
        )
    return pareto_front[solution_index]


def save_pareto_front(pareto_front):
    """Write the final Pareto front to CSV."""
    RESULTS_DIRECTORY.mkdir(exist_ok=True)
    output_path = RESULTS_DIRECTORY / "nsga2_pareto_front.csv"
    fieldnames = [
        "solution",
        "weighted_score",
        *OBJECTIVE_NAMES,
        "rtp",
        "win_rate",
        "symbol_concentration",
        "jackpot_probability",
        "reel_1",
        "reel_2",
        "reel_3",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for solution_index, individual in enumerate(pareto_front, start=1):
            writer.writerow({
                "solution": solution_index,
                "weighted_score": individual["weighted_score"],
                **dict(zip(OBJECTIVE_NAMES, individual["objectives"])),
                "rtp": individual["rtp"],
                "win_rate": individual["win_rate"],
                "symbol_concentration": individual[
                    "symbol_concentration"
                ],
                "jackpot_probability": individual[
                    "jackpot_probability"
                ],
                "reel_1": repr(individual["reels"][0]),
                "reel_2": repr(individual["reels"][1]),
                "reel_3": repr(individual["reels"][2]),
            })
    return output_path


def print_generation_summary(generation, pareto_front):
    """Print a quick summary of the current Pareto front and representative."""
    recommended = select_recommended_solution(pareto_front)
    print(
        f"Generation {generation:3d} | "
        f"Pareto solutions={len(pareto_front)} | "
        f"weighted score={recommended['weighted_score']:.6f} | "
        f"RTP={recommended['rtp']:.4%} | "
        f"win rate={recommended['win_rate']:.4%} | "
        f"concentration={recommended['symbol_concentration']:.6f} | "
        f"jackpot={recommended['jackpot_probability']:.6%}"
    )


def create_history_row(generation, recommended):
    """Create a history row that works with the shared GA charts."""
    return {
        "generation": generation,
        "algorithm": ALGORITHM_NAME,
        "fitness_mode": "multi-objective",
        "primary_fitness": recommended["weighted_score"],
        "weighted_error": recommended["weighted_score"],
        "missing_jackpot": recommended["missing_jackpot"],
        "jackpot_spins": recommended["jackpot_spins"],
        "jackpot_probability": recommended["jackpot_probability"],
        "symbol_concentration": recommended["symbol_concentration"],
        "win_rate_shortfall": recommended["win_rate_shortfall"],
        "rtp_error": recommended["rtp_error"],
        "rtp": recommended["rtp"],
        "win_rate": recommended["win_rate"],
    }


def run_nsga2():
    """Create one shared executor and run NSGA-II."""
    with create_evaluation_executor() as executor:
        return _run_nsga2(executor)


def _run_nsga2(executor):
    """Run NSGA-II and return the Pareto front and selected solution."""
    random.seed(RANDOM_SEED)
    clear_metrics_cache()
    initial_reels = create_initial_population()
    initial_metrics = evaluate_population(initial_reels, executor)
    population = [
        evaluate_reels(reels, metrics)
        for reels, metrics in zip(initial_reels, initial_metrics)
    ]
    history = []
    print(
        "Initial population: "
        f"balanced={BALANCED_INITIALIZATION_RATIO:.0%}, "
        f"random={1 - BALANCED_INITIALIZATION_RATIO:.0%}"
    )
    fronts = rank_and_assign_crowding(population)

    for generation in range(1, GENERATIONS + 1):
        offspring = create_offspring(population, executor)
        population = environmental_selection(population + offspring)
        fronts = rank_and_assign_crowding(population)
        pareto_front = fronts[0]
        recommended = select_recommended_solution(pareto_front)
        history.append(create_history_row(generation, recommended))
        history_path = save_history(history, RESULTS_DIRECTORY)

        if generation == 1 or generation % PRINT_INTERVAL == 0:
            print_generation_summary(generation, pareto_front)

    pareto_front = fronts[0]
    output_path = save_pareto_front(pareto_front)
    recommended = select_final_plot_solution(pareto_front)

    print(f"\nPareto front：{output_path}")
    print(f"Pareto solutions：{len(pareto_front)}")
    print(f"Selected Pareto solution: {FINAL_SOLUTION_NUMBER}")
    print("Hard constraints: disabled")
    print(f"Weighted score: {recommended['weighted_score']:.6f}")
    print(
        "Objective penalties: "
        + ", ".join(
            f"{name}={value:.6f}"
            for name, value in zip(
                OBJECTIVE_NAMES,
                recommended["objectives"],
            )
        )
    )
    print("\nRecommended reels:")
    for reel in recommended["reels"]:
        print(reel)
    print(f"RTP: {recommended['rtp']:.4%}")
    print(f"Win rate: {recommended['win_rate']:.4%}")
    print(
        "Symbol concentration: "
        f"{recommended['symbol_concentration']:.6f}"
    )
    print(
        f"Jackpot: {recommended['jackpot_spins']} spins "
        f"({recommended['jackpot_probability']:.6%})"
    )
    payout_statistics = calculate_winning_payout_statistics(
        recommended["reels"]
    )
    recommended_metrics = evaluate_metrics(recommended["reels"])
    best_solution_path = save_best_solution(
        algorithm_name=ALGORITHM_NAME,
        generation=generation,
        reels=recommended["reels"],
        metrics=recommended_metrics,
        score=(recommended["weighted_score"],),
        payout_statistics=payout_statistics,
        results_directory=RESULTS_DIRECTORY,
    )
    chart_paths = save_ga_charts(history_path, RESULTS_DIRECTORY)
    print_winning_payout_statistics(payout_statistics)
    print(f"History: {history_path}")
    print(f"Recommended solution: {best_solution_path}")
    print(f"Convergence chart: {chart_paths[0]}")
    print(f"Metrics chart: {chart_paths[1]}")
    print(f"Prize distribution chart: {chart_paths[2]}")
    print(f"Reel symbol distribution chart: {chart_paths[3]}")
    return pareto_front, recommended


if __name__ == "__main__":
    run_nsga2()
