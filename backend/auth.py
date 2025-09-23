from __future__ import annotations

import asyncio
import base64
import secrets
from typing import Dict, Optional, Tuple

from bilibili_api import Geetest, GeetestType, Credential as BiliCredential
from bilibili_api import login_v2
from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginChannel, QrCodeLoginEvents, LoginCheck, PhoneNumber
from bilibili_api.utils import picture as picture_utils

from .models import (
    CredentialDTO,
    GeetestTypeEnum,
    LoginMethod,
)
from .storage import save_credential, load_credential


class AuthSession:
    def __init__(self) -> None:
        self.qr: Optional[QrCodeLogin] = None
        self.qr_done: bool = False
        self.qr_state: Optional[QrCodeLoginEvents] = None
        self.qr_picture_b64: Optional[str] = None

        self.geetest: Optional[Geetest] = None
        self.geetest_type: Optional[GeetestType] = None
        self.geetest_url: Optional[str] = None

        self.login_check: Optional[LoginCheck] = None
        self.captcha_id: Optional[str] = None

        self.method: Optional[LoginMethod] = None
        self.cookies_saved: bool = False


class AuthManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, AuthSession] = {}
        self._lock = asyncio.Lock()

    def _new_token(self) -> str:
        return secrets.token_urlsafe(16)

    async def _ensure_session(self, token: Optional[str] = None) -> Tuple[str, AuthSession]:
        async with self._lock:
            if token and token in self._sessions:
                return token, self._sessions[token]
            t = self._new_token()
            sess = AuthSession()
            self._sessions[t] = sess
            return t, sess

    # ===== QR Login =====

    async def start_qr(self) -> Tuple[str, str]:
        token, sess = await self._ensure_session()
        sess.method = LoginMethod.QR
        sess.qr = QrCodeLogin(platform=QrCodeLoginChannel.WEB)
        await sess.qr.generate_qrcode()
        pic = sess.qr.get_qrcode_picture()  # Picture
        # Encode raw content bytes of Picture to base64
        if not pic or not isinstance(pic.content, (bytes, bytearray)):
            raise RuntimeError("QR code picture content not available")
        b64 = base64.b64encode(pic.content).decode("ascii")
        sess.qr_picture_b64 = b64
        return token, b64

    async def check_qr(self, token: str) -> Tuple[Optional[QrCodeLoginEvents], bool]:
        _, sess = await self._ensure_session(token)
        if not sess.qr:
            return None, False
        if sess.qr_done:
            return QrCodeLoginEvents.DONE, True

        state = await sess.qr.check_state()
        sess.qr_state = state
        if state == QrCodeLoginEvents.DONE:
            sess.qr_done = True
            cred = sess.qr.get_credential()
            self._save_bili_credential(cred)
            sess.cookies_saved = True
        return state, sess.qr_done

    # ===== Geetest =====

    async def start_geetest(self, type_: GeetestTypeEnum, token: Optional[str] = None) -> Tuple[str, str]:
        token, sess = await self._ensure_session(token)
        gt = Geetest()
        if type_ == GeetestTypeEnum.LOGIN:
            await gt.generate_test(type_=GeetestType.LOGIN)
            sess.geetest_type = GeetestType.LOGIN
        else:
            await gt.generate_test(type_=GeetestType.VERIFY)
            sess.geetest_type = GeetestType.VERIFY
        gt.start_geetest_server()
        url = gt.get_geetest_server_url()
        sess.geetest = gt
        sess.geetest_url = url
        return token, url

    async def geetest_has_done(self, token: str) -> bool:
        _, sess = await self._ensure_session(token)
        return bool(sess.geetest and sess.geetest.has_done())

    async def stop_geetest(self, token: str) -> None:
        _, sess = await self._ensure_session(token)
        if sess.geetest:
            try:
                sess.geetest.close_geetest_server()
            except Exception:
                pass

    # ===== Password Login =====

    async def login_with_password(self, token: str, username: str, password: str):
        _, sess = await self._ensure_session(token)
        if not sess.geetest or not sess.geetest.has_done():
            raise RuntimeError("Geetest not completed")
        sess.method = LoginMethod.PASSWORD
        res = await login_v2.login_with_password(username=username, password=password, geetest=sess.geetest)
        if isinstance(res, LoginCheck):
            sess.login_check = res
            return "NEED_VERIFY"
        else:
            self._save_bili_credential(res)
            sess.cookies_saved = True
            return "DONE"

    # ===== SMS Login =====

    async def send_sms(self, token: str, phone: str, country_code: str = "+86") -> str:
        _, sess = await self._ensure_session(token)
        if not sess.geetest or not sess.geetest.has_done():
            raise RuntimeError("Geetest not completed")
        sess.method = LoginMethod.SMS
        pn = PhoneNumber(number=phone, country=country_code)
        captcha_id = await login_v2.send_sms(phonenumber=pn, geetest=sess.geetest)
        sess.captcha_id = captcha_id
        return captcha_id

    async def login_with_sms(self, token: str, phone: str, country_code: str, code: str, captcha_id: str):
        _, sess = await self._ensure_session(token)
        pn = PhoneNumber(number=phone, country=country_code)
        res = await login_v2.login_with_sms(phonenumber=pn, code=code, captcha_id=captcha_id)
        if isinstance(res, LoginCheck):
            sess.login_check = res
            return "NEED_VERIFY"
        else:
            self._save_bili_credential(res)
            sess.cookies_saved = True
            return "DONE"

    # ===== Verify login check (2nd step) =====

    async def verify_send_sms(self, token: str) -> None:
        _, sess = await self._ensure_session(token)
        if not sess.login_check:
            raise RuntimeError("No login check session")
        if not sess.geetest or not sess.geetest.has_done() or sess.geetest_type != GeetestType.VERIFY:
            raise RuntimeError("Geetest VERIFY not completed")
        await sess.login_check.send_sms(sess.geetest)

    async def verify_complete(self, token: str, code: str) -> None:
        _, sess = await self._ensure_session(token)
        if not sess.login_check:
            raise RuntimeError("No login check session")
        cred = await sess.login_check.complete_check(code)
        self._save_bili_credential(cred)
        sess.cookies_saved = True

    # ===== helpers =====

    def _save_bili_credential(self, cred: BiliCredential) -> None:
        cookies = cred.get_cookies()
        dto = CredentialDTO(
            sessdata=cookies.get("SESSDATA"),
            bili_jct=cookies.get("bili_jct"),
            buvid3=cookies.get("buvid3"),
            dedeuserid=cookies.get("DedeUserID"),
            ac_time_value=cookies.get("ac_time_value"),
            buvid4=cookies.get("buvid4"),
        )
        save_credential(dto)


# Singleton
auth_manager = AuthManager()
