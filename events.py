"""生日：從 Google 日曆的私人 iCal 網址讀取（環境變數 CAL_ICS_URL），
沒有網址時讀本機 birthdays.json（[{"name": "宥勻", "month": 10, "day": 7}]，不進 git）。
只挑標題含「生日」或 🎂 的事件；每年重複的事件以其月日為準。
"""
import json, os, re
from datetime import date, datetime, timedelta
from pathlib import Path
import requests

HERE = Path(__file__).parent
CACHE = HERE / "events_cache.json"
LOCAL = HERE / "birthdays.json"


def _clean(title: str) -> str:
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", title)   # 去掉 emoji
    t = t.replace("的生日", "").replace("生日快樂！", "").replace("生日", "").strip(" ·!！")
    return t or "生日"


def _from_ics(url: str) -> list:
    from icalendar import Calendar
    cal = Calendar.from_ical(requests.get(url, timeout=20).content)
    out = []
    for ev in cal.walk("VEVENT"):
        title = str(ev.get("SUMMARY", ""))
        if "生日" not in title and "🎂" not in title:
            continue
        start = ev.get("DTSTART").dt
        if isinstance(start, datetime):
            start = start.date()
        rrule = ev.get("RRULE")
        yearly = bool(rrule and "YEARLY" in str(rrule.get("FREQ", "")).upper())
        out.append({"name": _clean(title), "month": start.month, "day": start.day,
                    "year": None if yearly else start.year})
    return out


def birthdays() -> list:
    url = os.environ.get("CAL_ICS_URL")
    if url:
        try:
            data = _from_ics(url)
            CACHE.write_text(json.dumps(data, ensure_ascii=False))
            return data
        except Exception:
            if CACHE.exists():
                return json.loads(CACHE.read_text())
    if LOCAL.exists():
        return json.loads(LOCAL.read_text())
    return []


def on_date(d: date, items=None) -> list:
    items = birthdays() if items is None else items
    return [b["name"] for b in items
            if b["month"] == d.month and b["day"] == d.day and (b.get("year") in (None, d.year))]


def upcoming(d: date, days: int = 14):
    """最近一個生日：(name, date, 幾天後)，今天算 0。"""
    items = birthdays()
    best = None
    for i in range(0, days + 1):
        t = d + timedelta(days=i)
        names = on_date(t, items)
        if names:
            return names[0], t, i
    return best
