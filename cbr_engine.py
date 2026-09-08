"""
cbr_engine.py
Pure calculation engine for the CBR (California Bearing Ratio) Test Analyzer,
following BS 1377-4:1990, Clause 7.

Kept independent of Streamlit so the math can be unit-tested on its own and
reused by other tools in the Automation Hub pool.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np

# Standard loads (BS 1377-4) at the two reference penetrations, on a
# 1935 mm^2 (49.63 mm diameter) plunger.
STD_LOAD_2_5_MM = 13.2  # kN
STD_LOAD_5_0_MM = 20.0  # kN
PLUNGER_AREA_MM2 = 1935


# --------------------------------------------------------------------------
# Compaction relationship (moisture-density curve)
# --------------------------------------------------------------------------

def mould_volume_cm3(diameter_mm: float, height_mm: float) -> Optional[float]:
    """Volume of a cylindrical CBR mould, in cm^3, from dimensions in mm."""
    if not diameter_mm or not height_mm:
        return None
    d_cm, h_cm = diameter_mm / 10.0, height_mm / 10.0
    return float(np.pi / 4 * d_cm ** 2 * h_cm)


@dataclass
class CompactionFit:
    a: float
    b: float
    c: float
    omc: float   # optimum moisture content, %
    mdd: float   # maximum dry density, g/cm3
    n_points: int


def fit_compaction(moistures: List[float], dry_densities: List[float]) -> Optional[CompactionFit]:
    """Least-squares parabola fit of dry density vs moisture content.

    Returns None if there are fewer than 3 usable points, or if the fitted
    parabola opens upward (no peak, i.e. not a valid compaction curve).
    """
    w = np.asarray(moistures, dtype=float)
    dd = np.asarray(dry_densities, dtype=float)
    mask = np.isfinite(w) & np.isfinite(dd)
    w, dd = w[mask], dd[mask]
    if len(w) < 3:
        return None
    a, b, c = np.polyfit(w, dd, 2)
    if a >= 0:
        return None
    omc = -b / (2 * a)
    mdd = a * omc ** 2 + b * omc + c
    if not np.isfinite(omc) or not np.isfinite(mdd) or omc <= 0:
        return None
    return CompactionFit(a=float(a), b=float(b), c=float(c), omc=float(omc), mdd=float(mdd), n_points=len(w))


# --------------------------------------------------------------------------
# Load-penetration curve correction and CBR
# --------------------------------------------------------------------------

def _ensure_origin(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    pts = sorted(points, key=lambda p: p[0])
    if not pts or pts[0][0] != 0:
        pts = [(0.0, 0.0)] + pts
    return pts


def auto_correction(points: List[Tuple[float, float]]) -> float:
    """Detects a concave-upward initial portion of the load-penetration curve
    and returns the correction (mm) by which the origin should be shifted:
    the tangent at the point of maximum slope (within the first 5 mm of
    penetration) is extended back to the penetration axis.
    Returns 0.0 if the curve is already well-behaved (no correction needed).
    """
    pts = _ensure_origin(points)
    max_slope, max_idx = -np.inf, 0
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        if p0[0] > 5:
            break
        dp = p1[0] - p0[0]
        if dp <= 0:
            continue
        slope = (p1[1] - p0[1]) / dp
        if slope > max_slope:
            max_slope, max_idx = slope, i
    if max_idx == 0 or max_slope <= 0:
        return 0.0
    p1 = pts[max_idx]
    x0 = p1[0] - p1[1] / max_slope
    return max(0.0, x0)


def interp_load(points: List[Tuple[float, float]], x: float) -> Optional[float]:
    """Linear interpolation (with straight-line extrapolation beyond the last
    segment) of load at a given penetration on the *original* (uncorrected)
    penetration axis."""
    pts = _ensure_origin(points)
    if len(pts) < 2:
        return None
    if x <= pts[0][0]:
        return pts[0][1]
    for i in range(len(pts) - 1):
        p0, p1 = pts[i], pts[i + 1]
        if p0[0] <= x <= p1[0]:
            t = (x - p0[0]) / (p1[0] - p0[0])
            return p0[1] + t * (p1[1] - p0[1])
    a, b = pts[-2], pts[-1]
    m = (b[1] - a[1]) / (b[0] - a[0])
    return b[1] + m * (x - b[0])


@dataclass
class CBRResult:
    correction_mm: float
    load_2_5: Optional[float]
    load_5_0: Optional[float]
    cbr_2_5: Optional[float]
    cbr_5_0: Optional[float]
    needs_retest: bool
    selected_cbr: Optional[float]
    governing: str  # "2.5 mm" | "5.0 mm (confirmed)" | "pending"


def compute_cbr(points: List[Tuple[float, float]],
                 manual_correction: Optional[float] = None,
                 retest_confirmed: bool = False) -> CBRResult:
    if len(points) < 2:
        return CBRResult(0.0, None, None, None, None, False, None, "pending")

    correction = manual_correction if manual_correction is not None else auto_correction(points)
    load25 = interp_load(points, 2.5 + correction)
    load50 = interp_load(points, 5.0 + correction)
    cbr25 = load25 / STD_LOAD_2_5_MM * 100 if load25 is not None else None
    cbr50 = load50 / STD_LOAD_5_0_MM * 100 if load50 is not None else None

    needs_retest = cbr25 is not None and cbr50 is not None and cbr50 > cbr25
    if cbr25 is None:
        selected, governing = None, "pending"
    elif needs_retest and retest_confirmed:
        selected, governing = cbr50, "5.0 mm (confirmed)"
    else:
        selected, governing = cbr25, "2.5 mm"

    return CBRResult(correction, load25, load50, cbr25, cbr50, needs_retest, selected, governing)


# --------------------------------------------------------------------------
# Swell
# --------------------------------------------------------------------------

def swell_percent(initial_reading_mm: float, final_reading_mm: float, specimen_height_mm: float) -> Optional[float]:
    if not specimen_height_mm:
        return None
    return (final_reading_mm - initial_reading_mm) / specimen_height_mm * 100
