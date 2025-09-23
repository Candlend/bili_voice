import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, connectDanmaku } from "../lib/api";

type Msg = {
  id: number;
  type: string;
  text: string;
  raw: any;
};

export default function PreviewPage() {
  const [roomId, setRoomId] = useState<number | "">("");
  const [connected, setConnected] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const nextId = useRef(1);
  const [err, setErr] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [msgs]);

  const connect = () => {
    if (!roomId || typeof roomId !== "number") {
      setErr("请输入有效的房间号");
      return;
    }
    setErr(null);
    try {
      const ws = connectDanmaku(roomId, (payload) => {
        const parsed = formatEvent(payload);
        setMsgs((m) => [
          ...m,
          {
            id: nextId.current++,
            type: payload.type,
            text: parsed.text,
            raw: payload,
          },
        ]);
      });
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onerror = () => setErr("连接错误或断开");
      wsRef.current = ws;
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const disconnect = () => {
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  };

  const clear = () => setMsgs([]);

  return (
    <div className="grid" style={{ gap: 16 }}>
      <header className="panel">
        <div style={{ fontWeight: 700, marginBottom: 8 }}>弹幕预览</div>
        <div className="row">
          <input
            className="input"
            placeholder="直播间房间号"
            value={roomId}
            onChange={(e) => {
              const v = e.target.value.trim();
              setRoomId(v === "" ? "" : Number(v));
            }}
          />
          {!connected ? (
            <button className="button" onClick={connect}>
              连接
            </button>
          ) : (
            <button className="button danger" onClick={disconnect}>
              断开
            </button>
          )}
          <button className="button secondary" onClick={clear}>
            清空
          </button>
          <span className="badge">{connected ? "已连接" : "未连接"}</span>
        </div>
        {err && <div className="small" style={{ color: "#ffb4b4" }}>{err}</div>}
      </header>

      <section className="panel">
        <div className="list" ref={listRef} style={{ height: 420 }}>
          {msgs.map((m) => (
            <div key={m.id} className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="badge">{m.type}</span>
                <details>
                  <summary className="small">原始数据</summary>
                  <pre className="small mono" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(m.raw, null, 2)}</pre>
                </details>
              </div>
              <div style={{ marginTop: 6 }}>{m.text}</div>
            </div>
          ))}
          {msgs.length === 0 && <div className="small">暂无消息，连接后开始显示。</div>}
        </div>
      </section>
    </div>
  );
}

function formatEvent(e: any): { text: string } {
  const t = e?.type;
  try {
    if (t === "DANMU_MSG") {
      const info = e.data.info;
      const text = info?.[1];
      const uname = info?.[2]?.[1];
      return { text: uname ? `${uname}: ${text}` : String(text ?? "") };
    }
    if (t === "SEND_GIFT" || t === "COMBO_SEND") {
      const d = e.data.data || {};
      const uname = d.uname || d.uname_text || d.uname_source || "";
      const gift = d.giftName || d.gift_name || "";
      const num = d.num || d.gift_num || 1;
      return { text: `${uname} 赠送 ${gift} × ${num}` };
    }
    if (t === "SUPER_CHAT_MESSAGE" || t === "SUPER_CHAT_MESSAGE_JPN") {
      const d = e.data.data || {};
      const uname = d.user_info?.uname || "";
      const msg = d.message || d.message_jpn || "";
      const price = d.price ?? d.rmb ?? d.price_safe;
      return { text: `SC ￥${price}: ${uname}：${msg}` };
    }
    if (t === "WELCOME" || t === "WELCOME_GUARD" || t === "INTERACT_WORD" || t === "ENTRY_EFFECT") {
      const d = e.data.data || e.data || {};
      const uname = d.uname || d.uname_text || d.un || d.username || "";
      return { text: `${uname} 进入直播间` };
    }
    if (t === "NOTICE_MSG") {
      const d = e.data.msg_self || e.data || {};
      const msg = d?.msg_common || d?.msg_self?.msg || d?.msg || "";
      return { text: `系统通知：${msg}` };
    }
  } catch {}
  return { text: JSON.stringify(e) };
}
