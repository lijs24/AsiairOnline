"""Server-side real-time sky dome (实时天球) renderer.

All-sky azimuthal-equidistant projection of the visible hemisphere (north up,
east LEFT — the planetarium convention for a chart you hold overhead), with the
equatorial grid rotated to the local sidereal time, bright stars, the sun, the
current scope pointing and the goto target. Pure numpy/PIL — a frame costs tens
of milliseconds on the CPU, cached by rounded pointing + sidereal time.
"""
from __future__ import annotations

import io
import logging
import math
import threading
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

BG = (7, 9, 9)
HORIZON = (88, 102, 100)
GRID = (34, 47, 49)
EQUATOR = (62, 86, 88)
MERIDIAN = (50, 64, 70)
STAR = (222, 230, 228)
POINTING = (226, 74, 64)
TARGET = (57, 217, 138)
SUN = (232, 179, 57)
TEXT = (98, 112, 110)
POLE = (120, 134, 132)

from .sky_stars import NAMED, STARS  # noqa: F401

import numpy as np

_STAR_RA = np.array([s[0] for s in STARS], dtype=np.float64)
_STAR_DEC = np.array([s[1] for s in STARS], dtype=np.float64)
_STAR_MAG = np.array([s[2] for s in STARS], dtype=np.float64)

_CACHE: dict = {}
_LOCK = threading.Lock()
_FONT_WARNED = False


def _alt_az(ha_deg: float, dec_deg: float, lat_deg: float) -> tuple[float, float]:
    H = math.radians(ha_deg)
    d = math.radians(dec_deg)
    p = math.radians(lat_deg)
    sa = math.sin(d) * math.sin(p) + math.cos(d) * math.cos(p) * math.cos(H)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sa))))
    y = -math.sin(H) * math.cos(d)
    x = math.sin(d) * math.cos(p) - math.cos(d) * math.sin(p) * math.cos(H)
    az = (math.degrees(math.atan2(y, x))) % 360.0
    return alt, az


