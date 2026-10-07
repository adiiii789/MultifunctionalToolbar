"""miku_tts_server.py - Lokaler TTS-Dienst für den 3D-Assistenten

Ablauf pro Satz:  Text --Edge-TTS (online, Microsoft)--> MP3
                       --RVC (lokal, Miku-Stimmmodell)--> WAV

Läuft in einer eigenen Python-Umgebung (venv/ in diesem Ordner, angelegt von
setup_tts.bat) und wird vom Plugin "3D Assistent" bei Bedarf gestartet.
Lauscht nur auf 127.0.0.1.

Start von Hand (zum Testen):
    venv\\Scripts\\python.exe miku_tts_server.py --port 5071 --device auto

Endpunkte:
    GET  /health            -> {"ok": true, "ready": ..., "device": ..., "model": ...}
    POST /tts   (JSON)      -> audio/wav       {"text": "...", optional siehe DEFAULTS}
    POST /convert (Audio)   -> audio/wav       beliebige Aufnahme in Mikus Stimme umwandeln

Einstellungen: tts_config.json neben dieser Datei (wird beim ersten Start
angelegt) - Stimme, Tonhöhe, Index-Stärke, Modell usw.
"""
import argparse
import asyncio
import ctypes
import io
import json
import logging
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
RVC_DIR = HERE / "rvc"                 # Code des offiziellen RVC-Projekts (setup_tts.py)
MODELS_DIR = HERE / "models"           # Stimmmodelle: models/<Ordner>/*.pth (+ *.index)
CONFIG_FILE = HERE / "tts_config.json"
LOG_DIR = HERE / "logs"
NUMBA_CACHE = HERE / "cache" / "numba"   # eigener Cache: kann gefahrlos gelöscht werden

DEFAULTS = {
    "model": "",                       # Ordner- oder Dateiname in models/ ("" = erstes gefundenes)
    "voice": "ja-JP-NanamiNeural",     # Edge-TTS-Sprecherin (liest auch Englisch, mit Akzent)
    "rate": "+0%",                     # Sprechtempo Edge-TTS, z. B. "+10%"
    "volume": "+0%",
    "pitch": "+0Hz",
    "f0_up_key": 6,                    # Tonhöhe für RVC in Halbtönen (Nanami -> Miku: 6)
    "f0_method": "rmvpe",              # "rmvpe" (besser) oder "pm" (schneller)
    "index_rate": 0.75,                # Anteil des Merkmal-Index (0 = aus, spart ~0,6 GB RAM)
    "protect": 0.33,                   # schützt stimmlose Laute (0..0.5)
    "rms_mix_rate": 1.0,
    "max_chars": 1000,
    "threads": 0,                      # CPU-Kerne für die Berechnung (0 = automatisch: halbe Kernzahl, max. 4)
    "low_priority": True               # Dienst mit niedriger Priorität laufen lassen (PC bleibt bedienbar)
}


