import React, { createContext, useCallback, useContext, useRef, useState, useEffect } from "react";
import { connectDanmaku, api } from "../lib/api";

export type DanmakuMsg = {
  id: number;
  type: string;
  text: string;
  raw: any;
  ttsKey?: string | null;
  ttsStatus?: "pending" | "playing" | "done" | "cancelled";
};

type DanmakuContextValue = {
  roomId: number | "";
  setRoomId: (v: number | "") => void;
  connected: boolean;
  msgs: DanmakuMsg[];
  err: string | null;
  connect: () => void;
  disconnect: () => void;
  clear: () => void;
};

const DanmakuContext = createContext<DanmakuContextValue | null>(null);

export function DanmakuProvider({ children }: { children: React.ReactNode }) {
  const [roomId, _setRoomId] = useState<number | "">("");
  const MAX_MSGS = 1000; // cap message count to avoid memory explosion

  // 初始化：优先从本地缓存恢复；若不可用（例如 pywebview 环境），则回退到后端保存的 last_room_id
  useEffect(() => {
    let mounted = true;
    (async () => {
      // 1) localStorage
      if (typeof window !== "undefined") {
        try {
          const saved = localStorage.getItem("room_id");
          if (saved) {
            const n = Number(saved);
            if (mounted) _setRoomId(Number.isFinite(n) && n > 0 ? n : "");
            return;
          }
        } catch {}
      }
      // 2) fallback to server
      try {
        const s = await api.getSettings();
        if (mounted) {
          const n = s?.last_room_id;
          if (typeof n === "number" && Number.isFinite(n) && n > 0) {
            _setRoomId(n);
          }
        }
      } catch {}
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // 包装 setter：同步到本地缓存
  const setRoomId = useCallback((v: number | "") => {
    _setRoomId(v);
    try {
      if (typeof window !== "undefined") {
        if (v === "") {
          localStorage.removeItem("room_id");
        } else {
          localStorage.setItem("room_id", String(v));
        }
      }
    } catch {}
    // 同步到后端，兼容 pywebview 等环境的本地存储不持久问题
    try {
      if (typeof v === "number" && Number.isFinite(v) && v > 0) {
        api.saveLastRoomId(v).catch(() => {});
      }
    } catch {}
  }, []);
  const [connected, setConnected] = useState(false);
  const [msgs, setMsgs] = useState<DanmakuMsg[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const nextId = useRef(1);
  const keyToIdRef = useRef<Map<string, number>>(new Map());
  const pendingStatusRef = useRef<Map<string, string>>(new Map());


  const handleMessage = useCallback((payload: any) => {
    const type = payload?.type || payload?.cmd || "UNKNOWN";

    // Handle TTS status events
    if (type === "TTS_STATUS") {
      const key: string | undefined = payload?.tts_key ?? payload?.key ?? undefined;
      const statusRaw = payload?.status;
      const status = typeof statusRaw === "string" ? (statusRaw.toLowerCase() as "pending" | "playing" | "done" | "cancelled") : undefined;
      console.debug("[WS] TTS_STATUS", { key, status });
      if (key && status) {
        const id = keyToIdRef.current.get(key);
        if (id) {
          setMsgs((prev) =>
            prev.map((m) => (m.id === id ? { ...m, ttsStatus: status } : m))
          );
        } else {
          // cache status if payload not arrived yet
          pendingStatusRef.current.set(key, status);
        }
      }
      return;
    }

    // Normal payload message
    const text = typeof payload?.text === "string" ? payload.text : JSON.stringify(payload);
    const raw = payload?.raw ?? payload;
    const ttsKey: string | null = payload?.tts_key ?? null;

    // initialize status from cache if exists
    let initStatus: "pending" | "playing" | "done" | "cancelled" | undefined = undefined;
    if (ttsKey && pendingStatusRef.current.has(ttsKey)) {
      const s = pendingStatusRef.current.get(ttsKey);
      if (s === "pending" || s === "playing" || s === "done" || s === "cancelled") {
        initStatus = s as any;
      }
      pendingStatusRef.current.delete(ttsKey);
    }

    const msg: DanmakuMsg = {
      id: nextId.current++,
      type,
      text,
      raw,
      ttsKey,
      ttsStatus: initStatus,
    };

    // map key -> id for subsequent status updates
    if (ttsKey) {
      keyToIdRef.current.set(ttsKey, msg.id);
    }

    console.debug("[WS] TTS_PAYLOAD", { type, ttsKey, text: msg.text });

    setMsgs((prev) => {
      const next = [...prev, msg];
      return next.length > MAX_MSGS ? next.slice(next.length - MAX_MSGS) : next;
    });
  }, []);

  const connect = useCallback(() => {
    if (!roomId || typeof roomId !== "number") {
      setErr("请输入有效的房间号");
      return;
    }
    setErr(null);
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.close();
        } catch {}
      }
      const ws = connectDanmaku(roomId, handleMessage);
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setErr("连接错误或断开");
      wsRef.current = ws;
    } catch (e: any) {
      setErr(e?.message || String(e));
    }
  }, [roomId, handleMessage]);

  const disconnect = useCallback(() => {
    try {
      wsRef.current?.close();
    } finally {
      wsRef.current = null;
      setConnected(false);
    }
  }, []);

  const clear = useCallback(() => {
    setMsgs([]);
    try { keyToIdRef.current.clear(); } catch {}
    try { pendingStatusRef.current.clear(); } catch {}
  }, []);

  const value: DanmakuContextValue = {
    roomId,
    setRoomId,
    connected,
    msgs,
    err,
    connect,
    disconnect,
    clear,
  };

  return <DanmakuContext.Provider value={value}>{children}</DanmakuContext.Provider>;
}

export function useDanmaku(): DanmakuContextValue {
  const ctx = useContext(DanmakuContext);
  if (!ctx) {
    throw new Error("useDanmaku must be used within DanmakuProvider");
  }
  return ctx;
}
