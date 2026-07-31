import csv
import math
import random
from pathlib import Path

from ga_common import (
    GENERATIONS,
    MIN_WIN_RATE,
    MUTATION_RATE,
    PAIR_MUTATION_RATE,
    POPULATION_SIZE,
    RTP_TOLERANCE,
    SWAP_MUTATION_RATE,
    clear_metrics_cache,
    crossover,
    create_individual,
    evaluate_metrics,
    mutate,
    repair_missing_symbol,
)
from slot_game import (
    calculate_winning_payout_statistics,
    print_winning_payout_statistics,
)


RANDOM_SEED = 42
PRINT_INTERVAL = 10
RTP_SEARCH_SCALE = 0.01
WIN_RATE_SEARCH_SCALE = 0.10
RESULTS_DIRECTORY = Path("nsga2_results")

OBJECTIVE_NAMES = (
    "rtp_error",
    "symbol_concentration",
)


def evaluate_reels(reels):
    """計算 NSGA-II objectives、constraints 與報表指標。"""
    metrics = evaluate_metrics(reels)
    constraint_count = (
        int(metrics["rtp_violation"] > 0)
        + int(metrics["win_rate_shortfall"] > 0)
        + metrics["missing_jackpot"]
        + int(metrics["missing_symbols"] > 0)
    )
    constraint_violation = (
        metrics["rtp_violation"] / RTP_SEARCH_SCALE
        + metrics["win_rate_shortfall"] / WIN_RATE_SEARCH_SCALE
        + metrics["jackpot_reel_shortfall"] / 3
        + metrics["missing_symbols"] / 5
    )

    return {
        "reels": [reel[:] for reel in reels],
        **metrics,
        "objectives": (
            metrics["rtp_error"],
            metrics["symbol_concentration"],
        ),
        "constraint_count": constraint_count,
        "constraint_violation": constraint_violation,
        "rank": None,
        "crowding_distance": 0.0,
    }


def dominates(individual_a, individual_b):
    """使用 constraint-domination 判斷 A 是否支配 B。"""
    violation_a = individual_a["constraint_violation"]
    violation_b = individual_b["constraint_violation"]
    feasible_a = individual_a["constraint_count"] == 0
    feasible_b = individual_b["constraint_count"] == 0

    if feasible_a != feasible_b:
        return feasible_a
    if not feasible_a:
        if not math.isclose(
            violation_a,
            violation_b,
            rel_tol=0,
            abs_tol=1e-12,
        ):
            return violation_a < violation_b

        count_a = individual_a["constraint_count"]
        count_b = individual_b["constraint_count"]
        if count_a != count_b:
            return count_a < count_b

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
    """使用 fast non-dominated sorting 將族群分成 Pareto fronts。"""
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
    """計算同一 Pareto front 內的 crowding distance。"""
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
    """完成 non-dominated sorting 並設定所有 crowding distances。"""
    fronts = non_dominated_sort(population)
    for front in fronts:
        assign_crowding_distance(front)
    return fronts


def tournament_select(population):
    """依 rank、crowding distance 進行 binary tournament。"""
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


def create_offspring(population):
    """使用 tournament、crossover 與 mutation 建立子代。"""
    offspring = []
    while len(offspring) < POPULATION_SIZE:
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
        repair_missing_symbol(child_reels)
        offspring.append(evaluate_reels(child_reels))
    return offspring


def environmental_selection(combined_population):
    """從 parents + offspring 中選出固定大小的下一代。"""
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
    """以 objectives 正規化後距離理想點最近者作為推薦解。"""
    feasible = [
        individual
        for individual in pareto_front
        if individual["constraint_count"] == 0
    ]
    candidates = feasible or pareto_front
    minimums = [
        min(item["objectives"][index] for item in candidates)
        for index in range(len(OBJECTIVE_NAMES))
    ]
    maximums = [
        max(item["objectives"][index] for item in candidates)
        for index in range(len(OBJECTIVE_NAMES))
    ]

    def ideal_distance(individual):
        normalized_values = []
        for index, value in enumerate(individual["objectives"]):
            span = maximums[index] - minimums[index]
            normalized_values.append(
                (value - minimums[index]) / span
                if span
                else 0
            )
        return math.sqrt(sum(value ** 2 for value in normalized_values))

    return min(candidates, key=ideal_distance)


