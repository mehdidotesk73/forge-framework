import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// ── Container ────────────────────────────────────────────────────────────────

export interface ContainerProps {
  /**
   * Direction children are laid out inside this container.
   * "column" → children stack vertically; the outer constraint is width (set via `size`).
   * "row"    → children sit side-by-side; the outer constraint is height (set via `size`).
   */
  direction?: "row" | "column";
  /**
   * Outer dimension descriptor.
   * • number  → flex ratio (flex: N), e.g. size={1} or size={2}
   * • string  → fixed value, e.g. size="220px" or size="100vh"
   *   - direction="column": sets width
   *   - direction="row":    sets height
   */
  size?: number | string;
  gap?: number | string;
  padding?: number | string;
  /** Draw a separator line between each direct child. */
  separator?: boolean;
  /** Children anchored to the start (top for column, left for row). */
  startChildren?: React.ReactNode;
  /** Children anchored to the end (bottom for column, right for row). A flex spacer is inserted before this group. */
  endChildren?: React.ReactNode;
  /** Shorthand — used as startChildren when startChildren/endChildren are absent. */
  children?: React.ReactNode;
  /** Grid layout mode. */
  layout?: "flex" | "grid";
  columns?: number;
  /**
   * Main-axis alignment of children.
   * Row containers accept: "left" | "center" | "right"
   * Column containers accept: "top" | "center" | "bottom"
   * Maps to CSS justify-content.
   */
  alignItems?: "left" | "center" | "right" | "top" | "bottom";
  /** Optional section title rendered at the top of the container. */
  title?: string;
  /** Title visual weight. "sm" = muted label; "md" = normal heading; "lg" = prominent heading. */
  titleSize?: "sm" | "md" | "lg";
  /** Optional icon rendered before the title text. */
  titleIcon?: string;
  /** CSS color for the title icon. Defaults to accent color for lg, muted for sm/md. */
  titleIconColor?: string;
  /** Background fill. "none" = transparent (default); "panel", "card", "surface" map to theme bg vars. */
  variant?: "none" | "panel" | "card" | "surface";
  className?: string;
  style?: React.CSSProperties;
}

const VARIANT_STYLE: Record<string, React.CSSProperties> = {
  panel: { background: "var(--bg-panel)", border: "1px solid var(--border)" },
  card: {
    background: "var(--bg-card)",
    border: "1px solid color-mix(in srgb, var(--border) 80%, transparent)",
  },
  surface: {
    background: "var(--bg-surface)",
    border:
      "1px solid color-mix(in srgb, var(--border) 120%, var(--bg-surface))",
  },
};

function toJustifyContent(
  alignItems: ContainerProps["alignItems"],
): React.CSSProperties["justifyContent"] | undefined {
  if (!alignItems) return undefined;
  if (alignItems === "center") return "center";
  if (alignItems === "left" || alignItems === "top") return "flex-start";
  if (alignItems === "right" || alignItems === "bottom") return "flex-end";
  return undefined;
}

const TITLE_STYLES: Record<"sm" | "md" | "lg", React.CSSProperties> = {
  sm: {
    fontSize: 11,
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 500,
  },
  md: {
    fontSize: 13,
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 700,
  },
  lg: {
    fontSize: 15,
    color: "var(--text)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 700,
  },
};

