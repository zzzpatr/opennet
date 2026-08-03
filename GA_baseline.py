from pathlib import Path

from ga_common import (
    MIN_WIN_RATE,
    RTP_TOLERANCE,
    run_single_objective_ga,
)


WIN_RATE_WEIGHT = 5.0
RESULTS_DIRECTORY = Path("ga_baseline_results")


def baseline_fitness(metrics):
    """Score a candidate using only the assignment's RTP and win-rate goals."""
    weighted_error = (
        metrics["rtp_error"]
        + WIN_RATE_WEIGHT * metrics["win_rate_shortfall"]
    )
    return (weighted_error,)


def baseline_target_reached(metrics):
    """Stop when RTP is near 95% and win rate is at least 55%."""
    return (
        metrics["rtp_error"] <= RTP_TOLERANCE
        and metrics["win_rate"] >= MIN_WIN_RATE
    )


def run_ga_baseline():
    return run_single_objective_ga(
        algorithm_name="GA baseline",
        fitness_function=baseline_fitness,
        target_reached=baseline_target_reached,
        results_directory=RESULTS_DIRECTORY,
        fitness_components=("rtp_error", "win_rate_shortfall"),
    )


if __name__ == "__main__":
    run_ga_baseline()
