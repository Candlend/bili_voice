from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
import httpx

from .models import Settings, CredentialDTO, LoginStatus, LoginMethod

# Project root = .../backend -> parents[2] is repo root
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "app_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = DATA_DIR / "settings.json"
CREDENTIAL_PATH = DATA_DIR / "credential.json"


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_settings() -> Settings:
    data = _read_json(SETTINGS_PATH)
    if not data:
        # Defaults
        return Settings()
    try:
        return Settings(**data)
    except Exception:
        return Settings()


def save_settings(settings: Settings) -> None:
    _write_json(SETTINGS_PATH, settings.model_dump())


def load_credential() -> Optional[CredentialDTO]:
    data = _read_json(CREDENTIAL_PATH)
    if not data:
        return None
    try:
        cred = CredentialDTO(**data)
        return cred if cred.is_valid() else None
    except Exception:
        return None


def save_credential(cred: CredentialDTO) -> None:
    _write_json(CREDENTIAL_PATH, cred.model_dump())


def clear_credential() -> None:
    if CREDENTIAL_PATH.exists():
        try:
            CREDENTIAL_PATH.unlink()
        except Exception:
            pass


def get_login_status() -> LoginStatus:
    cred = load_credential()
    if cred and cred.is_valid():
        # Expose minimal info; do not leak all cookies
        cookies = {
            k: v
            for k, v in cred.model_dump().items()
            if v and k in {"sessdata", "bili_jct", "buvid3", "dedeuserid"}
        }
        username: Optional[str] = None
        uid: Optional[int] = None
        avatar_url: Optional[str] = None
        try:
            # Query current account info via Bilibili web nav endpoint
            with httpx.Client(timeout=5.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = client.get(
                    "https://api.bilibili.com/x/web-interface/nav",
                    cookies={
                        "SESSDATA": cred.sessdata or "",
                        "bili_jct": cred.bili_jct or "",
                        "buvid3": cred.buvid3 or "",
                        "DedeUserID": cred.dedeuserid or "",
                    },
                )
                j = resp.json()
                if isinstance(j, dict) and j.get("code") == 0:
                    d = j.get("data") or {}
                    username = d.get("uname") or d.get("username")
                    avatar_url = d.get("face") or d.get("avatar")
                    try:
                        uid_val = d.get("mid") or d.get("uid")
                        uid = int(uid_val) if uid_val is not None else None
                    except Exception:
                        uid = None
        except Exception:
            # ignore network or parse errors; fallback to minimal status
            pass
        return LoginStatus(
            logged_in=True,
            method=None,
            cookies=cookies,
            username=username,
            uid=uid,
            avatar_url=avatar_url,
        )
    return LoginStatus(logged_in=False, method=None, cookies=None, username=None, uid=None, avatar_url=None)
