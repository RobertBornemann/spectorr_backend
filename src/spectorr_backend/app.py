# src/spectorr_backend/app.py (extend)
import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Spectorr Backend", version="0.1.0")
CURATED = Path(
    os.getenv(
        "SPECTORR_CURATED",
        os.getenv("SPECTORR_DATA", "~/Documents/Projects/spectorr/spectorr-data") + "/curated",
    )
).expanduser()
CSV = CURATED / "cleaned.csv"


@app.get("/portfolio/sentiment")
def portfolio_sentiment():
    if not CSV.exists():
        raise HTTPException(404, detail="curated file missing")
    df = pd.read_csv(CSV, parse_dates=["source_date"])
    agg = (
        df.assign(date=df["source_date"].astype(str))
        .groupby(["asset_id", "date"], as_index=False)["sentiment_score"]
        .mean()
    )
    return {"records": agg.to_dict(orient="records")}


@app.get("/assets/{asset_id}/daily")
def asset_daily(asset_id: str):
    if not CSV.exists():
        raise HTTPException(404, detail="curated file missing")
    df = pd.read_csv(CSV, parse_dates=["source_date"])
    df = df[df["asset_id"] == asset_id]
    if df.empty:
        return {"records": []}
    agg = (
        df.assign(date=df["source_date"].astype(str))
        .groupby("date", as_index=False)["sentiment_score"]
        .mean()
    )
    return {"asset_id": asset_id, "records": agg.to_dict(orient="records")}
