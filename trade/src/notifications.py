"""
Telegram Notifications
======================
Lightweight helpers that send messages to a Telegram chat via the Bot API.
Every function is fail-safe — network or config errors are logged but never
crash the pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List

import requests

from src.config import CFG
from src.utils import get_logger

log = get_logger("notifications")

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
_NAXISTANT_FOOTER = (
    "\n\n\u2014\n"
    "This is an automated notification from Naxistant. "
    "Naxistant cannot respond to these updates yet \u2014 coming in a future update."
)


# ---------------------------------------------------------------------------
# Core send
# ---------------------------------------------------------------------------

def _send_message(text: str) -> None:
    """Post *text* to the configured Telegram chat.  Silently no-ops when
    credentials are missing or the request fails."""
    token = CFG.telegram_bot_token
    chat_id = CFG.telegram_chat_id
    if not token or not chat_id:
        log.debug("Telegram not configured — skipping notification.")
        return

    try:
        resp = requests.post(
            _TELEGRAM_URL.format(token=token),
            json={"chat_id": chat_id, "text": text + _NAXISTANT_FOOTER, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not resp.ok:
            log.warning("Telegram API %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        log.warning("Telegram send failed: %s", exc)


# ---------------------------------------------------------------------------
# High-level notification helpers
# ---------------------------------------------------------------------------

def notify_pipeline_start(phases: str) -> None:
    """Notify that the pipeline is starting."""
    _send_message(f"🚀 *Trade-Bot* starting — {phases}")


def notify_pipeline_complete(phases: str) -> None:
    """Notify that the pipeline finished successfully."""
    _send_message(f"✅ *Trade-Bot* completed — {phases}")


def notify_signals(signals: List[Dict[str, Any]]) -> None:
    """Send a summary of today's ranked signals after Phase 4."""
    if not signals:
        return
    lines = ["📊 *Daily Signals*"]
    for s in signals:
        emoji = {"BUY": "🟢", "SELL": "🔴"}.get(s["signal"], "⚪")
        lines.append(
            f"  {emoji} {s['ticker']}  {s['signal']}  "
            f"prob={s['prob_up']:.2%}  close=${s['close']:.2f}"
        )
    _send_message("\n".join(lines))


def notify_trade(action: str, ticker: str, qty: int, price: float) -> None:
    """Alert after a trade order is submitted."""
    _send_message(
        f"💰 *{action}* {ticker} x{qty} @ ~${price:.2f}"
    )


def notify_position_exit(
    ticker: str, qty: int, entry_price: float, exit_price: float, reason: str,
) -> None:
    """Alert after a position is closed."""
    pnl_pct = (exit_price - entry_price) / entry_price
    emoji = "📈" if pnl_pct >= 0 else "📉"
    _send_message(
        f"{emoji} *Closed* {ticker} x{qty}  "
        f"entry=${entry_price:.2f} → exit=${exit_price:.2f}  "
        f"({pnl_pct:+.2%})  reason: {reason}"
    )


def notify_no_trade(reason: str) -> None:
    """Alert when no trades are executed."""
    _send_message(f"💤 *No trade today* — {reason}")


def notify_portfolio_summary(summary: dict) -> None:
    """Send an end-of-run portfolio summary to Telegram."""
    equity = summary["equity"]
    cash = summary["cash"]
    daily_pnl = summary["daily_pnl"]
    daily_pct = summary["daily_pct"]
    overall_pnl = summary["overall_pnl"]
    overall_pct = summary["overall_pct"]

    d_sign = "+" if daily_pnl >= 0 else ""
    o_sign = "+" if overall_pnl >= 0 else ""
    d_emoji = "\U0001f4c8" if daily_pnl >= 0 else "\U0001f4c9"
    o_emoji = "\U0001f4c8" if overall_pnl >= 0 else "\U0001f4c9"

    lines = [
        "\U0001f4ca *Portfolio Summary*",
        "",
        f"\U0001f4b0 *Equity:* ${equity:,.2f}",
        f"{d_emoji} *Daily:* {d_sign}${daily_pnl:,.2f} ({d_sign}{daily_pct:.2f}%)",
        f"{o_emoji} *Overall:* {o_sign}${overall_pnl:,.2f} ({o_sign}{overall_pct:.2f}%)",
    ]

    # Positions
    positions = summary.get("positions", [])
    if positions:
        lines.append("")
        lines.append(f"*Positions ({len(positions)})*")
        for p in positions:
            sign = "+" if p["pnl_pct"] >= 0 else ""
            lines.append(
                f"  {p['ticker']}"
                f"  {p['qty']} x ${p['current_price']:,.2f}"
                f" = ${p['market_value']:,.2f}"
                f"  {sign}{p['pnl_pct']:.1f}%"
            )
    else:
        lines.append("")
        lines.append("*Positions:* none")

    lines.append("")
    lines.append(f"\U0001f4b5 *Cash:* ${cash:,.2f}")

    _send_message("\n".join(lines))


