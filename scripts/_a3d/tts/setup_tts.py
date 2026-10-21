"""setup_tts.py - Einmalige Einrichtung des lokalen Miku-TTS (wird von setup_tts.bat gestartet)

Legt in diesem Ordner an:
    venv/     eigene Python-Umgebung (Torch, RVC-Abhängigkeiten, Edge-TTS)
    rvc/      Code des offiziellen RVC-Projekts (fester Stand, von GitHub)
    rvc/assets/hubert_base, rvc/assets/rmvpe   HuBERT + Tonhöhenmodell (Hugging Face)
    models/   Miku-Stimmmodell (Hugging Face: NoCrypt/miku_RVC)
und macht zum Schluss einen Probelauf.

Aufruf:  py -3.12 setup_tts.py [--dml | --no-dml] [--model ORDNER] [--skip-test]
         py -3.12 setup_tts.py --repair     (nach Absturz: Caches löschen, Modelle prüfen)
Kann gefahrlos erneut gestartet werden - fertige Schritte werden übersprungen.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / "venv"
RVC_DIR = HERE / "rvc"
MODELS_DIR = HERE / "models"

# Fester Stand des RVC-Projekts (getestet): transformers-HuBERT statt fairseq, DirectML-Unterstützung
RVC_COMMIT = "81eed5e8f68b6bed1789f682fe78cdd324495afc"
RVC_ZIP = "https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI/archive/" + RVC_COMMIT + ".zip"

DEFAULT_MODEL = "1a_miku_default_rvc_(aple)"      # wie im Hugging-Face-Space "mikuTTS"

TORCH = ["torch==2.4.1", "torchaudio==2.4.1"]     # passend zu torch-directml 0.2.5
DML = ["torch-directml==0.2.5.dev240914", "onnxruntime-directml>=1.20,<2"]
NO_DML = ["onnxruntime>=1.20,<2"]


def step(msg):
    print("\n=== " + msg, flush=True)


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd, **kw):
    print("> " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def check_python():
    v = sys.version_info
    if not ((3, 10) <= (v.major, v.minor) <= (3, 12)) or sys.maxsize < 2**32:
        sys.exit("Bitte Python 3.10, 3.11 oder 3.12 (64 Bit) verwenden - gefunden: %s" % sys.version.split()[0])
    print("Python %s (%s)" % (sys.version.split()[0], sys.executable))


def make_venv(use_dml):
    step("1/5 Python-Umgebung (venv) und Pakete - dauert beim ersten Mal einige Minuten")
    if not venv_python().exists():
        run([sys.executable, "-m", "venv", VENV])
    py = venv_python()
    run([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools<81", "wheel"])
    # Torch als reine CPU-Version (klein, kein CUDA nötig) - für AMD kommt DirectML dazu
    run([py, "-m", "pip", "install", *TORCH, "--index-url", "https://download.pytorch.org/whl/cpu"])
    run([py, "-m", "pip", "install", "-r", HERE / "requirements-tts.txt"])
    if use_dml:
        subprocess.run([str(py), "-m", "pip", "uninstall", "-y", "onnxruntime"])   # Konflikt mit -directml
        run([py, "-m", "pip", "install", *DML])
    else:
        run([py, "-m", "pip", "install", *NO_DML])


def get_rvc_code():
    step("2/5 RVC-Code (GitHub, fester Stand %s)" % RVC_COMMIT[:7])
    marker = RVC_DIR / ".commit"
    if marker.is_file() and marker.read_text().strip() == RVC_COMMIT:
        print("schon vorhanden")
        return
    print("lade " + RVC_ZIP)
    data = urllib.request.urlopen(RVC_ZIP, timeout=120).read()
    tmp = HERE / "_rvc_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(tmp)
    top = next(tmp.iterdir())
    keep_assets = RVC_DIR / "assets"
    saved = HERE / "_assets_keep"
    if keep_assets.is_dir():                         # bereits geladene Modelle behalten
        shutil.rmtree(saved, ignore_errors=True)
        shutil.move(str(keep_assets), str(saved))
    shutil.rmtree(RVC_DIR, ignore_errors=True)
    shutil.move(str(top), str(RVC_DIR))
    shutil.rmtree(tmp, ignore_errors=True)
    if saved.is_dir():
        shutil.rmtree(RVC_DIR / "assets", ignore_errors=True)
        shutil.move(str(saved), str(RVC_DIR / "assets"))
    marker.write_text(RVC_COMMIT)
    print("ok")


DOWNLOAD_SCRIPT = r'''
import sys
from huggingface_hub import hf_hub_download, snapshot_download
rvc, models, model, dml = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
print("HuBERT (~190 MB) ...", flush=True)
snapshot_download("lj1995/VoiceConversionWebUI", allow_patterns=["hubert_base/*"], local_dir=rvc + "/assets")
print("RMVPE (~180 MB) ...", flush=True)
hf_hub_download("lj1995/VoiceConversionWebUI", "rmvpe.pt", local_dir=rvc + "/assets/rmvpe")
if dml:
    print("RMVPE für DirectML (~360 MB) ...", flush=True)
    hf_hub_download("lj1995/VoiceConversionWebUI", "rmvpe.onnx", local_dir=rvc + "/assets/rmvpe")
print("Miku-Stimmmodell '%s' (~600 MB inkl. Index) ..." % model, flush=True)
snapshot_download("NoCrypt/miku_RVC", allow_patterns=[model + "/*"], local_dir=models)
print("fertig", flush=True)
'''


def download_models(model, use_dml):
    step("3/5 Modelle von Hugging Face (zusammen ca. 1-1,4 GB)")
    MODELS_DIR.mkdir(exist_ok=True)
    run([venv_python(), "-c", DOWNLOAD_SCRIPT, RVC_DIR, MODELS_DIR, model, "1" if use_dml else "0"])
    if not list((MODELS_DIR / model).glob("*.pth")):
        sys.exit("Stimmmodell nicht gefunden in %s" % (MODELS_DIR / model))


VERIFY_SCRIPT = r'''
import hashlib, os, sys
from huggingface_hub import HfApi, hf_hub_download
rvc, models, model = sys.argv[1], sys.argv[2], sys.argv[3]
api = HfApi()

def local_hash(path, kind):
    h = hashlib.sha256() if kind == "sha256" else hashlib.sha1()
    size = os.path.getsize(path)
    if kind == "git":                       # Git-Blob-Hash für kleine Dateien
        h.update(b"blob %d\0" % size)
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def check(repo, files, local_dir):
    bad = 0
    for info in api.get_paths_info(repo, files):
        path = os.path.join(local_dir, info.path)
        if info.lfs is not None:
            kind, want = "sha256", info.lfs.sha256
        else:
            kind, want = "git", info.blob_id
        ok = os.path.isfile(path) and os.path.getsize(path) == info.size and local_hash(path, kind) == want
        print(("  ok       " if ok else "  DEFEKT   ") + info.path, flush=True)
        if not ok:
            bad += 1
            hf_hub_download(repo, info.path, local_dir=local_dir, force_download=True)
            print("  -> neu geladen", flush=True)
    return bad

base = ["hubert_base/config.json", "hubert_base/preprocessor_config.json", "hubert_base/pytorch_model.bin"]
bad = check("lj1995/VoiceConversionWebUI", base, rvc + "/assets")
rm = [f for f in ("rmvpe.pt", "rmvpe.onnx") if os.path.isfile(os.path.join(rvc, "assets", "rmvpe", f))]
bad += check("lj1995/VoiceConversionWebUI", rm, rvc + "/assets/rmvpe")
mfiles = [model + "/" + f for f in sorted(os.listdir(os.path.join(models, model)))
          if not f.startswith(".") and os.path.isfile(os.path.join(models, model, f))]
bad += check("NoCrypt/miku_RVC", mfiles, models)
print("%d Datei(en) repariert" % bad if bad else "alle Modelldateien in Ordnung", flush=True)
'''


def repair(model):
    """Nach einem Absturz: Reste beseitigen, die beim harten Ausschalten halb geschrieben wurden."""
    step("Reparatur 1/4: Caches löschen (werden automatisch neu erzeugt)")
    removed = 0
    for root in (VENV / "Lib" / "site-packages", VENV / "lib", HERE / "cache"):
        if not root.exists():
            continue
        for f in list(root.rglob("*.nbi")) + list(root.rglob("*.nbc")):   # Numba-JIT-Cache (librosa)
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    shutil.rmtree(HERE / "cache", ignore_errors=True)
    print("%d Cache-Dateien gelöscht" % removed)

    step("Reparatur 2/4: tts_config.json prüfen")
    import json
    cfg = HERE / "tts_config.json"
    try:
        json.loads(cfg.read_text(encoding="utf-8"))
        print("in Ordnung")
    except Exception as e:
        print("defekt (%s) - wird neu angelegt" % e)
        if cfg.exists():
            cfg.replace(HERE / "tts_config.defekt.json")
        write_config(model)

    step("Reparatur 3/4: Modelldateien mit Hugging Face vergleichen (Prüfsummen)")
    run([venv_python(), "-c", VERIFY_SCRIPT, RVC_DIR, MODELS_DIR, model])

    step("Reparatur 4/4: Python-Pakete testen")
    test = "import torch, librosa, faiss, transformers, av, edge_tts, parselmouth; print('Pakete ok, Torch', torch.__version__)"
    if subprocess.run([str(venv_python()), "-c", test]).returncode != 0:
        print("Pakete beschädigt - installiere neu ...")
        run([venv_python(), "-m", "pip", "install", "--force-reinstall", "--no-deps", "-r", HERE / "requirements-tts.txt"])
        run([venv_python(), "-m", "pip", "install", "--force-reinstall", "--no-deps", *TORCH,
             "--index-url", "https://download.pytorch.org/whl/cpu"])


def write_config(model):
    step("4/5 Einstellungen (tts_config.json)")
    cfg = HERE / "tts_config.json"
    if cfg.is_file():
        print("vorhanden - bleibt unverändert")
        return
    import json
    sys.path.insert(0, str(HERE))
    from miku_tts_server import DEFAULTS
    d = dict(DEFAULTS)
    d["model"] = model
    cfg.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    print("angelegt: " + str(cfg))


def self_test():
    step("5/5 Probelauf (Dienst starten, einen Satz sprechen)")
    import json
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen([str(venv_python()), str(HERE / "miku_tts_server.py"), "--port", str(port)],
                            cwd=str(HERE))
    try:
        base = "http://127.0.0.1:%d" % port
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost nie über Proxy
        t0 = time.time()
        health = {}
        while time.time() - t0 < 300:
            time.sleep(2)
            try:
                health = json.loads(opener.open(base + "/health", timeout=3).read())
            except Exception:
                continue
            if health.get("ready") or health.get("error"):
                break
        if not health.get("ready"):
            sys.exit("Dienst nicht bereit: %s" % (health.get("error") or "Zeitüberschreitung"))
        print("bereit nach %.0f s auf Gerät: %s" % (time.time() - t0, health.get("device")))
        req = urllib.request.Request(base + "/tts", data=json.dumps({"text": "Hello! I am Hatsune Miku. Nice to meet you!"}).encode(),
                                     headers={"Content-Type": "application/json"})
        t1 = time.time()
        resp = opener.open(req, timeout=300)
        wav = resp.read()
        out = HERE / "test_miku.wav"
        out.write_bytes(wav)
        print("Satz erzeugt in %.1f s (%s) -> %s" % (time.time() - t1, resp.headers.get("X-TTS-Timing"), out))
        if os.name == "nt":
            os.startfile(str(out))                   # zum Anhören
    finally:
        proc.terminate()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dml", action="store_true", help="DirectML für AMD/Intel-GPU mitinstallieren")
    g.add_argument("--no-dml", action="store_true")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--skip-test", action="store_true")
    ap.add_argument("--repair", action="store_true", help="nach Absturz: Caches löschen, Dateien prüfen")
    args = ap.parse_args()
    check_python()
    if args.repair:
        if not venv_python().exists():
            sys.exit("Noch nicht eingerichtet - bitte setup_tts.bat ausführen")
        repair(args.model)
        if not args.skip_test:
            self_test()
        print("\nReparatur abgeschlossen.")
        return
    use_dml = args.dml
    if not args.dml and not args.no_dml and os.name == "nt":
        ans = input("DirectML für die AMD-Grafikkarte mitinstallieren? (schneller, aber experimentell) [j/N]: ")
        use_dml = ans.strip().lower() in ("j", "ja", "y", "yes")
    t0 = time.time()
    make_venv(use_dml)
    get_rvc_code()
    download_models(args.model, use_dml)
    write_config(args.model)
    if not args.skip_test:
        self_test()
    print("\nFertig nach %.0f min. Das Plugin startet den Dienst ab jetzt selbst." % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
