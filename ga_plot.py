import csv
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

    integer_fields = {"generation", "missing_symbols"}
    float_fields = {
        "weighted_error",
        "win_rate_shortfall",
        "rtp_error",
        "rtp",
        "win_rate",
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
        priority = ("missing_symbols", "win_rate", "rtp")
    return fitness_mode, priority


def save_ga_charts(
    history_path=DEFAULT_HISTORY_PATH,
    results_directory=None,
):
    """讀取完整 GA history，輸出 Plotly 收斂圖與指標變化圖。"""
    history_path = Path(history_path)
    history = load_ga_history(history_path)
    fitness_mode, priority = infer_fitness_settings(history)
    if results_directory is None:
        results_directory = history_path.parent
    results_directory = Path(results_directory)
    results_directory.mkdir(exist_ok=True)

    if fitness_mode == "weighted":
        convergence_series = [("Weighted fitness", "weighted_error")]
    else:
        label_by_name = {
            "missing_symbols": "Fitness: missing symbols",
            "win_rate": "Fitness: win-rate shortfall",
            "rtp": "Fitness: RTP error",
        }
        history_key_by_name = {
            "missing_symbols": "missing_symbols",
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
            ("Missing symbols", "missing_symbols"),
            ("Win-rate shortfall", "win_rate_shortfall"),
            ("RTP error", "rtp_error"),
            ("RTP", "rtp"),
            ("Win rate", "win_rate"),
        ],
    )

    convergence_path = results_directory / "ga_convergence.png"
    metrics_path = results_directory / "ga_metrics.png"
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
    return convergence_path, metrics_path


if __name__ == "__main__":
    paths = save_ga_charts()
    print("收斂圖：", paths[0])
    print("指標變化圖：", paths[1])
