"""Sprachliche Ein- und Ausgabe - komplett lokal.

Sprache läuft in Python, nicht im Browser: Qt WebEngine bringt keine
Spracherkennung mit.

Spracheingabe (Speech-to-Text): Mikrofon über sounddevice aufnehmen, faster-whisper
macht daraus Text. Das Whisper-Modell wird beim ersten Gebrauch geladen.
Sprachausgabe (Text-to-Speech): Piper (neuronale Stimme, wird beim ersten Gebrauch
geladen); geht das nicht, die eingebaute Windows-Stimme (SAPI). Hier entsteht nur das
Audio - abgespielt wird es im Viewer (assistant_server.py, POST /tts liefert die WAV).

Ablauf im Chat (viewer/js/voice.js über assistant_server.py): Mikrofon-Knopf ->
start(), zweiter Klick -> stop() liefert den Text, Escape -> cancel(). start()
kehrt sofort zurück, sonst käme ein Abbruch erst danach an.

Fehlen die Pakete, liefern create_speech_input() / create_synthesizer() None und
der Viewer blendet die Sprachfunktionen aus.

Eigener Prozess: PyQt5 bringt eine ältere msvcp140.dll mit - ist Qt zuerst geladen, stürzt
der Import von onnxruntime (Piper, Sprachfilter von faster-whisper) ab. Deshalb läuft dieser
Dienst nicht im Toolbar-Prozess.
"""
from __future__ import annotations

import importlib.util
import logging
import re
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from backend import config

log = logging.getLogger(__name__)

WHISPER_SAMPLE_RATE = 16000     # erwartet faster-whisper
MIN_RECORDING_S = 0.3           # kürzer = versehentlicher Doppelklick, nichts erkennen


@runtime_checkable
class SpeechInput(Protocol):
    def start(self) -> None:
        """Aufnahme starten; kehrt sofort zurück."""
        ...

    def stop(self) -> str:
        """Aufnahme beenden und als Text zurückgeben (leer, wenn nichts erkannt wurde)."""
        ...

    def cancel(self) -> None:
        """Aufnahme verwerfen."""
        ...


class Microphone:
    """Nimmt mono mit WHISPER_SAMPLE_RATE auf; die Aufnahme läuft im Audio-Thread von sounddevice."""

    def __init__(self, sample_rate: int = WHISPER_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._stream: Any = None
        self._chunks: list[Any] = []

    def start(self) -> None:
        import sounddevice as sd

        if self._stream is not None:
            return
        self._chunks = []
        try:
            self._stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                                          callback=self._on_audio)
        except sd.PortAudioError as exc:
            raise RuntimeError(f"Kein Mikrofon verfügbar: {exc}") from exc
        self._stream.start()

    def stop(self) -> Any:
        """Aufnahme beenden; liefert die Samples als float32-Array (leer, wenn nicht aufgenommen wurde)."""
        import numpy as np

        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        chunks, self._chunks = self._chunks, []
        return np.concatenate(chunks)[:, 0] if chunks else np.zeros(0, dtype=np.float32)

    def _on_audio(self, data, frames, time, status) -> None:  # noqa: ARG002 (sounddevice-API)
        self._chunks.append(data.copy())


class WhisperTranscriber:
    """faster-whisper auf der CPU; das Modell wird einmal geladen (beim ersten Mal heruntergeladen)."""

    def __init__(self, model_size: str, language: str | None, download_dir: Path):
        self._model_size = model_size
        self._language = language
        self._download_dir = download_dir
        self._model: Any = None
        self._lock = threading.Lock()

    def preload(self) -> None:
        """Modell im Hintergrund laden, damit transcribe() nach der Aufnahme nicht darauf warten muss."""
        if self._model is None:
            threading.Thread(target=self._load, name="whisper-load", daemon=True).start()

    def transcribe(self, audio: Any) -> str:
        segments, _info = self._load().transcribe(audio, language=self._language, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                log.info("Lade Whisper-Modell %r …", self._model_size)
                self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8",
                                           download_root=str(self._download_dir))
            return self._model


class VoiceInput:
    """SpeechInput aus Mikrofon und Transkription."""

    def __init__(self, microphone: Any, transcriber: Any):
        self._microphone = microphone
        self._transcriber = transcriber

    def start(self) -> None:
        self._microphone.start()
        self._transcriber.preload()

    def stop(self) -> str:
        audio = self._microphone.stop()
        if len(audio) < MIN_RECORDING_S * self._microphone.sample_rate:
            return ""
        return self._transcriber.transcribe(audio)

    def cancel(self) -> None:
        self._microphone.stop()


# --- Sprachausgabe -------------------------------------------------------------

class Synthesizer(Protocol):
    def synthesize(self, text: str) -> tuple[Any, int]:
        """Text in Audio umwandeln: (int16-Samples mono, Abtastrate)."""
        ...


