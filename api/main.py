"""
Venus OEV Analytics API — FastAPI application.

Endpoints expose aggregated OEV liquidation statistics for Venus Protocol on BNB Smart Chain,
computed from Dune Analytics queries 6702800 and 6715606.

All responses are served from an in-memory cache that refreshes every 6 hours.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Venus OEV Analytics API",
    version="1.0.0",
    description=(
        "Aggregated OEV liquidation statistics for Venus Protocol on BNB Smart Chain. "
        "Data sourced from Dune Analytics (queries 6702800 and 6715606) and cached in memory, "
        "refreshed every 6 hours."
    ),
)


@app.on_event("startup")
def startup() -> None:
    api_key = os.environ.get("DUNE_API_KEY")
    if not api_key:
        raise RuntimeError("DUNE_API_KEY environment variable is not set")
    scheduler.start_scheduler(api_key)


def _require_cache() -> dict:
    cache = scheduler.get_cache()
    if not cache:
        raise HTTPException(
            status_code=503,
            detail="Cache is not yet populated — the service is still loading data from Dune. Retry in a moment.",
        )
    return cache


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", summary="Health check")
def health() -> JSONResponse:
    """Returns service status and the timestamp of the last successful cache refresh."""
    cache = scheduler.get_cache()
    return JSONResponse({
        "status": "ok",
        "last_refreshed": cache.get("last_refreshed"),
        "dune_execution_time": cache.get("dune_execution_time"),
    })


@app.get("/metrics/summary", summary="Summary metrics")
def summary() -> JSONResponse:
    """
    Dollar-weighted OEV/collateral ratio, recapture efficiency, and
    aggregate liquidation statistics for RedStone on Venus Protocol.

    Key fields:
    - `oev_recapture_ratio_dollar_weighted_pct`: weighted average of OEV bid / collateral seized (%)
    - `oev_recapture_efficiency_pct`: share of the recapturable bonus bid back via OEV (%)
    - `total_liquidation_count`: number of RedStone liquidations with collateral > $1
    - `total_collateral_seized_usd`: total collateral seized across all RedStone liquidations
    - `total_oev_recaptured_usd`: total OEV bids paid back to the protocol
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "data": cache["summary"],
    })


@app.get("/metrics/coverage", summary="OEV coverage metrics")
def coverage() -> JSONResponse:
    """
    Coverage rates measuring what share of eligible liquidation opportunities
    were captured via the OEV channel.

    An eligible liquidation is one where the likely triggering asset is priced via a
    RedStone OEV-enabled vToken and collateral seized exceeded $0.50.

    Key fields:
    - `coverage_by_count_pct`: % of eligible liquidations (by count) captured via OEV
    - `coverage_dollar_weighted_pct`: % of eligible collateral USD captured via OEV
    - `eligible_count` / `eligible_usd`: total eligible liquidations and collateral
    - `captured_count` / `captured_usd`: liquidations captured via OEV
    - `missed_count` / `missed_usd`: eligible liquidations that bypassed OEV
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "data": cache["coverage"],
    })


@app.get("/metrics/daily", summary="Daily OEV fees time series")
def daily() -> JSONResponse:
    """
    Total OEV bids paid by searchers per day — the portion of the liquidation bonus
    returned to the protocol through the OEV auction.

    Returns a list of `{date, oev_bid_usd}` objects sorted chronologically.
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "data": cache["daily"],
    })


@app.get("/metrics/collateral-by-token", summary="Collateral seized by vToken")
def collateral_by_token() -> JSONResponse:
    """
    Total collateral seized broken down by vToken symbol, for all RedStone liquidations.
    Only tokens with total collateral seized >= $5 are included.

    Returns a list of `{token, coll_seized_usd}` objects sorted by value descending.
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "data": cache["collateral_by_token"],
    })
