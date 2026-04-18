import React, { useState } from "react";
import type { ForgeAction } from "../types/index.js";

export interface ButtonConfig {
  label?: string;
  icon?: React.ReactNode;
  tooltip?: string;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean;
  action: ForgeAction;
}

export interface ButtonGroupProps {
  buttons: ButtonConfig[];
  orientation?: "horizontal" | "vertical";
  size?: "sm" | "md" | "lg";
  renderMode?: "inline" | "menu";
  opacity?: number;
  onAction?: (action: ForgeAction) => void;
  className?: string;
}

export function ButtonGroup({
  buttons,
  orientation = "horizontal",
  size = "md",
  renderMode = "inline",
  opacity = 1,
  onAction,
  className = "",
}: ButtonGroupProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  const handleAction = (action: ForgeAction) => {
    onAction?.(action);
    if (action.kind === "ui") {
      action.handler();
    }
    setMenuOpen(false);
  };

  if (renderMode === "menu") {
    return (
      <div className={`forge-button-group forge-button-menu ${className}`} style={{ opacity }}>
        <button
          type="button"
          className={`forge-btn forge-btn-${size} forge-btn-secondary`}
          onClick={() => setMenuOpen((o) => !o)}
        >
          ⋮ Actions
        </button>
        {menuOpen && (
          <div className="forge-menu-dropdown">
            {buttons.map((btn, i) => (
              <button
                key={i}
                type="button"
                className={`forge-menu-item forge-btn-${btn.variant ?? "ghost"}`}
                disabled={btn.disabled}
                onClick={() => handleAction(btn.action)}
                title={btn.tooltip}
              >
                {btn.icon && <span className="forge-btn-icon">{btn.icon}</span>}
                {btn.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={`forge-button-group forge-orientation-${orientation} ${className}`}
      style={{ opacity }}
    >
      {buttons.map((btn, i) => (
        <button
          key={i}
          type="button"
          className={`forge-btn forge-btn-${size} forge-btn-${btn.variant ?? "primary"}`}
          disabled={btn.disabled}
          onClick={() => handleAction(btn.action)}
          title={btn.tooltip}
        >
          {btn.icon && <span className="forge-btn-icon">{btn.icon}</span>}
          {btn.label}
        </button>
      ))}
    </div>
  );
}
