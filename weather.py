"""高雄市天氣：Open-Meteo 7 天逐小時預報（免金鑰）。
有 CWA_API_KEY 時，今天的天氣描述與降雨機率改用中央氣象署的官方文字。
抓失敗時沿用上次快取，並標記是舊資料。
"""
import json, os, time
from datetime import date
from pathlib import Path
import requests

CACHE = Path(__file__).with_name("weather_cache.json")
CITY = "高雄市"
LAT, LON = 22.627, 120.301
TIMEOUT = 15

# WMO 天氣代碼 → (中文, 圖示類別, 嚴重度)
_WMO = {0: ("晴", "sun", 0), 1: ("晴時多雲", "partly", 1), 2: ("多雲", "cloudy", 2), 3: ("陰", "overcast", 3),
        45: ("霧", "fog", 4), 48: ("霧", "fog", 4),
        51: ("毛毛雨", "drizzle", 5), 53: ("毛毛雨", "drizzle", 5), 55: ("毛毛雨", "drizzle", 5),
        56: ("凍雨", "rain", 6), 57: ("凍雨", "rain", 6),
        61: ("小雨", "rain", 6), 63: ("雨", "rain", 7), 65: ("大雨", "rain", 8),
        66: ("凍雨", "rain", 7), 67: ("凍雨", "rain", 8),
        71: ("小雪", "snow", 6), 73: ("雪", "snow", 7), 75: ("大雪", "snow", 8), 77: ("雪", "snow", 7),
        80: ("陣雨", "rain", 6), 81: ("陣雨", "rain", 7), 82: ("強陣雨", "rain", 8),
        85: ("陣雪", "snow", 7), 86: ("陣雪", "snow", 8),
        95: ("雷雨", "thunder", 9), 96: ("雷雨", "thunder", 9), 99: ("雷雨", "thunder", 9)}
SLOTS = [("清晨", 0, 6), ("上午", 6, 12), ("下午", 12, 18), ("晚上", 18, 24)]


def _code(c):
    return _WMO.get(c, ("—", "cloudy", 2))


def uv_level(uv):
    if uv is None:
        return ""
    if uv < 3: return "低"
    if uv < 6: return "中"
    if uv < 8: return "高"
    if uv < 11: return "過量"
    return "危險"


def _open_meteo(d: date) -> dict:
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": LAT, "longitude": LON, "timezone": "Asia/Taipei",
                "start_date": d.isoformat(), "end_date": (d.fromordinal(d.toordinal() + 6)).isoformat(),
                "hourly": "temperature_2m,precipitation_probability,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                         "precipitation_probability_max,sunrise,sunset,uv_index_max"},
        timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    h, dy = j["hourly"], j["daily"]

    # 今天四個時段：取時段內最嚴重的天氣、溫度範圍、最高降雨機率
    slots = []
    for name, a, b in SLOTS:
        idx = [i for i, t in enumerate(h["time"]) if t.startswith(d.isoformat()) and a <= int(t[11:13]) < b]
        codes = [h["weather_code"][i] for i in idx]
        temps = [h["temperature_2m"][i] for i in idx]
        pops = [h["precipitation_probability"][i] for i in idx]
        worst = max(codes, key=lambda c: _code(c)[2])
        slots.append({"name": name, "hours": f"{a:02d}–{b:02d}", "desc": _code(worst)[0], "icon": _code(worst)[1],
                      "tmin": round(min(temps)), "tmax": round(max(temps)), "pop": max(pops)})

    days = []
    for i, t in enumerate(dy["time"]):
        c = _code(dy["weather_code"][i])
        days.append({"date": t, "desc": c[0], "icon": c[1],
                     "tmax": round(dy["temperature_2m_max"][i]), "tmin": round(dy["temperature_2m_min"][i]),
                     "pop": dy["precipitation_probability_max"][i]})
    today = days[0]
    return {"today": {**today, "sunrise": dy["sunrise"][0][11:], "sunset": dy["sunset"][0][11:],
                      "uv": round(dy["uv_index_max"][0]), "uv_level": uv_level(dy["uv_index_max"][0])},
            "slots": slots, "days": days, "source": "Open-Meteo"}


def _icon_from_text(desc: str) -> str:
    """氣象署的文字描述 → 圖示類別"""
    if "雷" in desc: return "thunder"
    if "大雨" in desc or "豪雨" in desc: return "rain"
    if "雨" in desc: return "drizzle" if "短暫" in desc or "局部" in desc else "rain"
    if "霧" in desc: return "fog"
    if "陰" in desc: return "overcast"
    if "多雲" in desc: return "partly" if "晴" in desc else "cloudy"
    if "晴" in desc: return "sun"
    return "cloudy"


def _cwa_headline(key: str) -> dict:
    r = requests.get(
        "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001",
        params={"Authorization": key, "locationName": CITY, "format": "JSON"}, timeout=TIMEOUT)
    r.raise_for_status()
    loc = r.json()["records"]["location"][0]
    el = {e["elementName"]: e["time"][0]["parameter"]["parameterName"] for e in loc["weatherElement"]}
    return {"desc": el["Wx"], "pop": int(el["PoP"]) if el["PoP"].strip() else None}


def weather(d: date) -> dict:
    try:
        w = _open_meteo(d)
        key = os.environ.get("CWA_API_KEY")
        if key:
            try:
                hl = _cwa_headline(key)
                w["today"]["desc"] = hl["desc"]
                w["today"]["icon"] = _icon_from_text(hl["desc"])
                if hl["pop"] is not None:
                    w["today"]["pop"] = hl["pop"]
                w["source"] = "中央氣象署 / Open-Meteo"
            except Exception:
                pass                                   # 官方資料抓不到就維持 Open-Meteo
        w["fetched_at"] = time.strftime("%Y-%m-%d %H:%M")
        w["stale"] = False
        CACHE.write_text(json.dumps(w, ensure_ascii=False))
        return w
    except Exception as e:
        if CACHE.exists():
            w = json.loads(CACHE.read_text())
            w["stale"] = True
            w["error"] = str(e)
            return w
        return None


if __name__ == "__main__":
    print(json.dumps(weather(date.today()), ensure_ascii=False, indent=1))
