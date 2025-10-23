# [HTML] dual_ui.py
# Liefert je nach mode ("popup" | "window") eine Inline-HTML-UI als String.

def get_inline_html(mode: str) -> str:
    mode = (mode or "window").lower()
    if mode == "popup":
        # Variante A: kompakte Transport-Buttons (passt in Buttonhöhe)
        return r"""
<style>
  .row{height:100%;display:flex;align-items:center;gap:6px;padding:0 8px}
  .btn{height:100%;min-width:36px;padding:0 10px;border:none;border-radius:8px;background:#444;color:#fff;font:12px/1 system-ui;cursor:pointer}
  .btn:hover{background:#666}
</style>
<div class="row">
  <button class="btn" title="Vorheriger" onclick="window.media?.prev()">⏮︎</button>
  <button class="btn" title="Play/Pause" onclick="window.media?.playPause()">⏯︎</button>
  <button class="btn" title="Nächster" onclick="window.media?.next()">⏭︎</button>
</div>
"""
    else:
        # Variante B: Lautstärke + Label für Main Window
        return r"""
<style>
  .row{height:100%;display:flex;align-items:center;gap:10px;padding:0 10px}
  .lbl{height:100%;display:flex;align-items:center;padding:0 12px;border-radius:8px;background:#203;color:#fff;font:13px/1 system-ui;opacity:.85}
  .btn{height:100%;min-width:40px;padding:0 12px;border:none;border-radius:8px;background:#2e6f3c;color:#fff;font:13px/1 system-ui;cursor:pointer}
  .btn:hover{background:#3c8250}
</style>
<div class="row">
  <span class="lbl">🎵 Player</span>
  <button class="btn" title="Leiser" onclick="window.media?.volDown()">🔉−</button>
  <button class="btn" title="Mute"   onclick="window.media?.mute()">🔇</button>
  <button class="btn" title="Lauter" onclick="window.media?.volUp()">🔊+</button>
</div>
"""
