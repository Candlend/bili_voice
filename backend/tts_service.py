from __future__ import annotations

import asyncio
import dataclasses
import enum
import io
import logging
import math
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple, Callable

import aiohttp
from pydub import AudioSegment
import winsound
import subprocess
import shutil

import re
from .models import Settings, ReplacementRule

logger = logging.getLogger("bili-voice.tts_service")
_global_status_listener: Optional[Callable[[Optional[int], Optional[str], str], None]] = None


class Priority(enum.IntEnum):
    HIGH = 0
    NORMAL = 1


@dataclasses.dataclass
class TtsTask:
    text: str
    priority: Priority = Priority.NORMAL
    key: Optional[str] = None
    room_id: Optional[int] = None


class _PredictQueue:
    def __init__(self, max_size: Optional[int] = None, on_evict: Optional[Callable[[TtsTask], None]] = None):
        self._max_size = max_size
        self._high: Deque[TtsTask] = deque()
        self._normal: Deque[TtsTask] = deque()
        self._cv = threading.Condition()
        self._on_evict = on_evict

    def push(self, task: TtsTask) -> bool:
        with self._cv:
            # capacity check
            cap = self._max_size if isinstance(self._max_size, int) and self._max_size > 0 else None
            size = len(self._high) + len(self._normal)
            if cap is not None and size >= cap:
                if task.priority == Priority.HIGH:
                    # evict from normal; if none, evict oldest high
                    evicted: Optional[TtsTask] = None
                    if self._normal:
                        evicted = self._normal.popleft()
                    elif self._high:
                        evicted = self._high.popleft()
                    else:
                        evicted = None
                    # notify eviction
                    try:
                        if evicted and self._on_evict:
                            self._on_evict(evicted)
                    except Exception:
                        pass
                else:
                    # drop normal task (not enqueued -> no pending emitted)
                    return False
            # enqueue
            if task.priority == Priority.HIGH:
                self._high.append(task)
            else:
                self._normal.append(task)
            self._cv.notify()
            return True

    def pop(self) -> TtsTask:
        with self._cv:
            while True:
                if self._high:
                    return self._high.popleft()
                if self._normal:
                    return self._normal.popleft()
                self._cv.wait()


class _AudioQueue:
    def __init__(self, max_size: Optional[int] = None, on_evict: Optional[Callable[[TtsTask], None]] = None):
        self._max_size = max_size
        self._q: Deque[Tuple[AudioSegment, TtsTask]] = deque()
        self._cv = threading.Condition()
        self._on_evict = on_evict

    def push(self, audio: AudioSegment, task: TtsTask):
        with self._cv:
            cap = self._max_size if isinstance(self._max_size, int) and self._max_size > 0 else None
            if cap is not None and len(self._q) >= cap:
                # drop oldest
                evicted: Optional[Tuple[AudioSegment, TtsTask]] = None
                try:
                    evicted = self._q.popleft()
                except Exception:
                    evicted = None
                # notify eviction
                try:
                    if evicted and self._on_evict:
                        self._on_evict(evicted[1])
                except Exception:
                    pass
            self._q.append((audio, task))
            self._cv.notify()

    def pop(self) -> Tuple[AudioSegment, TtsTask]:
        with self._cv:
            while True:
                try:
                    return self._q.popleft()
                except Exception:
                    self._cv.wait()


