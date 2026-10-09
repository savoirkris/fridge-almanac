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
from holidays import info as holiday_info, next_holiday
from icons import svg, CAKE
from events import on_date as birthdays_on, upcoming as next_birthday

HERE = Path(__file__).parent
OUT = HERE / "out"

# 本機用 .env 存授權碼（不進 git）；GitHub Actions 用 repo Secrets
if (HERE / ".env").exists():
    for line in (HERE / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
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
    out = [f'<div class="h{" we" if i in (0, 6) else ""}">{c}</div>' for i, c in enumerate("SMTWTFS")]
    first_wd = (date(d.year, d.month, 1).weekday() + 1) % 7   # 週日 = 0，放第一欄
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


def week_strip(d: date) -> str:
    """當週七天（週日開頭）：今天紅底白字，國定假日紅字。"""
    start = d - timedelta(days=(d.weekday() + 1) % 7)
    out = [f'<div class="h{" we" if i in (0, 6) else ""}">{c}</div>' for i, c in enumerate("SMTWTFS")]
    for i in range(7):
        t = start + timedelta(days=i)
        h = holiday_info(t)
        cls = "now" if t == d else ("hol" if h["holiday"] else ("past" if t < d else ""))   # 週末與國定假日都紅字
        cake = CAKE if birthdays_on(t) else ""
        out.append(f'<div class="d {cls}">{cake}{t.day}</div>')
    return "".join(out)


def month_grid(d: date) -> str:
    """整月日曆（週日開頭）：今天紅底白字，週末與假日紅字，生日有蛋糕，過去的日子細字。"""
    out = [f'<div class="h{" we" if i in (0, 6) else ""}">{c}</div>' for i, c in enumerate("SMTWTFS")]
    first = (date(d.year, d.month, 1).weekday() + 1) % 7
    out += ['<div class="d empty"></div>'] * first
    for day in range(1, calendar.monthrange(d.year, d.month)[1] + 1):
        t = date(d.year, d.month, day)
        h = holiday_info(t)
        cls = ("now hol" if h["holiday"] else "now") if t == d else ("hol" if h["holiday"] else ("past" if t < d else ""))
        cake = CAKE if birthdays_on(t) else ""
        out.append(f'<div class="d {cls}">{cake}{day}</div>')
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


def build_html(d: date, theme: str = "classic", layout: str = "wide") -> str:
    bg, accent = THEMES[theme]
    a = almanac(d)
    w = weather(d)
    ctx = {
        "day": d.day, "year": d.year,
        "wd_en": WD_EN[d.weekday()], "wd_zh": "星期" + WD_ZH[d.weekday()],
        "month_en": MONTH_EN[d.month], "month_zh": MONTH_ZH[d.month],
        "today_line": today_line(d, a),
        "grid": dot_grid(d),
        "week": week_strip(d),
        "month_grid": month_grid(d),
        "updated": datetime.now(TZ).strftime("%m/%d %H:%M"),
        "theme_css": f":root{{--bg:{bg};--accent:{accent};}}",
    }
    if w:
        t = w["today"]
        meta = [f'降雨 {t["pop"]}%', f'紫外線 {t["uv_level"]}', f'日出 {t["sunrise"]} · 日落 {t["sunset"]}']
        if w["stale"]:
            meta.append(f'舊資料 {w["fetched_at"][5:]}')
        cur = w.get("current") or {}
        use_now = layout == "wide" and d == datetime.now(TZ).date() and cur.get("temp") is not None
        if layout == "wide":                       # 天氣在右欄：2×2 小格
            if use_now:                            # 今天：大字是現在，小字補整天範圍與體感
                meta = [f'今日 {rng(t["tmin"], t["tmax"])} · 降雨 {t["pop"]}%', f'紫外線 {t["uv_level"]}',
                        f'日出 {t["sunrise"]} · 日落 {t["sunset"]}', f'體感 {cur["feels"]}°' if cur.get("feels") is not None else ""]
            else:                                  # 明後天：整天預報
                meta = [f'降雨 {t["pop"]}% · 紫外線 {t["uv_level"]}', "", f'日出 {t["sunrise"]} · 日落 {t["sunset"]}', ""]
            if w["stale"]:
                meta[1] = f'舊資料 {w["fetched_at"][5:10]}'
        elif layout.startswith("landscape"):        # 橫式：放大成兩行
            meta = [f'降雨 {t["pop"]}% · 紫外線 {t["uv_level"]}', f'日出 {t["sunrise"]} · 日落 {t["sunset"]}']
            if w["stale"]:
                meta[0] = f'舊資料 {w["fetched_at"][5:10]} · 降雨 {t["pop"]}%'
        slots = []
        for s in w["slots"]:
            dry = "dry" if s["pop"] < 30 else ""
            if layout != "portrait":
                slots.append(f'<div class="slot"><div class="n">{s["name"]}</div>'
                             f'{svg(s["icon"])}<div class="t">{rng(s["tmin"], s["tmax"])}</div>'
                             f'<div class="p {dry}">{s["pop"]}%</div></div>')
                continue
            slots.append(f'<div class="slot"><div class="n">{s["name"]}</div><div class="hrs">{s["hours"]}</div>'
                         f'{svg(s["icon"])}<div class="t">{rng(s["tmin"], s["tmax"])}</div>'
                         f'<div class="p {dry}">{s["pop"]}%</div></div>')
        # 橫式大區塊顯示「現在」的天氣（今天的圖才有現在；明後天仍用整天預報）
        head_icon = cur["icon"] if use_now else t["icon"]
        head_desc = cur["desc"] if use_now else t["desc"]
        head_temp = f'{cur["temp"]}°C' if use_now else rng(t["tmin"], t["tmax"], "°C")
        ctx["wx_day"] = f'日出 {t["sunrise"]} · 日落 {t["sunset"]} · 紫外線 {t["uv_level"]}'
        ctx.update({"wx_icon": svg(head_icon, tight=(layout == "wide")), "wx_desc": head_desc, "wx_temp": head_temp,
                    "wx_meta": "".join(f"<span>{m}</span>" for m in meta) if layout == "wide" else "<br>".join(meta), "slots": "".join(slots), "wx_src": w["source"]})
    else:
        ctx.update({"wx_icon": "", "wx_desc": "天氣暫無資料", "wx_temp": "", "wx_meta": "", "slots": "", "wx_src": "—", "wx_day": ""})
    nh = next_holiday(d)
    ctx["next_hol"] = (f'下個假日 <b>{nh[1]}</b> {nh[0].month}/{nh[0].day} · {nh[2]} 天後' if nh else "")
    nb = next_birthday(d, 7)                          # 一週內有生日就優先顯示
    if nb:
        when = "今天" if nb[2] == 0 else ("明天" if nb[2] == 1 else f"{nb[1].month}/{nb[1].day} · {nb[2]} 天後")
        ctx["next_hol"] = f'{CAKE}<b>{nb[0]} 生日</b> · {when}'
    ctx["body_cls"] = "nodots" if layout == "landscape-nodots" else ""
    # wide 版左欄：第一行節日／節氣，第二行農曆
    h = holiday_info(d)
    name = h["name"] or (a["festivals"][0] if a["festivals"] else "")
    first = []
    if name:
        first.append(f'<span class="hl">{name}</span>')
    if h["makeup_work"]:
        first.append('<span class="hl">補班</span>')
    first.append(f'<span class="hl">今日 {a["jieqi_today"]}</span>' if a["jieqi_today"]
                 else f'{a["jieqi_next"]} {a["jieqi_next_date"]}')
    ctx["info_l1"] = " · ".join(first)
    ctx["info_l2"] = f'農曆 {a["lunar_month"]}月{a["lunar_day"]}'
    ctx["num_cls"] = "hol" if h["holiday"] else ""      # 週末與國定假日大數字紅色
    tpl = {"wide": "template_wide.html", "portrait": "template.html"}.get(layout, "template_landscape.html")
    return fill((HERE / tpl).read_text(encoding="utf-8"), ctx)


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
    """用法：render.py [YYYY-MM-DD] [--theme classic|orange|beige] [--layout wide|portrait] [--days N]"""
    argv = sys.argv[1:]
    theme = argv[argv.index("--theme") + 1] if "--theme" in argv else "classic"
    layout = argv[argv.index("--layout") + 1] if "--layout" in argv else "wide"
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 1
    skip = set()
    for flag in ("--theme", "--layout", "--days"):
        if flag in argv:
            skip.add(argv[argv.index(flag) + 1])
    args = [x for x in argv if not x.startswith("--") and x not in skip]
    d = date.fromisoformat(args[0]) if args else datetime.now(TZ).date()
    OUT.mkdir(exist_ok=True)
    for i in range(days):
        t = d + timedelta(days=i)
        html = build_html(t, theme, layout)
        tag = "" if i == 0 else f"-{t.isoformat()}"            # 今天用固定檔名，其他天加日期
        (OUT / f"calendar{tag}.html").write_text(html, encoding="utf-8")
        screenshot(html, OUT / f"calendar{tag}.png", size=(480, 800) if layout == "portrait" else (800, 480))
        to_eink(OUT / f"calendar{tag}.png", OUT / f"calendar_eink{tag}.png", dither=(theme != "classic"))
        dev = Image.open(OUT / f"calendar_eink{tag}.png")
        if layout == "portrait":                   # 直式版面要轉 90 度才符合面板
            dev = dev.rotate(ROTATE, expand=True)
        dev.save(OUT / f"device-{t.isoformat()}.png", optimize=True)   # 機器依日期抓
        if i == 0:
            dev.save(OUT / "device.png", optimize=True)                 # 固定檔名：今天
        print("ok", t, theme)


if __name__ == "__main__":
    main()
