# scripts/pro_timer_html.py
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView

class PluginWidget(QMainWindow):
    def __init__(self, theme="light"):  # Default Light
        super().__init__()
        self.setWindowTitle("TIMER")
        self.resize(600, 400)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        # HTML UI
        self.html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    text-align: center;
                    transition: background 0.3s, color 0.3s;
                }
                h1 { margin-bottom: 20px; }
                #time {
                    font-size: 48px;
                    margin: 20px 0;
                }
                button {
                    margin: 5px;
                    padding: 10px 20px;
                    border-radius: 8px;
                    border: none;
                    font-size: 16px;
                    cursor: pointer;
                }
                ul { padding: 0; list-style: none; }

            </style>
        </head>
        <body class="light" id="bodyTag"> <!-- Default = light -->
            <h1>TIMER</h1>
            <div id="time">00:00:00</div>
            <button onclick="startStop()">Start</button>
            <button onclick="reset()">Reset</button>
            <button onclick="lap()">Runde</button>
            <ul id="laps"></ul>

            <script>
                let running = false;
                let startTime = 0;
                let elapsed = 0;
                let timer;

                function update() {
                    let now = Date.now();
                    elapsed = now - startTime;
                    let totalSec = Math.floor(elapsed / 1000);
                    let h = String(Math.floor(totalSec / 3600)).padStart(2,'0');
                    let m = String(Math.floor((totalSec % 3600) / 60)).padStart(2,'0');
                    let s = String(totalSec % 60).padStart(2,'0');
                    document.getElementById("time").textContent = h+":"+m+":"+s;
                }

                function startStop() {
                    if (!running) {
                        startTime = Date.now() - elapsed;
                        timer = setInterval(update, 200);
                        running = true;
                    } else {
                        clearInterval(timer);
                        running = false;
                    }
                }

                function reset() {
                    clearInterval(timer);
                    elapsed = 0;
                    document.getElementById("time").textContent = "00:00:00";
                    document.getElementById("laps").innerHTML = "";
                    running = false;
                }

                function lap() {
                    if (running) {
                        let li = document.createElement("li");
                        li.textContent = document.getElementById("time").textContent;
                        document.getElementById("laps").appendChild(li);
                    }
                }

                // JS Funktion zum Umschalten des Themes
                function switchTheme(mode) {
                    document.body.classList.remove("light","dark");
                    document.body.classList.add(mode);
                }
            </script>
        </body>
        </html>
        """

        self.browser.setHtml(self.html)

        # Theme gleich beim Start setzen
        self.set_theme(theme)

    def set_theme(self, theme: str):
        """Wechselt Light/Dark Mode im eingebetteten HTML"""
        js = f"switchTheme('{theme}');"
        self.browser.page().runJavaScript(js)
