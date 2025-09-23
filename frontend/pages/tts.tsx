import React, { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";
import { useDanmaku } from "../components/DanmakuProvider";

export default function TTSPage() {
  const { roomId } = useDanmaku();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const wantFocusRef = useRef(false);

  const focusTA = useCallback(() => {
    try {
      taRef.current?.focus();
      const el = taRef.current as HTMLTextAreaElement | null;
      if (el) {
        const len = el.value.length;
        try {
          el.setSelectionRange(len, len);
        } catch {}
      }
    } catch {}
    try {
      setTimeout(() => {
        try {
          taRef.current?.focus();
          const el2 = taRef.current as HTMLTextAreaElement | null;
          if (el2) {
            const len2 = el2.value.length;
            try {
              el2.setSelectionRange(len2, len2);
            } catch {}
          }
        } catch {}
      }, 0);
    } catch {}
    try {
      if (typeof window !== "undefined" && "requestAnimationFrame" in window) {
        window.requestAnimationFrame(() => {
          try {
            taRef.current?.focus();
            const el3 = taRef.current as HTMLTextAreaElement | null;
            if (el3) {
              const len3 = el3.value.length;
              try {
                el3.setSelectionRange(len3, len3);
              } catch {}
            }
          } catch {}
        });
      }
    } catch {}
  }, []);

  const doSubmit = useCallback(async () => {
    const t = text.trim();
    if (!t) {
      setError("请输入要合成的文本");
      setMessage(null);
      // 保持输入框焦点
      focusTA();
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const rid = typeof roomId === "number" ? roomId : undefined;
      const res = await api.ttsEnqueue(t, "NORMAL", rid);
      if (!res.ok) {
        setError(res.message || "加入TTS队列失败");
      } else {
        const key = (res.data as any)?.key;
        setMessage(key ? `已加入队列（key: ${key}）` : "已加入队列");
        setText("");
        // 提交后自动聚焦输入框，方便继续输入（等解除禁用后再聚焦）
        wantFocusRef.current = true;
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setSubmitting(false);
      setTimeout(() => {
        if (wantFocusRef.current) {
          focusTA();
          wantFocusRef.current = false;
        }
      }, 0);
    }
  }, [text, roomId]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!submitting) doSubmit();
      }
    },
    [doSubmit, submitting]
  );

  return (
    <div className="grid" style={{ gap: 16 }}>
      <section className="panel">
        <div style={{ fontWeight: 700, marginBottom: 8 }}>语音合成</div>
        <div className="small" style={{ marginBottom: 12 }}>
          输入要合成的文本，点击“生成并播放”，或直接按 Enter 提交（Shift+Enter 换行）。
        </div>

        <div className="grid" style={{ gap: 12 }}>
          <textarea
            ref={taRef}
            autoFocus
            className="input mono"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            rows={8}
            placeholder="在此输入要合成的文本..."
          />

          <div className="row">
            <button
              className="button"
              onClick={() => doSubmit()}
              disabled={submitting}
              title="生成并播放（Enter 提交，Shift+Enter 换行）"
            >
              {submitting ? "正在加入..." : "生成并播放"}
            </button>
            {message ? (
              <span className="small" style={{ color: "#9fb0c0" }}>{message}</span>
            ) : null}
            {error ? (
              <span className="small" style={{ color: "var(--danger)" }}>{error}</span>
            ) : null}
          </div>

          <div className="small" style={{ color: "#9fb0c0" }}>
            提示：服务器端TTS需要已配置并可连接的 GPT-SoVITS WebUI；TTS需在“应用设置”中启用。
          </div>
        </div>
      </section>
    </div>
  );
}
