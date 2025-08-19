# scripts/pro_timer_html.py
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):  # Default Light
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
<html lang="de">
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <title>Timer & Countdown</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"> <!-- Wichtig für Responsive -->
  <style>
    body {
      font-family: 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #1a1a1a, #2c2c2c);
      color: #f5f5f5;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      overflow: hidden;
    }

    h1 {
      font-family: 'Consolas', monospace;
      font-size: 3rem;
      margin-bottom: 1.2rem;
      letter-spacing: 3px;
      color: #ffffff;
      text-shadow: 0 0 12px rgba(255, 100, 100, 0.4);
      text-align: center;
    }

    *:focus {
      outline: none;
      box-shadow: none;
    }

    /* Umschalter */
    .tabs {
      display: flex;
      gap: 12px;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
      justify-content: center;
    }

    .tab-btn {
      padding: 8px 18px;
      border: none;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.95rem;
      font-weight: 500;
      background: #333;
      color: #f5f5f5;
      transition: all 0.25s ease;
      flex: 1 1 auto;
      min-width: 100px;
    }

    .tab-btn.active {
      background: #00e0aa;
      color: #1a1a1a;
      box-shadow: 0 4px 12px rgba(0,224,170,0.5);
    }

    /* Container für beide Ansichten */
    .view-container {
      width: 90%;
      max-width: 400px;
      height: 320px;
      position: relative;
      overflow: hidden;
    }

    .views {
      display: flex;
      width: 200%;
      height: 100%;
      transition: transform 0.6s ease;
    }

    .view {
      width: 50%;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
    }

    .timer, .countdown {
      font-family: 'Consolas', monospace;
      font-size: 3rem;
      margin-bottom: 1.2rem;
      letter-spacing: 3px;
      color: #00e0aa;
      text-shadow: 0 0 12px rgba(0, 224, 170, 0.6);
      text-align: center;
    }

    .buttons {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: center;
    }

    button {
      padding: 10px 22px;
      border: none;
      border-radius: 999px;
      cursor: pointer;
      font-size: 1rem;
      font-weight: 500;
      background: #333;
      color: #f5f5f5;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      transition: all 0.25s ease;
      flex: 1 1 auto;
      min-width: 80px;
    }

    .start-btn { background: #2f3a32; }
    .stop-btn { background: #3a2f2f; }

    button:hover { transform: translateY(-2px); }

    .start-btn:hover {
      background: #00e0aa;
      color: #1a1a1a;
      box-shadow: 0 6px 14px rgba(0, 224, 170, 0.4);
    }
    .stop-btn:hover {
      background: #ff4d4d;
      color: #1a1a1a;
      box-shadow: 0 6px 14px rgba(255, 77, 77, 0.4);
    }

    /* Runden */
    .rounds {
      margin-top: 1.2rem;
      max-height: 150px;
      overflow-y: auto;
      width: 100%;
      max-width: 260px;
      font-size: 0.9rem;
    }
    .rounds p {
      margin: 0.3rem 0;
      padding: 0.3rem 0.6rem;
      border-radius: 6px;
      background: rgba(255,255,255,0.05);
    }

    /* Countdown Eingabe */
    .countdown-input {
      margin-bottom: 1rem;
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: center;
    }
    .countdown-input input {
      width: 60px;
      padding: 6px;
      text-align: center;
      border: none;
      border-radius: 6px;
      background: #444;
      color: #fff;
      font-size: 1rem;
    }

    /* 🔹 Responsive Anpassungen */
    @media (max-width: 500px) {
      h1 {
        font-size: 2rem;
      }
      .timer, .countdown {
        font-size: 2rem;
      }
      .view-container {
        height: auto;
        min-height: 250px;
      }
      button {
        font-size: 0.9rem;
        padding: 8px 16px;
      }
      .countdown-input input {
        width: 50px;
        font-size: 0.9rem;
      }
    }

    @media (max-width: 350px) {
      h1 {
        font-size: 1.5rem;
      }
      .timer, .countdown {
        font-size: 1.5rem;
      }
      button {
        min-width: 70px;
        font-size: 0.8rem;
        padding: 6px 12px;
      }
      .countdown-input input {
        width: 45px;
        font-size: 0.8rem;
      }
    }
  </style>
</head>

<body>
  <h1>Timer & Countdown</h1>
  <div class="tabs">
    <button class="tab-btn active" id="tabTimer">Timer</button>
    <button class="tab-btn" id="tabCountdown">Countdown</button>
  </div>

  <div class="view-container">
    <div class="views" id="views">
      <!-- Timer View -->
      <div class="view">
        <div class="timer" id="display">00:00:00.00</div>
        <div class="buttons">
          <button id="startStop" class="start-btn">Start</button>
          <button id="round">Runde</button>
          <button id="reset">Reset</button>
        </div>
        <div class="rounds" id="rounds"></div>
      </div>

      <!-- Countdown View -->
      <div class="view">
        <div class="countdown" id="countdownDisplay">00:00:00.00</div>
        <div class="countdown-input">
          <input type="number" id="hours" placeholder="HH" min="0">
          <input type="number" id="minutes" placeholder="MM" min="0" max="59">
          <input type="number" id="seconds" placeholder="SS" min="0" max="59">
        </div>
        <div class="buttons">
          <button id="cdStartStop" class="start-btn">Start</button>
          <button id="cdReset">Reset</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    /* Tab Switch */
    const tabTimer = document.getElementById("tabTimer");
    const tabCountdown = document.getElementById("tabCountdown");
    const views = document.getElementById("views");

    tabTimer.addEventListener("click", () => {
      views.style.transform = "translateX(0%)";
      tabTimer.classList.add("active");
      tabCountdown.classList.remove("active");
    });
    tabCountdown.addEventListener("click", () => {
      views.style.transform = "translateX(-50%)";
      tabCountdown.classList.add("active");
      tabTimer.classList.remove("active");
    });

    /* Timer Logic */
    let timer, running = false, elapsed = 0, rounds = [];
    const display = document.getElementById("display");
    const startStopBtn = document.getElementById("startStop");
    const roundBtn = document.getElementById("round");
    const resetBtn = document.getElementById("reset");
    const roundsDiv = document.getElementById("rounds");

    function updateDisplay() {
      let totalMilliseconds = elapsed;
      let totalSeconds = Math.floor(totalMilliseconds / 1000);
      let hours = String(Math.floor(totalSeconds / 3600)).padStart(2,'0');
      let minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2,'0');
      let seconds = String(totalSeconds % 60).padStart(2,'0');
      let ms = String(Math.floor((totalMilliseconds % 1000) / 10)).padStart(2,'0');
      display.textContent = `${hours}:${minutes}:${seconds}.${ms}`;
    }
    function startTimer() {
      let startTime = Date.now() - elapsed;
      timer = setInterval(() => {
        elapsed = Date.now() - startTime;
        updateDisplay();
      }, 10);
    }
    startStopBtn.addEventListener("click", () => {
      if (running) {
        clearInterval(timer);
        startStopBtn.textContent = "Start";
        startStopBtn.classList.remove("stop-btn"); startStopBtn.classList.add("start-btn");
      } else {
        startTimer();
        startStopBtn.textContent = "Stopp";
        startStopBtn.classList.remove("start-btn"); startStopBtn.classList.add("stop-btn");
      }
      running = !running;
    });
    roundBtn.addEventListener("click", () => {
      if (running) {
        let time = display.textContent;
        rounds.push(time);
        let p = document.createElement("p");
        p.textContent = `Runde ${rounds.length}: ${time}`;
        roundsDiv.appendChild(p);
      }
    });
    resetBtn.addEventListener("click", () => {
      clearInterval(timer);
      running = false;
      elapsed = 0;
      updateDisplay();
      startStopBtn.textContent = "Start";
      startStopBtn.classList.remove("stop-btn"); startStopBtn.classList.add("start-btn");
      rounds = [];
      roundsDiv.innerHTML = "";
    });
    updateDisplay();

    /* Countdown Logic */
    let cdTimer, cdRunning = false, cdRemaining = 0;
    const cdDisplay = document.getElementById("countdownDisplay");
    const cdStartStop = document.getElementById("cdStartStop");
    const cdReset = document.getElementById("cdReset");
    const inputH = document.getElementById("hours");
    const inputM = document.getElementById("minutes");
    const inputS = document.getElementById("seconds");

    function updateCountdownDisplay() {
      let totalMilliseconds = cdRemaining;
      let totalSeconds = Math.floor(totalMilliseconds / 1000);
      let hours = String(Math.floor(totalSeconds / 3600)).padStart(2,'0');
      let minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2,'0');
      let seconds = String(totalSeconds % 60).padStart(2,'0');
      let ms = String(Math.floor((totalMilliseconds % 1000) / 10)).padStart(2,'0');
      cdDisplay.textContent = `${hours}:${minutes}:${seconds}.${ms}`;
    }

    function startCountdown() {
      let endTime = Date.now() + cdRemaining;
      cdTimer = setInterval(() => {
        cdRemaining = endTime - Date.now();
        if (cdRemaining <= 0) {
          clearInterval(cdTimer);
          cdRemaining = 0;
          cdRunning = false;
          cdStartStop.textContent = "Start";
          cdStartStop.classList.remove("stop-btn"); cdStartStop.classList.add("start-btn");
        }
        updateCountdownDisplay();
      }, 10);
    }

    cdStartStop.addEventListener("click", () => {
      if (cdRunning) {
        clearInterval(cdTimer);
        cdRunning = false;
        cdStartStop.textContent = "Start";
        cdStartStop.classList.remove("stop-btn"); cdStartStop.classList.add("start-btn");
      } else {
        if (cdRemaining === 0) {
          let h = parseInt(inputH.value) || 0;
          let m = parseInt(inputM.value) || 0;
          let s = parseInt(inputS.value) || 0;
          cdRemaining = (h*3600 + m*60 + s) * 1000;
        }
        if (cdRemaining > 0) {
          startCountdown();
          cdRunning = true;
          cdStartStop.textContent = "Stopp";
          cdStartStop.classList.remove("start-btn"); cdStartStop.classList.add("stop-btn");
        }
      }
    });

    cdReset.addEventListener("click", () => {
      clearInterval(cdTimer);
      cdRunning = false;
      cdRemaining = 0;
      updateCountdownDisplay();
      cdStartStop.textContent = "Start";
      cdStartStop.classList.remove("stop-btn"); cdStartStop.classList.add("start-btn");
    });

    updateCountdownDisplay();
  </script>
</body>
</html>
        """

        self.browser.setHtml(self.html)