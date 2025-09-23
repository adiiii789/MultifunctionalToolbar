# scripts/pro_calendar_html.py
import os
import json
import sys
from datetime import datetime, date, timedelta, time
from pathlib import Path

from pytz import timezone
from dateutil.rrule import rrulestr, rruleset
from icalendar import Calendar

from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QEvent
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QListWidget, QListWidgetItem, QLabel, QAbstractItemView,
    QSizePolicy
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

# ===========================
# Konfiguration / Farben
# ===========================
CONFIG_FILE = "calendar_config.json"
PALETTE = [
    "#8ab4f8", "#f28b82", "#fbbc04", "#34a853", "#a78bfa", "#80cbc4",
    "#ff79c6", "#c792ea", "#ffd54f", "#81c784", "#64b5f6"
]
LOCAL_TZ = timezone("Europe/Berlin")  # Lokale TZ für Normalisierung

# ===========================
# Pfade / Config
# ===========================
def _script_dir() -> Path:
    try:
        return Path(__file__).resolve().parent
    except Exception:
        return Path.cwd()


def config_path() -> Path:
    return _script_dir() / CONFIG_FILE


def load_config() -> list:
    p = config_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            norm_paths = []
            for path in data:
                full_path = Path(path)
                if not full_path.is_absolute():
                    full_path = _script_dir() / full_path
                norm_paths.append(str(full_path))
            return norm_paths
        except Exception:
            return []
    return []


def save_config(paths: list):
    p = config_path()
    p.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")


# ===========================
# Datums-/Zeit-Helfer
# ===========================
def ensure_datetime(x):
    """
    Normalize ICS date/datetime values to naive local datetimes (no tzinfo).
    - date -> combine with 00:00 local
    - aware datetime -> convert to LOCAL_TZ and drop tzinfo
    - naive datetime -> keep as is
    """
    if isinstance(x, date) and not isinstance(x, datetime):
        return datetime.combine(x, time.min)
    if isinstance(x, datetime):
        if x.tzinfo is None:
            return x
        dt_local = x.astimezone(LOCAL_TZ)
        return dt_local.replace(tzinfo=None)
    return x


def current_week_range(today: date = None):
    if today is None:
        today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def next_week_range(today: date = None):
    mo, _ = current_week_range(today)
    n_mo = mo + timedelta(days=7)
    n_su = n_mo + timedelta(days=6)
    return n_mo, n_su


# ===========================
# Drag&Drop-Liste
# ===========================
class DropListWidget(QListWidget):
    filesDropped = pyqtSignal(list)  # list[str]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self.viewport():
            if e.type() in (QEvent.DragEnter, QEvent.DragMove):
                if self._has_ics(e.mimeData()):
                    e.acceptProposedAction()
                else:
                    e.ignore()
                return True
            elif e.type() == QEvent.Drop:
                paths = self._extract_paths(e.mimeData())
                if paths:
                    e.acceptProposedAction()
                    self.filesDropped.emit(paths)
                else:
                    e.ignore()
                return True
        return super().eventFilter(obj, e)

    def _has_ics(self, mime):
        if mime.hasUrls():
            for u in mime.urls():
                p = u.toLocalFile()
                if p and p.lower().endswith(".ics"):
                    return True
        if mime.hasText():
            for line in mime.text().splitlines():
                s = line.strip()
                if s.startswith("file://"):
                    try:
                        p = QUrl(s).toLocalFile()
                        if p and p.lower().endswith(".ics"):
                            return True
                    except Exception:
                        pass
        return False

    def _extract_paths(self, mime):
        paths = []
        if mime.hasUrls():
            for u in mime.urls():
                p = u.toLocalFile()
                if p and p.lower().endswith(".ics"):
                    paths.append(p)
        if not paths and mime.hasText():
            for line in mime.text().splitlines():
                s = line.strip()
                if s.startswith("file://"):
                    p = QUrl(s).toLocalFile()
                    if p and p.lower().endswith(".ics"):
                        paths.append(p)
        # de-dupe
        return list(dict.fromkeys(paths))


