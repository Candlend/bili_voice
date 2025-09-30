from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, List

from pydantic import BaseModel, Field, HttpUrl


class ReplacementRule(BaseModel):
    key: str
    value: str
    match_case: bool = False
    whole_word: bool = False
    use_regex: bool = False


class Settings(BaseModel):
    enable_danmaku: bool = Field(True, description="播报普通弹幕")
    enable_gift: bool = Field(True, description="播报礼物")
    enable_guard: bool = Field(True, description="播报大航海")
    enable_super_chat: bool = Field(True, description="播报醒目留言")
    enable_entry: bool = Field(False, description="播报进场")
    enable_follow: bool = Field(False, description="播报关注")
    enable_share: bool = Field(False, description="播报分享")
    enable_like_click: bool = Field(False, description="播报点赞")
    min_price_yuan: float = Field(0, description="最低播报打赏价格（元）")
    last_room_id: Optional[int] = Field(None, description="最近使用的房间号")

    # 消息模板
    template_danmaku: str = Field("{uname} 说，{content}", description="普通弹幕格式")
    template_gift: str = Field("感谢 {uname} 的{num}个{gift_name}", description="礼物格式")
    template_captain: str = Field("感谢 {uname} 的{num}个舰长", description="舰长格式")
    template_admiral: str = Field("感谢 {uname} 的{num}个提督", description="提督格式")
    template_commander: str = Field("感谢 {uname} 的{num}个总督", description="总督格式")
    template_super_chat: str = Field("感谢 {uname} 的{price}元SC，{content}", description="醒目留言格式")
    template_entry: str = Field("欢迎 {uname} 进入直播间", description="进场格式")
    template_follow: str = Field("感谢 {uname} 的关注", description="关注格式")
    template_share: str = Field("感谢 {uname} 的分享", description="分享格式")
    template_like_click: str = Field("感谢 {uname} 的点赞", description="点赞格式")

    # AI 语音设置
    tts_enabled: bool = Field(True, description="启用AI语音播报")
    tts_volume: float = Field(0.0, description="音量增益 (dB，建议范围 -30 到 +12)")
    tts_rate: float = Field(1.0, description="语速(0.5-2)")
    tts_pitch: float = Field(1.0, description="音调(0-2)")
    tts_max_queue: int = Field(50, description="最大语音队列长度")
    tts_voice: Optional[str] = Field(None, description="语音名称（浏览器语音合成器）")

    # GPT-SoVITS WebUI 配置（参考 gpt-sovits-tts/config.py）
    gradio_server_url: str = Field("http://localhost:9872/", description="WebUI 服务地址")
    # 新增：GPT-SoVITS 根目录与自动启动开关
    sovits_root_path: str = Field("", description="GPT-SoVITS 根目录（包含 runtime/python.exe 与 GPT_SoVITS 目录）")
    autostart_sovits: bool = Field(True, description="启动程序后若 WebUI 未连接则自动启动 GPT-SoVITS")
    sovits_model: str = Field("", description="SoVITS 模型权重")
    gpt_model: str = Field("", description="GPT 模型权重")
    sample_steps: str = Field("32", description="采样步数")
    text_lang: str = Field("中文", description="文本语言")
    ref_audio_path: str = Field("", description="参考音频路径（本地路径）")
    ref_text_path: str = Field("", description="参考文本路径（本地路径）")
    top_k: int = Field(5, description="Top K")
    top_p: float = Field(1.0, description="Top P")
    temperature: float = Field(1.0, description="采样温度")
    text_split_method: str = Field("不切", description="文本切分方式")
    batch_size: int = Field(20, description="Batch Size")
    speed_factor: float = Field(1.0, description="语速调整")
    ref_text_free: bool = Field(False, description="无参考文本模式")
    split_bucket: bool = Field(True, description="是否分桶")
    fragment_interval: float = Field(0.3, description="片段间隔")
    seed: int = Field(-1, description="随机种子（-1随机）")
    keep_random: bool = Field(True, description="保持随机")
    parallel_infer: bool = Field(True, description="并行推理")
    repetition_penalty: float = Field(1.35, description="重复惩罚")
    super_sampling: bool = Field(False, description="超采样")
    # 与原配置一致的队列名称
    max_tts_queue_size: int = Field(5, description="最大TTS队列长度（服务端）")
    # 有序替换规则：[{ key, value, match_case, whole_word, use_regex }]，上方优先
    replacement_rules: List[ReplacementRule] = Field(default_factory=list, description="有序替换规则 [{key,value,match_case,whole_word,use_regex}]，上方优先")


class CredentialDTO(BaseModel):
    # Store only what bilibili_api.Credential needs. All optional because not all cookies are always present.
    sessdata: Optional[str] = None
    bili_jct: Optional[str] = None
    buvid3: Optional[str] = None
    dedeuserid: Optional[str] = None
    ac_time_value: Optional[str] = None
    buvid4: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.sessdata) and bool(self.bili_jct)


class LoginMethod(str, Enum):
    QR = "qr"
    SMS = "sms"
    PASSWORD = "password"


class LoginStatus(BaseModel):
    logged_in: bool
    method: Optional[LoginMethod] = None
    cookies: Optional[Dict[str, str]] = None
    username: Optional[str] = None
    uid: Optional[int] = None
    avatar_url: Optional[str] = None


# ===== QR Login =====

class QRStartResponse(BaseModel):
    token: str
    qrcode_base64: str


class QRState(str, Enum):
    SCAN = "SCAN"
    CONF = "CONF"
    TIMEOUT = "TIMEOUT"
    DONE = "DONE"
    PENDING = "PENDING"


class QRStatusResponse(BaseModel):
    token: str
    state: QRState
    done: bool = False


# ===== Geetest / SMS / Password Login =====

class GeetestTypeEnum(str, Enum):
    LOGIN = "LOGIN"
    VERIFY = "VERIFY"


class StartGeetestRequest(BaseModel):
    type: GeetestTypeEnum = GeetestTypeEnum.LOGIN
    token: Optional[str] = None


class StartGeetestResponse(BaseModel):
    token: str
    geetest_url: HttpUrl


class SendSmsRequest(BaseModel):
    token: str
    phone: str
    country_code: str = "+86"


class SendSmsResponse(BaseModel):
    token: str
    captcha_id: str


class SmsVerifyRequest(BaseModel):
    token: str
    phone: str
    country_code: str = "+86"
    code: str
    captcha_id: str


class PasswordLoginRequest(BaseModel):
    token: str
    username: str
    password: str


class VerifyChallengeRequest(BaseModel):
    token: str
    code: str


class CommonResponse(BaseModel):
    ok: bool = True
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# ===== TTS =====

class TtsEnqueueRequest(BaseModel):
    text: str
    priority: Optional[str] = "NORMAL"  # accepts "HIGH" | "NORMAL" (case-insensitive)
    room_id: Optional[int] = None


# ===== Danmaku =====

class DanmakuConnectQuery(BaseModel):
    room_id: int


class DanmakuEvent(BaseModel):
    type: str  # e.g., DANMU_MSG, SEND_GIFT, SUPER_CHAT_MESSAGE, etc.
    data: Dict[str, Any]


# ===== App status =====

class AppStatus(BaseModel):
    settings: Settings
    login: LoginStatus
