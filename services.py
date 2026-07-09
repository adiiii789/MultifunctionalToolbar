# =============================================================================
# services.py — Systemweite Dienste der Multifunctional Toolbar
# -----------------------------------------------------------------------------
# Hier liegen alle Dienste, die das Betriebssystem betreffen und von mehreren
# Plugins genutzt werden. Der Traylauncher managt nur — er importiert diese
# Dienste und reicht sie über den WebChannel an die Cards weiter ("media").
# Plugin-eigene Logik gehört NICHT hierher, sondern in die Plugin-Datei
# (handle_call / get_inline_html / PluginWidget).
#
# Enthalten:
#   - MediaControlBridge:   Windows-Medientasten (Play/Pause, Lautstärke ...)
#                           + Titel/Interpret/Album-Cover der laufenden Medien
#                           (Windows 10/11, optional "pip install winsdk")
#   - apply_native_titlebar: Färbt die NATIVE Windows-Titelleiste (DWM),
#                           ohne sie zu ersetzen — Snap/Andocken bleiben.
#   - create_services:      Registry aller Dienste für den WebChannel.
# =============================================================================

import traceback

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QEvent
from PyQt5.QtWidgets import QApplication


# =============================================================================
# Media-Service: Windows-Medientasten + Album-Cover (per MEDIA_BRIDGE abschaltbar)
# =============================================================================
class MediaControlBridge(QObject):
    themeChanged = pyqtSignal(str)
    mediaInfoChanged = pyqtSignal(str)  # JSON: Titel/Interpret/Cover (Win 10/11)

    def __init__(self, parent=None):
        super().__init__(parent)
        import platform
        self._is_windows = (platform.system().lower() == "windows")
        if self._is_windows:
            import ctypes
            self._user32 = ctypes.windll.user32
            self.VK_MEDIA_NEXT_TRACK = 0xB0
            self.VK_MEDIA_PREV_TRACK = 0xB1
            self.VK_MEDIA_STOP = 0xB2
            self.VK_MEDIA_PLAY_PAUSE = 0xB3
            self.VK_VOLUME_MUTE = 0xAD
            self.VK_VOLUME_DOWN = 0xAE
            self.VK_VOLUME_UP = 0xAF

        self._app = QApplication.instance()
        self._theme = self._read_theme()
        if self._app is not None:
            self._app.installEventFilter(self)
        self.destroyed.connect(self._detach_theme_watcher)

    def _read_theme(self):
        if self._app is not None:
            val = self._app.property("toolbar_theme")
            if isinstance(val, str):
                return val.lower()
        return "dark"

    def _update_theme(self, value):
        value = (value or "").lower()
        if value not in ("light", "dark"):
            return
        if value != self._theme:
            self._theme = value
            self.themeChanged.emit(self._theme)

    def _tap(self, vk):
        if not getattr(self, "_is_windows", False):
            return
        KEYEVENTF_KEYUP = 0x0002
        self._user32.keybd_event(vk, 0, 0, 0)
        self._user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def eventFilter(self, watched, event):
        if watched is self._app and event.type() == QEvent.DynamicPropertyChange:
            try:
                prop = event.propertyName().data().decode('utf-8')
            except Exception:
                prop = None
            if prop == "toolbar_theme":
                self._update_theme(self._app.property("toolbar_theme"))
        return super().eventFilter(watched, event)

    def _detach_theme_watcher(self):
        if self._app is not None:
            try:
                self._app.removeEventFilter(self)
            except Exception:
                pass
            self._app = None

    @pyqtSlot(result=str)
    def getTheme(self):
        return self._theme

    @pyqtSlot()
    def playPause(self):
        self._tap(self.VK_MEDIA_PLAY_PAUSE)

    @pyqtSlot()
    def next(self):
        self._tap(self.VK_MEDIA_NEXT_TRACK)

    @pyqtSlot()
    def prev(self):
        self._tap(self.VK_MEDIA_PREV_TRACK)

    @pyqtSlot()
    def stop(self):
        self._tap(self.VK_MEDIA_STOP)

    @pyqtSlot()
    def mute(self):
        self._tap(self.VK_VOLUME_MUTE)

    @pyqtSlot()
    def volUp(self):
        self._tap(self.VK_VOLUME_UP)

    @pyqtSlot()
    def volDown(self):
        self._tap(self.VK_VOLUME_DOWN)

    # --- Album-Cover / Titelinfo der laufenden Medien (Windows 10/11) ------
    # JS-Seite:  media.requestMediaInfo()  →  Signal  media.mediaInfoChanged(json)
    # JSON: {"available": bool, "title": str, "artist": str,
    #        "playing": bool|null, "thumbnail": "data:image/...;base64,..."}
    # Benötigt das optionale Paket "winsdk"  (pip install winsdk).
    @pyqtSlot()
    def requestMediaInfo(self):
        if not getattr(self, "_is_windows", False):
            self.mediaInfoChanged.emit('{"available": false}')
            return
        if getattr(self, "_media_busy", False):
            return
        self._media_busy = True
        import threading
        threading.Thread(target=self._fetch_media_info, daemon=True).start()

    def _fetch_media_info(self):
        # Läuft in eigenem Thread (WinRT ist async); Ergebnis kommt
        # thread-sicher per Qt-Signal zurück.
        import json
        import base64
        import asyncio
        payload = {"available": False}
        try:
            from winsdk.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as _GSMTC,
            )
            from winsdk.windows.storage.streams import (
                Buffer, DataReader, InputStreamOptions,
            )

            async def _grab():
                mgr = await _GSMTC.request_async()
                session = mgr.get_current_session()
                if session is None:
                    return None
                props = await session.try_get_media_properties_async()
                info = {"available": True,
                        "title": props.title or "",
                        "artist": props.artist or "",
                        "playing": None,
                        "thumbnail": ""}
                try:
                    status = session.get_playback_info().playback_status
                    info["playing"] = (int(status) == 4)  # 4 = PLAYING
                except Exception:
                    pass
                try:
                    ref = props.thumbnail
                    if ref is not None:
                        stream = await ref.open_read_async()
                        size = int(stream.size)
                        if 0 < size <= 5_000_000:
                            buf = Buffer(size)
                            await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
                            data = None
                            try:
                                data = bytes(memoryview(buf))[:buf.length]
                            except Exception:
                                try:
                                    reader = DataReader.from_buffer(buf)
                                    out = bytearray(buf.length)
                                    reader.read_bytes(out)
                                    data = bytes(out)
                                except Exception:
                                    data = None
                            if data:
                                is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
                                mime = "image/png" if is_png else "image/jpeg"
                                b64 = base64.b64encode(data).decode("ascii")
                                info["thumbnail"] = "data:" + mime + ";base64," + b64
                except Exception:
                    pass
                return info

            result = asyncio.run(_grab())
            if result:
                payload = result
        except ImportError:
            payload = {"available": False, "error": "winsdk fehlt (pip install winsdk)"}
        except Exception:
            payload = {"available": False}
        finally:
            self._media_busy = False
            try:
                self.mediaInfoChanged.emit(json.dumps(payload))
            except Exception:
                pass


