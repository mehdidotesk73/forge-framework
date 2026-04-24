import React from "react";

export interface MarkdownProps {
  /** Markdown string to render. Supports: headings (#/##/###), fenced code blocks (```), paragraphs. */
  children: string;
  className?: string;
}

type MNode =
  | { type: "h1" | "h2" | "h3"; text: string }
  | { type: "code"; content: string }
  | { type: "para"; text: string };

function parse(src: string): MNode[] {
  const lines = src.split("\n");
  const nodes: MNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("### ")) {
      nodes.push({ type: "h3", text: line.slice(4) });
      i++;
    } else if (line.startsWith("## ")) {
      nodes.push({ type: "h2", text: line.slice(3) });
      i++;
    } else if (line.startsWith("# ")) {
      nodes.push({ type: "h1", text: line.slice(2) });
      i++;
    } else if (line.trimStart().startsWith("```")) {
      i++;
      const codeLines: string[] = [];
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // consume closing ```
      nodes.push({ type: "code", content: codeLines.join("\n") });
    } else if (line.trim() === "") {
      i++;
    } else {
      const paraLines: string[] = [];
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        !lines[i].startsWith("#") &&
        !lines[i].trimStart().startsWith("```")
      ) {
        paraLines.push(lines[i]);
        i++;
      }
      if (paraLines.length > 0) {
        nodes.push({ type: "para", text: paraLines.join(" ") });
      }
    }
  }
  return nodes;
}

export function Markdown({ children, className = "" }: MarkdownProps) {
  const nodes = parse(children);
  return (
    <div
      className={`forge-markdown ${className}`}
      style={{ display: "flex", flexDirection: "column", gap: 6 }}
    >
      {nodes.map((node, i) => {
        switch (node.type) {
          case "h1":
            return (
              <h2
                key={i}
                style={{
                  margin: "12px 0 0",
                  fontSize: 15,
                  fontWeight: 700,
                  color: "var(--text)",
                }}
              >
                {node.text}
              </h2>
            );
          case "h2":
            return (
              <h3
                key={i}
                style={{
                  margin: "8px 0 0",
                  fontSize: 13,
                  fontWeight: 700,
                  color: "var(--text)",
                }}
              >
                {node.text}
              </h3>
            );
          case "h3":
            return (
              <h4
                key={i}
                style={{
                  margin: "12px 0 2px",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                {node.text}
              </h4>
            );
          case "code":
            return (
              <pre
                key={i}
                style={{
                  margin: 0,
                  padding: "10px 14px",
                  borderRadius: 6,
                  background: "var(--bg-hover)",
                  fontSize: 12,
                  fontFamily: "monospace",
                  color: "var(--text)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {node.content}
              </pre>
            );
          case "para":
            return (
              <p
                key={i}
                style={{ margin: 0, fontSize: 13, color: "var(--text-muted)" }}
              >
                {node.text}
              </p>
            );
        }
      })}
    </div>
  );
}
