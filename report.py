"""
report.py — builds the downloadable PDF lab report for the CBR Test Analyzer,
using reportlab. Kept separate from app.py so the report layout can evolve
independently of the Streamlit UI.

Covers all 4 stages of the project template this tool is modelled on:
  1. General compaction (OMC / MDD)
  2. CBR compaction at several compactive efforts
  3. Penetration testing per specimen (CBR @ 2.5 / 5.0 mm)
  4. Design CBR summary (CBR vs %MDD, read off at target compaction levels)
"""

import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak,
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


def _grid_table(rows, col_widths=None, align_right_from=1):
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), GRAPHITE),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F1")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _fmt(v, nd=2, suffix=""):
    try:
        if v is None or (isinstance(v, float) and v != v):
            return "—"
        return f"{float(v):.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return str(v) if v not in (None, "") else "—"


def build_pdf_report(project, comp_calc, fit, fig_comp,
                      cbr_comp_calc, cbr_results, figs_pen,
                      design_df, fig_design) -> bytes:
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=INK, fontSize=17, spaceAfter=2)
    eyebrow = ParagraphStyle("eyebrow", parent=styles["Normal"], textColor=INK_SOFT, fontSize=8,
                              fontName="Helvetica", spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=INK, fontSize=12, spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], textColor=INK, fontSize=10.5, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["Normal"], textColor=INK, fontSize=9, leading=13)
    small = ParagraphStyle("small", parent=styles["Normal"], textColor=INK_SOFT, fontSize=7.5, leading=11)
    warn_style = ParagraphStyle("warn", parent=body, textColor=colors.HexColor("#A6331F"))

    cell_style = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=10.5)

    def _cell(text):
        """Wrap a table cell value in a Paragraph so long text wraps instead
        of overflowing into the neighbouring column."""
        return Paragraph(str(text) if text not in (None, "") else "—", cell_style)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                             leftMargin=16 * mm, rightMargin=16 * mm)
    story = []

    story.append(Paragraph("BS 1377-4:1990 · Cl.7 · Compaction &amp; CBR Laboratory Report", eyebrow))
    story.append(Paragraph("California Bearing Ratio (CBR) Test Report", h1))
    story.append(HRFlowable(width="100%", color=LINE, thickness=1))
    story.append(Spacer(1, 8))

    # --- project table ---
    proj_rows = [
        ["Project", _cell(project.get("name")), "Test code", _cell(project.get("test_code"))],
        ["Material type", _cell(project.get("material")), "Layer", _cell(project.get("layer"))],
        ["Sampled from", _cell(project.get("sampled_from")), "Sampled date", _cell(project.get("sampled_date"))],
        ["Technician", _cell(project.get("technician")), "Test date", _cell(project.get("test_date"))],
        ["Condition", _cell(project.get("condition")), "Surcharge", f"{project.get('surcharge') or 0} kg"],
        ["Std. load @2.5mm", f"{_fmt(project.get('std_load_2_5'), 3)} kN",
         "Std. load @5.0mm", f"{_fmt(project.get('std_load_5_0'), 3)} kN"],
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
    mdd_s = f"{fit.mdd/1000:.3f} g/cm³ at {fit.omc:.1f}% OMC" if fit else "—"
    best = None
    if cbr_results:
        scored = [(lbl, r) for lbl, r in cbr_results.items() if r.selected_cbr is not None]
        if scored:
            best = max(scored, key=lambda t: t[1].selected_cbr)
    design_summary = "—"
    if design_df is not None and len(design_df):
        parts = [f"{row['Target (% MDD)']:.0f}%→{_fmt(row['Design CBR (%)'], 1, '%')}" for _, row in design_df.iterrows()]
        design_summary = "; ".join(parts)
    summary_rows = [
        ["Compaction (MDD / OMC)", mdd_s, "Specimens tested", str(len(cbr_results) if cbr_results else 0)],
        ["Highest specimen CBR", f"{best[1].selected_cbr:.1f}% ({best[0]})" if best else "—",
         "Design CBR summary", _cell(design_summary)],
    ]
    t2 = Table(summary_rows, colWidths=[38 * mm, 48 * mm, 38 * mm, 54 * mm])
    t2.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT), ("TEXTCOLOR", (2, 0), (2, -1), INK_SOFT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (1, -1), GOOD_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # --- 1. compaction ---
    story.append(Paragraph("1 · Compaction relationship (standard Proctor)", h2))
    if comp_calc is not None and len(comp_calc):
        header = ["Trial", "Air-dry (g)", "Mould factor", "Moisture (%)", "Wet density (kg/m³)", "Dry density (kg/m³)"]
        cols = ["Trial", "Air-dry sample (g)", "Mould Factor", "Moisture (%)", "Wet density (kg/m3)", "Dry density (kg/m3)"]
        body_rows = []
        for _, r in comp_calc.iterrows():
            body_rows.append([
                _fmt(r.get("Trial"), 0), _fmt(r.get("Air-dry sample (g)"), 0), _fmt(r.get("Mould Factor"), 4),
                _fmt(r.get("Moisture (%)"), 2), _fmt(r.get("Wet density (kg/m3)"), 1), _fmt(r.get("Dry density (kg/m3)"), 1),
            ])
        story.append(_grid_table([header] + body_rows))
        story.append(Spacer(1, 6))
        if fig_comp is not None:
            story.append(_fig_to_image(fig_comp))
    else:
        story.append(Paragraph("No compaction data recorded.", body))
    story.append(Spacer(1, 6))

    # --- 2 & 3. CBR compaction + penetration, per specimen ---
    story.append(Paragraph("2 · CBR compaction &amp; 3 · Penetration testing", h2))
    if cbr_comp_calc is not None and len(cbr_comp_calc):
        header = ["Specimen", "Moisture (%)", "Dry density (kg/m³)", "Relative compaction (%)",
                   "CBR@2.5mm (%)", "CBR@5.0mm (%)", "Governing CBR (%)"]
        body_rows = []
        for _, r in cbr_comp_calc.iterrows():
            lbl = r.get("Specimen")
            res = (cbr_results or {}).get(lbl)
            body_rows.append([
                lbl or "—", _fmt(r.get("Moisture (%)"), 2), _fmt(r.get("Dry density (kg/m3)"), 1),
                _fmt(r.get("Relative compaction (%)"), 1),
                _fmt(res.cbr_2_5, 1) if res else "—", _fmt(res.cbr_5_0, 1) if res else "—",
                _fmt(res.selected_cbr, 1) if res else "—",
            ])
        story.append(_grid_table([header] + body_rows, align_right_from=1))
        story.append(Spacer(1, 6))

        anomalies = [lbl for lbl, r in (cbr_results or {}).items() if r.anomaly]
        if anomalies:
            story.append(Paragraph(
                "Note: CBR@5.0mm exceeded CBR@2.5mm for: " + ", ".join(anomalies) +
                " — governing value taken as the higher (5.0 mm) result, per project convention.", warn_style))
            story.append(Spacer(1, 4))

        for lbl, fig in (figs_pen or {}).items():
            story.append(Paragraph(f"Penetration curve — {lbl}", h3))
            story.append(_fig_to_image(fig, width_mm=150))
    else:
        story.append(Paragraph("No CBR compaction / penetration data recorded.", body))

    story.append(PageBreak())

    # --- 4. Design CBR ---
    story.append(Paragraph("4 · Design CBR summary", h2))
    if design_df is not None and len(design_df):
        header = ["Target (% MDD)", "Design CBR (%)", "Note"]
        body_rows = [[_fmt(r["Target (% MDD)"], 0), _fmt(r["Design CBR (%)"], 1), r.get("Note") or ""]
                     for _, r in design_df.iterrows()]
        story.append(_grid_table([header] + body_rows, col_widths=[35 * mm, 35 * mm, 100 * mm]))
        story.append(Spacer(1, 6))
        if fig_design is not None:
            story.append(_fig_to_image(fig_design))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "CBR values fitted against relative compaction across the tested specimens (quadratic fit for 3+ "
            "points) and evaluated at each target compaction level — this is the design CBR used for pavement "
            "layer selection.", small))
    else:
        story.append(Paragraph("Design CBR not available — at least 2 specimens with relative compaction and "
                                "CBR are needed.", body))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", color=LINE, thickness=1))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Method: BS 1377-4:1990, Clause 7 — California Bearing Ratio. Governing CBR per specimen is the higher "
        "of the 2.5 mm and 5.0 mm values (project convention). This report assists calculation and curve "
        "fitting; results should be reviewed by a qualified geotechnical engineer before use in pavement design.",
        small))
    prep_rows = [["Prepared by", project.get("prepared_by") or "—", "Approved by", project.get("approved_by") or "—"]]
    story.append(Spacer(1, 8))
    tp = Table(prep_rows, colWidths=[26 * mm, 66 * mm, 26 * mm, 60 * mm])
    tp.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), INK_SOFT), ("TEXTCOLOR", (2, 0), (2, -1), INK_SOFT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tp)
    story.append(Paragraph(f"Report generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", small))

    doc.build(story)
    return buf.getvalue()
