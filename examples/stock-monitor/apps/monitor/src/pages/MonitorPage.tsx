/**
 * View Layer — Stock Price Monitor App
 *
 * Demonstrates:
 * - Stream object set (Price) — live pipeline output, read-only
 * - Selector bound to local state controlling computed column parameter
 * - ObjectTable with moving average computed column attached
 * - Chart with price series + moving average overlay
 *
 * The UI developer never writes fetch logic, never knows about dataset UUIDs,
 * DuckDB, or the moving average algorithm.
 */
import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Chart,
  Container,
  ObjectTable,
  Selector,
  bindState,
  type ForgeObjectSet,
} from "@forge-framework/ts";
import { fetchObjectSet } from "@forge-framework/ts/runtime";

// Endpoint UUID from the control layer (price_endpoints repo)
const MOVING_AVG_ID = "22222222-0000-0000-0000-000000000001";

type PriceRow = {
  symbol: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

const WINDOW_OPTIONS = [
  { value: "5", label: "5-day MA" },
  { value: "20", label: "20-day MA" },
  { value: "50", label: "50-day MA" },
  { value: "200", label: "200-day MA" },
];

const SYMBOL_OPTIONS = [
  { value: "AAPL", label: "AAPL" },
  { value: "MSFT", label: "MSFT" },
  { value: "GOOGL", label: "GOOGL" },
  { value: "AMZN", label: "AMZN" },
  { value: "NVDA", label: "NVDA" },
];

export function MonitorPage() {
  const [days, setDays] = useState("20");
  const [symbol, setSymbol] = useState("AAPL");

  const { data } = useQuery({
    queryKey: ["prices"],
    queryFn: () => fetchObjectSet<PriceRow>("Price", { limit: 5000 }),
    refetchInterval: 60_000,
  });

  // Filter to selected symbol for the chart
  const symbolRows = useMemo(
    () => (data?.rows ?? []).filter((r) => r.symbol === symbol),
    [data, symbol]
  );

  const objectSet: ForgeObjectSet<PriceRow> | undefined = data
    ? {
        rows: symbolRows,
        schema: data.schema as any,
        datasetId: "Price",
        mode: "stream",
        total: symbolRows.length,
      }
    : undefined;

  // Chart set merges price data — moving_avg column is added by computed endpoint
  // For the chart we pass the same objectSet; the Chart widget uses the raw rows.
  // A richer implementation would merge computed columns into chart data.

  if (!objectSet) return <div>Loading prices...</div>;

  return (
    <div>
      <h2>Stock Price Monitor</h2>

      <Container layout="flex" direction="row" gap="1rem" padding="0 0 1rem 0">
        <Selector
          label="Symbol"
          value={symbol}
          options={SYMBOL_OPTIONS}
          onChange={setSymbol}
        />
        <Selector
          label="Moving Average Window"
          value={days}
          options={WINDOW_OPTIONS}
          onChange={setDays}
        />
      </Container>

      {/* Chart: close price + moving average overlay */}
      <div style={{ marginBottom: "2rem" }}>
        <h3>{symbol} — Close Price</h3>
        <Chart
          objectSet={objectSet}
          chartType="line"
          xField="date"
          series={[
            { field: "close", label: "Close", color: "#6366f1" },
          ]}
          height={320}
        />
      </div>

      {/*
        ObjectTable with moving average computed column.
        The `days` selector value is passed via localState.
        bindState("days") tells the widget to resolve the `days` param
        from localState — so the endpoint refetches when the selector changes.
      */}
      <h3>Price Data with Moving Average</h3>
      <ObjectTable
        objectSet={objectSet}
        computedColumns={[
          {
            endpointId: MOVING_AVG_ID,
            params: {
              days: bindState("days"),
            },
          },
        ]}
        localState={{ days: parseInt(days) }}
        interaction={{
          visibleFields: ["date", "open", "high", "low", "close", "volume"],
          sortField: "date",
          sortOrder: "desc",
          density: "compact",
        }}
      />
    </div>
  );
}