# ===========================
# Haupt-Widget
# ===========================
class PluginWidget(QMainWindow):
    def __init__(self, theme="dark", mode="Window"):
        super().__init__()
        self.setWindowTitle("📅 Kalender")
        self.resize(1100, 740)
        self.mode = mode  # "Window" or "Popup"
        self.ics_files = load_config()

        # --- Layout Grundgerüst ---
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar + lists only for Window mode
        if self.mode == "Window":
            bar = QWidget()
            bar_l = QHBoxLayout(bar)
            bar_l.setContentsMargins(12, 10, 12, 10)
            bar_l.setSpacing(10)

            self.btn_add = QPushButton("ICS hinzufügen")
            self.btn_remove = QPushButton("Entfernen")
            self.btn_week = QPushButton("Woche")
            self.btn_2weeks = QPushButton("2 Wochen")
            self.btn_month = QPushButton("Monat")
            self.btn_day = QPushButton("Heute (kompakt)")
            self.title_label = QLabel(" ")
            self.title_label.setStyleSheet("color:#aaa;")

            bar_l.addWidget(self.btn_add)
            bar_l.addWidget(self.btn_remove)
            bar_l.addStretch(1)
            bar_l.addWidget(self.btn_day)
            bar_l.addWidget(self.btn_week)
            bar_l.addWidget(self.btn_2weeks)
            bar_l.addWidget(self.btn_month)
            bar_l.addStretch(1)
            bar_l.addWidget(self.title_label)

            # two calendar lists: one general, one for compact day view selection
            self.list_widget = DropListWidget()
            self.list_widget.setMaximumHeight(140)
            self.list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

            self.list_widget_day = DropListWidget()
            self.list_widget_day.setMaximumHeight(140)
            self.list_widget_day.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
            self.list_widget_day.setVisible(False)

            bar.setStyleSheet("""
                QWidget { background:#111318; }
                QPushButton {
                    background:#263238; color:#e6e6e6; border:none; padding:8px 12px; border-radius:10px;
                    font-weight: 600;
                }
                QPushButton:hover { background:#37474f; }
                QListWidget { background:#0f1115; color:#ddd; border-top:1px solid #1f2430; border-bottom:1px solid #1f2430; }
            """)

            root.addWidget(bar)
            root.addWidget(self.list_widget)
            root.addWidget(self.list_widget_day)

            # connect events
            self.btn_add.clicked.connect(self.add_ics_dialog)
            self.btn_remove.clicked.connect(self.remove_selected)
            self.btn_week.clicked.connect(lambda: self.render(mode="week"))
            self.btn_2weeks.clicked.connect(lambda: self.render(mode="two_weeks"))
            self.btn_month.clicked.connect(lambda: self.render(mode="month"))
            self.btn_day.clicked.connect(lambda: self.render(mode="day"))

            self.list_widget.itemChanged.connect(lambda _: self.render())
            self.list_widget_day.itemChanged.connect(lambda _: self.render("day"))

            self.list_widget.filesDropped.connect(self.add_ics_paths)
            self.list_widget_day.filesDropped.connect(self.add_ics_paths)

        # WebView (always)
        self.web = QWebEngineView()
        self.web.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.web, 1)

        # Initial
        if self.mode == "Window":
            self._refresh_calendar_list()
            self._refresh_calendar_list_day()
            self.render(mode="week")
        else:
            # popup -> directly day compact
            self.render(mode="day")

    # ---- Kalenderlisten ----
    def _refresh_calendar_list_day(self):
        if self.mode != "Window":
            return
        self.list_widget_day.clear()
        for path in self.ics_files:
            full = Path(path)
            if not full.is_absolute():
                full = _script_dir() / full
            if not full.exists():
                continue
            item = QListWidgetItem(full.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, str(full))
            self.list_widget_day.addItem(item)

    def _refresh_calendar_list(self):
        if self.mode != "Window":
            return
        self.list_widget.clear()
        for path in self.ics_files:
            full = Path(path)
            if not full.is_absolute():
                full = _script_dir() / full
            if not full.exists():
                continue
            item = QListWidgetItem(full.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, str(full))
            self.list_widget.addItem(item)

    def add_ics_paths(self, paths):
        changed = False
        current = set(self.ics_files)
        for p in paths:
            if p and p not in current and os.path.isfile(p):
                self.ics_files.append(p)
                changed = True
        if changed:
            save_config(self.ics_files)
            if self.mode == "Window":
                self._refresh_calendar_list()
                self._refresh_calendar_list_day()
            self.render()

    def add_ics_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "ICS-Dateien auswählen", "", "Kalender (*.ics)")
        if paths:
            self.add_ics_paths(paths)

    def remove_selected(self):
        if self.mode != "Window":
            return
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        to_remove = {it.data(Qt.UserRole) for it in selected}
        self.ics_files = [p for p in self.ics_files if p not in to_remove]
        save_config(self.ics_files)
        self._refresh_calendar_list()
        self._refresh_calendar_list_day()
        self.render()

    def _active_calendars(self):
        if self.mode != "Window":
            return self.ics_files
        act = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if it.checkState() == Qt.Checked:
                act.append(it.data(Qt.UserRole))
        return act

    def _active_calendars_day(self):
        if self.mode != "Window":
            return self.ics_files
        act = []
        for i in range(self.list_widget_day.count()):
            it = self.list_widget_day.item(i)
            if it.checkState() == Qt.Checked:
                act.append(it.data(Qt.UserRole))
        return act

    # ===========================
    # ICS laden / expandieren (inkl. RRULE/RDATE/EXDATE + overrides)
    # ===========================
    def load_events(self, active_paths=None):
        evs = []
        now = datetime.now()
        # big window so recurrences expand reliably
        window_start = now - timedelta(days=730)
        window_end = now + timedelta(days=730)

        calendars = active_paths if active_paths is not None else self._active_calendars()

        for i, path in enumerate(calendars):
            color = PALETTE[i % len(PALETTE)]
            try:
                with open(path, "rb") as f:
                    cal = Calendar.from_ical(f.read())

                masters = []
                overrides = {}

                for comp in cal.walk():
                    if comp.name != "VEVENT":
                        continue

                    uid = str(comp.get("UID") or "")
                    rec_id = comp.get("RECURRENCE-ID")

                    if rec_id:
                        # recurrence-id overrides
                        rid_dt = ensure_datetime(getattr(rec_id, "dt", rec_id))
                        overrides[(uid, rid_dt)] = comp
                    else:
                        masters.append(comp)

                for comp in masters:
                    uid = str(comp.get("UID") or "")
                    dtstart_prop = comp.get("DTSTART")
                    if not dtstart_prop:
                        continue

                    start_base = ensure_datetime(getattr(dtstart_prop, "dt", dtstart_prop))

                    end_prop = comp.get("DTEND")
                    if end_prop is not None:
                        end_base = ensure_datetime(getattr(end_prop, "dt", end_prop))
                    else:
                        dur_prop = comp.get("DURATION")
                        if dur_prop:
                            try:
                                delta = getattr(dur_prop, "dt", dur_prop)
                                end_base = start_base + delta
                            except Exception:
                                end_base = start_base + timedelta(hours=1)
                        else:
                            end_base = start_base + timedelta(hours=1)

                    duration = max(end_base - start_base, timedelta(minutes=1))

                    summary_base = str(comp.get("SUMMARY") or "Termin")
                    all_day_base = isinstance(getattr(dtstart_prop, "dt", dtstart_prop), date) and not isinstance(getattr(dtstart_prop, "dt", dtstart_prop), datetime)

                    rrule_prop = comp.get("RRULE")
                    rdate_props = comp.get("RDATE")
                    exdate_props = comp.get("EXDATE")

                    has_recur = bool(rrule_prop or rdate_props or exdate_props)

                    if has_recur:
                        rset = rruleset()

                        # RRULE
                        if rrule_prop:
                            try:
                                rule_bytes = rrule_prop.to_ical() if hasattr(rrule_prop, "to_ical") else None
                                rule_str = (rule_bytes.decode()
                                            if isinstance(rule_bytes, (bytes, bytearray))
                                            else (str(rule_bytes) if rule_bytes is not None else str(rrule_prop)))
                                r = rrulestr(rule_str, dtstart=start_base)
                                rset.rrule(r)
                            except Exception:
                                pass

                        # RDATE
                        if rdate_props:
                            rdate_list = rdate_props if isinstance(rdate_props, list) else [rdate_props]
                            for rdp in rdate_list:
                                dts = getattr(rdp, "dts", None)
                                if dts:
                                    for d in dts:
                                        try:
                                            rset.rdate(ensure_datetime(getattr(d, "dt", d)))
                                        except Exception:
                                            pass

                        # EXDATE
                        if exdate_props:
                            exdate_list = exdate_props if isinstance(exdate_props, list) else [exdate_props]
                            for edp in exdate_list:
                                dts = getattr(edp, "dts", None)
                                if dts:
                                    for d in dts:
                                        try:
                                            rset.exdate(ensure_datetime(getattr(d, "dt", d)))
                                        except Exception:
                                            pass

                        try:
                            occurrences = rset.between(window_start, window_end, inc=True)
                        except Exception:
                            occurrences = []

                        for occ_start in occurrences:
                            ov = overrides.get((uid, occ_start))
                            if ov:
                                o_dtstart_prop = ov.get("DTSTART")
                                o_dtend_prop = ov.get("DTEND")
                                o_start = ensure_datetime(getattr(o_dtstart_prop, "dt", o_dtstart_prop)) if o_dtstart_prop else occ_start
                                if o_dtend_prop:
                                    o_end = ensure_datetime(getattr(o_dtend_prop, "dt", o_dtend_prop))
                                else:
                                    o_end = o_start + duration
                                o_summary = str(ov.get("SUMMARY") or summary_base)
                                o_all_day = (
                                    isinstance(getattr(o_dtstart_prop, "dt", o_dtstart_prop), date) and
                                    not isinstance(getattr(o_dtstart_prop, "dt", o_dtstart_prop), datetime)
                                ) if o_dtstart_prop else all_day_base
                                if o_end <= o_start:
                                    o_end = o_start + timedelta(minutes=60)

                                evs.append({
                                    "title": o_summary,
                                    "start": o_start.isoformat(),
                                    "end": o_end.isoformat(),
                                    "allDay": bool(o_all_day),
                                    "calendar": os.path.basename(path),
                                    "color": color,
                                    "path": path
                                })
                            else:
                                occ_end = occ_start + duration
                                if occ_end <= occ_start:
                                    occ_end = occ_start + timedelta(minutes=60)
                                evs.append({
                                    "title": summary_base,
                                    "start": occ_start.isoformat(),
                                    "end": occ_end.isoformat(),
                                    "allDay": bool(all_day_base),
                                    "calendar": os.path.basename(path),
                                    "color": color,
                                    "path": path
                                })
                    else:
                        # single (non-recurrent) event
                        if end_base <= start_base:
                            end_base = start_base + timedelta(minutes=60)
                        evs.append({
                            "title": summary_base,
                            "start": start_base.isoformat(),
                            "end": end_base.isoformat(),
                            "allDay": bool(all_day_base),
                            "calendar": os.path.basename(path),
                            "color": color,
                            "path": path
                        })

            except Exception:
                # skip broken calendars but continue
                continue

        evs.sort(key=lambda e: (e["start"], e["end"]))
        return evs

    # ===========================
    # Rendern
    # ===========================
    def render(self, mode: str = None):
        if mode is None:
            mode = getattr(self, "_last_mode", "week")
        self._last_mode = mode

        if mode == "day":
            # compact day view
            if self.mode == "Window":
                self.list_widget.setVisible(False)
                self.list_widget_day.setVisible(True)
            all_events = self.load_events(active_paths=self._active_calendars_day())
            today_date = date.today()
            todays = []
            for ev in all_events:
                s = datetime.fromisoformat(ev["start"])
                e = datetime.fromisoformat(ev["end"])
                if s.date() <= today_date <= e.date():
                    todays.append(ev)

            # sort: all-day first, then by start time
            def _key(ev):
                s = datetime.fromisoformat(ev["start"])
                return (0 if ev.get("allDay") else 1, s.time())
            todays.sort(key=_key)

            html = self._build_day_compact_html(todays, today_date)
            self.web.setHtml(html, baseUrl=QUrl.fromLocalFile(str(_script_dir())))
            return

        # non-day: week/2-weeks/month
        if self.mode == "Window":
            self.list_widget.setVisible(True)
            self.list_widget_day.setVisible(False)

            events = self.load_events()
            if mode == "week":
                mo, su = current_week_range()
                self.title_label.setText(f"Aktuelle Woche · {mo.strftime('%d.%m.%Y')} – {su.strftime('%d.%m.%Y')}")
            elif mode == "two_weeks":
                mo, su = current_week_range()
                nmo, nsu = next_week_range()
                self.title_label.setText(
                    f"Woche + nächste · {mo.strftime('%d.%m')}–{su.strftime('%d.%m')} & {nmo.strftime('%d.%m')}–{nsu.strftime('%d.%m')}"
                )
            else:
                today = date.today()
                self.title_label.setText(today.strftime("Monat · %B %Y"))

            html = self._build_html(events, mode)
            self.web.setHtml(html, baseUrl=QUrl.fromLocalFile(str(_script_dir())))

    # ---- HTML für Woche/2 Wochen/Monat ----
    def _build_html(self, events, mode):
        events_json = json.dumps(events, ensure_ascii=False)
        today_iso = date.today().isoformat()

        html = WINDOW_HTML_TEMPLATE
        html = html.replace("__EVENTS__", events_json)
        html = html.replace("__MODE__", mode)
        html = html.replace("__TODAY__", today_iso)
        return html

    # ---- Kompakte Tagesansicht (keine Scrollbars) ----
    def _build_day_compact_html(self, events, today_date: date):
        # Create JS event list with start/end hours and minutes and allDay flag
        js_events = []
        for ev in events:
            start_dt = datetime.fromisoformat(ev["start"])
            end_dt = datetime.fromisoformat(ev["end"])
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(hours=1)
            js_events.append({
                "startH": start_dt.hour,
                "startM": start_dt.minute,
                "endH": end_dt.hour,
                "endM": end_dt.minute,
                "title": ev["title"],
                "color": ev.get("color", "#3a82f6"),
                "allDay": ev.get("allDay", False),
            })

        events_json = json.dumps(js_events, ensure_ascii=False)

        html = DAY_HTML_TEMPLATE
        html = html.replace("__EVENTS__", events_json)
        return html