# =============================================================================
# Native Windows-Titelleiste (DWM) — parametriert, ohne Launcher-Abhängigkeit
# =============================================================================
def apply_native_titlebar(widget, dark, caption_color, text_color):
    """Färbt die NATIVE Windows-Titelleiste (Win 10/11).

    Nutzt DwmSetWindowAttribute — die Leiste wird nicht ersetzt, alle
    Fenster-Features (Snap-Layouts, an die Seite andocken, Maximieren per
    Doppelklick usw.) bleiben vollständig erhalten.
    - Dark-Mode-Leiste:  Windows 10 1809+ (Attribut 19/20)
    - Eigene Farben:     Windows 11 (Attribute 35/36); auf Win 10 werden
                         diese Aufrufe still ignoriert.
    """
    import platform
    if platform.system().lower() != "windows":
        return
    try:
        import ctypes
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi

        flag = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (19 bei älteren Win10-Builds)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(flag), ctypes.sizeof(flag)) == 0:
                break

        def _colorref(hexstr):  # "#RRGGBB" → COLORREF 0x00BBGGRR
            r = int(hexstr[1:3], 16)
            g = int(hexstr[3:5], 16)
            b = int(hexstr[5:7], 16)
            return (b << 16) | (g << 8) | r

        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36
        c = ctypes.c_uint(_colorref(caption_color))
        t = ctypes.c_uint(_colorref(text_color))
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(c), ctypes.sizeof(c))
        dwm.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(t), ctypes.sizeof(t))
    except Exception:
        pass  # z. B. dwmapi nicht verfügbar → native Standard-Leiste bleibt


# =============================================================================
# Service-Registry: alles, was Cards über den WebChannel bekommen sollen
# =============================================================================
def create_services(parent=None):
    """Instanziiert alle systemweiten Dienste (Name → QObject).

    Neue Dienste hier ergänzen; der Launcher registriert sie automatisch
    unter ihrem Namen auf dem WebChannel der Cards.
    """
    return {"media": MediaControlBridge(parent)}
