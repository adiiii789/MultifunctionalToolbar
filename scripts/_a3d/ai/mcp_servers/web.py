"""Websuche und Webseiten lesen - genutzt von web_server.py.

search(query)    Treffer über ddgs (DuckDuckGo & Co., ohne API-Schlüssel)
fetch(url, part) lesbarer Text einer Seite, lange Texte in Teilen

Sicherheit: fetch ruft nur öffentliche http(s)-Adressen auf - auch nach Weiterleitungen.
Sonst könnte eine Webseite das Modell anweisen, Dienste auf diesem PC (127.0.0.1, z. B. den
Asset-Server des 3D-Assistenten) oder Geräte im Heimnetz (Router, NAS) aufzurufen.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser

MAX_RESULTS = 10
PART_CHARS = 6_000              # Seitentext in Teilen dieser Größe (passt in ein Tool-Ergebnis)
MAX_PAGE_BYTES = 3 * 1024 * 1024
TIMEOUT_S = 15
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
PAGE_END = "--- end of page ---"


class WebError(Exception):
    """Erwarteter Fehler (Adresse gesperrt, Seite nicht erreichbar ...) - Text geht ans Modell."""


# --- Suche -----------------------------------------------------------------------
def search(query: str, max_results: int = 5, region: str = "wt-wt") -> str:
    query = query.strip()
    if not query:
        raise WebError("Empty search query.")
    from ddgs import DDGS   # erst hier: lädt einiges
    try:
        results = DDGS().text(query, region=region or "wt-wt", max_results=max(1, min(max_results, MAX_RESULTS)))
    except Exception as error:  # noqa: BLE001  # ddgs wirft je nach Backend Verschiedenes
        raise WebError(f"Search failed: {error}") from error
    if not results:
        return f"No results for: {query}"
    lines = [f"Search results for: {query}"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '')}\n   {r.get('href', '')}\n   {r.get('body', '')}")
    return "\n".join(lines)


# --- Seite lesen ---------------------------------------------------------------------
def check_public_url(url: str) -> str:
    """Nur http(s) zu öffentlichen Adressen; gibt die URL zurück oder wirft WebError."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise WebError("Only http(s) URLs are allowed.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as error:
        raise WebError(f"Host not found: {parts.hostname}") from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global:
            raise WebError(f"Address not allowed (local or private network): {parts.hostname}")
    return url


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PublicRedirects())


