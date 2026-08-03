# Slot Game Reel Optimization Report

## 1. 作業目標

本作業以 Genetic Algorithm 搜尋 3×3 Slot Game 的 reel configuration。
每組 reels 都會完整枚舉所有停止位置，以精確計算 RTP、Win rate、Jackpot
與 symbol distribution。原始題目請參考 [DS-HomeWork.md](./DS-HomeWork.md)。

遊戲與目標設定：

- 3 條 circular reels，每條長度 12。
- 5 種 symbols，倍率為 `0.25、0.55、1、3、5`。
- 使用題目定義的五種 winning patterns。
- Pattern 4.5（3×3 全部相同）視為 Jackpot。
- 目標 RTP 為 95%，容許範圍為 94%～96%。
- Win rate 至少為 55%。

每組 reels 共有 `12³ = 1,728` 種停止組合。本作業使用完整枚舉，不使用
抽樣模擬。

## 2. 評估指標

### RTP 與 Win rate

```python
rtp = total_payout / total_bet
win_rate = winning_spins / total_spins
```

### Reel symbol concentration

使用 HHI 衡量每條 reel 的 symbol frequency，再取三條 reels 的平均：

```python
reel_hhi = sum((symbol_count / reel_length) ** 2)
symbol_concentration = mean(reel_hhi for reel in reels)
```

數值越低代表分布越平均。Reel 長度為 12 時，最平均配置為
`3, 3, 2, 2, 2`，最低 concentration 為 `0.208333`。

## 3. 方法

### 3.1 Baseline GA

Baseline 只最佳化題目要求的 RTP 與 Win rate：

```python
fitness = rtp_error + 5 * win_rate_shortfall
```

當 RTP 位於 94%～96% 且 Win rate 至少 55% 時停止。

### 3.2 Weighted GA

Weighted GA 同時考慮四個 penalties：

```python
objectives = (
    rtp_violation / 0.01,
    win_rate_shortfall / 0.01,
    missing_jackpot,
    30 * concentration_penalty,
)

fitness = sum(objectives)
```

初始族群由 50% balanced reels 與 50% random reels 組成，並以 10% 機率
進行 Jackpot repair。

### 3.3 NSGA-II

NSGA-II 使用與 Weighted GA 相同的四個 objectives，但不先相加，而是透過
Pareto dominance、non-dominated sorting 與 crowding distance 保留不同
取捨的解。

本次實驗不使用硬限制，並在分析 Pareto front 後人工選擇 solution 96 作為
最終報告解。此選擇只影響最終輸出，不影響 NSGA-II 搜尋過程。

## 4. 實驗結果

| Algorithm | Generation | RTP | Win rate | Concentration | Jackpot probability | Score |
|---|---:|---:|---:|---:|---:|---:|
| Baseline GA | 57 | 94.5833% | 55.9028% | 0.458333 | 0% | 0.004167 |
| Weighted GA | 1000 | 95.1736% | 56.7130% | 0.393519 | 3.472222% | 7.017544 |
| NSGA-II solution 96 | 1000 | 96.5278% | 51.5046% | 0.388889 | 0.694444% | 10.865253 |

Baseline 使用不同的 fitness，因此其 score 不能直接與另外兩種方法比較。

### 4.1 Baseline GA

Baseline 成功滿足 RTP 與 Win rate，但沒有 Jackpot，且 concentration 是
三者中最高的。

<details>
<summary>查看 Baseline reels 與圖表</summary>

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

</details>

### 4.2 Weighted GA

Weighted GA 是唯一同時符合 RTP、Win rate 與 Jackpot 條件的解，且
concentration 也比 Baseline 低，因此是本作業中最適合直接採用的結果。

<details>
<summary>查看 Weighted GA reels 與圖表</summary>

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

</details>

### 4.3 NSGA-II solution 96

Solution 96 的 concentration 略低於 Weighted GA，但 RTP 為 96.5278%、
Win rate 為 51.5046%，兩者都未符合原始條件。它是人工分析 Pareto front
後選出的折衷解，不應描述為完全合格。

<details>
<summary>查看 NSGA-II reels 與圖表</summary>

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

</details>

## 5. 結論

- Baseline GA 能快速找到符合原題 RTP 與 Win rate 的解，但沒有處理 Jackpot
  與 reel distribution。
- Weighted GA 同時滿足主要條件並改善 concentration，是本次最實用的解。
- NSGA-II 能展示不同 objectives 的 trade-off，但沒有硬限制時，Pareto 解
  不一定符合所有遊戲條件。

因此，本作業建議以 Weighted GA 作為最終方案，NSGA-II 則作為多目標分析
與延伸實驗。

## 6. 執行方式

安裝套件：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

執行三種演算法：

```powershell
.\.venv\Scripts\python.exe .\GA_baseline.py
.\.venv\Scripts\python.exe .\GA_weighted_game_design.py
.\.venv\Scripts\python.exe .\NSGAII.py
```

主要程式：

```text
slot_game.py                 遊戲規則與完整枚舉
ga_common.py                 共用 metrics、operators 與 GA runner
GA_baseline.py               Baseline GA
GA_weighted_game_design.py   Weighted GA
NSGAII.py                    NSGA-II 與 Pareto front
ga_plot.py                   結果圖表
```
