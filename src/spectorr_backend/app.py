# src/spectorr_backend/app.py
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# --- App setup -------------------------------------------------------------

app = FastAPI(title="Spectorr Backend", version="0.1.0")

# (Keep permissive in dev; restrict origins for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional demo routes (SSE + mockgen). Comment out if not using yet.
try:
    from spectorr_backend.routes.demo import (
        router as demo_router,  # correct package path
    )

    app.include_router(demo_router)
except Exception:
    # Safe to ignore if you haven't added routes/demo.py yet
    pass

# --- Paths / env -----------------------------------------------------------

# Use one canonical env var across backend & pipeline
DATA_ROOT = Path(
    os.getenv("SPECTORR_DATA_ROOT", "~/Documents/Projects/spectorr/spectorr-data")
).expanduser()
CURATED = DATA_ROOT / "curated"
CSV = CURATED / "cleaned.csv"
INSIGHTS = CURATED / "insights.json"

# --- Routes: aggregated sentiment from cleaned.csv ------------------------


@app.get("/portfolio/sentiment")
def portfolio_sentiment(
    limit: int = Query(500, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
):
    """
    Returns daily average sentiment per asset from curated/cleaned.csv
    Shape: [{"asset_id": "...", "date": "YYYY-MM-DD", "sentiment_score": float}, ...]
    """
    if not CSV.exists():
        raise HTTPException(404, detail="curated file missing (cleaned.csv)")
    df = pd.read_csv(CSV, parse_dates=["source_date"])
    agg = (
        df.assign(date=df["source_date"].dt.date.astype(str))
        .groupby(["asset_id", "date"], as_index=False)["sentiment_score"]
        .mean()
        .sort_values(["date", "asset_id"])
    )
    records = agg.to_dict(orient="records")
    return {"count": len(records), "items": records[offset : offset + limit]}


@app.get("/assets/{asset_id}/daily")
def asset_daily(asset_id: str):
    """
    Returns daily average sentiment for a single asset from curated/cleaned.csv
    Shape: {"asset_id": "...", "records": [{"date": "...","sentiment_score": float}, ...]}
    """
    if not CSV.exists():
        raise HTTPException(404, detail="curated file missing (cleaned.csv)")
    df = pd.read_csv(CSV, parse_dates=["source_date"])
    df = df[df["asset_id"] == asset_id]
    if df.empty:
        return {"asset_id": asset_id, "records": []}
    agg = (
        df.assign(date=df["source_date"].dt.date.astype(str))
        .groupby("date", as_index=False)["sentiment_score"]
        .mean()
        .sort_values("date")
    )
    return {"asset_id": asset_id, "records": agg.to_dict(orient="records")}


# --- Routes: model insights from insights.json ----------------------------


@app.get("/portfolio/insights")
def portfolio_insights(
    asset_id: str | None = Query(None),
    date: str | None = Query(None),  # "YYYY-MM-DD"
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Returns LLM-generated daily insights per asset from curated/insights.json
    Shape: {"count": int, "items": [ { asset_id, date, avg_sentiment, n, insight: {...} }, ... ]}
    """
    if not INSIGHTS.exists():
        raise HTTPException(404, detail="insights.json not found – run pipeline first")

    try:
        items = json.loads(INSIGHTS.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, detail=f"failed to read insights.json: {e}")

    # lightweight filtering
    if asset_id:
        items = [it for it in items if it.get("asset_id") == asset_id]
    if date:
        items = [it for it in items if it.get("date") == date]

    # stable ordering: newest first, then asset_id
    items.sort(key=lambda x: (x.get("date", ""), x.get("asset_id", "")), reverse=True)

    total = len(items)
    return {"count": total, "items": items[offset : offset + limit]}
