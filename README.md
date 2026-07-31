# Slot Game Reel Optimization

## 摘要

本作業的目標是產生一組 3×3 Slot Game reels，使遊戲的理論 RTP
（Return to Player）接近 95%，且 Win rate 不低於 55%。

本專案先建立可完整枚舉停止位置的 Slot Game 計算程式，再使用 Genetic
Algorithm（GA）搜尋龐大的 reel configuration 空間。取得符合原題要求的
baseline 後，進一步分析 symbol winning spins 與 Jackpot，觀察到只滿足
RTP 和 Win rate 不代表遊戲分布合理，因此再以 NSGA-II 探索 RTP 精度與
symbol 分布之間的 Pareto trade-off。

主要流程如下：

```text
建立精確遊戲模型
→ 使用 GA 搜尋原題可行解
→ 分析 baseline 的遊戲設計問題
→ 使用 NSGA-II 進行多目標改善
→ 比較改善前後結果
```

---

## 1. Slot Game 模型與精確枚舉

### 1.1 題目規則

遊戲畫面為 3 columns × 3 rows，共有五種 symbols：

```python
SYMBOL_MULTIPLIERS = {
    0: 0.25,
    1: 0.55,
    2: 1,
    3: 3,
    4: 5,
}
```

題目定義五種 winning patterns。Pattern 4.1～4.4 的 payout 為：

```text
Bet amount × symbol multiplier
```

Pattern 4.5 要求九格皆為相同 symbol，payout 為：

```text
Bet amount × symbol multiplier × 5
```

同一個畫面可以同時命中多個 patterns，每個命中的 pattern 都會獨立計算
獎金。因此九格相同時，會同時命中 4.1～4.5，總獎金為所有命中獎金的
加總。

完整題目請參考 [DS-HomeWork.md](./DS-HomeWork.md)。

### 1.2 Reel 與停止位置

每條 reel 是一個環狀 symbol sequence。若三條 reels 的長度分別為
`L1`、`L2`、`L3`，固定一組 reels 後，共有：

```text
L1 × L2 × L3
```

種停止位置。

[slot_game.py](./slot_game.py) 不使用抽樣模擬估計最終結果，而是完整枚舉
所有停止位置，因此可以得到精確的：

- RTP
- Win rate
- 總 payout
- 各 symbol winning spins
- 各 symbol 的 payout contribution
- 小獎、中獎、大獎與超大獎機率
- 九格同 symbol Jackpot 次數與機率

RTP 與 Win rate 分別計算為：

```python
rtp = total_payout / total_bet
win_rate = winning_spins / total_spins
```

完整枚舉使最後交付的 reels 可以被確定性驗證，不會因為模擬次數或 random
seed 不同而得到不同結果。

---

## 2. 使用 GA 搜尋 Reel Configuration

### 2.1 為什麼不能直接窮舉所有 reels

目前三條 reels 使用相同的固定長度 `L`，每格有 5 種 symbol。完整 reel
configuration 空間為：

```text
5^(3L)
```

以 `L = 12` 為例：

```text
5^36 ≈ 1.46 × 10^25
```

雖然固定一組 reels 後可以完整枚舉停止位置，但無法再窮舉所有可能的
reel configurations。因此本作業使用 GA 在龐大空間中快速搜尋可行解。

### 2.2 Baseline GA

[GA_baseline.py](./GA_baseline.py) 只處理原題明確要求：

```text
RTP 接近 95%
Win rate ≥ 55%
```

Fitness 定義為：

```python
weighted_error = (
    rtp_error
    + WIN_RATE_WEIGHT * win_rate_shortfall
)
```

其中：

```python
rtp_error = abs(rtp - 0.95)
win_rate_shortfall = max(0, 0.55 - win_rate)
```

Win rate 達標後，`win_rate_shortfall` 會變成 0，不會要求 Win rate
無限制提高；GA 會將搜尋資源集中於 RTP。

Baseline 的成功條件為：

```python
rtp_error <= RTP_TOLERANCE
win_rate >= 0.55
```

Jackpot、missing symbols、symbol concentration 和獎金分布都不影響
baseline fitness，避免將自行加入的遊戲設計偏好誤當成原題要求。

---

