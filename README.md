<div align="center">

<h1>BiliVoice</h1>

> 一款基于 FastAPI + Next.js 的 B 站直播弹幕桌面应用，支持与 GPT-SoVITS WebUI 对接实现弹幕语音播报。

  <em>轻量、易用，开箱即用的直播间消息可视化与语音播报工具。</em>
  <br/>
  

  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.112-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
</div>

---

## 📍 概览

BiliVoice 是一个桌面化（内置 WebView）的小工具，用于播报 B 站直播间的实时事件（弹幕、礼物、舰长、SC 等），可连接 GPT-SoVITS WebUI 完成语音合成与本地播放：

- 支持扫码登录 / 短信登录 / 密码登录（带极验流程）。
- 支持选择播报的消息类型与文本模板自定义。
- 内置 TTS 队列与优先级（如 SC/礼物消息优先播报），并支持音量增益与文本替换规则。
- 一键对接 GPT-SoVITS WebUI，可选自动启动外部 WebUI。
- 前端使用 Next.js 静态导出，由后端 FastAPI 直接托管，开箱即用。

> **注意**：本项目仅提供语音合成与播放功能，**不包含模型训练部分**。如需训练自定义语音模型，请参考[GPT-SoVITS 官方仓库](https://github.com/RVC-Boss/GPT-SoVITS)和[GPT-SoVITS 官方文档](https://github.com/RVC-Boss/GPT-SoVITS/blob/main/docs/README_zh.md)。

---

## 📁 仓库结构

```plaintext
bili_voice/
├── app_data/                 # 运行期数据（自动创建）
│   ├── credential.json       # 登录态 Cookie（站点 Cookie 的子集）
│   └── settings.json         # 应用配置
├── backend/                  # 后端（FastAPI）
│   ├── main.py               # 服务入口（被 run.py 调用）
│   ├── auth.py               # 登录相关（QR/SMS/密码 + 极验）
│   ├── danmaku.py            # 弹幕 WebSocket 转发与事件桥接
│   ├── tts_service.py        # 与 GPT-SoVITS WebUI 交互与本地播放
│   ├── models.py             # Pydantic 模型（Settings/DTO/请求响应）
│   ├── storage.py            # 配置与凭据的读写
│   └── ...
├── frontend/                 # 前端（Next.js 14）
│   ├── pages/                # 页面（/login /settings /danmaku 等）
│   ├── lib/api.ts            # 与后端 API 的调用封装
│   └── out/                  # 静态导出目录（由 next export 生成）
├── protos/                   # B 站相关 Protobuf 转译（供事件解析）
├── requirements.txt          # Python 依赖
├── run.py                    # 桌面启动入口（启动 FastAPI 并打开 WebView/浏览器）
└── README.md
```

---

## 🚀 快速开始

### 环境要求

- Windows 10/11
- Python 3.12（建议使用 conda 环境）
- Node.js 18+（用于构建前端）
- FFmpeg（用于多媒体处理）
- 已安装的 GPT-SoVITS WebUI

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/candlend/bili_voice.git
cd bili_voice
```

2. 安装后端依赖（建议使用 conda 环境）

```bash
# 创建并激活 conda 环境
conda create -n bili_voice python=3.12
conda activate bili_voice
pip install -r requirements.txt
```

3. 构建前端静态文件

```bash
cd frontend
npm install
npm run build
cd ..
```

4. 启动应用

```bash
python run.py
```

首次启动后端会监听本机端口（默认 5176，若占用会自动递增），并自动打开内置窗口；若无 WebView 环境，则回退到默认浏览器。

---

## 🧭 使用指引

1. 进入 首页，点击“账号登录”，按提示完成 QR/SMS/密码登录（涉及极验流程时，按界面指引进入极验页面完成验证）。
2. 打开“应用设置”，按需勾选展示的消息类型，配置相关参数。
3. 进入“弹幕预览”，输入直播间房间号并连接，可实时查看消息；若启用 TTS，会按照优先级排队语音播放。

---

## ⚙️ 配置说明

运行时配置位于 `app_data/settings.json`，亦可在 UI 中直接保存。常用字段：

- `tts_enabled`：是否启用语音播报。
- `tts_volume`：音量增益（dB，建议 -30 到 +12）。
- `replacement_rules`：文本替换规则。
- `max_tts_queue_size`：服务端 TTS 队列长度上限（含优先级队列）。
- `gradio_server_url`：GPT-SoVITS WebUI 地址（示例 `http://localhost:9872/`）。
- `sovits_root_path`：GPT-SoVITS 根目录（用于自动启动，需包含 `runtime/python.exe` 与 `GPT_SoVITS/`）。
- `autostart_sovits`：启用后，启动本应用且健康检查未通过时，自动尝试启动外部 WebUI。
- `sovits_model` / `gpt_model` / `text_lang` / 采样参数：与 WebUI 一致，用于服务端选择权重与推理参数。
- `template_*`：各类消息的文案模板，例如普通弹幕、礼物、舰长、SC、进场、关注、分享、点赞等。

登录态保存在 `app_data/credential.json`，仅存储调用所需的 Cookie 子集；如需退出登录，可在首页点击“退出登录”或删除该文件。

---

## ❓ 常见问题

- TTS 未播放或报健康检查失败：
  - 检查 `gradio_server_url` 是否可访问；如启用了自动启动，确认 `sovits_root_path` 配置正确。

---

## 🏆 鸣谢

- [`bilibili-api`](https://github.com/Nemo2011/bilibili-api)：B 站 API 封装库
- [`GPT-SoVITS`](https://github.com/RVC-Boss/GPT-SoVITS) 与相关社区项目：语音合成能力与参考实现

---

> 本项目99%代码由GPT-5生成，仍在持续打磨中。欢迎提出建议或贡献改进！
