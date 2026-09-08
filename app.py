"""
CBR Test Analyzer — Streamlit front end
BS 1377-4:1990, Clause 7 (California Bearing Ratio)

Run locally:   streamlit run app.py
Deploy:        push this folder to a GitHub repo and connect it on
               https://share.streamlit.io  (Streamlit Community Cloud).
               See README.md for the full walkthrough.
"""

import io
from datetime import date

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from cbr_engine import (
    STD_LOAD_2_5_MM, STD_LOAD_5_0_MM, PLUNGER_AREA_MM2,
    mould_volume_cm3, fit_compaction, compute_cbr, swell_percent,
)
from report import build_pdf_report

BRASS = "#8C6A24"
GRAPHITE = "#2E4B54"
INK = "#1B231E"
INK_SOFT = "#57645C"
GOOD = "#2F6B3D"
WARN = "#A6331F"
LINE = "#D6DCD3"

st.set_page_config(page_title="CBR Test Analyzer", page_icon="📐", layout="wide")

st.markdown(
    f"""
    <style>
      .stMetric {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 4px;
                   padding: 0.6rem 0.8rem; }}
      div[data-testid="stMetricLabel"] {{ font-size: 0.72rem; text-transform: uppercase;
                   letter-spacing: .06em; color: {INK_SOFT}; }}
      div[data-testid="stMetricValue"] {{ color: {INK}; }}
      h1, h2, h3 {{ color: {INK}; }}
      .cbr-eyebrow {{ font-family: monospace; font-size: 0.75rem; letter-spacing: .1em;
                      text-transform: uppercase; color: {INK_SOFT}; margin-bottom: -0.3rem;}}
      .cbr-banner {{ border: 1px dashed #B7C0B3; border-radius: 4px; padding: .5rem .8rem;
                     font-size: .85rem; color: {INK_SOFT}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Example / blank datasets
# ---------------------------------------------------------------------------

def example_project():
    return dict(
        name="Kumasi–Techiman Trunk Road Upgrade", location="Ch. 12+450, LHS",
        sample="TP-07 / BH-3, 0.5-1.5 m", tester="E. Owusu", checker="K. Mensah",
        test_date=date(2026, 8, 14), mould_dia=152.0, mould_height=127.0,
        condition="Soaked (96 h)", surcharge=4.5, soak_hours=96,
    )


def blank_project():
    return dict(
        name="", location="", sample="", tester="", checker="",
        test_date=date.today(), mould_dia=152.0, mould_height=127.0,
        condition="Soaked (96 h)", surcharge=4.5, soak_hours=96,
    )


def example_compaction_df():
    return pd.DataFrame({
        "Trial": [1, 2, 3, 4, 5, 6],
        "Mould + soil (g)": [8343, 8646, 8909, 9098, 9103, 8997],
        "Empty mould (g)": [4210, 4210, 4210, 4210, 4210, 4210],
        "Moisture (%)": [8.0, 10.0, 12.0, 14.0, 16.0, 18.0],
    })


def blank_compaction_df():
    return pd.DataFrame({
        "Trial": [1, 2, 3], "Mould + soil (g)": [None, None, None],
        "Empty mould (g)": [None, None, None], "Moisture (%)": [None, None, None],
    })


def example_penetration_df():
    return pd.DataFrame({
        "Penetration (mm)": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0, 12.5],
        "Reading": [0.00, 0.08, 0.22, 0.42, 0.68, 0.98, 1.22, 1.65, 2.00, 2.55, 2.95, 3.25],
    })


def blank_penetration_df():
    pen = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0, 12.5]
    return pd.DataFrame({"Penetration (mm)": pen, "Reading": [None] * len(pen)})


def init_state():
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.is_example = True
        st.session_state.data_version = 0
        st.session_state.project = example_project()
        st.session_state.compaction_df = example_compaction_df()
        st.session_state.penetration_df = example_penetration_df()
        st.session_state.load_mode = "Direct load (kN)"
        st.session_state.calibration = 0.01
        st.session_state.manual_corr_on = False
        st.session_state.manual_corr = 0.0
        st.session_state.retest_confirmed = False
        st.session_state.swell_init = 0.00
        st.session_state.swell_final = 1.85
        st.session_state.swell_height = 127.0
        st.session_state.swell_target = 2.0
        st.session_state.field_density = 1.79
        st.session_state.target_pct = 95


init_state()
dv = st.session_state.data_version  # bump this to force-reset all keyed widgets below

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown('<p class="cbr-eyebrow">BS 1377-4:1990 · Cl.7 · Laboratory test</p>', unsafe_allow_html=True)
    st.title("📐 CBR Test Analyzer")
with hcol2:
    st.write("")
    b1, b2 = st.columns(2)
    if b1.button("New blank test", use_container_width=True):
        st.session_state.is_example = False
        st.session_state.data_version += 1
        st.session_state.project = blank_project()
        st.session_state.compaction_df = blank_compaction_df()
        st.session_state.penetration_df = blank_penetration_df()
        st.session_state.manual_corr_on = False
        st.session_state.retest_confirmed = False
        st.session_state.swell_init = None
        st.session_state.swell_final = None
        st.session_state.field_density = None
        st.rerun()
    if b2.button("Load example", use_container_width=True):
        st.session_state.is_example = True
        st.session_state.data_version += 1
        st.session_state.project = example_project()
        st.session_state.compaction_df = example_compaction_df()
        st.session_state.penetration_df = example_penetration_df()
        st.session_state.manual_corr_on = False
        st.session_state.retest_confirmed = False
        st.session_state.swell_init = 0.00
        st.session_state.swell_final = 1.85
        st.session_state.field_density = 1.79
        st.rerun()

if st.session_state.is_example:
    st.markdown(
        '<p class="cbr-banner">Showing example data for TP-07 / BH-3 — edit any field below, '
        'or click "New blank test" to start your own.</p>', unsafe_allow_html=True)

readout = st.container()
st.divider()

# ---------------------------------------------------------------------------
# Panel 01 — Project & specimen
# ---------------------------------------------------------------------------

st.header("01 — Project & specimen")
p = st.session_state.project
c1, c2, c3 = st.columns(3)
with c1:
    p["name"] = st.text_input("Project", p["name"], key=f"name_{dv}")
    p["location"] = st.text_input("Location / chainage", p["location"], key=f"location_{dv}")
    p["sample"] = st.text_input("Sample / borehole ID", p["sample"], key=f"sample_{dv}")
with c2:
    p["tester"] = st.text_input("Tested by", p["tester"], key=f"tester_{dv}")
    p["checker"] = st.text_input("Checked by", p["checker"], key=f"checker_{dv}")
    p["test_date"] = st.date_input("Date tested", p["test_date"], key=f"test_date_{dv}")
with c3:
    p["mould_dia"] = st.number_input("Mould diameter (mm)", value=float(p["mould_dia"]), step=0.1, key=f"mould_dia_{dv}")
    p["mould_height"] = st.number_input("Mould height (mm)", value=float(p["mould_height"]), step=0.1, key=f"mould_height_{dv}")
    p["condition"] = st.selectbox("Condition", ["Soaked (96 h)", "Unsoaked"],
                                   index=0 if p["condition"].startswith("Soaked") else 1, key=f"condition_{dv}")
c4, c5 = st.columns(2)
with c4:
    p["surcharge"] = st.number_input("Surcharge mass (kg)", value=float(p["surcharge"]), step=0.1, key=f"surcharge_{dv}")
with c5:
    p["soak_hours"] = st.number_input("Soak period (hours)", value=int(p["soak_hours"]), step=1, key=f"soak_hours_{dv}")

mould_vol = mould_volume_cm3(p["mould_dia"], p["mould_height"])

# ---------------------------------------------------------------------------
# Panel 02 — Compaction relationship
# ---------------------------------------------------------------------------

st.header("02 — Compaction relationship")
st.caption("Dry density is fitted against moisture content with a least-squares parabola to locate OMC and MDD.")

comp_df = st.data_editor(
    st.session_state.compaction_df, num_rows="dynamic", use_container_width=True,
    key=f"compaction_editor_{st.session_state.data_version}",
)
st.session_state.compaction_df = comp_df

comp_calc = comp_df.copy()
if mould_vol:
    wet = (comp_calc["Mould + soil (g)"] - comp_calc["Empty mould (g)"]) / mould_vol
    comp_calc["Wet density (g/cm3)"] = wet.round(3)
    comp_calc["Dry density (g/cm3)"] = (wet / (1 + comp_calc["Moisture (%)"] / 100)).round(3)
else:
    comp_calc["Wet density (g/cm3)"] = np.nan
    comp_calc["Dry density (g/cm3)"] = np.nan
st.dataframe(comp_calc[["Trial", "Wet density (g/cm3)", "Dry density (g/cm3)"]],
             use_container_width=True, hide_index=True)

fit = None
usable = comp_calc.dropna(subset=["Moisture (%)", "Dry density (g/cm3)"])
if len(usable) >= 3:
    fit = fit_compaction(usable["Moisture (%)"].tolist(), usable["Dry density (g/cm3)"].tolist())

fig_comp, ax_comp = plt.subplots(figsize=(7, 3.2))
if len(usable):
    ax_comp.scatter(usable["Moisture (%)"], usable["Dry density (g/cm3)"], color=GRAPHITE, zorder=3, label="Trial points")
if fit:
    xs = np.linspace(usable["Moisture (%)"].min() - 3, usable["Moisture (%)"].max() + 3, 100)
    ys = fit.a * xs ** 2 + fit.b * xs + fit.c
    ax_comp.plot(xs, ys, color=BRASS, linewidth=2, label="Fitted curve")
    ax_comp.scatter([fit.omc], [fit.mdd], color=BRASS, edgecolor=INK, s=90, marker="D", zorder=4, label="OMC / MDD")
    st.success(f"Fitted maximum dry density **{fit.mdd:.3f} g/cm³** at optimum moisture content **{fit.omc:.1f} %** "
               f"(least-squares parabola, {fit.n_points} trials).")
elif len(usable) < 3:
    st.info("Add at least 3 trials (with density and moisture) to fit a compaction curve.")
else:
    st.warning("Points do not show a clear peak — check moisture/density values, or add trials either side of the optimum.")
ax_comp.set_xlabel("Moisture content (%)"); ax_comp.set_ylabel("Dry density (g/cm³)")
ax_comp.grid(color=LINE, linewidth=0.6); ax_comp.legend(fontsize=8, frameon=False)
for spine in ["top", "right"]:
    ax_comp.spines[spine].set_visible(False)
st.pyplot(fig_comp, use_container_width=True)

# ---------------------------------------------------------------------------
# Panel 03 — Penetration test data
# ---------------------------------------------------------------------------

st.header("03 — Penetration test data")
st.caption(f"Standard loads: {STD_LOAD_2_5_MM} kN at 2.5 mm and {STD_LOAD_5_0_MM} kN at 5.0 mm, "
           f"on a {PLUNGER_AREA_MM2} mm² plunger (BS 1377-4).")

lm1, lm2 = st.columns([2, 1])
with lm1:
    st.session_state.load_mode = st.radio(
        "Load input mode", ["Direct load (kN)", "Proving ring dial reading"],
        index=0 if st.session_state.load_mode == "Direct load (kN)" else 1, horizontal=True,
        key=f"load_mode_{dv}",
    )
with lm2:
    if st.session_state.load_mode == "Proving ring dial reading":
        st.session_state.calibration = st.number_input("Calibration (kN / division)",
                                                         value=float(st.session_state.calibration), step=0.001,
                                                         format="%.3f", key=f"calibration_{dv}")

pen_label = "Load (kN)" if st.session_state.load_mode == "Direct load (kN)" else "Dial reading (division)"
pen_df = st.session_state.penetration_df.rename(columns={"Reading": pen_label})
pen_df = st.data_editor(pen_df, num_rows="dynamic", use_container_width=True,
                         key=f"penetration_editor_{st.session_state.data_version}")
pen_df = pen_df.rename(columns={pen_label: "Reading"})
st.session_state.penetration_df = pen_df

pen_calc = pen_df.dropna(subset=["Penetration (mm)", "Reading"]).copy()
if st.session_state.load_mode == "Proving ring dial reading":
    pen_calc["Load (kN)"] = pen_calc["Reading"] * st.session_state.calibration
    st.dataframe(pen_calc[["Penetration (mm)", "Load (kN)"]].round(3), use_container_width=True, hide_index=True)
else:
    pen_calc["Load (kN)"] = pen_calc["Reading"]

points = list(zip(pen_calc["Penetration (mm)"].tolist(), pen_calc["Load (kN)"].tolist()))

oc1, oc2, oc3 = st.columns([1, 1, 2])
with oc1:
    st.session_state.manual_corr_on = st.checkbox("Override auto correction", value=st.session_state.manual_corr_on,
                                                    key=f"manual_corr_on_{dv}")
with oc2:
    st.session_state.manual_corr = st.number_input("Correction (mm)", value=float(st.session_state.manual_corr),
                                                     step=0.01, disabled=not st.session_state.manual_corr_on,
                                                     key=f"manual_corr_{dv}")

manual = st.session_state.manual_corr if st.session_state.manual_corr_on else None
cbr = compute_cbr(points, manual_correction=manual, retest_confirmed=st.session_state.retest_confirmed)

if cbr.needs_retest:
    st.session_state.retest_confirmed = st.checkbox(
        "⚠ 5.0 mm value exceeds 2.5 mm — repeat test to confirm; check once retest verifies this result.",
        value=st.session_state.retest_confirmed, key=f"retest_{dv}")
    cbr = compute_cbr(points, manual_correction=manual, retest_confirmed=st.session_state.retest_confirmed)
else:
    st.session_state.retest_confirmed = False

fig_pen, ax_pen = plt.subplots(figsize=(7, 3.4))
if points:
    raw = sorted(points)
    corr_pts = [(max(0, x - cbr.correction_mm), y) for x, y in raw]
    ax_pen.plot(*zip(*raw), color=INK_SOFT, linestyle="--", linewidth=1.3, label="Raw curve")
    ax_pen.plot(*zip(*corr_pts), color=BRASS, linewidth=2.4, label="Corrected curve")
    markers_x, markers_y = [], []
    if cbr.cbr_2_5 is not None:
        markers_x.append(2.5); markers_y.append(cbr.cbr_2_5 / 100 * STD_LOAD_2_5_MM)
    if cbr.cbr_5_0 is not None:
        markers_x.append(5.0); markers_y.append(cbr.cbr_5_0 / 100 * STD_LOAD_5_0_MM)
    if markers_x:
        ax_pen.scatter(markers_x, markers_y, color=GRAPHITE, edgecolor="white", s=80, zorder=5, label="2.5 / 5.0 mm")
ax_pen.set_xlabel("Penetration (mm)"); ax_pen.set_ylabel("Load (kN)")
ax_pen.grid(color=LINE, linewidth=0.6); ax_pen.legend(fontsize=8, frameon=False)
for spine in ["top", "right"]:
    ax_pen.spines[spine].set_visible(False)
st.pyplot(fig_pen, use_container_width=True)

st.caption("CBR is normally reported at 2.5 mm penetration; the 5.0 mm value is used only once a repeat test "
           "confirms it exceeds the 2.5 mm value.")

# ---------------------------------------------------------------------------
# Panel 04 — Swell
# ---------------------------------------------------------------------------

swell_pct = None
if p["condition"].startswith("Soaked"):
    st.header("04 — Swell")
    st.caption("Dial gauge readings before and after the soaking period, per BS 1377-4 Cl.7.3.")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.session_state.swell_init = st.number_input("Initial dial reading (mm)",
                                                        value=st.session_state.swell_init, step=0.01,
                                                        key=f"swell_init_{dv}")
    with s2:
        st.session_state.swell_final = st.number_input("Final dial reading (mm)",
                                                         value=st.session_state.swell_final, step=0.01,
                                                         key=f"swell_final_{dv}")
    with s3:
        st.session_state.swell_height = st.number_input("Specimen height (mm)",
                                                          value=st.session_state.swell_height, step=0.1,
                                                          key=f"swell_height_{dv}")
    with s4:
        st.session_state.swell_target = st.number_input("Target max swell (%, optional)",
                                                          value=st.session_state.swell_target, step=0.1,
                                                          key=f"swell_target_{dv}")
    if st.session_state.swell_init is not None and st.session_state.swell_final is not None:
        swell_pct = swell_percent(st.session_state.swell_init, st.session_state.swell_final, st.session_state.swell_height)
        if swell_pct is not None and st.session_state.swell_target:
            (st.success if swell_pct <= st.session_state.swell_target else st.warning)(
                f"Swell = {swell_pct:.2f}% ({'within' if swell_pct <= st.session_state.swell_target else 'exceeds'} "
                f"target of {st.session_state.swell_target:.1f}%).")

# ---------------------------------------------------------------------------
# Panel 05 — Field compaction check
# ---------------------------------------------------------------------------

st.header("05 — Field compaction check (optional)")
st.caption("Compares a measured field dry density against the MDD fitted in Panel 02.")
f1, f2 = st.columns(2)
with f1:
    st.session_state.field_density = st.number_input("Field dry density (g/cm³)",
                                                       value=st.session_state.field_density, step=0.01,
                                                       key=f"field_density_{dv}")
with f2:
    st.session_state.target_pct = st.number_input("Target compaction (% of MDD)",
                                                    value=int(st.session_state.target_pct), step=1,
                                                    key=f"target_pct_{dv}")

pct_mdd = None
if fit and st.session_state.field_density:
    pct_mdd = st.session_state.field_density / fit.mdd * 100
    (st.success if pct_mdd >= st.session_state.target_pct else st.warning)(
        f"Field density is {pct_mdd:.1f}% of MDD "
        f"({'meets' if pct_mdd >= st.session_state.target_pct else 'below'} the {st.session_state.target_pct}% target).")

# ---------------------------------------------------------------------------
# Readout (filled last, rendered first)
# ---------------------------------------------------------------------------

with readout:
    cols = st.columns(7)
    cols[0].metric("Selected CBR", f"{cbr.selected_cbr:.1f}%" if cbr.selected_cbr is not None else "—", cbr.governing)
    cols[1].metric("CBR @ 2.5 mm", f"{cbr.cbr_2_5:.1f}%" if cbr.cbr_2_5 is not None else "—")
    cols[2].metric("CBR @ 5.0 mm", f"{cbr.cbr_5_0:.1f}%" if cbr.cbr_5_0 is not None else "—")
    cols[3].metric("Correction", f"{cbr.correction_mm:.2f} mm")
    cols[4].metric("Swell", f"{swell_pct:.2f}%" if swell_pct is not None else "—")
    cols[5].metric("MDD / OMC", f"{fit.mdd:.2f} g/cm³" if fit else "—", f"at {fit.omc:.1f}% OMC" if fit else None)
    cols[6].metric("Field compaction", f"{pct_mdd:.1f}% MDD" if pct_mdd is not None else "—")

st.divider()

# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------

st.header("Report")
st.caption("Method: BS 1377-4:1990, Clause 7. This tool assists calculation and curve correction; results should "
           "still be reviewed by a qualified geotechnical engineer, and any 5.0 mm / 2.5 mm anomaly confirmed by retest.")

pdf_bytes = build_pdf_report(
    project=p, mould_vol=mould_vol, comp_calc=comp_calc, fit=fit,
    pen_calc=pen_calc if points else None, cbr=cbr,
    swell_pct=swell_pct, swell_state=st.session_state, pct_mdd=pct_mdd,
    fig_comp=fig_comp, fig_pen=fig_pen,
)
st.download_button("⬇ Download PDF report", data=pdf_bytes,
                    file_name=f"CBR_report_{p['sample'] or 'test'}.pdf".replace(" ", "_").replace("/", "-"),
                    mime="application/pdf")