class _GradioClient:
    """
    Minimal Gradio client to talk to GPT-SoVITS WebUI following the behavior
    referenced in gpt-sovits-tts/tts.py and tts_client.py.
    """
    def __init__(self, base_url: str, ssl_verify: bool = False, timeout: int = 300):
        self.base_url = base_url if base_url.endswith("/") else (base_url + "/")
        self.ssl_verify = ssl_verify
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._fn_map: Dict[str, int] = {}

    async def ensure(self):
        if self._session is None:
            connector = aiohttp.TCPConnector(ssl=self.ssl_verify)
            self._session = aiohttp.ClientSession(timeout=self.timeout, connector=connector, headers={
                "User-Agent": "bili-voice/tts_service"
            })
            await self._load_config()

    async def _load_config(self):
        assert self._session is not None
        url = self.base_url + "config"
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            cfg = await resp.json()
        deps = cfg.get("dependencies") or []
        # Build api_name -> fn_index map
        for i, dep in enumerate(deps):
            api_name = (dep or {}).get("api_name")
            if api_name:
                self._fn_map[str(api_name).strip().lstrip("/")] = int((dep or {}).get("id", i))

    async def close(self):
        if self._session is not None:
            s = self._session
            self._session = None
            try:
                await s.close()
            except Exception:
                pass

    async def _upload_file(self, file_path: str) -> str:
        assert self._session is not None
        url = self.base_url + "upload"
        data = aiohttp.FormData()
        data.add_field("files", open(file_path, "rb"), filename=file_path.split("/")[-1], content_type="application/octet-stream")
        async with self._session.post(url, data=data) as resp:
            resp.raise_for_status()
            j = await resp.json()
            # returns list of uploaded paths
            return j[0]

    async def _process_inputs(self, args: List[Any]) -> List[Any]:
        processed: List[Any] = []
        for a in args:
            if isinstance(a, dict) and a.get("meta", {}).get("_type") == "gradio.FileData":
                p = a.get("path")
                if p and not (str(p).startswith("http://") or str(p).startswith("https://")):
                    # local path -> upload
                    uploaded = await self._upload_file(p)
                    processed.append({
                        "path": uploaded,
                        "orig_name": a.get("orig_name") or (str(p).split("/")[-1]),
                        "meta": {"_type": "gradio.FileData"},
                    })
                else:
                    processed.append(a)
            else:
                processed.append(a)
        return processed

    async def predict(self, api_name: str, *args: Any) -> Any:
        await self.ensure()
        assert self._session is not None
        fn = self._fn_map.get(api_name.strip().lstrip("/"))
        if fn is None:
            raise RuntimeError(f"API '{api_name}' not found in gradio config")
        url = self.base_url + "api/predict/"
        data = {
            "data": await self._process_inputs(list(args)),
            "fn_index": fn,
            "session_hash": str(int(time.time() * 1000))
        }
        async with self._session.post(url, json=data) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"Gradio predict failed: {resp.status} {text[:200]}")
            j = await resp.json()
            if j.get("error"):
                raise RuntimeError(f"Gradio API error: {j.get('error')}")
            return j.get("data")


