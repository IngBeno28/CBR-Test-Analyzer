"""
report.py — builds the downloadable PDF lab report for the CBR Test Analyzer,
using reportlab.

Layout follows the shared Automation_hub report template (same cover page,
per-item results/chart page rhythm, and certification page used by the
suite's other tools): a branded cover page, then one results page + one
chart page per test item, then a certification page — with a running footer
on every page.

Kept separate from app.py so the report layout can evolve independently of
the Streamlit UI. Covers all 4 stages of the project template this tool is
modelled on:
  1. General compaction (OMC / MDD)
  2. CBR compaction at several compactive efforts
  3. Penetration testing per specimen (CBR @ 2.5 / 5.0 mm)
  4. Design CBR summary (CBR vs %MDD, read off at target compaction levels)
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak,
)

import assets

# ============================================================================
# Branding constants — shared across Automation_hub's tools. Edit these in
# one place to rebrand the report.
# ============================================================================
COMPANY_NAME = "Automation_hub Engineering Group Limited"
APP_NAME = "CBR Test Analyzer"
APP_TAGLINE = "Built for engineering precision"

BRASS = colors.HexColor("#8C6A24")
GRAPHITE = colors.HexColor("#2E4B54")
INK = colors.HexColor("#1B231E")
INK_SOFT = colors.HexColor("#57645C")
LINE = colors.HexColor("#D6DCD3")
WARN = colors.HexColor("#A6331F")

PAGE_SIZE = A4
MARGIN = 18 * mm
BANNER_HEIGHT = 11 * mm


# ============================================================================
# Logo (embedded in assets.py — no external image file needed)
# ============================================================================
def _logo_flowable(max_w_mm=45, max_h_mm=28):
    """Fit the Automation_hub logo within a bounding box, preserving its
    aspect ratio (it isn't square) rather than stretching it to fit."""
    from PIL import Image as PILImage

    buf = assets.get_logo_image()
    w_px, h_px = PILImage.open(buf).size
    buf.seek(0)
    aspect = h_px / w_px
    width = max_w_mm * mm
    height = width * aspect
    if height > max_h_mm * mm:
        height = max_h_mm * mm
        width = height / aspect
    flow = Image(buf, width=width, height=height)
    flow.hAlign = "CENTER"
    return flow


# ============================================================================
# Paragraph styles
# ============================================================================
def _styles():
    return {
        "title": ParagraphStyle(
            "ReportTitle", fontName="Helvetica-Bold", fontSize=21,
            textColor=BRASS, alignment=TA_CENTER, spaceBefore=8, spaceAfter=4, leading=25,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", fontName="Helvetica", fontSize=11,
            textColor=INK_SOFT, alignment=TA_CENTER, spaceAfter=6,
        ),
        "item_label": ParagraphStyle(
            "ItemLabel", fontName="Helvetica-Bold", fontSize=13,
            textColor=INK, alignment=TA_CENTER, spaceBefore=4, spaceAfter=6,
        ),
        "item_headline": ParagraphStyle(
            "ItemHeadline", fontName="Helvetica-Bold", fontSize=19,
            textColor=BRASS, alignment=TA_CENTER, spaceAfter=4, leading=23,
        ),
        "item_subtitle": ParagraphStyle(
            "ItemSubtitle", fontName="Helvetica", fontSize=10,
            textColor=INK_SOFT, alignment=TA_CENTER, spaceAfter=12,
        ),
        "section_header": ParagraphStyle(
            "SectionHeader", fontName="Helvetica-Bold", fontSize=13,
            textColor=INK, alignment=TA_LEFT, spaceBefore=12, spaceAfter=6,
        ),
        "sub_header": ParagraphStyle(
            "SubHeader", fontName="Helvetica-Bold", fontSize=10,
            textColor=INK, alignment=TA_LEFT, spaceBefore=2, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body", fontName="Helvetica", fontSize=9.5, textColor=INK,
            alignment=TA_LEFT, spaceAfter=6, leading=13.5,
        ),
        "bullet": ParagraphStyle(
            "Bullet", fontName="Helvetica", fontSize=9.5, textColor=INK,
            alignment=TA_LEFT, spaceAfter=3, leading=13, leftIndent=10,
        ),
        "warn_bullet": ParagraphStyle(
            "WarnBullet", fontName="Helvetica", fontSize=9.5, textColor=WARN,
            alignment=TA_LEFT, spaceAfter=3, leading=13, leftIndent=10,
        ),
        "italic_center": ParagraphStyle(
            "ItalicCenter", fontName="Helvetica-Oblique", fontSize=9,
            textColor=INK_SOFT, alignment=TA_CENTER,
        ),
        "italic_left": ParagraphStyle(
            "ItalicLeft", fontName="Helvetica-Oblique", fontSize=8.5,
            textColor=INK_SOFT, alignment=TA_LEFT,
        ),
        "cert_title": ParagraphStyle(
            "CertTitle", fontName="Helvetica-Bold", fontSize=18,
            textColor=INK, alignment=TA_CENTER, spaceAfter=14,
        ),
        "cell": ParagraphStyle(
            "Cell", fontName="Helvetica", fontSize=8.5, textColor=INK, leading=11,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold", fontName="Helvetica-Bold", fontSize=8.5, textColor=INK, leading=11,
        ),
    }


# ============================================================================
# Footer with page numbers (two-pass canvas, standard reportlab recipe)
# ============================================================================
def _make_footer_canvas():
    class FooterCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            page_count = len(self._saved_page_states)
            for i, state in enumerate(self._saved_page_states):
                self.__dict__.update(state)
                if i == 0:
                    self._draw_cover_banner()
                self._draw_footer(i + 1, page_count)
                super().showPage()
            super().save()

        def _draw_cover_banner(self):
            """Solid-color bar across the very top of the cover page only —
            matches the banner on the reference report template."""
            width, height = PAGE_SIZE
            self.saveState()
            self.setFillColor(BRASS)
            self.rect(0, height - BANNER_HEIGHT, width, BANNER_HEIGHT, fill=1, stroke=0)
            self.restoreState()

        def _draw_footer(self, page_num, page_count):
            width, _ = PAGE_SIZE
            y = 14 * mm
            self.saveState()
            self.setStrokeColor(LINE)
            self.setLineWidth(0.5)
            self.line(MARGIN, y + 8, width - MARGIN, y + 8)
            self.setFont("Helvetica", 8)
            self.setFillColor(INK_SOFT)
            left = f"{COMPANY_NAME} | © {datetime.now().year} {APP_NAME} | {APP_TAGLINE}"
            self.drawString(MARGIN, y, left)
            self.drawRightString(width - MARGIN, y, f"Page {page_num}/{page_count}")
            self.restoreState()

    return FooterCanvas


# ============================================================================
# Chart embedding helper
# ============================================================================
def _fig_to_image(fig, max_width_mm=165, max_height_mm=220):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    buf.seek(0)
    from PIL import Image as PILImage
    w_px, h_px = PILImage.open(buf).size
    buf.seek(0)
    aspect = h_px / w_px
    width = max_width_mm * mm
    height = width * aspect
    if height > max_height_mm * mm:
        height = max_height_mm * mm
        width = height / aspect
    flow = Image(buf, width=width, height=height)
    flow.hAlign = "CENTER"
    return flow


# ============================================================================
# Table helpers
# ============================================================================
def _info_table(rows, col_widths=(42 * mm, 122 * mm)):
    """Cover-page style table: bold label column, plain value column, thin
    border, no header row."""
    tbl = Table(rows, colWidths=list(col_widths))
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOX", (0, 0), (-1, -1), 0.75, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _plain_table(rows, col_widths=None, center_cols=()):
    """Bordered data table with a bold (non-colored) header row — the style
    used for every multi-row results table in this report."""
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for c in center_cols:
        style.append(("ALIGN", (c, 0), (c, -1), "CENTER"))
    t.setStyle(TableStyle(style))
    return t


def _fmt(v, nd=2, suffix=""):
    try:
        if v is None or (isinstance(v, float) and v != v):
            return "—"
        return f"{float(v):.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return str(v) if v not in (None, "") else "—"


def _cell(text, styles, bold=False):
    return Paragraph(str(text) if text not in (None, "") else "—",
                      styles["cell_bold"] if bold else styles["cell"])


# ============================================================================
# Per-specimen "Engineering Interpretation" notes — every line below is read
# directly off values already computed elsewhere (nothing new is inferred),
# in the same spirit as the shared report template's auto-generated notes.
# ============================================================================
def _specimen_interpretation(res, condition, relative_compaction, swell_pct):
    summary = None
    notes = []
    if res is not None and res.selected_cbr is not None:
        rc_txt = f", specimen compacted to {relative_compaction:.1f}% of MDD" if relative_compaction == relative_compaction and relative_compaction is not None else ""
        summary = f"Governing CBR of {res.selected_cbr:.1f}% taken at {res.governing_mm}{rc_txt}."
        if res.anomaly:
            notes.append(
                f"CBR@5.0mm ({_fmt(res.cbr_5_0, 1)}%) exceeded CBR@2.5mm ({_fmt(res.cbr_2_5, 1)}%) — "
                "governing value taken as the higher (5.0 mm) result, per project convention."
            )
        if res.correction_mm:
            notes.append(f"Curve-origin correction of {res.correction_mm:.2f} mm applied before CBR was read off.")
    else:
        summary = "No penetration data recorded for this specimen."
    if condition and str(condition).startswith("Soaked") and swell_pct is not None:
        notes.append(f"Swell recorded during soaking: {swell_pct:.2f}%.")
    return summary, notes


def _interpretation_block(story, styles, title, summary, notes):
    story.append(Paragraph("Engineering Interpretation", styles["section_header"]))
    if title:
        story.append(Paragraph(title, styles["sub_header"]))
    story.append(Paragraph(summary, styles["body"]))
    for n in notes:
        style = styles["warn_bullet"] if n.lower().startswith("cbr@5.0mm") else styles["bullet"]
        story.append(Paragraph(f"• {n}", style))


# ============================================================================
# Main entry point
# ============================================================================
def build_pdf_report(project, comp_calc, fit, fig_comp,
                      cbr_comp_calc, cbr_results, figs_pen,
                      design_df, fig_design, swell=None) -> bytes:
    styles = _styles()
    swell = swell or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=PAGE_SIZE, topMargin=MARGIN, bottomMargin=28 * mm,
        leftMargin=MARGIN, rightMargin=MARGIN, title=f"{APP_NAME} Report",
    )
    story = []

    # ---------------- Page 1: cover ----------------
    story.append(Spacer(1, 6 * mm))
    story.append(_logo_flowable())
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("CBR Test Report", styles["title"]))
    story.append(Paragraph("CBR Test Analyzer · BS 1377-4:1990, Clause 7", styles["subtitle"]))
    story.append(HRFlowable(width="55%", thickness=1.4, color=BRASS, spaceAfter=10, hAlign="CENTER"))
    story.append(Spacer(1, 6 * mm))

    n_specimens = len(cbr_results) if cbr_results else 0
    info_rows = [
        [Paragraph("Project", styles["cell_bold"]), _cell(project.get("name") or "Unnamed Project", styles)],
        [Paragraph("Prepared By", styles["cell_bold"]), _cell(project.get("prepared_by") or COMPANY_NAME, styles)],
        [Paragraph("Date Generated", styles["cell_bold"]), _cell(datetime.now().strftime("%Y-%m-%d %H:%M"), styles)],
        [Paragraph("Specimens Tested", styles["cell_bold"]), _cell(str(n_specimens), styles)],
    ]
    story.append(_info_table(info_rows))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph(
        f"© {datetime.now().year} {APP_NAME} | {APP_TAGLINE}", styles["italic_center"],
    ))
    story.append(PageBreak())

    # ---------------- Compaction (Proctor): results page ----------------
    story.append(Paragraph("Compaction (Proctor)", styles["item_label"]))
    mdd_headline = f"{fit.mdd:.1f} kg/m³ MDD" if fit else "MDD —"
    story.append(Paragraph(mdd_headline, styles["item_headline"]))
    omc_sub = f"at {fit.omc:.1f}% optimum moisture content ({fit.n_points} trials)" if fit else "Not enough trials to fit a curve"
    story.append(Paragraph(omc_sub, styles["item_subtitle"]))

    if comp_calc is not None and len(comp_calc):
        header = ["Trial", "Air-dry (g)", "Mould factor", "Moisture (%)", "Wet density (kg/m³)", "Dry density (kg/m³)"]
        body_rows = []
        for _, r in comp_calc.iterrows():
            body_rows.append([
                _fmt(r.get("Trial"), 0), _fmt(r.get("Air-dry sample (g)"), 0), _fmt(r.get("Mould Factor"), 4),
                _fmt(r.get("Moisture (%)"), 2), _fmt(r.get("Wet density (kg/m3)"), 1), _fmt(r.get("Dry density (kg/m3)"), 1),
            ])
        story.append(_plain_table([header] + body_rows, center_cols=range(1, 6)))
        story.append(Spacer(1, 10))
        summary = (
            f"Fitted maximum dry density {fit.mdd:.1f} kg/m³ ({fit.mdd / 1000:.3f} g/cm³) at optimum "
            f"moisture content {fit.omc:.1f}% (least-squares parabola, {fit.n_points} trials)."
            if fit else
            "Fewer than 3 usable trials were recorded, or the points did not show a clear peak — a "
            "compaction curve could not be fitted."
        )
        _interpretation_block(story, styles, None, summary, [])
    else:
        story.append(Paragraph("No compaction data recorded.", styles["body"]))
    story.append(PageBreak())

    # ---------------- Compaction (Proctor): chart page ----------------
    if fig_comp is not None:
        story.append(_fig_to_image(fig_comp))
        story.append(PageBreak())

    # ---------------- Per-specimen: results + chart pages ----------------
    if cbr_comp_calc is not None and len(cbr_comp_calc):
        for _, r in cbr_comp_calc.iterrows():
            lbl = r.get("Specimen")
            res = (cbr_results or {}).get(lbl)
            rel_comp = r.get("Relative compaction (%)")

            story.append(Paragraph(f"Specimen: {lbl}", styles["item_label"]))
            headline = f"Governing CBR: {_fmt(res.selected_cbr, 1, '%')}" if res else "Governing CBR: —"
            story.append(Paragraph(headline, styles["item_headline"]))
            sub = f"Governing at {res.governing_mm}" if (res and res.selected_cbr is not None) else "No penetration data recorded"
            if project.get("condition"):
                sub += f" · {project['condition']}"
            story.append(Paragraph(sub, styles["item_subtitle"]))

            param_rows = [
                ["Parameter", "Value", "Unit"],
                ["Moisture content", _fmt(r.get("Moisture (%)"), 2), "%"],
                ["Dry density", _fmt(r.get("Dry density (kg/m3)"), 1), "kg/m³"],
                ["Relative compaction", _fmt(rel_comp, 1), "% MDD"],
                ["CBR @ 2.5 mm", _fmt(res.cbr_2_5, 1) if res else "—", "%"],
                ["CBR @ 5.0 mm", _fmt(res.cbr_5_0, 1) if res else "—", "%"],
                ["Governing CBR", _fmt(res.selected_cbr, 1) if res else "—", "%"],
            ]
            sw = swell.get(lbl) or {}
            swell_pct = None
            if str(project.get("condition") or "").startswith("Soaked") and sw:
                from cbr_engine import swell_percent
                swell_pct = swell_percent(sw.get("init"), sw.get("final"), sw.get("height"))
                param_rows.append(["Swell", _fmt(swell_pct, 2), "%"])
            story.append(_plain_table(param_rows, col_widths=[75 * mm, 55 * mm, 34 * mm], center_cols=(1, 2)))
            story.append(Spacer(1, 10))

            summary, notes = _specimen_interpretation(res, project.get("condition"), rel_comp, swell_pct)
            _interpretation_block(story, styles, f"Specimen {lbl}", summary, notes)
            story.append(PageBreak())

            fig = (figs_pen or {}).get(lbl)
            if fig is not None:
                story.append(Paragraph(f"Load–penetration curve — {lbl}", styles["item_label"]))
                story.append(_fig_to_image(fig))
                story.append(PageBreak())
    else:
        story.append(Paragraph("No CBR compaction / penetration data recorded.", styles["body"]))
        story.append(PageBreak())

    # ---------------- Design CBR: results page ----------------
    story.append(Paragraph("Design CBR Summary", styles["item_label"]))
    if design_df is not None and len(design_df):
        best_row = design_df.iloc[(design_df["Target (% MDD)"] - 95).abs().argsort()[:1]]
        headline = f"{_fmt(best_row['Design CBR (%)'].iloc[0], 1)}% at {best_row['Target (% MDD)'].iloc[0]:.0f}% MDD" if len(best_row) else "—"
        story.append(Paragraph(headline, styles["item_headline"]))
        story.append(Paragraph("Closest design point to 95% MDD, shown for reference", styles["item_subtitle"]))

        header = ["Target (% MDD)", "Design CBR (%)", "Note"]
        body_rows = [[_fmt(r["Target (% MDD)"], 0), _fmt(r["Design CBR (%)"], 1), r.get("Note") or "—"]
                     for _, r in design_df.iterrows()]
        story.append(_plain_table([header] + body_rows, col_widths=[40 * mm, 40 * mm, 84 * mm], center_cols=(0, 1)))
        story.append(Spacer(1, 10))
        summary = (
            "CBR values fitted against relative compaction across the tested specimens (quadratic fit for 3+ "
            "points) and evaluated at each target compaction level — this is the design CBR used for pavement "
            "layer selection."
        )
        notes = []
        if design_df["Note"].astype(str).str.contains("extrapolat").any():
            notes.append("One or more target levels fall outside the tested compaction range and are extrapolated.")
        _interpretation_block(story, styles, None, summary, notes)
        story.append(PageBreak())

        if fig_design is not None:
            story.append(_fig_to_image(fig_design))
            story.append(PageBreak())
    else:
        story.append(Paragraph(
            "Design CBR not available — at least 2 specimens with relative compaction and CBR are needed.",
            styles["body"]))
        story.append(PageBreak())

    # ---------------- Certification ----------------
    story.append(Paragraph("Certification", styles["cert_title"]))
    story.append(Paragraph(
        "This CBR test report has been reviewed and is certified as suitable for the stated project and "
        "engineering requirements. Results assist calculation and curve fitting; they should be reviewed by a "
        "qualified geotechnical engineer before use in pavement design.", styles["body"],
    ))
    story.append(Spacer(1, 10 * mm))
    cert_rows = [
        ["Engineer Name:", ""],
        ["Date:", datetime.now().strftime("%Y-%m-%d")],
    ]
    cert_tbl = Table(cert_rows, colWidths=[35 * mm, 110 * mm], rowHeights=[10 * mm, 10 * mm])
    cert_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW", (1, 0), (1, -1), 0.75, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(cert_tbl)
    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph("Signature / Stamp", ParagraphStyle("sig", parent=styles["sub_header"], spaceBefore=0)))
    story.append(Spacer(1, 2 * mm))
    box = Table([[""]], colWidths=[65 * mm], rowHeights=[26 * mm])
    box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.75, LINE)]))
    story.append(box)
    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph(
        f"Report prepared using {APP_NAME} by {COMPANY_NAME}. "
        f"© {datetime.now().year} {APP_NAME} | {APP_TAGLINE}",
        styles["italic_left"],
    ))

    doc.build(story, canvasmaker=_make_footer_canvas())
    buf.seek(0)
    return buf.getvalue()
