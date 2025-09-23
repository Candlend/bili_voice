import type { AppProps } from "next/app";
import Link from "next/link";
import Head from "next/head";
import "../styles/globals.css";
import { DanmakuProvider } from "../components/DanmakuProvider";
import GlobalLogAlerts from "../components/GlobalLogAlerts";

function Nav() {
  return (
    <nav className="nav">
      <div className="nav-inner container">
        <div className="nav-title">BiliVoice</div>
        <div className="nav-links">
          <Link href="/login">账号登录</Link>
          <Link href="/settings">应用设置</Link>
          <Link href="/tts">语音合成</Link>
          <Link href="/danmaku">弹幕播报</Link>
          <Link href="/logs">运行日志</Link>
        </div>
      </div>
    </nav>
  );
}

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <Nav />
      <DanmakuProvider>
        <main className="container">
          <Component {...pageProps} />
        </main>
        <GlobalLogAlerts />
      </DanmakuProvider>
    </>
  );
}
