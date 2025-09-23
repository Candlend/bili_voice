import React, { useEffect, useMemo, useRef, useState } from "react";

type LogItem = {
  type: "LOG";
  ts: number;
  time: string;
  level: string;
  logger: string;
  message: string;
  pathname?: string;
  lineno?: number;
  funcName?: string;
};

export default function LogsPage() {
  const [connected, setConnected] = useState(false);
  const [items, setItems] = useState<LogItem[]>([]);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [enableBottomBtn, setEnableBottomBtn] = useState(false);
  const [search, setSearch] = useState("");
  const [levels, setLevels] = useState<Record<string, boolean>>({
    DEBUG: true,
    INFO: true,
    WARNING: true,
    ERROR: true,
    CRITICAL: true,
  });

  const listRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Scroll listener
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const onScroll = () => {
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
      setStickToBottom(atBottom);
      setEnableBottomBtn(!atBottom);
    };
    el.addEventListener("scroll", onScroll);
    onScroll();
    return () => {
      el.removeEventListener("scroll", onScroll);
    };
  }, []);

  // Auto stick to bottom
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (stickToBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [items, stickToBottom]);

  // Connect WS
  useEffect(() => {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${location.host}/ws/logs`;
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setConnected(false);
      ws.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data);
          if (payload?.type === "LOG") {
            const li: LogItem = payload as LogItem;
            setItems((prev) => {
              const next = [...prev, li];
              // Cap to avoid memory blow-up
              return next.length > 2000 ? next.slice(next.length - 2000) : next;
            });
          }
        } catch {
          // ignore misc text frames
        }
      };
    } catch {
      // ignore
    }
    return () => {
      try {
        wsRef.current?.close();
      } catch {}
      wsRef.current = null;
      setConnected(false);
    };
  }, []);

  const filtered = useMemo(() => {
    const s = (search || "").trim().toLowerCase();
    return items.filter((it) => {
      if (!levels[(it.level || "").toUpperCase()]) return false;
      if (!s) return true;
      const txt =
        `${it.time} ${it.level} ${it.logger} ${it.message} ${it.pathname || ""} ${it.funcName || ""}`.toLowerCase();
      return txt.includes(s);
    });
  }, [items, levels, search]);

  const levelBadgeStyle = (lvl: string): React.CSSProperties => {
    const L = (lvl || "").toUpperCase();
    if (L === "DEBUG") return { color: "#9fb0c0", background: "#0d1e2a", borderColor: "#1a2f3d" };
    if (L === "INFO") return { color: "#cfe3ff", background: "#0f1c2b", borderColor: "#1f3a57" };
    if (L === "WARNING" || L === "WARN")
      return { color: "#ffe6b3", background: "#2b2410", borderColor: "#403817" };
    if (L === "ERROR")
      return { color: "#ffb4b4", background: "#2b1919", borderColor: "#3a2323" };
    if (L === "CRITICAL")
      return { color: "#ffd6f2", background: "#2b1021", borderColor: "#40172f" };
    return { color: "#cfe3ff", background: "#0f1c2b", borderColor: "#1f3a57" };
  };

  const toggleLevel = (lvl: string) => {
    setLevels((prev) => ({ ...prev, [lvl]: !prev[lvl] }));
  };

  return (
    <div className="grid" style={{ gap: 16 }}>
      <header className="panel">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div className="row" style={{ alignItems: "center", gap: 12 }}>
            <div style={{ fontWeight: 700 }}>运行日志</div>
            <span className="badge">{connected ? "已连接" : "未连接"}</span>
          </div>
          <div className="row" style={{ gap: 12 }}>
            <input
              className="input"
              placeholder="搜索关键字"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 240 }}
            />
            <button className="button secondary" onClick={() => setItems([])}>
              清空
            </button>
          </div>
        </div>
        <div className="row" style={{ gap: 12, marginTop: 8, flexWrap: "wrap" }}>
          {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((lvl) => (
            <label key={lvl} className="row" style={{ alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                checked={!!levels[lvl]}
                onChange={() => toggleLevel(lvl)}
              />
              <span className="badge" style={levelBadgeStyle(lvl)}>{lvl}</span>
            </label>
          ))}
        </div>
      </header>

      <section className="panel">
        <div style={{ position: "relative" }}>
          <div className="list" ref={listRef} style={{ height: "calc(100vh - 260px)", maxHeight: "none" }}>
            {filtered.map((m, idx) => (
              <div key={idx} className="card">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <div className="row" style={{ gap: 8, alignItems: "center" }}>
                    <span className="badge small" style={levelBadgeStyle(m.level)}>{m.level}</span>
                    <span className="small mono">{m.time}</span>
                    <span className="small mono" style={{ opacity: 0.8 }}>{m.logger}</span>
                  </div>
                </div>
                <div style={{ marginTop: 6 }} className="wrap small mono">
                  {m.message}
                </div>
                {(m.pathname || m.funcName || m.lineno) && (
                  <div className="small mono" style={{ marginTop: 4, opacity: 0.7 }}>
                    {m.pathname || ""}{m.funcName ? `#${m.funcName}` : ""}{m.lineno ? `:${m.lineno}` : ""}
                  </div>
                )}
              </div>
            ))}
            {filtered.length === 0 && <div className="small">暂无日志输出。</div>}
          </div>
          {enableBottomBtn && (
            <button
              className="button"
              onClick={() => {
                const el = listRef.current;
                if (el) el.scrollTop = el.scrollHeight;
              }}
              style={{ position: "absolute", right: 8, bottom: 8, zIndex: 1 }}
            >
              回到底部
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