## 3. GA Operators 與收斂設計

三種搜尋方法共用 [ga_common.py](./ga_common.py) 的 reel encoding、
evaluation cache 與 genetic operators，確保實驗差異來自 fitness 或
selection，而不是不同的 mutation 實作。

### 3.1 Selection 與 elitism

每一代會保留少量 elite，避免目前最佳解被 crossover 或 mutation
破壞。其餘 parents 從族群中較佳的前半部選取。

### 3.2 Single-point crossover

每條 child reel 分別選擇一個切割位置，前段取自 parent A，後段取自
parent B，使 parent 中連續的 symbol 結構可以被保留。

### 3.3 Single-symbol mutation

每個位置以一定機率替換成另一個 symbol，改變各 symbol 的數量並提供
一般性的搜尋能力。

### 3.4 Pair mutation

除了傳統單格 mutation，本專案加入相鄰 pair mutation：

```text
[0, 2, 1, 3] → [0, 2, 2, 3]
```

題目的前四個 winning patterns 都包含 2×2 相同 symbols。要形成 2×2，
相鄰 reels 必須分別具有相鄰相同 symbol，因此 pair mutation 比完全隨機
的單格替換更符合題目結構，也更容易建立可能中獎的 reel segments。

Reel 為環狀結構，所以最後一格與第一格也視為相鄰。

### 3.5 Swap mutation

Swap mutation 交換同一條 reel 的兩個位置：

```text
[0, 1, 2, 3] → [0, 3, 2, 1]
```

它不改變 symbol 數量，只改變排列與相鄰關係，適合對已經接近目標的
symbol frequency 做局部調整。

### 3.6 Missing-symbol repair

Game-design GA 與 NSGA-II 共用一個 domain-specific repair operator。
一般 mutation 完成後，若目前仍有完全不能中獎的 symbol，程式會以：

```python
MISSING_SYMBOL_REPAIR_RATE = 0.30
```

的機率挑選其中一種，並在 `(reel 0, reel 1)` 或
`(reel 1, reel 2)` 各建立一組相鄰 pair。這會直接建立一種可對齊成
2×2 winning pattern 的停止組合。

Baseline GA 不使用這個 repair，因為所有 symbols 都能中獎不是原題
要求。Game-design GA 與 NSGA-II 則使用完全相同的 repair 實作與機率，
避免將 operator 差異誤認為 selection 演算法差異。

### 3.7 停滯處理

普通 GA 停滯時會：

- 執行單格 local search
- 暫時提高 mutation rates
- 加入 random immigrants

Local search 負責改善目前最佳解附近的鄰居；boosted mutation 與
immigrants 則增加跳出 local optimum 的機會。

### 3.8 Cache 與收斂紀錄

相同 reels 可能透過 elite 或 crossover 重複出現。程式使用 immutable
reel key 快取完整枚舉結果，避免重複計算。

每一代的最佳 fitness 與 metrics 會寫入 CSV，再由
[ga_plot.py](./ga_plot.py) 使用 Plotly 產生完整 generations 的 PNG
收斂圖。最後一代最佳解會另外保存成 `best_solution.json`，並產生
獎金分布與 symbol winning-spins 分布圖，方便直接放入報告。

---

## 4. Baseline 解的遊戲設計分析

Baseline GA 的目標只是回答原題。即使 RTP 與 Win rate 達標，仍可能
出現以下問題：

1. Winning spins 集中在少數 symbols。
2. 某些 symbols 存在於 reels，卻完全無法形成 winning pattern。
3. Pattern 4.5 的九格 Jackpot 沒有任何可能的停止組合。
4. 大部分 payout 集中於少數獎級，玩家體驗可能缺乏變化。

### 4.1 Symbol concentration

本專案使用 HHI 衡量各 symbol winning spins 的集中程度：

```python
symbol_concentration = sum(
    (symbol_wins / total_symbol_wins) ** 2
)
```

五種 symbols 完全平均時：

```text
HHI = 5 × 0.2² = 0.2
```

全部集中於單一 symbol 時：

```text
HHI = 1.0
```

因此 concentration 越低越平均，越高則代表中獎集中在少數 symbols。

### 4.2 Jackpot

