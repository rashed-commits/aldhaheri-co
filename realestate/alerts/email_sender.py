"""
Email Sender — Brevo Transactional API
========================================
Sends the daily PDF report as an email with:
  - Polished HTML body with top 5 listings preview
  - PDF attached (base64-encoded)

Uses Brevo's HTTP API (port 443) — works on VPS providers that
block outbound SMTP ports 465/587 (e.g. DigitalOcean).

Setup:
  1. Sign up at https://app.brevo.com
  2. Get your API key at https://app.brevo.com/settings/keys/api
  3. Set environment variable:
       BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxx

Public interface:
  send_report_email(split, pdf_path) → bool
"""

import base64
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from config import EMAIL, SCORING
from utils.logger import get_logger

log = get_logger()


def _build_html_body(scored_listings: list[dict], summary: dict) -> str:
    """Build a polished HTML email body with top 5 listings preview."""
    date_str = summary.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    total_scored = summary.get("total_scored", 0)
    above_threshold = summary.get("above_threshold", 0)
    top_score = summary.get("top_score", 0)
    top_areas = ", ".join(summary.get("top_areas", [])) or "—"
    offplan_count = summary.get("offplan_count", 0)
    secondary_count = summary.get("secondary_count", 0)

    # Build top 5 listing rows
    table_rows = ""
    for entry in scored_listings[:5]:
        l = entry["listing"]
        bd = entry["breakdown"]
        score = entry["composite_score"]

        city = "Abu Dhabi" if l.get("city") == "abu-dhabi" else "Dubai"
        yield_pct = bd["rental_yield"].get("gross_yield_pct", 0)
        yield_str = f"{yield_pct:.1f}%" if yield_pct else "—"
        discount = bd["price_below_avg"].get("discount_pct", 0)
        disc_str = f"{discount:+.1f}%" if discount else "—"
        price = l.get("price", 0)
        if price >= 1_000_000:
            price_str = f"AED {price / 1_000_000:,.2f}M"
        elif price >= 1_000:
            price_str = f"AED {price / 1_000:,.0f}K"
        else:
            price_str = f"AED {price:,.0f}"

        title = (l.get("title") or "Untitled")[:45]
        url = l.get("url", "")
        offplan_badge = ' <span style="color:#e76f51;font-weight:600;">★</span>' if l.get("is_offplan") else ""
        title_html = (
            f'<a href="{url}" style="color:#0d6efd;text-decoration:none;">{title}</a>{offplan_badge}'
            if url
            else f"{title}{offplan_badge}"
        )

        score_color = "#2d6a4f" if score >= 60 else "#e76f51"

        table_rows += f"""<tr style="border-bottom:1px solid #e9ecef;">
            <td style="padding:10px 12px;font-size:13px;">{title_html}</td>
            <td style="padding:10px 8px;font-size:13px;text-align:center;">{city}</td>
            <td style="padding:10px 8px;font-size:13px;text-align:right;">{price_str}</td>
            <td style="padding:10px 8px;font-size:13px;text-align:center;">{yield_str}</td>
            <td style="padding:10px 8px;font-size:13px;text-align:center;">{disc_str}</td>
            <td style="padding:10px 8px;font-size:13px;text-align:center;font-weight:600;color:{score_color};">{score:.0f}</td>
        </tr>"""

    if not table_rows:
        table_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6c757d;">No listings above threshold today</td></tr>'

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:640px;margin:20px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:28px 32px;">
      <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">UAE Real Estate</h1>
      <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:14px;">Daily Opportunity Report &mdash; {date_str}</p>
    </div>

    <!-- Summary Stats -->
    <div style="padding:20px 32px;background:#f8f9fa;border-bottom:1px solid #e9ecef;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="text-align:center;padding:8px;">
            <div style="font-size:24px;font-weight:700;color:#1a1a2e;">{offplan_count} + {secondary_count}</div>
            <div style="font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:0.5px;">Off-plan + Secondary</div>
          </td>
          <td style="text-align:center;padding:8px;">
            <div style="font-size:24px;font-weight:700;color:#2d6a4f;">{top_score:.0f}</div>
            <div style="font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:0.5px;">Top Score</div>
          </td>
          <td style="text-align:center;padding:8px;">
            <div style="font-size:24px;font-weight:700;color:#1a1a2e;">{total_scored:,}</div>
            <div style="font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:0.5px;">Listings Scored</div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Top 5 Listings -->
    <div style="padding:24px 32px;">
      <h2 style="margin:0 0 16px;font-size:16px;color:#1a1a2e;">Top 5 at a Glance</h2>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        <tr style="background:#16213e;">
          <th style="padding:10px 12px;font-size:11px;color:#ffffff;text-align:left;text-transform:uppercase;letter-spacing:0.5px;">Listing</th>
          <th style="padding:10px 8px;font-size:11px;color:#ffffff;text-align:center;text-transform:uppercase;letter-spacing:0.5px;">City</th>
          <th style="padding:10px 8px;font-size:11px;color:#ffffff;text-align:right;text-transform:uppercase;letter-spacing:0.5px;">Price</th>
          <th style="padding:10px 8px;font-size:11px;color:#ffffff;text-align:center;text-transform:uppercase;letter-spacing:0.5px;">Yield</th>
          <th style="padding:10px 8px;font-size:11px;color:#ffffff;text-align:center;text-transform:uppercase;letter-spacing:0.5px;">Disc.</th>
          <th style="padding:10px 8px;font-size:11px;color:#ffffff;text-align:center;text-transform:uppercase;letter-spacing:0.5px;">Score</th>
        </tr>
        {table_rows}
      </table>
    </div>

    <!-- Top Areas -->
    <div style="padding:0 32px 24px;">
      <p style="margin:0;font-size:13px;color:#6c757d;"><strong>Hot areas:</strong> {top_areas}</p>
    </div>

    <!-- CTA -->
    <div style="padding:16px 32px;background:#f8f9fa;border-top:1px solid #e9ecef;text-align:center;">
      <p style="margin:0;font-size:13px;color:#495057;">Full report with {offplan_count + secondary_count} listings attached as PDF &darr;</p>
    </div>

    <!-- Footer -->
    <div style="padding:16px 32px;text-align:center;">
      <p style="margin:0;font-size:11px;color:#adb5bd;">UAE Real Estate Monitor Bot &mdash; Scoring: Yield 40% &middot; Discount 25% &middot; Drop 20% &middot; Off-plan 15%</p>
    </div>
  </div>