# ===========================
# HTML-Templates (Window + Day)
# ===========================
WINDOW_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <title>Kalender</title>
  <style>
    :root {
      --bg:#1c1f24;
      --panel:#2a2f35;
      --text:#e8e8e8;
      --muted:#a9b0b7;
      --border:#3a4048;
      --chip:#3c4550;
    }
    * { box-sizing: border-box; }
    html, body, .wrap {
      height: 100vh;
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
      display: flex;
      flex-direction: column;
    }
    .wrap { flex-grow: 1; display: flex; flex-direction: column; height: 100%; }
    .toolbar {
      display: flex; justify-content: space-between; align-items: center; gap: 12px;
      padding: 10px 14px; background: var(--panel); border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .toolbar .left, .toolbar .right { display: flex; align-items: center; gap: 8px; }
    .btn {
      background: #3a444f; color: var(--text); border: 1px solid var(--border);
      padding: 8px 14px; border-radius: 10px; cursor: pointer; font-weight: 600; user-select: none;
    }
    .btn:hover { filter: brightness(1.1); }

    .legend {
      display: flex; flex-wrap: wrap; gap: 12px; padding: 8px 14px;
      background: var(--panel); border-bottom: 1px solid var(--border); flex-shrink: 0; user-select: none;
    }
    .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.9em; color: var(--muted); }
    .legend-color { width: 14px; height: 14px; border-radius: 4px; flex-shrink: 0; }

    #calendar {
      flex-grow: 1; display: grid; grid-template-columns: repeat(7, 1fr);
      gap: 8px; padding: 10px; overflow-y: auto;
      background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0));
    }

    .day-label { font-weight: 600; color: var(--muted); font-size: 0.92em; margin-bottom: 2px; }

    .day {
      background: #2f3640; border-radius: 12px; padding: 8px;
      display: flex; flex-direction: column; box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      transition: background-color 0.3s ease; user-select: none; overflow: hidden;
    }
    .date-num { font-size: 1em; font-weight: 700; color: var(--muted); margin-bottom: 6px; flex-shrink: 0; }
    .events { flex: 1 1 auto; display: flex; flex-direction: column; gap: 4px; overflow: hidden; }
    .event {
      font-size: 0.8em; padding: 4px 6px; border-radius: 8px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      box-shadow: 0 1px 3px rgba(0,0,0,0.5); color: #fff; transition: filter 0.2s ease;
    }
    .event:hover { filter: brightness(1.1); }

    .other-month { opacity: 0.32; }

    .month-header {
      text-align: center; font-size: 1.4em; font-weight: 700; padding: 10px 0;
      background: var(--panel); border-bottom: 1px solid var(--border); color: var(--text);
      flex-shrink: 0; user-select: none;
    }
  </style>
