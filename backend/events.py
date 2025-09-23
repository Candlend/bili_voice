from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional, Type

from .models import Settings
from protos import interact_word_v2_pb2

# ------------ Utilities ------------

def _pick(d: dict, candidates: List[str]):
    for k in candidates:
        cur = d
        ok = True
        for part in k.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, "", []):
            return cur
    return None


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _fmt(tpl: str, ctx: dict) -> str:
    try:
        return tpl.format_map(_SafeDict(**ctx))
    except Exception:
        return tpl

# ------------ OO Event Model ------------

class LiveEvent:
    raw: Dict[str, Any]
    event_type: str

    def __init__(self, raw: Dict[str, Any]) -> None:
        # Keep full raw in _full for debugging; normalize self.raw to the most useful layer
        self._full = raw
        self.raw = raw.get("data") or raw
        self.event_type = (raw.get("type") or raw.get("cmd") or "").strip() or "UNKNOWN"

    def is_allowed(self, s: Settings) -> bool:
        return False

    def normalize(self) -> Dict[str, Any]:
        """
        Return normalized useful info.
        Common keys: uname, content, price, gift_name, num, text, ...
        """
        return {}

    def format(self, s: Settings) -> str:
        """
        Return formatted text using settings templates and normalized fields.
        """
        return ""

    def to_payload(self, s: Settings) -> Optional[Dict[str, Any]]:
        if not self.is_allowed(s):
            return None
        text = self.format(s)
        if not isinstance(text, str) or not text:
            return None
        return {"type": self.event_type, "text": text, "raw": self._full}


# ===== Chat / SC =====

class DanmakuEvent(LiveEvent):
    def is_allowed(self, s: Settings) -> bool:
        return bool(s.enable_danmaku)

    def normalize(self) -> Dict[str, Any]:
        data = self.raw
        info = data["info"]
        content = info[1]
        uname = info[2][1]
        is_emoticon = bool(isinstance(info[0][13], Dict) and info[0][13].get("emoticon_unique", ""))
        if is_emoticon and content.startswith("[") and content.endswith("]"):
            content = content[1:-1]
            content = content.split("_")[-1]
        return {"uname": uname, "content": content, "is_emoticon": is_emoticon}

    def format(self, s: Settings) -> str:
        return _fmt(s.template_danmaku, self.normalize())


class SuperChatEvent(LiveEvent):
    def is_allowed(self, s: Settings) -> bool:
        if not s.enable_super_chat:
            return False
        price = self.raw["price"]
        return price >= s.min_price_yuan

    def normalize(self) -> Dict[str, Any]:
        data = self.raw
        uname = _pick(data, ["uname", "username", "user_info.uname", "user_info.username"])
        content = data["message"]
        price = data["price"]
        return {"uname": uname, "content": content, "price": price}

    def format(self, s: Settings) -> str:
        return _fmt(s.template_super_chat, self.normalize())


class SendGiftEvent(LiveEvent):
    def is_allowed(self, s: Settings) -> bool:
        if not s.enable_gift:
            return False
        price = self.raw["total_coin"] / 1000
        if not self.raw["is_first"]:
            return False
        return price >= s.min_price_yuan

    def normalize(self) -> Dict[str, Any]:
        data = self.raw
        uname = _pick(data, ["uname", "username", "user_info.uname", "user_info.username"])
        gift_name = _pick(data, ["gift_name", "giftName"])
        num = data["num"]
        price = data["total_coin"] / 1000
        return {"uname": uname, "gift_name": gift_name, "num": num, "price": price}

    def format(self, s: Settings) -> str:
        n = self.normalize()
        tpl = s.template_gift
        return _fmt(tpl, n)


class ComboSendEvent(SendGiftEvent):
    def is_allowed(self, s: Settings) -> bool:
        if not s.enable_gift:
            return False
        price = self.raw["combo_total_coin"] / 1000
        return price >= s.min_price_yuan

    def normalize(self) -> Dict[str, Any]:
        data = self.raw
        uname = _pick(data, ["uname", "username", "user_info.uname", "user_info.username"])

        gift_name = _pick(data, ["gift_name", "giftName"])
        num = data["total_num"]
        price = data["combo_total_coin"] / 1000
        return {"uname": uname, "gift_name": gift_name, "num": num, "price": price}


