import random

from slot_game import calculate_game_statistics


# 五種 symbol 都要能形成 2x2 中獎時，中間 reel 至少需要五組相鄰配對。
REEL_LENGTH = 12
POPULATION_SIZE = 200
GENERATIONS = 500
ELITE_SIZE = 5
MUTATION_RATE = 0.08
PAIR_MUTATION_RATE = 0.10
SWAP_MUTATION_RATE = 0.10
STAGNATION_LIMIT = 20
BOOSTED_MUTATION_RATE = 0.15
BOOSTED_PAIR_MUTATION_RATE = 0.20
BOOSTED_SWAP_MUTATION_RATE = 0.30
BOOST_DURATION = 10
IMMIGRANT_RATIO = 0.25

TARGET_RTP = 0.95
MIN_WIN_RATE = 0.55
FITNESS_CACHE = {}


def create_individual():
    """隨機建立三個 reels。"""
    return [
        [random.randint(0, 4) for _ in range(REEL_LENGTH)]
        for _ in range(3)
    ]


def fitness(reels):
    """依硬條件、win rate、RTP 的優先順序回傳分層分數。"""
    key = tuple(tuple(reel) for reel in reels)
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
    fitness_score = (
        missing_winning_symbol_count,
        win_rate_shortfall,
        rtp_error,
    )

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


def local_search(reels):
    """測試所有單格替換，回傳 reels 附近最好的結果。"""
    best_reels = [reel[:] for reel in reels]
    best_result = fitness(best_reels)

    for reel_index in range(3):
        for position in range(REEL_LENGTH):
            old_symbol = reels[reel_index][position]

            for new_symbol in range(5):
                if new_symbol == old_symbol:
                    continue

                candidate = [reel[:] for reel in reels]
                candidate[reel_index][position] = new_symbol
                candidate_result = fitness(candidate)

                if candidate_result[0] < best_result[0]:
                    best_reels = candidate
                    best_result = candidate_result

    return best_reels, best_result


def run_ga():
    random.seed(42)
    population = [create_individual() for _ in range(POPULATION_SIZE)]
    best_score_so_far = (float("inf"), float("inf"), float("inf"))
    generations_without_improvement = 0
    boost_generations_remaining = 0

    for generation in range(1, GENERATIONS + 1):
        evaluated = [(fitness(reels), reels) for reels in population]
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
            for reel in best_reels:
                print(reel)
            print(
                f"Generation {generation:3d} | "
                f"missing symbols={best_score[0]} | "
                f"win rate shortfall={best_score[1]:.6f} | "
                f"RTP error={best_score[2]:.6f} | "
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

            local_reels, local_result = local_search(best_reels)
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

        if (
            best_score[0] == 0
            and best_score[1] == 0
            and best_score[2] < 0.0001
        ):
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
    print(
        "Fitness score "
        "(missing symbols, win rate shortfall, RTP error): "
        f"{best_score}"
    )


if __name__ == "__main__":
    run_ga()