class TTSService:
    def __init__(self) -> None:
        self._cfg: Optional[Settings] = None
        self._predict_q = _PredictQueue(on_evict=lambda t: self._emit_status(getattr(t, "room_id", None), getattr(t, "key", None), "cancelled"))
        self._audio_q = _AudioQueue(on_evict=lambda t: self._emit_status(getattr(t, "room_id", None), getattr(t, "key", None), "cancelled"))
        self._predict_thread = threading.Thread(target=self._predict_worker, daemon=True)
        self._play_thread = threading.Thread(target=self._play_worker, daemon=True)
        self._threads_started = False
        self._gradio_ready = threading.Event()
        self._status_listener: Optional[Callable[[Optional[int], Optional[str], str], None]] = None

    def init(self, settings: Settings):
        self._cfg = settings
        # start threads once
        if not self._threads_started:
            self._threads_started = True
            self._predict_thread.start()
            self._play_thread.start()

    def update_settings(self, settings: Settings):
        self._cfg = settings

    def set_status_listener(self, fn: Optional[Callable[[Optional[int], Optional[str], str], None]]):
        self._status_listener = fn

    def _emit_status(self, room_id: Optional[int], key: Optional[str], status: str):
        try:
            logger.debug("TTS_STATUS room=%s key=%s status=%s", room_id, key, status)
        except Exception:
            pass
        try:
            if self._status_listener:
                self._status_listener(room_id, key, status)
        except Exception:
            pass

    def enqueue_text(self, text: str, priority: Priority = Priority.NORMAL, key: Optional[str] = None, room_id: Optional[int] = None) -> bool:
        if not self._cfg or not getattr(self._cfg, "tts_enabled", False):
            return False
        # replacement rules（仅使用有序列表 replacement_rules）
        t = text or ""
        try:
            text_to_process = t
            rep_list = getattr(self._cfg, "replacement_rules", None) or []
            if isinstance(rep_list, list) and len(rep_list) > 0:
                for raw in rep_list:
                    try:
                        rule: ReplacementRule
                        if isinstance(raw, ReplacementRule):
                            rule = raw
                        else:
                            # tolerate dict input
                            rule = ReplacementRule(**(raw or {}))
                    except Exception:
                        continue
                    if not rule.key:
                        continue

                    # Build pattern/replacement according to flags
                    flags = 0 if rule.match_case else re.IGNORECASE
                    pattern: str
                    if rule.use_regex:
                        pattern = rule.key
                    else:
                        # escape literal
                        pattern = re.escape(rule.key)
                    if rule.whole_word:
                        # Use word boundaries; for CJK this may not be perfect, but acceptable
                        pattern = r"\b" + pattern + r"\b"
                    try:
                        text_to_process = re.sub(pattern, rule.value, text_to_process, flags=flags)
                    except re.error:
                        # invalid regex -> skip
                        continue
            t = text_to_process
        except Exception:
            pass

        max_q = getattr(self._cfg, "max_tts_queue_size", None) or getattr(self._cfg, "tts_max_queue_size", None)
        try:
            cap = int(max_q) if max_q is not None else None
        except Exception:
            cap = None
        # reconfigure capacity
        self._predict_q._max_size = cap
        self._audio_q._max_size = cap
        ok = self._predict_q.push(TtsTask(text=t, priority=priority, key=key, room_id=room_id))
        if ok:
            try:
                self._emit_status(room_id, key, "pending")
            except Exception:
                pass
        else:
            # Not enqueued due to capacity and normal priority drop -> mark as cancelled
            try:
                if key is not None:
                    self._emit_status(room_id, key, "cancelled")
            except Exception:
                pass
        return ok

    # ---------- workers ----------

    def _predict_worker(self):
        logger.info("TTS predict worker started")
        client: Optional[_GradioClient] = None
        selected_sig: Optional[Tuple[str, str, str, str]] = None  # (base, sovits, gpt, text_lang)

        async def _ensure_and_select_models():
            nonlocal client, selected_sig
            cfg = self._cfg
            if not cfg:
                return False
            base = (cfg.gradio_server_url or "").strip()
            if not base:
                logger.warning("Gradio server URL not set; waiting...")
                return False
            # (re)create client when base changes
            if client is None or (isinstance(client, _GradioClient) and client.base_url.rstrip("/") != (base if base.endswith("/") else (base + "/")).rstrip("/")):
                client = _GradioClient(base, ssl_verify=False)
                selected_sig = None
            try:
                # Select weights only when signature changed
                sig = (base, str(cfg.sovits_model), str(cfg.gpt_model), str(cfg.text_lang))
                if selected_sig != sig:
                    await client.predict("/change_sovits_weights", cfg.sovits_model, cfg.text_lang, cfg.text_lang)
                    await client.predict("/change_gpt_weights", cfg.gpt_model)
                    selected_sig = sig
                    self._gradio_ready.set()
                return True
            except Exception as e:
                logger.warning("Failed to initialize Gradio client: %s", e)
                client.close()
                client = None
                selected_sig = None
                self._gradio_ready.clear()
                return False

        def _new_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

        loop = _new_loop()
        while True:
            try:
                task = self._predict_q.pop()
                # ensure client ready
                ok = loop.run_until_complete(_ensure_and_select_models())
                if not ok:
                    # backoff and skip this task to avoid blocking queue forever
                    time.sleep(2.0)
                    continue

                cfg = self._cfg
                assert cfg is not None
                assert client is not None

                # Build inputs
                ref_audio_dict: Optional[Dict[str, Any]] = None
                if isinstance(cfg.ref_audio_path, str) and cfg.ref_audio_path.strip():
                    ref_audio_dict = {
                        "path": cfg.ref_audio_path.strip(),
                        "orig_name": cfg.ref_audio_path.strip().split("/")[-1],
                        "meta": {"_type": "gradio.FileData"},
                    }
                # read ref text
                ref_text = ""
                if isinstance(cfg.ref_text_path, str) and cfg.ref_text_path.strip():
                    try:
                        with open(cfg.ref_text_path.strip(), "r", encoding="utf-8") as f:
                            ref_text = f.read().strip()
                    except Exception:
                        ref_text = ""

                # call inference
                logger.info("Generating TTS: %s", task.text)
                data = loop.run_until_complete(client.predict(
                    "/inference",
                    task.text,  # text
                    cfg.text_lang,  # text_lang
                    ref_audio_dict,  # ref_audio
                    [],  # aux_ref_audios
                    ref_text,  # prompt_text
                    cfg.text_lang,  # prompt_lang
                    int(cfg.top_k),
                    float(cfg.top_p),
                    float(cfg.temperature),
                    cfg.text_split_method,
                    int(cfg.batch_size),
                    float(cfg.speed_factor),
                    bool(cfg.ref_text_free),
                    bool(cfg.split_bucket),
                    float(cfg.fragment_interval),
                    int(cfg.seed),
                    bool(cfg.keep_random),
                    bool(cfg.parallel_infer),
                    float(cfg.repetition_penalty),
                    str(cfg.sample_steps),
                    bool(cfg.super_sampling),
                ))

                # parse audio url
                audio_url: Optional[str] = None
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    audio_url = data[0].get("url")
                elif isinstance(data, list) and len(data) > 0:
                    try:
                        for sublist in data[0]:
                            if (isinstance(sublist, list) and len(sublist) >= 3 and
                                isinstance(sublist[1], list) and len(sublist[1]) > 0 and
                                sublist[1][0] == "url"):
                                audio_url = sublist[2]
                                break
                    except Exception:
                        pass
                if not audio_url:
                    logger.error("Unexpected inference result: %s", repr(data)[:200])
                    continue

                # download audio
                async def _download(url: str) -> bytes:
                    assert client is not None
                    assert client._session is not None
                    async with client._session.get(url) as resp:
                        resp.raise_for_status()
                        return await resp.read()

                start = time.time()
                buf = loop.run_until_complete(_download(audio_url))
                logger.info("Downloaded audio %.1f KB in %.2fs", len(buf) / 1024, time.time() - start)

                # load and adjust volume (treat tts_volume as dB directly)
                audio = AudioSegment.from_file(io.BytesIO(buf))
                vol_db = float(getattr(cfg, "tts_volume", 0.0) or 0.0)
                # clamp to a safe range to avoid clipping/inaudible extremes
                if vol_db > 24.0:
                    vol_db = 24.0
                if vol_db < -60.0:
                    vol_db = -60.0
                if vol_db != 0.0:
                    audio = audio.apply_gain(vol_db)

                # enqueue to play queue (server-side playback)
                self._audio_q.push(audio, task)
                logger.info("Enqueued audio: %s", task.text)
            except Exception as e:
                logger.error("Predict worker error: %s", e, exc_info=True)
                time.sleep(1.0)

    def _play_worker(self):
        logger.info("TTS play worker started")
        while True:
            try:
                audio, task = self._audio_q.pop()
                try:
                    self._emit_status(getattr(task, "room_id", None), getattr(task, "key", None), "playing")
                except Exception:
                    pass
                logger.info("Playing: %s", task.text)
                # Export to WAV bytes and play synchronously via winsound (no simpleaudio)
                buf = io.BytesIO()
                audio.export(buf, format="wav")
                data = buf.getvalue()
                try:
                    winsound.PlaySound(data, winsound.SND_MEMORY)
                except Exception as we:
                    logger.warning("winsound playback failed: %s; trying ffplay fallback", we)
                    try:
                        if shutil.which("ffplay"):
                            subprocess.run(
                                ["ffplay", "-autoexit", "-nodisp", "-loglevel", "error", "-f", "wav", "-i", "pipe:0"],
                                input=data,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=True,
                            )
                        else:
                            raise
                    except Exception as fe:
                        logger.error("FFplay playback failed: %s", fe)
                finally:
                    try:
                        self._emit_status(getattr(task, "room_id", None), getattr(task, "key", None), "done")
                    except Exception:
                        pass
            except Exception as e:
                logger.error("Play worker error: %s", e, exc_info=True)


