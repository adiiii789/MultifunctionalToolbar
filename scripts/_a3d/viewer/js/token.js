/* token.js - Zugang zum Asset-Server des Plugins (3D Assistent.py).
   Das Plugin hängt beim Öffnen ein zufälliges Token an die Adresse (viewer.html?k=...).
   Der Server nimmt Anfragen an /ai/*, /tts*, /board/* und alle POSTs nur mit diesem Token an -
   sonst könnte jedes Programm auf dem PC (oder eine Webseite, die den Port errät) Miku Aufträge
   geben. Hier wird fetch so umhüllt, dass jede Anfrage an den eigenen Server das Token im Header
   X-A3D-Token mitschickt. Muss vor allen anderen Skripten geladen werden. */
(function () {
  const token = new URLSearchParams(location.search).get("k");
  if (!token || !window.fetch) return;
  const originalFetch = window.fetch.bind(window);
  window.A3D_TOKEN = token;                 // für Seiten im Board (board/plugin.html)
  window.fetch = function (input, init) {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin !== location.origin) return originalFetch(input, init);
    init = Object.assign({}, init || {});
    const headers = new Headers(init.headers || (typeof input === "string" ? {} : input.headers));
    headers.set("X-A3D-Token", token);
    init.headers = headers;
    return originalFetch(input, init);
  };
})();
