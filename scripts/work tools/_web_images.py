"""Gemeinsam für Bildersuche.py und Gifsuche.py: Bilder sicher aus dem Internet laden.

"_" am Anfang: kein Plugin (Explorer und Werkzeugliste überspringen die Datei). Die Plugins laden
sie mit load_helper() aus ihrem eigenen Ordner.

Sicherheit:
  - Nur öffentliche http(s)-Adressen, auch nach Weiterleitungen - Suchergebnisse könnten sonst auf
    Geräte im Heimnetz (Router, NAS) oder Dienste auf diesem PC zeigen.
  - Nur JPEG, PNG, GIF und WebP (Inhaltstyp und Dateianfang geprüft), kein SVG; Größen-, Pixel-
    und Zeitlimit.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QImage, QImageReader
from PyQt5.QtWidgets import QApplication

IMAGE_MAX_PIXELS = 40_000_000    # größere Bilder werden nicht dekodiert
TIMEOUT_S = 15
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
_FORMATS = {"image/jpeg": b"\xff\xd8", "image/png": b"\x89PNG", "image/gif": b"GIF8", "image/webp": b"RIFF"}
_DECODABLE = ("jpeg", "jpg", "png", "gif", "webp")


class ImageError(Exception):
    """Erwarteter Fehler beim Laden eines Bildes (Adresse gesperrt, kein Bild, zu groß ...)."""


def check_public_url(url: str) -> str:
    """Nur http(s) zu öffentlichen Adressen (wie web.py des KI-Dienstes)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ImageError("nur http(s)")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as error:
        raise ImageError(f"Server nicht gefunden: {parts.hostname}") from error
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise ImageError(f"Adresse im lokalen Netz gesperrt: {parts.hostname}")
    return url


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(_PublicRedirects())


def fetch_image(url: str, max_bytes: int) -> bytes:
    """Bilddaten von einer öffentlichen Adresse - nur JPEG/PNG/GIF/WebP, höchstens max_bytes."""
    request = urllib.request.Request(check_public_url(url), headers={"User-Agent": USER_AGENT,
                                                                      "Accept": "image/webp,image/*;q=0.8"})
    try:
        with OPENER.open(request, timeout=TIMEOUT_S) as response:
            content_type = (response.headers.get_content_type() or "").lower()
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        raise ImageError(f"HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ImageError(f"nicht erreichbar: {error}") from error
    if len(data) > max_bytes:
        raise ImageError("Bild zu groß")
    magic = _FORMATS.get(content_type)
    if magic is None or not data.startswith(magic) or (content_type == "image/webp" and data[8:12] != b"WEBP"):
        raise ImageError(f"kein unterstütztes Bild ({content_type or 'unbekannt'})")
    return data


def image_reader(data: bytes) -> tuple[QImageReader, QBuffer]:
    """QImageReader für die Daten - nur JPEG/PNG/GIF/WebP (kein SVG, das externe Inhalte nachladen
    könnte), Größe vor dem Dekodieren geprüft. Den Puffer am Leben halten, solange gelesen wird."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.ReadOnly)
    reader = QImageReader(buffer)
    if bytes(reader.format()).decode().lower() not in _DECODABLE:
        raise ImageError("kein unterstütztes Bild")
    size = reader.size()
    if size.isValid() and size.width() * size.height() > IMAGE_MAX_PIXELS:
        raise ImageError("Bild zu groß")
    return reader, buffer


def decode_image(data: bytes) -> QImage:
    reader, _buffer = image_reader(data)
    image = reader.read()
    if image.isNull():
        raise ImageError(f"Bild nicht lesbar: {reader.errorString()}")
    return image


def detect_theme(default="dark"):
    app = QApplication.instance()
    value = app.property("toolbar_theme") if app is not None else None
    return value.lower() if isinstance(value, str) and value.lower() in ("light", "dark") else default


STYLES = {
    "dark": """
        QWidget#root { background: #1d2128; color: #e6e6e6; }
        QLineEdit { background: #2a2f37; color: #f0f0f0; border: 1px solid #3a414c; border-radius: 6px;
                    padding: 6px 8px; font-size: 14px; }
        QPushButton { background: #8ab4f8; color: #1c1f24; border: none; border-radius: 6px;
                      padding: 6px 14px; font-weight: 600; }
        QPushButton:hover { background: #a9c5ff; }
        QLabel { color: #9aa4b2; }
        QListWidget { background: #1d2128; color: #c9d1db; border: 1px solid #2f353f; font-size: 11px; }
        QListWidget::item { border-radius: 6px; padding: 4px; }
        QListWidget::item:hover { background: #2a3140; }
        QListWidget::item:selected { background: #34507a; color: white; }
    """,
    "light": """
        QWidget#root { background: #f7f8fa; color: #1a1a1a; }
        QLineEdit { background: white; color: #1a1a1a; border: 1px solid #c9ced6; border-radius: 6px;
                    padding: 6px 8px; font-size: 14px; }
        QPushButton { background: #007aff; color: white; border: none; border-radius: 6px;
                      padding: 6px 14px; font-weight: 600; }
        QPushButton:hover { background: #2b8fff; }
        QLabel { color: #5b6470; }
        QListWidget { background: white; color: #333; border: 1px solid #dde1e7; font-size: 11px; }
        QListWidget::item { border-radius: 6px; padding: 4px; }
        QListWidget::item:hover { background: #eef3fb; }
        QListWidget::item:selected { background: #cfe0fa; color: #1a1a1a; }
    """,
}
