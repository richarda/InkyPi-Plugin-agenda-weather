"""
Pure PIL/Pillow renderer for the Agenda + Weather dashboard plugin.

Produces a crisp, e-paper-optimised image without any browser dependency.
Designed for 7-colour Inky Impression displays (800×480) but works with
any resolution.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from utils.app_utils import get_font

logger = logging.getLogger(__name__)

# ── colour palette (7-colour Inky Impression safe) ────────────────────
WHITE      = (255, 255, 255)
BLACK      = (0,   0,   0)
RED        = (224, 0,   0)
GREEN      = (0,   200, 0)
BLUE       = (0,   0,   255)
YELLOW     = (255, 200, 0)
ORANGE     = (255, 128, 0)
DARK_BLUE  = (0,   50,  140)   # deeper blue for tomorrow/day-after headers
DARK_GRAY  = (80,  80,  80)    # secondary text
MED_GRAY   = (150, 150, 150)   # subtle text / borders
LIGHT_GRAY = (218, 218, 218)   # dividers / slot backgrounds


def _load_weather_icon(icon_path: str | None, size: int) -> Image.Image | None:
    """Load a weather icon from *icon_path* and resize to *size*×*size*.

    Returns ``None`` when the path is missing or the file cannot be opened.
    """
    if not icon_path or not os.path.isfile(icon_path):
        return None
    try:
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((size, size), Image.LANCZOS)
        return icon
    except Exception as exc:
        logger.warning("Failed to load weather icon %s: %s", icon_path, exc)
        return None


def _paste_icon(img: Image.Image, icon: Image.Image, x: int, y: int):
    """Paste an RGBA icon onto *img* at (x, y) using the alpha channel as mask."""
    img.paste(icon, (x, y), icon)

# ── compact weather labels for small slots ───────────────────────────
WEATHER_SYMBOLS_SHORT: dict[int, str] = {
    0: "Clear",
    1: "Clear",
    2: "P.Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Lt Rain",
    63: "Rain",
    65: "Hvy Rain",
    71: "Lt Snow",
    73: "Snow",
    75: "Hvy Snow",
    80: "Showers",
    81: "Showers",
    82: "Showers",
    95: "Thunder",
    96: "Thunder",
    99: "Thunder",
}
WEATHER_SYMBOLS: dict[int, str] = {
    0: "Clear",
    1: "Mostly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Light Drizzle",
    53: "Drizzle",
    55: "Heavy Drizzle",
    61: "Light Rain",
    63: "Rain",
    65: "Heavy Rain",
    71: "Light Snow",
    73: "Snow",
    75: "Heavy Snow",
    80: "Showers",
    81: "Rain Showers",
    82: "Heavy Showers",
    95: "Thunderstorm",
    96: "T-storm + Hail",
    99: "T-storm + Hail",
}


def _convert_temp(celsius: float | None, units: str) -> str:
    """Return a formatted temperature string in the requested unit system."""
    if celsius is None:
        return "--"
    if units == "imperial":
        return f"{round(celsius * 9 / 5 + 32)}°F"
    elif units == "standard":
        return f"{round(celsius + 273.15)}K"
    else:  # metric
        return f"{round(celsius)}°C"


def _convert_temp_short(celsius: float | None, units: str) -> str:
    """Short temp string without unit suffix (for ranges)."""
    if celsius is None:
        return "--"
    if units == "imperial":
        return f"{round(celsius * 9 / 5 + 32)}°"
    elif units == "standard":
        return f"{round(celsius + 273.15)}°"
    else:
        return f"{round(celsius)}°"


def _unit_suffix(units: str) -> str:
    if units == "imperial":
        return "F"
    elif units == "standard":
        return "K"
    return "C"


# ── main entry point ──────────────────────────────────────────────────
def render_dashboard(
    dimensions: tuple[int, int],
    events: list[dict[str, Any]],
    weather: dict[str, Any] | None,
    current_dt: datetime,
    timezone_str: str,
    time_format: str = "12h",
    labels: dict[str, str] | None = None,
    locale_code: str = "en",
    font_scale: float = 1.0,
    bg_color: str = "#ffffff",
    text_color: str = "#000000",
    units: str = "imperial",
) -> Image.Image:
    """Render the agenda + weather dashboard entirely via PIL."""
    width, height = dimensions
    labels = labels or {}

    # Parse colours
    try:
        bg = _parse_color(bg_color)
    except Exception:
        bg = WHITE
    try:
        fg = _parse_color(text_color)
    except Exception:
        fg = BLACK

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # ── fonts ──────────────────────────────────────────────────────────
    title_size = int(28 * font_scale)
    header_size = int(20 * font_scale)
    event_size = int(17 * font_scale)
    weather_big = int(32 * font_scale)
    weather_med = int(20 * font_scale)
    weather_sm = int(15 * font_scale)

    font_title = get_font("Jost", title_size, "bold") or ImageFont.load_default()
    font_header = get_font("Jost", header_size, "bold") or ImageFont.load_default()
    font_event = get_font("Jost", event_size) or ImageFont.load_default()
    font_event_bold = get_font("Jost", event_size, "bold") or ImageFont.load_default()
    font_weather_big = get_font("Jost", weather_big, "bold") or ImageFont.load_default()
    font_weather_med = get_font("Jost", weather_med, "bold") or ImageFont.load_default()
    font_weather_sm = get_font("Jost", weather_sm) or ImageFont.load_default()
    font_weather_sm_bold = get_font("Jost", weather_sm, "bold") or ImageFont.load_default()

    # ── layout constants ───────────────────────────────────────────────
    padding = int(10 * font_scale)
    divider_x = int(width * 0.64)  # left column ends here
    title_h = title_size + padding * 2

    # ── 1. title bar ──────────────────────────────────────────────────
    _draw_title_bar(draw, width, title_h, current_dt, font_title, padding)


    # ── 3. calendar (left column) ─────────────────────────────────────
    cal_y = title_h + padding
    cal_y = _draw_calendar(
        draw, img, events, current_dt, timezone_str, time_format,
        labels, locale_code, font_header, font_event, font_event_bold,
        fg, bg, padding, 0, cal_y, divider_x - padding, height,
        font_scale,
    )

    # ── 4. weather (right column) ─────────────────────────────────────
    wx = divider_x + padding * 2
    wy = title_h + padding
    w_width = width - wx - padding
    _draw_weather(
        draw, img, weather, units, labels, time_format,
        font_weather_big, font_weather_med, font_weather_sm, font_weather_sm_bold,
        fg, bg, wx, wy, w_width, height - wy - padding, font_scale,
    )

    return img


# ── helpers ────────────────────────────────────────────────────────────

def _parse_color(color_str: str) -> tuple[int, int, int]:
    from PIL import ImageColor
    return ImageColor.getrgb(color_str)


def _draw_title_bar(
    draw: ImageDraw.ImageDraw,
    width: int,
    title_h: int,
    current_dt: datetime,
    font: ImageFont.FreeTypeFont,
    padding: int,
):
    """Draw the full-width date title at the top of the dashboard."""
    # Solid black background
    draw.rectangle([(0, 0), (width, title_h)], fill=BLACK)

    title_text = current_dt.strftime("%A, %B %-d, %Y").upper()
    bbox = draw.textbbox((0, 0), title_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (width - tw) // 2
    ty = (title_h - th) // 2
    draw.text((tx, ty), title_text, fill=WHITE, font=font)

    # Orange accent stripe at the base of the title bar
    draw.rectangle([(0, title_h - 4), (width, title_h)], fill=ORANGE)


def _draw_calendar(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    events: list[dict],
    current_dt: datetime,
    timezone_str: str,
    time_format: str,
    labels: dict,
    locale_code: str,
    font_header: ImageFont.FreeTypeFont,
    font_event: ImageFont.FreeTypeFont,
    font_event_bold: ImageFont.FreeTypeFont,
    fg: tuple,
    bg: tuple,
    padding: int,
    x0: int,
    y0: int,
    x1: int,
    y_max: int,
    font_scale: float,
) -> int:
    """Draw 3-day event list.  Returns the final y position."""
    y = y0
    day_labels = [
        labels.get("today", "Today"),
        (current_dt + timedelta(days=1)).strftime("%A"),
        (current_dt + timedelta(days=2)).strftime("%A"),
    ]
    day_dates = [
        current_dt.date(),
        current_dt.date() + timedelta(days=1),
        current_dt.date() + timedelta(days=2),
    ]
    day_colors = [BLACK, DARK_BLUE, DARK_BLUE]

    header_h = int(32 * font_scale)
    event_line_h = int(26 * font_scale)
    event_padding = int(5 * font_scale)

    for i, (label, date, header_bg) in enumerate(zip(day_labels, day_dates, day_colors)):
        if y + header_h > y_max:
            break

        # ── day header ─────────────────────────────────────────────────
        draw.rectangle([(x0, y), (x1, y + header_h)], fill=header_bg)
        # Left accent stripe (orange for today, yellow for future days)
        accent_col = ORANGE if i == 0 else YELLOW
        draw.rectangle([(x0, y), (x0 + 5, y + header_h)], fill=accent_col)
        label_text = label.upper()
        date_text  = date.strftime("%-d %b")          # compact: "1 Mar"
        label_bbox = draw.textbbox((0, 0), label_text, font=font_header)
        label_w    = label_bbox[2] - label_bbox[0]
        date_font  = get_font("Jost", int(font_header.size * 0.82)) or font_header
        sep        = "  ·  "
        sep_bbox   = draw.textbbox((0, 0), sep, font=date_font)
        text_y     = y + (header_h - (label_bbox[3] - label_bbox[1])) // 2
        tx         = x0 + 5 + padding
        draw.text((tx, text_y), label_text, fill=WHITE, font=font_header)
        draw.text(
            (tx + label_w + sep_bbox[2] - sep_bbox[0], text_y + int(1 * font_scale)),
            date_text, fill=LIGHT_GRAY, font=date_font,
        )
        draw.text(
            (tx + label_w, text_y + int(1 * font_scale)),
            sep, fill=MED_GRAY, font=date_font,
        )
        y += header_h

        # ── events for this day ────────────────────────────────────────
        day_events = _events_for_date(events, date, timezone_str)
        if not day_events:
            # "Nothing scheduled!"
            placeholder = labels.get("noEventsContent", "Nothing scheduled!")
            draw.text(
                (x0 + padding, y + event_padding),
                placeholder,
                fill=LIGHT_GRAY,
                font=font_event,
            )
            y += event_line_h + event_padding
        else:
            for ev in day_events:
                if y + event_line_h > y_max:
                    break
                y = _draw_event_row(
                    draw, ev, date, time_format, timezone_str,
                    font_event, font_event_bold,
                    fg, bg, x0, y, x1, event_line_h, event_padding, padding,
                )

        # small gap between day sections
        y += int(4 * font_scale)

    return y


def _events_for_date(events: list[dict], date, timezone_str: str) -> list[dict]:
    """Filter events that occur on *date*."""
    import pytz
    tz = pytz.timezone(timezone_str)
    result = []
    for ev in events:
        start_str = ev.get("start")
        if not start_str:
            continue
        try:
            dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = tz.localize(dt)
            else:
                dt = dt.astimezone(tz)
            if dt.date() == date:
                result.append(ev)
        except (ValueError, TypeError):
            continue
    # Sort: all-day first, then by start time
    result.sort(key=lambda e: (0 if e.get("allDay") else 1, e.get("start", "")))
    return result


def _draw_event_row(
    draw: ImageDraw.ImageDraw,
    ev: dict,
    date,
    time_format: str,
    timezone_str: str,
    font: ImageFont.FreeTypeFont,
    font_bold: ImageFont.FreeTypeFont,
    fg: tuple,
    bg: tuple,
    x0: int,
    y: int,
    x1: int,
    line_h: int,
    event_padding: int,
    padding: int,
) -> int:
    """Draw one event row. Returns new y."""
    import pytz

    is_placeholder = "senior-dashboard-nothing-more" in (ev.get("classNames") or [])

    # Left-edge colour accent bar
    bar_w     = 5
    bar_color = _parse_color(ev.get("backgroundColor", "#007BFF"))
    draw.rectangle(
        [(x0 + padding, y + event_padding),
         (x0 + padding + bar_w, y + event_padding + line_h - 2)],
        fill=bar_color,
    )

    text_x = x0 + padding + bar_w + padding

    # time label
    if ev.get("allDay") and not is_placeholder:
        time_str = "All day"
    elif is_placeholder:
        time_str = ""
    else:
        time_str = _format_event_time(ev, time_format, timezone_str)

    if time_str:
        draw.text((text_x, y + event_padding), time_str, fill=MED_GRAY, font=font)
        time_w = draw.textbbox((0, 0), time_str, font=font)[2] + padding
        title_x = text_x + time_w
    else:
        title_x = text_x

    # title (truncate if too long)
    title = ev.get("title", "")
    max_title_w = x1 - title_x - padding
    if max_title_w > 0:
        title = _truncate_text(draw, title, font_bold, max_title_w)
        draw.text((title_x, y + event_padding), title, fill=fg, font=font_bold)

    return y + line_h + event_padding


def _format_event_time(ev: dict, time_format: str, timezone_str: str) -> str:
    import pytz
    tz = pytz.timezone(timezone_str)
    start_str = ev.get("start", "")
    try:
        dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        else:
            dt = dt.astimezone(tz)
        if time_format == "12h":
            return dt.strftime("%-I:%M %p").lower()
        else:
            return dt.strftime("%H:%M")
    except Exception:
        return ""


def _truncate_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    while len(text) > 1:
        text = text[:-1]
        if draw.textbbox((0, 0), text + "…", font=font)[2] <= max_w:
            return text + "…"
    return "…"


# ── weather drawing ────────────────────────────────────────────────────

def _draw_weather(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    weather: dict | None,
    units: str,
    labels: dict,
    time_format: str,
    font_big: ImageFont.FreeTypeFont,
    font_med: ImageFont.FreeTypeFont,
    font_sm: ImageFont.FreeTypeFont,
    font_sm_bold: ImageFont.FreeTypeFont,
    fg: tuple,
    bg: tuple,
    x: int,
    y: int,
    w: int,
    h: int,
    font_scale: float,
):
    if not weather:
        draw.text((x, y), "No weather data", fill=LIGHT_GRAY, font=font_sm)
        return

    gap = int(12 * font_scale)
    current = weather.get("current")
    today = weather.get("today")
    forecast = weather.get("forecast", [])

    # ── current conditions ─────────────────────────────────────────────
    if current:
        temp = _convert_temp(current.get("temperature"), units)
        code = current.get("weathercode", 0)
        desc = WEATHER_SYMBOLS.get(code, "?")

        cur_icon_sz = int(56 * font_scale)
        cur_icon = _load_weather_icon(current.get("icon_path"), cur_icon_sz)
        if cur_icon:
            _paste_icon(img, cur_icon, x, y)
            tx = x + cur_icon_sz + int(8 * font_scale)
        else:
            tx = x
        draw.text((tx, y + (cur_icon_sz - font_big.size) // 2), temp, fill=fg, font=font_big)
        temp_w = draw.textbbox((0, 0), temp, font=font_big)
        desc_y = y + (cur_icon_sz - font_sm.size) // 2 + font_big.size - int(4 * font_scale)
        draw.text((tx, desc_y), desc, fill=MED_GRAY, font=font_sm)
        y += max(cur_icon_sz, font_big.size) + gap

    # ── hourly snapshot ────────────────────────────────────────────────
    if today:
        hourly = today.get("hourly", {})
        if hourly:
            slot_labels_12 = {"8am": "8am", "noon": "Noon", "3pm": "3pm", "8pm": "8pm"}
            slot_labels_24 = {"8am": "08:00", "noon": "12:00", "3pm": "15:00", "8pm": "20:00"}
            slot_labels = slot_labels_12 if time_format == "12h" else slot_labels_24
            slot_x = x
            slot_w = w // max(len(hourly), 1)
            icon_sz  = int(slot_w * 0.6)              # icon fills ~65% of slot width
            inner    = int(4 * font_scale)
            label_h  = font_sm.size + inner
            temp_h   = font_sm_bold.size + inner
            box_h    = label_h + icon_sz + temp_h + inner
            for key in ["8am", "noon", "3pm", "8pm"]:
                if key not in hourly:
                    continue
                slot_data = hourly[key]
                if isinstance(slot_data, dict):
                    temp_val   = _convert_temp_short(slot_data.get("temp"), units)
                    icon_path  = slot_data.get("icon_path")
                else:
                    temp_val   = _convert_temp_short(slot_data, units)
                    icon_path  = None
                lbl   = slot_labels.get(key, key)
                box_w = slot_w - int(4 * font_scale)
                # Row 1: time label (centred)
                lbl_w = draw.textbbox((0, 0), lbl, font=font_sm)[2]
                draw.text(
                    (slot_x + (box_w - lbl_w) // 2, y + inner // 2),
                    lbl, fill=DARK_GRAY, font=font_sm,
                )
                # Row 2: weather icon (centred), fallback to short symbol text
                icon_y = y + label_h
                icon = _load_weather_icon(icon_path, icon_sz)
                if icon:
                    icon_x = slot_x + (box_w - icon_sz) // 2
                    _paste_icon(img, icon, icon_x, icon_y)
                else:
                    sym = WEATHER_SYMBOLS_SHORT.get(
                        slot_data.get("code", 0) if isinstance(slot_data, dict) else 0, ""
                    )
                    sym_display = _truncate_text(draw, sym, font_sm, box_w - inner * 2)
                    draw.text((slot_x + inner, icon_y + (icon_sz - font_sm.size) // 2),
                              sym_display, fill=MED_GRAY, font=font_sm)
                # Row 3: temperature (centred bold)
                temp_w2 = draw.textbbox((0, 0), temp_val, font=font_sm_bold)[2]
                draw.text(
                    (slot_x + (box_w - temp_w2) // 2, y + label_h + icon_sz),
                    temp_val, fill=BLACK, font=font_sm_bold,
                )
                slot_x += slot_w
            y += box_h + int(6 * font_scale)

        # divider
        draw.line([(x, y), (x + w, y)], fill=LIGHT_GRAY, width=1)
        y += gap

    # ── forecast ───────────────────────────────────────────────────────
    forecast_icon_size = int(56 * font_scale)
    for day in forecast:
        date_label = day.get("date", "")
        code = day.get("weathercode", 0)
        desc = WEATHER_SYMBOLS.get(code, "?")
        t_min = day.get("temp_min")
        t_max = day.get("temp_max")
        lo = _convert_temp_short(t_min, units)
        hi = _convert_temp_short(t_max, units)
        suffix = _unit_suffix(units)

        # Row 1: day label
        draw.text((x, y), date_label, fill=fg, font=font_sm_bold)
        y += font_sm_bold.size + int(10 * font_scale)

        # Row 2: icon + condition description (vertically centred on icon)
        fc_icon = _load_weather_icon(day.get("icon_path"), forecast_icon_size)
        if fc_icon:
            _paste_icon(img, fc_icon, x, y)
            desc_x = x + forecast_icon_size + int(6 * font_scale)
        else:
            desc_x = x
        desc_y = y + (forecast_icon_size - font_sm.size) // 2
        draw.text((desc_x, desc_y), desc, fill=fg, font=font_sm)
        y += forecast_icon_size + int(4 * font_scale)

        # Row 3: temp range
        draw.text((x, y), f"{lo}–{hi}{suffix}", fill=fg, font=font_sm)
        y += font_sm.size + gap

        # divider
        draw.line([(x, y), (x + w, y)], fill=LIGHT_GRAY, width=1)
        y += gap