class GuardBuyEvent(LiveEvent):
    def is_allowed(self, s: Settings) -> bool:
        return bool(s.enable_guard)

    def normalize(self) -> Dict[str, Any]:
        data = self.raw
        uname = _pick(data, ["uname", "username", "user_info.uname", "user_info.username"])
        num = data["num"]
        guard_level = data["guard_level"]
        guard_name = {1: "总督", 2: "提督", 3: "舰长"}[guard_level]
        return {"uname": uname, "num": num, "guard_name": guard_name}

    def format(self, s: Settings) -> str:
        n = self.normalize()
        tpl_captain = getattr(s, "template_captain", None) or "感谢 {uname} 的{num}个舰长"
        tpl_admiral = getattr(s, "template_admiral", None) or "感谢 {uname} 的{num}个提督"
        tpl_commander = getattr(s, "template_commander", None) or "感谢 {uname} 的{num}个总督"
        if n["guard_name"] == "舰长":
            return _fmt(tpl_captain, n)
        elif n["guard_name"] == "提督":
            return _fmt(tpl_admiral, n)
        elif n["guard_name"] == "总督":
            return _fmt(tpl_commander, n)
        return ""


class InteractWordEvent(LiveEvent):
    def _parse_pb(self):
        data = self.raw
        pb_base64 = data["pb"]
        buf = base64.b64decode(pb_base64)
        msg = interact_word_v2_pb2.InteractWord()
        msg.ParseFromString(buf)
        return msg

    def is_allowed(self, s: Settings) -> bool:
        msg = self._parse_pb()
        msg_type = msg.msg_type  # 1: entry, 2: follow, 3: share
        if msg_type == 1:
            return bool(s.enable_entry)
        elif msg_type == 2:
            return bool(s.enable_follow)
        elif msg_type == 3:
            return bool(s.enable_share)
        return False

    def normalize(self) -> Dict[str, Any]:
        msg = self._parse_pb()
        uname = msg.uname
        msg_type = msg.msg_type  # 1: entry, 2: follow, 3: share
        return {"uname": uname, "msg_type": msg_type}

    def format(self, s: Settings) -> str:
        n = self.normalize()
        tpl_entry = getattr(s, "template_entry", None) or "欢迎 {uname} 进入直播间"
        tpl_follow = getattr(s, "template_follow", None) or "感谢 {uname} 的关注"
        tpl_share = getattr(s, "template_share", None) or "感谢 {uname} 的分享"
        if n["msg_type"] == 1:
            return _fmt(tpl_entry, n)
        elif n["msg_type"] == 2:
            return _fmt(tpl_follow, n)
        elif n["msg_type"] == 3:
            return _fmt(tpl_share, n)
        return ""


class LikeClickEvent(LiveEvent):
    def is_allowed(self, s: Settings) -> bool:
        return bool(s.enable_like_click)

    def normalize(self) -> Dict[str, Any]:
        data = self.raw
        uname = _pick(data, ["uname", "username", "user_info.uname", "user_info.username"])
        return {"uname": uname}

    def format(self, s: Settings) -> str:
        n = self.normalize()
        tpl = getattr(s, "template_like_click", None) or "感谢 {uname} 的点赞"
        return _fmt(tpl, n)

# ------------ Factory ------------

_EVENT_MAP: Dict[str, Type[LiveEvent]] = {
    "DANMU_MSG": DanmakuEvent,
    "SUPER_CHAT_MESSAGE": SuperChatEvent,
    "SEND_GIFT": SendGiftEvent,
    "COMBO_SEND": ComboSendEvent,
    "GUARD_BUY": GuardBuyEvent,
    "INTERACT_WORD_V2": InteractWordEvent,
    "LIKE_INFO_V3_CLICK": LikeClickEvent,
}

def create_event(raw: Dict[str, Any]) -> LiveEvent:
    et = (raw.get("type") or raw.get("cmd") or "").strip().upper()
    cls = _EVENT_MAP.get(et)
    if cls is None:
        # fallback unknown event type wrapper that is always filtered out
        return LiveEvent(raw)
    return cls(raw)
