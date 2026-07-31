import random


# 三個滾輪（reels），之後可以再調整內容與長度。
REELS = [
    [3, 1, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 4, 4, 0],
    [3, 4, 4, 4, 4, 4, 4, 2]
]

BET_AMOUNT = 100

# 依單局總獎金相對於 bet 的倍數區分獎金級距。
SMALL_PRIZE_MAX_MULTIPLIER = 1.0
BIG_PRIZE_MIN_MULTIPLIER = 5.0
SUPER_BIG_PRIZE_MIN_MULTIPLIER = 10.0

SYMBOL_MULTIPLIERS = {
    0: 0.25,
    1: 0.55,
    2: 1,
    3: 3,
    4: 5,
}

# 每個座標都是 (row, column)。
# 一個 pattern 內的所有位置必須是相同 symbol 才算成功。
WINNING_PATTERNS = {
    "4.1": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "4.2": [(0, 1), (0, 2), (1, 1), (1, 2)],
    "4.3": [(1, 0), (1, 1), (2, 0), (2, 1)],
    "4.4": [(1, 1), (1, 2), (2, 1), (2, 2)],
    "4.5": [
        (0, 0), (0, 1), (0, 2),
        (1, 0), (1, 1), (1, 2),
        (2, 0), (2, 1), (2, 2),
    ],
}


def spin(reels=REELS, stops=None):
    """轉動三個滾輪，回傳 3×3 的畫面。"""
    if stops is None:
        stops = [random.randrange(len(reel)) for reel in reels]

    grid = []
    for row in range(3):
        current_row = []

        for column in range(3):
            reel = reels[column]
            position = (stops[column] + row) % len(reel)
            current_row.append(reel[position])

        grid.append(current_row)

    return grid


def print_grid(grid):
    """將 3×3 畫面印出來。"""
    print("+---+---+---+")
    for row in grid:
        print("| " + " | ".join(str(symbol) for symbol in row) + " |")
        print("+---+---+---+")


def check_win(grid):
    """檢查畫面，回傳所有成功的 pattern 編號。"""
    matched_patterns = []

    for pattern_name, positions in WINNING_PATTERNS.items():
        first_row, first_column = positions[0]
        target_symbol = grid[first_row][first_column]

        if all(grid[row][column] == target_symbol for row, column in positions):
            matched_patterns.append(pattern_name)

    return matched_patterns


def calculate_payout(grid, matched_patterns):
    """計算各 pattern 的獎金，以及加總後的總獎金。"""
    payout_details = []
    total_payout = 0

    for pattern_name in matched_patterns:
        positions = WINNING_PATTERNS[pattern_name]
        first_row, first_column = positions[0]
        symbol = grid[first_row][first_column]
        multiplier = SYMBOL_MULTIPLIERS[symbol]

        payout = BET_AMOUNT * multiplier
        if pattern_name == "4.5":
            payout *= 5

        payout_details.append((pattern_name, symbol, multiplier, payout))
        total_payout += payout

    return payout_details, total_payout


def classify_prize(payout):
    """依單局總獎金相對於 bet 的倍數回傳獎金級距。"""
    payout_multiplier = payout / BET_AMOUNT
    if payout_multiplier <= SMALL_PRIZE_MAX_MULTIPLIER:
        return "small"
    if payout_multiplier < BIG_PRIZE_MIN_MULTIPLIER:
        return "medium"
    if payout_multiplier < SUPER_BIG_PRIZE_MIN_MULTIPLIER:
        return "big"
    return "super_big"


