import argparse
import csv
import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from slot_game import SYMBOL_MULTIPLIERS


DEFAULT_HISTORY_PATH = Path(
    "ga_weighted_game_design_results/ga_history.csv"
)


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


def create_reel_symbol_distribution_figure(best_solution):
    """建立各 reel 的 symbol 數量與占比分布圖。"""
    reels = best_solution["reels"]
    symbols = tuple(SYMBOL_MULTIPLIERS)
    labels = [f"Symbol {symbol}" for symbol in symbols]
    figure = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.18,
        subplot_titles=("Symbol counts by reel", "Symbol shares by reel"),
    )
    colors = ["#2563eb", "#dc2626", "#059669"]
    for reel_index, reel in enumerate(reels):
        counts = [reel.count(symbol) for symbol in symbols]
        shares = [count / len(reel) for count in counts]
        name = f"Reel {reel_index + 1}"
        figure.add_trace(
            go.Bar(
                x=labels,
                y=counts,
                marker_color=colors[reel_index % len(colors)],
                text=[str(count) for count in counts],
                textposition="inside",
                name=name,
                legendgroup=name,
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Bar(
                x=labels,
                y=shares,
                marker_color=colors[reel_index % len(colors)],
                text=[f"{share:.1%}" for share in shares],
                textposition="inside",
                name=name,
                legendgroup=name,
                showlegend=False,
            ),
            row=2,
            col=1,
        )
    figure.update_yaxes(title_text="Count", row=1, col=1)
    figure.update_yaxes(
        title_text="Share",
        tickformat=".0%",
        row=2,
        col=1,
    )
    figure.update_layout(
        title=(
            f"{best_solution['algorithm']} - Reel Symbol Distribution "
            f"(Generation {best_solution['generation']})"
        ),
        barmode="stack",
        height=850,
        template="plotly_white",
    )
    return figure


def add_metric_target_lines(figure, best_solution):
    """在四個核心 metrics 子圖加入遊戲設計目標線。"""
    metrics = best_solution["metrics"]
    reel_length = len(best_solution["reels"][0])
    symbol_count = len(SYMBOL_MULTIPLIERS)
    base_count, remainder = divmod(reel_length, symbol_count)
    minimum_concentration = (
        remainder * (base_count + 1) ** 2
        + (symbol_count - remainder) * base_count ** 2
    ) / reel_length ** 2
    jackpot_target = 1 / metrics["total_spins"]
    targets = (
        (jackpot_target, "Target: at least 1 spin"),
        (minimum_concentration, "Theoretical minimum"),
        (0.95, "Target: 95%"),
        (0.55, "Target: 55%"),
    )
    for row, (target, label) in enumerate(targets, start=1):
        figure.add_hline(
            y=target,
            line_dash="dash",
            line_color="#111827",
            line_width=1.5,
            annotation_text=label,
            annotation_position="top right",
            row=row,
            col=1,
        )
    figure.update_yaxes(tickformat=".2%", row=1, col=1)
    figure.update_yaxes(tickformat=".4f", row=2, col=1)
    figure.update_yaxes(tickformat=".2%", row=3, col=1)
    figure.update_yaxes(tickformat=".2%", row=4, col=1)
    return figure


def save_ga_charts(
    history_path=DEFAULT_HISTORY_PATH,
    results_directory=None,
):
    """讀取完整 GA history，輸出 Plotly 收斂圖與指標變化圖。"""
    history_path = Path(history_path)
    history = load_ga_history(history_path)
    best_solution = load_best_solution(history_path)
    fitness_mode = history[0]["fitness_mode"]
    algorithm_name = history[0].get("algorithm") or "GA"
    if results_directory is None:
        results_directory = history_path.parent
    results_directory = Path(results_directory)
    results_directory.mkdir(exist_ok=True)

    if fitness_mode == "multi-objective":
        convergence_series = [
            ("Selected weighted score", "weighted_error")
        ]
    else:
        convergence_series = [("Primary fitness", "primary_fitness")]

    convergence_figure = add_series_figure(
        history,
        f"{algorithm_name} Fitness Convergence",
        convergence_series,
    )
    metrics_figure = add_series_figure(
        history,
        f"{algorithm_name} Metrics by Generation",
        [
            ("Jackpot probability", "jackpot_probability"),
            ("Symbol concentration", "symbol_concentration"),
            ("RTP", "rtp"),
            ("Win rate", "win_rate"),
        ],
    )
    add_metric_target_lines(metrics_figure, best_solution)

    convergence_path = results_directory / "ga_convergence.png"
    metrics_path = results_directory / "ga_metrics.png"
    prize_distribution_path = (
        results_directory / "ga_prize_distribution.png"
    )
    reel_symbol_distribution_path = (
        results_directory / "ga_reel_symbol_distribution.png"
    )
    prize_distribution_figure = create_prize_distribution_figure(
        best_solution
    )
    reel_symbol_distribution_figure = (
        create_reel_symbol_distribution_figure(best_solution)
    )
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
    reel_symbol_distribution_figure.write_image(
        reel_symbol_distribution_path,
        format="png",
        scale=2,
    )
    return (
        convergence_path,
        metrics_path,
        prize_distribution_path,
        reel_symbol_distribution_path,
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
    print("Reel symbol 分布圖：", paths[3])
