#!/usr/bin/env python3
"""Генерирует SVG-ассеты профиля в стиле Cyberpunk 2077: шапку, иконку-нейтраннера, полосу языков.

Запуск из корня репозитория профиля:

    python3 scripts/gen_assets.py            # всё; языки собираются через gh api (нужен доступ к приватным репо)
    python3 scripts/gen_assets.py --no-fetch # языки берутся из assets/languages.json

Пишет в assets/: header-{dark,light}.svg, netrunner.svg, langs-{dark,light}.svg, languages.json.
PNG-аватар:  rsvg-convert -w 1024 -h 1024 assets/netrunner.svg -o assets/netrunner.png
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

LOGIN = "NameLucky2205"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
LEGEND_MAX = 6  # языков в легенде отдельно, остальное — «Прочее»

# Палитра Cyberpunk 2077: кислотно-жёлтый, циан, красный, чёрный.
YELLOW, CYAN, RED, BLACK = "#fcee0a", "#00f0ff", "#ff003c", "#0a0a0c"

# Цвета как у GitHub Linguist.
LANG_COLORS: Mapping[str, str] = {
    "TypeScript": "#3178c6", "Python": "#3572A5", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "Vue": "#41b883", "CSS": "#663399", "Rust": "#dea584", "Swift": "#F05138", "Shell": "#89e051",
    "PLpgSQL": "#336790", "Java": "#b07219", "Прочее": "#8b949e",
}

THEMES: Mapping[str, Mapping[str, str]] = {
    # тёмная: чёрный экран, жёлтые заголовки, циановые акценты
    "dark": {
        "bg_top": "#0a0a0c", "bg_mid": "#101016", "bg_bottom": "#0b1517",
        "title": YELLOW, "subtitle": "#d4d4dc", "muted": "#6f6f7c",
        "accent": CYAN, "accent2": YELLOW, "glitch_a": CYAN, "glitch_b": RED,
        "grid_text": CYAN, "grid_opacity": "0.10",
        "chip_fill": YELLOW, "chip_fill_opacity": "0.06", "chip_stroke": YELLOW, "chip_text": YELLOW,
        "panel_fill": "#121218", "panel_stroke": CYAN,
        "hood": "#17171e", "hood_stroke": CYAN, "face": "#08080a", "trace": YELLOW,
        "bar_track": "#ffffff", "bar_track_opacity": "0.08", "legend": "#e6e6ee",
    },
    # светлая: фирменный жёлтый постер, чёрный текст, циановый глитч
    "light": {
        "bg_top": "#fcee0a", "bg_mid": "#f9e900", "bg_bottom": "#fcee0a",
        "title": BLACK, "subtitle": "#1c1c20", "muted": "#5c5608",
        "accent": "#00b8c4", "accent2": BLACK, "glitch_a": "#00b8c4", "glitch_b": RED,
        "grid_text": BLACK, "grid_opacity": "0.10",
        "chip_fill": BLACK, "chip_fill_opacity": "0.05", "chip_stroke": BLACK, "chip_text": BLACK,
        "panel_fill": "#0a0a0c", "panel_stroke": BLACK,
        "hood": "#17171e", "hood_stroke": CYAN, "face": "#08080a", "trace": YELLOW,
        "bar_track": BLACK, "bar_track_opacity": "0.10", "legend": BLACK,
    },
}

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
BREACH_ROWS = ("55 1C BD E9 FF 7A", "BD 55 1C 7A E9 55", "1C E9 55 BD 7A FF", "7A BD FF 1C 55 E9", "E9 7A 55 FF BD 1C")


# ---------------------------------------------------------------- языки


def fetch_languages(login: str) -> dict[str, int]:
    """Суммирует байты языков по всем собственным (не форк) репозиториям."""
    listing = subprocess.run(
        ["gh", "repo", "list", login, "--limit", "200", "--json", "name,isFork"],
        check=True, capture_output=True, text=True,
    )
    repos = [r["name"] for r in json.loads(listing.stdout) if not r["isFork"]]
    totals: dict[str, int] = {}
    for name in repos:
        result = subprocess.run(["gh", "api", f"repos/{login}/{name}/languages"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ! {name}: {result.stderr.strip()}", file=sys.stderr)
            continue
        for lang, size in json.loads(result.stdout).items():
            totals = {**totals, lang: totals.get(lang, 0) + size}
    if not totals:
        raise RuntimeError("не удалось получить данные ни по одному репозиторию")
    return totals


def to_shares(totals: Mapping[str, int]) -> list[tuple[str, float]]:
    """Доли в процентах: топ-N языков отдельно, остальные — «Прочее»."""
    total = sum(totals.values())
    ordered = sorted(totals.items(), key=lambda kv: -kv[1])
    head = [(lang, 100 * size / total) for lang, size in ordered[:LEGEND_MAX]]
    rest = sum(size for _, size in ordered[LEGEND_MAX:])
    return head if rest == 0 else [*head, ("Прочее", 100 * rest / total)]


def load_cached_shares() -> list[tuple[str, float]]:
    cache = ASSETS / "languages.json"
    if not cache.exists():
        raise FileNotFoundError(f"нет кэша {cache}; запустите без --no-fetch")
    return [(row["lang"], float(row["percent"])) for row in json.loads(cache.read_text(encoding="utf-8"))]


def save_shares(shares: Sequence[tuple[str, float]]) -> None:
    rows = [{"lang": lang, "percent": round(pct, 2)} for lang, pct in shares]
    (ASSETS / "languages.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- примитивы


def chamfer(x: float, y: float, w: float, h: float, c: float) -> str:
    """Точки многоугольника со срезанными углами (верхний левый и нижний правый) — фирменная рамка CP2077."""
    return f"{x + c},{y} {x + w},{y} {x + w},{y + h - c} {x + w - c},{y + h} {x},{y + h} {x},{y + c}"


def ecg_path(width: int, baseline: int, start: int = 40, beat: int = 300) -> str:
    """Линия кардиограммы: ровный участок и комплекс P-QRS-T каждые `beat` px."""
    parts, x = [f"M0 {baseline}"], start
    while x + 160 < width:
        parts.append(f"H{x} l8 -6 l8 6 H{x + 52} l5 -40 l9 72 l5 -32 H{x + 108} l12 -12 l12 12")
        x += beat
    return " ".join([*parts, f"H{width}"])


def chip(x: int, y: int, label: str, t: Mapping[str, str]) -> str:
    width = int(len(label) * 8.4) + 26
    return (
        f'<g transform="translate({x} {y})">'
        f'<polygon points="{chamfer(0, 0, width, 28, 7)}" fill="{t["chip_fill"]}" fill-opacity="{t["chip_fill_opacity"]}" '
        f'stroke="{t["chip_stroke"]}" stroke-opacity="0.7" stroke-width="1.2"/>'
        f'<text x="{width / 2}" y="18.5" text-anchor="middle" font-family="{MONO}" font-size="13" '
        f'fill="{t["chip_text"]}">{label}</text></g>'
    )


def chips_row(labels: Sequence[str], x: int, y: int, t: Mapping[str, str]) -> str:
    out, cursor = [], x
    for label in labels:
        out.append(chip(cursor, y, label, t))
        cursor += int(len(label) * 8.4) + 26 + 10
    return "".join(out)


def glitch_text(x: int, y: int, text: str, size: int, t: Mapping[str, str], uid: str) -> str:
    """Текст с глитчем: две цветные копии, обрезанные прыгающими полосами."""
    common = f'font-family="{SANS}" font-size="{size}" font-weight="800" letter-spacing="-1"'
    cursor = f'<tspan fill="{t["accent"]}" font-weight="400">▌<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" repeatCount="indefinite"/></tspan>'
    text = f"{text}{cursor}"
    band = f'<rect x="0" y="{y - size}" width="1200" height="{size * 0.3:.0f}">'
    jump_a = f'<animate attributeName="y" values="{y - size};{y - size * 0.5:.0f};{y - size * 0.8:.0f};{y - size * 0.2:.0f};{y - size}" calcMode="discrete" dur="2.3s" repeatCount="indefinite"/>'
    jump_b = f'<animate attributeName="y" values="{y - size * 0.3:.0f};{y - size};{y - size * 0.6:.0f};{y - size * 0.9:.0f};{y - size * 0.3:.0f}" calcMode="discrete" dur="1.7s" repeatCount="indefinite"/>'
    return (
        f'<defs><clipPath id="{uid}a">{band}{jump_a}</rect></clipPath>'
        f'<clipPath id="{uid}b">{band}{jump_b}</rect></clipPath></defs>'
        f'<text x="{x}" y="{y}" {common} fill="{t["title"]}">{text}</text>'
        f'<g clip-path="url(#{uid}a)"><text x="{x - 3}" y="{y}" {common} fill="{t["glitch_a"]}">{text}</text></g>'
        f'<g clip-path="url(#{uid}b)"><text x="{x + 3}" y="{y + 1}" {common} fill="{t["glitch_b"]}" fill-opacity="0.85">{text}</text></g>'
    )


def breach_grid(x: int, y: int, t: Mapping[str, str]) -> str:
    """Сетка байтов как в мини-игре Breach Protocol; одна строка подсвечивается по кругу."""
    rows = []
    for i, row in enumerate(BREACH_ROWS):
        begin = f"{i * 1.2:.1f}s"
        rows.append(
            f'<text x="{x}" y="{y + i * 22}" font-family="{MONO}" font-size="14" letter-spacing="3" '
            f'fill="{t["grid_text"]}" fill-opacity="{t["grid_opacity"]}">{row}'
            f'<animate attributeName="fill-opacity" values="{t["grid_opacity"]};0.55;{t["grid_opacity"]}" '
            f'dur="6s" begin="{begin}" repeatCount="indefinite"/></text>'
        )
    return "".join(rows)


# ---------------------------------------------------------------- нейтраннер


def netrunner(t: Mapping[str, str], uid: str = "nr") -> str:
    """Фигура нейтраннера в системе координат 0..256: капюшон, визор, дорожки, разъём, глитч-полосы."""
    return f"""<g>
    <defs>
      <filter id="{uid}glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="4"/></filter>
      <linearGradient id="{uid}visor" x1="0" x2="1"><stop offset="0" stop-color="{t["accent"]}" stop-opacity="0.2"/><stop offset="0.5" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity="0.2"/></linearGradient>
    </defs>
    <path d="M22 262 L60 206 L196 206 L234 262 Z" fill="{t["hood"]}" stroke="{t["hood_stroke"]}" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M128 20 C116 42 82 60 66 110 C58 138 54 174 52 208 L204 208 C202 174 198 138 190 110 C174 60 140 42 128 20 Z" fill="{t["hood"]}" stroke="{t["hood_stroke"]}" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M128 60 C114 74 98 98 93 126 L90 190 L166 190 L163 126 C158 98 142 74 128 60 Z" fill="{t["face"]}"/>
    <g stroke="{t["accent"]}" stroke-width="1.5" opacity="0.55"><line x1="110" y1="160" x2="146" y2="160"/><line x1="112" y1="168" x2="144" y2="168"/><line x1="116" y1="176" x2="140" y2="176"/></g>
    <g stroke="{t["trace"]}" stroke-width="1.6" fill="none" stroke-linecap="round">
      <polyline points="70,120 84,120 92,108 104,108"/><polyline points="66,150 80,150 88,140"/>
      <polyline points="186,120 172,120 164,108 152,108"/><polyline points="190,150 176,150 168,140"/>
      <polyline points="60,186 78,186 86,178"/><polyline points="196,186 178,186 170,178"/>
    </g>
    <g fill="{t["trace"]}"><circle cx="104" cy="108" r="2.6"/><circle cx="152" cy="108" r="2.6"/><circle cx="88" cy="140" r="2.2"/><circle cx="168" cy="140" r="2.2"/><circle cx="86" cy="178" r="2.2"/><circle cx="170" cy="178" r="2.2"/></g>
    <polygon points="90,126 166,126 162,142 94,142" fill="{t["accent"]}" opacity="0.7" filter="url(#{uid}glow)"/>
    <polygon points="92,128 164,128 160,140 96,140" fill="url(#{uid}visor)">
      <animate attributeName="opacity" values="1;1;0.55;1;1;0.8;1" dur="3.4s" repeatCount="indefinite"/>
    </polygon>
    <rect x="96" y="148" width="64" height="2" fill="{t["trace"]}" opacity="0.9"/>
    <rect x="196" y="214" width="14" height="10" fill="{t["accent"]}"/>
    <path d="M210 219 C232 219 240 234 240 262" fill="none" stroke="{t["accent"]}" stroke-width="2.5"/>
    <rect x="40" y="96" width="176" height="3" fill="{t["glitch_a"]}" opacity="0"><animate attributeName="opacity" values="0;0;1;0;0;0;1;0" calcMode="discrete" dur="2.9s" repeatCount="indefinite"/></rect>
    <rect x="46" y="164" width="164" height="3" fill="{t["glitch_b"]}" opacity="0"><animate attributeName="opacity" values="0;1;0;0;0;1;0;0" calcMode="discrete" dur="3.7s" repeatCount="indefinite"/></rect>
  </g>"""


def render_avatar() -> str:
    """Отдельная иконка 512×512 под круглую обрезку аватара GitHub."""
    t = THEMES["dark"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="Нейтраннер — аватар {LOGIN}">
  <defs>
    <radialGradient id="avbg" cx="0.5" cy="0.45" r="0.7"><stop offset="0" stop-color="#15151c"/><stop offset="1" stop-color="{BLACK}"/></radialGradient>
    <clipPath id="avring"><circle cx="256" cy="256" r="256"/></clipPath>
  </defs>
  <g clip-path="url(#avring)">
    <rect width="512" height="512" fill="url(#avbg)"/>
    <g transform="translate(96 88)">{breach_grid(0, 0, t)}</g>
    <g transform="translate(300 380)">{breach_grid(0, 0, t)}</g>
    <circle cx="256" cy="256" r="236" fill="none" stroke="{YELLOW}" stroke-width="10" pathLength="1" stroke-dasharray="0.42 0.05 0.28 0.05 0.15 0.05" stroke-linecap="butt">
      <animateTransform attributeName="transform" type="rotate" from="0 256 256" to="360 256 256" dur="40s" repeatCount="indefinite"/>
    </circle>
    <circle cx="256" cy="256" r="222" fill="none" stroke="{CYAN}" stroke-width="2" opacity="0.6"/>
    <g transform="translate(76 76) scale(1.4)">{netrunner(t, "av")}</g>
  </g>
</svg>
"""