# ---- Singleton API ----

_service: Optional[TTSService] = None

def init(settings: Settings):
    global _service
    if _service is None:
        _service = TTSService()
        _service.init(settings)
        try:
            if _global_status_listener:
                _service.set_status_listener(_global_status_listener)
        except Exception:
            pass

def update_settings(settings: Settings):
    if _service is None:
        init(settings)
    else:
        _service.update_settings(settings)

def set_status_listener(fn: Optional[Callable[[Optional[int], Optional[str], str], None]]):
    global _global_status_listener, _service
    _global_status_listener = fn
    if _service is not None:
        try:
            _service.set_status_listener(fn)
        except Exception:
            pass

def enqueue_text(text: str, priority: Priority = Priority.NORMAL, key: Optional[str] = None, room_id: Optional[int] = None) -> bool:
    if _service is None:
        return False
    return _service.enqueue_text(text, priority, key=key, room_id=room_id)

def priority_from_event_type(event_type: str) -> Priority:
    t = (event_type or "").upper()
    if "SUPER_CHAT" in t or t in ("SEND_GIFT", "COMBO_SEND", "GUARD_BUY"):
        return Priority.HIGH
    return Priority.NORMAL


# ---- HTTP helper API for frontend-driven playback ----
# These helpers let the backend talk to Gradio to generate audio bytes
# without performing any server-side playback. They cache model selection
# and only re-select when relevant settings change.

