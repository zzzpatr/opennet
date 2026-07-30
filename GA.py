import csv
import random
from pathlib import Path

from ga_plot import save_ga_charts
from slot_game import (
    calculate_game_statistics,
    calculate_winning_payout_statistics,
    print_winning_payout_statistics,
)


# 五種 symbol 都要能形成 2x2 中獎時，中間 reel 至少需要五組相鄰配對。







REEL_LENGTH = 12
POPULATION_SIZE = 200
GENERATIONS = 500
ELITE_SIZE = 5
MUTATION_RATE = 0.08
SWAP_MUTATION_RATE = 0.10
STAGNATION_LIMIT = 20
BOOSTED_MUTATION_RATE = 0.15
BOOSTED_SWAP_MUTATION_RATE = 0.30
BOOST_DURATION = 10
IMMIGRANT_RATIO = 0.25

PAIR_MUTATION_RATE = 0.15
BOOSTED_PAIR_MUTATION_RATE = 0.30


TARGET_RTP = 0.95
MIN_WIN_RATE = 0.55

# Fitness 模式："lexicographic"（分層排序）或 "weighted"（加權總和）。
FITNESS_MODE = "weighted"

# 分層 fitness 的比較順序；越前面的條件優先級越高。
# 可用名稱："missing_symbols"、"win_rate"、"rtp"
FITNESS_PRIORITY = (
    "missing_symbols",
    "win_rate",
    "rtp",
)

# 加權 fitness 的權重；分數越小越好。
FITNESS_WEIGHTS = {
    "missing_symbols": 1.0,
    "win_rate": 1.0,
    "rtp": 1.0,
}

RESULTS_DIRECTORY = Path("ga_results")

FITNESS_CACHE = {}


def get_fitness_mode():
    """驗證並回傳 fitness 模式。"""
    if FITNESS_MODE not in {"lexicographic", "weighted"}:
        raise ValueError(
            'FITNESS_MODE 必須是 "lexicographic" 或 "weighted"'
        )
    return FITNESS_MODE


def get_fitness_priority(include_missing_symbols):
    """依執行模式取得並驗證實際使用的 fitness 順序。"""
    valid_names = {"missing_symbols", "win_rate", "rtp"}
    priority = tuple(FITNESS_PRIORITY)

    if len(priority) != len(set(priority)):
        raise ValueError("FITNESS_PRIORITY 不可包含重複項目")
    unknown_names = set(priority) - valid_names
    if unknown_names:
        raise ValueError(
            "FITNESS_PRIORITY 包含無效名稱："
            + ", ".join(sorted(unknown_names))
            + "；請確認每個項目後面都有逗號"
        )
    required_names = {"win_rate", "rtp"}
    if not required_names.issubset(priority):
        raise ValueError(
            'FITNESS_PRIORITY 必須包含 "win_rate" 和 "rtp"'
        )

    if not include_missing_symbols:
        priority = tuple(
            name for name in priority
            if name != "missing_symbols"
        )
    elif "missing_symbols" not in priority:
        raise ValueError(
            "考量 missing symbols 時，FITNESS_PRIORITY "
            '必須包含 "missing_symbols"'
        )

    return priority


def get_fitness_weights(priority):
    """驗證並回傳目前實際使用的加權參數。"""
    missing_weights = set(priority) - set(FITNESS_WEIGHTS)
    if missing_weights:
        raise ValueError(
            "FITNESS_WEIGHTS 缺少權重："
            + ", ".join(sorted(missing_weights))
        )

    weights = tuple(FITNESS_WEIGHTS[name] for name in priority)
    if any(
        not isinstance(weight, (int, float)) or weight < 0
        for weight in weights
    ):
        raise ValueError("FITNESS_WEIGHTS 必須是大於等於 0 的數字")
    if not any(weights):
        raise ValueError("FITNESS_WEIGHTS 至少要有一個權重大於 0")
    return weights