def _alt_az_vec(
    ha_deg_arr: np.ndarray,
    dec_deg_arr: np.ndarray,
    lat_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    H = np.radians(ha_deg_arr)
    d = np.radians(dec_deg_arr)
    p = np.radians(lat_deg)
    sa = np.sin(d) * np.sin(p) + np.cos(d) * np.cos(p) * np.cos(H)
    alt = np.degrees(np.arcsin(np.clip(sa, -1.0, 1.0)))
    y = -np.sin(H) * np.cos(d)
    x = np.sin(d) * np.cos(p) - np.cos(d) * np.sin(p) * np.cos(H)
    az = np.degrees(np.arctan2(y, x)) % 360.0
    return alt, az


def _sun_ra_dec() -> tuple[float, float]:
    """Low-precision solar position (good to ~0.01 deg, plenty for a chart)."""
    now = datetime.now(timezone.utc)
    n = (now - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0
    L = (280.460 + 0.9856474 * n) % 360.0
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 4e-7 * n)
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360.0
    dec = math.degrees(math.asin(math.sin(eps) * math.sin(lam)))
    return ra / 15.0, dec


import functools


@functools.lru_cache(maxsize=16)
def _font(size: int):
    global _FONT_WARNED
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                 "/System/Library/Fonts/PingFang.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                 "/usr/share/fonts/google-noto-cjk/NotoSerifCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    if not _FONT_WARNED:
        logging.getLogger(__name__).warning(
            "Chinese font not found; rendered text will fall back to PIL default font and may degrade."
        )
        _FONT_WARNED = True
    return ImageFont.load_default()


def render_sky_png(
    ra_hours: float | None,
    dec_degrees: float | None,
    lst_hours: float | None,
    lat: float = 40.0,
    target_ra: float | None = None,
    target_dec: float | None = None,
    size: int = 520,
) -> bytes:
    img = Image.new("RGB", (size, size), BG)
    dr = ImageDraw.Draw(img)
    cx = cy = size / 2.0
    R = size / 2.0 - 18.0
    s = size / 520.0
    lst = lst_hours if lst_hours is not None else 0.0

    def proj(alt: float, az: float) -> tuple[float, float]:
        r = (90.0 - alt) / 90.0 * R
        a = math.radians(az)
        return cx - r * math.sin(a), cy - r * math.cos(a)  # north up, east left

    def eq_point(ra_h: float, dec_d: float):
        alt, az = _alt_az((lst - ra_h) * 15.0, dec_d, lat)
        return alt, az

    def polyline_eq(points, color, width=1):
        run: list = []
        for ra_h, dec_d in points:
            alt, az = eq_point(ra_h, dec_d)
            if alt > -0.3:
                run.append(proj(min(alt, 90.0), az))
            else:
                if len(run) > 1:
                    dr.line(run, fill=color, width=width)
                run = []
        if len(run) > 1:
            dr.line(run, fill=color, width=width)

    # equatorial grid: dec circles + RA hour circles
    for dec_c in (-30, 0, 30, 60):
        pts = [(h / 4.0, float(dec_c)) for h in range(0, 24 * 4 + 1)]
        polyline_eq(pts, EQUATOR if dec_c == 0 else GRID, 2 if dec_c == 0 else 1)
    for ra_c in range(0, 24, 2):
        pts = [(float(ra_c), d / 2.0) for d in range(-60, 178)]
        polyline_eq(pts, GRID, 1)

    # local meridian (faint, alt-az native)
    for az0 in (0.0, 180.0):
        pts = [proj(a / 2.0, az0) for a in range(0, 181)]
        dr.line(pts, fill=MERIDIAN, width=1)

    # horizon ring + cardinal labels
    dr.ellipse([cx - R, cy - R, cx + R, cy + R], outline=HORIZON, width=2)
    f = _font(max(11, int(13 * s)))
    f2 = _font(max(10, int(11 * s)))
    for az0, name in ((0, "北"), (90, "东"), (180, "南"), (270, "西")):
        x, y = proj(-4.5, az0)
        dr.text((x, y), name, fill=HORIZON, font=f, anchor="mm")

    # north celestial pole
    alt, az = eq_point(2.5303, 89.9)
    px, py = proj(alt, az)
    dr.line([px - 5 * s, py, px + 5 * s, py], fill=POLE, width=1)
    dr.line([px, py - 5 * s, px, py + 5 * s], fill=POLE, width=1)

    # bright stars
    star_alt, star_az = _alt_az_vec((lst - _STAR_RA) * 15.0, _STAR_DEC, lat)
    visible = star_alt > 0
    visible_alt = star_alt[visible]
    visible_az = star_az[visible]
    visible_mag = _STAR_MAG[visible]
    star_r = (90.0 - np.minimum(visible_alt, 90.0)) / 90.0 * R
    star_a = np.radians(visible_az)
    star_x = cx - star_r * np.sin(star_a)
    star_y = cy - star_r * np.cos(star_a)
    star_rr = np.maximum(0.8, 3.4 - 0.72 * visible_mag) * s
    for x, y, r in zip(star_x, star_y, star_rr):
        dr.ellipse([x - r, y - r, x + r, y + r], fill=STAR)
    for ra_h, dec_d, name in NAMED:
        alt, az = eq_point(ra_h, dec_d)
        if alt <= 2:
            continue
        x, y = proj(alt, az)
        dr.text((x + 6 * s, y - 2 * s), name, fill=TEXT, font=f2, anchor="lm")

    # the sun
    sra, sdec = _sun_ra_dec()
    alt, az = eq_point(sra, sdec)
    if alt > -1:
        x, y = proj(max(alt, 0.0), az)
        r = 6.5 * s
        dr.ellipse([x - r, y - r, x + r, y + r], outline=SUN, width=2)
        dr.ellipse([x - 1.6 * s, y - 1.6 * s, x + 1.6 * s, y + 1.6 * s], fill=SUN)
        dr.text((x + 9 * s, y), "日", fill=SUN, font=f2, anchor="lm")

    # goto target marker
    if target_ra is not None and target_dec is not None:
        alt, az = eq_point(float(target_ra), float(target_dec))
        if alt > 0:
            x, y = proj(alt, az)
            r = 7 * s
            dr.ellipse([x - r, y - r, x + r, y + r], outline=TARGET, width=2)

    # current pointing reticle
    note = None
    if ra_hours is not None and dec_degrees is not None:
        alt, az = eq_point(float(ra_hours), float(dec_degrees))
        if alt > 0:
            x, y = proj(alt, az)
            r = 9 * s
            dr.ellipse([x - r, y - r, x + r, y + r], outline=POINTING, width=2)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                dr.line([x + dx * (r - 3 * s), y + dy * (r - 3 * s), x + dx * (r + 5 * s), y + dy * (r + 5 * s)],
                        fill=POINTING, width=2)
            note = f"高度 {alt:.0f}°  方位 {az:.0f}°"
        else:
            note = f"指向在地平线下 ({alt:.0f}°)"

    # footer text
    if lst_hours is not None:
        dr.text((10 * s, size - 14 * s), f"LST {lst_hours:.3f}h", fill=TEXT, font=f2, anchor="lm")
    if note:
        dr.text((size - 10 * s, size - 14 * s), note, fill=POINTING if "地平线下" in note else TEXT,
                font=f2, anchor="rm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_sky_cached(params: dict, max_entries: int = 32) -> bytes:
    def f(name, default=None):
        v = params.get(name)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    ra = f("ra")
    dec = f("dec")
    lst = f("lst")
    lat = f("lat", 40.0)
    tra = f("tra")
    tdec = f("tdec")
    size = int(f("size", 520.0))
    key = (
        None if ra is None else round(ra, 2),
        None if dec is None else round(dec, 1),
        None if lst is None else round(lst, 2),   # ~36 s of sidereal rotation
        round(lat, 1),
        None if tra is None else round(tra, 2),
        None if tdec is None else round(tdec, 1),
        size,
        datetime.now(timezone.utc).strftime("%Y%m%d%H"),  # sun moves; refresh hourly
    )
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            _CACHE[key] = _CACHE.pop(key)
            return hit
    png = render_sky_png(ra, dec, lst, lat, tra, tdec, size)
    with _LOCK:
        _CACHE[key] = png
        while len(_CACHE) > max_entries:
            _CACHE.pop(next(iter(_CACHE)))
    return png