</head>
<body>
<div class="wrap">
  <div class="toolbar">
    <div class="left">
      <button class="btn" onclick="prev()">◀</button>
      <button class="btn" onclick="next()">▶</button>
    </div>
    <div class="right">
      <span id="title" style="color:var(--muted)"></span>
    </div>
  </div>

  <div class="legend" id="legend"></div>
  <div class="month-header" id="monthHeader"></div>
  <div id="calendar"></div>
</div>

<script>
  const EVENTS_JSON = __EVENTS__;
  let currentMode = "__MODE__"; // "week" | "two_weeks" | "month"
  let currentDate = new Date("__TODAY__");

  function parseLocalISO(s){
    const [datePart, timePart] = String(s).split("T");
    const [y,m,d] = datePart.split("-").map(Number);
    if(!timePart) return new Date(y, m-1, d);
    const clean = timePart.replace("Z","");
    const [hh="0", mm="0", ss="0"] = clean.split(":");
    return new Date(y, m-1, d, parseInt(hh||"0"), parseInt(mm||"0"), parseInt(ss||"0"));
  }

  const events = EVENTS_JSON.map(ev=>{
    let s = parseLocalISO(ev.start);
    let e = ev.end ? parseLocalISO(ev.end) : null;
    if(!e || e <= s) e = new Date(s.getTime()+60*60*1000);
    return {...ev, startDate:s, endDate:e, allDay:!!ev.allDay};
  });

  function startOfWeekMonday(d){
    const tmp = new Date(d);
    const dow = (tmp.getDay()+6)%7;
    tmp.setDate(tmp.getDate()-dow);
    tmp.setHours(0,0,0,0);
    return tmp;
  }

  function setClientTitle(){
    const t = document.getElementById("title");
    const fmt = d => d.toLocaleDateString();
    if(currentMode==="week"){
      const start = startOfWeekMonday(currentDate);
      const end = new Date(start); end.setDate(start.getDate()+6);
      t.textContent = `Woche: ${fmt(start)} – ${fmt(end)}`;
    }else if(currentMode==="two_weeks"){
      const start = startOfWeekMonday(currentDate);
      const end = new Date(start); end.setDate(start.getDate()+13);
      t.textContent = `2 Wochen: ${fmt(start)} – ${fmt(end)}`;
    }else{
      t.textContent = currentDate.toLocaleDateString(undefined, {month:"long", year:"numeric"});
    }
  }

  function buildLegend(){
    const legend = document.getElementById("legend");
    legend.innerHTML = "";
    const byCalendar = {};
    events.forEach(ev => { byCalendar[ev.calendar] = ev.color; });
    Object.entries(byCalendar).forEach(([cal, color])=>{
      const item = document.createElement("div");
      item.className = "legend-item";
      item.innerHTML = `<span class="legend-color" style="background:${color}"></span> ${cal}`;
      legend.appendChild(item);
    });
  }

  function render(){
    setClientTitle();
    buildLegend();
    if(currentMode==="month"){
      setMonthHeader();
      renderMonth();
    }else{
      document.getElementById("monthHeader").textContent = "";
      if(currentMode==="week") renderDays(7);
      else if(currentMode==="two_weeks") renderDays(14);
    }
  }

  function setMonthHeader(){
    const header = document.getElementById("monthHeader");
    const options = {month:'long', year:'numeric'};
    header.textContent = currentDate.toLocaleDateString(undefined, options);
  }

  function renderDays(numDays){
    const container = document.getElementById("calendar");
    container.innerHTML = "";
    container.style.gridTemplateColumns = "repeat(7, 1fr)";
    container.style.gridTemplateRows = `repeat(${Math.ceil(numDays/7)}, 1fr)`;

    const start = startOfWeekMonday(currentDate);
    for(let i=0;i<numDays;i++){
      const d0 = new Date(start);
      d0.setDate(start.getDate()+i);
      makeDayBox(d0, container);
    }
  }

  function renderMonth(){
    const container = document.getElementById("calendar");
    container.innerHTML = "";
    container.style.gridTemplateColumns = "repeat(7, 1fr)";
    container.style.gridTemplateRows = "repeat(6, 1fr)";

    const first = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const start = startOfWeekMonday(first); // ensure Monday start

    for(let i=0;i<42;i++){
      const d0 = new Date(start);
      d0.setDate(start.getDate()+i);
      const box = makeDayBox(d0, container);
      if(d0.getMonth() !== currentDate.getMonth()){
        box.classList.add("other-month");
      }
    }
  }

  function makeDayBox(d0, container){
    const box = document.createElement("div");
    box.className = "day";

    const dateNum = document.createElement("div");
    dateNum.className = "date-num";
    dateNum.textContent = d0.getDate();
    box.appendChild(dateNum);

    const evWrap = document.createElement("div");
    evWrap.className = "events";
    box.appendChild(evWrap);

    const dayStart = new Date(d0); dayStart.setHours(0,0,0,0);
    const dayEnd = new Date(d0); dayEnd.setHours(23,59,59,999);

    const dayEvents = events.filter(ev => ev.startDate <= dayEnd && ev.endDate > dayStart);

    dayEvents.sort((a,b)=>{
      const aAll = !!a.allDay, bAll = !!b.allDay;
      if(aAll!==bAll) return aAll ? -1 : 1;
      return a.startDate - b.startDate;
    });

    dayEvents.forEach(ev=>{
      const el = document.createElement("div");
      el.className = "event";
      el.style.background = ev.color;

      if(ev.allDay){
        el.textContent = ev.title;
      }else{
        const st = ev.startDate.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
        const et = ev.endDate.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
        el.textContent = `${st} – ${et} ${ev.title}`;
      }
      evWrap.appendChild(el);
    });

    container.appendChild(box);
    return box;
  }

  function prev(){
    if(currentMode==="week"){
      currentDate.setDate(currentDate.getDate()-7);
    }else if(currentMode==="two_weeks"){
      currentDate.setDate(currentDate.getDate()-14);
    }else{
      currentDate.setMonth(currentDate.getMonth()-1);
    }
    render();
  }

  function next(){
    if(currentMode==="week"){
      currentDate.setDate(currentDate.getDate()+7);
    }else if(currentMode==="two_weeks"){
      currentDate.setDate(currentDate.getDate()+14);
    }else{
      currentDate.setMonth(currentDate.getMonth()+1);
    }
    render();
  }

  render();
