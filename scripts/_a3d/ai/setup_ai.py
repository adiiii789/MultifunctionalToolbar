"""setup_ai.py - Einmalige Einrichtung des KI-Dienstes (wird von setup_ai.bat gestartet)

Legt in diesem Ordner venv/ an (Pakete aus requirements-ai.txt), lädt das Whisper-Modell
und die Piper-Stimme vorab (sonst dauert die erste Spracheingabe Minuten) und prüft, ob
Ollama läuft und ein Modell installiert ist.

Aufruf:  py -3.12 setup_ai.py [--skip-models]
Kann gefahrlos erneut gestartet werden - fertige Schritte werden übersprungen.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / "venv"

PRELOAD = """
import sys
sys.path.insert(0, ".")
from backend import config, speech
print("Whisper-Modell %r ..." % config.WHISPER_MODEL, flush=True)
speech.WhisperTranscriber(config.WHISPER_MODEL, None, config.SPEECH_DIR / "whisper")._load()
print("Piper-Stimme %r ..." % config.PIPER_VOICE, flush=True)
speech.PiperSynthesizer(config.PIPER_VOICE, config.SPEECH_DIR / "piper").synthesize("Test")
print("Modelle liegen in", config.SPEECH_DIR)
"""


def step(msg):
    print("\n=== " + msg, flush=True)


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd, **kw):
    print("> " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def check_ollama():
    url = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            models = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception as e:
        print("Ollama ist unter %s nicht erreichbar (%s)." % (url, e))
        print("-> https://ollama.com installieren und starten, dann z. B.:  ollama pull qwen3:8b")
        return
    if models:
        print("Ollama läuft, installierte Modelle: " + ", ".join(models))
    else:
        print("Ollama läuft, aber es ist kein Modell installiert -> z. B.:  ollama pull qwen3:8b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-models", action="store_true", help="Whisper/Piper nicht vorab laden")
    args = ap.parse_args()
    v = sys.version_info
    if not ((3, 10) <= (v.major, v.minor) <= (3, 12)) or sys.maxsize < 2**32:
        sys.exit("Bitte Python 3.10, 3.11 oder 3.12 (64 Bit) verwenden - gefunden: %s" % sys.version.split()[0])

    step("Python-Umgebung (venv)")
    if not venv_python().exists():
        run([sys.executable, "-m", "venv", VENV])
    run([venv_python(), "-m", "pip", "install", "--upgrade", "pip"])
    run([venv_python(), "-m", "pip", "install", "-r", HERE / "requirements-ai.txt"])

    if not args.skip_models:
        step("Sprachmodelle vorab laden (Whisper ~480 MB, Piper ~60 MB)")
        run([venv_python(), "-c", PRELOAD], cwd=HERE)

    step("Ollama")
    check_ollama()

    env_file = HERE / "mcp_servers" / ".env"
    if not env_file.exists():
        print("\nE-Mail (optional): mcp_servers/.env.example nach mcp_servers/.env kopieren und ausfüllen.")
    print("\nFertig. Toolbar neu starten.")


if __name__ == "__main__":
    main()
