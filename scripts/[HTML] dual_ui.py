# [HTML] dual_ui.py
# Liefert je nach mode ("popup" | "window") eine Inline-HTML-UI als String.

def get_inline_html(mode: str) -> str:
    mode = (mode or "window").lower()
    common_css = """
<style>
  :root {
    --btn-bg: rgba(255,255,255,0.12);
    --btn-hover: rgba(255,255,255,0.26);
    --btn-color: #f9f9f9;
    --row-bg: transparent;
  }
  body[data-theme="light"] {
    --btn-bg: #f2f4fc;
    --btn-hover: #e0e6ff;
    --btn-color: #212438;
    --row-bg: transparent;
  }
  body[data-theme="dark"] {
    --btn-bg: rgba(255,255,255,0.12);
    --btn-hover: rgba(255,255,255,0.26);
    --btn-color: #f9f9f9;
  }
  .row {
    position: relative;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-start; /* linksbündig, damit right-buttons immer am Rand */
    padding: 0 10px;
    background: var(--row-bg);
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
    background: var(--row-bg);
  }
  .btn{
    flex: 1 1 0;
    height: 100%;
    min-width: 44px;
    max-width: 120px;
    background: var(--btn-bg);
    color: var(--btn-color);
    border: none;
    border-radius: 9px;
    font-size: 2vw;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    line-height: 1;
    margin: 0;
    transition: background .2s, transform .2s;
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
    background: var(--btn-hover);
    transform: translateY(-1px);
  }
  .btn:focus {
    outline: none;
    box-shadow: none;
  }
  .btn svg {
    width: 32px;
    height: 32px;
    display: block;
    fill: currentColor;
    stroke: currentColor;
  }
</style>
"""
    theme_js = """
<script>
(function() {
  const applyTheme = (theme) => {
    const body = document.body;
    const normalized = (theme === 'dark') ? 'dark' : 'light';
    body.setAttribute('data-theme', normalized);
  };

  function connectThemeBridge(attempt = 0) {
    if (!window.media) {
      if (attempt < 40) {
        return void setTimeout(() => connectThemeBridge(attempt + 1), 120);
      }
      return applyTheme('light');
    }

    if (window.media.themeChanged && typeof window.media.themeChanged.connect === 'function') {
      window.media.themeChanged.connect(applyTheme);
    }

    if (typeof window.media.getTheme === 'function') {
      try {
        window.media.getTheme(function(theme) { applyTheme(theme); });
      } catch (err) {
        applyTheme('light');
      }
    } else {
      applyTheme('light');
    }
  }

  window.addEventListener('load', () => connectThemeBridge());
})();
</script>
"""
    if mode == "popup":
        return common_css + r'''
<div class="row">
  <button class="btn" title="Vorheriger" onclick="window.media?.prev()">
    <svg viewBox="0 0 32 32">
      <polygon points="26,6 12,16 26,26" fill="currentColor"/>
      <rect x="6" y="6" width="4" height="20" rx="1.5" fill="currentColor"/>
    </svg>
  </button>
  <button class="btn" title="Play/Pause" onclick="window.media?.playPause()">
    <svg viewBox="0 0 32 32">
      <polygon points="8,6 26,16 8,26" fill="currentColor"/>
    </svg>
  </button>
  <button class="btn" title="Nächster" onclick="window.media?.next()">
    <svg viewBox="0 0 32 32">
      <polygon points="6,6 20,16 6,26" fill="currentColor"/>
      <rect x="22" y="6" width="4" height="20" rx="1.5" fill="currentColor"/>
    </svg>
  </button>
</div>
''' + theme_js
    else:
        return common_css + r'''
<div class="row">
  <div class="left-buttons">
    <button class="btn" title="Vorheriger" onclick="window.media?.prev()">
      <svg viewBox="0 0 32 32">
        <polygon points="26,6 12,16 26,26" fill="currentColor"/>
        <rect x="6" y="6" width="4" height="20" rx="1.5" fill="currentColor"/>
      </svg>
    </button>
    <button class="btn" title="Play/Pause" onclick="window.media?.playPause()">
      <svg viewBox="0 0 32 32">
        <polygon points="8,6 26,16 8,26" fill="currentColor"/>
      </svg>
    </button>
    <button class="btn" title="Nächster" onclick="window.media?.next()">
      <svg viewBox="0 0 32 32">
        <polygon points="6,6 20,16 6,26" fill="currentColor"/>
        <rect x="22" y="6" width="4" height="20" rx="1.5" fill="currentColor"/>
      </svg>
    </button>
  </div>
  <div class="right-buttons">
    <button class="btn" title="Leiser" onclick="window.media?.volDown()">
      <svg viewBox="0 0 32 32">
        <rect x="4" y="12" width="6" height="8" rx="2" fill="currentColor"/>
        <polygon points="10,12 18,8 18,24 10,20" fill="currentColor"/>
        <path d="M22 12 q4 4 0 8" stroke="currentColor" stroke-width="2" fill="none"/>
      </svg>
    </button>
    <button class="btn" title="Lauter" onclick="window.media?.volUp()">
      <svg viewBox="0 0 32 32">
        <rect x="4" y="12" width="6" height="8" rx="2" fill="currentColor"/>
        <polygon points="10,12 18,8 18,24 10,20" fill="currentColor"/>
        <path d="M22 12 q4 4 0 8" stroke="currentColor" stroke-width="2" fill="none"/>
        <path d="M25 10 q7 6 0 12" stroke="currentColor" stroke-width="2" fill="none"/>
      </svg>
    </button>
    <button class="btn" title="Mute" onclick="window.media?.mute()">
      <svg viewBox="0 0 32 32">
        <rect x="4" y="12" width="6" height="8" rx="2" fill="currentColor"/>
        <polygon points="10,12 18,8 18,24 10,20" fill="currentColor"/>
        <line x1="22" y1="12" x2="28" y2="20" stroke="currentColor" stroke-width="2"/>
        <line x1="28" y1="12" x2="22" y2="20" stroke="currentColor" stroke-width="2"/>
      </svg>
    </button>
  </div>
</div>
''' + theme_js

