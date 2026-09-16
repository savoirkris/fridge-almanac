"""天氣圖示：簡單線條 SVG，顏色限制在黑、黃、藍。"""
_SUN = '<circle cx="32" cy="32" r="11" fill="#f5c400"/><g stroke="#f5c400" stroke-width="4" stroke-linecap="round">' + \
       ''.join(f'<line x1="32" y1="32" x2="32" y2="8" transform="rotate({a} 32 32)"/>' for a in range(0, 360, 45)) + '</g>'
_CLOUD = '<path d="M20 50h26a11 11 0 0 0 1-22 15 15 0 0 0-29 4 9 9 0 0 0 2 18z" fill="#fff" stroke="#000" stroke-width="3.5" stroke-linejoin="round"/>'
_CLOUD_DARK = '<path d="M20 50h26a11 11 0 0 0 1-22 15 15 0 0 0-29 4 9 9 0 0 0 2 18z" fill="#000"/>'
_DROPS = '<g stroke="#0040ff" stroke-width="3.5" stroke-linecap="round"><line x1="24" y1="55" x2="21" y2="62"/><line x1="34" y1="55" x2="31" y2="62"/><line x1="44" y1="55" x2="41" y2="62"/></g>'
_DRIZZLE = '<g fill="#0040ff"><circle cx="24" cy="58" r="2.2"/><circle cx="34" cy="58" r="2.2"/><circle cx="44" cy="58" r="2.2"/></g>'
_BOLT = '<path d="M36 46l-8 12h6l-3 9 10-13h-6l3-8z" fill="#f5c400" stroke="#000" stroke-width="1.5" stroke-linejoin="round"/>'
_FOG = '<g stroke="#000" stroke-width="3.5" stroke-linecap="round"><line x1="14" y1="28" x2="50" y2="28"/><line x1="18" y1="38" x2="46" y2="38"/><line x1="22" y1="48" x2="42" y2="48"/></g>'
_SNOW = '<g fill="#000"><circle cx="24" cy="58" r="2.5"/><circle cx="34" cy="58" r="2.5"/><circle cx="44" cy="58" r="2.5"/></g>'
_SMALLSUN = '<g transform="translate(12 -4) scale(.6)">' + _SUN + '</g>'

ICONS = {
    "sun": _SUN,
    "partly": _SMALLSUN + _CLOUD,
    "cloudy": _CLOUD,
    "overcast": _CLOUD_DARK,
    "fog": _FOG,
    "drizzle": _CLOUD + _DRIZZLE,
    "rain": _CLOUD + _DROPS,
    "thunder": _CLOUD_DARK + _BOLT,
    "snow": _CLOUD + _SNOW,
}


def svg(kind: str) -> str:
    return f'<svg viewBox="0 0 64 68" xmlns="http://www.w3.org/2000/svg">{ICONS.get(kind, _CLOUD)}</svg>'
