from __future__ import annotations

from pathlib import Path
from typing import Optional
import asyncio
import os
import subprocess

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from .auth import auth_manager
from .danmaku import danmaku_hub
from .models import (
    AppStatus,
    CommonResponse,
    PasswordLoginRequest,
    QRStartResponse,
    QRStatusResponse,
    QRState,
    SendSmsRequest,
    SendSmsResponse,
    Settings,
    SmsVerifyRequest,
    StartGeetestRequest,
    StartGeetestResponse,
    VerifyChallengeRequest,
    TtsEnqueueRequest,
)
from .storage import (
    clear_credential,
    get_login_status,
    load_settings,
    save_settings,
)
from . import tts_service
from . import proc_manager
from .logs import get_logs_hub, install_log_handler


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_OUT = ROOT_DIR / "frontend" / "out"

app = FastAPI(title="Bilibili Danmaku Desktop Backend", version="0.1.0")

# CORS (webview loads same origin typically, but enable for safety in dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    # Initialize TTS service with current settings on server start and register TTS status broadcaster
    try:
        tts_service.init(load_settings())
    except Exception:
        # Do not block startup on TTS init failures
        pass

    # Expose loop via app.state for cross-thread callbacks
    try:
        app.state.loop = asyncio.get_running_loop()
    except Exception:
        app.state.loop = None

    # Register a status listener that broadcasts TTS status to the room via WS
    def _listener(room_id: Optional[int], key: Optional[str], status: str):
        if not room_id or not key:
            return
        payload = {"type": "TTS_STATUS", "tts_key": key, "status": status}
        try:
            loop = getattr(app.state, "loop", None)
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(danmaku_hub.broadcast_to_room(int(room_id), payload), loop)
        except Exception:
            # ignore listener errors
            pass

    try:
        tts_service.set_status_listener(_listener)
    except Exception:
        pass

    # Install WebSocket log handler
    try:
        install_log_handler(lambda: getattr(app.state, "loop", None))
    except Exception:
        pass

    # Auto-start GPT-SoVITS WebUI if configured and health check fails
    try:
        s = load_settings()
        if getattr(s, "autostart_sovits", False):
            health = await tts_service.gradio_health(s)
            ok = bool(health.get("ok") and health.get("ready"))
            if not ok:
                root = (s.sovits_root_path or "").strip()
                if root:
                    root_path = Path(root).resolve()
                    py = root_path / "runtime" / "python.exe"
                    script = root_path / "GPT_SoVITS" / "inference_webui_fast.py"
                    if py.exists() and script.exists():
                        # Launch external process via proc_manager; it will be tied to parent lifetime
                        proc_manager.start_process([str(py), str(script)], cwd=str(root_path))
    except Exception:
        pass


@app.get("/api/status", response_model=AppStatus)
def api_status():
    return AppStatus(settings=load_settings(), login=get_login_status())


# ========== Settings ==========

@app.get("/api/settings", response_model=Settings)
def api_get_settings():
    return load_settings()


@app.post("/api/settings", response_model=CommonResponse)
def api_save_settings(settings: Settings):
    save_settings(settings)
    # Update TTS service runtime config
    try:
        tts_service.update_settings(settings)
    except Exception:
        pass
    return CommonResponse(ok=True, message="saved")


@app.post("/api/settings/last_room_id", response_model=CommonResponse)
def api_save_last_room_id(last_room_id: int = Body(embed=True)):
    s = load_settings()
    try:
        s.last_room_id = int(last_room_id)
    except Exception:
        s.last_room_id = None
    save_settings(s)
    return CommonResponse(ok=True, message="last_room_id saved", data={"last_room_id": s.last_room_id})


# ========== TTS (Gradio) ==========
@app.get("/api/tts/health")
async def api_tts_health(url: str | None = Query(default=None)):
    """
    Check connectivity to GPT-SoVITS WebUI at current settings or override ?url=.
    """
    try:
        s = load_settings()
        if url:
            # allow testing unsaved input from UI
            try:
                s.gradio_server_url = url  # type: ignore
            except Exception:
                pass
        result = await tts_service.gradio_health(s)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "ready": False, "message": str(e)}, status_code=200)

@app.post("/api/tts/enqueue", response_model=CommonResponse)
def api_tts_enqueue(req: TtsEnqueueRequest):
    """
    Enqueue text into server-side TTS queue for generation and playback.
    Returns a key that can be used to track status via websocket if room_id is provided.
    """
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")
    # map priority (accepts string "HIGH"/"NORMAL", case-insensitive)
    try:
        p_raw = req.priority or "NORMAL"
        p_str = str(p_raw).upper()
        pr = tts_service.Priority.HIGH if p_str == "HIGH" else tts_service.Priority.NORMAL
    except Exception:
        pr = tts_service.Priority.NORMAL
    # normalize room_id
    room_id: Optional[int] = None
    try:
        if req.room_id and int(req.room_id) > 0:
            room_id = int(req.room_id)
    except Exception:
        room_id = None
    # generate tracking key (optional)
    try:
        import uuid
        key = uuid.uuid4().hex
    except Exception:
        key = None
    ok = tts_service.enqueue_text(text, pr, key=key, room_id=room_id)
    if not ok:
        return CommonResponse(ok=False, message="TTS 未启用或队列已满")
    return CommonResponse(ok=True, data={"key": key})

