import csv
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from pathlib import Path

from ga_plot import save_ga_charts
from slot_game import (
    BET_AMOUNT,
    SYMBOL_MULTIPLIERS,
    calculate_game_statistics,
    calculate_winning_payout_statistics,
    print_winning_payout_statistics,
)


REEL_LENGTH = 12
POPULATION_SIZE = 200
GENERATIONS = 1000
ELITE_SIZE = 5
MUTATION_RATE = 0.04
PAIR_MUTATION_RATE = 0.25
SWAP_MUTATION_RATE = 0.15
STAGNATION_LIMIT = 20
BOOSTED_MUTATION_RATE = 0.15
BOOSTED_PAIR_MUTATION_RATE = 0.30
BOOSTED_SWAP_MUTATION_RATE = 0.30
BOOST_DURATION = 10
IMMIGRANT_RATIO = 0.25
TARGET_RTP = 0.95
MIN_WIN_RATE = 0.55
RTP_TOLERANCE = 0.01
RANDOM_SEED = 42
PRINT_INTERVAL = 10
USE_MULTIPROCESSING = True
MAX_WORKERS = min(8, os.cpu_count() or 1)

METRICS_CACHE = {}


def clear_metrics_cache():
    METRICS_CACHE.clear()


def reel_key(reels):
    return tuple(tuple(reel) for reel in reels)


def create_individual():
    """Create three random reels with a fixed length."""
    return [
        [
            random.choice(tuple(SYMBOL_MULTIPLIERS))
            for _ in range(REEL_LENGTH)
        ]
        for _ in range(3)
    ]


def crossover(parent_a, parent_b):
    """Apply single-point crossover to each reel."""
    child = []
    for reel_index in range(3):
        reel_length = len(parent_a[reel_index])
        cut = random.randint(1, reel_length - 1)
        child.append(
            parent_a[reel_index][:cut]
            + parent_b[reel_index][cut:]
        )
    return child


def mutate(
    reels,
    mutation_rate=MUTATION_RATE,
    pair_rate=PAIR_MUTATION_RATE,
    swap_rate=SWAP_MUTATION_RATE,
):
    """Apply single-symbol, adjacent-pair, and swap mutations."""
    symbols = tuple(SYMBOL_MULTIPLIERS)
    for reel in reels:
        reel_length = len(reel)
        for position in range(reel_length):
            if random.random() < mutation_rate:
                old_symbol = reel[position]
                reel[position] = random.choice([
                    symbol for symbol in symbols
                    if symbol != old_symbol
                ])

        if random.random() < pair_rate:
            position_a = random.randrange(reel_length)
            position_b = (position_a + 1) % reel_length
            new_symbol = random.choice(symbols)
            reel[position_a] = new_symbol
            reel[position_b] = new_symbol

        if random.random() < swap_rate:
            position_a, position_b = random.sample(
                range(reel_length),
                2,
            )
            reel[position_a], reel[position_b] = (
                reel[position_b],
                reel[position_a],
            )


def calculate_symbol_concentration(reels):
    """Measure reel concentration with symbol-frequency HHI."""
    reel_concentrations = []
    symbols = tuple(SYMBOL_MULTIPLIERS)
    for reel in reels:
        reel_length = len(reel)
        if reel_length == 0:
            raise ValueError("A reel cannot be empty.")
        reel_concentrations.append(sum(
            (reel.count(symbol) / reel_length) ** 2
            for symbol in symbols
        ))
    if not reel_concentrations:
        raise ValueError("The reels list cannot be empty.")
    return sum(reel_concentrations) / len(reel_concentrations)


def evaluate_metrics(reels):
    """Fully enumerate the reels and return the shared exact metrics."""
    key = reel_key(reels)
    if key in METRICS_CACHE:
        return METRICS_CACHE[key]

    (
        total_spins,
        winning_spins,
        total_payout,
        rtp,
        win_rate,
        _symbol_statistics,
        payout_statistics,
    ) = calculate_game_statistics(
        reels,
        include_payout_statistics=True,
    )
    jackpot_spins = payout_statistics["jackpot_spins"]
    metrics = {
        "total_spins": total_spins,
        "winning_spins": winning_spins,
        "total_payout": total_payout,
        "rtp": rtp,
        "rtp_error": abs(rtp - TARGET_RTP),
        "rtp_violation": max(
            0,
            abs(rtp - TARGET_RTP) - RTP_TOLERANCE,
        ),
        "win_rate": win_rate,
        "win_rate_shortfall": max(0, MIN_WIN_RATE - win_rate),
        "symbol_concentration": calculate_symbol_concentration(
            reels
        ),
        "jackpot_spins": jackpot_spins,
        "jackpot_probability": jackpot_spins / total_spins,
        "missing_jackpot": int(jackpot_spins == 0),
    }
    METRICS_CACHE[key] = metrics
    return metrics


