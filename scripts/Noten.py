from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEvent, QObject, pyqtSignal
import sys

# --- KONFIGURATION & THEMES ---

THEME_LIGHT = "light"
THEME_DARK = "dark"
SUPPORTED_THEMES = {THEME_LIGHT, THEME_DARK}


def _detect_host_theme(default=THEME_DARK):
    app = QApplication.instance()
    if app is not None:
        value = app.property("toolbar_theme")
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in SUPPORTED_THEMES:
                return lowered
    return default


class HostThemeWatcher(QObject):
    themeChanged = pyqtSignal(str)

    def __init__(self, app_instance):
        super().__init__(app_instance)
        self._app = app_instance
        if self._app is not None:
            self._app.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._app and event.type() == QEvent.DynamicPropertyChange:
            try:
                prop_name = event.propertyName().data().decode('utf-8')
            except Exception:
                prop_name = None
            if prop_name == "toolbar_theme":
                value = self._app.property("toolbar_theme")
                if isinstance(value, str):
                    self.themeChanged.emit(value.lower())
        return super().eventFilter(watched, event)

    def cleanup(self):
        if self._app is not None:
            try:
                self._app.removeEventFilter(self)
            except Exception:
                pass
            self._app = None


# --- CSS OVERRIDES & STYLING ---
THEME_OVERRIDE_CSS = """
<style>
/* Reset & Base */
* { box-shadow: none !important; outline: none; box-sizing: border-box; }
html, body { height: 100%; margin: 0; padding: 0; font-family: 'Segoe UI', Inter, sans-serif; overflow: hidden; }

/* VARIABLES */
body {
    --grade-excellent: #10b981; /* 1.0 - 1.5 & Bestanden */
    --grade-good: #3b82f6;      /* 1.6 - 2.5 */
    --grade-ok: #f59e0b;        /* 2.6 - 3.5 */
    --grade-bad: #ef4444;       /* 3.6 - 5.0 */
    --card-radius: 12px;
}

/* DARK THEME */
body.theme-dark {
  background: #1e1e1e !important;
  color: #e0e0e0 !important;
  --bg-color: #1e1e1e;
  --sidebar-bg: #252526;
  --card-bg: #2d2d2d;
  --input-bg: #3c3c3c;
  --border-color: #3e3e42;
  --text-main: #e0e0e0;
  --text-muted: #858585;
  --hover-bg: #3e3e42;
}

/* LIGHT THEME */
body.theme-light {
  background: #f3f4f6 !important;
  color: #1f2937 !important;
  --bg-color: #f3f4f6;
  --sidebar-bg: #ffffff;
  --card-bg: #ffffff;
  --input-bg: #f9fafb;
  --border-color: #e5e7eb;
  --text-main: #1f2937;
  --text-muted: #6b7280;
  --hover-bg: #f3f4f6;
}

/* LAYOUT */
.app-layout { display: flex; height: 100vh; width: 100%; }

/* SIDEBAR */
.sidebar {
    width: 260px; background: var(--sidebar-bg); border-right: 1px solid var(--border-color);
    display: flex; flex-direction: column; padding: 20px; flex-shrink: 0;
}
.sidebar h1 { margin: 0 0 20px 0; font-size: 20px; font-weight: 700; color: var(--text-main); }
.stats-container { display: flex; flex-direction: column; gap: 15px; }

.stat-card {
    background: var(--card-bg); border: 1px solid var(--border-color);
    padding: 15px; border-radius: var(--card-radius); text-align: center;
}
.stat-value { font-size: 32px; font-weight: 800; margin-bottom: 5px; }
.stat-label { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); }

/* CHART AREA IN SIDEBAR - FIXED */
.chart-container {
    margin-top: 30px; flex: 1; display: flex; flex-direction: column; justify-content: flex-end;
}
.chart-title { font-size: 12px; color: var(--text-muted); margin-bottom: 10px; text-align: center; }
.bars-wrapper {
    display: flex; align-items: flex-end; justify-content: space-between; 
    height: 150px; gap: 4px; padding-bottom: 5px; border-bottom: 1px solid var(--border-color);
}
.bar-col { 
    display: flex; flex-direction: column; align-items: center; justify-content: flex-end;
    flex: 1; height: 100%; 
}
.bar {
    width: 100%; min-width: 8px; border-radius: 4px 4px 0 0; 
    transition: height 0.5s ease; opacity: 0.8;
}
.bar:hover { opacity: 1; }
.bar-label { font-size: 10px; color: var(--text-muted); margin-top: 4px; }


/* MAIN CONTENT */
.main { flex: 1; display: flex; flex-direction: column; padding: 20px 40px; overflow-y: auto; }

/* INPUT FORM */
.add-form {
    display: grid; grid-template-columns: 2fr 1fr 1fr 1fr auto; gap: 10px;
    background: var(--card-bg); padding: 15px; border-radius: var(--card-radius);
    margin-bottom: 30px; border: 1px solid var(--border-color); align-items: center;
}
input, select {
    background: var(--input-bg); border: 1px solid var(--border-color); color: var(--text-main);
    padding: 10px; border-radius: 6px; font-size: 14px; width: 100%;
}
.btn-add {
    background: var(--text-main); color: var(--bg-color); border: none; 
    padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer;
    transition: opacity 0.2s;
}
.btn-add:hover { opacity: 0.9; }

/* SEMESTER LISTS */
.semester-block { margin-bottom: 30px; animation: fadeIn 0.3s ease; }
.sem-header {
    display: flex; justify-content: space-between; align-items: flex-end; 
    margin-bottom: 10px; padding: 0 5px; border-bottom: 2px solid var(--border-color); padding-bottom: 5px;
}
.sem-title { font-size: 18px; font-weight: bold; color: var(--text-main); }
.sem-stats { font-size: 14px; color: var(--text-muted); }
.sem-avg-badge {
    background: var(--input-bg); padding: 2px 8px; border-radius: 4px; 
    font-weight: bold; margin-left: 10px; color: var(--text-main);
}

.table-container {
    background: var(--card-bg); border-radius: var(--card-radius); 
    border: 1px solid var(--border-color); overflow: hidden;
}
.row {
    display: grid; grid-template-columns: 3fr 1fr 1fr 40px; 
    padding: 12px 15px; align-items: center; border-bottom: 1px solid var(--border-color);
}
.row:last-child { border-bottom: none; }
.row-header { background: var(--hover-bg); font-size: 12px; font-weight: bold; color: var(--text-muted); text-transform: uppercase; }

.cell-name { font-weight: 500; }
.cell-grade { font-weight: bold; }
.cell-credits { color: var(--text-muted); }

/* Editierbare Felder Styling */
[contenteditable]:hover { background: var(--input-bg); cursor: text; border-radius: 4px; padding: 0 4px; }
[contenteditable]:focus { background: var(--input-bg); border-bottom: 2px solid var(--text-main); }

.btn-del {
    background: transparent; border: none; color: var(--text-muted); 
    cursor: pointer; font-size: 18px; display: flex; justify-content: center;
}
.btn-del:hover { color: #ef4444; }

/* Helper Classes for Colors */
.color-exc { color: var(--grade-excellent); }
.color-good { color: var(--grade-good); }
.color-ok { color: var(--grade-ok); }
.color-bad { color: var(--grade-bad); }

@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

</style>
"""

