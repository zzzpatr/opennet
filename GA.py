"""相容入口；原題 baseline 請直接使用 GA_baseline.py。"""

from GA_baseline import run_ga_baseline


def run_ga():
    print(
        "GA.py 現在是相容入口，實際執行 GA_baseline.py。\n"
        "遊戲設計版本請執行 GA_game_design.py。"
    )
    return run_ga_baseline()


if __name__ == "__main__":
    run_ga()