def create_evaluation_executor():
    """Create one process pool for the run, or an empty context if disabled."""
    if not USE_MULTIPROCESSING or MAX_WORKERS <= 1:
        return nullcontext(None)
    return ProcessPoolExecutor(max_workers=MAX_WORKERS)


def evaluate_population(reels_population, executor=None):
    """Evaluate unique reels in batches and cache them in the main process."""
    keys = [reel_key(reels) for reels in reels_population]
    pending = {}
    for key, reels in zip(keys, reels_population):
        if key not in METRICS_CACHE and key not in pending:
            pending[key] = reels

    if pending:
        pending_keys = list(pending)
        pending_reels = [pending[key] for key in pending_keys]
        if executor is None:
            results = map(evaluate_metrics, pending_reels)
        else:
            results = executor.map(evaluate_metrics, pending_reels)
        for key, metrics in zip(pending_keys, results):
            METRICS_CACHE[key] = metrics

    return [METRICS_CACHE[key] for key in keys]


def save_history(history, results_directory):
    """Write each generation's representative result to CSV."""
    results_directory = Path(results_directory)
    results_directory.mkdir(exist_ok=True)
    output_path = results_directory / "ga_history.csv"
    fieldnames = [
        "generation",
        "algorithm",
        "fitness_mode",
        "primary_fitness",
        "weighted_error",
        "missing_jackpot",
        "jackpot_spins",
        "jackpot_probability",
        "symbol_concentration",
        "win_rate_shortfall",
        "rtp_error",
        "rtp",
        "win_rate",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)
    return output_path


