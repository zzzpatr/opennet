# Slot Game Reel Optimization

本專案以完整枚舉計算 3×3 Slot Game 的精確 RTP、Win rate、Jackpot 與
獎金分布，再使用 Baseline GA、Weighted GA 和 NSGA-II 搜尋 reel
configuration。原始題目請參考 [DS-HomeWork.md](./DS-HomeWork.md)。

## 遊戲設定

- 3 條 circular reels，每條長度 12。
- 5 種 symbols，倍率為 `0.25、0.55、1、3、5`。
- 每次 spin 顯示 3×3 grid。
- 依題目定義的五種 winning patterns 計算 payout。
- Pattern 4.5（3×3 全部相同）視為 Jackpot。
- 目標 RTP 為 95%，容許範圍為 94%～96%。
- 最低 Win rate 為 55%。

每組 reels 共有：

```text
12 × 12 × 12 = 1,728
```

種停止組合。所有 fitness 與最終報表都使用完整枚舉，不使用抽樣模擬。


## 結果

以下結果皆以 1,728 種停止組合完整枚舉驗證。Baseline 使用自己的 fitness；
Weighted GA 與 NSGA-II 的 weighted score 使用相同四項 penalties，因此只有
後兩者的 score 可以直接比較。

| Algorithm | Generation | RTP | Win rate | Concentration | Jackpot probability | Score | RTP 合格 | Win rate 合格 |
|---|---:|---:|---:|---:|---:|---:|:---:|:---:|
| Baseline GA | 57 | 94.5833% | 55.9028% | 0.458333 | 0% | 0.004167 | ✓ | ✓ |
| Weighted GA | 1000 | 95.1736% | 56.7130% | 0.393519 | 3.472222% | 7.017544 | ✓ | ✓ |
| NSGA-II solution 96 | 1000 | 96.5278% | 51.5046% | 0.388889 | 0.694444% | 10.865253 | ✗ | ✗ |

### Baseline GA 最終解

```text
Reel 1: [1, 1, 3, 1, 1, 1, 1, 3, 3, 3, 3, 1]
Reel 2: [3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3]
Reel 3: [0, 2, 2, 1, 1, 3, 3, 2, 3, 3, 1, 3]
```

| Convergence | Metrics |
|---|---|
| ![Baseline convergence](./ga_baseline_results/ga_convergence.png) | ![Baseline metrics](./ga_baseline_results/ga_metrics.png) |
| Prize distribution | Reel symbol distribution |
| ![Baseline prize distribution](./ga_baseline_results/ga_prize_distribution.png) | ![Baseline reel symbol distribution](./ga_baseline_results/ga_reel_symbol_distribution.png) |

### Weighted GA 最終解

```text
Reel 1: [1, 1, 1, 1, 3, 3, 4, 0, 2, 1, 1, 1]
Reel 2: [1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1]
Reel 3: [1, 3, 3, 3, 2, 2, 0, 4, 0, 1, 1, 1]
```

| Convergence | Metrics |
|---|---|
| ![Weighted GA convergence](./ga_weighted_game_design_results/ga_convergence.png) | ![Weighted GA metrics](./ga_weighted_game_design_results/ga_metrics.png) |
| Prize distribution | Reel symbol distribution |
| ![Weighted GA prize distribution](./ga_weighted_game_design_results/ga_prize_distribution.png) | ![Weighted GA reel symbol distribution](./ga_weighted_game_design_results/ga_reel_symbol_distribution.png) |

### NSGA-II solution 96

```text
Reel 1: [2, 2, 2, 1, 3, 3, 2, 2, 4, 2, 2, 4]
Reel 2: [2, 2, 2, 2, 2, 2, 2, 4, 3, 3, 3, 2]
Reel 3: [2, 2, 2, 2, 0, 3, 3, 3, 1, 4, 4, 4]
```

| Convergence | Metrics |
|---|---|
| ![NSGA-II convergence](./nsga2_results/ga_convergence.png) | ![NSGA-II metrics](./nsga2_results/ga_metrics.png) |
| Prize distribution | Reel symbol distribution |
| ![NSGA-II prize distribution](./nsga2_results/ga_prize_distribution.png) | ![NSGA-II reel symbol distribution](./nsga2_results/ga_reel_symbol_distribution.png) |

Weighted GA 是三者中唯一同時符合 RTP、Win rate 與 Jackpot 條件的解。
NSGA-II solution 96 的 concentration 略低，但以 RTP 與 Win rate 違規作為
代價；這是保留完整 Pareto front 後再進行人工選擇的 trade-off。

## 演算法

### Baseline GA

[GA_baseline.py](./GA_baseline.py) 只處理原題主要條件：RTP 與 Win rate。

```python
fitness = rtp_error + 5 * win_rate_shortfall
```

當 RTP 位於 94%～96%，且 Win rate 至少 55% 時提前停止。

### Weighted GA

[GA_weighted_game_design.py](./GA_weighted_game_design.py) 使用四個 penalty：

```python
objectives = (
    rtp_violation / 0.01,
    win_rate_shortfall / 0.01,
    missing_jackpot,
    30 * concentration_penalty,
)

fitness = sum(objectives)
```

其中：