def calculate_game_statistics(reels=REELS, include_payout_statistics=False):
    """枚舉所有停止位置，計算整體與各 symbol 的精確統計。"""
    total_spins = 0
    winning_spins = 0
    jackpot_spins = 0
    total_payout = 0
    payout_counts = {}
    prize_tier_counts = {
        "small": 0,
        "medium": 0,
        "big": 0,
        "super_big": 0,
    }
    symbol_statistics = {
        symbol: {
            "winning_spins": 0,
            "win_rate": 0,
            "matched_patterns": 0,
            "total_payout": 0,
        }
        for symbol in SYMBOL_MULTIPLIERS
    }

    for stop_1 in range(len(reels[0])):
        for stop_2 in range(len(reels[1])):
            for stop_3 in range(len(reels[2])):
                grid = spin(reels, [stop_1, stop_2, stop_3])
                matched_patterns = check_win(grid)
                payout_details, payout = calculate_payout(
                    grid,
                    matched_patterns,
                )

                total_spins += 1
                total_payout += payout

                if matched_patterns:
                    winning_spins += 1
                    if "4.5" in matched_patterns:
                        jackpot_spins += 1
                    payout_counts[payout] = payout_counts.get(payout, 0) + 1
                    prize_tier = classify_prize(payout)
                    prize_tier_counts[prize_tier] += 1
                    symbols_won_this_spin = set()

                    for _, symbol, _, pattern_payout in payout_details:
                        symbol_statistics[symbol]["matched_patterns"] += 1
                        symbol_statistics[symbol]["total_payout"] += (
                            pattern_payout
                        )
                        symbols_won_this_spin.add(symbol)

                    # 同一局同 symbol 即使命中多個 pattern，也只算一個中獎局。
                    for symbol in symbols_won_this_spin:
                        symbol_statistics[symbol]["winning_spins"] += 1

    total_bet = total_spins * BET_AMOUNT
    rtp = total_payout / total_bet
    win_rate = winning_spins / total_spins

    for statistics in symbol_statistics.values():
        statistics["win_rate"] = (
            statistics["winning_spins"] / total_spins
        )

    result = (
        total_spins,
        winning_spins,
        total_payout,
        rtp,
        win_rate,
        symbol_statistics,
    )
    if not include_payout_statistics:
        return result

    payout_distribution = {}
    for payout, spin_count in sorted(payout_counts.items()):
        payout_total = payout * spin_count
        payout_distribution[payout] = {
            "spin_count": spin_count,
            "probability": spin_count / total_spins,
            "probability_among_wins": (
                spin_count / winning_spins
                if winning_spins
                else 0
            ),
            "total_payout": payout_total,
            "payout_share": (
                payout_total / total_payout
                if total_payout
                else 0
            ),
        }

    prize_tiers = {}
    for tier_name, spin_count in prize_tier_counts.items():
        prize_tiers[tier_name] = {
            "spin_count": spin_count,
            "probability": spin_count / total_spins,
            "probability_among_wins": (
                spin_count / winning_spins
                if winning_spins
                else 0
            ),
        }

    payout_statistics = {
        "jackpot_spins": jackpot_spins,
        "jackpot_probability": jackpot_spins / total_spins,
        "average_winning_payout": (
            total_payout / winning_spins
            if winning_spins
            else 0
        ),
        "minimum_winning_payout": (
            min(payout_counts)
            if payout_counts
            else 0
        ),
        "maximum_winning_payout": (
            max(payout_counts)
            if payout_counts
            else 0
        ),
        "payout_distribution": payout_distribution,
        "prize_tiers": prize_tiers,
    }
    return result + (payout_statistics,)


def calculate_winning_payout_statistics(reels=REELS):
    """回傳中獎金額分布與小、中、大獎機率。"""
    return calculate_game_statistics(
        reels,
        include_payout_statistics=True,
    )[-1]


