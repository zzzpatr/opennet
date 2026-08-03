# Slot Game Reel Optimization Report

## 1. 作業目標

本作業以 Genetic Algorithm 搜尋 3×3 Slot Game 的 reel configuration。
每組 reels 都會完整枚舉所有停止位置，以精確計算 RTP、Win rate、Jackpot
與 symbol distribution。原始題目請參考 [DS-HomeWork.md](./DS-HomeWork.md)。

除了滿足 RTP 與 Win rate，本作業也從遊戲設計與使用者體驗出發加入兩個
最佳化目標。第一，若 reel 過度集中在少數 symbols，玩家可能會覺得畫面
重複、分布不自然，因此加入 symbol concentration，希望每條 reel 的 symbols
分布更平均。第二，一個合理的老虎機應該保留出現 Jackpot 的可能性，因此
要求至少存在 3×3 九格全部相同的停止組合，並將 Jackpot probability 納入
評估。

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
取捨的解。它的優點不是只給出一個固定答案，而是產生多組 Pareto solutions，
讓我們觀察降低 concentration 時，RTP、Win rate 與 Jackpot probability
可能產生的 trade-off。

本次實驗不使用硬限制，並在分析 Pareto front 後人工選擇 solution 96 作為
最終報告解。若目標是讓 concentration 更低，可以選擇 solution 96；但代價是
RTP 與 Win rate 可能違反原始限制。此選擇只影響最終輸出，不影響 NSGA-II
搜尋過程。

### 3.4 GA operators 與客製化設計

三種演算法共用逐條 reel 的 single-point crossover，並搭配三種 mutation：

- **Single-symbol mutation**：將單一位置替換成其他 symbol，改變 symbol 數量
  與遊戲指標。
- **Adjacent-pair mutation**：將 circular reel 中相鄰兩格改成相同 symbol，
  增加產生連續相同 symbols 的機會。
- **Swap mutation**：交換同一條 reel 的兩個位置。此操作不改變 symbol 數量
  與 concentration，但可以調整排列、RTP、Win rate 與中獎組合。

Baseline GA 與 Weighted GA 使用 elitism，保留每代前 5 個 individuals。若
連續 20 代沒有改善，演算法會提高 mutation rates、對最佳解執行單格 local
search，並加入 25% random immigrants，以增加跳出 local optimum 的機會。

Weighted GA 與 NSGA-II 另外使用兩項遊戲設計導向的調整：初始族群由 50%
balanced reels 與 50% random reels 組成，讓搜尋兼顧低 concentration 與
多樣性；同時以 10% 機率執行 Jackpot repair，透過最少 replacements 建立
三條 reels 的共同三連續 symbol，使九格相同的 Jackpot 成為可能。

NSGA-II 的 mutation 與 repair 相同，但 selection 改用 Pareto rank、crowding
distance 和 binary tournament，並從 parents 與 offspring 中共同選出下一代。

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
- NSGA-II 能提供多組解，幫助理解 RTP、Win rate、Jackpot probability 與
  concentration 之間的 trade-off。若優先追求更低的 concentration，可以選擇
  solution 96，但其 RTP 與 Win rate 會違反原始限制。

因此，本作業建議以 Weighted GA 作為最終方案，NSGA-II 則作為多目標分析
與延伸實驗。

## 6. 延伸方向

本作業目前主要聚焦在 reel configuration 的遊戲設計，最佳化目標仍可從
以下方向擴充：

- **獎金分布與遊戲波動度**：除了 RTP，也可以控制小獎、中獎與大獎的出現
  比例，分析 payout variance，使遊戲節奏更符合預期。
- **Near-winning 體驗**：統計差一格即可連線或觸發 Jackpot 的結果，將其頻率
  納入最佳化。不過需要避免過度製造接近中獎的錯覺，在玩家體驗與公平性之間
  取得平衡。
- **不同長度的 reels**：目前為了簡化完整枚舉與比較，三條 reels 都限制為
  12 格。未來可以允許每條 reel 使用不同長度，增加 symbol arrangement 與
  中獎機率的變化性。
- **更多遊戲規則**：可加入更多 paylines、Wild、Scatter、Bonus Game 或
  Free Spin，研究不同機制對 RTP、Win rate 與 Jackpot 的影響。
- **限制與解的選擇方式**：可在 NSGA-II 加入必要的 RTP、Win rate 硬限制，
  或設計自動選解規則，從 Pareto front 中找出最符合實際需求的方案。
- **結果穩定性**：GA 具有隨機性，應使用不同 random seeds 重複實驗，比較各演算法的平均表現、
  標準差與成功率，避免只根據單次執行結果下結論。

## 7. 執行方式

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
