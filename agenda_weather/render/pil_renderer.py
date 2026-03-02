"""
Pure PIL/Pillow renderer for the Agenda + Weather dashboard plugin.

Produces a crisp, e-paper-optimised image without any browser dependency.
Designed for 7-colour Inky Impression displays (800×480) but works with
any resolution.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from utils.app_utils import get_font

logger = logging.getLogger(__name__)

# ── colour palette (7-colour Inky Impression safe) ────────────────────
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (224, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 200, 0)
ORANGE = (255, 128, 0)
LIGHT_GRAY = (200, 200, 200)

# ── simple ASCII weather symbols (no emoji needed) ────────────────────
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
    _draw_title_bar(draw, img, width, title_h, current_dt, font_title, fg, bg, padding)

    # ── 2. vertical divider ────────────────────────────────────────────
    draw.line([(divider_x, title_h), (divider_x, height)], fill=LIGHT_GRAY, width=1)

    # ── 3. calendar (left column) ─────────────────────────────────────
    cal_y = title_h + padding
    cal_y = _draw_calendar(
        draw, img, events, current_dt, timezone_str, time_format,
        labels, locale_code, font_header, font_event, font_event_bold,
        fg, bg, padding, 0, cal_y, divider_x - padding, height,
        font_scale,
    )

    # ── 4. weather (right column) ─────────────────────────────────────
    wx = divider_x + padding
    wy = title_h + padding
    w_width = width - wx - padding
    _draw_weather(
        draw, weather, units, labels, time_format,
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
    img: Image.Image,
    width: int,
    title_h: int,
    current_dt: datetime,
    font: ImageFont.FreeTypeFont,
    fg: tuple,
    bg: tuple,
    padding: int,
):
    """Draw the full-width date title at the top of the dashboard."""
    # Format using Python's strftime (locale-independent but good enough)
    title_text = current_dt.strftime("%A, %B %-d, %Y")

    # Draw centred
    bbox = draw.textbbox((0, 0), title_text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (width - tw) // 2
    ty = padding
    draw.text((tx, ty), title_text, fill=fg, font=font)

    # Underline
    draw.line([(0, title_h), (width, title_h)], fill=LIGHT_GRAY, width=1)


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
        labels.get("tomorrow", "Tomorrow"),
        labels.get("dayAfterTomorrow", "Day after tomorrow"),
    ]
    day_dates = [
        current_dt.date(),
        current_dt.date() + timedelta(days=1),
        current_dt.date() + timedelta(days=2),
    ]
    day_colors = [GREEN, BLUE, BLUE]

    header_h = int(28 * font_scale)
    event_line_h = int(24 * font_scale)
    event_padding = int(4 * font_scale)

    for i, (label, date, header_bg) in enumerate(zip(day_labels, day_dates, day_colors)):
        if y + header_h > y_max:
            break

        # ── day header ─────────────────────────────────────────────────
        header_text = f"{label}: {date.strftime('%A, %B %-d, %Y')}"
        draw.rectangle([(x0, y), (x1, y + header_h)], fill=header_bg)
        draw.text(
            (x0 + padding, y + (header_h - font_header.size) // 2),
            header_text,
            fill=WHITE,
            font=font_header,
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

    # colour dot
    dot_r = 5
    dot_x = x0 + padding + dot_r
    dot_y = y + event_padding + line_h // 2
    dot_color = _parse_color(ev.get("backgroundColor", "#007BFF"))
    draw.ellipse(
        [(dot_x - dot_r, dot_y - dot_r), (dot_x + dot_r, dot_y + dot_r)],
        fill=dot_color,
    )

    text_x = dot_x + dot_r + padding

    # time label
    if ev.get("allDay") and not is_placeholder:
        time_str = "All day"
    elif is_placeholder:
        time_str = ""
    else:
        time_str = _format_event_time(ev, time_format, timezone_str)

    if time_str:
        draw.text((text_x, y + event_padding), time_str, fill=LIGHT_GRAY, font=font)
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

        draw.text((x, y), temp, fill=fg, font=font_big)
        temp_w = draw.textbbox((0, 0), temp, font=font_big)
        y_desc = y + (font_big.size - font_sm.size)
        draw.text((x + temp_w[2] + int(10 * font_scale), y_desc), desc, fill=fg, font=font_sm)
        y += font_big.size + gap

    # ── today min/max ──────────────────────────────────────────────────
    if today:
        t_min = today.get("temp_min")
        t_max = today.get("temp_max")
        if t_min is not None and t_max is not None:
            lo = _convert_temp_short(t_min, units)
            hi = _convert_temp_short(t_max, units)
            suffix = _unit_suffix(units)

            # Colour code min/max
            draw.text((x, y), lo, fill=BLUE, font=font_med)

            sep_text = f"{lo} – "
            sep_bbox = draw.textbbox((x, y), sep_text, font=font_med)
            draw.text((sep_bbox[2], y), f"{hi}{suffix}", fill=RED, font=font_med)

            y += font_med.size + int(6 * font_scale)

        # hourly snapshot
        hourly = today.get("hourly", {})
        if hourly:
            slot_labels_12 = {"8am": "8am", "noon": "Noon", "3pm": "3pm", "8pm": "8pm"}
            slot_labels_24 = {"8am": "08:00", "noon": "12:00", "3pm": "15:00", "8pm": "20:00"}
            slot_labels = slot_labels_12 if time_format == "12h" else slot_labels_24
            slot_x = x
            slot_w = w // max(len(hourly), 1)
            for key in ["8am", "noon", "3pm", "8pm"]:
                if key not in hourly:
                    continue
                temp_val = _convert_temp_short(hourly[key], units)
                lbl = slot_labels.get(key, key)
                draw.text((slot_x, y), lbl, fill=LIGHT_GRAY, font=font_sm)
                draw.text((slot_x, y + font_sm.size + 2), temp_val, fill=fg, font=font_sm_bold)
                slot_x += slot_w
            y += font_sm.size * 2 + int(8 * font_scale)

        # divider
        draw.line([(x, y), (x + w, y)], fill=LIGHT_GRAY, width=1)
        y += gap

    # ── forecast ───────────────────────────────────────────────────────
    for day in forecast:
        date_label = day.get("date", "")
        code = day.get("weathercode", 0)
        desc = WEATHER_SYMBOLS.get(code, "?")
        t_min = day.get("temp_min")
        t_max = day.get("temp_max")
        lo = _convert_temp_short(t_min, units)
        hi = _convert_temp_short(t_max, units)
        suffix = _unit_suffix(units)

        draw.text((x, y), date_label, fill=fg, font=font_sm_bold)
        y += font_sm_bold.size + 2

        desc_text = f"{desc}   {lo}–{hi}{suffix}"
        draw.text((x, y), desc_text, fill=fg, font=font_sm)
        y += font_sm.size + gap

        # divider
        draw.line([(x, y), (x + w, y)], fill=LIGHT_GRAY, width=1)
        y += gap