def print_winning_payout_statistics(payout_statistics):
    """印出各中獎金額及獎金級距的精確機率。"""
    print("\n--- 中獎金額分布 ---")
    for payout, statistics in (
        payout_statistics["payout_distribution"].items()
    ):
        print(
            f"獎金 {payout:g}（{payout / BET_AMOUNT:g}x bet）："
            f"出現={statistics['spin_count']} 次，"
            f"全部 spins 機率={statistics['probability']:.2%}，"
            f"中獎時機率="
            f"{statistics['probability_among_wins']:.2%}，"
            f"獎金貢獻={statistics['payout_share']:.2%}"
        )

    print("\n--- 小／中／大／超大獎機率 ---")
    tier_labels = {
        "small": (
            f"小獎（小於等於 {SMALL_PRIZE_MAX_MULTIPLIER:g}x bet）"
        ),
        "medium": (
            f"中獎（大於 {SMALL_PRIZE_MAX_MULTIPLIER:g}x "
            f"且小於 {BIG_PRIZE_MIN_MULTIPLIER:g}x bet）"
        ),
        "big": (
            f"大獎（大於等於 {BIG_PRIZE_MIN_MULTIPLIER:g}x "
            f"且小於 {SUPER_BIG_PRIZE_MIN_MULTIPLIER:g}x bet）"
        ),
        "super_big": (
            "超大獎（大於等於 "
            f"{SUPER_BIG_PRIZE_MIN_MULTIPLIER:g}x bet）"
        ),
    }
    for tier_name, statistics in payout_statistics["prize_tiers"].items():
        print(
            f"{tier_labels[tier_name]}："
            f"出現={statistics['spin_count']} 次，"
            f"全部 spins 機率={statistics['probability']:.2%}，"
            f"中獎時機率="
            f"{statistics['probability_among_wins']:.2%}"
        )

    print(
        "中獎時平均獎金："
        f"{payout_statistics['average_winning_payout']:g}"
    )
    print(
        "最低／最高單局獎金："
        f"{payout_statistics['minimum_winning_payout']:g} / "
        f"{payout_statistics['maximum_winning_payout']:g}"
    )
    print(
        "Jackpot（九格同 symbol）："
        f"{payout_statistics['jackpot_spins']} 次，"
        f"機率={payout_statistics['jackpot_probability']:.6%}"
    )


def calculate_rtp_and_win_rate(reels=REELS):
    """保留原有五個回傳值，供既有程式相容使用。"""
    return calculate_game_statistics(reels)[:5]


if __name__ == "__main__":
    simulation_spins = 10
    simulation_wins = 0
    simulation_total_payout = 0

    for spin_number in range(1, simulation_spins + 1):
        print(f"\n第 {spin_number} 次 spin")

        result = spin()
        print_grid(result)

        matched_patterns = check_win(result)

        if matched_patterns:
            simulation_wins += 1
            print("成功！命中的 pattern：", ", ".join(matched_patterns))

            payout_details, total_payout = calculate_payout(
                result,
                matched_patterns,
            )

            print(f"Bet amount：{BET_AMOUNT}")
            for pattern_name, symbol, multiplier, payout in payout_details:
                extra = " × 5" if pattern_name == "4.5" else ""
                print(
                    f"Pattern {pattern_name}："
                    f"{BET_AMOUNT} × {multiplier}{extra} = {payout:g} "
                    f"（symbol {symbol}）"
                )

            print(f"總獎金：{total_payout:g}")
            simulation_total_payout += total_payout

        else:
            print("失敗，本次獎金：0")

    simulation_total_bet = simulation_spins * BET_AMOUNT
    simulation_rtp = simulation_total_payout / simulation_total_bet
    simulation_win_rate = simulation_wins / simulation_spins

    print("\n--- 10 次隨機遊玩結果 ---")
    print(f"遊玩次數：{simulation_spins}")
    print(f"成功次數：{simulation_wins}")
    print(f"總下注：{simulation_total_bet:g}")
    print(f"總獎金：{simulation_total_payout:g}")
    print(f"RTP：{simulation_rtp:.2%}")
    print(f"Win rate：{simulation_win_rate:.2%}")

    (
        exact_spins,
        exact_wins,
        exact_payout,
        exact_rtp,
        exact_win_rate,
        exact_symbol_statistics,
        exact_payout_statistics,
    ) = (
        calculate_game_statistics(include_payout_statistics=True)
    )

    print("\n--- 所有停止位置的精確計算 ---")
    print(f"總組合數：{exact_spins}")
    print(f"成功組合數：{exact_wins}")
    print(f"總下注：{exact_spins * BET_AMOUNT:g}")
    print(f"總獎金：{exact_payout:g}")
    print(f"RTP：{exact_rtp:.2%}")
    print(f"Win rate：{exact_win_rate:.2%}")

    print("\n--- 各 symbol 中獎統計 ---")
    for symbol, statistics in exact_symbol_statistics.items():
        print(
            f"Symbol {symbol}："
            f"中獎局數={statistics['winning_spins']}，"
            f"中獎率={statistics['win_rate']:.2%}，"
            f"命中 pattern 數={statistics['matched_patterns']}，"
            f"總獎金={statistics['total_payout']:g}"
        )

    print_winning_payout_statistics(exact_payout_statistics)