# ========== Login: QR ==========

@app.post("/api/login/qr/start", response_model=QRStartResponse)
async def api_login_qr_start():
    token, b64 = await auth_manager.start_qr()
    # prefix with data url for easier render
    data_url = f"data:image/png;base64,{b64}"
    return QRStartResponse(token=token, qrcode_base64=data_url)


@app.get("/api/login/qr/status", response_model=QRStatusResponse)
async def api_login_qr_status(token: str):
    state, done = await auth_manager.check_qr(token)
    if state is None:
        raise HTTPException(status_code=400, detail="invalid token or session")
    # map enum to our exposed state
    if state.name in QRState.__members__:
        qr_state = QRState[state.name]
    else:
        qr_state = QRState.PENDING
    return QRStatusResponse(token=token, state=qr_state, done=done)


# ========== Login: Geetest (LOGIN/VERIFY) ==========

@app.post("/api/login/geetest/start", response_model=StartGeetestResponse)
async def api_geetest_start(req: StartGeetestRequest):
    token, url = await auth_manager.start_geetest(req.type, req.token)
    return StartGeetestResponse(token=token, geetest_url=url)


@app.get("/api/login/geetest/done", response_model=CommonResponse)
async def api_geetest_done(token: str):
    done = await auth_manager.geetest_has_done(token)
    return CommonResponse(ok=done)


@app.post("/api/login/geetest/stop", response_model=CommonResponse)
async def api_geetest_stop(token: str = Body(embed=True)):
    await auth_manager.stop_geetest(token)
    return CommonResponse(ok=True)


# ========== Login: Password ==========

@app.post("/api/login/password", response_model=CommonResponse)
async def api_login_password(req: PasswordLoginRequest):
    try:
        status = await auth_manager.login_with_password(req.token, req.username, req.password)
        return CommonResponse(ok=True, data={"status": status})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Login: SMS ==========

@app.post("/api/login/sms/send", response_model=SendSmsResponse)
async def api_login_sms_send(req: SendSmsRequest):
    try:
        captcha_id = await auth_manager.send_sms(req.token, req.phone, req.country_code)
        return SendSmsResponse(token=req.token, captcha_id=captcha_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/login/sms/verify", response_model=CommonResponse)
async def api_login_sms_verify(req: SmsVerifyRequest):
    try:
        status = await auth_manager.login_with_sms(req.token, req.phone, req.country_code, req.code, req.captcha_id)
        return CommonResponse(ok=True, data={"status": status})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Login: Second-step VERIFY (LoginCheck) ==========

@app.post("/api/login/verify/send", response_model=CommonResponse)
async def api_login_verify_send(token: str = Body(embed=True)):
    try:
        await auth_manager.verify_send_sms(token)
        return CommonResponse(ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/login/verify/complete", response_model=CommonResponse)
async def api_login_verify_complete(req: VerifyChallengeRequest):
    try:
        await auth_manager.verify_complete(req.token, req.code)
        return CommonResponse(ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Logout ==========

@app.post("/api/logout", response_model=CommonResponse)
def api_logout():
    clear_credential()
    return CommonResponse(ok=True)


# ========== WebSocket: Danmaku ==========


@app.websocket("/ws/danmaku")
async def ws_danmaku(ws: WebSocket):
    # Expect query param: ?room_id=123
    room_id_str: Optional[str] = ws.query_params.get("room_id")
    if not room_id_str or not room_id_str.isdigit():
        await ws.close()
        return
    room_id = int(room_id_str)
    await ws.accept()
    await danmaku_hub.add_client(room_id, ws)
    try:
        # Keep the connection open; client doesn't need to send anything
        while True:
            # ping-pong or read text to detect disconnect
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await danmaku_hub.remove_client(room_id, ws)

# ========== WebSocket: Logs ==========
@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    hub = get_logs_hub()
    await hub.add_client(ws)
    try:
        while True:
            # Keep connection alive; client doesn't need to send anything
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.remove_client(ws)




# ========== Static: Next.js Exported Site ==========

if FRONTEND_OUT.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_OUT), html=True), name="frontend")
else:
    # fallback placeholder
    @app.get("/")
    def index_fallback():
        return JSONResponse(
            {
                "message": "Frontend not built. Please run `cd frontend && npm i && npm run build`.",
                "expected_dir": str(FRONTEND_OUT),
            }
        )
