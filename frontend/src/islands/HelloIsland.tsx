import { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  version: string;
}

export function HelloIsland() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: HealthResponse) => setHealth(data))
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return <div style={{ padding: "1rem", color: "#c00" }}>API error: {error}</div>;
  }

  if (!health) {
    return <div style={{ padding: "1rem", opacity: 0.5 }}>Connecting...</div>;
  }

  return (
    <div
      style={{
        padding: "0.75rem 1rem",
        background: "var(--bn-colour-surface-alt, #f0f0f0)",
        borderRadius: "6px",
        fontSize: "0.85rem",
        marginTop: "1rem",
      }}
    >
      React connected — Bristlenose v{health.version}
    </div>
  );
}