def save_pareto_front(pareto_front):
    """將最終 Pareto front 寫入 CSV。"""
    RESULTS_DIRECTORY.mkdir(exist_ok=True)
    output_path = RESULTS_DIRECTORY / "nsga2_pareto_front.csv"
    fieldnames = [
        "solution",
        "feasible",
        "constraint_count",
        "constraint_violation",
        "rtp",
        "rtp_error",
        "win_rate",
        "win_rate_shortfall",
        "symbol_concentration",
        "missing_symbols",
        "missing_jackpot",
        "jackpot_reel_shortfall",
        "jackpot_spins",
        "jackpot_probability",
        "symbol_winning_spins",
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
                "feasible": individual["constraint_count"] == 0,
                "constraint_count": individual["constraint_count"],
                "constraint_violation": individual[
                    "constraint_violation"
                ],
                "rtp": individual["rtp"],
                "rtp_error": individual["rtp_error"],
                "win_rate": individual["win_rate"],
                "win_rate_shortfall": individual[
                    "win_rate_shortfall"
                ],
                "symbol_concentration": individual[
                    "symbol_concentration"
                ],
                "missing_symbols": individual["missing_symbols"],
                "missing_jackpot": individual["missing_jackpot"],
                "jackpot_reel_shortfall": individual[
                    "jackpot_reel_shortfall"
                ],
                "jackpot_spins": individual["jackpot_spins"],
                "jackpot_probability": individual[
                    "jackpot_probability"
                ],
                "symbol_winning_spins": repr(
                    individual["symbol_winning_spins"]
                ),
                "reel_1": repr(individual["reels"][0]),
                "reel_2": repr(individual["reels"][1]),
                "reel_3": repr(individual["reels"][2]),
            })
    return output_path


def print_generation_summary(generation, pareto_front):
    """輸出當代 Pareto front 與推薦解摘要。"""
    feasible_count = sum(
        individual["constraint_count"] == 0
        for individual in pareto_front
    )
    recommended = select_recommended_solution(pareto_front)
    print(
        f"Generation {generation:3d} | "
        f"Pareto solutions={len(pareto_front)} | "
        f"feasible={feasible_count} | "
        f"constraint count={recommended['constraint_count']} | "
        f"violation={recommended['constraint_violation']:.6f} | "
        f"missing symbols={recommended['missing_symbols']} | "
        f"RTP={recommended['rtp']:.4%} | "
        f"win rate={recommended['win_rate']:.4%} | "
        f"concentration={recommended['symbol_concentration']:.6f} | "
        f"jackpot={recommended['jackpot_probability']:.6%}"
    )


def run_nsga2():
    """執行 NSGA-II，回傳 Pareto front 與推薦解。"""
    random.seed(RANDOM_SEED)
    clear_metrics_cache()
    population = [
        evaluate_reels(create_individual())
        for _ in range(POPULATION_SIZE)
    ]
    fronts = rank_and_assign_crowding(population)

    for generation in range(1, GENERATIONS + 1):
        offspring = create_offspring(population)
        population = environmental_selection(population + offspring)
        fronts = rank_and_assign_crowding(population)
        pareto_front = fronts[0]

        if generation == 1 or generation % PRINT_INTERVAL == 0:
            print_generation_summary(generation, pareto_front)

    pareto_front = fronts[0]
    output_path = save_pareto_front(pareto_front)
    recommended = select_recommended_solution(pareto_front)

    print(f"\nPareto front：{output_path}")
    print(f"Pareto solutions：{len(pareto_front)}")
    recommended_is_feasible = (
        recommended["constraint_count"] == 0
    )
    print(f"Recommended solution feasible: {recommended_is_feasible}")
    if not recommended_is_feasible:
        print(
            "警告：本次搜尋沒有找到同時符合 Win rate 與 Jackpot "
            "硬條件的解，請增加 generations、population 或更換 seed。"
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
        "Symbol winning spins: "
        + ", ".join(
            f"{symbol}={winning_spins}"
            for symbol, winning_spins in enumerate(
                recommended["symbol_winning_spins"]
            )
        )
    )
    print(
        f"Jackpot: {recommended['jackpot_spins']} spins "
        f"({recommended['jackpot_probability']:.6%})"
    )
    payout_statistics = calculate_winning_payout_statistics(
        recommended["reels"]
    )
    print_winning_payout_statistics(payout_statistics)
    return pareto_front, recommended


if __name__ == "__main__":
    run_nsga2()
