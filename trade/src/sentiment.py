"""
FinBERT Sentiment Scoring
=========================
Fetches financial news headlines via yfinance and scores them with
ProsusAI/finbert to produce daily per-ticker sentiment features:

- ``sentiment_positive_score`` — mean confidence of positive headlines
- ``sentiment_negative_score`` — mean confidence of negative headlines
- ``sentiment_net_score``      — positive minus negative (net daily sentiment)

Missing days (no news) are filled with 0 (neutral).
"""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from src.config import CFG
from src.utils import get_logger

log = get_logger("sentiment")

# Lazy-loaded globals (heavy imports — only load when needed)
_tokenizer = None
_model = None


def _load_finbert() -> Tuple:
    """Lazy-load ProsusAI/finbert model and tokenizer."""
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    log.info("Loading ProsusAI/finbert model (first call — may take a moment) ...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        _model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        _model.eval()  # inference mode

    log.info("FinBERT model loaded.")
    return _tokenizer, _model


def _score_headlines(headlines: List[str]) -> Dict[str, float]:
    """
    Score a batch of headlines with FinBERT.

    Returns
    -------
    dict with keys ``positive``, ``negative``, ``neutral`` —
    each the mean confidence across all headlines for that class.
    """
    if not headlines:
        return {"positive": 0.0, "negative": 0.0, "neutral": 0.0}

    import torch
    from torch.nn.functional import softmax

    tokenizer, model = _load_finbert()

    # FinBERT labels: 0=positive, 1=negative, 2=neutral
    pos_scores, neg_scores, neu_scores = [], [], []

    # Process in small batches to avoid OOM
    batch_size = 16
    for i in range(0, len(headlines), batch_size):
        batch = headlines[i : i + batch_size]
        inputs = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
            probs = softmax(outputs.logits, dim=1)

        pos_scores.extend(probs[:, 0].tolist())
        neg_scores.extend(probs[:, 1].tolist())
        neu_scores.extend(probs[:, 2].tolist())

    return {
        "positive": float(np.mean(pos_scores)),
        "negative": float(np.mean(neg_scores)),
        "neutral": float(np.mean(neu_scores)),
    }


def fetch_news_yfinance(ticker: str) -> List[Dict]:
    """
    Fetch news articles for *ticker* via yfinance.

    Returns a list of dicts with keys: ``title``, ``published``.
    yfinance typically returns ~8-20 recent articles (last 1-2 weeks).
    """
    try:
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return []

        articles = []
        for item in news:
            # yfinance >= 1.0 wraps news in {"id": ..., "content": {...}}
            content = item.get("content", item)

            title = content.get("title", "")
            # pubDate is ISO string like "2026-03-15T12:30:27Z"
            pub_date_str = content.get("pubDate") or content.get("displayTime")
            if pub_date_str and isinstance(pub_date_str, str):
                pub_date = pub_date_str[:10]
            else:
                # Legacy format: providerPublishTime as unix timestamp
                pub_ts = item.get("providerPublishTime")
                if pub_ts and isinstance(pub_ts, (int, float)):
                    pub_date = datetime.utcfromtimestamp(pub_ts).strftime("%Y-%m-%d")
                else:
                    pub_date = datetime.utcnow().strftime("%Y-%m-%d")

            if title:
                articles.append({"title": title, "published": pub_date})
        return articles
    except Exception as exc:
        log.warning("Failed to fetch news for %s: %s", ticker, exc)
        return []


def score_ticker_sentiment(ticker: str) -> pd.DataFrame:
    """
    Fetch news for *ticker* and return a DataFrame with daily sentiment scores.

    Returns
    -------
    pd.DataFrame
        Columns: ``date``, ``ticker``, ``sentiment_positive_score``,
        ``sentiment_negative_score``, ``sentiment_net_score``,
        ``headline_count``.
    """
    articles = fetch_news_yfinance(ticker)
    if not articles:
        log.info("  %s: 0 articles found — will fill with neutral.", ticker)
        return pd.DataFrame()

    # Group headlines by date
    by_date: Dict[str, List[str]] = {}
    for art in articles:
        d = art["published"]
        by_date.setdefault(d, []).append(art["title"])

    records = []
    for date_str, headlines in sorted(by_date.items()):
        scores = _score_headlines(headlines)
        records.append({
            "date": date_str,
            "ticker": ticker,
            "sentiment_positive_score": scores["positive"],
            "sentiment_negative_score": scores["negative"],
            "sentiment_net_score": scores["positive"] - scores["negative"],
            "headline_count": len(headlines),
        })

    log.info(
        "  %s: %d articles across %d days (avg %.1f/day)",
        ticker,
        len(articles),
        len(records),
        len(articles) / max(len(records), 1),
    )

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_all_sentiment(tickers: List[str] | None = None) -> pd.DataFrame:
    """
    Fetch and score sentiment for all tickers.

    Returns a combined DataFrame with daily sentiment per ticker.
    """
    if tickers is None:
        tickers = CFG.tickers

    log.info("Fetching FinBERT sentiment for %d tickers ...", len(tickers))
    frames = []
    ticker_stats = {}
    for ticker in tickers:
        df = score_ticker_sentiment(ticker)
        if not df.empty:
            frames.append(df)
            ticker_stats[ticker] = {
                "days": len(df),
                "total_headlines": int(df["headline_count"].sum()),
            }
        else:
            ticker_stats[ticker] = {"days": 0, "total_headlines": 0}

    # Log summary
    log.info("Sentiment coverage summary:")
    for t, stats in sorted(ticker_stats.items()):
        log.info(
            "  %-6s  %2d days  %3d headlines",
            t, stats["days"], stats["total_headlines"],
        )

    if not frames:
        log.warning("No sentiment data collected for any ticker.")
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)
