"""台灣放假、補假、補班：政府行政機關辦公日曆表（ruyut/TaiwanCalendar 整理版）。"""
import json
from datetime import date, timedelta
from pathlib import Path
import requests

URL = "https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json"
HERE = Path(__file__).parent
_cache: dict = {}


def _year(y: int) -> dict:
    if y in _cache:
        return _cache[y]
    f = HERE / f"holidays_{y}.json"
    try:
        data = requests.get(URL.format(year=y), timeout=15).json()
        f.write_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        data = json.loads(f.read_text()) if f.exists() else []
    _cache[y] = {x["date"]: x for x in data}
    return _cache[y]


def info(d: date) -> dict:
    """{'holiday': bool, 'name': '中秋節' 或 '', 'makeup_work': bool}"""
    x = _year(d.year).get(d.strftime("%Y%m%d"))
    if not x:
        return {"holiday": d.weekday() >= 5, "name": "", "makeup_work": False}
    desc = x.get("description", "")
    return {"holiday": bool(x["isHoliday"]), "name": desc if x["isHoliday"] else "",
            "makeup_work": (not x["isHoliday"]) and d.weekday() >= 5}


def next_holiday(d: date, limit=120):
    """下一個有名字的假日（含補假），回傳 (date, name, 天數)。"""
    for i in range(1, limit):
        t = d + timedelta(days=i)
        h = info(t)
        if h["holiday"] and h["name"]:
            return t, h["name"], i
    return None


def next_makeup_work(d: date, limit=21):
    for i in range(0, limit):
        t = d + timedelta(days=i)
        if info(t)["makeup_work"]:
            return t, i
    return None
