import React, { useEffect, useRef, useState } from "react";

export interface LogLine {
  event: string;
  data: string;
  ts: number;
}

export interface LogPanelProps {
  lines: LogLine[];
  running?: boolean;
}

export function LogPanel({ lines, running = false }: LogPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines.length]);

  const color = (event: string) => {
    if (event === "stderr") return "var(--accent-orange)";
    if (event === "error") return "var(--accent-red)";
    if (event === "status") return "var(--accent)";
    return "var(--text)";
  };

  const handleCopy = () => {
    const text = lines.map((l) => l.data).join("\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <button
        onClick={handleCopy}
        title={copied ? "Copied!" : "Copy to clipboard"}
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          zIndex: 1,
          background: "transparent",
          border: "1px solid var(--border)",
          borderRadius: 4,
          padding: "2px 6px",
          cursor: "pointer",
          color: copied ? "var(--accent-green)" : "var(--text-muted)",
          fontSize: 12,
          lineHeight: 1.4,
          transition: "color 0.15s",
        }}
      >
        {copied ? "✓" : "⎘"}
      </button>
      <div style={{
        background: "#0a0c12",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "12px 36px 12px 12px",
        fontFamily: "monospace",
        fontSize: 12,
        lineHeight: 1.6,
        maxHeight: 320,
        overflowY: "auto",
        overflowX: "hidden",
        minHeight: 80,
        width: "100%",
        boxSizing: "border-box",
      }}>
        {lines.length === 0 && !running && (
          <span style={{ color: "var(--text-muted)" }}>No output yet.</span>
        )}
        {lines.map((l, i) => (
          <div key={i} style={{ color: color(l.event) }}>
            {l.data}
          </div>
        ))}
        {running && (
          <div style={{ color: "var(--text-muted)" }}>▌</div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
