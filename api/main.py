"""
Venus OEV Analytics API — FastAPI application (multi-provider branch).

Endpoints expose aggregated OEV liquidation statistics for Venus Protocol on BNB Smart Chain,
computed from Dune Analytics queries 6702800 and 6715606.

Every endpoint returns a "providers" dict containing per-provider data for both
"redstone" and "chainlink". All responses are served from an in-memory cache
that refreshes every 6 hours.
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
    version="2.0.0",
    description=(
        "Aggregated OEV liquidation statistics for Venus Protocol on BNB Smart Chain. "
        "Returns per-provider data for RedStone and Chainlink. "
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


@app.get("/metrics/summary", summary="Summary metrics — all providers")
def summary() -> JSONResponse:
    """
    Dollar-weighted OEV/collateral ratio, recapture efficiency, and aggregate
    liquidation statistics, returned for each provider under a "providers" key.

    Provider keys: "redstone", "chainlink".

    Per-provider fields:
    - `oev_recapture_ratio_dollar_weighted_pct`: weighted average of OEV bid / collateral seized (%)
    - `oev_recapture_efficiency_pct`: share of the recapturable bonus bid back via OEV (%)
    - `total_liquidation_count`: liquidation transactions with collateral > $1
    - `total_collateral_seized_usd`: total collateral seized
    - `total_oev_recaptured_usd`: total OEV bids paid back to the protocol
    - `simulated_gross_liquidation_bonus_usd`, `treasury_fee_usd`, `recapturable_bonus_usd`
    - `realized_lb_pct_without_oev`, `realized_lb_pct_with_oev`
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "providers": cache["summary"],
    })


@app.get("/metrics/coverage", summary="OEV coverage metrics — all providers")
def coverage() -> JSONResponse:
    """
    Coverage rates measuring what share of eligible liquidation opportunities
    were captured via the OEV channel, for each provider.

    An eligible liquidation is one where the likely triggering asset is priced via
    an OEV-enabled vToken for that provider, and collateral seized exceeded $0.50.

    Provider keys: "redstone", "chainlink".

    Per-provider fields:
    - `coverage_by_count_pct`: % of eligible liquidations (by count) captured via OEV
    - `eligible_count`: total eligible liquidations
    - `captured_count`: liquidations captured via OEV
    - `missed_count`: eligible liquidations that bypassed OEV
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "providers": cache["coverage"],
    })


@app.get("/metrics/daily", summary="Daily OEV fees time series — all providers")
def daily() -> JSONResponse:
    """
    Total OEV bids paid by searchers per day, for each provider.

    Provider keys: "redstone", "chainlink".
    Each value is a list of `{date, oev_bid_usd}` objects sorted chronologically.
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "providers": cache["daily"],
    })


@app.get("/metrics/collateral-by-token", summary="Collateral seized by vToken — all providers")
def collateral_by_token() -> JSONResponse:
    """
    Total collateral seized broken down by vToken symbol, for each provider.
    Only tokens with total collateral seized >= $5 are included.

    Provider keys: "redstone", "chainlink".
    Each value is a list of `{token, coll_seized_usd}` objects sorted by value descending.
    """
    cache = _require_cache()
    return JSONResponse({
        "last_refreshed": cache["last_refreshed"],
        "providers": cache["collateral_by_token"],
    })
