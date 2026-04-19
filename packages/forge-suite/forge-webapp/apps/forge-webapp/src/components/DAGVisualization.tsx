import React, { useMemo } from "react";

interface DAGNode {
  id: string;
  kind: "pipeline" | "dataset";
  label: string;
  schedule?: string;
}

interface DAGEdge {
  source: string;
  target: string;
}

interface Props {
  nodes: DAGNode[];
  edges: DAGEdge[];
}

const NODE_W = 120;
const NODE_H = 40;
const H_GAP = 80;
const V_GAP = 56;
const PAD = 24;

function layoutNodes(nodes: DAGNode[], edges: DAGEdge[]) {
  // Assign columns by topological sort (simplified BFS)
  const colMap = new Map<string, number>();
  const inEdges = new Map<string, string[]>();
  nodes.forEach((n) => inEdges.set(n.id, []));
  edges.forEach((e) => {
    inEdges.get(e.target)?.push(e.source);
  });

  const queue: string[] = [];
  nodes.forEach((n) => {
    if ((inEdges.get(n.id) ?? []).length === 0) queue.push(n.id);
  });

  while (queue.length) {
    const id = queue.shift()!;
    const col = Math.max(
      0,
      ...(inEdges.get(id) ?? []).map((src) => (colMap.get(src) ?? 0) + 1)
    );
    colMap.set(id, col);
    edges
      .filter((e) => e.source === id)
      .forEach((e) => {
        if (!colMap.has(e.target)) queue.push(e.target);
      });
  }

  // Group by column
  const cols = new Map<number, DAGNode[]>();
  nodes.forEach((n) => {
    const c = colMap.get(n.id) ?? 0;
    if (!cols.has(c)) cols.set(c, []);
    cols.get(c)!.push(n);
  });

  const pos = new Map<string, { x: number; y: number }>();
  Array.from(cols.entries())
    .sort(([a], [b]) => a - b)
    .forEach(([col, colNodes]) => {
      const x = PAD + col * (NODE_W + H_GAP);
      const totalH = colNodes.length * NODE_H + (colNodes.length - 1) * (V_GAP - NODE_H);
      const startY = PAD + Math.max(0, (200 - totalH) / 2);
      colNodes.forEach((n, i) => {
        pos.set(n.id, { x, y: startY + i * V_GAP });
      });
    });

  const maxCol = Math.max(0, ...Array.from(colMap.values()));
  const svgW = PAD * 2 + (maxCol + 1) * (NODE_W + H_GAP);
  const maxNodeBottom = Math.max(0, ...Array.from(pos.values()).map(({ y }) => y + NODE_H + 20));
  const svgH = maxNodeBottom + PAD;

  return { pos, svgW: Math.max(svgW, 200), svgH: Math.max(svgH, 100) };
}

export function DAGVisualization({ nodes, edges }: Props) {
  const { pos, svgW, svgH } = useMemo(() => layoutNodes(nodes, edges), [nodes, edges]);

  if (nodes.length === 0) {
    return (
      <div className="empty-state" style={{ padding: "32px 0" }}>
        No pipeline data. Register and sync a project first.
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto", overflowY: "hidden" }}>
    <svg
      width={svgW}
      height={svgH}
      style={{ display: "block" }}
    >
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="var(--text-muted)" />
        </marker>
      </defs>

      {edges.map((e, i) => {
        const s = pos.get(e.source);
        const t = pos.get(e.target);
        if (!s || !t) return null;
        const sx = s.x + NODE_W;
        const sy = s.y + NODE_H / 2;
        const tx = t.x;
        const ty = t.y + NODE_H / 2;
        const mx = (sx + tx) / 2;
        return (
          <path
            key={i}
            d={`M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`}
            fill="none"
            stroke="var(--text-muted)"
            strokeWidth={1.5}
            markerEnd="url(#arrow)"
            opacity={0.6}
          />
        );
      })}

      {nodes.map((n) => {
        const p = pos.get(n.id);
        if (!p) return null;
        const isPipeline = n.kind === "pipeline";
        const fill = isPipeline ? "#1d2a3a" : "#1a1d27";
        const stroke = isPipeline ? "var(--accent)" : "var(--border)";
        const textColor = isPipeline ? "var(--accent)" : "var(--text-muted)";
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`}>
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={isPipeline ? 6 : 20}
              fill={fill}
              stroke={stroke}
              strokeWidth={1.5}
            />
            <text
              x={NODE_W / 2}
              y={NODE_H / 2}
              dominantBaseline="middle"
              textAnchor="middle"
              fontSize={11}
              fill={textColor}
              fontFamily="monospace"
            >
              {n.label.length > 14 ? n.label.slice(0, 13) + "…" : n.label}
            </text>
            {isPipeline && n.schedule && (
              <text
                x={NODE_W / 2}
                y={NODE_H + 12}
                dominantBaseline="middle"
                textAnchor="middle"
                fontSize={9}
                fill="var(--text-muted)"
              >
                {n.schedule}
              </text>
            )}
          </g>
        );
      })}
    </svg>
    </div>
  );
}
