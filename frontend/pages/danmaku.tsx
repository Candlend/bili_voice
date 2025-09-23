import React, { useEffect, useRef, useState } from "react";
import { useDanmaku } from "../components/DanmakuProvider";

export default function DanmakuPage() {
  const { roomId, setRoomId, connected, msgs, err, connect, disconnect, clear } = useDanmaku();
  const listRef = useRef<HTMLDivElement | null>(null);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [enableBottomBtn, setEnableBottomBtn] = useState(false);


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

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    if (stickToBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [msgs, stickToBottom]);

  return (
    <div className="grid" style={{ gap: 16 }}>
      <header className="panel">
        <div style={{ fontWeight: 700, marginBottom: 8 }}>弹幕播报</div>
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
        {err && (
          <div className="small" style={{ color: "#ffb4b4" }}>
            {err}
          </div>
        )}
      </header>

      <section className="panel">
        <div style={{ position: "relative" }}>
          <div className="list" ref={listRef} style={{ height: "calc(100vh - 260px)", maxHeight: "none" }}>
          {msgs.map((m) => (
            <div key={m.id} className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div className="row" style={{ gap: 8, alignItems: "center" }}>
                  <span className="badge">{m.type}</span>
                  {(m.ttsStatus === "pending" || m.ttsStatus === "playing") && (
                    <span
                      className="badge"
                      style={
                        m.ttsStatus === "playing"
                          ? { color: "#b3ffd9", background: "#0f2b1f", borderColor: "#174035" }
                          : { color: "#ffe6b3", background: "#2b2410", borderColor: "#403817" }
                      }
                    >
                      {m.ttsStatus === "playing" ? "播报中" : "待播报"}
                    </span>
                  )}
                </div>
                <details>
                  <summary className="small">原始数据</summary>
                  <pre className="small mono wrap">
                    {JSON.stringify(m.raw, null, 2)}
                  </pre>
                </details>
              </div>
              <div style={{ marginTop: 6 }} className="wrap">{m.text}</div>
            </div>
          ))}
          {msgs.length === 0 && <div className="small">暂无消息，连接后开始播报。</div>}
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