</script>

</body>
</html>
"""

DAY_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>Tagesansicht</title>
  <style>
    html, body {
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      background: #1e1e1e;
      color: #ddd;
    }

    .day-view {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    .all-day {
      border-bottom: 1px solid #333;
      padding: 0px;
      background: #2a2a2a;
      min-height: 0px;
    }
    .all-day-event {
      display: inline-block;
      background: #3a82f6;
      color: white;
      padding: 2px 6px;
      margin: 2px;
      border-radius: 4px;
      font-size: 12px;
    }

    .hours {
      flex: 1;
      position: relative;
      display: flex;
      flex-direction: column;
      height: calc(100vh - 80px);
    }
    .hour {
      border-top: 1px solid #333;
      flex: 1;
      position: relative;
    }
    .hour-label {
      position: absolute;
      left: 0;
      top: 0;
      width: 50px;
      text-align: right;
      font-size: 11px;
      color: #aaa;
      padding-right: 5px;
    }

    .event {
      position: absolute;
      left: 60px;
      right: 10px;
      background: #7ed321;
      border-radius: 4px;
      padding: 4px;
      color: #fff;
      font-size: 12px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      overflow: hidden;
    }
  </style>
</head>
<body>
  <div class="day-view">
    <div class="all-day" id="allDayEvents"></div>
    <div class="hours" id="hours">
      <div class="hour"><div class="hour-label">00:00</div></div>
      <div class="hour"><div class="hour-label">01:00</div></div>
      <div class="hour"><div class="hour-label">02:00</div></div>
      <div class="hour"><div class="hour-label">03:00</div></div>
      <div class="hour"><div class="hour-label">04:00</div></div>
      <div class="hour"><div class="hour-label">05:00</div></div>
      <div class="hour"><div class="hour-label">06:00</div></div>
      <div class="hour"><div class="hour-label">07:00</div></div>
      <div class="hour"><div class="hour-label">08:00</div></div>
      <div class="hour"><div class="hour-label">09:00</div></div>
      <div class="hour"><div class="hour-label">10:00</div></div>
      <div class="hour"><div class="hour-label">11:00</div></div>
      <div class="hour"><div class="hour-label">12:00</div></div>
      <div class="hour"><div class="hour-label">13:00</div></div>
      <div class="hour"><div class="hour-label">14:00</div></div>
      <div class="hour"><div class="hour-label">15:00</div></div>
      <div class="hour"><div class="hour-label">16:00</div></div>
      <div class="hour"><div class="hour-label">17:00</div></div>
      <div class="hour"><div class="hour-label">18:00</div></div>
      <div class="hour"><div class="hour-label">19:00</div></div>
      <div class="hour"><div class="hour-label">20:00</div></div>
      <div class="hour"><div class="hour-label">21:00</div></div>
      <div class="hour"><div class="hour-label">22:00</div></div>
      <div class="hour"><div class="hour-label">23:00</div></div>
    </div>
  </div>

  <script>
    const events = __EVENTS__;

    function renderEvents() {
      const hoursDiv = document.getElementById("hours");
      const allDayDiv = document.getElementById("allDayEvents");
      const totalMinutes = 24 * 60;
      const hourHeight = hoursDiv.clientHeight || (window.innerHeight - 80);
      const pxPerMinute = hourHeight / totalMinutes;

      // remove old events
      [...document.querySelectorAll(".event")].forEach(e => e.remove());
      allDayDiv.innerHTML = "";

      events.forEach(ev => {
        if(ev.allDay) {
          const span = document.createElement("span");
          span.className = "all-day-event";
          span.textContent = ev.title;
          allDayDiv.appendChild(span);
        } else {
          const start = ev.startH * 60 + ev.startM;
          const end = ev.endH * 60 + ev.endM;

          const top = start * pxPerMinute;
          const height = Math.max((end - start) * pxPerMinute, 18);

          const div = document.createElement("div");
          div.className = "event";
          div.style.top = top + "px";
          div.style.height = height + "px";
          div.style.background = ev.color;
          div.innerHTML = ev.title + "<br>" +
                          String(ev.startH).padStart(2,"0") + ":" + String(ev.startM).padStart(2,"0") +
                          " - " +
                          String(ev.endH).padStart(2,"0") + ":" + String(ev.endM).padStart(2,"0");
          hoursDiv.appendChild(div);
        }
      });
    }

    window.addEventListener("resize", renderEvents);
    window.addEventListener("load", renderEvents);
    // call after a short delay in case webview sizing isn't immediate
    setTimeout(renderEvents, 120);
  </script>
</body>
</html>
"""

# ===========================
# Programmstart
# ===========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # optional: pass "Popup" as first arg to start popup mode
    mode = "Window"
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("popup", "--popup", "-popup"):
        mode = "Popup"
    w = PluginWidget(mode=mode)
    w.show()
    sys.exit(app.exec_())
