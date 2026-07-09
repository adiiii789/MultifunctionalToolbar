# =============================================================================
# Demo: Abwärtskompatibilität — [html]-Prefix im Dateinamen + get_inline_html()
# funktionieren exakt wie im Original, ganz ohne neue Parameter.
# =============================================================================

def get_inline_html(mode="window"):
    size = "18px" if mode == "popup" else "22px"
    return f"""
<div style="display:flex;align-items:center;justify-content:center;height:100%;
            font:{size}/1 system-ui;color:inherit;">
  🕒 <span id="clock" style="margin-left:8px;">--:--:--</span>
</div>
<script>
setInterval(() => {{
  document.getElementById('clock').textContent = new Date().toLocaleTimeString();
}}, 1000);
</script>
"""