THEME_SCRIPT = """
<script>
(function () {
  window.applyTheme = function(theme) {
    var normalized = (theme === 'light') ? 'theme-light' : 'theme-dark';
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(normalized);
  };
})();
</script>
"""


class PluginWidget(QMainWindow):
    def __init__(self, theme="dark", mode="Window"):
        super().__init__()
        self.setWindowTitle("Grade Manager Pro")
        self.resize(1100, 750)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        normalized_theme = theme.lower()
        host_theme = _detect_host_theme(normalized_theme if normalized_theme in SUPPORTED_THEMES else THEME_DARK)
        self._current_theme = host_theme if host_theme in SUPPORTED_THEMES else THEME_DARK

        body_class = f"theme-{self._current_theme}"
        html = self._build_html(body_class)
        self.browser.setHtml(html, QUrl("http://localhost/"))

        self._view_ready = False
        self.browser.loadFinished.connect(self._on_view_ready)

        app_instance = QApplication.instance()
        if app_instance is not None:
            self._theme_watcher = HostThemeWatcher(app_instance)
            self._theme_watcher.themeChanged.connect(self._on_host_theme_changed)

    def _build_html(self, body_class):
        return """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<title>Grade Manager</title>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">

<div class="app-layout">

    <div class="sidebar">
        <h1>Notenübersicht</h1>

        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-value" id="totalGPA">-</div>
                <div class="stat-label">Gesamtschnitt</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="totalCP" style="font-size:24px;">0</div>
                <div class="stat-label">Total Credits (ECTS)</div>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Verlauf (Ø pro Semester)</div>
            <div class="bars-wrapper" id="chartBars">
                </div>
        </div>
    </div>

    <div class="main">

        <div class="add-form">
            <input id="inSubject" placeholder="Fachname (z.B. Mathe 1)" />
            <input id="inGrade" type="text" placeholder="Note (z.B. 2.3 oder 'b')" />
            <input id="inCP" type="number" step="0.5" placeholder="Credits (z.B. 5)" />
            <input id="inSem" type="number" placeholder="Semester (z.B. 1)" />
            <button class="btn-add" onclick="addSubject()">Hinzufügen</button>
        </div>

        <div id="semesterLists"></div>

    </div>
</div>

<script>
const KEY = 'grade_manager_data_v2';
let subjects = [];

/* --- DATA LOGIC --- */
function load() {
    const raw = localStorage.getItem(KEY);
    if (raw) {
        subjects = JSON.parse(raw);
    } else {
        // Beispiel-Daten
        subjects = [
            { id: '1', name: 'Einführung Programmieren', grade: 1.3, cp: 5, sem: 1 },
            { id: '2', name: 'Praxisprojekt', grade: 'b', cp: 10, sem: 2 }, 
            { id: '3', name: 'Datenbanken', grade: 2.7, cp: 5, sem: 1 }
        ];
        save();
    }
    render();
}

function save() {
    localStorage.setItem(KEY, JSON.stringify(subjects));
    render();
}

function addSubject() {
    const name = document.getElementById('inSubject').value.trim();
    const gradeRaw = document.getElementById('inGrade').value.trim();
    const cpVal = document.getElementById('inCP').value;
    const semVal = document.getElementById('inSem').value;

    if (!name || !gradeRaw || !cpVal || !semVal) {
        alert("Bitte alle Felder ausfüllen!");
        return;
    }

    let gradeToStore;
    if (gradeRaw.toLowerCase() === 'b') {
        gradeToStore = 'b';
    } else {
        gradeToStore = parseFloat(gradeRaw.replace(',', '.'));
        if (isNaN(gradeToStore)) {
            alert("Bitte eine gültige Zahl oder 'b' eingeben.");
            return;
        }
    }

    subjects.push({
        id: Date.now().toString(),
        name: name,
        grade: gradeToStore,
        cp: parseFloat(cpVal),
        sem: parseInt(semVal)
    });

    document.getElementById('inSubject').value = '';
    document.getElementById('inGrade').value = '';
    document.getElementById('inCP').value = '';

    save();
}

function deleteSubject(id) {
    if(confirm("Fach wirklich löschen?")) {
        subjects = subjects.filter(s => s.id !== id);
        save();
    }
}

function updateSubject(id, field, value) {
    const s = subjects.find(x => x.id === id);
    if (!s) return;

    value = value.trim();

    if (field === 'name') {
        s.name = value;
    } else if (field === 'grade') {
        if (value.toLowerCase() === 'b') {
            s.grade = 'b';
        } else {
            const parsed = parseFloat(value.replace(',', '.'));
            if (!isNaN(parsed)) s.grade = parsed;
        }
    } else {
        const parsed = parseFloat(value);
        if (!isNaN(parsed)) s[field] = parsed;
    }

    save();
}

/* --- HELPER --- */
function getColorClass(grade) {
    if (grade === 'b') return 'color-exc';
    if (grade <= 1.5) return 'color-exc';
    if (grade <= 2.5) return 'color-good';
    if (grade <= 3.5) return 'color-ok';
    return 'color-bad';
}

function calculateAverage(subs) {
    let totalGradePoints = 0;
    let countedCP = 0;

    subs.forEach(s => {
        if (s.grade === 'b') return; 
        totalGradePoints += (s.grade * s.cp);
        countedCP += s.cp;
    });

    return countedCP === 0 ? null : (totalGradePoints / countedCP);
}

/* --- RENDER --- */
function render() {
    const container = document.getElementById('semesterLists');
    container.innerHTML = '';

    const semMap = {};
    subjects.forEach(s => {
        if (!semMap[s.sem]) semMap[s.sem] = [];
        semMap[s.sem].push(s);
    });

    const semesters = Object.keys(semMap).map(Number).sort((a,b) => a - b);
    const chartData = [];

    semesters.forEach(sem => {
        const semSubjects = semMap[sem];

        const semAvg = calculateAverage(semSubjects);
        const semTotalCP = semSubjects.reduce((acc, cur) => acc + cur.cp, 0);

        if (semAvg !== null) {
            chartData.push({ sem: sem, avg: semAvg });
        }

        const block = document.createElement('div');
        block.className = 'semester-block';

        const avgDisplay = semAvg !== null ? `Ø ${semAvg.toFixed(2)}` : 'N/A';
        const avgColor = semAvg !== null ? getColorClass(semAvg) : '';

        block.innerHTML = `
            <div class="sem-header">
                <div class="sem-title">Semester ${sem} 
                    ${semAvg !== null ? `<span class="sem-avg-badge ${avgColor}">${avgDisplay}</span>` : ''}
                </div>
                <div class="sem-stats">${semTotalCP} Credits</div>
            </div>
            <div class="table-container">
                <div class="row row-header">
                    <div>Fach</div>
                    <div>Note</div>
                    <div>Credits</div>
                    <div></div>
                </div>
                <div id="rows-${sem}"></div>
            </div>
        `;
        container.appendChild(block);

        const rowsContainer = block.querySelector(`#rows-${sem}`);
        semSubjects.forEach(s => {
            const r = document.createElement('div');
            r.className = 'row';

            let gradeDisplay = s.grade === 'b' ? 'B' : s.grade;
            let gColor = getColorClass(s.grade);

            r.innerHTML = `
                <div class="cell-name" contenteditable="true" onblur="updateSubject('${s.id}', 'name', this.innerText)">${s.name}</div>
                <div class="cell-grade ${gColor}" contenteditable="true" onblur="updateSubject('${s.id}', 'grade', this.innerText)">${gradeDisplay}</div>
                <div class="cell-credits" contenteditable="true" onblur="updateSubject('${s.id}', 'cp', this.innerText)">${s.cp}</div>
                <button class="btn-del" onclick="deleteSubject('${s.id}')">×</button>
            `;
            rowsContainer.appendChild(r);
        });
    });

    const totalAvg = calculateAverage(subjects);
    const totalCredits = subjects.reduce((acc, cur) => acc + cur.cp, 0);

    const totalEl = document.getElementById('totalGPA');
    if (totalAvg !== null) {
        totalEl.innerText = totalAvg.toFixed(2);
        totalEl.className = 'stat-value ' + getColorClass(totalAvg);
    } else {
        totalEl.innerText = '-';
        totalEl.className = 'stat-value';
    }

    document.getElementById('totalCP').innerText = totalCredits;

    renderChart(chartData);
}

function renderChart(data) {
    const wrapper = document.getElementById('chartBars');
    wrapper.innerHTML = '';

    if (data.length === 0) return;

    data.forEach(d => {
        const col = document.createElement('div');
        col.className = 'bar-col';

        let pct = ((5 - d.avg) / 4) * 100;
        if (pct < 5) pct = 5; 
        if (pct > 100) pct = 100;

        const colorVar = d.avg <= 1.5 ? 'var(--grade-excellent)' :
                         d.avg <= 2.5 ? 'var(--grade-good)' :
                         d.avg <= 3.5 ? 'var(--grade-ok)' : 'var(--grade-bad)';

        col.innerHTML = `
            <div class="bar" style="height:${pct}%; background:${colorVar};" title="Ø ${d.avg.toFixed(2)}"></div>
            <div class="bar-label">S${d.sem}</div>
        `;
        wrapper.appendChild(col);
    });
}

document.getElementById('inSem').addEventListener('keydown', (e) => {
    if(e.key === 'Enter') addSubject();
});

load();
</script>
</body>
</html>
""".replace("__BODY_CLASS__", body_class)

    def _on_view_ready(self, ok: bool):
        self._view_ready = bool(ok)
        if ok:
            self._apply_theme(self._current_theme)

    def _apply_theme(self, theme: str):
        if not self._view_ready: return
        script = f'window.applyTheme && window.applyTheme("{theme}")'
        self.browser.page().runJavaScript(script)

    def _on_host_theme_changed(self, theme: str):
        normalized = theme if theme in SUPPORTED_THEMES else THEME_DARK
        self._current_theme = normalized
        self._apply_theme(normalized)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setProperty("toolbar_theme", "dark")
    window = PluginWidget(theme="dark")
    window.show()
    sys.exit(app.exec_())