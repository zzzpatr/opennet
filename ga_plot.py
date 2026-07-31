import argparse
import csv
import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots


DEFAULT_HISTORY_PATH = Path("ga_results/ga_history.csv")


def load_ga_history(history_path=DEFAULT_HISTORY_PATH):
    """讀取 GA CSV，並將繪圖欄位轉成數字。"""
    history_path = Path(history_path)
    with history_path.open(encoding="utf-8-sig", newline="") as file:
        history = list(csv.DictReader(file))

    if not history:
        raise ValueError(f"GA history 沒有資料：{history_path}")

    integer_fields = {
        "generation",
        "missing_jackpot",
        "jackpot_spins",
        "missing_symbols",
    }
    float_fields = {
        "primary_fitness",
        "weighted_error",
        "jackpot_probability",
        "win_rate_shortfall",
        "rtp_error",
        "rtp",
        "win_rate",
        "symbol_concentration",
    }
    for row in history:
        for field in integer_fields:
            row[field] = int(row[field])
        for field in float_fields:
            value = row.get(field, "")
            row[field] = float(value) if value != "" else None
    return history


def add_series_figure(history, title, series):
    """建立每項指標各自使用 Y 軸的 Plotly 子圖。"""
    figure = make_subplots(
        rows=len(series),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=min(0.08, 0.25 / len(series)),
        subplot_titles=[label for label, _ in series],
    )
    generations = [row["generation"] for row in history]
    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c"]

    for row_index, (label, key) in enumerate(series, start=1):
        figure.add_trace(
            go.Scatter(
                x=generations,
                y=[row[key] for row in history],
                mode="lines",
                name=label,
                line={"color": colors[(row_index - 1) % len(colors)]},
                hovertemplate=(
                    "Generation %{x}<br>"
                    + label
                    + ": %{y:.8g}<extra></extra>"
                ),
            ),
            row=row_index,
            col=1,
        )
        figure.update_yaxes(title_text=label, row=row_index, col=1)

    figure.update_xaxes(
        title_text="Generation",
        row=len(series),
        col=1,
    )
    figure.update_layout(
        title=title,
        height=max(420, 260 * len(series)),
        template="plotly_white",
        hovermode="x unified",
        showlegend=False,
    )
    return figure


def infer_fitness_settings(history):
    """由 CSV 推斷 fitness 模式及分層優先順序。"""
    fitness_mode = history[0]["fitness_mode"]
    stored_priority = history[0].get("fitness_priority", "")
    priority = tuple(
        name for name in stored_priority.split(">")
        if name
    )
    if not priority:
        priority = (
            "missing_jackpot",
            "missing_symbols",
            "win_rate",
            "rtp",
        )
    return fitness_mode, priority


def load_best_solution(history_path):
    """讀取與 history CSV 位於同一目錄的最終最佳解。"""
    solution_path = Path(history_path).parent / "best_solution.json"
    if not solution_path.exists():
        raise FileNotFoundError(
            f"找不到最終最佳解：{solution_path}；請先重新執行 GA。"
        )
    with solution_path.open(encoding="utf-8") as file:
        return json.load(file)


def create_prize_distribution_figure(best_solution):
    """建立精確 payout 與 prize-tier 分布圖。"""
    payout_statistics = best_solution["payout_statistics"]
    payout_distribution = payout_statistics["payout_distribution"]
    prize_tiers = payout_statistics["prize_tiers"]
    figure = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.18,
        subplot_titles=(
            "Exact payout distribution",
            "Prize-tier distribution",
        ),
    )
    payout_labels = [
        f"{item['payout_multiplier']:g}x"
        for item in payout_distribution
    ]
    figure.add_trace(
        go.Bar(
            x=payout_labels,
            y=[
                item["probability_among_wins"]
                for item in payout_distribution
            ],
            name="Probability among wins",
            marker_color="#2563eb",
            text=[
                f"{item['probability_among_wins']:.2%}"
                for item in payout_distribution
            ],
            textposition="outside",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=payout_labels,
            y=[item["payout_share"] for item in payout_distribution],
            name="Payout contribution",
            marker_color="#f97316",
            text=[
                f"{item['payout_share']:.2%}"
                for item in payout_distribution
            ],
            textposition="outside",
        ),
        row=1,
        col=1,
    )

    tier_names = list(prize_tiers)
    tier_labels = {
        "small": "Small",
        "medium": "Medium",
        "big": "Big",
        "super_big": "Super big",
    }
    tier_values = [
        prize_tiers[name]["probability_among_wins"]
        for name in tier_names
    ]
    figure.add_trace(
        go.Bar(
            x=[tier_labels.get(name, name) for name in tier_names],
            y=tier_values,
            name="Prize-tier probability",
            marker_color="#059669",
            text=[f"{value:.2%}" for value in tier_values],
            textposition="outside",
        ),
        row=2,
        col=1,
    )
    figure.update_yaxes(tickformat=".0%", row=1, col=1)
    figure.update_yaxes(tickformat=".0%", row=2, col=1)
    figure.update_xaxes(title_text="Payout / bet", row=1, col=1)
    figure.update_xaxes(title_text="Prize tier", row=2, col=1)
    figure.update_layout(
        title=(
            f"{best_solution['algorithm']} – Prize Distribution "
            f"(Generation {best_solution['generation']})"
        ),
        barmode="group",
        height=900,
        template="plotly_white",
    )
    return figure