def notify_feedback(result: dict) -> None:
    """Send prediction accuracy feedback to Telegram."""
    signal_date = result["signal_date"]
    total = result["total"]
    correct = result["correct"]
    accuracy = result["accuracy"]
    emoji = "\U0001f3af" if accuracy >= 0.6 else "\U0001f914"
    _send_message(
        f"{emoji} *Prediction Feedback* ({signal_date})\n"
        f"Accuracy: {correct}/{total} ({accuracy:.1%})\n"
        f"Horizon: {result.get('horizon', 5)} days"
    )


def notify_weekly_summary() -> None:
    """Send a post-retrain weekly summary to Telegram.

    Includes CV metrics, week's signal distribution, trade count,
    circuit breaker status, and any abnormality flags.
    """
    import json
    from datetime import date, timedelta

    lines = ["📋 *Weekly Trade-Bot Summary*", ""]

    # CV metrics from latest retrain
    metrics_path = CFG.model_dir / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path) as f:
            m = json.load(f)
        acc = m["accuracy"]["mean"] * 100
        auc = m["roc_auc"]["mean"] * 100
        f1 = m["f1"]["mean"] * 100
        fold_accs = [round(v * 100, 1) for v in m["accuracy"]["values"]]
        lines.append(f"*Model (retrained today)*")
        lines.append(f"  Accuracy: {acc:.1f}%  AUC: {auc:.1f}%  F1: {f1:.1f}%")
        lines.append(f"  Folds: {fold_accs}")

    # Feature count
    fn_path = CFG.model_dir / "feature_names.json"
    if fn_path.exists():
        with open(fn_path) as f:
            feat_names = json.load(f)
        lines.append(f"  Features: {len(feat_names)}")
    lines.append("")

    # Signal distribution for past 7 days
    today = date.today()
    week_start = today - timedelta(days=7)
    buys, sells, holds = 0, 0, 0
    signal_days = 0
    for i in range(7):
        d = (week_start + timedelta(days=i)).isoformat()
        sig_path = CFG.output_dir / f"signals_{d}.json"
        if sig_path.exists():
            signal_days += 1
            with open(sig_path) as f:
                sigs = json.load(f)
            for s in sigs:
                sig = s.get("signal", "HOLD")
                if sig == "BUY":
                    buys += 1
                elif sig == "SELL":
                    sells += 1
                else:
                    holds += 1

    lines.append(f"*Signals (past 7 days, {signal_days} trading days)*")
    lines.append(f"  BUY: {buys}  SELL: {sells}  HOLD: {holds}")
    total_dir = buys + sells
    lines.append(f"  Directional: {total_dir}")
    lines.append("")

    # Trade count (open positions)
    pos_path = CFG.output_dir / "open_positions.json"
    if pos_path.exists():
        with open(pos_path) as f:
            positions = json.load(f)
        lines.append(f"*Open positions:* {len(positions)}")
    else:
        lines.append("*Open positions:* 0")

    # Circuit breaker
    halt_path = CFG.output_dir / "drawdown_halt.json"
    if halt_path.exists():
        with open(halt_path) as f:
            halt = json.load(f)
        halt_until = halt.get("halt_until")
        if halt_until:
            lines.append(f"⚠️ *Circuit breaker ACTIVE* until {halt_until}")
        else:
            lines.append("Circuit breaker: clear")
    lines.append("")

    # Feedback accuracy (recent entries)
    fb_path = CFG.output_dir / "feedback_history.json"
    if fb_path.exists():
        with open(fb_path) as f:
            fb = json.load(f)
        # Entries from the last 2 weeks
        recent = [e for e in fb if e.get("signal_date", "") >= (today - timedelta(days=14)).isoformat()]
        if recent:
            lines.append(f"*Recent feedback ({len(recent)} evals)*")
            for e in recent[-3:]:
                da = e.get("directional_accuracy")
                dt = e.get("directional_total", 0)
                da_str = f"{da:.0%}" if da is not None else "N/A"
                lines.append(f"  {e['signal_date']}: dir_acc={da_str} ({dt} trades)")
        else:
            lines.append("*Feedback:* no recent evaluations")
    lines.append("")

    # Abnormality flags
    flags = []
    if metrics_path.exists():
        last_fold = m["accuracy"]["values"][-1]
        if last_fold < 0.50:
            flags.append(f"Fold 5 accuracy below 50% ({last_fold*100:.1f}%)")
    if total_dir == 0 and signal_days >= 3:
        flags.append("Zero directional signals all week")

    if flags:
        lines.append("🚩 *Flags*")
        for flag in flags:
            lines.append(f"  - {flag}")
    else:
        lines.append("✅ No abnormalities detected")

    _send_message("\n".join(lines))


def notify_error(phase: str, error_msg: str) -> None:
    """Alert on pipeline error."""
    _send_message(f"❌ *Error in {phase}*\n```\n{error_msg}\n```")
