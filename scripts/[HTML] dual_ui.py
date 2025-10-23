# [HTML] dual_ui.py
# Liefert je nach mode ("popup" | "window") eine Inline-HTML-UI als String.

def get_inline_html(mode: str) -> str:
    mode = (mode or "window").lower()
    common_css = """
<style>
  .row {
    position: relative;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-start; /* linksbündig, damit right-buttons immer am Rand */
    padding: 0 10px;
  }
  .left-buttons {
    position: absolute;
    left: 50%;
    top: 0;
    transform: translateX(-50%);
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 10px;
    height: 100%;
  }
  .right-buttons {
    margin-left: auto;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    height: 100%;
    /* Kein position:absolute, damit der Platz rechts sauber bleibt */
  }
  .btn{
    flex: 1 1 0;
    height: 100%;
    min-width: 44px;
    max-width: 120px;
    background: #444;
    color: white;
    border: none;
    border-radius: 9px;
    font-size: 2vw;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    line-height: 1;
    margin: 0;
    transition: background .2s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    overflow: hidden;
    cursor: pointer;
    margin-right: 0.5vw;
  }
  .left-buttons .btn {
    min-width: 100%;
    max-width: 120px;
  }
  .right-buttons .btn {
    max-width: 60px;
    flex: 0 0 auto;
  }
  .btn:hover {
    background: #666;
  }
  .btn:focus {
    outline: none;
    box-shadow: none;
  }
  .btn svg {
    width: 32px;
    height: 32px;
    display: block;
  }
</style>
"""
    if mode == "popup":
        return common_css + r'''
<div class="row">
  <button class="btn" title="Vorheriger" onclick="window.media?.prev()">
    <svg viewBox="0 0 32 32">
      <polygon points="26,6 12,16 26,26" fill="#fff"/>
      <rect x="6" y="6" width="4" height="20" rx="1.5" fill="#fff"/>
    </svg>
  </button>
  <button class="btn" title="Play/Pause" onclick="window.media?.playPause()">
    <svg viewBox="0 0 32 32">
      <polygon points="8,6 26,16 8,26" fill="#fff"/>
    </svg>
  </button>
  <button class="btn" title="Nächster" onclick="window.media?.next()">
    <svg viewBox="0 0 32 32">
      <polygon points="6,6 20,16 6,26" fill="#fff"/>
      <rect x="22" y="6" width="4" height="20" rx="1.5" fill="#fff"/>
    </svg>
  </button>
</div>
'''
    else:
        return common_css + r'''
<div class="row">
  <div class="left-buttons">
    <button class="btn" title="Vorheriger" onclick="window.media?.prev()">
      <svg viewBox="0 0 32 32">
        <polygon points="26,6 12,16 26,26" fill="#fff"/>
        <rect x="6" y="6" width="4" height="20" rx="1.5" fill="#fff"/>
      </svg>
    </button>
    <button class="btn" title="Play/Pause" onclick="window.media?.playPause()">
      <svg viewBox="0 0 32 32">
        <polygon points="8,6 26,16 8,26" fill="#fff"/>
      </svg>
    </button>
    <button class="btn" title="Nächster" onclick="window.media?.next()">
      <svg viewBox="0 0 32 32">
        <polygon points="6,6 20,16 6,26" fill="#fff"/>
        <rect x="22" y="6" width="4" height="20" rx="1.5" fill="#fff"/>
      </svg>
    </button>
  </div>
  <div class="right-buttons">
    <button class="btn" title="Leiser" onclick="window.media?.volDown()">
      <svg viewBox="0 0 32 32">
        <rect x="4" y="12" width="6" height="8" rx="2" fill="#fff"/>
        <polygon points="10,12 18,8 18,24 10,20" fill="#fff"/>
        <path d="M22 12 q4 4 0 8" stroke="#fff" stroke-width="2" fill="none"/>
      </svg>
    </button>
    <button class="btn" title="Lauter" onclick="window.media?.volUp()">
      <svg viewBox="0 0 32 32">
        <rect x="4" y="12" width="6" height="8" rx="2" fill="#fff"/>
        <polygon points="10,12 18,8 18,24 10,20" fill="#fff"/>
        <path d="M22 12 q4 4 0 8" stroke="#fff" stroke-width="2" fill="none"/>
        <path d="M25 10 q7 6 0 12" stroke="#fff" stroke-width="2" fill="none"/>
      </svg>
    </button>
    <button class="btn" title="Mute" onclick="window.media?.mute()">
      <svg viewBox="0 0 32 32">
        <rect x="4" y="12" width="6" height="8" rx="2" fill="#fff"/>
        <polygon points="10,12 18,8 18,24 10,20" fill="#fff"/>
        <line x1="22" y1="12" x2="28" y2="20" stroke="#fff" stroke-width="2"/>
        <line x1="28" y1="12" x2="22" y2="20" stroke="#fff" stroke-width="2"/>
      </svg>
    </button>
  </div>
</div>
'''