def cpu_threads(settings):
    n = int(settings.get("threads") or 0)
    if n <= 0:
        n = min(4, max(1, (os.cpu_count() or 2) // 2))
    return n


def limit_cpu(settings):
    """VOR dem Laden von Torch/NumPy/faiss aufrufen: begrenzt die Rechen-Threads
    (Standard wäre: alle Kerne auf 100 %) und senkt die Prozesspriorität."""
    n = str(cpu_threads(settings))
    os.environ["NUMBA_CACHE_DIR"] = str(NUMBA_CACHE)   # librosa-JIT-Cache an einen festen, löschbaren Ort
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = n
    if settings.get("low_priority", True) and os.name == "nt":
        BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
    elif settings.get("low_priority", True):
        try:
            os.nice(5)
        except OSError:
            pass
    return int(n)

log = logging.getLogger("miku_tts")


def _write_config(settings):
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CONFIG_FILE)                 # atomar: nie halb geschrieben


def load_settings():
    settings = dict(DEFAULTS)
    if CONFIG_FILE.is_file():
        try:
            settings.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
            return settings
        except Exception as e:
            # z. B. nach einem Absturz mit Nullen gefüllt: sichern und neu anlegen
            broken = CONFIG_FILE.with_suffix(".defekt.json")
            log.warning("tts_config.json nicht lesbar (%s) - gesichert als %s, neu angelegt", e, broken.name)
            try:
                os.replace(CONFIG_FILE, broken)
            except OSError:
                pass
    try:
        _write_config(settings)
    except OSError:
        pass
    return settings


def find_model(name):
    """-> (Ordner, .pth-Dateiname, .index-Pfad oder "")"""
    candidates = sorted(MODELS_DIR.rglob("*.pth")) if MODELS_DIR.is_dir() else []
    if not candidates:
        raise FileNotFoundError("Kein Stimmmodell (*.pth) in %s - setup_tts.bat ausführen" % MODELS_DIR)
    chosen = candidates[0]
    if name:
        for p in candidates:
            if name in (p.parent.name, p.stem, p.name):
                chosen = p
                break
        else:
            log.warning("Modell '%s' nicht gefunden - nutze %s", name, chosen.name)
    indexes = sorted(i for i in chosen.parent.glob("*.index") if "trained" not in i.name.lower())
    return chosen.parent, chosen.name, str(indexes[0]) if indexes else ""


class _CachedFaiss:
    """Ersetzt faiss in der RVC-Pipeline: Der Index (~0,5 GB) wird nur einmal
    geladen statt bei jedem Satz."""

    def __init__(self, faiss_module):
        self._faiss = faiss_module
        self._cache = {}

    def __getattr__(self, name):
        return getattr(self._faiss, name)

    def read_index(self, path):
        if path not in self._cache:
            log.info("Lade Index %s ...", path)
            self._cache[path] = _CachedIndex(self._faiss.read_index(path))
        return self._cache[path]


class _CachedIndex:
    def __init__(self, index):
        self._index = index
        self._vectors = {}

    def __getattr__(self, name):
        return getattr(self._index, name)

    def reconstruct_n(self, start, count):
        key = (start, count)
        if key not in self._vectors:
            self._vectors[key] = self._index.reconstruct_n(start, count)
        return self._vectors[key]


class Engine:
    """RVC-Modell + HuBERT + Edge-TTS. Nur ein Satz gleichzeitig (Lock)."""

    def __init__(self, device):
        self.lock = threading.Lock()
        self.settings = load_settings()
        self.requested_device = device
        self.ready = False
        self.error = ""
        self.device = "?"
        self.model = ""
        self.vc = None
        self.index_path = ""

    # -- Laden --------------------------------------------------------------
    def load(self):
        t0 = time.time()
        if not (RVC_DIR / "infer").is_dir():
            raise FileNotFoundError("RVC-Code fehlt in %s - setup_tts.bat ausführen" % RVC_DIR)
        if self.requested_device == "cpu":
            sys.modules["torch_directml"] = None       # DirectML-Erkennung in RVC verhindern
        model_dir, model_file, index_path = find_model(self.settings.get("model", ""))
        os.environ["weight_root"] = str(model_dir)
        os.environ["index_root"] = str(model_dir)
        os.environ["outside_index_root"] = str(model_dir)
        os.environ["rmvpe_root"] = str(RVC_DIR / "assets" / "rmvpe")
        os.chdir(RVC_DIR)                               # RVC erwartet sein Projektverzeichnis
        if str(RVC_DIR) not in sys.path:
            sys.path.insert(0, str(RVC_DIR))

        saved_argv = sys.argv
        sys.argv = [sys.argv[0]]                        # RVC-Config parst sonst unsere Argumente
        try:
            from configs.config import Config
            config = Config()
        finally:
            sys.argv = saved_argv
        if self.requested_device == "dml" and not config.dml:
            raise RuntimeError("DirectML angefordert, aber nicht verfügbar (torch-directml installiert?)")

        import torch
        threads = cpu_threads(self.settings)
        torch.set_num_threads(threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass
        import infer.vc.pipeline as rvc_pipeline
        try:
            rvc_pipeline.faiss.omp_set_num_threads(threads)
        except Exception:
            pass
        log.info("CPU-Threads: %d (von %s Kernen), niedrige Priorität: %s", threads, os.cpu_count(),
                 bool(self.settings.get("low_priority", True)))
        from infer.vc.modules import VC
        from infer.vc.utils import load_hubert
        rvc_pipeline.faiss = _CachedFaiss(rvc_pipeline.faiss)

        vc = VC(config)
        vc.get_vc(model_file)
        vc.hubert_model = load_hubert(config)
        self.vc = vc
        self.index_path = index_path if float(self.settings.get("index_rate", 0)) > 0 else ""
        self.device = "dml" if config.dml else str(config.device)
        self.model = "%s/%s" % (model_dir.name, model_file)
        log.info("Modell %s geladen (%s, %s Hz, %s) in %.1f s - Index: %s", self.model, self.device,
                 vc.tgt_sr, vc.version, time.time() - t0, self.index_path or "aus")
        # Aufwärmen mit einem stimmähnlichen Signal (Grundton + Obertöne, 3 s): lädt
        # RMVPE und den Index und durchläuft alle Rechenwege einmal - sonst dauert
        # der erste echte Satz deutlich länger.
        import numpy as np
        t = np.arange(48000) / 16000.0
        f0 = 220 + 25 * np.sin(2 * np.pi * 0.8 * t)
        phase = 2 * np.pi * np.cumsum(f0) / 16000.0
        warm = sum(np.sin(k * phase) / k for k in range(1, 6)) * 0.2 * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
        self._rvc(warm.astype(np.float32), self.settings)
        self.ready = True
        log.info("Bereit nach %.1f s", time.time() - t0)

    # -- Bausteine ------------------------------------------------------------
    def _rvc(self, audio16k, s):
        """float32-Audio (16 kHz, mono) -> (Abtastrate, int16-Audio) in Mikus Stimme."""
        import numpy as np
        audio = audio16k.astype(np.float32)
        peak = float(np.abs(audio).max()) / 0.95 if audio.size else 0
        if peak > 1:
            audio /= peak
        vc = self.vc
        out = vc.pipeline.pipeline(
            vc.hubert_model, vc.net_g, 0, audio, [0, 0, 0],
            int(s["f0_up_key"]), s["f0_method"], self.index_path, float(s["index_rate"]),
            vc.if_f0, vc.tgt_sr, 0, float(s["rms_mix_rate"]), vc.version, float(s["protect"]))
        return vc.tgt_sr, out

    @staticmethod
    def _edge_tts(text, s):
        import edge_tts

        async def run():
            com = edge_tts.Communicate(text, s["voice"], rate=s["rate"], volume=s["volume"], pitch=s["pitch"])
            buf = bytearray()
            async for chunk in com.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        data = asyncio.run(run())
        if not data:
            raise RuntimeError("Edge-TTS hat kein Audio geliefert")
        return data

    @staticmethod
    def _decode_16k(data):
        """Beliebiges Audio (MP3/WAV/...) -> float32 mono 16 kHz (über PyAV, kein ffmpeg.exe nötig)."""
        import av
        import numpy as np
        chunks = []
        with av.open(io.BytesIO(data)) as container:
            resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
        if not chunks:
            raise RuntimeError("Audio konnte nicht dekodiert werden")
        return np.concatenate(chunks).astype(np.float32)

    @staticmethod
    def _wav_bytes(sr, audio):
        import soundfile as sf
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    # -- Öffentlich -----------------------------------------------------------
    def tts(self, text, overrides=None):
        s = dict(self.settings)
        s.update({k: v for k, v in (overrides or {}).items()
                  if k in DEFAULTS and k not in ("model", "max_chars", "threads", "low_priority")})
        text = (text or "").strip()[: int(s["max_chars"])]
        if not text:
            raise ValueError("Kein Text")
        with self.lock:
            t0 = time.time()
            mp3 = self._edge_tts(text, s)
            t1 = time.time()
            audio16 = self._decode_16k(mp3)
            sr, out = self._rvc(audio16, s)
            t2 = time.time()
        log.info("TTS %d Zeichen: Edge %.2f s, RVC %.2f s, Audio %.2f s", len(text), t1 - t0, t2 - t1, len(out) / sr)
        return self._wav_bytes(sr, out), {"edge": t1 - t0, "rvc": t2 - t1, "audio": len(out) / sr}

    def convert(self, data):
        with self.lock:
            t0 = time.time()
            sr, out = self._rvc(self._decode_16k(data), self.settings)
        return self._wav_bytes(sr, out), {"rvc": time.time() - t0, "audio": len(out) / sr}


ENGINE = None


class Handler(BaseHTTPRequestHandler):
    server_version = "MikuTTS/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _wav(self, data, timing):
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-TTS-Timing", json.dumps({k: round(v, 3) for k, v in timing.items()}))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            e = ENGINE
            self._json(200, {"ok": True, "ready": e.ready, "error": e.error, "device": e.device,
                             "model": e.model, "voice": e.settings.get("voice")})
        else:
            self._json(404, {"error": "unbekannter Pfad"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > 20 * 1024 * 1024:
            self._json(400, {"error": "leere oder zu große Anfrage"})
            return
        body = self.rfile.read(length)
        if not ENGINE.ready:
            self._json(503, {"error": ENGINE.error or "Modell lädt noch"})
            return
        try:
            if path == "/tts":
                req = json.loads(body.decode("utf-8"))
                data, timing = ENGINE.tts(req.get("text", ""), req)
            elif path == "/convert":
                data, timing = ENGINE.convert(body)
            else:
                self._json(404, {"error": "unbekannter Pfad"})
                return
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return
        except Exception as e:
            log.error("Fehler: %s\n%s", e, traceback.format_exc())
            self._json(500, {"error": "%s: %s" % (type(e).__name__, e), "device": ENGINE.device})
            return
        self._wav(data, timing)


def _process_alive(pid):
    """Läuft der Prozess noch? (Windows: ohne ihn zu beenden - os.kill wäre dort fatal.)"""
    if os.name == "nt":
        SYNCHRONIZE, WAIT_TIMEOUT = 0x00100000, 0x102
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _watch_parent(pid, server):
    while True:
        time.sleep(2)
        if not _process_alive(pid):
            log.info("Toolbar beendet - TTS-Dienst fährt herunter")
            server.shutdown()
            return


def main():
    global ENGINE
    ap = argparse.ArgumentParser(description="Lokaler Miku-TTS-Dienst (Edge-TTS + RVC)")
    ap.add_argument("--port", type=int, default=5071)
    ap.add_argument("--device", choices=["auto", "cpu", "dml"], default="auto",
                    help="auto = DirectML (AMD/Intel-GPU) falls installiert, sonst CPU")
    ap.add_argument("--parent-pid", type=int, default=0, help="beenden, wenn dieser Prozess endet")
    args = ap.parse_args()

    limit_cpu(load_settings())          # vor allem anderen: Threads + Priorität
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8")])
    ENGINE = Engine(args.device)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    if args.parent_pid:
        threading.Thread(target=_watch_parent, args=(args.parent_pid, server), daemon=True).start()

    def load():
        try:
            try:
                ENGINE.load()
            except Exception as e:
                # Typische Absturz-Folge: kaputter JIT-Cache ("invalid load key") -> löschen, nochmal laden
                if "load key" not in str(e) and "pickle" not in type(e).__name__.lower():
                    raise
                log.warning("Kaputter Cache (%s) - lösche %s und lade erneut", e, NUMBA_CACHE)
                import shutil
                shutil.rmtree(NUMBA_CACHE, ignore_errors=True)
                ENGINE.load()
        except Exception as e:
            ENGINE.error = "%s: %s" % (type(e).__name__, e)
            log.error("Laden fehlgeschlagen: %s\n%s", e, traceback.format_exc())

    threading.Thread(target=load, daemon=True).start()   # /health antwortet schon während des Ladens
    log.info("Miku-TTS lauscht auf http://127.0.0.1:%d (Gerät: %s)", args.port, args.device)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
