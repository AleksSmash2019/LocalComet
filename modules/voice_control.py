from datetime import datetime
import json
import os
from pathlib import Path
from modules.project_paths import get_project_root
import queue
import subprocess
import tempfile
import time
import wave

from core.state import get_value, set_value


ROOT_DIR = get_project_root()
REPORTS_DIR = ROOT_DIR / "Projects" / "Reports" / "voice_sessions"
VOICE_MODELS_DIR = ROOT_DIR / "Projects" / "VoiceModels"
DEFAULT_VOSK_MODEL_DIR = VOICE_MODELS_DIR / "vosk-model-small-ru-0.22"
DEFAULT_WHISPER_MODEL_SIZE = "medium"
DEFAULT_PIPER_EXE = Path.home() / "Documents" / "piper" / "piper.exe"
DEFAULT_PIPER_VOICE = Path.home() / "Documents" / "piper" / "ru_RU-dmitri-medium.onnx"

VOICE_DEPENDENCY_HINT = (
    "Voice dependencies are not installed. Install SpeechRecognition and PyAudio "
    "for microphone input, and pyttsx3 for local TTS."
)

_LISTENING = False
_MUTED = bool(get_value("voice_tts_muted", False))
_WHISPER_MODEL = None


DANGEROUS_TERMS = [
    "оплатить",
    "оплати",
    "купить",
    "купи",
    "оформить заказ",
    "добавить в корзину",
    "корзина",
    "заказ",
    "ставка",
    "поставить ставку",
    "казино",
    "банк",
    "кредит",
    "пароль",
    "логин",
    "войти",
    "зарегистрироваться",
    "2fa",
    "смс",
    "sms",
    "удалить аккаунт",
    "закрыть аккаунт",
    "отправь деньги",
    "переведи деньги",
    "kaspi",
    "банковская карта",
    "pay",
    "buy",
    "order",
    "checkout",
    "cart",
    "bet",
    "casino",
    "bank",
    "password",
    "login",
    "sign in",
    "sign up",
    "delete account",
    "close account",
    "send money",
    "transfer money",
    "credit card",
]


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _import_ok(module_name):
    try:
        __import__(module_name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _windows_sapi_available():
    try:
        import win32com.client  # noqa: F401

        return True, ""
    except Exception as exc:
        return False, str(exc)


def _windows_sapi_recognition_available():
    try:
        import win32com.client

        win32com.client.Dispatch("SAPI.SpSharedRecognizer")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _find_vosk_model():
    configured = str(get_value("voice_vosk_model_path", "") or "").strip()

    candidates = []

    if configured:
        candidates.append(Path(configured))

    candidates.append(DEFAULT_VOSK_MODEL_DIR)

    if VOICE_MODELS_DIR.exists():
        candidates.extend(sorted(VOICE_MODELS_DIR.glob("vosk-model*ru*")))
        candidates.extend(sorted(VOICE_MODELS_DIR.glob("*ru*")))

    for path in candidates:
        if path.exists() and path.is_dir() and (path / "conf").exists():
            return path

    return None


def _piper_paths():
    exe = Path(str(get_value("voice_piper_exe", str(DEFAULT_PIPER_EXE)) or DEFAULT_PIPER_EXE))
    voice = Path(str(get_value("voice_piper_voice", str(DEFAULT_PIPER_VOICE)) or DEFAULT_PIPER_VOICE))
    return exe, voice


def _piper_available():
    exe, voice = _piper_paths()
    return bool(exe.exists() and voice.exists()), exe, voice


def check_voice_dependencies():
    faster_whisper_ok, faster_whisper_error = _import_ok("faster_whisper")
    numpy_ok, numpy_error = _import_ok("numpy")
    speech_ok, speech_error = _import_ok("speech_recognition")
    sphinx_ok, sphinx_error = _import_ok("pocketsphinx")
    vosk_ok, vosk_error = _import_ok("vosk")
    sounddevice_ok, sounddevice_error = _import_ok("sounddevice")
    tts_ok, tts_error = _import_ok("pyttsx3")
    pyaudio_ok, pyaudio_error = _import_ok("pyaudio")
    sapi_ok, sapi_error = _windows_sapi_available()
    sapi_stt_ok, sapi_stt_error = _windows_sapi_recognition_available()
    vosk_model = _find_vosk_model()
    vosk_usable = bool(vosk_ok and sounddevice_ok and vosk_model)
    piper_ok, piper_exe, piper_voice = _piper_available()
    faster_whisper_usable = bool(faster_whisper_ok and sounddevice_ok and numpy_ok)

    messages = []

    if not faster_whisper_ok:
        messages.append(f"faster-whisper unavailable: {faster_whisper_error}")

    if not numpy_ok:
        messages.append(f"numpy unavailable: {numpy_error}")

    if not vosk_ok:
        messages.append(f"Vosk unavailable: {vosk_error}")

    if not sounddevice_ok:
        messages.append(f"sounddevice unavailable: {sounddevice_error}")

    if vosk_ok and sounddevice_ok and not vosk_model:
        messages.append(
            "Russian Vosk model not found. Put a Vosk Russian model folder into "
            f"{VOICE_MODELS_DIR}, for example vosk-model-small-ru-0.22."
        )

    if not speech_ok:
        messages.append(f"SpeechRecognition unavailable: {speech_error}")

    if not pyaudio_ok:
        messages.append(f"PyAudio unavailable: {pyaudio_error}")

    if not tts_ok and not sapi_ok:
        messages.append(f"TTS unavailable: pyttsx3={tts_error}; Windows SAPI={sapi_error}")

    if not piper_ok:
        messages.append(f"Piper TTS unavailable: exe={piper_exe.exists()} voice={piper_voice.exists()}")

    if speech_ok and pyaudio_ok and not sphinx_ok:
        messages.append(f"Offline Sphinx STT unavailable: {sphinx_error}")

    if sapi_stt_ok and not vosk_usable and (not speech_ok or not pyaudio_ok or not sphinx_ok):
        messages.append("Windows SAPI speech recognition fallback is available for Push to talk.")

    if not sapi_stt_ok and (not speech_ok or not pyaudio_ok):
        messages.append(VOICE_DEPENDENCY_HINT)

    if sapi_ok and not sapi_stt_ok:
        messages.append(f"Windows SAPI recognition unavailable: {sapi_stt_error}")

    return {
        "speech_recognition_available": speech_ok,
        "pocketsphinx_available": sphinx_ok,
        "faster_whisper_available": faster_whisper_ok,
        "numpy_available": numpy_ok,
        "usable_faster_whisper_ru": faster_whisper_usable,
        "faster_whisper_model_size": str(get_value("voice_whisper_model_size", DEFAULT_WHISPER_MODEL_SIZE) or DEFAULT_WHISPER_MODEL_SIZE),
        "vosk_available": vosk_ok,
        "sounddevice_available": sounddevice_ok,
        "vosk_model_path": str(vosk_model) if vosk_model else "",
        "usable_vosk_ru": vosk_usable,
        "piper_available": piper_ok,
        "piper_exe": str(piper_exe),
        "piper_voice": str(piper_voice),
        "pyttsx3_available": tts_ok,
        "pyaudio_available": pyaudio_ok,
        "windows_sapi_available": sapi_ok,
        "windows_sapi_stt_available": sapi_stt_ok,
        "usable_stt": bool(faster_whisper_usable or vosk_usable or (speech_ok and pyaudio_ok and sphinx_ok) or sapi_stt_ok),
        "usable_tts": bool(piper_ok or tts_ok or sapi_ok),
        "messages": messages,
    }


def get_voice_status():
    deps = check_voice_dependencies()
    return {
        "enabled": bool(deps.get("usable_stt") or deps.get("usable_tts")),
        "listening": _LISTENING,
        "muted": bool(get_value("voice_tts_muted", _MUTED)),
        "stt_engine": (
            "Faster-Whisper Russian offline"
            if deps.get("usable_faster_whisper_ru")
            else (
                "Vosk Russian offline"
                if deps.get("usable_vosk_ru")
                else (
                    "SpeechRecognition + PyAudio + PocketSphinx"
                    if deps.get("speech_recognition_available") and deps.get("pyaudio_available") and deps.get("pocketsphinx_available")
                    else ("Windows SAPI" if deps.get("windows_sapi_stt_available") else "unavailable")
                )
            )
        ),
        "tts_engine": (
            "Piper ru_RU dmitri medium"
            if deps.get("piper_available")
            else ("pyttsx3" if deps.get("pyttsx3_available") else ("Windows SAPI" if deps.get("windows_sapi_available") else "unavailable"))
        ),
        "last_transcript": get_value("last_voice_transcript", ""),
        "last_error": get_value("last_voice_error", ""),
        "last_report": get_value("last_voice_session_report", ""),
        "dependencies": deps,
    }


def transcribe_once(timeout=5, phrase_time_limit=10, language="ru-RU"):
    global _LISTENING

    deps = check_voice_dependencies()

    if not deps.get("usable_stt"):
        message = (
            VOICE_DEPENDENCY_HINT
            + " Offline STT also needs pocketsphinx. Audio was not sent to external services."
        )
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "unavailable"}

    if deps.get("usable_faster_whisper_ru"):
        return _transcribe_once_faster_whisper(timeout=timeout, phrase_time_limit=phrase_time_limit)

    if deps.get("usable_vosk_ru"):
        return _transcribe_once_vosk(timeout=timeout, phrase_time_limit=phrase_time_limit)

    if deps.get("windows_sapi_stt_available") and not (
        deps.get("speech_recognition_available") and deps.get("pyaudio_available") and deps.get("pocketsphinx_available")
    ):
        return _transcribe_once_windows_sapi(timeout=timeout, phrase_time_limit=phrase_time_limit)

    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        _LISTENING = True

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

        text = recognizer.recognize_sphinx(audio, language=language)
        set_value("last_voice_transcript", text)
        set_value("last_voice_error", "")
        return {"ok": True, "text": text, "error": None, "engine": "SpeechRecognition/PocketSphinx"}
    except Exception as exc:
        message = f"Voice recognition failed: {exc}"
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "SpeechRecognition"}
    finally:
        _LISTENING = False


