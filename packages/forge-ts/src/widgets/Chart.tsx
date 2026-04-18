import React from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ForgeObjectSet } from "../types/index.js";

export type ChartType = "line" | "bar" | "area";

export interface ChartSeries {
  field: string;
  label?: string;
  color?: string;
}

export interface ChartProps<T extends Record<string, unknown>> {
  objectSet: ForgeObjectSet<T>;
  chartType?: ChartType;
  xField: string;
  series: ChartSeries[];
  height?: number;
  className?: string;
}

const COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6"];

export function Chart<T extends Record<string, unknown>>({
  objectSet,
  chartType = "line",
  xField,
  series,
  height = 300,
  className = "",
}: ChartProps<T>) {
  const data = objectSet.rows as Record<string, unknown>[];

  const renderLines = () =>
    series.map((s, i) => {
      const color = s.color ?? COLORS[i % COLORS.length];
      const name = s.label ?? s.field;
      if (chartType === "bar")
        return <Bar key={s.field} dataKey={s.field} name={name} fill={color} />;
      if (chartType === "area")
        return (
          <Area
            key={s.field}
            type="monotone"
            dataKey={s.field}
            name={name}
            stroke={color}
            fill={color}
            fillOpacity={0.2}
          />
        );
      return (
        <Line
          key={s.field}
          type="monotone"
          dataKey={s.field}
          name={name}
          stroke={color}
          dot={false}
        />
      );
    });

  const ChartComponent =
    chartType === "bar" ? BarChart : chartType === "area" ? AreaChart : LineChart;

  return (
    <div className={`forge-chart ${className}`}>
      <ResponsiveContainer width="100%" height={height}>
        <ChartComponent data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xField} />
          <YAxis />
          <Tooltip />
          <Legend />
          {renderLines()}
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  );
}
