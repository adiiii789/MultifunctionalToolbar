from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView


class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):  # Default Light
        super().__init__()
        self.setWindowTitle("Plugin")
        self.resize(600, 800)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        if mode == "Window":
            self.html = r"""
            <!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<title>Lights Out - Logikspiel</title>
<style>
  body {
    font-family: Arial, sans-serif;
    text-align: center;
    background: #222;
    color: #eee;
    margin: 0;
    padding: 40px 20px;
  }
  h1 {
    margin-bottom: 10px;
  }
  #grid {
    display: grid;
    grid-template-columns: repeat(5, 60px);
    grid-gap: 10px;
    justify-content: center;
    margin: 20px auto;
  }
  .cell {
    width: 60px;
    height: 60px;
    background: #444;
    border-radius: 12px;
    cursor: pointer;
    box-shadow: inset 0 0 15px #000;
    transition: background 0.25s ease;
  }
  .cell.on {
    background: #ffeb3b;
    box-shadow: 0 0 15px 4px #ffe600;
  }
  #message {
    margin-top: 25px;
    font-size: 20px;
  }
  #resetBtn {
    margin-top: 20px;
    padding: 10px 28px;
    font-size: 18px;
    background: #0288d1;
    border: none;
    border-radius: 14px;
    color: white;
    cursor: pointer;
    transition: background 0.2s;
  }
  #resetBtn:hover {
    background: #0277bd;
  }
</style>
</head>
<body>
  <h1>Lights Out</h1>
  <p>Klicke die Felder, um alle Lichter auszuschalten!</p>
  <div id="grid"></div>
  <button id="resetBtn">Neu starten</button>
  <div id="message"></div>

  <script>
    const gridSize = 5;
    const grid = document.getElementById('grid');
    const message = document.getElementById('message');
    const resetBtn = document.getElementById('resetBtn');

    // 5x5 Array mit zufälligen Zuständen (true=an, false=aus)
    let cells = [];

    function init() {
      cells = [];
      grid.innerHTML = '';
      message.textContent = '';

      for (let i = 0; i < gridSize * gridSize; i++) {
        const cell = document.createElement('div');
        cell.classList.add('cell');
        cell.dataset.index = i;
        // Zufällig an oder aus
        const on = Math.random() > 0.5;
        if (on) cell.classList.add('on');
        cells.push(on);

        cell.addEventListener('click', () => {
          toggle(i);
          updateGrid();
          if (checkWin()) {
            message.textContent = 'Gewonnen! 🎉';
          }
        });

        grid.appendChild(cell);
      }
    }

    // Schaltet das Feld i und seine Nachbarn um
    function toggle(i) {
      const toggleIndex = (idx) => {
        if (idx >= 0 && idx < cells.length) {
          cells[idx] = !cells[idx];
        }
      };

      toggleIndex(i);
      if (i % gridSize !== 0) toggleIndex(i - 1);       // links
      if ((i + 1) % gridSize !== 0) toggleIndex(i + 1); // rechts
      if (i - gridSize >= 0) toggleIndex(i - gridSize); // oben
      if (i + gridSize < cells.length) toggleIndex(i + gridSize); // unten
    }

    // Zeigt die aktuellen Zustände auf dem Grid an
    function updateGrid() {
      const gridCells = document.querySelectorAll('.cell');
      gridCells.forEach((cell, idx) => {
        if (cells[idx]) cell.classList.add('on');
        else cell.classList.remove('on');
      });
    }

    // Prüft ob alle auf aus sind
    function checkWin() {
      return cells.every(c => c === false);
    }

    resetBtn.addEventListener('click', () => {
      init();
    });

    // Initialisierung beim Laden
    init();
  </script>
</body>
</html>
            """
        elif mode == "Popup":
            self.html = r"""
        <!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plugin Hinweis</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #2E2E2E; /* dunkelgrau */
            font-family: Arial, sans-serif;
        }

        h1 {
            color: #FFFFFF; /* weiß */
            font-weight: bold;
            font-size: 2rem;
            text-align: center;
        }
    </style>
</head>
<body>
    <h1>Use this Plugin in the Main Window</h1>
</body>
</html>
            """
        self.browser.setHtml(self.html)