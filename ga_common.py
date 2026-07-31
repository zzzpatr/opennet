import csv
import json
import random
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
GENERATIONS = 500
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
MISSING_SYMBOL_REPAIR_RATE = 0.8
TARGET_RTP = 0.95
MIN_WIN_RATE = 0.55
RTP_TOLERANCE = 0.01
RANDOM_SEED = 42
PRINT_INTERVAL = 10

METRICS_CACHE = {}


def clear_metrics_cache():
    METRICS_CACHE.clear()


def reel_key(reels):
    return tuple(tuple(reel) for reel in reels)


def create_individual():
    """隨機建立三條固定長度 reels。"""
    return [
        [
            random.choice(tuple(SYMBOL_MULTIPLIERS))
            for _ in range(REEL_LENGTH)
        ]
        for _ in range(3)
    ]


def crossover(parent_a, parent_b):
    """每條 reel 使用單點 crossover。"""
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
    """執行單格、相鄰 pair 與 swap mutation。"""
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


def repair_missing_symbol(
    reels,
    metrics=None,
    repair_rate=MISSING_SYMBOL_REPAIR_RATE,
):
    """替一個無法中獎的 symbol 在相鄰兩條 reels 建立 pair。"""
    if random.random() >= repair_rate:
        return False
    if metrics is None:
        metrics = evaluate_metrics(reels)

    missing_symbols = [
        symbol
        for symbol, winning_spins in enumerate(
            metrics["symbol_winning_spins"]
        )
        if winning_spins == 0
    ]
    if not missing_symbols:
        return False

    target_symbol = random.choice(missing_symbols)
    reel_pair = random.choice(((0, 1), (1, 2)))
    for reel_index in reel_pair:
        reel = reels[reel_index]
        start = random.randrange(len(reel))
        reel[start] = target_symbol
        reel[(start + 1) % len(reel)] = target_symbol
    return True


def calculate_symbol_concentration(symbol_winning_spins):
    """以 HHI 衡量 symbol winning-spins 集中程度。"""
    total_wins = sum(symbol_winning_spins)
    if total_wins == 0:
        return 1.0
    return sum(
        (winning_spins / total_wins) ** 2
        for winning_spins in symbol_winning_spins
    )


def calculate_jackpot_reel_shortfall(reels):
    """最佳 symbol 還缺幾條 reels 才能各自形成連續三格。"""
    capable_reel_counts = []
    for symbol in SYMBOL_MULTIPLIERS:
        capable_reels = 0
        for reel in reels:
            reel_length = len(reel)
            if any(
                all(
                    reel[(start + offset) % reel_length] == symbol
                    for offset in range(3)
                )
                for start in range(reel_length)
            ):
                capable_reels += 1
        capable_reel_counts.append(capable_reels)
    return 3 - max(capable_reel_counts)


def evaluate_metrics(reels):
    """完整枚舉 reels，回傳所有演算法共用的精確指標。"""
    key = reel_key(reels)
    if key in METRICS_CACHE:
        return METRICS_CACHE[key]

    (
        total_spins,
        winning_spins,
        total_payout,
        rtp,
        win_rate,
        symbol_statistics,
        payout_statistics,
    ) = calculate_game_statistics(
        reels,
        include_payout_statistics=True,
    )
    symbol_winning_spins = tuple(
        statistics["winning_spins"]
        for statistics in symbol_statistics.values()
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
        "symbol_winning_spins": symbol_winning_spins,
        "missing_symbols": sum(
            winning_spins == 0
            for winning_spins in symbol_winning_spins
        ),
        "symbol_concentration": calculate_symbol_concentration(
            symbol_winning_spins
        ),
        "jackpot_spins": jackpot_spins,
        "jackpot_probability": jackpot_spins / total_spins,
        "missing_jackpot": int(jackpot_spins == 0),
        "jackpot_reel_shortfall": calculate_jackpot_reel_shortfall(
            reels
        ),
    }
    METRICS_CACHE[key] = metrics
    return metrics


def save_history(history, results_directory):
    """將每代最佳解寫入 CSV。"""
    results_directory = Path(results_directory)
    results_directory.mkdir(exist_ok=True)
    output_path = results_directory / "ga_history.csv"
    fieldnames = [
        "generation",
        "algorithm",
        "fitness_mode",
        "fitness_priority",
        "fitness_score",
        "primary_fitness",
        "weighted_error",
        "missing_jackpot",
        "jackpot_spins",
        "jackpot_probability",
        "missing_symbols",
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
    """保存最後一代最佳解及報告繪圖需要的完整資料。"""
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
        "metrics": {
            **metrics,
            "symbol_winning_spins": list(
                metrics["symbol_winning_spins"]
            ),
        },
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
    """檢查所有單格 replacement 鄰居。"""
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
        f"missing symbols={metrics['missing_symbols']} | "
        f"concentration={metrics['symbol_concentration']:.6f} | "
        f"jackpot={metrics['jackpot_spins']} "
        f"({metrics['jackpot_probability']:.6%})"
    )


def run_single_objective_ga(
    *,
    algorithm_name,
    fitness_function,
    target_reached,
    results_directory,
    fitness_mode,
    fitness_priority,
    primary_fitness,
    repair_function=None,
):
    """執行兩個普通 GA 共用的世代流程。"""
    random.seed(RANDOM_SEED)
    clear_metrics_cache()
    population = [create_individual() for _ in range(POPULATION_SIZE)]
    history = []
    best_score_so_far = None
    generations_without_improvement = 0
    boost_generations_remaining = 0

    print(f"\nAlgorithm: {algorithm_name}")
    print(f"Fitness: {' > '.join(fitness_priority)}\n")

    for generation in range(1, GENERATIONS + 1):
        evaluated = []
        for reels in population:
            metrics = evaluate_metrics(reels)
            evaluated.append(
                (fitness_function(metrics), metrics, reels)
            )
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
            "fitness_mode": fitness_mode,
            "fitness_priority": ">".join(fitness_priority),
            "fitness_score": repr(best_score),
            "primary_fitness": primary_fitness(
                best_score,
                best_metrics,
            ),
            "weighted_error": primary_fitness(
                best_score,
                best_metrics,
            ),
            "missing_jackpot": best_metrics["missing_jackpot"],
            "jackpot_spins": best_metrics["jackpot_spins"],
            "jackpot_probability": best_metrics[
                "jackpot_probability"
            ],
            "missing_symbols": best_metrics["missing_symbols"],
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
    print(f"Symbol winning chart: {chart_paths[3]}")
    print("\nBest reels:")
    print_metrics(generation, best_reels, best_metrics, best_score)
    print_winning_payout_statistics(payout_statistics)
    return best_reels, best_metrics, best_score
