# 冰箱日曆（高雄市）

每天產生一張日曆圖片給 Wi-Fi 彩色電子紙（Seeed reTerminal E1002）顯示。
國曆為主、Dieter Rams 風格圓點月曆、當天節日或節氣、整天四個時段的天氣。

## 架構

1. **出圖**：`render.py` 用 lunar-python、Open-Meteo、台灣行事曆組出網頁，Chrome 截圖成 480×800 PNG，量化成電子紙六色，再轉成 800×480 橫向的 `out/device.png`。
2. **排程**：`.github/workflows/render.yml` 在 GitHub Actions 每天台灣時間 00:10、06:10、12:10、18:10 出圖，發佈到 GitHub Pages。
3. **機器**：`device/reterminal-e1002.yaml` 是 ESPHome 設定，機器每 6 小時醒來抓 `device.png` 顯示後深度睡眠。

## 本機執行

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python render.py                       # 今天
./.venv/bin/python render.py 2026-09-25            # 指定日期（16 天內有天氣預報）
./.venv/bin/python render.py --theme orange        # 白底橘點；預設 classic 白底紅點
DEVICE_ROTATE=270 ./.venv/bin/python render.py     # 機器反過來掛時改轉向
```

輸出在 `out/`：`calendar.png` 預覽、`calendar_eink.png` 六色版、`device.png` 機器用、`calendar.html` 版面。

## 資料來源

- 天氣：Open-Meteo 逐小時預報（免金鑰），含日出日落與紫外線。設定 `CWA_API_KEY`（中央氣象署授權碼，GitHub 上放在 repo Secrets）後，今天的天氣描述與降雨機率改用氣象署文字。
- 假日、補假、補班：政府行政機關辦公日曆表（ruyut/TaiwanCalendar 整理版）。
- 農曆、節氣：lunar-python，轉台灣繁體。

抓不到天氣時沿用快取並標示舊資料；機器抓不到圖時保留上一張。

## 版面規則

- 圓點：過去實心黑、今天紅、未來空心；未來的國定假日與補假紅色空心。
- 日期下方一行：國定假日或節日、補班、當天節氣（皆紅字），否則顯示下一個節氣日期，再接農曆日期。
- 顏色只用 Spectra 6 面板原生的黑、白、紅、黃、藍，不靠混點。

## 機器注意事項

- TRMNL 韌體在 E1002 上只有黑白模式，所以不走 TRMNL，用 ESPHome。
- 只支援 2.4GHz Wi-Fi。
- 機身是橫式，這個版面是直式，掛的時候轉 90 度；方向不對就改 `DEVICE_ROTATE`。
