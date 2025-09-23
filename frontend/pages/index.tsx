import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api, AppStatus } from "../lib/api";

export default function HomePage() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.status().then(setStatus).catch(() => {});
  }, []);
  
  const doLogout = async () => {
    setLoading(true);
    try {
      await api.logout();
      // 简单刷新状态
      const s = await api.status();
      setStatus(s);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="grid" style={{ gap: 20 }}>
      <header className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>BiliVoice</div>
            <div className="small">基于 GPT SoVITS 的 Bilibili 直播弹幕语音播报应用</div>
          </div>
          <div>
            {status?.login?.logged_in ? (
              <div className="row" style={{ gap: 8, alignItems: "center" }}>
                {status?.login?.avatar_url && (
                  <img
                    src={status.login.avatar_url}
                    referrerPolicy="no-referrer"
                    alt="avatar"
                    style={{ width: 28, height: 28, borderRadius: 999, border: "1px solid var(--border)" }}
                  />
                )}
                <span className="small">
                  {status?.login?.username || "已登录"}
                  {status?.login?.uid ? ` (UID: ${status.login.uid})` : ""}
                </span>
                <button className="button secondary" onClick={doLogout} disabled={loading}>
                  退出登录
                </button>
              </div>
            ) : (
              <span className="badge" style={{ color: "#ffb4b4", background: "#2b1919", borderColor: "#3a2323" }}>
                未登录
              </span>
            )}
          </div>
        </div>
      </header>

      <section className="panel">
        <div className="grid" style={{ gap: 12 }}>
          <div className="row" style={{ gap: 12 }}>
            <Link href="/login" className="button">
              账号登录
            </Link>
            <Link href="/settings" className="button">
              应用设置
            </Link>
            <Link href="/danmaku" className="button">
              弹幕播报
            </Link>
          </div>
          <div className="small">
            使用说明：
            <ol>
              <li>先进入“账号登录”完成登录</li>
              <li>在“应用设置”中设置需要播报的消息类型和相关设置</li>
              <li>进入“弹幕播报”，输入直播间房间号并连接，开始播报实时消息</li>
            </ol>
          </div>
        </div>
      </section>
    </div>
  );
}
