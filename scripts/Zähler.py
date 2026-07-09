# =============================================================================
# Demo: Geschlossenes Plugin-System.
# UI (BUTTON_HTML), Backend-Logik (handle_call) und Zustand (_count) liegen
# vollständig in DIESER Datei. Der Traylauncher lädt das Modul nur und routet
# pluginCall(...) aus der Card hierher — er führt keine eigene Logik aus.
# =============================================================================
HTML_BUTTON = True
NAME = "Zähler"
ICON = "🔢"
BUTTON_HEIGHT = 64
MEDIA_BRIDGE = False  # dieser Card reicht das eigene Backend

_count = 0  # Zustand bleibt erhalten (Modul wird gecacht)


def handle_call(method, args):
    """Backend der Card. Wird per pluginCall('inc', {...}) aus dem HTML gerufen."""
    global _count
    if method == "inc":
        _count += int(args.get("step", 1))
    elif method == "reset":
        _count = 0
    # "get" (und alles andere) liefert nur den aktuellen Stand
    return {"count": _count}


BUTTON_HTML = """
<div style="display:flex;align-items:center;justify-content:center;height:100%;gap:10px;
            font-family:system-ui;color:inherit;">
  <span id="c" style="font-size:20px;min-width:44px;text-align:center;">…</span>
  <button onclick="call('inc',{step:1})"  style="padding:4px 12px;border-radius:8px;border:none;cursor:pointer;">+1</button>
  <button onclick="call('inc',{step:10})" style="padding:4px 12px;border-radius:8px;border:none;cursor:pointer;">+10</button>
  <button onclick="call('reset')"         style="padding:4px 12px;border-radius:8px;border:none;cursor:pointer;">Reset</button>
</div>
<script>
function call(m, a){
  pluginCall(m, a || {}, function(raw){
    try { var r = JSON.parse(raw);
      if (r.ok) document.getElementById('c').textContent = r.result.count; }
    catch(e){}
  });
}
window.addEventListener('load', function(){ setTimeout(function(){ call('get'); }, 300); });
</script>
"""
