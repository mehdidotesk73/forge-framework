/**
 * Layout widgets: Container, Navbar, Modal
 */
import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

// ── Container ────────────────────────────────────────────────────────────────

export interface ContainerProps {
  layout?: "flex" | "grid";
  direction?: "row" | "column";
  gap?: number | string;
  columns?: number;
  padding?: number | string;
  children?: React.ReactNode;
  className?: string;
}

export function Container({
  layout = "flex",
  direction = "row",
  gap = "1rem",
  columns = 2,
  padding = "1rem",
  children,
  className = "",
}: ContainerProps) {
  const style: React.CSSProperties =
    layout === "grid"
      ? {
          display: "grid",
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap,
          padding,
        }
      : {
          display: "flex",
          flexDirection: direction,
          gap,
          padding,
        };

  return (
    <div className={`forge-container ${className}`} style={style}>
      {children}
    </div>
  );
}

// ── Navbar ───────────────────────────────────────────────────────────────────

export interface NavItem {
  label: string;
  href?: string;
  onClick?: () => void;
  active?: boolean;
}

export interface NavbarProps {
  title?: string;
  items?: NavItem[];
  rightContent?: React.ReactNode;
  className?: string;
}

export function Navbar({ title, items = [], rightContent, className = "" }: NavbarProps) {
  return (
    <nav className={`forge-navbar ${className}`}>
      {title && <div className="forge-navbar-title">{title}</div>}
      <div className="forge-navbar-items">
        {items.map((item, i) =>
          item.onClick ? (
            <button
              key={i}
              type="button"
              className={`forge-navbar-item ${item.active ? "forge-navbar-item-active" : ""}`}
              onClick={item.onClick}
            >
              {item.label}
            </button>
          ) : (
            <a
              key={i}
              href={item.href ?? "#"}
              className={`forge-navbar-item ${item.active ? "forge-navbar-item-active" : ""}`}
            >
              {item.label}
            </a>
          )
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

export function Modal({ open, onClose, title, children, size = "md", className = "" }: ModalProps) {
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
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className={`forge-modal forge-modal-${size} ${className}`}>
        <div className="forge-modal-header">
          {title && <h2 className="forge-modal-title">{title}</h2>}
          <button type="button" className="forge-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="forge-modal-body">{children}</div>
      </div>
    </div>,
    document.body
  );
}
