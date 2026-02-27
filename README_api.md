# Venus OEV Analytics API

A FastAPI service exposing aggregated OEV (Oracle Extractable Value) liquidation statistics for **Venus Protocol on BNB Smart Chain**, powered by RedStone Atom.

Data is sourced from Dune Analytics (queries [6702800](https://dune.com/queries/6702800) and [6715606](https://dune.com/queries/6715606)) and cached in memory, refreshed every 6 hours.

---

## Endpoints

### `GET /`

Health check. Returns service status and the timestamp of the last successful data refresh.

```json
{
  "status": "ok",
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "dune_execution_time": "2026-02-27T09:45:00+00:00"
}
```

---

### `GET /metrics/summary`

Dollar-weighted OEV/collateral ratio, recapture efficiency, and aggregate liquidation statistics.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "data": {
    "oev_recapture_ratio_dollar_weighted_pct": 2.145,
    "oev_recapture_efficiency_pct": 73.42,
    "total_liquidation_count": 128,
    "total_collateral_seized_usd": 4820310.55,
    "total_collateral_liquidated_usd": 4901250.00,
    "total_debt_repaid_usd": 4650000.00,
    "total_oev_recaptured_usd": 187430.20,
    "simulated_gross_liquidation_bonus_usd": 251250.00,
    "treasury_fee_usd": 232500.00,
    "recapturable_bonus_usd": 255300.00,
    "realized_lb_pct_without_oev": 5.126,
    "realized_lb_pct_with_oev": 1.302
  }
}
```

**Field definitions:**

| Field | Definition |
|---|---|
| `oev_recapture_ratio_dollar_weighted_pct` | Dollar-weighted average of OEV bid ÷ collateral seized, across all RedStone liquidations |
| `oev_recapture_efficiency_pct` | Share of the recapturable bonus (gross bonus minus Venus 5% treasury take) that was bid back via OEV |
| `total_liquidation_count` | RedStone liquidation transactions where collateral seized > $1 |
| `total_collateral_seized_usd` | Sum of collateral seized (USD) for RedStone liquidations with a valid OEV ratio |
| `total_collateral_liquidated_usd` | Sum of collateral seized across all RedStone liquidations |
| `total_debt_repaid_usd` | Sum of debt repaid by liquidators |
| `total_oev_recaptured_usd` | Sum of OEV bids paid back to the protocol |
| `simulated_gross_liquidation_bonus_usd` | Collateral seized − Debt repaid |
| `treasury_fee_usd` | Venus 5% treasury fee (= 0.05 × debt repaid) |
| `recapturable_bonus_usd` | Gross bonus − Treasury fee; the maximum a solver could theoretically bid |
| `realized_lb_pct_without_oev` | Gross bonus as % of collateral, as if no OEV bids were made |
| `realized_lb_pct_with_oev` | Net bonus after OEV bids, as % of collateral |

---

### `GET /metrics/coverage`

Coverage rates measuring what share of eligible liquidation opportunities were captured via the OEV channel.

An *eligible* liquidation is one where the asset that most likely triggered the health-factor breach is priced via a RedStone OEV-enabled vToken, and collateral seized exceeded $0.50.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "data": {
    "coverage_by_count_pct": 82.4,
    "coverage_dollar_weighted_pct": 91.3,
    "eligible_count": 85,
    "eligible_usd": 3204500.00,
    "captured_count": 70,
    "captured_usd": 2925500.00,
    "missed_count": 15,
    "missed_usd": 279000.00
  }
}
```

| Field | Definition |
|---|---|
| `coverage_by_count_pct` | % of eligible liquidations (by count) captured via OEV |
| `coverage_dollar_weighted_pct` | % of eligible collateral USD captured via OEV |
| `eligible_count` | Total eligible liquidations (captured + missed) |
| `eligible_usd` | Total collateral USD across all eligible liquidations |
| `captured_count` / `captured_usd` | Liquidations captured via OEV and their collateral value |
| `missed_count` / `missed_usd` | Eligible liquidations that bypassed OEV entirely |

---

### `GET /metrics/daily`

Total OEV bids paid by searchers per day, sorted chronologically.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "data": [
    {"date": "2026-02-07", "oev_bid_usd": 4210.50},
    {"date": "2026-02-08", "oev_bid_usd": 9830.75},
    {"date": "2026-02-09", "oev_bid_usd": 6120.00}
  ]
}
```

---

### `GET /metrics/collateral-by-token`

Collateral seized broken down by vToken symbol, sorted by value descending. Only tokens with total collateral seized ≥ $5 are included.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "data": [
    {"token": "vBNB", "coll_seized_usd": 1840200.00},
    {"token": "vETH", "coll_seized_usd": 930150.50},
    {"token": "vBTC", "coll_seized_usd": 410000.00}
  ]
}
```

---

## Setup & deployment

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `DUNE_API_KEY` | Yes | Your Dune Analytics API key |
| `PORT` | No (Railway injects it) | Port for the Uvicorn server (defaults to `8000`) |

### Local development

```bash
cd oev-apis
pip install -r requirements_api.txt
# Set your API key in the shell — do not commit it
export DUNE_API_KEY=your_key_here
uvicorn api.main:app --reload
```

The service will warm the cache on startup (one Dune API call per query). Subsequent refreshes happen automatically every 6 hours.

Interactive API docs are available at `http://localhost:8000/docs`.

### Docker

```bash
docker build -t oev-api .
# Pass your API key at runtime
docker run -e DUNE_API_KEY=your_key_here -e PORT=8000 -p 8000:8000 oev-api
```

### Railway

1. Create a new Railway project and connect this repository (or the `oev-apis/` directory).
2. In **Settings → Variables**, add `DUNE_API_KEY` with your Dune API key.
3. Railway will detect the `Dockerfile` and build automatically. The `$PORT` variable is injected at runtime.

---

## Notes

- All values are in USD unless otherwise stated.
- Analysis covers Venus Protocol liquidations from 7 February 2026 00:00 CET onwards.
- The 503 response on `/metrics/*` endpoints means the service is still loading data from Dune on first boot — retry after a few seconds.
