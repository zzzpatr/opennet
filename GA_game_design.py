from pathlib import Path

from ga_common import (
    MIN_WIN_RATE,
    RTP_TOLERANCE,
    repair_missing_symbol,
    run_single_objective_ga,
)


SYMBOL_CONCENTRATION_WEIGHT = 0.10
RESULTS_DIRECTORY = Path("ga_game_design_results")


def game_design_fitness(metrics):
    """硬條件分層後，以加權分數改善 RTP 與 symbol 集中度。"""
    constraint_count = (
        int(metrics["rtp_violation"] > 0)
        + int(metrics["win_rate_shortfall"] > 0)
        + metrics["missing_jackpot"]
        + int(metrics["missing_symbols"] > 0)
    )
    normalized_violation = (
        metrics["rtp_violation"] / RTP_TOLERANCE
        + metrics["win_rate_shortfall"] / MIN_WIN_RATE
        + metrics["jackpot_reel_shortfall"] / 3
        + metrics["missing_symbols"] / 5
    )
    design_score = (
        metrics["rtp_error"]
        + SYMBOL_CONCENTRATION_WEIGHT
        * metrics["symbol_concentration"]
    )
    return (
        metrics["missing_jackpot"],
        metrics["missing_symbols"],
        metrics["jackpot_reel_shortfall"],
        constraint_count,
        normalized_violation,
        design_score,
    )


def keep_searching_for_game_design(metrics):
    """沒有主觀 concentration 門檻，因此跑完整 generations。"""
    return False


def run_ga_game_design():
    return run_single_objective_ga(
        algorithm_name="GA game design",
        fitness_function=game_design_fitness,
        target_reached=keep_searching_for_game_design,
        results_directory=RESULTS_DIRECTORY,
        fitness_mode="hybrid",
        fitness_priority=(
            "missing_jackpot",
            "missing_symbols",
            "jackpot_reel_shortfall",
            "constraint_count",
            "constraint_violation",
            "rtp_error + symbol_concentration",
        ),
        primary_fitness=lambda score, metrics: score[-1],
        repair_function=repair_missing_symbol,
    )


if __name__ == "__main__":
    run_ga_game_design()