_http_client: Optional[_GradioClient] = None
_selected_sig: Optional[Tuple[str, str, str, str]] = None  # (base_url, sovits_model, gpt_model, text_lang)

async def _ensure_client_and_models(settings: Settings) -> bool:
    global _http_client, _selected_sig
    base = (settings.gradio_server_url or "").strip()
    if not base:
        return False
    if _http_client is None or (_http_client is not None and _http_client.base_url.rstrip("/") != base.rstrip("/") + ""):
        # reset client and selection when base changes
        try:
            if _http_client is not None:
                await _http_client.close()
        except Exception:
            pass
        _http_client = _GradioClient(base, ssl_verify=False)
        _selected_sig = None
    assert _http_client is not None
    await _http_client.ensure()
    sig = (base, str(settings.sovits_model), str(settings.gpt_model), str(settings.text_lang))
    # Select weights only if signature changed
    if _selected_sig != sig:
        try:
            await _http_client.predict("/change_sovits_weights", settings.sovits_model, settings.text_lang, settings.text_lang)
            await _http_client.predict("/change_gpt_weights", settings.gpt_model)
            _selected_sig = sig
        except Exception as e:
            logger.warning("Failed to select models on Gradio server: %s", e)
            return False
    return True


async def gradio_health(settings: Settings) -> Dict[str, Any]:
    """
    Check whether Gradio server is reachable by requesting /config.
    Returns a JSON-serializable dict: { ok, ready, url, message? }
    Note: This does NOT rely on cached client/session to avoid false positives.
    """
    base = (settings.gradio_server_url or "").strip()
    if not base:
        return {"ok": False, "ready": False, "url": base, "message": "未配置 WebUI 服务地址"}
    url = (base if base.endswith("/") else (base + "/")) + "config"
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return {"ok": False, "ready": False, "url": base, "message": f"HTTP {resp.status}: {text[:120]}"}
        # reachable -> ok/ready true
        return {"ok": True, "ready": True, "url": base}
    except Exception as e:
        # On failure, clear cached selection/client so next generate reselects
        global _selected_sig
        _selected_sig = None
        try:
            if _http_client is not None:
                await _http_client.close()
        except Exception:
            pass
        return {"ok": False, "ready": False, "url": base, "message": str(e)}