def _get_whisper_model():
    global _WHISPER_MODEL

    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel

        model_size = str(get_value("voice_whisper_model_size", DEFAULT_WHISPER_MODEL_SIZE) or DEFAULT_WHISPER_MODEL_SIZE)
        _WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")

    return _WHISPER_MODEL


def _transcribe_once_faster_whisper(timeout=5, phrase_time_limit=10, samplerate=16000):
    global _LISTENING

    try:
        import numpy as np
        import sounddevice as sd

        seconds = max(1, int(phrase_time_limit or timeout or 7))
        _LISTENING = True
        audio = sd.rec(
            int(seconds * samplerate),
            samplerate=samplerate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        _LISTENING = False
        audio = audio.flatten()
        rms_level = float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0

        if rms_level < 0.001:
            message = (
                "Microphone signal is almost silent. Check the selected Windows input device "
                "and microphone volume."
            )
            set_value("last_voice_error", message)
            return {"ok": False, "text": "", "error": message, "engine": "Faster-Whisper Russian offline"}

        model = _get_whisper_model()
        segments, _info = model.transcribe(
            audio,
            language="ru",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()

        if text:
            set_value("last_voice_transcript", text)
            set_value("last_voice_error", "")
            return {"ok": True, "text": text, "error": None, "engine": "Faster-Whisper Russian offline"}

        message = f"No Russian speech recognized by Faster-Whisper. Microphone rms={rms_level:.4f}."
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Faster-Whisper Russian offline"}
    except Exception as exc:
        message = f"Faster-Whisper recognition failed: {exc}"
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Faster-Whisper Russian offline"}
    finally:
        _LISTENING = False


def _transcribe_once_vosk(timeout=5, phrase_time_limit=10, samplerate=16000):
    global _LISTENING

    try:
        import sounddevice as sd
        from vosk import KaldiRecognizer, Model

        model_path = _find_vosk_model()

        if not model_path:
            message = (
                "Russian Vosk model not found. Put a Vosk Russian model folder into "
                f"{VOICE_MODELS_DIR}, for example vosk-model-small-ru-0.22."
            )
            set_value("last_voice_error", message)
            return {"ok": False, "text": "", "error": message, "engine": "Vosk Russian offline"}

        audio_queue = queue.Queue()
        recognizer = KaldiRecognizer(Model(str(model_path)), int(samplerate))

        def callback(indata, frames, time_info, status):
            if status:
                set_value("last_voice_error", str(status))
            audio_queue.put(bytes(indata))

        _LISTENING = True
        deadline = time.monotonic() + max(1, int(timeout or 5)) + max(1, int(phrase_time_limit or 10))

        with sd.RawInputStream(
            samplerate=int(samplerate),
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            while _LISTENING and time.monotonic() < deadline:
                try:
                    data = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    payload = json.loads(recognizer.Result() or "{}")
                    text = str(payload.get("text", "") or "").strip()

                    if text:
                        set_value("last_voice_transcript", text)
                        set_value("last_voice_error", "")
                        return {"ok": True, "text": text, "error": None, "engine": "Vosk Russian offline"}

        payload = json.loads(recognizer.FinalResult() or "{}")
        text = str(payload.get("text", "") or "").strip()

        if text:
            set_value("last_voice_transcript", text)
            set_value("last_voice_error", "")
            return {"ok": True, "text": text, "error": None, "engine": "Vosk Russian offline"}

        message = "No Russian speech recognized by Vosk. Check microphone input and speak closer to the mic."
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Vosk Russian offline"}
    except Exception as exc:
        message = f"Vosk recognition failed: {exc}"
        set_value("last_voice_error", message)
        return {"ok": False, "text": "", "error": message, "engine": "Vosk Russian offline"}
    finally:
        _LISTENING = False


def _transcribe_once_windows_sapi(timeout=5, phrase_time_limit=10):
    global _LISTENING

    try:
        import pythoncom
        import win32com.client

        class RecognitionEvents:
            text = ""
            error = ""

            def OnRecognition(self, stream_number, stream_position, recognition_type, result):
                try:
                    self.text = result.PhraseInfo.GetText()
                except Exception as exc:
                    self.error = str(exc)

        def listen_with_context(context_factory):
            context_raw = context_factory()
            context = win32com.client.WithEvents(context_raw, RecognitionEvents)
            grammar = context_raw.CreateGrammar()
            grammar.DictationSetState(1)

            try:
                deadline = time.monotonic() + max(1, int(timeout or 5)) + max(1, int(phrase_time_limit or 10))

                while _LISTENING and time.monotonic() < deadline and not getattr(context, "text", ""):
                    pythoncom.PumpWaitingMessages()
                    time.sleep(0.05)

                text = str(getattr(context, "text", "") or "").strip()
                error = str(getattr(context, "error", "") or "").strip()
                return text, error
            finally:
                try:
                    grammar.DictationSetState(0)
                except Exception:
                    pass

        pythoncom.CoInitialize()
        _LISTENING = True

        try:
            try:
                text, error = listen_with_context(lambda: win32com.client.Dispatch("SAPI.SpSharedRecoContext"))
                engine = "Windows SAPI Shared"
            except Exception as shared_exc:
                recognizer = win32com.client.Dispatch("SAPI.SpInprocRecognizer")
                text, error = listen_with_context(recognizer.CreateRecoContext)
                engine = f"Windows SAPI InProc after shared failed: {shared_exc}"

            if text:
                set_value("last_voice_transcript", text)
                set_value("last_voice_error", "")
                return {"ok": True, "text": text, "error": None, "engine": engine}

            message = error or "No speech recognized by Windows SAPI. Check microphone and Windows speech language settings."
            set_value("last_voice_error", message)
            return {"ok": False, "text": "", "error": message, "engine": engine}
        finally:
            _LISTENING = False
            pythoncom.CoUninitialize()
    except Exception as exc:
        message = f"Windows SAPI recognition failed: {exc}"
        set_value("last_voice_error", message)
        _LISTENING = False
        return {"ok": False, "text": "", "error": message, "engine": "Windows SAPI"}


def stop_listening():
    global _LISTENING
    _LISTENING = False

    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        pass

    return {"ok": True, "listening": False}


def speak_text(text, enabled=True):
    if not enabled or bool(get_value("voice_tts_muted", False)):
        return {"ok": False, "error": "TTS is muted.", "engine": "muted"}

    value = str(text or "").strip()

    if not value:
        return {"ok": False, "error": "Nothing to speak.", "engine": "none"}

    deps = check_voice_dependencies()

    if deps.get("piper_available"):
        exe, voice = _piper_paths()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = tmp.name

        try:
            import numpy as np
            import sounddevice as sd

            subprocess.run(
                [str(exe), "--model", str(voice), "--output_file", out_path],
                input=value[:1200].encode("utf-8"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            with wave.open(out_path, "rb") as wf:
                audio_data = wf.readframes(wf.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                sd.play(audio_np, samplerate=wf.getframerate())
                sd.wait()

            return {"ok": True, "error": None, "engine": "Piper ru_RU dmitri medium"}
        except Exception as exc:
            set_value("last_voice_error", str(exc))
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    if deps.get("pyttsx3_available"):
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.say(value[:1200])
            engine.runAndWait()
            return {"ok": True, "error": None, "engine": "pyttsx3"}
        except Exception as exc:
            set_value("last_voice_error", str(exc))

    if deps.get("windows_sapi_available"):
        try:
            import win32com.client

            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(value[:1200])
            return {"ok": True, "error": None, "engine": "Windows SAPI"}
        except Exception as exc:
            set_value("last_voice_error", str(exc))
            return {"ok": False, "error": f"TTS failed: {exc}", "engine": "Windows SAPI"}

    message = "Local TTS is unavailable. Install pyttsx3 or enable Windows SAPI support."
    set_value("last_voice_error", message)
    return {"ok": False, "error": message, "engine": "unavailable"}


def classify_voice_command_safety(text):
    lower = str(text or "").lower()
    matched = [term for term in DANGEROUS_TERMS if term in lower]

    if matched:
        return {
            "safe": False,
            "needs_confirmation": True,
            "blocked_reason": "Voice command requires typed confirmation because it may be risky.",
            "matched_terms": matched,
        }

    return {
        "safe": True,
        "needs_confirmation": False,
        "blocked_reason": "",
        "matched_terms": [],
    }


def save_voice_session_report(
    transcript="",
    safety=None,
    command_result="",
    errors=None,
    status=None,
):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"voice_session_{_stamp()}.md"
    safety = safety or classify_voice_command_safety(transcript)
    status = status or get_voice_status()
    errors = errors or []

    lines = [
        "# Voice Session",
        "",
        "## Summary",
        f"- created_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- safe: {safety.get('safe')}",
        f"- needs_confirmation: {safety.get('needs_confirmation')}",
        "",
        "## Voice status",
    ]

    for key, value in status.items():
        if key != "dependencies":
            lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Transcript",
        str(transcript or "нет"),
        "",
        "## Safety classification",
        f"- blocked_reason: {safety.get('blocked_reason') or 'нет'}",
        f"- matched_terms: {', '.join(safety.get('matched_terms') or []) or 'нет'}",
        "",
        "## Command result",
        str(command_result or "нет"),
        "",
        "## Errors",
    ])

    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- нет")

    lines.extend([
        "",
        "## Next steps",
        "- Проверь transcript перед выполнением risky-команд.",
        "- Для опасных действий используй ручное typed confirmation вне Voice Mode.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    set_value("last_voice_session_report", str(path))
    set_value("last_voice_transcript", str(transcript or ""))
    set_value("last_voice_result", str(command_result or ""))
    set_value("last_voice_error", "\n".join(errors) if errors else "")
    return path


def latest_voice_session_report():
    path = str(get_value("last_voice_session_report", "") or "").strip()

    if path and Path(path).exists():
        return path

    if not REPORTS_DIR.exists():
        return ""

    reports = list(REPORTS_DIR.glob("voice_session_*.md"))

    if not reports:
        return ""

    return str(max(reports, key=lambda item: item.stat().st_mtime))


def set_tts_muted(muted=True):
    set_value("voice_tts_muted", bool(muted))
    return bool(muted)
