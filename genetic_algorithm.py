import random

from slot_game import calculate_rtp_and_win_rate


REEL_LENGTH = 10
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
    """分數越小越好，0 代表完全符合目標。"""
    key = tuple(tuple(reel) for reel in reels)
    if key in FITNESS_CACHE:
        return FITNESS_CACHE[key]

    _, _, _, rtp, win_rate = calculate_rtp_and_win_rate(reels)

    rtp_error = abs(rtp - TARGET_RTP)
    win_rate_shortfall = max(0, MIN_WIN_RATE - win_rate)

    # 如果完全沒有使用某種 symbol，給予額外 penalty。
    used_symbols = set(reels[0] + reels[1] + reels[2])
    missing_symbol_penalty = (5 - len(used_symbols)) * 0.1

    error = rtp_error + 5 * win_rate_shortfall + missing_symbol_penalty
    result = (error, rtp, win_rate)
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


def mutate(reels, mutation_rate=MUTATION_RATE, swap_rate=SWAP_MUTATION_RATE):
    """使用 replacement 與 swap 兩種 mutation。"""
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

        # 模式二：交換兩個位置，不改變數量，只改變相鄰順序。
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
    best_error_so_far = float("inf")
    generations_without_improvement = 0
    boost_generations_remaining = 0

    for generation in range(1, GENERATIONS + 1):
        evaluated = [(fitness(reels), reels) for reels in population]
        evaluated.sort(key=lambda item: item[0][0])

        (best_error, best_rtp, best_win_rate), best_reels = evaluated[0]

        if best_error < best_error_so_far:
            best_error_so_far = best_error
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
            current_swap_rate = BOOSTED_SWAP_MUTATION_RATE
        else:
            current_mutation_rate = MUTATION_RATE
            current_swap_rate = SWAP_MUTATION_RATE

        if generation == 1 or generation % 10 == 0:
            for reel in best_reels:
                print(reel)
            print(
                f"Generation {generation:3d} | "
                f"error={best_error:.6f} | "
                f"RTP={best_rtp:.4f} | "
                f"win rate={best_win_rate:.4f} | "
                f"mutation={current_mutation_rate:.2f}"
            )

        if stagnation_triggered:
            print(
                "  停滯達 "
                f"{STAGNATION_LIMIT} 代：執行 local search、"
                "提高 mutation，並加入隨機個體\n"
                f"  mutation={BOOSTED_MUTATION_RATE:.2f}、"
                f"swap={BOOSTED_SWAP_MUTATION_RATE:.2f}，"
                f"維持最多 {BOOST_DURATION} 代"
            )

            local_reels, local_result = local_search(best_reels)
            if local_result[0] < best_error:
                best_reels = local_reels
                best_error, best_rtp, best_win_rate = local_result
                best_error_so_far = best_error
                evaluated[0] = (local_result, local_reels)
                evaluated.sort(key=lambda item: item[0][0])
                print(
                    f"  Local search 改善至 error={best_error:.6f}, "
                    f"RTP={best_rtp:.4f}, "
                    f"win rate={best_win_rate:.4f}"
                )

        if best_error < 0.0001:
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
    print(f"Error: {best_error:.6f}")


if __name__ == "__main__":
    run_ga()
