export type Settings = {
  enable_danmaku: boolean;
  enable_gift: boolean;
  enable_guard: boolean;
  enable_super_chat: boolean;
  enable_entry: boolean;
  enable_follow: boolean;
  enable_share: boolean;
  enable_like_click: boolean;
  min_price_yuan: number;
  last_room_id?: number | null;

  // 文本模板
  template_danmaku: string; // 普通弹幕
  template_gift: string; // 礼物
  template_captain: string; // 舰长
  template_admiral: string; // 提督
  template_commander: string; // 总督
  template_super_chat: string; // 醒目留言
  template_entry: string; // 进场
  template_follow: string; // 关注
  template_share: string; // 分享
  template_like_click: string; // 点赞

  // 语音播报设置
  tts_enabled: boolean;
  tts_volume: number; // dB gain (-30..+12 recommended)
  tts_rate: number;   // 0.5-2
  tts_pitch: number;  // 0-2
  tts_max_queue: number;
  tts_voice?: string | null; // 语音名称

  // GPT-SoVITS WebUI 配置
  gradio_server_url: string; // WebUI 服务地址
  // 新增：GPT-SoVITS 根目录与自动启动
  sovits_root_path: string;
  autostart_sovits: boolean;
  sovits_model: string; // SoVITS 模型权重
  gpt_model: string; // GPT 模型权重
  sample_steps: string; // 采样步数
  text_lang: string; // 文本语言
  ref_audio_path: string; // 参考音频路径（本地路径或URL）
  ref_text_path: string; // 参考文本路径（本地路径）
  top_k: number;
  top_p: number;
  temperature: number;
  text_split_method: string; // 文本切分方式
  batch_size: number;
  speed_factor: number;
  ref_text_free: boolean;
  split_bucket: boolean;
  fragment_interval: number;
  seed: number;
  keep_random: boolean;
  parallel_infer: boolean;
  repetition_penalty: number;
  super_sampling: boolean;

  // 服务端队列与替换规则
  max_tts_queue_size: number;
  // 有序替换规则（上方优先）
  replacement_rules: { key: string; value: string; match_case?: boolean; whole_word?: boolean; use_regex?: boolean }[];
};

export type AppStatus = {
  settings: Settings;
  login: {
    logged_in: boolean;
    method?: "qr" | "sms" | "password";
    cookies?: Record<string, string>;
    username?: string;
    uid?: number;
    avatar_url?: string;
  };
};

export type CommonResponse<T = any> = {
  ok: boolean;
  message?: string | null;
  data?: T;
};

export type QRStartResponse = {
  token: string;
  qrcode_base64: string; // data url
};

export type QRStatusResponse = {
  token: string;
  state: "SCAN" | "CONF" | "TIMEOUT" | "DONE" | "PENDING";
  done: boolean;
};

export type StartGeetestResponse = {
  token: string;
  geetest_url: string;
};

export type SendSmsResponse = {
  token: string;
  captcha_id: string;
};

export type TtsHealth = {
  ok: boolean;
  ready: boolean;
  url?: string;
  message?: string;
};

export type TtsPriority = "HIGH" | "NORMAL";

const API_BASE = "";

// simple fetch wrapper
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + url, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let msg = await res.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail || j.message || msg;
    } catch {}
    throw new Error(msg || `HTTP ${res.status}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return (await res.json()) as T;
  }
  // @ts-ignore
  return (await res.text()) as T;
}

// fetch wrapper for binary responses (Blob)
async function requestBlob(url: string, init?: RequestInit): Promise<Blob> {
  const res = await fetch(API_BASE + url, {
    // let caller decide headers (e.g., JSON body)
    ...init,
  });
  if (!res.ok) {
    let msg = await res.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail || j.message || msg;
    } catch {}
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return await res.blob();
}

export const api = {
  status: () => request<AppStatus>("/api/status"),
  getSettings: () => request<Settings>("/api/settings"),
  saveSettings: (s: Settings) =>
    request<CommonResponse>("/api/settings", { method: "POST", body: JSON.stringify(s) }),
  saveLastRoomId: (last_room_id: number) =>
    request<CommonResponse>("/api/settings/last_room_id", {
      method: "POST",
      body: JSON.stringify({ last_room_id }),
    }),

  // QR login
  qrStart: () => request<QRStartResponse>("/api/login/qr/start", { method: "POST" }),
  qrStatus: (token: string) => request<QRStatusResponse>(`/api/login/qr/status?token=${encodeURIComponent(token)}`),

  // Geetest
  geetestStart: (type: "LOGIN" | "VERIFY", token?: string) =>
    request<StartGeetestResponse>("/api/login/geetest/start", {
      method: "POST",
      body: JSON.stringify({ type, token }),
    }),
  geetestDone: (token: string) => request<CommonResponse>(`/api/login/geetest/done?token=${encodeURIComponent(token)}`),
  geetestStop: (token: string) =>
    request<CommonResponse>("/api/login/geetest/stop", { method: "POST", body: JSON.stringify({ token }) }),

  // Password
  loginPassword: (token: string, username: string, password: string) =>
    request<CommonResponse<{ status: "DONE" | "NEED_VERIFY" }>>("/api/login/password", {
      method: "POST",
      body: JSON.stringify({ token, username, password }),
    }),

  // SMS
  smsSend: (token: string, phone: string, country_code = "+86") =>
    request<SendSmsResponse>("/api/login/sms/send", {
      method: "POST",
      body: JSON.stringify({ token, phone, country_code }),
    }),
  smsVerify: (token: string, phone: string, code: string, captcha_id: string, country_code = "+86") =>
    request<CommonResponse<{ status: "DONE" | "NEED_VERIFY" }>>("/api/login/sms/verify", {
      method: "POST",
      body: JSON.stringify({ token, phone, code, captcha_id, country_code }),
    }),

  // Second-step verify
  verifySend: (token: string) =>
    request<CommonResponse>("/api/login/verify/send", { method: "POST", body: JSON.stringify({ token }) }),
  verifyComplete: (token: string, code: string) =>
    request<CommonResponse>("/api/login/verify/complete", {
      method: "POST",
      body: JSON.stringify({ token, code }),
    }),

  logout: () => request<CommonResponse>("/api/logout", { method: "POST" }),

  // TTS/Gradio
  ttsHealth: (url?: string) =>
    request<TtsHealth>(`/api/tts/health${url ? `?url=${encodeURIComponent(url)}` : ""}`),

  ttsEnqueue: (text: string, priority: TtsPriority = "NORMAL", room_id?: number) =>
    request<CommonResponse<{ key?: string }>>("/api/tts/enqueue", {
      method: "POST",
      body: JSON.stringify({ text, priority, room_id }),
    }),
};

export function connectDanmaku(room_id: number, onMessage: (payload: any) => void): WebSocket {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${location.host}/ws/danmaku?room_id=${room_id}`;
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {
      // ignore
    }
  };
  return ws;
}