```python
rtp_violation = max(0, abs(rtp - 0.95) - 0.01)
win_rate_shortfall = max(0, 0.55 - win_rate)
concentration_penalty = (
    symbol_concentration - minimum_concentration
) / (1 - minimum_concentration)
```

Weighted GA 的初始族群為 50% balanced reels 與 50% random reels。每次
mutation 後有 10% 機率使用最少 replacements 建立共同 triple，增加
Jackpot 搜尋機會。

### NSGA-II

[NSGAII.py](./NSGAII.py) 與 Weighted GA 共用相同的初始化、Jackpot
repair 和四個 penalties，但不把 objectives 先相加來做 selection，而是
使用：

- Pareto dominance
- Non-dominated sorting
- Crowding distance
- Binary tournament selection
- Elitist environmental selection

目前 NSGA-II 不使用硬限制。不合格解仍可留在 Pareto front，方便觀察
RTP、Win rate、Jackpot 與 concentration 的取捨。

每代 history 使用 Pareto front 中 `weighted_score` 最低的解追蹤收斂；
最終 `best_solution.json` 與分布圖則使用：

```python
FINAL_SOLUTION_NUMBER = 96
```

這只決定最終報表採用哪個 Pareto 解，不影響 NSGA-II 的演化與 Pareto
selection。若重新執行後 Pareto front 少於 96 個 solutions，程式會明確
回報錯誤，避免誤選其他解。

目前選定的 solution 96：

| Metric | Value |
|---|---:|
| RTP | 96.5278% |
| Win rate | 51.5046% |
| Symbol concentration | 0.388889 |
| Jackpot probability | 0.694444% |
| Weighted score | 10.865253 |

此解略微超出 RTP tolerance 且 Win rate 低於 55%，是分析 Pareto front 後
人工選定的折衷解，報告中不應描述為完全符合原題條件。


## Reel symbol concentration

`symbol_concentration` 衡量每條 reel 的 symbol frequency 是否集中。程式先
對每條 reel 計算 HHI，再取三條 reels 的平均：

```python
reel_hhi = sum((symbol_count / reel_length) ** 2)
symbol_concentration = mean(reel_hhi for reel in reels)
```

Concentration 越低表示 reel symbols 越平均。Reel 長度為 12、symbol
數量為 5 時，最平均的數量配置是 `3, 3, 2, 2, 2`，理論最低值為：

```text
(3² + 3² + 2² + 2² + 2²) / 12² = 0.208333
```

此指標只看 reel 上的 symbol 數量，不使用 winning-pattern symbol 分布。


## 共用 GA 設定

主要設定集中於 [ga_common.py](./ga_common.py)：

```text
REEL_LENGTH       = 12
POPULATION_SIZE   = 200
GENERATIONS       = 1000
ELITE_SIZE        = 5
MUTATION_RATE     = 0.04
PAIR_MUTATION_RATE = 0.25
SWAP_MUTATION_RATE = 0.15
RANDOM_SEED       = 42
```

普通 GA 另外使用停滯偵測、提高 mutation rates、local search 與 random
immigrants。族群評估支援 multiprocessing，預設最多使用 8 個 workers，
並以 reel key 快取重複個體的精確枚舉結果。

## 輸出

Baseline GA 輸出到 `ga_baseline_results/`，Weighted GA 輸出到
`ga_weighted_game_design_results/`，NSGA-II 輸出到 `nsga2_results/`。

普通 GA 與 NSGA-II 都會產生：

```text
ga_history.csv
best_solution.json
ga_convergence.png
ga_metrics.png
ga_prize_distribution.png
ga_reel_symbol_distribution.png
```

`ga_metrics.png` 只顯示以下四項，並標示目標線：

- Jackpot probability：至少一個 Jackpot spin。
- Symbol concentration：理論最低值。
- RTP：95%。
- Win rate：55%。

`ga_reel_symbol_distribution.png` 以 stacked bars 顯示三條 reels 在各
symbol 的數量與占比。

NSGA-II 另外輸出精簡的 `nsga2_pareto_front.csv`：

```text
solution
weighted_score
四個 objective penalties
rtp
win_rate
symbol_concentration
jackpot_probability
reel_1 / reel_2 / reel_3
```

## 執行方式

建立環境並安裝套件：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

執行遊戲規則與完整枚舉示例：

```powershell
.\.venv\Scripts\python.exe .\slot_game.py
```

執行三種搜尋：

```powershell
.\.venv\Scripts\python.exe .\GA_baseline.py
.\.venv\Scripts\python.exe .\GA_weighted_game_design.py
.\.venv\Scripts\python.exe .\NSGAII.py
```

從既有 history 重新產圖：

```powershell
.\.venv\Scripts\python.exe .\ga_plot.py `
    .\nsga2_results\ga_history.csv
```

## 專案結構

```text
slot_game.py                 遊戲規則、完整枚舉與 payout 統計
ga_common.py                 共用 metrics、operators、cache 與 GA runner
GA_baseline.py               RTP／Win-rate baseline
GA_weighted_game_design.py   四項 penalty 的 Weighted GA
NSGAII.py                    四目標 NSGA-II 與 Pareto front 輸出
ga_plot.py                   收斂、metrics 與分布圖
DS-HomeWork.md               原始題目
requirements.txt             Plotly 與 Kaleido 版本
```
