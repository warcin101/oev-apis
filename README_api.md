# Venus OEV Analytics API — multi-provider

A FastAPI service exposing aggregated OEV (Oracle Extractable Value) liquidation statistics for **Venus Protocol on BNB Smart Chain**, covering both **RedStone** and **Chainlink** oracle providers.

Data is sourced from Dune Analytics (queries [6702800](https://dune.com/queries/6702800) and [6715606](https://dune.com/queries/6715606)) and cached in memory, refreshed every 6 hours.

> **Branch note:** The `main` branch of this repo exposes RedStone-only statistics. This `multi-provider` branch returns per-provider data for both RedStone and Chainlink under a `"providers"` key in every response.

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

Dollar-weighted OEV/collateral ratio, recapture efficiency, and aggregate liquidation statistics for each provider.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "providers": {
    "redstone": {
      "oev_recapture_ratio_dollar_weighted_pct": 2.145,
      "oev_recapture_efficiency_pct": 73.42,
      "total_liquidation_count": 128,
      "total_collateral_seized_usd": 4820310.55,
      "total_debt_repaid_usd": 4650000.00,
      "total_oev_recaptured_usd": 187430.20,
      "simulated_gross_liquidation_bonus_usd": 251250.00,
      "treasury_fee_usd": 232500.00,
      "recapturable_bonus_usd": 255300.00,
      "realized_lb_pct_without_oev": 5.126,
      "realized_lb_pct_with_oev": 1.302
    },
    "chainlink": {
      "oev_recapture_ratio_dollar_weighted_pct": 1.823,
      "oev_recapture_efficiency_pct": 61.10,
      "total_liquidation_count": 54,
      "total_collateral_seized_usd": 1940200.00,
      "total_debt_repaid_usd": 1850000.00,
      "total_oev_recaptured_usd": 58400.00,
      "simulated_gross_liquidation_bonus_usd": 130000.00,
      "treasury_fee_usd": 92500.00,
      "recapturable_bonus_usd": 95500.00,
      "realized_lb_pct_without_oev": 6.565,
      "realized_lb_pct_with_oev": 3.616
    }
  }
}
```

**Field definitions (same for both providers):**

| Field | Definition |
|---|---|
| `oev_recapture_ratio_dollar_weighted_pct` | Dollar-weighted average of OEV bid ÷ collateral seized (%) |
| `oev_recapture_efficiency_pct` | Share of the recapturable bonus (gross bonus minus Venus 5% treasury take) bid back via OEV (%) |
| `total_liquidation_count` | Liquidation transactions where collateral seized > $1 |
| `total_collateral_seized_usd` | Sum of collateral seized (USD) across all provider liquidations |
| `total_debt_repaid_usd` | Sum of debt repaid by liquidators |
| `total_oev_recaptured_usd` | Sum of OEV bids paid back to the protocol |
| `simulated_gross_liquidation_bonus_usd` | Collateral seized − Debt repaid |
| `treasury_fee_usd` | Venus 5% treasury fee (= 0.05 × debt repaid) |
| `recapturable_bonus_usd` | Gross bonus − Treasury fee; the maximum a solver could theoretically bid |
| `realized_lb_pct_without_oev` | Gross bonus as % of collateral, as if no OEV bids were made |
| `realized_lb_pct_with_oev` | Net bonus after OEV bids, as % of collateral |

---

### `GET /metrics/coverage`

Coverage rates measuring what share of eligible liquidation opportunities were captured via the OEV channel, for each provider.

An *eligible* liquidation is one where the asset that most likely triggered the health-factor breach is priced via an OEV-enabled vToken for that provider, and collateral seized exceeded $0.50.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "providers": {
    "redstone": {
      "coverage_by_count_pct": 82.4,
      "coverage_dollar_weighted_pct": 91.3,
      "eligible_count": 85,
      "eligible_usd": 3204500.00,
      "captured_count": 70,
      "captured_usd": 2925500.00,
      "missed_count": 15,
      "missed_usd": 279000.00
    },
    "chainlink": {
      "coverage_by_count_pct": 55.0,
      "coverage_dollar_weighted_pct": 63.2,
      "eligible_count": 40,
      "eligible_usd": 1100000.00,
      "captured_count": 22,
      "captured_usd": 695200.00,
      "missed_count": 18,
      "missed_usd": 404800.00
    }
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

Total OEV bids paid by searchers per day, for each provider, sorted chronologically.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "providers": {
    "redstone": [
      {"date": "2026-02-07", "oev_bid_usd": 4210.50},
      {"date": "2026-02-08", "oev_bid_usd": 9830.75}
    ],
    "chainlink": [
      {"date": "2026-02-07", "oev_bid_usd": 1200.00},
      {"date": "2026-02-08", "oev_bid_usd": 3450.25}
    ]
  }
}
```

---

### `GET /metrics/collateral-by-token`

Collateral seized broken down by vToken symbol, for each provider, sorted by value descending. Only tokens with total collateral seized ≥ $5 are included.

```json
{
  "last_refreshed": "2026-02-27T10:00:00+00:00",
  "providers": {
    "redstone": [
      {"token": "vBNB", "coll_seized_usd": 1840200.00},
      {"token": "vETH", "coll_seized_usd": 930150.50}
    ],
    "chainlink": [
      {"token": "vBTC", "coll_seized_usd": 820000.00},
      {"token": "vUSDT", "coll_seized_usd": 310400.00}
    ]
  }
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
git checkout multi-provider
pip install -r requirements_api.txt
# Set your API key in the shell — do not commit it
export DUNE_API_KEY=your_key_here
uvicorn api.main:app --reload
```

The service warms the cache on startup (one Dune API call per query). Subsequent refreshes happen automatically every 6 hours.

Interactive API docs are available at `http://localhost:8000/docs`.

### Docker

```bash
docker build -t oev-api-multi .
docker run -e DUNE_API_KEY=your_key_here -e PORT=8000 -p 8000:8000 oev-api-multi
```

### Railway

1. Create a new Railway project and connect this repository.
2. In **Settings → Variables**, add `DUNE_API_KEY`.
3. In **Settings → Source**, set the branch to `multi-provider`.
4. Railway will detect the `Dockerfile` and build automatically.

---

## Notes

- All values are in USD unless otherwise stated.
- Analysis covers Venus Protocol liquidations from 7 February 2026 00:00 CET onwards.
- The 503 response on `/metrics/*` endpoints means the service is still loading data from Dune on first boot — retry after a few seconds.
- The `"chainlink"` provider data reflects liquidations where Chainlink's price feed processed the OEV auction. If Chainlink has no OEV activity in the dataset, its numeric fields will be zero.
