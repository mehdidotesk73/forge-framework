# stock-monitor — Forge Example Project

Demonstrates stream objects, scheduled pipelines, parameterized computed column endpoints, and chart display.

## Quick Start

```bash
cd examples/stock-monitor
bash setup.sh           # provisions dataset, runs pipeline, builds models + endpoints

forge dev serve &       # starts API server on :8000

cd apps/monitor && npm install && npm run dev   # :5175
```

## Layer Developer Guide

### Pipeline developer (`pipelines/`)

You fetch daily OHLCV prices for AAPL, MSFT, GOOGL, AMZN, NVDA via yfinance and write them to the prices dataset. The pipeline is declared with a cron schedule (`0 18 * * 1-5` — weekdays at 18:00 UTC). Falls back to synthetic data if yfinance is unavailable.

```bash
forge pipeline run price_pipeline       # manual trigger
forge pipeline history price_pipeline   # show run log
forge dev serve                         # internal scheduler fires automatically
```

Trigger from an external scheduler or CI:
```bash
curl -X POST http://localhost:8000/api/pipelines/price_pipeline/run
```

### Model developer (`models/`)

You declare `Price` as a stream object backed by the prices dataset. Stream objects are read-only — no snapshot is taken, no CRUD operations exist.

```bash
forge model build
```

When the pipeline reruns, the Price object set automatically reflects the new data.

### API developer (`endpoint_repos/price_endpoints/`)

You write `compute_moving_average` — a computed column endpoint that accepts a list of Price records and a `days` parameter and returns a `moving_avg` column (rolling mean of close price per symbol).

```bash
forge endpoint build
```

The `days` parameter is declared in the endpoint descriptor. The view layer binds it to a Selector widget so the moving average window is controllable from the UI without any backend changes.

### UI developer (`apps/monitor/`)

```bash
cd apps/monitor && npm run dev
```

The monitor page composes:
- `Selector` for symbol and for MA window (bound to computed column `days` param)
- `Chart` showing close price as a line
- `ObjectTable` with the `moving_avg` computed column attached; refetches automatically when the MA window selector changes

You never call the yfinance API. You never compute rolling averages. You never know the prices dataset UUID.