export function Container({
  direction = "row",
  size,
  gap = 0,
  padding = 0,
  separator = false,
  startChildren,
  endChildren,
  children,
  layout = "flex",
  columns = 2,
  alignItems,
  variant = "none",
  title,
  titleSize = "sm",
  titleIcon,
  titleIconColor,
  className = "",
  style: styleProp,
}: ContainerProps) {
  const bgStyle: React.CSSProperties =
    variant !== "none" ? VARIANT_STYLE[variant] : {};
  const sizeStyle: React.CSSProperties = {};
  if (size !== undefined) {
    if (typeof size === "number") {
      sizeStyle.flex = size;
    } else if (direction === "column") {
      sizeStyle.width = size;
      sizeStyle.flexShrink = 0;
    } else {
      sizeStyle.height = size;
      sizeStyle.flexShrink = 0;
    }
  }

  const titleEl = title ? (
    <div
      style={{
        ...TITLE_STYLES[titleSize],
        padding: "8px 0 4px",
        display: "flex",
        alignItems: "center",
        gap: 6,
        flexShrink: 0,
      }}
    >
      {titleIcon && (
        <span
          style={{
            color:
              titleIconColor ??
              (titleSize === "lg" ? "var(--accent)" : "inherit"),
          }}
        >
          {titleIcon}
        </span>
      )}
      {title}
    </div>
  ) : null;

  if (layout === "grid") {
    return (
      <div
        className={`forge-container ${className}`}
        style={{
          display: "flex",
          flexDirection: "column",
          padding,
          ...bgStyle,
          ...sizeStyle,
          ...styleProp,
        }}
      >
        {titleEl}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${columns}, 1fr)`,
            gap,
            justifyContent: toJustifyContent(alignItems),
            flex: 1,
          }}
        >
          {children ?? startChildren}
        </div>
      </div>
    );
  }

  // Inserts a zero-size border element between adjacent children when separator=true.
  const sepEl = (i: number) =>
    direction === "column" ? (
      <div
        key={`__sep_${i}`}
        style={{ height: 0, borderBottom: "1px solid var(--border)" }}
      />
    ) : (
      <div
        key={`__sep_${i}`}
        style={{ width: 0, borderRight: "1px solid var(--border)" }}
      />
    );

  // React.Children.toArray treats fragments as opaque single nodes; flatten them recursively.
  const flattenNodes = (nodes: React.ReactNode): React.ReactNode[] => {
    const result: React.ReactNode[] = [];
    React.Children.forEach(nodes, (child) => {
      if (React.isValidElement(child) && child.type === React.Fragment) {
        result.push(
          ...flattenNodes(
            (child.props as { children?: React.ReactNode }).children,
          ),
        );
      } else {
        result.push(child);
      }
    });
    return result;
  };

  const withSep = (nodes: React.ReactNode) => {
    if (!separator) return nodes;
    const arr = flattenNodes(nodes);
    return arr.map((child, i) =>
      i < arr.length - 1 ? [child, sepEl(i)] : [child],
    );
  };

  const hasGroups = startChildren !== undefined || endChildren !== undefined;

  // Simple mode: all children in one group
  if (!hasGroups) {
    if (titleEl) {
      return (
        <div
          className={`forge-container ${className}`}
          style={{
            display: "flex",
            flexDirection: "column",
            padding,
            ...bgStyle,
            ...sizeStyle,
            ...styleProp,
          }}
        >
          {titleEl}
          <div
            style={{
              display: "flex",
              flexDirection: direction,
              gap: separator ? 0 : gap,
              justifyContent: toJustifyContent(alignItems),
              flex: 1,
            }}
          >
            {withSep(children)}
          </div>
        </div>
      );
    }
    return (
      <div
        className={`forge-container ${className}`}
        style={{
          display: "flex",
          flexDirection: direction,
          gap: separator ? 0 : gap,
          padding,
          justifyContent: toJustifyContent(alignItems),
          ...bgStyle,
          ...sizeStyle,
          ...styleProp,
        }}
      >
        {withSep(children)}
      </div>
    );
  }

  // Start / end group mode
  const endBorder: React.CSSProperties = separator
    ? direction === "column"
      ? { borderTop: "1px solid var(--border)" }
      : { borderLeft: "1px solid var(--border)" }
    : {};

  return (
    <div
      className={`forge-container ${className}`}
      style={{
        display: "flex",
        flexDirection: titleEl ? "column" : direction,
        justifyContent: titleEl ? undefined : toJustifyContent(alignItems),
        padding,
        ...bgStyle,
        ...sizeStyle,
        ...styleProp,
      }}
    >
      {titleEl}
      <div
        style={{
          display: "flex",
          flexDirection: direction,
          flex: 1,
          gap: separator ? 0 : gap,
          justifyContent: toJustifyContent(alignItems),
        }}
      >
        {startChildren !== undefined && (
          <div style={{ display: "flex", flexDirection: direction }}>
            {withSep(startChildren)}
          </div>
        )}
        {endChildren !== undefined && <div style={{ flex: 1 }} />}
        {endChildren !== undefined && (
          <div
            style={{ display: "flex", flexDirection: direction, ...endBorder }}
          >
            {withSep(endChildren)}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Navbar ───────────────────────────────────────────────────────────────────

export interface NavItem {
  id?: string;
  label: string;
  icon?: string;
  href?: string;
  onClick?: () => void;
  active?: boolean;
}

export interface NavbarProps {
  title?: string;
  items?: NavItem[];
  /** "horizontal" (default) — top bar; "vertical" — side nav stacked column. */
  orientation?: "horizontal" | "vertical";
  /** Controls button padding, font size, and font weight. Defaults to "md". */
  size?: "sm" | "md" | "lg";
  rightContent?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

const NAVBAR_ITEM_SIZES = {
  sm: {
    fontSize: 11,
    padding: "5px 8px",
    iconSize: 12,
    gap: 7,
    borderRadius: 4,
  },
  md: {
    fontSize: 13,
    padding: "8px 10px",
    iconSize: 14,
    gap: 10,
    borderRadius: 6,
  },
  lg: {
    fontSize: 15,
    padding: "10px 12px",
    iconSize: 16,
    gap: 12,
    borderRadius: 7,
  },
} as const;

export function Navbar({
  title,
  items = [],
  orientation = "horizontal",
  size = "md",
  rightContent,
  className = "",
  style: styleProp,
}: NavbarProps) {
  if (orientation === "vertical") {
    const s = NAVBAR_ITEM_SIZES[size];
    return (
      <nav
        className={`forge-navbar forge-navbar-vertical ${className}`}
        style={{ display: "flex", flexDirection: "column", ...styleProp }}
      >
        {title && (
          <div
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              padding: "8px 16px 4px",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {title}
          </div>
        )}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 2,
            padding: "4px 8px",
          }}
        >
          {items.map((item, i) => (
            <button
              key={item.id ?? i}
              type="button"
              onClick={item.onClick}
              style={{
                display: "flex",
                alignItems: "center",
                gap: s.gap,
                width: "100%",
                padding: s.padding,
                borderRadius: s.borderRadius,
                border: "none",
                background: item.active ? "var(--bg-hover)" : "transparent",
                color: item.active ? "var(--text)" : "var(--text-muted)",
                fontSize: s.fontSize,
                fontWeight: item.active ? 600 : 400,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              {item.icon && (
                <span
                  style={{
                    fontSize: s.iconSize,
                    color: item.active ? "var(--accent)" : "inherit",
                  }}
                >
                  {item.icon}
                </span>
              )}
              {item.label}
            </button>
          ))}
        </div>
      </nav>
    );
  }

  return (
    <nav
      className={`forge-navbar forge-navbar-${size} ${className}`}
      style={styleProp}
    >
      {title && <div className="forge-navbar-title">{title}</div>}
      <div className="forge-navbar-items">
        {items.map((item, i) =>
          item.onClick ? (
            <button
              key={item.id ?? i}
              type="button"
              className={`forge-navbar-item ${item.active ? "forge-navbar-item-active" : ""}`}
              onClick={item.onClick}
            >
              {item.label}
            </button>
          ) : (
            <a
              key={item.id ?? i}
              href={item.href ?? "#"}
              className={`forge-navbar-item ${item.active ? "forge-navbar-item-active" : ""}`}
            >
              {item.label}
            </a>
          ),
        )}
      </div>
      {rightContent && <div className="forge-navbar-right">{rightContent}</div>}
    </nav>
  );
}

// ── Modal ────────────────────────────────────────────────────────────────────

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  size = "md",
  className = "",
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="forge-modal-overlay"
      ref={overlayRef}
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className={`forge-modal forge-modal-${size} ${className}`}>
        <div className="forge-modal-header">
          {title && <h2 className="forge-modal-title">{title}</h2>}
          <button type="button" className="forge-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="forge-modal-body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
