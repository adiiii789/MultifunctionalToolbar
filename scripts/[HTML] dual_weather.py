# [HTML] weather_dual_stuttgart.py
# Inline: Stadt, Temperatur, Regen-Chance (Open-Meteo), 1 Button "Regenradar"
# Klick: öffnet Windy-Embed (Regen-Layer) mit Overlay "Regenwahrscheinlichkeit" oben rechts
#
# Voraussetzungen in deinem Tray:
# - InlineInterceptPage + HtmlInlineButton (fertig)
# - (Empfohlen) AppBridge in Python registriert:
#     class AppBridge(QObject):
#         @pyqtSlot(float, float, result=str)
#         def getWeather(self, lat, lon) -> str:  # wie in unserem Patch
#             ...
#     # und in HtmlInlineButton.__init__ nach media:
#     self.appbridge = AppBridge(self); self.channel.registerObject("app", self.appbridge)
#
# Standort: Stuttgart
LAT = 48.7758
LON = 9.1829
CITY = "Stuttgart"

def get_inline_html(mode: str) -> str:
    mode = (mode or "window").lower()
    compact = (mode == "popup")

    css = rf"""
<style>
  :root {{
    --pill-bg: rgba(255,255,255,0.12);
    --pill-color: #fdfdfd;
    --temp-bg: #244c88;
    --temp-color: #fefefe;
    --btn-bg: #3c7d3c;
    --btn-hover: #4b9150;
    --btn-color: #fefefe;
  }}
  body[data-theme="light"] {{
    --pill-bg: rgba(236,239,245,0.9);
    --pill-color: #1b2334;
    --temp-bg: #dfe8ff;
    --temp-color: #102148;
    --btn-bg: #4f7ef5;
    --btn-hover: #3d6ae0;
    --btn-color: #ffffff;
  }}
  body[data-theme="dark"] {{
    --pill-bg: rgba(255,255,255,0.12);
    --pill-color: #fdfdfd;
    --temp-bg: #244c88;
    --temp-color: #fefefe;
    --btn-bg: #3c7d3c;
    --btn-hover: #4b9150;
    --btn-color: #fefefe;
  }}
  html,body{{height:100%;margin:0;padding:0;background:transparent;overflow:hidden}}
  *{{box-sizing:border-box}}
  .wrap{{height:100%;display:flex;align-items:center;gap:{'6px' if compact else '10px'};padding:0 {'8px' if compact else '12px'};}}
  .pill{{
    height:100%;display:flex;align-items:center;justify-content:center;
    background:var(--pill-bg);color:var(--pill-color);border-radius:10px;
    padding:0 {'10px' if compact else '14px'};
    font:{'600 13px' if compact else '600 14px'}/1 system-ui,Segoe UI,Arial;
  }}
  .temp{{
    height:100%;display:flex;align-items:center;justify-content:center;
    background:var(--temp-bg);color:var(--temp-color);border-radius:10px;
    padding:0 {'12px' if compact else '16px'};
    font:{'700 16px' if compact else '700 18px'}/1.1 ui-monospace,Consolas,monospace;
  }}
  .btn{{
    height:100%;display:flex;align-items:center;justify-content:center;
    background:var(--btn-bg);color:var(--btn-color);border:none;border-radius:10px;cursor:pointer;
    padding:0 {'10px' if compact else '14px'};
    font:{'600 12px' if compact else '600 13px'}/1 system-ui,Segoe UI,Arial;
    text-decoration:none;
    transition: background .2s, transform .2s;
  }}
  .btn:hover{{background:var(--btn-hover); transform: translateY(-1px);}}
</style>
"""
    if mode == "window":
        body = f"""
    <div class="wrap {'popup' if compact else 'window'}">
      <div class="pill">🌍 {CITY}</div>
      <div class="temp" id="temp">--°C</div>
      <div class="pill" id="rain">Regen: --%</div>
      <a class="btn" id="btnRadar" href="#">Regenradar</a>
    </div>
    """
    else: body = f"""
    <div class="wrap {'popup' if compact else 'window'}">
      <div class="pill">🌍 {CITY}</div>
      <div class="temp" id="temp">--°C</div>
      <div class="pill" id="rain">Regen: --%</div>
    </div>
    """


    js = f"""
<script>
(function(){{
  const LAT = {LAT:.6f}, LON = {LON:.6f};
  const CITY = {CITY!r};
  const qs = (s)=>document.querySelector(s);
  const tempEl = qs('#temp');
  const rainEl = qs('#rain');
  const btnRadar = qs('#btnRadar');

  let lastProb = null;

  // -------- Wetter laden (fetch -> Fallback über WebChannel app.getWeather) --------
  const url = "https://api.open-meteo.com/v1/forecast?latitude=" + LAT + "&longitude=" + LON +
              "&current=temperature_2m&hourly=precipitation_probability&forecast_days=1&timezone=auto";

  function applyWeather(d){{
    try {{
      if (d.current && typeof d.current.temperature_2m === 'number') {{
        tempEl.textContent = Math.round(d.current.temperature_2m) + "°C";
      }}
      let prob = null;
      if (d.hourly && d.hourly.time && d.hourly.precipitation_probability) {{
        const times=d.hourly.time, probs=d.hourly.precipitation_probability;
        const now = new Date();
        let best=0, bd=1e15;
        for (let i=0;i<times.length;i++) {{
          const t=new Date(times[i]);
          const diff=Math.abs(t-now);
          if (diff<bd){{bd=diff;best=i;}}
        }}
        prob = typeof probs[best] === 'number' ? probs[best] : null;
      }}
      if (prob==null) prob = 0;
      lastProb = prob;
      rainEl.textContent = "Regen: " + prob + "%";
    }} catch(e){{ console.warn("applyWeather error", e); }}
  }}

  (async function loadWeather(){{
    try {{
      const ctrl = new AbortController();
      const timer = setTimeout(()=>ctrl.abort(), 4000);
      const resp = await fetch(url, {{signal: ctrl.signal}});
      clearTimeout(timer);
      const d = await resp.json();
      applyWeather(d);
    }} catch(e) {{
      try {{
        if (window.app && typeof window.app.getWeather === 'function') {{
          const maybe = window.app.getWeather(LAT, LON);
          if (maybe && typeof maybe.then === 'function') {{
            // Promise-ähnlich
            maybe.then(function(raw){{ try{{ applyWeather(JSON.parse(raw||"{{}}")); }}catch(_e){{}} }});
          }} else if (typeof maybe === 'string') {{
            try {{ applyWeather(JSON.parse(maybe||"{{}}")); }} catch(_e) {{}}
          }}
        }}
      }} catch(_e) {{
        console.warn("Bridge fallback failed", _e);
      }}
    }}
  }})();

  // -------- Klick: Windy-Embed in data:-Seite mit Overlay (Regenwahrscheinlichkeit) --------
  if (btnRadar) btnRadar.addEventListener('click', function(e){{
    e.preventDefault();

    const prob = (lastProb==null ? '–' : (lastProb + '%'));
    // Windy Embed: Regen-Layer, zentriert auf Stuttgart
    // Doku/Config: https://embed.windy.com/
    const windySrc = "https://embed.windy.com/embed2.html"
                   + "?lat=" + LAT
                   + "&lon=" + LON
                   + "&zoom=8"
                   + "&detailLat=" + LAT
                   + "&detailLon=" + LON
                   + "&overlay=rain"
                   + "&level=surface"
                   + "&product=radar"
                   + "&menu=&message=true&marker=true";

    const html = `
<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Regenradar · ${'{' }CITY{'}'}</title>
<style>
  html,body{{margin:0;padding:0;height:100%;overflow:hidden;font:14px/1.2 system-ui,Segoe UI,Arial}}
  .bar{{position:fixed;top:10px;right:10px;z-index:10;background:rgba(0,0,0,.6);color:#fff;border-radius:10px;padding:8px 12px}}
  .bar b{{font-weight:700}}
  iframe{{position:absolute;inset:0;border:0;width:100%;height:100%}}
</style>
<div class="bar">☔ Regenwahrscheinlichkeit: <b>${'{' }prob{'}'}</b></div>
<iframe src="` + windySrc + `" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe>`;
    const dataUrl = "data:text/html;charset=utf-8," + encodeURIComponent(html);

    // -> wird von deiner InlineInterceptPage als Plugin-Ansicht in der App geöffnet
    window.open(dataUrl, "_blank");
  }});
}})();
</script>
"""
    theme_js = """
<script>
(function() {{
  const applyTheme = (theme) => {{
    const normalized = (theme === 'dark') ? 'dark' : 'light';
    document.body.setAttribute('data-theme', normalized);
  }};

  function connectThemeBridge(attempt = 0) {{
    if (!window.media) {{
      if (attempt < 40) {{
        return void setTimeout(() => connectThemeBridge(attempt + 1), 120);
      }}
      return applyTheme('light');
    }}

    if (window.media.themeChanged && typeof window.media.themeChanged.connect === 'function') {{
      window.media.themeChanged.connect(applyTheme);
    }}

    if (typeof window.media.getTheme === 'function') {{
      try {{
        window.media.getTheme(function(theme) {{ applyTheme(theme); }});
      }} catch (err) {{
        applyTheme('light');
      }}
    }} else {{
      applyTheme('light');
    }}
  }}

  window.addEventListener('load', () => connectThemeBridge());
}})();
</script>
"""
    return css + body + js + theme_js
