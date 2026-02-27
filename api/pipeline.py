"""
Data fetching and aggregation logic for the Venus OEV Analytics API.

Mirrors the computations in venus/app.py without any Streamlit dependency.
Variable names use the updated conventions: liqs / liqs_dedup (not legacy l_2023 / l_dedup).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from dune_client.client import DuneClient

QUERY_LIQUIDATIONS = 6702800
QUERY_COVERAGE = 6715606


# ---------------------------------------------------------------------------
# Raw data fetching
# ---------------------------------------------------------------------------

def fetch_liquidation_data(api_key: str) -> tuple[pd.DataFrame, datetime]:
    """Fetch query 6702800 and return (liqs DataFrame, Dune execution timestamp)."""
    dune = DuneClient(api_key)
    result = dune.get_latest_result(QUERY_LIQUIDATIONS)
    try:
        fetch_time = result.times.execution_ended_at
        if fetch_time.tzinfo is None:
            fetch_time = fetch_time.replace(tzinfo=timezone.utc)
    except AttributeError:
        fetch_time = datetime.now(timezone.utc)
    liqs = pd.DataFrame(result.result.rows)
    liqs["is_primary_row"] = liqs["is_primary_row"].astype(bool)
    return liqs, fetch_time


def fetch_coverage_data(api_key: str) -> pd.DataFrame:
    """Fetch query 6715606 and return oev_cov DataFrame."""
    dune = DuneClient(api_key)
    result = dune.get_latest_result(QUERY_COVERAGE)
    return pd.DataFrame(result.result.rows)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _compute_summary(liqs: pd.DataFrame) -> dict:
    """
    Dollar-weighted OEV/collateral ratio, recapture efficiency, and
    total liquidation count / total collateral seized.

    Mirrors app.py lines 66-82, 146-173, 202-216.
    """
    # One row per tx
    liqs_dedup = liqs[liqs["is_primary_row"]].copy()

    # df_filtered: RedStone only, with a valid ratio (used for dollar-weighted avg)
    df_filtered = liqs_dedup[
        (liqs_dedup["oev_provider"] == "RedStone")
        & (liqs_dedup["oev_to_collateral_ratio"].notna())
    ].copy()

    # Dollar-weighted average OEV/collateral ratio (as %)
    if df_filtered["total_coll_seized_usd"].sum() > 0:
        rs_weighted_avg = (
            (df_filtered["oev_to_collateral_ratio"] * df_filtered["total_coll_seized_usd"]).sum()
            / df_filtered["total_coll_seized_usd"].sum()
            * 100
        )
    else:
        rs_weighted_avg = 0.0

    # Recapture efficiency: uses liqs_dedup filtered to RedStone
    # Note: named-aggregation syntax only works after groupby; use direct series ops here.
    df_oev = liqs_dedup[liqs_dedup["oev_provider"] == "RedStone"].copy()
    oev_liquidation_count = len(df_oev)
    total_collateral_liquidated_usd = float(df_oev["total_coll_seized_usd"].sum())
    total_debt_repaid_usd = float(df_oev["total_debt_repaid_usd"].sum())
    total_oev_usd = float(df_oev["oev_bid_usd"].sum())

    total_actual_bonus_usd = total_collateral_liquidated_usd - total_debt_repaid_usd
    treasury_fee_usd = 0.05 * total_debt_repaid_usd
    recapturable_bonus_usd = total_actual_bonus_usd - treasury_fee_usd
    oev_recapture_pct = (
        total_oev_usd / recapturable_bonus_usd * 100
        if recapturable_bonus_usd > 0
        else 0.0
    )
    realized_lb_pct_without_oev = (
        total_actual_bonus_usd / total_collateral_liquidated_usd * 100
        if total_collateral_liquidated_usd > 0
        else 0.0
    )
    realized_lb_pct_with_oev = (
        (total_actual_bonus_usd - total_oev_usd) / total_collateral_liquidated_usd * 100
        if total_collateral_liquidated_usd > 0
        else 0.0
    )

    # Total RS collateral (same filter as df_filtered)
    total_rs_coll = df_filtered["total_coll_seized_usd"].sum()

    # Total liquidation count: from liqs (all rows), grouped by tx_hash, coll > $1
    rs_raw = liqs[liqs["oev_provider"] == "RedStone"]
    redstone_liqs_count = (
        rs_raw
        .groupby("tx_hash", sort=False)
        .agg(total_coll_seized_usd=("total_coll_seized_usd", "first"))
        .query("total_coll_seized_usd > 1")
    )
    total_liq_count = len(redstone_liqs_count)

    return {
        "oev_recapture_ratio_dollar_weighted_pct": round(rs_weighted_avg, 3),
        "oev_recapture_efficiency_pct": round(float(oev_recapture_pct), 2),
        "total_liquidation_count": int(total_liq_count),
        "total_collateral_seized_usd": round(float(total_rs_coll), 2),
        "total_collateral_liquidated_usd": round(total_collateral_liquidated_usd, 2),
        "total_debt_repaid_usd": round(total_debt_repaid_usd, 2),
        "total_oev_recaptured_usd": round(total_oev_usd, 2),
        "simulated_gross_liquidation_bonus_usd": round(float(total_actual_bonus_usd), 2),
        "treasury_fee_usd": round(float(treasury_fee_usd), 2),
        "recapturable_bonus_usd": round(float(recapturable_bonus_usd), 2),
        "realized_lb_pct_without_oev": round(float(realized_lb_pct_without_oev), 3),
        "realized_lb_pct_with_oev": round(float(realized_lb_pct_with_oev), 3),
    }


def _compute_coverage(oev_cov: pd.DataFrame) -> dict:
    """
    OEV coverage rates by count and dollar-weighted.

    Mirrors app.py lines 297-363.
    """
    classified = oev_cov[
        (oev_cov["likely_cause_provider"].isin(["RedStone", "Chainlink"]))
        & (oev_cov["total_coll_seized_usd"] > 0.5)
    ].copy()

    rs_captured = classified[
        (classified["likely_cause_provider"] == "RedStone")
        & (classified["oev_provider"] == "RedStone")
    ]
    rs_missed = classified[
        (classified["likely_cause_provider"] == "RedStone")
        & (classified["oev_provider"] == "none")
    ]

    rs_captured_usd = float(rs_captured["total_coll_seized_usd"].sum())
    rs_missed_usd = float(rs_missed["total_coll_seized_usd"].sum())
    rs_total_usd = rs_captured_usd + rs_missed_usd
    rs_total = len(rs_captured) + len(rs_missed)

    coverage_by_count_pct = round(len(rs_captured) / rs_total * 100, 1) if rs_total > 0 else 0.0
    coverage_dollar_weighted_pct = round(rs_captured_usd / rs_total_usd * 100, 1) if rs_total_usd > 0 else 0.0

    return {
        "coverage_by_count_pct": coverage_by_count_pct,
        "coverage_dollar_weighted_pct": coverage_dollar_weighted_pct,
        "eligible_count": rs_total,
        "eligible_usd": round(rs_total_usd, 2),
        "captured_count": len(rs_captured),
        "captured_usd": round(rs_captured_usd, 2),
        "missed_count": len(rs_missed),
        "missed_usd": round(rs_missed_usd, 2),
    }


def _compute_daily(liqs: pd.DataFrame) -> list[dict]:
    """
    Daily OEV fees recaptured time series.

    Mirrors app.py lines 113-121.
    Source: liqs_dedup filtered to RedStone, grouped by date.
    """
    liqs_dedup = liqs[liqs["is_primary_row"]].copy()
    df_daily = liqs_dedup[liqs_dedup["oev_provider"] == "RedStone"].copy()
    df_daily["date"] = pd.to_datetime(df_daily["block_time"]).dt.date

    daily_oev = (
        df_daily
        .groupby("date")["oev_bid_usd"]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    return [
        {"date": str(row["date"]), "oev_bid_usd": round(float(row["oev_bid_usd"]), 2)}
        for _, row in daily_oev.iterrows()
    ]


def _compute_collateral_by_token(liqs: pd.DataFrame) -> list[dict]:
    """
    Collateral seized grouped by vToken symbol.

    Mirrors app.py lines 370-378.
    Source: liqs (all rows, NOT deduped) — multi-token txs have one row per
    collateral token, so summing coll_seized_usd across all rows gives correct totals.
    """
    df_tokens = liqs[liqs["oev_provider"] == "RedStone"]
    rs_by_coll = (
        df_tokens
        .groupby("coll_token_symbol")["coll_seized_usd"]
        .sum()
        .reset_index(name="coll_seized_usd")
        .query("coll_seized_usd >= 5")
        .sort_values("coll_seized_usd", ascending=False)
    )
    return [
        {"token": row["coll_token_symbol"], "coll_seized_usd": round(float(row["coll_seized_usd"]), 2)}
        for _, row in rs_by_coll.iterrows()
    ]


# ---------------------------------------------------------------------------
# Main cache builder
# ---------------------------------------------------------------------------

def build_cache(api_key: str) -> dict:
    """
    Fetch both Dune queries and compute all four aggregated payloads.
    Returns a dict ready to be stored as the in-memory cache.
    """
    liqs, fetch_time = fetch_liquidation_data(api_key)
    oev_cov = fetch_coverage_data(api_key)

    return {
        "last_refreshed": datetime.now(timezone.utc).isoformat(),
        "dune_execution_time": fetch_time.isoformat(),
        "summary": _compute_summary(liqs),
        "coverage": _compute_coverage(oev_cov),
        "daily": _compute_daily(liqs),
        "collateral_by_token": _compute_collateral_by_token(liqs),
    }
