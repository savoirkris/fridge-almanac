"""產生 480×800 的冰箱日曆圖片（國曆為主、圓點月曆、整天天氣）。
用法：python render.py [YYYY-MM-DD]
輸出：out/calendar.png（預覽）與 out/calendar_eink.png（限制成電子紙六色）
"""
import calendar, os, platform, shutil, subprocess, sys, tempfile, time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image
from almanac import almanac
from weather import weather
from holidays import info as holiday_info
from icons import svg

HERE = Path(__file__).parent
OUT = HERE / "out"
def find_chrome() -> str:
    """CHROME_BIN 環境變數優先；否則依平台找 Chrome / Chromium。"""
    if os.environ.get("CHROME_BIN"):
        return os.environ["CHROME_BIN"]
    if platform.system() == "Darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
        if shutil.which(name):
            return shutil.which(name)
    raise RuntimeError("找不到 Chrome，請設定 CHROME_BIN")


CHROME = find_chrome()
ROTATE = int(os.environ.get("DEVICE_ROTATE", "90"))   # 機器橫放時圖片要轉的角度：90 或 270
TZ = ZoneInfo("Asia/Taipei")
PALETTE = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (255, 255, 0), (0, 0, 255), (0, 255, 0)]
THEMES = {  # 名稱: (背景, 強調色)
    "classic": ("#ffffff", "#e60012"),   # 白底紅點：面板原生色，不用混點
    "orange": ("#ffffff", "#e8672a"),    # 白底橘點：橘色用紅黃混點
    "beige": ("#e9e5dd", "#e8672a"),     # Pinterest 原配色：米灰底整片混點
}
MONTH_EN = ["", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
            "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
MONTH_ZH = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WD_ZH = "一二三四五六日"


def fill(tpl: str, ctx: dict) -> str:
    for k, v in ctx.items():
        tpl = tpl.replace("{{" + k + "}}", str(v))
    return tpl


def dot_grid(d: date) -> str:
    out = [f'<div class="h{" we" if i >= 5 else ""}">{c}</div>' for i, c in enumerate("MTWTFSS")]
    first_wd = date(d.year, d.month, 1).weekday()            # 週一 = 0
    out += ['<div class="dot empty"></div>'] * first_wd
    for day in range(1, calendar.monthrange(d.year, d.month)[1] + 1):
        t = date(d.year, d.month, day)
        if t < d:
            cls = "past"
        elif t == d:
            cls = "now"
        else:
            h = holiday_info(t)
            cls = "future hol" if (h["holiday"] and h["name"]) else "future"
        out.append(f'<div class="dot {cls}" title="{day}"></div>')
    return "".join(out)


def today_line(d: date, a: dict) -> str:
    h = holiday_info(d)
    parts = []
    if h["name"]:
        parts.append(f'<span class="hl">{h["name"]}</span>')
    elif a["festivals"]:
        parts.append(f'<span class="hl">{a["festivals"][0]}</span>')
    if h["makeup_work"]:
        parts.append('<span class="hl">補班</span>')
    if a["jieqi_today"]:
        parts.append(f'<span class="hl">{a["jieqi_today"]}</span>')
    else:
        parts.append(f'<span class="lunar">{a["jieqi_next"]} {a["jieqi_next_date"]}</span>')
    parts.append(f'<span class="lunar">農曆{a["lunar_month"]}月{a["lunar_day"]}</span>')
    return '<span>·</span>'.join(parts)


def rng(lo, hi, unit="°"):
    return f"{lo}{unit}" if lo == hi else f"{lo}–{hi}{unit}"


def build_html(d: date, theme: str = "classic") -> str:
    bg, accent = THEMES[theme]
    a = almanac(d)
    w = weather(d)
    ctx = {
        "day": d.day, "year": d.year,
        "wd_en": WD_EN[d.weekday()], "wd_zh": "星期" + WD_ZH[d.weekday()],
        "month_en": MONTH_EN[d.month], "month_zh": MONTH_ZH[d.month],
        "today_line": today_line(d, a),
        "grid": dot_grid(d),
        "updated": datetime.now(TZ).strftime("%m/%d %H:%M"),
        "theme_css": f":root{{--bg:{bg};--accent:{accent};}}",
    }
    if w:
        t = w["today"]
        meta = [f'降雨 {t["pop"]}%', f'紫外線 {t["uv_level"]}', f'日出 {t["sunrise"]} · 日落 {t["sunset"]}']
        if w["stale"]:
            meta.append(f'舊資料 {w["fetched_at"][5:]}')
        slots = []
        for s in w["slots"]:
            dry = "dry" if s["pop"] < 30 else ""
            slots.append(f'<div class="slot"><div class="n">{s["name"]}</div><div class="hrs">{s["hours"]}</div>'
                         f'{svg(s["icon"])}<div class="t">{rng(s["tmin"], s["tmax"])}</div>'
                         f'<div class="p {dry}">{s["pop"]}%</div></div>')
        ctx.update({"wx_icon": svg(t["icon"]), "wx_desc": t["desc"], "wx_temp": rng(t["tmin"], t["tmax"], "°C"),
                    "wx_meta": "<br>".join(meta), "slots": "".join(slots), "wx_src": w["source"]})
    else:
        ctx.update({"wx_icon": "", "wx_desc": "天氣暫無資料", "wx_temp": "", "wx_meta": "", "slots": "", "wx_src": "—"})
    return fill((HERE / "template.html").read_text(encoding="utf-8"), ctx)


def screenshot(html: str, png: Path, size=(480, 800)) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(html, encoding="utf-8")
        png.unlink(missing_ok=True)
        # Chrome 截圖後常因背景更新程式不退出，所以看到檔案就結束它
        proc = subprocess.Popen([CHROME, "--headless=old", "--disable-gpu", "--hide-scrollbars",
                                 "--no-first-run", "--no-default-browser-check",
                                 f"--user-data-dir={tmp}/profile",
                                 f"--window-size={size[0]},{size[1]}", "--timeout=15000",
                                 f"--screenshot={png}", page.as_uri()],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 60
        while time.time() < deadline and not png.exists() and proc.poll() is None:
            time.sleep(0.3)
        time.sleep(0.5)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if not png.exists():
            raise RuntimeError("Chrome 沒有產生截圖")


def to_eink(src: Path, dst: Path, dither: bool = False) -> None:
    """量化成六色。dither=True 用誤差擴散混點模擬橘色、米灰等面板沒有的顏色。"""
    pal = Image.new("P", (1, 1))
    pal.putpalette(sum(PALETTE, ()) + (0, 0, 0) * (256 - len(PALETTE)))
    mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    Image.open(src).convert("RGB").quantize(palette=pal, dither=mode).convert("RGB").save(dst)


def main():
    """用法：render.py [YYYY-MM-DD] [--theme classic|orange|beige]"""
    argv = sys.argv[1:]
    theme = argv[argv.index("--theme") + 1] if "--theme" in argv else "classic"
    args = [x for x in argv if not x.startswith("--") and x not in THEMES]
    d = date.fromisoformat(args[0]) if args else datetime.now(TZ).date()
    OUT.mkdir(exist_ok=True)
    html = build_html(d, theme)
    (OUT / "calendar.html").write_text(html, encoding="utf-8")
    screenshot(html, OUT / "calendar.png")
    to_eink(OUT / "calendar.png", OUT / "calendar_eink.png", dither=(theme != "classic"))
    # 機器用：轉成 800×480 橫向、只含六色的 PNG
    Image.open(OUT / "calendar_eink.png").rotate(ROTATE, expand=True).save(OUT / "device.png", optimize=True)
    print("ok", d, theme, OUT / "calendar.png")


if __name__ == "__main__":
    main()