本報告將命中 Pattern 4.5，也就是 3×3 九格都是相同 symbol，定義為
Jackpot。Jackpot 是否至少存在一個停止組合不是原題的明確要求，但可作為
遊戲設計分析指標。

### 4.3 Baseline 實驗結果

下表應在正式執行 `GA_baseline.py` 後填入精確結果：

| 指標 | Baseline 結果 | 原題是否達標 |
|---|---:|---|
| RTP | 待填入 | 待確認 |
| RTP error | 待填入 | 待確認 |
| Win rate | 待填入 | 待確認 |
| Symbol concentration | 待填入 | 非原題要求 |
| Missing winning symbols | 待填入 | 非原題要求 |
| Jackpot probability | 待填入 | 非原題要求 |

各 symbol winning spins：

| Symbol | Winning spins | Winning-spins share |
|---:|---:|---:|
| 0 | 待填入 | 待填入 |
| 1 | 待填入 | 待填入 |
| 2 | 待填入 | 待填入 |
| 3 | 待填入 | 待填入 |
| 4 | 待填入 | 待填入 |

分析時應先確認 baseline 是否真的存在集中或缺少 Jackpot，再據實描述；
不應在尚未取得結果前預設一定會發生。

---

## 5. 使用 NSGA-II 進行多目標改善

### 5.1 為什麼使用 NSGA-II

RTP 精度與 symbol 分布可能互相衝突：

- 某組 reels 的 RTP 非常接近 95%，但 winning spins 高度集中。
- 另一組 reels 的 symbols 較平均，但 RTP error 稍高。

若使用普通加權 GA，必須先決定兩者的人工權重。NSGA-II 則保留多組
non-dominated solutions，讓不同 trade-offs 形成 Pareto front。

### 5.2 Hard constraints

[NSGAII.py](./NSGAII.py) 將以下條件視為硬限制：

```text
RTP 落在 RTP tolerance
Win rate ≥ 55%
至少存在一個九格 Jackpot
五種 symbols 都至少能產生一次 winning spin
```

Feasible solution 一定優先於 infeasible solution。尚未找到 feasible
solution 時，程式比較正規化後的 constraint violation；搜尋尺度只控制
不合格階段的 selection pressure，不改變合格條件本身。

`missing_symbols == 0` 只保證每種 symbol 至少具有一次中獎機會。
尚未合格時，`missing_symbols / 5` 提供漸進式搜尋方向；合格後仍由
`symbol_concentration` objective 改善 winning spins 是否過度集中。

### 5.3 Pareto objectives

硬條件合格後比較：

```python
objectives = (
    rtp_error,
    symbol_concentration,
)
```

兩項 objectives 都是越小越好。若兩個解各自在一項 objective 較好，
兩者都可能保留在 Pareto front。

### 5.4 Non-dominated sorting 與 crowding distance

NSGA-II 先使用 non-dominated sorting 將族群分成多層 fronts。同一
front 中再利用 crowding distance 保留分布較分散的 solutions，避免所有
結果集中在 Pareto front 的單一區域。

每一代會合併 parents 與 offspring，再從合併族群中選出下一代：

```text
Parents + Offspring
→ Non-dominated sorting
→ Crowding distance
→ Environmental selection
```

最終完整 Pareto front 會輸出到：

```text
nsga2_results/nsga2_pareto_front.csv
```

---

## 6. 優化前後比較

正式報告應從 feasible Pareto front 選取一組推薦解，再與 baseline 使用
相同的完整枚舉方式比較。

| 指標 | Baseline GA | NSGA-II 推薦解 | 變化 |
|---|---:|---:|---:|
| RTP | 待填入 | 待填入 | 待填入 |
| RTP error | 待填入 | 待填入 | 待填入 |
| Win rate | 待填入 | 待填入 | 待填入 |
| Symbol concentration | 待填入 | 待填入 | 待填入 |
| Missing winning symbols | 待填入 | 待填入 | 待填入 |
| Jackpot probability | 待填入 | 待填入 | 待填入 |

判讀時需要注意：

- NSGA-II 的改善不應以破壞原題條件為代價。
- `feasible=0` 時的 Pareto front 仍是不合格解，不能作為最終改善成果。
- Pareto solutions 數量代表 front 中的 individuals，不一定等於不同的
  reel configurations，需注意重複解。