</body>
</html>"""


def _build_summary(scored_listings: list[dict], split: dict | None = None) -> dict:
    """Build a summary dict from scored listings."""
    from collections import Counter

    if not scored_listings:
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "total_scored": 0,
            "above_threshold": 0,
            "top_score": 0,
            "top_areas": [],
            "offplan_count": 0,
            "secondary_count": 0,
        }

    threshold = SCORING["alert_threshold"]
    above = [s for s in scored_listings if s["composite_score"] >= threshold]
    area_counts = Counter(s["listing"]["area_name"] for s in above)

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_scored": len(scored_listings),
        "above_threshold": len(above),
        "top_score": above[0]["composite_score"] if above else 0,
        "top_areas": [area for area, _ in area_counts.most_common(5)],
        "offplan_count": len(split.get("offplan", [])) if split else len(above),
        "secondary_count": len(split.get("secondary", [])) if split else 0,
    }


def send_report_email(
    split: dict[str, list[dict]],
    pdf_path: Path | str,
) -> bool:
    """
    Send the daily report email with PDF attachment via Brevo API.

    Args:
        split: {"offplan": [...], "secondary": [...]} scored listings
        pdf_path: Path to the generated PDF report

    Returns:
        True if email sent successfully, False otherwise.
    """
    api_key = EMAIL.get("brevo_api_key", "")
    sender_email = EMAIL.get("sender_email", "")
    sender_name = EMAIL.get("sender_name", "RE Monitor Bot")
    recipient = EMAIL["recipient"]

    if not api_key:
        log.warning(
            "Brevo API key not configured. "
            "Set BREVO_API_KEY environment variable."
        )
        return False

    if not sender_email:
        log.warning(
            "Sender email not configured. "
            "Set SENDER_EMAIL environment variable."
        )
        return False

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        log.error("PDF not found: %s", pdf_path)
        return False

    # Combine listings for summary and preview
    all_listings = split.get("offplan", []) + split.get("secondary", [])
    summary = _build_summary(all_listings, split)
    date_str = summary["date"]

    # Build HTML body
    html = _build_html_body(all_listings, summary)

    # Read and base64-encode the PDF
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("ascii")

    # Build Brevo API payload
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": recipient}],
        "subject": f"UAE Real Estate Report — {date_str}",
        "htmlContent": html,
        "attachment": [
            {
                "content": pdf_b64,
                "name": pdf_path.name,
            }
        ],
    }

    # Send via Brevo Transactional Email API (HTTPS, port 443)
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
            msg_id = body.get("messageId", "unknown")
        log.info("Report email sent to %s via Brevo (messageId: %s, PDF: %s)", recipient, msg_id, pdf_path.name)
        return True
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        log.error("Brevo API error %d: %s", exc.code, error_body)
        return False
    except Exception as exc:
        log.error("Failed to send email via Brevo: %s", exc)
        return False