def save_ga_history(history):
    """將每一代最佳解的 fitness 與原始指標寫入 CSV。"""
    RESULTS_DIRECTORY.mkdir(exist_ok=True)
    output_path = RESULTS_DIRECTORY / "ga_history.csv"
    fieldnames = [
        "generation",
        "fitness_mode",
        "fitness_priority",
        "fitness_score",
        "weighted_error",
        "missing_symbols",
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


def create_individual():
    """隨機建立三個 reels。"""
    return [
        [random.randint(0, 4) for _ in range(REEL_LENGTH)]
        for _ in range(3)
    ]


def fitness(reels, include_missing_symbols=True):
    """依所選模式回傳分層或加權 fitness 分數。"""
    mode = get_fitness_mode()
    priority = get_fitness_priority(include_missing_symbols)
    weights = (
        get_fitness_weights(priority)
        if mode == "weighted"
        else ()
    )
    key = (
        include_missing_symbols,
        mode,
        priority,
        weights,
        tuple(tuple(reel) for reel in reels),
    )
    if key in FITNESS_CACHE:
        return FITNESS_CACHE[key]

    (
        _,
        _,
        _,
        rtp,
        win_rate,
        symbol_statistics,
    ) = calculate_game_statistics(reels)

    rtp_error = abs(rtp - TARGET_RTP)
    win_rate_shortfall = max(0, MIN_WIN_RATE - win_rate)

    symbol_winning_spins = tuple(
        statistics["winning_spins"]
        for statistics in symbol_statistics.values()
    )
    missing_winning_symbol_count = sum(
        winning_spins == 0
        for winning_spins in symbol_winning_spins
    )
    score_by_name = {
        "missing_symbols": missing_winning_symbol_count,
        "win_rate": win_rate_shortfall,
        "rtp": rtp_error,
    }
    if mode == "lexicographic":
        fitness_score = tuple(
            score_by_name[name]
            for name in priority
        )
    else:
        weighted_error = sum(
            score_by_name[name] * weight
            for name, weight in zip(priority, weights)
        )
        fitness_score = (weighted_error,)

    result = (fitness_score, rtp, win_rate, symbol_winning_spins)
    FITNESS_CACHE[key] = result
    return result


def crossover(parent_a, parent_b):
    """使用單點切割，保留 parent 中連續的 symbol 區段。"""
    child = []

    for reel_index in range(3):
        cut = random.randint(1, REEL_LENGTH - 1)
        child_reel = (
            parent_a[reel_index][:cut]
            + parent_b[reel_index][cut:]
        )
        child.append(child_reel)

    return child


def mutate(
    reels,
    mutation_rate=MUTATION_RATE,
    pair_rate=PAIR_MUTATION_RATE,
    swap_rate=SWAP_MUTATION_RATE,
):
    """使用單格 replacement、相鄰 pair replacement 與 swap mutation。"""
    for reel in reels:
        # 模式一：替換 symbol，改變各 symbol 的數量。
        for position in range(REEL_LENGTH):
            if random.random() < mutation_rate:
                old_symbol = reel[position]
                possible_symbols = [
                    symbol for symbol in range(5)
                    if symbol != old_symbol
                ]
                reel[position] = random.choice(possible_symbols)

        # 模式二：將相鄰兩格替換為相同 symbol，支援 reel 首尾相鄰。
        if random.random() < pair_rate:
            position_a = random.randrange(REEL_LENGTH)
            position_b = (position_a + 1) % REEL_LENGTH
            old_pair = (reel[position_a], reel[position_b])
            possible_symbols = [
                symbol
                for symbol in range(5)
                if old_pair != (symbol, symbol)
            ]
            new_symbol = random.choice(possible_symbols)
            reel[position_a] = new_symbol
            reel[position_b] = new_symbol

        # 模式三：交換兩個位置，不改變數量，只改變相鄰順序。
        if random.random() < swap_rate:
            position_a, position_b = random.sample(
                range(REEL_LENGTH),
                2,
            )
            reel[position_a], reel[position_b] = (
                reel[position_b],
                reel[position_a],
            )


def local_search(reels, include_missing_symbols=True):
    """測試所有單格替換，回傳 reels 附近最好的結果。"""
    best_reels = [reel[:] for reel in reels]
    best_result = fitness(best_reels, include_missing_symbols)

    for reel_index in range(3):
        for position in range(REEL_LENGTH):
            old_symbol = reels[reel_index][position]

            for new_symbol in range(5):
                if new_symbol == old_symbol:
                    continue

                candidate = [reel[:] for reel in reels]
                candidate[reel_index][position] = new_symbol
                candidate_result = fitness(
                    candidate,
                    include_missing_symbols,
                )

                if candidate_result[0] < best_result[0]:
                    best_reels = candidate
                    best_result = candidate_result

    return best_reels, best_result


def choose_missing_symbols_mode():
    """讓使用者選擇 missing symbols 是否納入 fitness。"""
    print("請選擇 GA 搜尋模式：")
    print("  1. 考量 missing symbols（預設）")
    print("  2. 不考量 missing symbols")

    while True:
        choice = input("請輸入 1 或 2 [1]: ").strip()
        if choice in ("", "1"):
            return True
        if choice == "2":
            return False
        print("輸入無效，請輸入 1 或 2。")


def run_ga(include_missing_symbols=True):
    random.seed(42)
    population = [create_individual() for _ in range(POPULATION_SIZE)]
    fitness_mode = get_fitness_mode()
    priority = get_fitness_priority(include_missing_symbols)
    weights = (
        get_fitness_weights(priority)
        if fitness_mode == "weighted"
        else ()
    )
    score_length = len(priority) if fitness_mode == "lexicographic" else 1
    best_score_so_far = tuple(float("inf") for _ in range(score_length))
    generations_without_improvement = 0
    boost_generations_remaining = 0
    history = []
    mode_name = (
        "考量 missing symbols"
        if include_missing_symbols
        else "不考量 missing symbols"
    )
    print(f"\n執行模式：{mode_name}\n")
    if fitness_mode == "lexicographic":
        print("Fitness 模式：分層排序")
        print("Fitness 優先順序：" + " > ".join(priority) + "\n")
    else:
        weighted_terms = " + ".join(
            f"{name}*{weight:g}"
            for name, weight in zip(priority, weights)
        )
        print("Fitness 模式：加權總和")
        print("Fitness 公式：" + weighted_terms + "\n")

    for generation in range(1, GENERATIONS + 1):
        evaluated = [
            (fitness(reels, include_missing_symbols), reels)
            for reels in population
        ]
        evaluated.sort(key=lambda item: item[0][0])

        (
            best_score,
            best_rtp,
            best_win_rate,
            best_symbol_winning_spins,
        ), best_reels = evaluated[0]

        if best_score < best_score_so_far:
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

        if boost_generations_remaining > 0:
            current_mutation_rate = BOOSTED_MUTATION_RATE
            current_pair_rate = BOOSTED_PAIR_MUTATION_RATE
            current_swap_rate = BOOSTED_SWAP_MUTATION_RATE
        else:
            current_mutation_rate = MUTATION_RATE
            current_pair_rate = PAIR_MUTATION_RATE
            current_swap_rate = SWAP_MUTATION_RATE

        if generation == 1 or generation % 10 == 0:
            missing_symbol_count = sum(
                winning_spins == 0
                for winning_spins in best_symbol_winning_spins
            )
            for reel in best_reels:
                print(reel)
            status = (
                f"Generation {generation:3d} | "
                f"missing symbols={missing_symbol_count}"
            )
            if not include_missing_symbols:
                status += " (not in fitness)"
            print(
                status
                + f" | win rate shortfall="
                f"{max(0, MIN_WIN_RATE - best_win_rate):.6f} | "
                f"RTP error={abs(best_rtp - TARGET_RTP):.6f} | "
                f"RTP={best_rtp:.4f} | "
                f"win rate={best_win_rate:.4f} | "
                f"mutation={current_mutation_rate:.2f} | "
                f"pair mutation={current_pair_rate:.2f}"
            )
            print(
                "Symbol winning spins: "
                + ", ".join(
                    f"{symbol}={winning_spins}"
                    for symbol, winning_spins in enumerate(
                        best_symbol_winning_spins
                    )
                )
            )
            print(f"\n--- Generation {generation} 最佳解獎金統計 ---")
            generation_payout_statistics = (
                calculate_winning_payout_statistics(best_reels)
            )
            print_winning_payout_statistics(
                generation_payout_statistics
            )

        if stagnation_triggered:
            print(
                "  停滯達 "
                f"{STAGNATION_LIMIT} 代：執行 local search、"
                "提高 mutation，並加入隨機個體\n"
                f"  mutation={BOOSTED_MUTATION_RATE:.2f}、"
                f"pair={BOOSTED_PAIR_MUTATION_RATE:.2f}、"
                f"swap={BOOSTED_SWAP_MUTATION_RATE:.2f}，"
                f"維持最多 {BOOST_DURATION} 代"
            )

            local_reels, local_result = local_search(
                best_reels,
                include_missing_symbols,
            )
            if local_result[0] < best_score:
                best_reels = local_reels
                (
                    best_score,
                    best_rtp,
                    best_win_rate,
                    best_symbol_winning_spins,
                ) = local_result
                best_score_so_far = best_score
                evaluated[0] = (local_result, local_reels)
                evaluated.sort(key=lambda item: item[0][0])
                print(
                    "  Local search 改善至 "
                    f"score={best_score}, "
                    f"RTP={best_rtp:.4f}, "
                    f"win rate={best_win_rate:.4f}"
                )

        missing_symbol_count = sum(
            winning_spins == 0
            for winning_spins in best_symbol_winning_spins
        )
        win_rate_shortfall = max(
            0,
            MIN_WIN_RATE - best_win_rate,
        )
        rtp_error = abs(best_rtp - TARGET_RTP)
        history.append({
            "generation": generation,
            "fitness_mode": fitness_mode,
            "fitness_priority": ">".join(priority),
            "fitness_score": repr(best_score),
            "weighted_error": (
                best_score[0]
                if fitness_mode == "weighted"
                else ""
            ),
            "missing_symbols": missing_symbol_count,
            "win_rate_shortfall": win_rate_shortfall,
            "rtp_error": rtp_error,
            "rtp": best_rtp,
            "win_rate": best_win_rate,
        })
        history_path = save_ga_history(history)

        target_reached = (
            best_win_rate >= MIN_WIN_RATE
            and rtp_error < 0.0001
            and (
                not include_missing_symbols
                or missing_symbol_count == 0
            )
        )
        if target_reached:
            break

        # 保留最好的個體，並從較好的前半族群選擇 parents。
        next_population = [
            [reel[:] for reel in reels]
            for _, reels in evaluated[:ELITE_SIZE]
        ]
        parent_pool = [reels for _, reels in evaluated[:POPULATION_SIZE // 2]]
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
                mutation_rate=current_mutation_rate,
                pair_rate=current_pair_rate,
                swap_rate=current_swap_rate,
            )
            next_population.append(child)

        for _ in range(immigrant_count):
            next_population.append(create_individual())

        if stagnation_triggered:
            generations_without_improvement = 0

        population = next_population

        if boost_generations_remaining > 0:
            boost_generations_remaining -= 1

    convergence_path, metrics_path = save_ga_charts(history_path)
    print(
        f"\nGA 在第 {generation} 代結束，已依完整 CSV 產圖：\n"
        f"歷史資料：{history_path}\n"
        f"收斂圖：{convergence_path}\n"
        f"指標變化圖：{metrics_path}"
    )

    print("\nBest reels:")
    for reel in best_reels:
        print(reel)
    print(f"RTP: {best_rtp:.4%}")
    print(f"Win rate: {best_win_rate:.4%}")
    print(
        "Symbol winning spins: "
        + ", ".join(
            f"{symbol}={winning_spins}"
            for symbol, winning_spins in enumerate(
                best_symbol_winning_spins
            )
        )
    )
    if fitness_mode == "lexicographic":
        score_description = ", ".join(priority)
    else:
        score_description = "weighted error"
    print(f"Fitness score ({score_description}): {best_score}")
    payout_statistics = calculate_winning_payout_statistics(best_reels)
    print_winning_payout_statistics(payout_statistics)


if __name__ == "__main__":
    run_ga(choose_missing_symbols_mode())
