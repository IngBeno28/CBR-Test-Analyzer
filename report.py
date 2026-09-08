"""
report.py — builds the downloadable PDF lab report for the CBR Test Analyzer,
using reportlab. Kept separate from app.py so the report layout can evolve
independently of the Streamlit UI.
"""

import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable,
)

BRASS = colors.HexColor("#8C6A24")
GRAPHITE = colors.HexColor("#2E4B54")
INK = colors.HexColor("#1B231E")
INK_SOFT = colors.HexColor("#57645C")
LINE = colors.HexColor("#D6DCD3")
GOOD_BG = colors.HexColor("#E4F0E6")
WARN_BG = colors.HexColor("#F6E1DC")


def _fig_to_image(fig, width_mm=170):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight")
    buf.seek(0)
    return Image(buf, width=width_mm * mm, height=width_mm * mm * fig.get_figheight() / fig.get_figwidth())


def build_pdf_report(project, mould_vol, comp_calc, fit, pen_calc, cbr,
                      swell_pct, swell_state, pct_mdd, fig_comp, fig_pen) -> bytes:
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=INK, fontSize=17, spaceAfter=2)
    eyebrow = ParagraphStyle("eyebrow", parent=styles["Normal"], textColor=INK_SOFT, fontSize=8,
                              fontName="Helvetica", spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=INK, fontSize=12, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], textColor=INK, fontSize=9, leading=13)
    small = ParagraphStyle("small", parent=styles["Normal"], textColor=INK_SOFT, fontSize=7.5, leading=11)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm)
    story = []

    story.append(Paragraph("BS 1377-4:1990 · Cl.7 · Laboratory Test", eyebrow))
    story.append(Paragraph("California Bearing Ratio (CBR) Test Report", h1))
    story.append(HRFlowable(width="100%", color=LINE, thickness=1))
    story.append(Spacer(1, 8))

    # --- project table ---
    proj_rows = [
        ["Project", project.get("name") or "—", "Sample / borehole ID", project.get("sample") or "—"],
        ["Location / chainage", project.get("location") or "—", "Date tested", str(project.get("test_date") or "—")],
        ["Tested by", project.get("tester") or "—", "Checked by", project.get("checker") or "—"],
        ["Condition", project.get("condition") or "—", "Surcharge", f"{project.get('surcharge') or 0} kg"],
        ["Mould diameter", f"{project.get('mould_dia') or 0} mm", "Mould height", f"{project.get('mould_height') or 0} mm"],
    ]
    t = Table(proj_rows, colWidths=[32 * mm, 60 * mm, 32 * mm, 54 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT), ("TEXTCOLOR", (2, 0), (2, -1), INK_SOFT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # --- results summary ---
    story.append(Paragraph("Results summary", h2))
    sel = f"{cbr.selected_cbr:.1f}%" if cbr.selected_cbr is not None else "—"
    c25 = f"{cbr.cbr_2_5:.1f}%" if cbr.cbr_2_5 is not None else "—"
    c50 = f"{cbr.cbr_5_0:.1f}%" if cbr.cbr_5_0 is not None else "—"
    mdd_s = f"{fit.mdd:.3f} g/cm³ at {fit.omc:.1f}% OMC" if fit else "—"
    swell_s = f"{swell_pct:.2f}%" if swell_pct is not None else "—"
    field_s = f"{pct_mdd:.1f}% of MDD" if pct_mdd is not None else "—"
    summary_rows = [
        ["Selected CBR", sel, "Governed by", cbr.governing],
        ["CBR @ 2.5 mm", c25, "CBR @ 5.0 mm", c50],
        ["Curve correction", f"{cbr.correction_mm:.2f} mm", "Compaction (MDD / OMC)", mdd_s],
        ["Swell", swell_s, "Field compaction", field_s],
    ]
    pending_retest = cbr.needs_retest and cbr.governing == "2.5 mm"
    t2 = Table(summary_rows, colWidths=[36 * mm, 40 * mm, 40 * mm, 62 * mm])
    t2.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT), ("TEXTCOLOR", (2, 0), (2, -1), INK_SOFT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Courier-Bold"), ("FONTNAME", (3, 0), (3, -1), "Courier-Bold"),
        ("BACKGROUND", (0, 0), (1, 0), WARN_BG if pending_retest else GOOD_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
    if cbr.needs_retest:
        note_style = ParagraphStyle("warn", parent=body, textColor=colors.HexColor("#A6331F"))
        confirmed = getattr(swell_state, "retest_confirmed", False)
        msg = ("5.0 mm value exceeds 2.5 mm — " +
               ("confirmed by retest; 5.0 mm value reported." if confirmed else
                "repeat test to confirm before relying on this result."))
        story.append(Spacer(1, 4))
        story.append(Paragraph("⚠ " + msg, note_style))
    story.append(Spacer(1, 10))

    # --- compaction ---
    story.append(Paragraph("Compaction relationship", h2))
    if comp_calc is not None and len(comp_calc):
        header = ["Trial", "Mould+soil (g)", "Empty mould (g)", "Moisture (%)", "Wet density", "Dry density"]
        body_df = comp_calc[["Trial", "Mould + soil (g)", "Empty mould (g)", "Moisture (%)",
                              "Wet density (g/cm3)", "Dry density (g/cm3)"]].copy()
        body_df["Trial"] = body_df["Trial"].apply(lambda v: str(int(v)) if pd.notna(v) else "—")
        rows = [header] + body_df.fillna("—").values.tolist()
        tc = Table(rows, repeatRows=1)
        tc.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), GRAPHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F1")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tc)
        story.append(Spacer(1, 6))
        story.append(_fig_to_image(fig_comp))
    else:
        story.append(Paragraph("No compaction data recorded.", body))
    story.append(Spacer(1, 10))

    # --- penetration ---
    story.append(Paragraph("Penetration test data", h2))
    if pen_calc is not None and len(pen_calc):
        header = ["Penetration (mm)", "Load (kN)"]
        rows = [header] + pen_calc[["Penetration (mm)", "Load (kN)"]].round(3).values.tolist()
        tp = Table(rows, repeatRows=1, colWidths=[50 * mm, 50 * mm])
        tp.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), GRAPHITE),
            ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F1")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tp)
        story.append(Spacer(1, 6))
        story.append(_fig_to_image(fig_pen))
    else:
        story.append(Paragraph("No penetration data recorded.", body))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", color=LINE, thickness=1))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Method: BS 1377-4:1990, Clause 7 — California Bearing Ratio. Standard loads 13.2 kN @ 2.5 mm / "
        "20.0 kN @ 5.0 mm on a 1935 mm² (49.63 mm dia.) plunger. This report assists calculation and curve "
        "correction; results should be reviewed by a qualified geotechnical engineer, and any 5.0 mm / 2.5 mm "
        "anomaly confirmed by retest per the standard.", small))
    story.append(Paragraph(f"Report generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", small))

    doc.build(story)
    return buf.getvalue()
