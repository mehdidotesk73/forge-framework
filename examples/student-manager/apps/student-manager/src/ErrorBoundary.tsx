import React from "react";

interface State { error: Error | null; }

export class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, color: "#e06070", fontFamily: "monospace", background: "#1a1a2e", minHeight: "100vh" }}>
          <strong>Something went wrong:</strong>
          <pre style={{ marginTop: 12, whiteSpace: "pre-wrap", fontSize: 13 }}>
            {this.state.error.message}
          </pre>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            style={{ marginTop: 16, padding: "8px 16px", background: "#e8833a", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer" }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