# ---------------------------------------------------------------- шапка


def render_header(theme: str) -> str:
    t = THEMES[theme]
    w, h = 1200, 320
    line = ecg_path(w, 276)
    tags = ["AVATEK", "Pulse", "Pantheon LLM", "AVAREANGE", "Mr. Robot", "LabStock"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{LOGIN} — AI-агенты, кибербезопасность, своя LLM-инфраструктура">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{t["bg_top"]}"/><stop offset="0.55" stop-color="{t["bg_mid"]}"/><stop offset="1" stop-color="{t["bg_bottom"]}"/>
    </linearGradient>
    <linearGradient id="line" x1="0" x2="1"><stop offset="0" stop-color="{t["accent2"]}"/><stop offset="1" stop-color="{t["accent"]}"/></linearGradient>
    <pattern id="hazard" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="7" height="14" fill="{t["accent2"]}" fill-opacity="0.9"/>
    </pattern>
    <filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
    <clipPath id="frame"><polygon points="{chamfer(0, 0, w, h, 26)}"/></clipPath>
  </defs>

  <g clip-path="url(#frame)">
    <rect width="{w}" height="{h}" fill="url(#bg)"/>
    <g filter="url(#soft)" opacity="{"0.35" if theme == "dark" else "0.18"}">
      <circle cx="980" cy="60" r="150" fill="{t["accent"]}"><animateTransform attributeName="transform" type="translate" values="0 0; -40 30; 0 0" dur="16s" repeatCount="indefinite"/></circle>
      <circle cx="120" cy="300" r="130" fill="{t["accent2"] if theme == "dark" else t["accent"]}"><animateTransform attributeName="transform" type="translate" values="0 0; 50 -30; 0 0" dur="19s" repeatCount="indefinite"/></circle>
    </g>
    {breach_grid(700, 78, t)}

    <rect x="0" y="0" width="{w}" height="6" fill="url(#hazard)"/>
    <rect x="0" y="{h - 6}" width="{w}" height="6" fill="url(#hazard)"/>

    <path d="{line}" fill="none" stroke="{t["accent"]}" stroke-opacity="0.18" stroke-width="2" stroke-linejoin="round"/>
    <path d="{line}" fill="none" stroke="url(#line)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" pathLength="1" stroke-dasharray="0.22 0.78">
      <animate attributeName="stroke-dashoffset" from="1" to="0" dur="7s" repeatCount="indefinite"/>
    </path>

    <text x="72" y="82" font-family="{MONO}" font-size="15" letter-spacing="2" fill="{t["accent"]}">// NETRUNNER ~ $ whoami</text>
    {glitch_text(72, 148, LOGIN, 60, t, "g")}
    <text x="72" y="190" font-family="{SANS}" font-size="22" fill="{t["subtitle"]}">AI-агенты · кибербезопасность · своя LLM-инфраструктура</text>
    {chips_row(tags, 72, 212, t)}

    <g transform="translate(920 38)">
      <polygon points="{chamfer(0, 0, 210, 244, 18)}" fill="{t["panel_fill"]}" stroke="{t["panel_stroke"]}" stroke-width="1.5"/>
      <g transform="translate(-2 -6) scale(0.84)">{netrunner(t, "hd")}</g>
      <text x="105" y="232" text-anchor="middle" font-family="{MONO}" font-size="12" letter-spacing="4" fill="{t["accent"]}">NETRUNNER</text>
    </g>
  </g>
</svg>
"""


# ---------------------------------------------------------------- языки (SVG)


def render_langs(theme: str, shares: Sequence[tuple[str, float]]) -> str:
    t = THEMES[theme]
    w, bar_x, bar_w, bar_y, bar_h = 900, 20, 860, 44, 14
    segments, legend, x = [], [], float(bar_x)
    for i, (lang, pct) in enumerate(shares):
        seg_w = bar_w * pct / 100
        color = LANG_COLORS.get(lang, "#8b949e")
        segments.append(
            f'<rect x="{x:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{seg_w:.2f}" dur="0.9s" begin="{i * 0.08:.2f}s" fill="freeze"/></rect>'
        )
        lx, ly = bar_x + (i % 4) * 215, bar_y + 46 + (i // 4) * 26
        legend.append(
            f'<circle cx="{lx + 6}" cy="{ly - 4}" r="6" fill="{color}"/>'
            f'<text x="{lx + 20}" y="{ly}" font-family="{SANS}" font-size="14" fill="{t["legend"]}">{lang} '
            f'<tspan font-family="{MONO}" font-size="13" fill="{t["muted"]}">{pct:.1f}%</tspan></text>'
        )
        x += seg_w
    h = bar_y + 46 + ((len(shares) + 3) // 4) * 26 + 4
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Языки в репозиториях {LOGIN}">
  <defs><clipPath id="bar"><polygon points="{chamfer(bar_x, bar_y, bar_w, bar_h, 6)}"/></clipPath></defs>
  <text x="{bar_x}" y="26" font-family="{MONO}" font-size="15" letter-spacing="2" fill="{t["accent2"] if theme == "dark" else t["title"]}">// ЯЗЫКИ В МОИХ РЕПОЗИТОРИЯХ</text>
  <text x="{w - bar_x}" y="26" text-anchor="end" font-family="{MONO}" font-size="12" fill="{t["muted"]}">по байтам кода, включая приватные</text>
  <polygon points="{chamfer(bar_x, bar_y, bar_w, bar_h, 6)}" fill="{t["bar_track"]}" fill-opacity="{t["bar_track_opacity"]}"/>
  <g clip-path="url(#bar)">{"".join(segments)}</g>
  {"".join(legend)}
</svg>
"""


# ---------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-fetch", action="store_true", help="не ходить в gh api, взять assets/languages.json")
    args = parser.parse_args()

    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (ASSETS / f"header-{theme}.svg").write_text(render_header(theme), encoding="utf-8")
        print(f"  ✓ assets/header-{theme}.svg")
    (ASSETS / "netrunner.svg").write_text(render_avatar(), encoding="utf-8")
    print("  ✓ assets/netrunner.svg")

    try:
        shares = load_cached_shares() if args.no_fetch else to_shares(fetch_languages(LOGIN))
    except (RuntimeError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"языки: {exc}", file=sys.stderr)
        return 1
    if not args.no_fetch:
        save_shares(shares)
    for theme in THEMES:
        (ASSETS / f"langs-{theme}.svg").write_text(render_langs(theme, shares), encoding="utf-8")
        print(f"  ✓ assets/langs-{theme}.svg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