def create_symbol_winning_figure(best_solution):
    """建立各 symbol winning-spins 次數與占比圖。"""
    winning_spins = best_solution["metrics"]["symbol_winning_spins"]
    total = sum(winning_spins)
    shares = [
        value / total if total else 0
        for value in winning_spins
    ]
    labels = [f"Symbol {index}" for index in range(len(winning_spins))]
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Winning spins", "Winning-spins share"),
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=winning_spins,
            marker_color="#7c3aed",
            text=[str(value) for value in winning_spins],
            textposition="outside",
            name="Winning spins",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=shares,
            marker_color="#dc2626",
            text=[f"{share:.2%}" for share in shares],
            textposition="outside",
            name="Share",
        ),
        row=1,
        col=2,
    )
    figure.update_yaxes(title_text="Spins", row=1, col=1)
    figure.update_yaxes(
        title_text="Share",
        tickformat=".0%",
        row=1,
        col=2,
    )
    figure.update_layout(
        title=(
            f"{best_solution['algorithm']} – Symbol Winning Distribution "
            f"(Generation {best_solution['generation']})"
        ),
        height=520,
        template="plotly_white",
        showlegend=False,
    )
    return figure


def save_ga_charts(
    history_path=DEFAULT_HISTORY_PATH,
    results_directory=None,
):
    """讀取完整 GA history，輸出 Plotly 收斂圖與指標變化圖。"""
    history_path = Path(history_path)
    history = load_ga_history(history_path)
    best_solution = load_best_solution(history_path)
    fitness_mode, priority = infer_fitness_settings(history)
    if results_directory is None:
        results_directory = history_path.parent
    results_directory = Path(results_directory)
    results_directory.mkdir(exist_ok=True)

    if history[0].get("primary_fitness") is not None:
        convergence_series = [("Primary fitness", "primary_fitness")]
    elif fitness_mode == "weighted":
        convergence_series = [("Weighted fitness", "weighted_error")]
    else:
        label_by_name = {
            "missing_symbols": "Fitness: missing symbols",
            "missing_jackpot": "Fitness: missing jackpot",
            "win_rate": "Fitness: win-rate shortfall",
            "rtp": "Fitness: RTP error",
        }
        history_key_by_name = {
            "missing_symbols": "missing_symbols",
            "missing_jackpot": "missing_jackpot",
            "win_rate": "win_rate_shortfall",
            "rtp": "rtp_error",
        }
        convergence_series = [
            (label_by_name[name], history_key_by_name[name])
            for name in priority
        ]

    convergence_figure = add_series_figure(
        history,
        "GA Fitness Convergence",
        convergence_series,
    )
    metrics_figure = add_series_figure(
        history,
        "GA Metrics by Generation",
        [
            ("Missing jackpot", "missing_jackpot"),
            ("Jackpot spins", "jackpot_spins"),
            ("Jackpot probability", "jackpot_probability"),
            ("Missing symbols", "missing_symbols"),
            ("Symbol concentration", "symbol_concentration"),
            ("Win-rate shortfall", "win_rate_shortfall"),
            ("RTP error", "rtp_error"),
            ("RTP", "rtp"),
            ("Win rate", "win_rate"),
        ],
    )

    convergence_path = results_directory / "ga_convergence.png"
    metrics_path = results_directory / "ga_metrics.png"
    prize_distribution_path = (
        results_directory / "ga_prize_distribution.png"
    )
    symbol_winning_path = (
        results_directory / "ga_symbol_winning_distribution.png"
    )
    prize_distribution_figure = create_prize_distribution_figure(
        best_solution
    )
    symbol_winning_figure = create_symbol_winning_figure(best_solution)
    convergence_figure.write_image(
        convergence_path,
        format="png",
        scale=2,
    )
    metrics_figure.write_image(
        metrics_path,
        format="png",
        scale=2,
    )
    prize_distribution_figure.write_image(
        prize_distribution_path,
        format="png",
        scale=2,
    )
    symbol_winning_figure.write_image(
        symbol_winning_path,
        format="png",
        scale=2,
    )
    return (
        convergence_path,
        metrics_path,
        prize_distribution_path,
        symbol_winning_path,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="依 GA history CSV 產生收斂與指標 PNG。",
    )
    parser.add_argument(
        "history_path",
        nargs="?",
        default=DEFAULT_HISTORY_PATH,
        help=(
            "ga_history.csv 路徑 "
            "（預設：ga_results/ga_history.csv）"
        ),
    )
    arguments = parser.parse_args()
    paths = save_ga_charts(arguments.history_path)
    print("收斂圖：", paths[0])
    print("指標變化圖：", paths[1])
    print("獎金分布圖：", paths[2])
    print("Symbol winning 分布圖：", paths[3])
