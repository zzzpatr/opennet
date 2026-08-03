import random
from pathlib import Path

from ga_common import (
    POPULATION_SIZE,
    REEL_LENGTH,
    create_individual,
    run_single_objective_ga,
)
from slot_game import SYMBOL_MULTIPLIERS


RTP_VIOLATION_SCALE = 0.01
WIN_RATE_VIOLATION_SCALE = 0.01
CONCENTRATION_WEIGHT = 30

BALANCED_INITIALIZATION_RATIO = 0.50
JACKPOT_REPAIR_RATE = 0.1
RESULTS_DIRECTORY = Path("ga_weighted_game_design_results")
SYMBOLS = tuple(SYMBOL_MULTIPLIERS)


def minimum_symbol_concentration():
    """回傳目前 reel 長度能達到的最低 symbol-frequency HHI。"""
    base_count, remainder = divmod(REEL_LENGTH, len(SYMBOLS))
    squared_counts = (
        remainder * (base_count + 1) ** 2
        + (len(SYMBOLS) - remainder) * base_count ** 2
    )
    return squared_counts / REEL_LENGTH ** 2


MIN_SYMBOL_CONCENTRATION = minimum_symbol_concentration()


def create_balanced_reel():
    """建立各 symbol 數量最多只差一個的 reel。"""
    base_count, remainder = divmod(REEL_LENGTH, len(SYMBOLS))
    extra_symbols = set(random.sample(SYMBOLS, remainder))
    reel = [
        symbol
        for symbol in SYMBOLS
        for _ in range(base_count + int(symbol in extra_symbols))
    ]
    random.shuffle(reel)
    return reel


def create_balanced_individual():
    return [create_balanced_reel() for _ in range(3)]


def create_initial_population():
    """以 balanced 與 random individuals 各建立一半初始族群。"""
    balanced_count = int(
        POPULATION_SIZE * BALANCED_INITIALIZATION_RATIO
    )
    population = (
        [create_balanced_individual() for _ in range(balanced_count)]
        + [
            create_individual()
            for _ in range(POPULATION_SIZE - balanced_count)
        ]
    )
    random.shuffle(population)
    return population


def best_triple_window(reel, symbol):
    """找出在 circular reel 建立指定 symbol triple 的最少修改位置。"""
    candidates = []
    for start in range(len(reel)):
        positions = tuple(
            (start + offset) % len(reel)
            for offset in range(3)
        )
        changes = sum(reel[position] != symbol for position in positions)
        candidates.append((changes, positions))
    minimum_changes = min(changes for changes, _ in candidates)
    return random.choice([
        candidate
        for candidate in candidates
        if candidate[0] == minimum_changes
    ])


def repair_missing_jackpot(reels):
    """偶爾以最少 replacements 建立三條 reels 的共同 triple。"""
    if random.random() >= JACKPOT_REPAIR_RATE:
        return False

    repair_options = []
    for symbol in SYMBOLS:
        windows = [best_triple_window(reel, symbol) for reel in reels]
        repair_options.append((
            sum(changes for changes, _ in windows),
            symbol,
            windows,
        ))

    minimum_changes = min(option[0] for option in repair_options)
    _, target_symbol, target_windows = random.choice([
        option
        for option in repair_options
        if option[0] == minimum_changes
    ])
    if minimum_changes == 0:
        return False

    for reel, (_, positions) in zip(reels, target_windows):
        for position in positions:
            reel[position] = target_symbol
    return True


def calculate_objective_penalties(metrics):
    """回傳 Weighted GA 與 NSGA-II 共用的四個目標分數。"""
    concentration_penalty = max(
        0.0,
        (
            metrics["symbol_concentration"]
            - MIN_SYMBOL_CONCENTRATION
        )
        / (1.0 - MIN_SYMBOL_CONCENTRATION),
    )
    return (
        metrics["rtp_violation"] / RTP_VIOLATION_SCALE,
        metrics["win_rate_shortfall"] / WIN_RATE_VIOLATION_SCALE,
        metrics["missing_jackpot"],
        CONCENTRATION_WEIGHT * concentration_penalty,
    )


def weighted_game_design_fitness(metrics):
    """將四個目標相加為 Weighted GA 的單一 fitness。"""
    return (sum(calculate_objective_penalties(metrics)),)


def run_ga_weighted_game_design():
    return run_single_objective_ga(
        algorithm_name="GA weighted game design",
        fitness_function=weighted_game_design_fitness,
        # Concentration 是持續改善的軟目標，因此執行完整 generations。
        target_reached=lambda _: False,
        results_directory=RESULTS_DIRECTORY,
        fitness_components=(
            "rtp_violation_penalty",
            "win_rate_shortfall_penalty",
            "missing_jackpot_penalty",
            "symbol_concentration_penalty",
        ),
        repair_function=repair_missing_jackpot,
        population_factory=create_initial_population,
    )


if __name__ == "__main__":
    run_ga_weighted_game_design()