def fetch(url: str, part: int = 1) -> str:
    url = check_public_url(url.strip())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en,de;q=0.8",
                                                   "Accept-Encoding": "gzip, deflate"})
    try:
        with _OPENER.open(request, timeout=TIMEOUT_S) as response:
            content_type = response.headers.get("Content-Type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            encoding = (response.headers.get("Content-Encoding") or "").lower()
            raw = _decompress(response.read(MAX_PAGE_BYTES + 1), encoding)
    except urllib.error.HTTPError as error:
        raise WebError(f"HTTP {error.code} for {url}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise WebError(f"Page not reachable: {error}") from error
    if "html" not in content_type and "text" not in content_type:
        raise WebError(f"Not a text page ({content_type or 'unknown type'}).")
    text = raw[:MAX_PAGE_BYTES].decode(charset, errors="replace")
    title, body = html_to_text(text) if "html" in content_type else ("", text)
    return _part(url, title, body, part)


def _decompress(data: bytes, encoding: str) -> bytes:
    """gzip/deflate entpacken (manche Server packen auch ungefragt) - höchstens MAX_PAGE_BYTES."""
    if encoding in ("", "identity"):
        return data
    if encoding not in ("gzip", "x-gzip", "deflate"):
        raise WebError(f"Unsupported content encoding: {encoding}")
    wbits = 16 + zlib.MAX_WBITS if "gzip" in encoding else zlib.MAX_WBITS
    try:
        return zlib.decompressobj(wbits).decompress(data, MAX_PAGE_BYTES + 1)
    except zlib.error as error:
        raise WebError(f"Could not unpack the page: {error}") from error


def _part(url: str, title: str, body: str, part: int) -> str:
    chunks = [body[i:i + PART_CHARS] for i in range(0, len(body), PART_CHARS)] or [""]
    part = max(1, min(part, len(chunks)))
    head = f"Page: {title}\nURL: {url}\nPart {part} of {len(chunks)}\n\n"
    tail = (f"\n\n[More text: call web_fetch with part={part + 1}]" if part < len(chunks) else f"\n{PAGE_END}")
    return head + chunks[part - 1] + tail


# --- Einbetten (Board-iframe des 3D-Assistenten) ------------------------------------
EMBED_PROBE_BYTES = 256 * 1024     # für den <title>


def embeddable(url: str) -> tuple[str, str] | None:
    """(Endadresse nach Weiterleitungen, Titel), wenn die Seite öffentlich ist und sich einbetten lässt -
    also weder X-Frame-Options noch Content-Security-Policy: frame-ancestors (ohne *) es verbieten.
    Sonst None (der Browser würde sie im iframe ohnehin verweigern)."""
    try:
        request = urllib.request.Request(check_public_url(url.strip()), headers={
            "User-Agent": USER_AGENT, "Accept-Language": "de,en;q=0.8", "Accept-Encoding": "gzip, deflate"})
        with _OPENER.open(request, timeout=TIMEOUT_S) as response:
            final = response.geturl()
            headers = response.headers
            if "html" not in (headers.get("Content-Type") or "") or headers.get("X-Frame-Options"):
                return None
            for policy in headers.get_all("Content-Security-Policy") or []:
                for directive in policy.split(";"):
                    parts = directive.split()
                    if parts and parts[0].lower() == "frame-ancestors" and "*" not in parts[1:]:
                        return None
            raw = _decompress(response.read(EMBED_PROBE_BYTES), (headers.get("Content-Encoding") or "").lower())
            charset = headers.get_content_charset() or "utf-8"
        check_public_url(final)
    except (WebError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    title, _ = html_to_text(raw[:EMBED_PROBE_BYTES].decode(charset, errors="replace"))
    return final, title[:200]


# --- Stelle auf der Seite, an der die Antwort steht (Board scrollt dorthin) --------------
# Die Seite läuft im Board ohne Skripte in einem fremden Ursprung - von außen lässt sie sich nicht
# scrollen. Was immer geht, ist ein Sprungziel in der Adresse (seite.html#abschnitt): Der Browser
# scrollt dann selbst zu dem Element mit dieser id. Also: den Absatz suchen, der am besten zur
# Antwort passt, und das letzte Sprungziel davor nehmen.
ANCHOR_MIN_WORDS = 3            # so viele verschiedene Wörter der Antwort müssen in der Stelle vorkommen
ANCHOR_WINDOW = 3               # Absätze, die zusammen bewertet werden (Listen, Tabellenzeilen)
ANCHOR_SKIP_TOP_CHARS = 500     # steht die Stelle ohnehin ganz oben, bleibt die Seite oben
_WORD = re.compile(r"[^\W_]{4,}|\d{2,}")
_STOPWORDS = frozenset(
    "aber alle auch dass dann denn dies diese dieser doch eine einem einen einer eines haben hatte hier "
    "kann mehr nach nicht noch oder sehr sich sind über unter wenn werden wird wurde zwischen auf dem board "
    "about also been from have into more most only other some such than that their them then there these "
    "they this were what when which will with would your".split())


class _AnchorFinder(HTMLParser):
    """Textblöcke der Seite, jeder mit dem letzten Sprungziel (id bzw. <a name>) davor."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str | None, str]] = []
        self._anchor: str | None = None
        self._buffer: list[str] = []
        self._skip = 0
        self._in_title = False

    def _flush(self):
        text = " ".join("".join(self._buffer).split())
        self._buffer = []
        if text:
            self.blocks.append((self._anchor, text))

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
        if self._skip:
            return
        attributes = dict(attrs)
        target = attributes.get("id") or (attributes.get("name") if tag == "a" else None)
        if target or tag in _BLOCK:
            self._flush()
        if target:
            self._anchor = target

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK:
            self._flush()

    def handle_data(self, data):
        if not self._skip and not self._in_title:
            self._buffer.append(data)


def _words(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if word not in _STOPWORDS}


def find_anchor(html: str, answer: str) -> str | None:
    """Sprungziel (id) vor der Stelle der Seite, die am besten zur Antwort passt - oder None, wenn
    nichts deutlich passt, die Stelle ohnehin oben steht oder die Seite dort keine Sprungziele hat."""
    wanted = _words(answer)
    if len(wanted) < ANCHOR_MIN_WORDS:
        return None
    finder = _AnchorFinder()
    finder.feed(html)
    finder.close()
    finder._flush()
    blocks = finder.blocks
    if not blocks:
        return None
    found = [_words(text) & wanted for _, text in blocks]
    # Seltene Wörter zählen mehr: Ein Name oder eine Zahl sagt mehr als ein Wort, das überall steht
    spread = {word: sum(word in block for block in found) for word in wanted}
    weight = {word: 1.0 / count for word, count in spread.items() if count}
    best, best_score, best_words = -1, 0.0, 0
    for i in range(len(blocks)):
        words = set().union(*found[i:i + ANCHOR_WINDOW])
        score = sum(weight[word] for word in words)
        if score > best_score:
            best, best_score, best_words = i, score, len(words)
    if best < 0 or best_words < ANCHOR_MIN_WORDS:
        return None
    # Im besten Fenster den Absatz nehmen, der selbst am meisten trifft - sonst landet man einen
    # Abschnitt zu früh (das Fenster beginnt oft schon vor der eigentlichen Stelle)
    best = max(range(best, min(best + ANCHOR_WINDOW, len(blocks))),
               key=lambda i: (sum(weight[word] for word in found[i]), -i))
    if sum(len(text) for _, text in blocks[:best]) < ANCHOR_SKIP_TOP_CHARS:
        return None
    return blocks[best][0]


def page_anchor(url: str, answer: str) -> str | None:
    """Adresse mit Sprungziel (url#id) zu der Stelle, an der die Antwort steht - None ohne Treffer."""
    try:
        request = urllib.request.Request(check_public_url(url.strip()), headers={
            "User-Agent": USER_AGENT, "Accept-Language": "de,en;q=0.8", "Accept-Encoding": "gzip, deflate"})
        with _OPENER.open(request, timeout=TIMEOUT_S) as response:
            headers = response.headers
            raw = _decompress(response.read(MAX_PAGE_BYTES + 1), (headers.get("Content-Encoding") or "").lower())
            charset = headers.get_content_charset() or "utf-8"
    except (WebError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    anchor = find_anchor(raw[:MAX_PAGE_BYTES].decode(charset, errors="replace"), answer)
    if not anchor:
        return None
    return urllib.parse.urldefrag(url)[0] + "#" + urllib.parse.quote(anchor, safe="")


# --- HTML -> Text --------------------------------------------------------------------
_SKIP = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form", "button", "iframe"}
_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    """(Titel, lesbarer Text) - ohne Skripte, Navigation, Kopf- und Fußzeilen."""
    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts))
    text = "\n".join(line.strip() for line in text.split("\n"))
    return parser.title.strip(), re.sub(r"\n{3,}", "\n\n", text).strip()