class PiperSynthesizer:
    """Neuronale Stimme mit Piper; die Stimme wird beim ersten Gebrauch heruntergeladen."""

    def __init__(self, voice: str, voice_dir: Path):
        self._voice_name = voice
        self._voice_dir = voice_dir
        self._voice: Any = None

    def synthesize(self, text: str) -> tuple[Any, int]:
        import numpy as np

        voice = self._load()
        chunks = [chunk.audio_int16_array for chunk in voice.synthesize(text)]
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
        return audio, voice.config.sample_rate

    def _load(self) -> Any:
        if self._voice is None:
            from piper import PiperVoice

            model = self._voice_dir / f"{self._voice_name}.onnx"
            if not model.exists():
                from piper.download_voices import download_voice

                log.info("Lade Piper-Stimme %r …", self._voice_name)
                self._voice_dir.mkdir(parents=True, exist_ok=True)
                download_voice(self._voice_name, self._voice_dir)
            self._voice = PiperVoice.load(model)
        return self._voice


class SapiSynthesizer:
    """Eingebaute Windows-Stimme; bevorzugt eine in SPEECH_LANGUAGE, sonst die Standardstimme."""

    _FORMAT_22KHZ_16BIT_MONO = 22   # SpeechAudioFormatType.SAFT22kHz16BitMono
    _SAMPLE_RATE = 22050
    _LANGUAGE_IDS = {"de": "407", "en": "409"}   # Windows-Sprachkennungen (hex)

    def __init__(self, language: str | None):
        self._language = language

    def synthesize(self, text: str) -> tuple[Any, int]:
        import numpy as np
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()   # COM pro Thread; mehrfach aufrufen ist erlaubt
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        self._select_voice(voice)
        stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
        stream.Format.Type = self._FORMAT_22KHZ_16BIT_MONO
        voice.AudioOutputStream = stream
        voice.Speak(text)
        return np.frombuffer(bytes(stream.GetData()), dtype=np.int16), self._SAMPLE_RATE

    def _select_voice(self, voice: Any) -> None:
        wanted = self._LANGUAGE_IDS.get(self._language or "")
        if wanted is None:
            return
        for token in voice.GetVoices():
            if wanted in token.GetAttribute("Language").lower().split(";"):
                voice.Voice = token
                return


class FallbackSynthesizer:
    """Nimmt den ersten Synthesizer, der funktioniert; ein fehlgeschlagener wird nicht erneut versucht."""

    def __init__(self, synthesizers: Sequence[Synthesizer]):
        self._synthesizers = list(synthesizers)

    def synthesize(self, text: str) -> tuple[Any, int]:
        while self._synthesizers:
            synthesizer = self._synthesizers[0]
            try:
                return synthesizer.synthesize(text)
            except Exception:  # noqa: BLE001  # z. B. Stimme nicht ladbar - nächsten versuchen
                log.exception("%s geht nicht, nehme den nächsten", type(synthesizer).__name__)
                self._synthesizers.pop(0)
        raise RuntimeError("Keine Sprachausgabe verfügbar")


_MARKDOWN = re.compile(r"[*_#`>|~]+")
_URL = re.compile(r"https?://\S+")


def speakable(text: str) -> str:
    """Markdown-Zeichen und Links entfernen - die würde die Stimme sonst mitlesen."""
    text = _URL.sub("", text)
    text = _MARKDOWN.sub(" ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


# --- Fabriken ------------------------------------------------------------------

def _installed(*modules: str) -> bool:
    return all(importlib.util.find_spec(module) is not None for module in modules)


def create_speech_input() -> SpeechInput | None:
    """Spracheingabe mit Whisper, oder None, wenn die Pakete fehlen."""
    if not _installed("sounddevice", "numpy", "faster_whisper"):
        log.info("Spracheingabe aus: sounddevice/faster-whisper nicht installiert")
        return None
    transcriber = WhisperTranscriber(config.WHISPER_MODEL, config.SPEECH_LANGUAGE or None,
                                     config.SPEECH_DIR / "whisper")
    return VoiceInput(Microphone(), transcriber)


def create_synthesizer() -> Synthesizer | None:
    """Piper, ersatzweise Windows-Stimme - nur das Audio, ohne Abspielen (das macht der Viewer:
    Lautstärke, Mund folgt dem Audio). None, wenn beides fehlt."""
    synthesizers: list[Synthesizer] = []
    if _installed("piper"):
        synthesizers.append(PiperSynthesizer(config.PIPER_VOICE, config.SPEECH_DIR / "piper"))
    if _installed("win32com"):
        synthesizers.append(SapiSynthesizer(config.SPEECH_LANGUAGE or None))
    if not synthesizers:
        log.info("Sprachausgabe aus: weder Piper noch die Windows-Stimme verfügbar")
        return None
    return FallbackSynthesizer(synthesizers)