- Symbol concentration 降低才表示 winning spins 變得更平均。

如果 NSGA-II 在設定 generations 內沒有找到 feasible solution，應如實
報告為實驗限制，不應將最小 violation 解描述成成功結果。

---

## 7. 結論與延伸方向

### 7.1 結論

本作業將搜尋問題拆成兩層：

1. 對固定 reels 完整枚舉所有停止位置，得到確定性的 RTP 與 Win rate。
2. 使用演化演算法搜尋無法直接窮舉的 reel configuration 空間。

Baseline GA 負責直接回答原題，pair mutation 等 domain-specific
operators 則利用 winning-pattern 結構提高搜尋效率。取得 baseline 後，
額外分析 symbol concentration、Jackpot 與獎金分布，可以說明數學條件
達標不一定等同於完整的遊戲設計品質。

NSGA-II 是額外的多目標實驗，用來探索 RTP 精度與 symbol balance 的
trade-off。對面試作業而言，Baseline GA 與精確驗證仍是主要交付；
NSGA-II 應視為延伸，而不是完成原題的必要條件。

### 7.2 Prize distribution

目前程式已統計：

```text
小獎：≤1x bet
中獎：>1x 且 <5x bet
大獎：≥5x 且 <10x bet
超大獎：≥10x bet
```

未來可以進一步分析各獎級的 hit probability 與 RTP contribution。若要將
它加入 fitness，必須先定義有依據的目標分布，避免使用任意權重。

### 7.3 Near-win probability

Near win 可以定義為只差一格就命中某個 pattern 的畫面。它不應計入
Win rate 或 payout，但可以作為玩家感受與遊戲節奏的分析指標。

需要注意 near-win 呈現可能涉及玩家保護、公平性與法規問題，因此應將
它用於透明的體驗分析，而不是刻意誤導玩家。

### 7.4 玩家行為分析

若未來取得匿名且經適當同意的實際遊玩資料，可分析：

- Session length
- Bet-size changes
- 玩家在大獎或連敗後的離開機率
- 不同 volatility 對留存的影響
- Bonus 或 Jackpot 對行為的影響

這類分析必須注意隱私、負責任遊戲與避免針對高風險玩家進行剝削性
個人化。

### 7.5 其他演算法方向

- 使用多個 random seeds 比較成功率與穩定性。
- 用普通 GA 的 feasible solution 初始化 NSGA-II。
- 加入 adaptive mutation 與 immigrants 處理停滯。
- 使用 hypervolume 評估 Pareto front 收斂程度。
- 使用不同 reel lengths 或 virtual reels 擴大可表達的機率範圍。

---

## 執行方式

安裝依賴：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

執行規則與精確統計：

```powershell
.\.venv\Scripts\python.exe .\slot_game.py
```

執行 Baseline GA：

```powershell
.\.venv\Scripts\python.exe .\GA_baseline.py
```

執行加入遊戲設計考量的普通 GA：

```powershell
.\.venv\Scripts\python.exe .\GA_game_design.py
```

執行 NSGA-II：

```powershell
.\.venv\Scripts\python.exe .\NSGAII.py
```

普通 GA 執行完會自動產圖。也可以指定 history CSV 手動重新產圖：

```powershell
.\.venv\Scripts\python.exe .\ga_plot.py `
    .\ga_baseline_results\ga_history.csv
```

Game-design GA：

```powershell
.\.venv\Scripts\python.exe .\ga_plot.py `
    .\ga_game_design_results\ga_history.csv
```

舊的 `GA.py` 保留為相容入口，目前等同執行 `GA_baseline.py`。

---

## 專案結構

```text
DS-HomeWork.md    原始作業要求
slot_game.py      Slot Game 規則、payout 與精確枚舉
ga_common.py      共用 operators、metrics、cache 與普通 GA runner
GA_baseline.py    只考量原題要求的 GA
GA_game_design.py 加入 Jackpot 與 symbol concentration 的 GA
NSGAII.py         多目標 NSGA-II 延伸實驗
ga_plot.py        從 GA history 產生 Plotly PNG
GA.py             Baseline GA 相容入口
```
