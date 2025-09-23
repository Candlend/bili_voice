import React, { useEffect, useMemo, useRef, useState } from "react";
import { api, AppStatus, QRStatusResponse, StartGeetestResponse } from "../lib/api";

type Tab = "qr" | "password" | "sms";

export default function LoginPage() {
  const [tab, setTab] = useState<Tab>("qr");
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Poll app status
  useEffect(() => {
    let stop = false;
    const run = async () => {
      while (!stop) {
        try {
          const s = await api.status();
          if (!stop) setStatus(s);
        } catch (e: any) {
          // ignore
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
    };
    run();
    return () => {
      stop = true;
    };
  }, []);
  
  const doLogout = async () => {
    setErr(null);
    setLoading(true);
    try {
      await api.logout();
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="grid" style={{ gap: 20 }}>
      <header className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>账号登录</div>
            <div className="small">支持二维码、短信验证码、用户名密码登录</div>
          </div>
          <div>
            {status?.login?.logged_in ? (
              <div className="row" style={{ gap: 8, alignItems: "center" }}>
                {status?.login?.avatar_url && (
                  <img
                    src={status.login.avatar_url}
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
        <div className="hr" />
        <div className="row">
          <button className="button" onClick={() => setTab("qr")} disabled={tab === "qr"}>
            二维码登录
          </button>
          <button className="button" onClick={() => setTab("sms")} disabled={tab === "sms"}>
            短信验证码登录
          </button>
          <button className="button" onClick={() => setTab("password")} disabled={tab === "password"}>
            用户名密码登录
          </button>
        </div>
      </header>

      {tab === "qr" && <QRLogin />}
      {tab === "sms" && <SMSLogin />}
      {tab === "password" && <PasswordLogin />}

      {err && (
        <div className="panel" style={{ borderColor: "#3a2323" }}>
          <div className="small" style={{ color: "#ffb4b4" }}>
            {err}
          </div>
        </div>
      )}
    </div>
  );
}

function QRLogin() {
  const [token, setToken] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [state, setState] = useState<QRStatusResponse["state"]>("PENDING");
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const start = async () => {
    setErr(null);
    setDone(false);
    setState("PENDING");
    try {
      const r = await api.qrStart();
      setToken(r.token);
      setQr(r.qrcode_base64);
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  // poll
  useEffect(() => {
    if (!token) return;
    let stop = false;
    const loop = async () => {
      while (!stop && !done) {
        try {
          const s = await api.qrStatus(token);
          setState(s.state);
          setDone(s.done);
        } catch (e: any) {
          setErr(e.message || String(e));
          break;
        }
        await new Promise((r) => setTimeout(r, 1200));
      }
    };
    loop();
    return () => {
      stop = true;
    };
  }, [token, done]);

  return (
    <section className="panel">
      <div style={{ fontWeight: 700, marginBottom: 8 }}>二维码登录</div>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div style={{ display: "grid", gap: 8 }}>
          {qr ? (
            <img className="qr" src={qr} alt="QR code" />
          ) : (
            <div className="qr" style={{ display: "grid", placeItems: "center", color: "var(--muted)" }}>
              点击“生成二维码”
            </div>
          )}
          <div className="row">
            <button className="button" onClick={start}>
              生成二维码
            </button>
            <StatusPill state={state} done={done} />
          </div>
        </div>
        <ul className="small" style={{ margin: 0 }}>
          <li>点击“生成二维码”，使用B站手机App扫码并确认</li>
          <li>状态变为 DONE 即登录完成</li>
        </ul>
      </div>
      {err && <div className="small" style={{ color: "#ffb4b4" }}>{err}</div>}
    </section>
  );
}

function PasswordLogin() {
  const [phase, setPhase] = useState<"idle" | "login_geetest" | "login_fill" | "need_verify" | "verify_geetest" | "verify_fill" | "done">("idle");
  const [geetest, setGeetest] = useState<StartGeetestResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const startGeetest = async () => {
    setErr(null);
    try {
      const r = await api.geetestStart("LOGIN");
      setGeetest(r);
      setToken(r.token);
      setPhase("login_geetest");
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const checkGeetestDone = async () => {
    if (!token) return;
    setErr(null);
    try {
      const r = await api.geetestDone(token);
      if (r.ok) {
        setPhase("login_fill");
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const submitLogin = async () => {
    if (!token) return;
    setErr(null);
    try {
      const r = await api.loginPassword(token, username, password);
      if (r.data?.status === "DONE") {
        setPhase("done");
      } else {
        // need verify
        const g = await api.geetestStart("VERIFY", token);
        setGeetest(g);
        setPhase("verify_geetest");
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const checkVerifyGeetestDone = async () => {
    if (!token) return;
    setErr(null);
    try {
      const r = await api.geetestDone(token);
      if (r.ok) {
        await api.verifySend(token);
        setPhase("verify_fill");
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const completeVerify = async () => {
    if (!token) return;
    setErr(null);
    try {
      await api.verifyComplete(token, verifyCode);
      setPhase("done");
      await api.geetestStop(token).catch(() => {});
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  return (
    <section className="panel">
      <div style={{ fontWeight: 700, marginBottom: 8 }}>用户名密码登录</div>
      {phase === "idle" && (
        <div className="row">
          <button className="button" onClick={startGeetest}>
            人机验证
          </button>
        </div>
      )}
      {phase === "login_geetest" && geetest && (
        <GeetestPanel url={geetest.geetest_url} onDone={checkGeetestDone} token={geetest.token} />
      )}
      {phase === "login_fill" && (
        <div className="grid">
          <div className="row">
            <input className="input" placeholder="手机号/邮箱" value={username} onChange={(e) => setUsername(e.target.value)} />
            <input className="input" placeholder="密码" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button className="button" onClick={submitLogin}>
              登录
            </button>
          </div>
          <div className="small">如需安全验证，会自动进入二次验证流程</div>
        </div>
      )}
      {phase === "verify_geetest" && geetest && (
        <GeetestPanel url={geetest.geetest_url} onDone={checkVerifyGeetestDone} token={geetest.token} />
      )}
      {phase === "verify_fill" && (
        <div className="row">
          <input className="input" placeholder="短信验证码" value={verifyCode} onChange={(e) => setVerifyCode(e.target.value)} />
          <button className="button" onClick={completeVerify}>
            完成验证
          </button>
        </div>
      )}
      {phase === "done" && <div className="badge">登录完成</div>}
      {err && <div className="small" style={{ color: "#ffb4b4" }}>{err}</div>}
    </section>
  );
}

function SMSLogin() {
  const [phase, setPhase] = useState<"idle" | "login_geetest" | "login_fill" | "need_verify" | "verify_geetest" | "verify_fill" | "done">("idle");
  const [geetest, setGeetest] = useState<StartGeetestResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [captchaId, setCaptchaId] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const startGeetest = async () => {
    setErr(null);
    try {
      const r = await api.geetestStart("LOGIN");
      setGeetest(r);
      setToken(r.token);
      setPhase("login_geetest");
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const checkGeetestDone = async () => {
    if (!token) return;
    setErr(null);
    try {
      const r = await api.geetestDone(token);
      if (r.ok) {
        setPhase("login_fill");
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const sendSms = async () => {
    if (!token) return;
    setErr(null);
    try {
      const r = await api.smsSend(token, phone, "+86");
      setCaptchaId(r.captcha_id);
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const verifySms = async () => {
    if (!token || !captchaId) return;
    setErr(null);
    try {
      const r = await api.smsVerify(token, phone, code, captchaId, "+86");
      if (r.data?.status === "DONE") {
        setPhase("done");
      } else {
        const g = await api.geetestStart("VERIFY", token);
        setGeetest(g);
        setPhase("verify_geetest");
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const checkVerifyGeetestDone = async () => {
    if (!token) return;
    setErr(null);
    try {
      const r = await api.geetestDone(token);
      if (r.ok) {
        await api.verifySend(token);
        setPhase("verify_fill");
      }
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  const completeVerify = async () => {
    if (!token) return;
    setErr(null);
    try {
      await api.verifyComplete(token, verifyCode);
      setPhase("done");
      await api.geetestStop(token).catch(() => {});
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  return (
    <section className="panel">
      <div style={{ fontWeight: 700, marginBottom: 8 }}>短信验证码登录</div>
      {phase === "idle" && (
        <div className="row">
          <button className="button" onClick={startGeetest}>
            人机验证
          </button>
        </div>
      )}
      {phase === "login_geetest" && geetest && (
        <GeetestPanel url={geetest.geetest_url} onDone={checkGeetestDone} token={geetest.token} />
      )}
      {phase === "login_fill" && (
        <div className="row">
          <input className="input" placeholder="手机号（+86）" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <button className="button" onClick={sendSms}>
            发送短信验证码
          </button>
          <input className="input" placeholder="验证码" value={code} onChange={(e) => setCode(e.target.value)} />
          <button className="button" onClick={verifySms}>
            登录
          </button>
        </div>
      )}
      {phase === "verify_geetest" && geetest && (
        <GeetestPanel url={geetest.geetest_url} onDone={checkVerifyGeetestDone} token={geetest.token} />
      )}
      {phase === "verify_fill" && (
        <div className="row">
          <input className="input" placeholder="短信验证码" value={verifyCode} onChange={(e) => setVerifyCode(e.target.value)} />
          <button className="button" onClick={completeVerify}>
            完成验证
          </button>
        </div>
      )}
      {phase === "done" && <div className="badge">登录完成</div>}
      {err && <div className="small" style={{ color: "#ffb4b4" }}>{err}</div>}
    </section>
  );
}

function GeetestPanel({ url, onDone, token }: { url: string; onDone: () => void; token: string }) {
  return (
    <div className="grid">
      <div className="small">请在下方窗口完成验证码</div>
      <iframe src={url} style={{ width: "100%", height: 420, border: "1px solid var(--border)", borderRadius: 10 }} />
      <div className="row">
        <button className="button" onClick={onDone}>
          我已完成
        </button>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onDone();
          }}
        >
          <button className="button secondary" type="submit">
            刷新状态
          </button>
        </form>
      </div>
      <div className="small">若无法播报，请点击在外部浏览器打开：<a href={url} target="_blank" rel="noreferrer">{url}</a></div>
    </div>
  );
}

function StatusPill({ state, done }: { state: QRStatusResponse["state"]; done: boolean }) {
  const color = useMemo(() => {
    switch (state) {
      case "SCAN":
        return "#f59e0b";
      case "CONF":
        return "#22c55e";
      case "DONE":
        return "#22c55e";
      case "TIMEOUT":
        return "#ff4d4f";
      default:
        return "#9fb0c0";
    }
  }, [state]);
  return (
    <span className="badge" style={{ color, borderColor: "rgba(255,255,255,0.08)", background: "rgba(0,0,0,0.15)" }}>
      {state} {done ? "✓" : ""}
    </span>
  );
}
