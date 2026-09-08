"""
cbr_engine.py
Pure calculation engine for the CBR (California Bearing Ratio) Test Analyzer.

Rebuilt around a real project lab-report template (4 worksheets):
  1. General compaction (standard Proctor) test  -> OMC / MDD
  2. CBR compaction at several compactive efforts -> per-specimen density & %compaction
  3. Soaked (or unsoaked) penetration testing     -> per-specimen CBR @ 2.5 / 5.0 mm
  4. Design CBR summary                            -> CBR vs %MDD curve, read off at
                                                       target compaction levels

Kept independent of Streamlit so the math can be unit-tested on its own and
reused by other tools in the Automation Hub pool. All densities are handled
in kg/m3 (matching the template's "Mould Factor" convention below); moisture
contents and CBR values are in %.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

# Default standard loads (BS 1377-4) at the two reference penetrations, on a
# 1935 mm^2 (49.63 mm diameter) plunger. Real project paperwork sometimes
# carries slightly different calibrated values (e.g. 13.344 / 20.016 kN) —
# these are exposed as editable inputs in the app, not hard-wired.
STD_LOAD_2_5_MM = 13.2  # kN
STD_LOAD_5_0_MM = 20.0  # kN
PLUNGER_AREA_MM2 = 1935

DEFAULT_TARGET_PCTS = (93.0, 95.0, 98.0, 100.0)


def _f(x) -> Optional[float]:
    """Coerce a scalar cell value to a plain float, or None.

    Dataframe cells arriving from Streamlit's data_editor can be Python
    ``None``, ``float('nan')``, or pandas' nullable-dtype ``pd.NA`` (from
    "Float64"/"Int64" columns with blank cells) — the last of which raises
    ``TypeError`` on ``bool()`` and breaks plain truthiness checks. Routing
    every scalar through this first makes all three behave identically.
    """
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if xf != xf:  # NaN
        return None
    return xf


# ==========================================================================
# 1. Shared mass / density / moisture helpers
#    (used by both the general Compaction sheet and the CBR-compaction sheet)
# ==========================================================================

def mould_volume_cm3(diameter_mm: float, height_mm: float) -> Optional[float]:
    """Volume of a cylindrical mould, in cm^3, from dimensions in mm."""
    diameter_mm, height_mm = _f(diameter_mm), _f(height_mm)
    if not diameter_mm or not height_mm:
        return None
    d_cm, h_cm = diameter_mm / 10.0, height_mm / 10.0
    return float(np.pi / 4 * d_cm ** 2 * h_cm)


def mould_factor_from_volume(volume_cm3: Optional[float]) -> Optional[float]:
    """Mould factor (kg/m3 per gram of wet soil) = 1000 / volume_cm3.

    This is the calibration constant the template enters directly per mould
    (each physical mould is calibrated once); this helper lets it be derived
    from dimensions instead, if the mould hasn't been individually calibrated.
    """
    volume_cm3 = _f(volume_cm3)
    if not volume_cm3:
        return None
    return 1000.0 / volume_cm3


def wet_density_kgm3(wet_soil_mass_g: Optional[float], mould_factor: Optional[float]) -> Optional[float]:
    """Wet (bulk) density in kg/m3 = mass of wet soil in the mould (g) x mould factor."""
    wet_soil_mass_g, mould_factor = _f(wet_soil_mass_g), _f(mould_factor)
    if wet_soil_mass_g is None or mould_factor is None:
        return None
    return wet_soil_mass_g * mould_factor


def moisture_content_pct(pan_g: Optional[float], pan_wet_g: Optional[float],
                          pan_dry_g: Optional[float]) -> Optional[float]:
    """Oven-dry moisture content (%) from pan / pan+wet-soil / pan+dry-soil masses."""
    pan_g, pan_wet_g, pan_dry_g = _f(pan_g), _f(pan_wet_g), _f(pan_dry_g)
    if pan_g is None or pan_wet_g is None or pan_dry_g is None:
        return None
    water = pan_wet_g - pan_dry_g
    dry_soil = pan_dry_g - pan_g
    if not dry_soil:
        return None
    return water / dry_soil * 100.0


def dry_density_from_wet(wet_density: Optional[float], moisture_pct: Optional[float]) -> Optional[float]:
    """Dry density (same units as wet_density) = 100 x wet_density / (100 + MC%)."""
    wet_density, moisture_pct = _f(wet_density), _f(moisture_pct)
    if wet_density is None or moisture_pct is None:
        return None
    return 100.0 * wet_density / (100.0 + moisture_pct)


def relative_compaction_pct(dry_density: Optional[float], mdd: Optional[float]) -> Optional[float]:
    """Relative compaction (%) = specimen dry density / MDD x 100."""
    dry_density, mdd = _f(dry_density), _f(mdd)
    if dry_density is None or mdd is None or not mdd:
        return None
    return dry_density / mdd * 100.0


# ==========================================================================
# 2. Compaction relationship (moisture-density curve) -> OMC / MDD
# ==========================================================================

@dataclass
class CompactionFit:
    a: float
    b: float
    c: float
    omc: float   # optimum moisture content, %
    mdd: float   # maximum dry density, kg/m3
    n_points: int


def fit_compaction(moistures: Sequence[float], dry_densities: Sequence[float]) -> Optional[CompactionFit]:
    """Least-squares parabola fit of dry density vs moisture content.

    Returns None if there are fewer than 3 usable points, or if the fitted
    parabola opens upward (no peak, i.e. not a valid compaction curve).
    """
    pairs = [(_f(m), _f(d)) for m, d in zip(moistures, dry_densities)]
    pairs = [(m, d) for m, d in pairs if m is not None and d is not None]
    if len(pairs) < 3:
        return None
    w = np.asarray([m for m, _ in pairs], dtype=float)
    dd = np.asarray([d for _, d in pairs], dtype=float)
    a, b, c = np.polyfit(w, dd, 2)
    if a >= 0:
        return None
    omc = -b / (2 * a)
    mdd = a * omc ** 2 + b * omc + c
    if not np.isfinite(omc) or not np.isfinite(mdd) or omc <= 0:
        return None
    return CompactionFit(a=float(a), b=float(b), c=float(c), omc=float(omc), mdd=float(mdd), n_points=len(w))


# ==========================================================================
# 3. Load-penetration curve: optional BS1377 origin correction, and CBR
# ==========================================================================

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
    This is an advisory BS1377 curve-shape correction — the source template
    does not apply it (its "corrected" column refers to load-ring calibration,
    not curve-origin shift), so it defaults to an opt-in toggle in the app.
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
    governing_mm: str            # "2.5 mm" | "5.0 mm" | "pending"
    selected_cbr: Optional[float]
    anomaly: bool                 # advisory flag: CBR@5.0mm > CBR@2.5mm


def compute_cbr(points: List[Tuple[float, float]],
                 std_load_2_5: float = STD_LOAD_2_5_MM,
                 std_load_5_0: float = STD_LOAD_5_0_MM,
                 manual_correction: Optional[float] = None,
                 apply_correction: bool = False) -> CBRResult:
    """Governing CBR = MAX(CBR@2.5mm, CBR@5.0mm) — matching the project
    template's convention. The BS1377 curve-origin correction is optional
    (apply_correction=True) since the source paperwork does not use it;
    when applied, an explicit manual_correction overrides the auto-detected
    tangent correction.
    """
    if len(points) < 2:
        return CBRResult(0.0, None, None, None, None, "pending", None, False)

    if apply_correction:
        correction = manual_correction if manual_correction is not None else auto_correction(points)
    else:
        correction = manual_correction if manual_correction is not None else 0.0

    load25 = interp_load(points, 2.5 + correction)
    load50 = interp_load(points, 5.0 + correction)
    cbr25 = load25 / std_load_2_5 * 100 if load25 is not None else None
    cbr50 = load50 / std_load_5_0 * 100 if load50 is not None else None

    if cbr25 is None and cbr50 is None:
        return CBRResult(correction, load25, load50, cbr25, cbr50, "pending", None, False)

    anomaly = cbr25 is not None and cbr50 is not None and cbr50 > cbr25
    candidates = [(v, lbl) for v, lbl in ((cbr25, "2.5 mm"), (cbr50, "5.0 mm")) if v is not None]
    selected, governing = max(candidates, key=lambda t: t[0])

    return CBRResult(correction, load25, load50, cbr25, cbr50, governing, selected, anomaly)


# ==========================================================================
# 4. Design CBR: fit CBR vs %compaction across specimens, read off targets
# ==========================================================================

@dataclass
class DesignCBRFit:
    coeffs: Tuple[float, ...]   # np.polyfit coefficients, highest degree first
    degree: int
    n_points: int
    x_min: float
    x_max: float


def fit_cbr_vs_compaction(rel_compactions: Sequence[float], cbrs: Sequence[float]) -> Optional[DesignCBRFit]:
    """Fits a smooth curve of CBR (%) vs relative compaction (%) through the
    per-specimen results (one point per compactive effort). Uses a quadratic
    fit for 3+ points (an exact parabola through exactly 3), linear for 2,
    generalizing the template's "plot a smooth curve through the 3 points and
    read values off it" step into an actual computed interpolation.
    """
    pairs = [(_f(a), _f(b)) for a, b in zip(rel_compactions, cbrs)]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 2:
        return None
    x = np.asarray([a for a, _ in pairs], dtype=float)
    y = np.asarray([b for _, b in pairs], dtype=float)
    order = np.argsort(x)
    x, y = x[order], y[order]
    degree = min(2, len(x) - 1)
    coeffs = np.polyfit(x, y, degree)
    return DesignCBRFit(coeffs=tuple(float(c) for c in coeffs), degree=degree,
                         n_points=len(x), x_min=float(x[0]), x_max=float(x[-1]))


def eval_design_cbr(fit: Optional[DesignCBRFit], target_pct: float) -> Tuple[Optional[float], bool]:
    """Returns (design_cbr, extrapolated) for one target %MDD. extrapolated
    is True when target_pct falls outside the tested compaction range, i.e.
    the answer relies on extending the fitted curve rather than interpolating."""
    if fit is None:
        return None, False
    y = float(np.polyval(fit.coeffs, target_pct))
    extrapolated = target_pct < fit.x_min or target_pct > fit.x_max
    return y, extrapolated


def design_cbr_table(rel_compactions: Sequence[float], cbrs: Sequence[float],
                      targets: Sequence[float] = DEFAULT_TARGET_PCTS
                      ) -> Dict[float, Tuple[Optional[float], bool]]:
    """Convenience wrapper: fit once, evaluate at every target %MDD."""
    fit = fit_cbr_vs_compaction(rel_compactions, cbrs)
    return {t: eval_design_cbr(fit, t) for t in targets}


# ==========================================================================
# 5. Swell
# ==========================================================================

def swell_percent(initial_reading_mm: Optional[float], final_reading_mm: Optional[float],
                   specimen_height_mm: Optional[float]) -> Optional[float]:
    initial_reading_mm, final_reading_mm = _f(initial_reading_mm), _f(final_reading_mm)
    specimen_height_mm = _f(specimen_height_mm)
    if not specimen_height_mm or initial_reading_mm is None or final_reading_mm is None:
        return None
    return (final_reading_mm - initial_reading_mm) / specimen_height_mm * 100
