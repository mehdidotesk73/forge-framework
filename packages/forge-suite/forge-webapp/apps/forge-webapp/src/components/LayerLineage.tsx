import React from "react";

interface LayerItem {
  label: string;
  detail: string;
}

interface Layer {
  name: string;
  color: string;
  items: LayerItem[];
}

interface Props {
  layers: Layer[];
}

const LAYER_H = 72;
const BAND_PAD = 12;

export function LayerLineage({ layers }: Props) {
  if (layers.length === 0) {
    return (
      <div className="empty-state" style={{ padding: "32px 0" }}>
        No layer data. Register and sync a project first.
      </div>
    );
  }

  const svgW = 600;
  const svgH = layers.length * (LAYER_H + BAND_PAD) + BAND_PAD;

  return (
    <svg
      width={svgW}
      height={svgH}
      style={{ display: "block", maxWidth: "100%" }}
    >
      {layers.map((layer, li) => {
        const y = BAND_PAD + li * (LAYER_H + BAND_PAD);
        const labelW = 90;
        const itemsX = labelW + 16;
        const itemW = 110;
        const itemGap = 8;

        return (
          <g key={layer.name}>
            {/* Band background */}
            <rect
              x={0}
              y={y}
              width={svgW}
              height={LAYER_H}
              rx={8}
              fill={layer.color + "18"}
              stroke={layer.color + "44"}
              strokeWidth={1}
            />

            {/* Layer label */}
            <text
              x={labelW - 8}
              y={y + LAYER_H / 2}
              dominantBaseline="middle"
              textAnchor="end"
              fontSize={11}
              fontWeight={700}
              fill={layer.color}
              fontFamily="system-ui, sans-serif"
            >
              {layer.name}
            </text>

            {/* Divider */}
            <line
              x1={labelW}
              y1={y + 10}
              x2={labelW}
              y2={y + LAYER_H - 10}
              stroke={layer.color + "55"}
              strokeWidth={1}
            />

            {/* Items */}
            {layer.items.map((item, ii) => {
              const ix = itemsX + ii * (itemW + itemGap);
              return (
                <g key={item.label} transform={`translate(${ix}, ${y + LAYER_H / 2 - 18})`}>
                  <rect
                    width={itemW}
                    height={36}
                    rx={6}
                    fill={layer.color + "22"}
                    stroke={layer.color + "66"}
                    strokeWidth={1}
                  />
                  <text
                    x={itemW / 2}
                    y={13}
                    dominantBaseline="middle"
                    textAnchor="middle"
                    fontSize={11}
                    fontWeight={600}
                    fill={layer.color}
                    fontFamily="system-ui, sans-serif"
                  >
                    {item.label.length > 13 ? item.label.slice(0, 12) + "…" : item.label}
                  </text>
                  <text
                    x={itemW / 2}
                    y={26}
                    dominantBaseline="middle"
                    textAnchor="middle"
                    fontSize={9}
                    fill={layer.color + "bb"}
                    fontFamily="system-ui, sans-serif"
                  >
                    {item.detail}
                  </text>
                </g>
              );
            })}

            {layer.items.length === 0 && (
              <text
                x={itemsX}
                y={y + LAYER_H / 2}
                dominantBaseline="middle"
                fontSize={11}
                fill={layer.color + "66"}
                fontFamily="system-ui, sans-serif"
              >
                (empty)
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
