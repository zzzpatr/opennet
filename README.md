# Slot Game－第一步

目前只有最基本的模擬器：

1. 三個滾輪各自隨機停止。
2. 每個滾輪顯示連續三個 symbol。
3. 超過滾輪尾端時會回到開頭。
4. 執行一次會輸出一個 3×3 畫面。

執行：

```powershell
.\.venv\Scripts\python.exe .\slot_game.py
```

目前尚未加入 winning pattern、獎金與 RTP 計算。

執行簡易 Genetic Algorithm 搜尋 reels：

```powershell
.\.venv\Scripts\python.exe .\genetic_algorithm.py
```

GA 目前固定每個 reel 為 8 格，fitness 會同時考慮：

- RTP 與 `0.95` 的距離。
- Win rate 低於 `0.55` 的差距。
- 是否有使用全部五種 symbols。
