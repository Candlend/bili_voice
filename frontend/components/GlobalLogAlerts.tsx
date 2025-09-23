import React, { useEffect, useRef, useState } from "react";

type LogPayload = {
  type?: string;
  ts?: number;
  time?: string;
  level?: string; // "INFO" | "WARNING" | "ERROR" | "CRITICAL" | ...
  logger?: string;
  message?: string;
  pathname?: string;
  lineno?: number;
  funcName?: string;
};

type AlertItem = {
  id: number;
  level: "WARNING" | "ERROR" | "CRITICAL";
  text: string;
};

const levelToColor: Record<AlertItem["level"], { fg: string; bg: string; border: string; label: string }> = {
  WARNING: { fg: "#fff3cd", bg: "#3a2f09", border: "#5a4a0e", label: "警告" },
  ERROR: { fg: "#ffcccc", bg: "#3a0f0f", border: "#5a1818", label: "错误" },
  CRITICAL: { fg: "#ffd6e0", bg: "#3a0716", border: "#5a0b21", label: "严重" },
};

export default function GlobalLogAlerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const nextId = useRef(1);

  useEffect(() => {
    try {
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${location.host}/ws/logs`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const payload: LogPayload = JSON.parse(ev.data);
          if (payload?.type === "LOG") {
            const lvl = String(payload.level || "").toUpperCase();
            if (lvl === "WARNING" || lvl === "ERROR" || lvl === "CRITICAL") {
              const id = nextId.current++;
              const msg = payload.message || `${payload.logger || ""}: ${payload.level || ""}`;
              const item: AlertItem = { id, level: lvl as any, text: msg };
              setAlerts((prev) => [...prev, item]);
              // auto dismiss after 5s
              setTimeout(() => {
                setAlerts((prev) => prev.filter((a) => a.id !== id));
              }, 5000);
            }
          }
        } catch {
          // ignore parse error
        }
      };
      ws.onerror = () => {
        // ignore
      };
      ws.onclose = () => {
        wsRef.current = null;
      };
    } catch {
      // ignore
    }
    return () => {
      try {
        wsRef.current?.close();
      } catch {}
      wsRef.current = null;
    };
  }, []);

  if (alerts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 12,
        right: 12,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "none",
      }}
    >
      {alerts.map((a) => {
        const c = levelToColor[a.level];
        return (
          <div
            key={a.id}
            onClick={() => setAlerts((prev) => prev.filter((x) => x.id !== a.id))}
            title="点击关闭"
            style={{
              pointerEvents: "auto",
              maxWidth: 420,
              border: `1px solid ${c.border}`,
              background: c.bg,
              color: c.fg,
              padding: "8px 12px",
              borderRadius: 8,
              boxShadow: "0 4px 12px rgba(0,0,0,0.35)",
              userSelect: "none",
              cursor: "pointer",
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{c.label}</div>
            <div className="small" style={{ lineHeight: 1.35, wordBreak: "break-word", whiteSpace: "pre-wrap" }}>
              {a.text}
            </div>
          </div>
        );
      })}
    </div>
  );
}
