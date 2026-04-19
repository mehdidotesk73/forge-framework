import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchObjectSet,
  callEndpoint,
  DateInput,
  NumberInput,
  ButtonGroup,
  Container,
} from "@forge-framework/ts";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const GET_BITCOIN_METRICS_ID = "2fecbcfc-e136-49c1-aa5c-c3a36c608169";

type PriceRow = {
  pK: string;
  Date: string;
  Close: number;
  High: number;
  Low: number;
  Open: number;
  Volume: number;
};

export function PriceChart() {
  const [maWindow, setMaWindow] = useState(180);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const {
    data: priceData,
    isLoading: pricesLoading,
    error: priceError,
  } = useQuery({
    queryKey: ["BitcoinPrice"],
    queryFn: async () => {
      const result = await fetchObjectSet<PriceRow>("BitcoinPrice", {
        limit: 10000,
      });
      console.log(
        "[btc-chart] BitcoinPrice rows:",
        result?.rows?.length,
        result,
      );
      return result;
    },
    staleTime: 60_000,
  });
  if (priceError) console.error("[btc-chart] BitcoinPrice error:", priceError);

  const allRows = useMemo(() => {
    return (priceData?.rows ?? [])
      .slice()
      .sort((a, b) => a.Date.localeCompare(b.Date));
  }, [priceData]);

  const primaryKeys = useMemo(() => allRows.map((r) => r.pK), [allRows]);

  const {
    data: metricsData,
    isLoading: metricsLoading,
    error: metricsError,
  } = useQuery({
    queryKey: ["bitcoin_metrics", maWindow],
    queryFn: async () => {
      const result = await callEndpoint<{
        columns: Record<string, { moving_average: number }>;
      }>(GET_BITCOIN_METRICS_ID, {
        primary_keys: primaryKeys,
        window: maWindow,
      });
      console.log("[btc-chart] metrics result:", result);
      return result;
    },
    enabled: primaryKeys.length > 0,
    staleTime: 30_000,
  });
  if (metricsError) console.error("[btc-chart] metrics error:", metricsError);

  const chartData = useMemo(() => {
    const columns = metricsData?.columns ?? {};
    let rows = allRows.map((r) => ({
      date: r.Date,
      close: r.Close,
      ma: columns[r.pK]?.moving_average ?? null,
    }));

    if (dateFrom) rows = rows.filter((r) => r.date >= dateFrom);
    if (dateTo) rows = rows.filter((r) => r.date <= dateTo);

    return rows;
  }, [allRows, metricsData, dateFrom, dateTo]);

  const isLoading = pricesLoading || metricsLoading;

  return (
    <div>
      <Container
        direction='row'
        layout='flex'
        gap='16px'
        padding='0'
        style={{ marginBottom: 24, flexWrap: "wrap", alignItems: "flex-end" }}
      >
        <DateInput label='From' value={dateFrom} onChange={setDateFrom} />
        <DateInput label='To' value={dateTo} onChange={setDateTo} />
        {(dateFrom || dateTo) && (
          <ButtonGroup
            buttons={[
              {
                label: "Reset range",
                variant: "ghost",
                action: {
                  kind: "ui",
                  handler: () => {
                    setDateFrom("");
                    setDateTo("");
                  },
                },
              },
            ]}
          />
        )}
        <NumberInput
          label='MA window (days)'
          value={maWindow}
          onChange={(v) => {
            if (v > 0) setMaWindow(v);
          }}
          min={1}
          max={365}
        />
      </Container>

      <div
        style={{
          background: "#161b27",
          borderRadius: 10,
          padding: "20px 8px 8px 0",
          border: "1px solid #1e2535",
        }}
      >
        {isLoading ? (
          <div
            style={{
              height: 400,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#64748b",
            }}
          >
            Loading…
          </div>
        ) : (
          <ResponsiveContainer width='100%' height={420}>
            <LineChart
              data={chartData}
              margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray='3 3' stroke='#1e2535' />
              <XAxis
                dataKey='date'
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickFormatter={(v) => v.slice(0, 7)}
                interval='preserveStartEnd'
                minTickGap={60}
              />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickFormatter={(v) => `$${(v as number).toLocaleString()}`}
                width={80}
              />
              <Tooltip
                contentStyle={{
                  background: "#1e2535",
                  border: "1px solid #334155",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#94a3b8" }}
                formatter={(value: number, name: string) => [
                  `$${value?.toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
                  name === "close"
                    ? "BTC (Close)"
                    : `BTC (Close) - MA (${maWindow}d)`,
                ]}
              />
              <Legend
                formatter={(value) =>
                  value === "close"
                    ? "BTC (Close)"
                    : `BTC (Close) - MA (${maWindow}d)`
                }
                wrapperStyle={{ fontSize: 12, color: "#94a3b8", paddingTop: 8 }}
              />
              <Line
                type='monotone'
                dataKey='close'
                stroke='#f7931a'
                dot={false}
                strokeWidth={1.5}
                isAnimationActive={false}
              />
              <Line
                type='monotone'
                dataKey='ma'
                stroke='#38bdf8'
                dot={false}
                strokeWidth={1.5}
                strokeDasharray='4 2'
                isAnimationActive={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div
        style={{
          marginTop: 8,
          fontSize: 11,
          color: "#475569",
          textAlign: "right",
        }}
      >
        {chartData.length.toLocaleString()} data points shown
      </div>
    </div>
  );
}
