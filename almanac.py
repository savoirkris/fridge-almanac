"""農民曆資料：用 lunar-python 計算，轉成台灣繁體用語。"""
from datetime import date
from lunar_python import Solar
from opencc import OpenCC

_cc = OpenCC("s2twp")

# 程式庫輸出是簡體、大陸通書用語；這裡覆寫成台灣農民曆慣用寫法。
_TERMS = {
    "平治道涂": "平治道塗",
    "修饰垣墙": "修飾垣牆",
    "馀事勿取": "餘事勿取",
    "诸事不宜": "諸事不宜",
    "馀": "餘",
    "涂": "塗",
    "干支": "干支",
}
WEEKDAYS = "一二三四五六日"

# 台灣常見節日（程式庫內建的是大陸節日表，不採用）
SOLAR_FESTIVALS = {(1, 1): "元旦", (2, 28): "和平紀念日", (4, 4): "兒童節", (5, 1): "勞動節",
                   (9, 28): "教師節", (10, 10): "國慶日", (10, 25): "光復節", (12, 25): "行憲紀念日"}
LUNAR_FESTIVALS = {(1, 1): "春節", (1, 15): "元宵節", (5, 5): "端午節", (7, 7): "七夕",
                   (7, 15): "中元節", (8, 15): "中秋節", (9, 9): "重陽節"}


def tw(text: str) -> str:
    if text in _TERMS:
        return _TERMS[text]
    return _cc.convert(text)


def almanac(d: date) -> dict:
    s = Solar.fromYmd(d.year, d.month, d.day)
    l = s.getLunar()
    today_jq = l.getJieQi()          # 今天剛好是節氣才會有值
    prev_jq, next_jq = l.getPrevJieQi(), l.getNextJieQi()
    nx = next_jq.getSolar()
    festivals = []
    if (d.month, d.day) in SOLAR_FESTIVALS:
        festivals.append(SOLAR_FESTIVALS[(d.month, d.day)])
    if l.getMonth() > 0 and (l.getMonth(), l.getDay()) in LUNAR_FESTIVALS:   # 閏月不算
        festivals.append(LUNAR_FESTIVALS[(l.getMonth(), l.getDay())])
    if any("除夕" in f for f in l.getFestivals()):
        festivals.append("除夕")
    return {
        "date": d.isoformat(),
        "year": d.year, "month": d.month, "day": d.day,
        "weekday": "星期" + WEEKDAYS[d.weekday()],
        "lunar_year": tw(l.getYearInChinese()),
        "lunar_month": tw(l.getMonthInChinese()),
        "lunar_day": tw(l.getDayInChinese()),
        "gz_year": l.getYearInGanZhi(),
        "gz_month": l.getMonthInGanZhi(),
        "gz_day": l.getDayInGanZhi(),
        "shengxiao": tw(l.getYearShengXiao()),
        "jieqi_today": tw(today_jq) if today_jq else "",
        "jieqi_prev": tw(prev_jq.getName()),
        "jieqi_next": tw(next_jq.getName()),
        "jieqi_next_date": f"{nx.getMonth()}/{nx.getDay()}",
        "yi": [tw(x) for x in l.getDayYi()],
        "ji": [tw(x) for x in l.getDayJi()],
        "chong": tw(l.getDayChongDesc()),   # 例：(丁亥)豬
        "sha": tw(l.getDaySha()),           # 例：東
        "festivals": festivals,
    }


if __name__ == "__main__":
    import json, sys
    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    print(json.dumps(almanac(d), ensure_ascii=False, indent=1))
