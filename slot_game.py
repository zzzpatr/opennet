import random


# These are the three reels. Their symbols and lengths can be changed later.
REELS = [
    [3, 1, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 4, 4, 0],
    [3, 4, 4, 4, 4, 4, 4, 2]
]

BET_AMOUNT = 100

# Group prizes by the total payout-to-bet multiplier for one spin.
SMALL_PRIZE_MAX_MULTIPLIER = 1.0
BIG_PRIZE_MIN_MULTIPLIER = 5.0

SYMBOL_MULTIPLIERS = {
    0: 0.25,
    1: 0.55,
    2: 1,
    3: 3,
    4: 5,
}

# Each coordinate is written as (row, column).
# A pattern wins only when all of its positions contain the same symbol.
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
    """Spin the three reels and return the 3x3 screen."""
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
    """Print a 3x3 screen."""
    print("+---+---+---+")
    for row in grid:
        print("| " + " | ".join(str(symbol) for symbol in row) + " |")
        print("+---+---+---+")


def check_win(grid):
    """Check the screen and return every matched pattern ID."""
    matched_patterns = []

    for pattern_name, positions in WINNING_PATTERNS.items():
        first_row, first_column = positions[0]
        target_symbol = grid[first_row][first_column]

        if all(grid[row][column] == target_symbol for row, column in positions):
            matched_patterns.append(pattern_name)

    return matched_patterns


def calculate_payout(grid, matched_patterns):
    """Calculate each pattern payout and the total prize for the spin."""
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
    """Classify a prize by its payout-to-bet multiplier."""
    payout_multiplier = payout / BET_AMOUNT
    if payout_multiplier <= SMALL_PRIZE_MAX_MULTIPLIER:
        return "small"
    if payout_multiplier < BIG_PRIZE_MIN_MULTIPLIER:
        return "medium"
    return "big"


def calculate_game_statistics(reels=REELS, include_payout_statistics=False):
    """Enumerate every stop and calculate exact game and symbol statistics."""
    total_spins = 0
    winning_spins = 0
    jackpot_spins = 0
    total_payout = 0
    payout_counts = {}
    prize_tier_counts = {
        "small": 0,
        "medium": 0,
        "big": 0,
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

                    # Count a symbol once per winning spin, even if several patterns match.
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
    """Return the payout distribution and small, medium, and big prize rates."""
    return calculate_game_statistics(
        reels,
        include_payout_statistics=True,
    )[-1]


def print_winning_payout_statistics(payout_statistics):
    """Print exact probabilities for payouts and prize tiers."""
    print("\n--- Winning payout distribution ---")
    for payout, statistics in (
        payout_statistics["payout_distribution"].items()
    ):
        print(
            f"Prize {payout:g} ({payout / BET_AMOUNT:g}x bet): "
            f"spins={statistics['spin_count']}, "
            f"all-spin probability={statistics['probability']:.2%}, "
            f"probability among wins="
            f"{statistics['probability_among_wins']:.2%}, "
            f"payout share={statistics['payout_share']:.2%}"
        )

    print("\n--- Small / medium / big prize rates ---")
    tier_labels = {
        "small": (
            f"Small (up to {SMALL_PRIZE_MAX_MULTIPLIER:g}x bet)"
        ),
        "medium": (
            f"Medium (over {SMALL_PRIZE_MAX_MULTIPLIER:g}x and "
            f"under {BIG_PRIZE_MIN_MULTIPLIER:g}x bet)"
        ),
        "big": (
            f"Big ({BIG_PRIZE_MIN_MULTIPLIER:g}x bet or more)"
        ),
    }
    for tier_name, statistics in payout_statistics["prize_tiers"].items():
        print(
            f"{tier_labels[tier_name]}: "
            f"spins={statistics['spin_count']}, "
            f"all-spin probability={statistics['probability']:.2%}, "
            f"probability among wins="
            f"{statistics['probability_among_wins']:.2%}"
        )

    print(
        "Average payout among wins: "
        f"{payout_statistics['average_winning_payout']:g}"
    )
    print(
        "Minimum / maximum winning payout: "
        f"{payout_statistics['minimum_winning_payout']:g} / "
        f"{payout_statistics['maximum_winning_payout']:g}"
    )
    print(
        "Jackpot (all nine cells match): "
        f"{payout_statistics['jackpot_spins']} spins, "
        f"probability={payout_statistics['jackpot_probability']:.6%}"
    )


if __name__ == "__main__":
    simulation_spins = 10
    simulation_wins = 0
    simulation_total_payout = 0

    for spin_number in range(1, simulation_spins + 1):
        print(f"\nSpin {spin_number}")

        result = spin()
        print_grid(result)

        matched_patterns = check_win(result)

        if matched_patterns:
            simulation_wins += 1
            print("Win! Matched patterns:", ", ".join(matched_patterns))

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

            print(f"Total payout: {total_payout:g}")
            simulation_total_payout += total_payout

        else:
            print("No win. Payout: 0")

    simulation_total_bet = simulation_spins * BET_AMOUNT
    simulation_rtp = simulation_total_payout / simulation_total_bet
    simulation_win_rate = simulation_wins / simulation_spins

    print("\n--- Results from 10 random spins ---")
    print(f"Spins: {simulation_spins}")
    print(f"Wins: {simulation_wins}")
    print(f"Total bet: {simulation_total_bet:g}")
    print(f"Total payout: {simulation_total_payout:g}")
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

    print("\n--- Exact results across every stop combination ---")
    print(f"Total combinations: {exact_spins}")
    print(f"Winning combinations: {exact_wins}")
    print(f"Total bet: {exact_spins * BET_AMOUNT:g}")
    print(f"Total payout: {exact_payout:g}")
    print(f"RTP：{exact_rtp:.2%}")
    print(f"Win rate：{exact_win_rate:.2%}")

    print("\n--- Win statistics by symbol ---")
    for symbol, statistics in exact_symbol_statistics.items():
        print(
            f"Symbol {symbol}："
            f"winning spins={statistics['winning_spins']}, "
            f"win rate={statistics['win_rate']:.2%}, "
            f"matched patterns={statistics['matched_patterns']}, "
            f"total payout={statistics['total_payout']:g}"
        )

    print_winning_payout_statistics(exact_payout_statistics)
