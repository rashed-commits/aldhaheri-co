"""
PDF Report Generator
====================
Produces a compact, table-based daily PDF report of top-scored listings.
Uses reportlab. Landscape A4 for maximum column density.

Public interface:
  generate_report(scored_listings, output_path) → Path
"""

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from config import SCORING
from utils.logger import get_logger

log = get_logger()

# ─── Colour palette ─────────────────────────────────────────────────────
_DARK = colors.HexColor("#1a1a2e")
_ACCENT = colors.HexColor("#16213e")
_GREEN = colors.HexColor("#2d6a4f")
_AMBER = colors.HexColor("#e76f51")
_LIGHT_BG = colors.HexColor("#f8f9fa")
_HEADER_BG = colors.HexColor("#16213e")
_BORDER = colors.HexColor("#dee2e6")
_WHITE = colors.white
_LINK_BLUE = colors.HexColor("#0d6efd")
_MUTED = colors.HexColor("#6c757d")


def _build_styles():
    """Custom paragraph styles for the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"],
            fontSize=18, leading=22, textColor=_DARK,
            spaceAfter=2, fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", parent=base["Normal"],
            fontSize=10, leading=13, textColor=_MUTED,
            spaceAfter=10, fontName="Helvetica",
        ),
        "section": ParagraphStyle(
            "SectionHead", parent=base["Heading2"],
            fontSize=12, leading=15, textColor=_ACCENT,
            spaceBefore=10, spaceAfter=6, fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=9, leading=12, textColor=colors.HexColor("#212529"),
            fontName="Helvetica",
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"],
            fontSize=7.5, leading=9, textColor=_MUTED,
            fontName="Helvetica",
        ),
        # Styles used inside table cells (must be tiny to fit)
        "cell": ParagraphStyle(
            "Cell", parent=base["Normal"],
            fontSize=7.5, leading=9.5, textColor=_DARK,
            fontName="Helvetica",
        ),
        "cell_bold": ParagraphStyle(
            "CellBold", parent=base["Normal"],
            fontSize=7.5, leading=9.5, textColor=_DARK,
            fontName="Helvetica-Bold",
        ),
        "cell_link": ParagraphStyle(
            "CellLink", parent=base["Normal"],
            fontSize=6.5, leading=8, textColor=_LINK_BLUE,
            fontName="Helvetica",
        ),
        "cell_green": ParagraphStyle(
            "CellGreen", parent=base["Normal"],
            fontSize=8, leading=10, textColor=_GREEN,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "cell_amber": ParagraphStyle(
            "CellAmber", parent=base["Normal"],
            fontSize=8, leading=10, textColor=_AMBER,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "cell_center": ParagraphStyle(
            "CellCenter", parent=base["Normal"],
            fontSize=7.5, leading=9.5, textColor=_DARK,
            fontName="Helvetica", alignment=TA_CENTER,
        ),
        "cell_right": ParagraphStyle(
            "CellRight", parent=base["Normal"],
            fontSize=7.5, leading=9.5, textColor=_DARK,
            fontName="Helvetica", alignment=TA_RIGHT,
        ),
        "header_cell": ParagraphStyle(
            "HeaderCell", parent=base["Normal"],
            fontSize=7, leading=9, textColor=_WHITE,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        ),
        "header_cell_left": ParagraphStyle(
            "HeaderCellLeft", parent=base["Normal"],
            fontSize=7, leading=9, textColor=_WHITE,
            fontName="Helvetica-Bold",
        ),
    }


def _fmt_price(price) -> str:
    if not price:
        return "—"
    if price >= 1_000_000:
        return f"{price / 1_000_000:,.2f}M"
    elif price >= 1_000:
        return f"{price / 1_000:,.0f}K"
    return f"{price:,.0f}"


def _fmt_pct(val, plus=False) -> str:
    if not val:
        return "—"
    fmt = f"{val:+.1f}%" if plus else f"{val:.1f}%"
    return fmt


def _build_main_table(scored_listings: list[dict], styles: dict) -> Table:
    """Build the core data table with all listings as rows."""

    # Column headers
    headers = [
        Paragraph("#", styles["header_cell"]),
        Paragraph("Listing", styles["header_cell_left"]),
        Paragraph("Area", styles["header_cell_left"]),
        Paragraph("Type", styles["header_cell"]),
        Paragraph("Beds", styles["header_cell"]),
        Paragraph("Price (AED)", styles["header_cell"]),
        Paragraph("Size<br/>(sqft)", styles["header_cell"]),
        Paragraph("AED/<br/>sqft", styles["header_cell"]),
        Paragraph("Area<br/>Avg", styles["header_cell"]),
        Paragraph("Disc.", styles["header_cell"]),
        Paragraph("Yield", styles["header_cell"]),
        Paragraph("Rent/yr<br/>(AED)", styles["header_cell"]),
        Paragraph("Drop", styles["header_cell"]),
        Paragraph("Score", styles["header_cell"]),
    ]

    data = [headers]

    for i, entry in enumerate(scored_listings, 1):
        l = entry["listing"]
        bd = entry["breakdown"]
        score = entry["composite_score"]

        city_short = "AD" if l.get("city") == "abu-dhabi" else "DXB"
        area = l.get("area_name", "")
        beds = l.get("bedrooms")
        beds_str = str(beds) if beds is not None else "—"
        ptype = (l.get("property_type") or "—").title()
        if len(ptype) > 5:
            ptype = ptype[:4] + "."
        offplan = " ★" if l.get("is_offplan") else ""

        # Truncate title and make it a link
        title = (l.get("title") or "Untitled")
        if len(title) > 35:
            title = title[:33] + "…"
        url = l.get("url", "")
        if url:
            title_cell = Paragraph(f'<a href="{url}" color="#0d6efd">{title}</a>', styles["cell"])
        else:
            title_cell = Paragraph(title, styles["cell"])

        # Truncate area name
        area_display = area
        if len(area_display) > 18:
            area_display = area_display[:16] + "…"
        area_cell = Paragraph(f"{area_display}<br/><font size='6' color='#6c757d'>{city_short}{offplan}</font>", styles["cell"])

        price = _fmt_price(l.get("price"))
        sqft = f"{l.get('area_sqft'):,.0f}" if l.get("area_sqft") else "—"
        psf = f"{bd['price_below_avg'].get('listing_psf', 0):,.0f}" if bd["price_below_avg"].get("listing_psf") else "—"
        avg_psf = f"{bd['price_below_avg'].get('area_avg_psf', 0):,.0f}" if bd["price_below_avg"].get("area_avg_psf") else "—"

        discount = bd["price_below_avg"].get("discount_pct", 0)
        disc_str = _fmt_pct(discount, plus=True) if discount else "—"

        yield_pct = bd["rental_yield"].get("gross_yield_pct", 0)
        yield_str = _fmt_pct(yield_pct) if yield_pct else "—"

        est_rent = _fmt_price(bd["rental_yield"].get("estimated_annual_rent"))

        drop = bd["price_drop"].get("drop_pct", 0)
        drop_str = f"↓{drop:.1f}%" if drop > 0 else "—"

        # Score cell with color
        score_style = styles["cell_green"] if score >= 60 else styles["cell_amber"]
        score_cell = Paragraph(f"{score:.0f}", score_style)

        row = [
            Paragraph(f"<b>{i}</b>", styles["cell_center"]),
            title_cell,
            area_cell,
            Paragraph(ptype, styles["cell_center"]),
            Paragraph(beds_str, styles["cell_center"]),
            Paragraph(price, styles["cell_right"]),
            Paragraph(sqft, styles["cell_right"]),
            Paragraph(psf, styles["cell_right"]),
            Paragraph(avg_psf, styles["cell_right"]),
            Paragraph(disc_str, styles["cell_center"]),
            Paragraph(yield_str, styles["cell_center"]),
            Paragraph(est_rent, styles["cell_right"]),
            Paragraph(drop_str, styles["cell_center"]),
            score_cell,
        ]
        data.append(row)

    # Column widths — landscape A4 usable width = 277mm (297 - 10 - 10)
    col_widths = [
        10 * mm,   # #
        55 * mm,   # Listing (title)
        32 * mm,   # Area
        14 * mm,   # Type
        12 * mm,   # Beds
        24 * mm,   # Price
        16 * mm,   # Size
        16 * mm,   # AED/sqft
        16 * mm,   # Area Avg
        14 * mm,   # Disc.
        14 * mm,   # Yield
        20 * mm,   # Rent/yr
        14 * mm,   # Drop
        20 * mm,   # Score
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Build style commands
    style_cmds = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),

        # All cells
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),

        # Grid
        ("LINEBELOW", (0, 0), (-1, 0), 1, _ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, _BORDER),
        ("LINEBEFORE", (0, 0), (0, -1), 0.5, _BORDER),
        ("LINEAFTER", (-1, 0), (-1, -1), 0.5, _BORDER),
    ]

    # Alternating row backgrounds
    for row_idx in range(1, len(data)):
        if row_idx % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), _LIGHT_BG))

    table.setStyle(TableStyle(style_cmds))
    return table


def generate_report(
    scored_listings: list[dict] | None = None,
    output_path: str | Path | None = None,
    *,
    split: dict[str, list[dict]] | None = None,
) -> Path:
    """
    Generate a compact table-based PDF report.

    Two calling modes:
      1. generate_report(scored_listings)          — single table (legacy)
      2. generate_report(split={"offplan": [...], "secondary": [...]})  — two tables
    Returns the path to the generated PDF.
    """
    from config import PROJECT_ROOT

    if output_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = PROJECT_ROOT / "reports" / f"opportunity_report_{ts}.pdf"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = _build_styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=landscape(A4),
        topMargin=12 * mm,
        bottomMargin=10 * mm,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        title="UAE Real Estate — Daily Opportunity Report",
        author="Perplexity Computer",
    )

    elements = []
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %d, %Y")

    # Determine sections to render
    if split is not None:
        sections = [
            ("★  Top Off-Plan Opportunities", split.get("offplan", [])),
            ("Top Secondary / Ready Opportunities", split.get("secondary", [])),
        ]
        all_listings = split.get("offplan", []) + split.get("secondary", [])
    else:
        sections = [("Top Opportunities", scored_listings or [])]
        all_listings = scored_listings or []

    total_count = len(all_listings)

    # ── Header ────────────────────────────────────────────────────────────
    elements.append(Paragraph("UAE Real Estate — Daily Opportunity Report", styles["title"]))
    elements.append(Paragraph(date_str, styles["subtitle"]))

    # ── Summary stats row ─────────────────────────────────────────────────
    if total_count > 0:
        top_score = max(s["composite_score"] for s in all_listings)
        avg_score = sum(s["composite_score"] for s in all_listings) / total_count
        cities = set(s["listing"]["city"] for s in all_listings)
        areas = set(s["listing"]["area_name"] for s in all_listings)

        if split is not None:
            count_label = f"{len(split.get('offplan',[]))} off-plan  +  {len(split.get('secondary',[]))} secondary"
        else:
            count_label = str(total_count)

        summary_data = [
            ["Listings", "Top Score", "Avg Score", "Cities", "Areas", "Scoring Weights"],
            [
                count_label, f"{top_score:.0f}", f"{avg_score:.0f}",
                str(len(cities)), str(len(areas)),
                "Yield 40%  ·  Discount 25%  ·  Drop 20%  ·  Off-plan 15%",
            ],
        ]
        summary_table = Table(summary_data, colWidths=[42 * mm, 24 * mm, 24 * mm, 20 * mm, 20 * mm, 100 * mm])
        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), _MUTED),
            ("TEXTCOLOR", (0, 1), (-1, 1), _DARK),
            ("ALIGN", (0, 0), (4, -1), "CENTER"),
            ("ALIGN", (5, 0), (5, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_BG),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, _BORDER),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ]))
        elements.append(summary_table)
    else:
        elements.append(Paragraph("No listings met the scoring threshold today.", styles["body"]))

    # ── Section tables ────────────────────────────────────────────────────
    for section_title, section_listings in sections:
        if not section_listings:
            continue
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(section_title, styles["section"]))
        elements.append(Spacer(1, 4))
        elements.append(_build_main_table(section_listings, styles))

    # ── Footer ────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        f"Generated by UAE Real Estate Monitor Bot — {now.strftime('%Y-%m-%d %H:%M UTC')}  "
        f"·  Threshold: {SCORING['alert_threshold']}+  "
        f"·  ★ = Off-plan  ·  AD = Abu Dhabi  ·  DXB = Dubai",
        styles["small"],
    ))

    doc.build(elements)
    log.info("PDF report generated: %s (%d listings)", output_path, total_count)
    return output_path
