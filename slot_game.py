import random


# 三個滾輪（reels），之後可以再調整內容與長度。
REELS = [
    [3, 1, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 4, 4, 0],
    [3, 4, 4, 4, 4, 4, 4, 2]
]

BET_AMOUNT = 100

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


def calculate_rtp_and_win_rate(reels=REELS):
    """枚舉所有停止位置，計算精確 RTP 與 win rate。"""
    total_spins = 0
    winning_spins = 0
    total_payout = 0

    for stop_1 in range(len(reels[0])):
        for stop_2 in range(len(reels[1])):
            for stop_3 in range(len(reels[2])):
                grid = spin(reels, [stop_1, stop_2, stop_3])
                matched_patterns = check_win(grid)
                _, payout = calculate_payout(grid, matched_patterns)

                total_spins += 1
                total_payout += payout

                if matched_patterns:
                    winning_spins += 1

    total_bet = total_spins * BET_AMOUNT
    rtp = total_payout / total_bet
    win_rate = winning_spins / total_spins

    return total_spins, winning_spins, total_payout, rtp, win_rate


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

    exact_spins, exact_wins, exact_payout, exact_rtp, exact_win_rate = (
        calculate_rtp_and_win_rate()
    )

    print("\n--- 所有停止位置的精確計算 ---")
    print(f"總組合數：{exact_spins}")
    print(f"成功組合數：{exact_wins}")
    print(f"總下注：{exact_spins * BET_AMOUNT:g}")
    print(f"總獎金：{exact_payout:g}")
    print(f"RTP：{exact_rtp:.2%}")
    print(f"Win rate：{exact_win_rate:.2%}")