def save_best_solution(
    *,
    algorithm_name,
    generation,
    reels,
    metrics,
    score,
    payout_statistics,
    results_directory,
):
    """Save the final solution and everything needed by the report charts."""
    results_directory = Path(results_directory)
    results_directory.mkdir(exist_ok=True)
    output_path = results_directory / "best_solution.json"
    payout_distribution = [
        {
            "payout": payout,
                "payout_multiplier": payout / BET_AMOUNT,
            **statistics,
        }
        for payout, statistics in (
            payout_statistics["payout_distribution"].items()
        )
    ]
    payload = {
        "algorithm": algorithm_name,
        "generation": generation,
        "fitness_score": list(score),
        "reels": reels,
        "metrics": metrics,
        "payout_statistics": {
            **payout_statistics,
            "payout_distribution": payout_distribution,
        },
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def local_search(reels, fitness_function):
    """Try every one-position replacement around the current solution."""
    best_reels = [reel[:] for reel in reels]
    best_metrics = evaluate_metrics(best_reels)
    best_score = fitness_function(best_metrics)
    for reel_index, reel in enumerate(reels):
        for position, old_symbol in enumerate(reel):
            for new_symbol in SYMBOL_MULTIPLIERS:
                if new_symbol == old_symbol:
                    continue
                candidate = [candidate_reel[:] for candidate_reel in reels]
                candidate[reel_index][position] = new_symbol
                candidate_metrics = evaluate_metrics(candidate)
                candidate_score = fitness_function(candidate_metrics)
                if candidate_score < best_score:
                    best_reels = candidate
                    best_metrics = candidate_metrics
                    best_score = candidate_score
    return best_reels, best_metrics, best_score


def print_metrics(generation, reels, metrics, score):
    for reel in reels:
        print(reel)
    print(
        f"Generation {generation:3d} | score={score} | "
        f"RTP={metrics['rtp']:.4%} | "
        f"win rate={metrics['win_rate']:.4%} | "
        f"concentration={metrics['symbol_concentration']:.6f} | "
        f"jackpot={metrics['jackpot_spins']} "
        f"({metrics['jackpot_probability']:.6%})"
    )


def run_single_objective_ga(**kwargs):
    """Create one shared executor and run a single-objective GA."""
    with create_evaluation_executor() as executor:
        return _run_single_objective_ga(executor=executor, **kwargs)


def _run_single_objective_ga(
    *,
    executor,
    algorithm_name,
    fitness_function,
    target_reached,
    results_directory,
    fitness_components,
    repair_function=None,
    population_factory=None,
):
    """Run the generation loop shared by both single-objective GAs."""
    random.seed(RANDOM_SEED)
    clear_metrics_cache()
    population = (
        population_factory()
        if population_factory is not None
        else [create_individual() for _ in range(POPULATION_SIZE)]
    )
    if len(population) != POPULATION_SIZE:
        raise ValueError(
            "population_factory must create exactly "
            f"{POPULATION_SIZE} individuals."
        )
    history = []
    best_score_so_far = None
    generations_without_improvement = 0
    boost_generations_remaining = 0

    print(f"\nAlgorithm: {algorithm_name}")
    print(f"Fitness components: {' + '.join(fitness_components)}\n")
    print(
        "Evaluation: "
        + (
            f"multiprocessing ({MAX_WORKERS} workers)"
            if executor is not None
            else "single process"
        )
    )

    for generation in range(1, GENERATIONS + 1):
        metrics_list = evaluate_population(population, executor)
        evaluated = [
            (fitness_function(metrics), metrics, reels)
            for reels, metrics in zip(population, metrics_list)
        ]
        evaluated.sort(key=lambda item: item[0])
        best_score, best_metrics, best_reels = evaluated[0]

        if best_score_so_far is None or best_score < best_score_so_far:
            best_score_so_far = best_score
            generations_without_improvement = 0
            boost_generations_remaining = 0
        else:
            generations_without_improvement += 1

        stagnation_triggered = (
            generations_without_improvement >= STAGNATION_LIMIT
        )
        if stagnation_triggered:
            boost_generations_remaining = BOOST_DURATION
            (
                local_reels,
                local_metrics,
                local_score,
            ) = local_search(best_reels, fitness_function)
            if local_score < best_score:
                best_reels = local_reels
                best_metrics = local_metrics
                best_score = local_score
                best_score_so_far = local_score
                evaluated[0] = (
                    local_score,
                    local_metrics,
                    local_reels,
                )
                evaluated.sort(key=lambda item: item[0])

        if generation == 1 or generation % PRINT_INTERVAL == 0:
            print_metrics(
                generation,
                best_reels,
                best_metrics,
                best_score,
            )

        history.append({
            "generation": generation,
            "algorithm": algorithm_name,
            "fitness_mode": "single-objective",
            "primary_fitness": best_score[0],
            "weighted_error": best_score[0],
            "missing_jackpot": best_metrics["missing_jackpot"],
            "jackpot_spins": best_metrics["jackpot_spins"],
            "jackpot_probability": best_metrics[
                "jackpot_probability"
            ],
            "symbol_concentration": best_metrics[
                "symbol_concentration"
            ],
            "win_rate_shortfall": best_metrics[
                "win_rate_shortfall"
            ],
            "rtp_error": best_metrics["rtp_error"],
            "rtp": best_metrics["rtp"],
            "win_rate": best_metrics["win_rate"],
        })
        history_path = save_history(history, results_directory)

        if target_reached(best_metrics):
            break

        if boost_generations_remaining > 0:
            mutation_rate = BOOSTED_MUTATION_RATE
            pair_rate = BOOSTED_PAIR_MUTATION_RATE
            swap_rate = BOOSTED_SWAP_MUTATION_RATE
        else:
            mutation_rate = MUTATION_RATE
            pair_rate = PAIR_MUTATION_RATE
            swap_rate = SWAP_MUTATION_RATE

        next_population = [
            [reel[:] for reel in reels]
            for _, _, reels in evaluated[:ELITE_SIZE]
        ]
        parent_pool = [
            reels
            for _, _, reels in evaluated[:POPULATION_SIZE // 2]
        ]
        immigrant_count = (
            int(POPULATION_SIZE * IMMIGRANT_RATIO)
            if stagnation_triggered
            else 0
        )
        while len(next_population) < POPULATION_SIZE - immigrant_count:
            parent_a, parent_b = random.sample(parent_pool, 2)
            child = crossover(parent_a, parent_b)
            mutate(
                child,
                mutation_rate=mutation_rate,
                pair_rate=pair_rate,
                swap_rate=swap_rate,
            )
            if repair_function is not None:
                repair_function(child)
            next_population.append(child)
        next_population.extend(
            create_individual()
            for _ in range(immigrant_count)
        )
        population = next_population
        if stagnation_triggered:
            generations_without_improvement = 0
        if boost_generations_remaining > 0:
            boost_generations_remaining -= 1

    payout_statistics = calculate_winning_payout_statistics(best_reels)
    best_solution_path = save_best_solution(
        algorithm_name=algorithm_name,
        generation=generation,
        reels=best_reels,
        metrics=best_metrics,
        score=best_score,
        payout_statistics=payout_statistics,
        results_directory=results_directory,
    )
    chart_paths = save_ga_charts(history_path)
    print(f"\nHistory: {history_path}")
    print(f"Best solution: {best_solution_path}")
    print(f"Convergence chart: {chart_paths[0]}")
    print(f"Metrics chart: {chart_paths[1]}")
    print(f"Prize distribution chart: {chart_paths[2]}")
    print(f"Reel symbol distribution chart: {chart_paths[3]}")
    print("\nBest reels:")
    print_metrics(generation, best_reels, best_metrics, best_score)
    print_winning_payout_statistics(payout_statistics)
    return best_reels, best_metrics, best_score
