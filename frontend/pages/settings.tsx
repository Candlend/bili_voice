import React, { useEffect, useState } from "react";
import Toggle from "../components/Toggle";
import { api, Settings, TtsHealth } from "../lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [health, setHealth] = useState<TtsHealth | null>(null);
  const [checking, setChecking] = useState(false);

  // 替换规则行
  const [repRows, setRepRows] = useState<{ key: string; value: string; match_case?: boolean; whole_word?: boolean; use_regex?: boolean }[]>([]);
  // 拖拽排序状态
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  useEffect(() => {
    if (settings) {
      const repList = (settings as any).replacement_rules as { key: string; value: string; match_case?: boolean; whole_word?: boolean; use_regex?: boolean }[] | undefined;
      const rows = (Array.isArray(repList) ? repList : []).map((it) => ({
        key: String(it.key || ""),
        value: String(it.value || ""),
        match_case: !!it.match_case,
        whole_word: !!it.whole_word,
        use_regex: !!it.use_regex,
      }));
      setRepRows(rows);
    }
  }, [settings]);

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => setMsg(e.message || String(e)));
  }, []);

  // 自动检测 Gradio 连接状态：页面加载后、以及地址变更时
  useEffect(() => {
    if (!settings) return;
    (async () => {
      setChecking(true);
      try {
        const h = await api.ttsHealth(settings.gradio_server_url);
        setHealth(h);
      } catch (e: any) {
        setHealth({ ok: false, ready: false, message: e?.message || String(e) });
      } finally {
        setChecking(false);
      }
    })();
  }, [settings?.gradio_server_url]);

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setMsg(null);
    try {
      // 将 repRows 合成为 replacement_rules（仅用此字段）
      const normRows = repRows
        .map((r) => ({
          key: r.key.trim(),
          value: r.value.trim(),
          match_case: !!r.match_case,
          whole_word: !!r.whole_word,
          use_regex: !!r.use_regex,
        }))
        .filter((r) => !!r.key);
      const replacement_rules = normRows;
      const payload = { ...settings, replacement_rules } as any;
      await api.saveSettings(payload as Settings);
      setMsg("设置已保存");
    } catch (e: any) {
      setMsg(e.message || String(e));
    } finally {
      setSaving(false);
    }
  };

  const checkHealth = async () => {
    setChecking(true);
    try {
      const h = await api.ttsHealth(settings?.gradio_server_url);
      setHealth(h);
    } catch (e: any) {
      setHealth({ ok: false, ready: false, message: e?.message || String(e) });
    } finally {
      setChecking(false);
    }
  };

  if (!settings) {
    return (
      <div className="panel">
        <div className="small">正在加载设置...</div>
      </div>
    );
  }

  return (
    <div className="grid" style={{ gap: 16 }}>
      <header className="panel">
        <div style={{ fontWeight: 700, marginBottom: 8 }}>应用设置</div>
        <div className="small">控制弹幕、礼物、入场、醒目留言等播报开关及最低价格。</div>
      </header>

      <section className="panel">
        <div className="grid" style={{ gap: 12 }}>
          <Toggle label="播报普通弹幕" checked={settings.enable_danmaku} onChange={(v) => setSettings({ ...settings, enable_danmaku: v })} />
          <Toggle label="播报礼物" checked={settings.enable_gift} onChange={(v) => setSettings({ ...settings, enable_gift: v })} />
          <Toggle label="播报大航海" checked={settings.enable_guard} onChange={(v) => setSettings({ ...settings, enable_guard: v })} />
          <Toggle label="播报醒目留言" checked={settings.enable_super_chat} onChange={(v) => setSettings({ ...settings, enable_super_chat: v })} />
          <Toggle label="播报进场" checked={settings.enable_entry} onChange={(v) => setSettings({ ...settings, enable_entry: v })} />
          <Toggle label="播报关注" checked={settings.enable_follow} onChange={(v) => setSettings({ ...settings, enable_follow: v })} />
          <Toggle label="播报分享" checked={settings.enable_share} onChange={(v) => setSettings({ ...settings, enable_share: v })} />
          <Toggle label="播报点赞" checked={settings.enable_like_click} onChange={(v) => setSettings({ ...settings, enable_like_click: v })} />
          <div className="row">
            <label>最低播报打赏价格（元）</label>
            <input
              className="number"
              type="number"
              min={0}
              step={0.1}
              value={settings.min_price_yuan}
              onChange={(e) => setSettings({ ...settings, min_price_yuan: Number(e.target.value) })}
            />
          </div>

          <div className="hr" />

          <div style={{ fontWeight: 700 }}>语音播报设置</div>
          <div className="small">通过 GPT-SoVITS WebUI 合成语音并在本机播放。</div>

          <div className="row">
            <label>启用AI语音播报</label>
            <Toggle
              label=""
              checked={!!settings.tts_enabled}
              onChange={(v) => setSettings({ ...settings, tts_enabled: v })}
            />
          </div>

          <div className="row" style={{ alignItems: "center", gap: 8 }}>
            <label>音量 (dB)</label>
            <input
              className="range"
              type="range"
              min={-30}
              max={12}
              step={0.5}
              value={Number.isFinite(settings.tts_volume as any) ? (settings.tts_volume as any) : 0}
              onChange={(e) => setSettings({ ...settings, tts_volume: Number(e.target.value) })}
              style={{ width: 180 }}
            />
            <span className="small" style={{ width: 50, textAlign: "right" }}>
              {(Number.isFinite(settings.tts_volume as any) ? (settings.tts_volume as any) : 0).toFixed(1)} dB
            </span>
          </div>

          <div className="row">
            <label>最大队列长度</label>
            <input
              className="number"
              type="number"
              min={1}
              max={200}
              step={1}
              value={Number.isFinite((settings as any).max_tts_queue_size as any) ? (settings as any).max_tts_queue_size : 5}
              onChange={(e) => setSettings({ ...settings, max_tts_queue_size: Math.max(1, Math.min(200, Math.floor(Number(e.target.value)))) })}
            />
          </div>

          <div className="hr" />

          <div style={{ fontWeight: 700 }}>GPT-SoVITS 配置</div>

          <div className="row" style={{ alignItems: "center", gap: 8 }}>
            <label>WebUI 服务地址</label>
            <input
              className="input"
              value={settings.gradio_server_url}
              onChange={(e) => setSettings({ ...settings, gradio_server_url: e.target.value })}
              placeholder="http://localhost:9872/"
              style={{ flex: 1, minWidth: 320 }}
            />
            <button className="button secondary" onClick={checkHealth} disabled={checking} style={{ whiteSpace: "nowrap" }}>
              {checking ? "检测中..." : "测试连接"}
            </button>
            <span className="badge" title={health?.message || ""} style={{ background: health?.ok && health?.ready ? "#204d26" : "#4d2020" }}>
              {health ? (health.ok && health.ready ? "已连接" : "未连接") : "未知"}
            </span>
          </div>

          <div className="row" style={{ alignItems: "center", gap: 8 }}>
            <label>GPT-SoVITS 根目录</label>
            <input
              className="input"
              value={(settings as any).sovits_root_path || ""}
              onChange={(e) => setSettings({ ...settings, sovits_root_path: e.target.value })}
              placeholder="例如 D:\\GPT-SoVITS"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row">
            <label>启动时自动尝试启动 WebUI</label>
            <Toggle
              label=""
              checked={!!(settings as any).autostart_sovits}
              onChange={(v) => setSettings({ ...settings, autostart_sovits: v as any })}
            />
          </div>

          <div className="row">
            <label>SoVITS 模型</label>
            <input
              className="input"
              value={settings.sovits_model}
              onChange={(e) => setSettings({ ...settings, sovits_model: e.target.value })}
              placeholder="xxx.pth"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row">
            <label>GPT 模型</label>
            <input
              className="input"
              value={settings.gpt_model}
              onChange={(e) => setSettings({ ...settings, gpt_model: e.target.value })}
              placeholder="xxx.ckpt"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row">
            <label>采样步数</label>
            <input
              className="input"
              value={settings.sample_steps}
              onChange={(e) => setSettings({ ...settings, sample_steps: e.target.value })}
              placeholder="32"
              style={{ flex: 1, minWidth: 160 }}
            />
          </div>

          <div className="row">
            <label>文本语言</label>
            <select
              className="input"
              value={settings.text_lang}
              onChange={(e) => setSettings({ ...settings, text_lang: e.target.value })}
              style={{ flex: 1, minWidth: 240 }}
            >
              {["中文","英文","日文","粤语","韩文","中英混合","日英混合","粤英混合","韩英混合","多语种混合","多语种混合(粤语)"].map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>

          <div className="row" style={{ alignItems: "center", gap: 8 }}>
            <label>参考音频路径</label>
            <input
              className="input"
              value={settings.ref_audio_path}
              onChange={(e) => setSettings({ ...settings, ref_audio_path: e.target.value })}
              placeholder="本地路径或URL"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "center", gap: 8 }}>
            <label>参考文本路径</label>
            <input
              className="input"
              value={settings.ref_text_path}
              onChange={(e) => setSettings({ ...settings, ref_text_path: e.target.value })}
              placeholder="本地文本路径"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row">
            <label>Top K</label>
            <input
              className="number"
              type="number"
              min={1}
              max={100}
              step={1}
              value={settings.top_k}
              onChange={(e) => setSettings({ ...settings, top_k: Math.max(1, Math.min(100, Math.floor(Number(e.target.value)))) })}
            />
          </div>

          <div className="row">
            <label>Top P</label>
            <input
              className="number"
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={settings.top_p}
              onChange={(e) => setSettings({ ...settings, top_p: Math.max(0, Math.min(1, Number(e.target.value))) })}
            />
          </div>

          <div className="row">
            <label>Temperature</label>
            <input
              className="number"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={settings.temperature}
              onChange={(e) => setSettings({ ...settings, temperature: Math.max(0, Math.min(1, Number(e.target.value))) })}
            />
          </div>

          <div className="row">
            <label>文本切分方式</label>
            <select
              className="input"
              value={settings.text_split_method}
              onChange={(e) => setSettings({ ...settings, text_split_method: e.target.value })}
              style={{ flex: 1, minWidth: 240 }}
            >
              {["不切","凑四句一切","凑50字一切","按中文句号。切","按英文句号.切","按标点符号切"].map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>

          <div className="row">
            <label>Batch Size</label>
            <input
              className="number"
              type="number"
              min={1}
              max={200}
              step={1}
              value={settings.batch_size}
              onChange={(e) => setSettings({ ...settings, batch_size: Math.max(1, Math.min(200, Math.floor(Number(e.target.value)))) })}
            />
          </div>

          <div className="row">
            <label>语速调整</label>
            <input
              className="number"
              type="number"
              min={0.6}
              max={1.65}
              step={0.05}
              value={settings.speed_factor}
              onChange={(e) => setSettings({ ...settings, speed_factor: Math.max(0.6, Math.min(1.65, Number(e.target.value))) })}
            />
          </div>

          <div className="row">
            <label>无参考文本模式</label>
            <Toggle label="" checked={settings.ref_text_free} onChange={(v) => setSettings({ ...settings, ref_text_free: v })} />
          </div>

          <div className="row">
            <label>是否分桶</label>
            <Toggle label="" checked={settings.split_bucket} onChange={(v) => setSettings({ ...settings, split_bucket: v })} />
          </div>

          <div className="row">
            <label>片段间隔</label>
            <input
              className="number"
              type="number"
              min={0.01}
              max={1}
              step={0.01}
              value={settings.fragment_interval}
              onChange={(e) => setSettings({ ...settings, fragment_interval: Math.max(0.01, Math.min(1, Number(e.target.value))) })}
            />
          </div>

          <div className="row">
            <label>随机种子</label>
            <input
              className="number"
              type="number"
              min={-1}
              step={1}
              value={settings.seed}
              onChange={(e) => setSettings({ ...settings, seed: Math.floor(Number(e.target.value)) })}
            />
          </div>

          <div className="row">
            <label>保持随机</label>
            <Toggle label="" checked={settings.keep_random} onChange={(v) => setSettings({ ...settings, keep_random: v })} />
          </div>

          <div className="row">
            <label>并行推理</label>
            <Toggle label="" checked={settings.parallel_infer} onChange={(v) => setSettings({ ...settings, parallel_infer: v })} />
          </div>

          <div className="row">
            <label>重复惩罚</label>
            <input
              className="number"
              type="number"
              min={0}
              max={2}
              step={0.05}
              value={settings.repetition_penalty}
              onChange={(e) => setSettings({ ...settings, repetition_penalty: Math.max(0, Math.min(2, Number(e.target.value))) })}
            />
          </div>

          <div className="row">
            <label>超采样</label>
            <Toggle label="" checked={settings.super_sampling} onChange={(v) => setSettings({ ...settings, super_sampling: v })} />
          </div>

          <div className="hr" />

          <div style={{ fontWeight: 700 }}>替换规则</div>
          <div className="small">上方规则优先，依次替换。例如：将“_”替换为“下划线”</div>
          <div className="grid" style={{ gap: 8 }}>
            {repRows.map((row, idx) => (
              <div
                key={idx}
                className="row"
                style={{
                  alignItems: "center",
                  cursor: "move",
                  ...(dragOverIndex === idx ? { background: "#1f2a38" } : {}),
                }}
                draggable
                onDragStart={(e) => {
                  try {
                    e.dataTransfer?.setData("text/plain", String(idx));
                  } catch {}
                  setDragIndex(idx);
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (dragOverIndex !== idx) setDragOverIndex(idx);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const from = dragIndex;
                  const to = idx;
                  setDragOverIndex(null);
                  setDragIndex(null);
                  if (from === null || to === null || from === to) return;
                  const next = [...repRows];
                  const [item] = next.splice(from, 1);
                  next.splice(to, 0, item);
                  setRepRows(next);
                }}
                onDragEnd={() => {
                  setDragOverIndex(null);
                  setDragIndex(null);
                }}
              >
                <input
                  className="input"
                  placeholder="键"
                  value={row.key}
                  onChange={(e) => {
                    const next = [...repRows];
                    next[idx] = { ...next[idx], key: e.target.value };
                    setRepRows(next);
                  }}
                  style={{ flex: 1, minWidth: 160, marginRight: 8 }}
                />
                <input
                  className="input"
                  placeholder="值"
                  value={row.value}
                  onChange={(e) => {
                    const next = [...repRows];
                    next[idx] = { ...next[idx], value: e.target.value };
                    setRepRows(next);
                  }}
                  style={{ flex: 2, minWidth: 240, marginRight: 8 }}
                />
                <div className="row" style={{ gap: 6, marginRight: 8 }}>
                  <button
                    className="button secondary"
                    title="区分大小写"
                    onClick={() => {
                      const next = [...repRows];
                      next[idx] = { ...next[idx], match_case: !next[idx].match_case };
                      setRepRows(next);
                    }}
                    style={{
                      opacity: row.match_case ? 1 : 0.6,
                      width: 32,
                      height: 32,
                      minWidth: 32,
                      minHeight: 32,
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 0,
                      textAlign: "center",
                    }}
                  >
                    Aa
                  </button>
                  <button
                    className="button secondary"
                    title="整词匹配"
                    onClick={() => {
                      const next = [...repRows];
                      next[idx] = { ...next[idx], whole_word: !next[idx].whole_word };
                      setRepRows(next);
                    }}
                    style={{
                      opacity: row.whole_word ? 1 : 0.6,
                      width: 32,
                      height: 32,
                      minWidth: 32,
                      minHeight: 32,
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 0,
                      textAlign: "center",
                    }}
                  >
                    W
                  </button>
                  <button
                    className="button secondary"
                    title="使用正则表达式"
                    onClick={() => {
                      const next = [...repRows];
                      next[idx] = { ...next[idx], use_regex: !next[idx].use_regex };
                      setRepRows(next);
                    }}
                    style={{
                      opacity: row.use_regex ? 1 : 0.6,
                      width: 32,
                      height: 32,
                      minWidth: 32,
                      minHeight: 32,
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 0,
                      textAlign: "center",
                    }}
                  >
                    .*
                  </button>
                </div>
                <button
                  className="button danger"
                  onClick={() => {
                    const next = repRows.slice(0, idx).concat(repRows.slice(idx + 1));
                    setRepRows(next);
                  }}
                >
                  删除
                </button>
              </div>
            ))}
            <div>
              <button
                className="button secondary"
                onClick={() => setRepRows([...repRows, { key: "", value: "" }])}
              >
                添加一行
              </button>
            </div>
          </div>

          <div className="hr" />

          <div style={{ fontWeight: 700 }}>消息模板</div>
          <div className="small">
            可用变量: {"{uname}"} {"{content}"} {"{gift_name}"} {"{num}"} {"{price}"}
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>普通弹幕</label>
            <input
              className="input"
              value={settings.template_danmaku}
              onChange={(e) => setSettings({ ...settings, template_danmaku: e.target.value })}
              placeholder="{uname} 说，{content}"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>礼物</label>
            <input
              className="input"
              value={settings.template_gift}
              onChange={(e) => setSettings({ ...settings, template_gift: e.target.value })}
              placeholder="感谢 {uname} 的{num}个{gift_name}"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>舰长</label>
            <input
              className="input"
              value={settings.template_captain}
              onChange={(e) => setSettings({ ...settings, template_captain: e.target.value })}
              placeholder="感谢 {uname} 的{num}个舰长"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>提督</label>
            <input
              className="input"
              value={settings.template_admiral}
              onChange={(e) => setSettings({ ...settings, template_admiral: e.target.value })}
              placeholder="感谢 {uname} 的{num}个提督"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>总督</label>
            <input
              className="input"
              value={settings.template_commander}
              onChange={(e) => setSettings({ ...settings, template_commander: e.target.value })}
              placeholder="感谢 {uname} 的{num}个总督"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>醒目留言</label>
            <input
              className="input"
              value={settings.template_super_chat}
              onChange={(e) => setSettings({ ...settings, template_super_chat: e.target.value })}
              placeholder="感谢 {uname} 的{price}元SC，{content}"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>进场</label>
            <input
              className="input"
              value={settings.template_entry}
              onChange={(e) => setSettings({ ...settings, template_entry: e.target.value })}
              placeholder="欢迎 {uname} 进入直播间"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>
        
          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>关注</label>
            <input
              className="input"
              value={settings.template_follow}
              onChange={(e) => setSettings({ ...settings, template_follow: e.target.value })}
              placeholder="感谢 {uname} 的关注"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>分享</label>
            <input
              className="input"
              value={settings.template_share}
              onChange={(e) => setSettings({ ...settings, template_share: e.target.value })}
              placeholder="感谢 {uname} 的分享"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row" style={{ alignItems: "stretch" }}>
            <label style={{ minWidth: 140 }}>点赞</label>
            <input
              className="input"
              value={settings.template_like_click}
              onChange={(e) => setSettings({ ...settings, template_like_click: e.target.value })}
              placeholder="感谢 {uname} 的点赞"
              style={{ flex: 1, minWidth: 320 }}
            />
          </div>

          <div className="row">
            <button className="button" disabled={saving} onClick={save}>
              {saving ? "保存中..." : "保存设置"}
            </button>
            {msg && <span className="small" style={{ color: "#9fb0c0" }}>{msg}</span>}
          </div>
        </div>
      </section>
    </div>
  );
}
