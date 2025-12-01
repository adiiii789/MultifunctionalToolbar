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
<html lang="de" class="theme-dark"> <head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ultimate Coffee Pomodoro Timer</title>
  <style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
    /* --- 1. CSS-Variablen (Themes & Basis) --- */
    :root {
      --font-main: 'Poppins', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      /* Basis-Timing */
      --timing-fast: 0.2s;
      --timing-med: 0.4s;
    }

    /* Theme "Dark Roast" (Standard) */
    :root.theme-dark {
      --color-bg: #2e2118;
      --color-bg-gradient: radial-gradient(ellipse at center, #413023 0%, #2e2118 100%);
      --color-text-primary: #f3eada;
      --color-text-secondary: #f6d6ad;
      --color-container-bg: rgba(46, 33, 24, 0.75);
      --color-container-border: rgba(243, 234, 218, 0.15);
      --color-container-shadow: rgba(18, 12, 7, 0.37);
      
      --color-machine-body: #505050;
      --color-machine-accent: #333;
      --color-machine-shine: #777;
      --color-machine-base: #222;
      --color-brew-light-off: #333;
      --color-brew-light-on: #4eff81;
      
      --color-cup-border: #6b4c3b;
      --color-cup-bg: #221a14;
      --color-cup-shine: rgba(255, 255, 255, 0.05);

      --color-coffee-dark: #6d4a2f;
      --color-coffee-mid: #8b5e3c;
      --color-coffee-light: #a1703a;

      --color-btn-primary: #6b4c3b;
      --color-btn-primary-shadow: #4b2e0e;
      --color-btn-primary-hover: #8b6a4f;
      --color-btn-secondary: #5a5a5a;
      --color-btn-secondary-shadow: #333;
      --color-btn-secondary-hover: #777;
      
      --color-settings-bg: #36271b;
      --color-settings-border: #6b4c3b;
      --color-settings-input-bg: #2e2118;

      --color-broken-main: #b44f4f;
      --color-broken-shadow: #721a1a;
      --color-broken-glow: #ff4d4d;
    }

    /* Theme "Light Roast" */
    :root.theme-light {
      --color-bg: #f4f0e9;
      --color-bg-gradient: radial-gradient(ellipse at center, #ffffff 0%, #f4f0e9 100%);
      --color-text-primary: #3d2c1f;
      --color-text-secondary: #6b4c3b;
      --color-container-bg: rgba(255, 255, 255, 0.75);
      --color-container-border: rgba(61, 44, 31, 0.15);
      --color-container-shadow: rgba(61, 44, 31, 0.15);
      
      --color-machine-body: #c0c0c0;
      --color-machine-accent: #9e9e9e;
      --color-machine-shine: #f0f0f0;
      --color-machine-base: #777;
      --color-brew-light-off: #a0a0a0;
      --color-brew-light-on: #00e05a;
      
      --color-cup-border: #bcaaa4;
      --color-cup-bg: #ffffff;
      --color-cup-shine: rgba(0, 0, 0, 0.03);

      --color-coffee-dark: #6d4a2f;
      --color-coffee-mid: #8b5e3c;
      --color-coffee-light: #a1703a;

      --color-btn-primary: #8d6e63;
      --color-btn-primary-shadow: #5f4339;
      --color-btn-primary-hover: #a1887f;
      --color-btn-secondary: #9e9e9e;
      --color-btn-secondary-shadow: #707070;
      --color-btn-secondary-hover: #b0b0b0;
      
      --color-settings-bg: #fdfaf6;
      --color-settings-border: #d7ccc8;
      --color-settings-input-bg: #f4f0e9;

      --color-broken-main: #d32f2f;
      --color-broken-shadow: #9a0007;
      --color-broken-glow: #ff6659;
    }

    /* --- 2. Grund-Layout & Body --- */
    *, *::before, *::after {
      box-sizing: border-box;
    }

    body {
      background: var(--color-bg);
      background-image: var(--color-bg-gradient);
      color: var(--color-text-primary);
      font-family: var(--font-main);
      margin: 0;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-direction: column;
      padding: 20px;
      transition: background var(--timing-med), color var(--timing-med);
      overflow-x: hidden;
    }

    /* Subtile Hintergrund-Partikel */
    .particles {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: -1;
      pointer-events: none;
    }
    .particle {
      position: absolute;
      background: var(--color-text-secondary);
      border-radius: 50%;
      opacity: 0;
      animation: floatUp 20s infinite linear;
    }
    .particle:nth-child(1) { width: 5px; height: 5px; left: 10%; animation-duration: 15s;
      animation-delay: 1s; }
    .particle:nth-child(2) { width: 3px; height: 3px; left: 30%; animation-duration: 25s; animation-delay: 5s;
    }
    .particle:nth-child(3) { width: 6px; height: 6px; left: 50%; animation-duration: 18s; animation-delay: 3s;
    }
    .particle:nth-child(4) { width: 4px; height: 4px; left: 70%; animation-duration: 22s; animation-delay: 8s;
    }
    .particle:nth-child(5) { width: 3px; height: 3px; left: 90%; animation-duration: 30s; animation-delay: 2s;
    }
    
    @keyframes floatUp {
      0% { transform: translateY(100vh) translateX(0);
      opacity: 0; }
      10% { opacity: 0.1;
      }
      90% { opacity: 0.05;
      }
      100% { transform: translateY(-10vh) translateX(20px); opacity: 0;
      }
    }

    /* --- 3. Haupt-Container --- */
    .container {
      background: var(--color-container-bg);
      border: 1px solid var(--color-container-border);
      border-radius: 24px;
      padding: 30px 40px;
      box-shadow: 0 8px 32px 0 var(--color-container-shadow);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      max-width: 420px;
      width: 100%;
      text-align: center;
      position: relative;
      z-index: 10;
      transition: background var(--timing-med), border var(--timing-med), box-shadow var(--timing-med);
    }
    
    /* --- 4. Kaffeemaschine (Redesign Level 3) --- */
    .coffee-machine {
      margin: 0 auto 10px auto;
      width: 150px; /* Breiter */
      height: 160px;
      position: relative;
      z-index: 10;
      /* Maschine ist auf Ebene 10 */
      filter: drop-shadow(0 4px 5px rgba(0,0,0,0.3));
    }
    
    /* Maschinen-Kopf (integrierter Deckel) */
    .machine-head {
      width: 100%;
      height: 40px;
      position: absolute;
      top: 0;
      background: linear-gradient(to right, var(--color-machine-accent) 0%, var(--color-machine-body) 20%, var(--color-machine-shine) 50%, var(--color-machine-body) 80%, var(--color-machine-accent) 100%);
      border-radius: 16px 16px 0 0;
      border: 2px solid var(--color-machine-accent);
      border-bottom: none;
      box-shadow: inset 0 2px 4px rgba(255,255,255,0.1);
    }
    /* Glanz-Effekt */
    .machine-head::after {
      content: '';
      position: absolute;
      top: 4px;
      left: 10%;
      width: 80%;
      height: 4px;
      background: rgba(255,255,255,0.2);
      border-radius: 2px;
    }
    
    /* Maschinen-Körper */
    .machine-body {
      width: 140px;
      /* Schmaler als Kopf */
      height: 120px;
      position: absolute;
      top: 40px;
      /* Direkt unter Kopf */
      left: 5px;
      background: var(--color-machine-body);
      border-left: 2px solid var(--color-machine-accent);
      border-right: 2px solid var(--color-machine-accent);
    }

    /* Wassertank (Pseudo-Element) */
    .machine-body::before {
      content: '';
      position: absolute;
      top: 10px;
      right: 10px;
      width: 30px;
      height: 80px;
      background: rgba(180, 210, 255, 0.2);
      border: 2px solid rgba(255,255,255,0.1);
      border-radius: 4px;
      box-shadow: inset 0 1px 3px rgba(0,0,0,0.2);
    }
    
    /* Maschinen-Basis */
    .machine-base {
      width: 100%;
      height: 20px;
      background: var(--color-machine-base);
      position: absolute;
      bottom: -18px; /* Überlappt mit Körper */
      border-radius: 0 0 12px 12px;
      border: 2px solid var(--color-machine-base);
      box-shadow: 0 4px 0 #111;
    }

    /* "Brühlicht" */
    .brew-light {
      width: 12px;
      height: 12px;
      background: var(--color-brew-light-off);
      border-radius: 50%;
      position: absolute;
      bottom: 15px;
      left: 15px;
      border: 2px solid #222;
      transition: background 0.3s, box-shadow 0.3s;
    }

    /* Maschinen-Ausguss */
    .machine-spout {
      width: 24px;
      height: 30px; /* Kürzer */
      background: var(--color-machine-accent);
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      bottom: -10px;
      /* Hängt aus dem Körper */
      border-radius: 0 0 8px 8px;
      z-index: 14;
      /* Tülle ist auf Ebene 14 */
      border: 2px solid #222;
    }
    
    /* Maschinen-Dampf */
    .machine-steam {
      pointer-events: none;
      position: absolute; left: 50%; top: -10px; width: 36px; height: 32px; opacity: 0.8; z-index: 4; display: none; transform: translateX(-50%);
    }
    .machine-steam-cloud {
      position: absolute; width: 10px; height: 20px; left: 0;
      border-radius: 10px 10px 13px 13px / 12px 12px 16px 16px; background: linear-gradient(180deg, #fff 60%, #ffffff3a 100%); opacity: 0.75;
      animation: steamUp 2.2s infinite; filter: blur(0.5px);
    }
    .machine-steam-cloud:nth-child(2) { left: 13px; width: 8px; height: 14px; opacity: 0.55;
      animation: steamUp 2s 1s infinite; }
    .machine-steam-cloud:nth-child(3) { left: 23px; width: 7px; height: 11px; opacity: 0.38;
      animation: steamUp 2.3s 0.4s infinite; }
    
    @keyframes steamUp {
      0% { transform: translateY(0) scale(1);
      opacity: 0.7;}
      100% { transform: translateY(-20px) scale(1.1);
      opacity: 0;}
    }

    /* --- 5. "Maschine arbeitet"-Zustände --- */
    .coffee-machine.is-working .machine-body {
      animation: machineVibrate 0.18s infinite linear;
    }
    .coffee-machine.is-working .brew-light {
      background: var(--color-brew-light-on);
      box-shadow: 0 0 10px 2px var(--color-brew-light-on), inset 0 0 2px #fff;
      animation: pulse 1s infinite;
    }
    .coffee-machine.is-working .machine-steam {
      display: block;
    }
    
    @keyframes machineVibrate {
      0%{transform: translateX(0) translateY(0);} 18%{transform: translateX(1px) translateY(-1px);} 31%{transform: translateX(-1px) translateY(1px);} 50%{transform: translateX(0.7px) translateY(0);} 62%{transform: translateX(-1px) translateY(-1px);} 100% {transform: translateX(0) translateY(0);}
    }
    @keyframes pulse {
      0% { opacity: 1;
      } 50% { opacity: 0.6; } 100% { opacity: 1;
      }
    }
    
    /* --- 6. Kaffeetasse & Füllung (L3 Wellen) --- */
    .coffee-cup {
      margin: 40px auto 10px auto;
      /* Mehr Abstand zur Maschine */
      width: 100px;
      height: 90px;
      border: 4px solid var(--color-cup-border);
      border-radius: 0 0 50px 50px;
      position: relative;
      overflow: hidden;
      background: var(--color-cup-bg);
      box-sizing: border-box;
      z-index: 5;
      /* Tasse ist auf Ebene 5 */
      box-shadow: 0 4px 8px rgba(0,0,0,0.2), inset 0 3px 5px rgba(0,0,0,0.3);
      transition: border var(--timing-med), background var(--timing-med);
    }
    /* Tassen-Glanz */
    .coffee-cup::after {
      content: '';
      position: absolute;
      top: 5px;
      left: 5px;
      width: 86px;
      height: 40px;
      border-radius: 0 0 40px 40px;
      background: var(--color-cup-shine);
      transform: rotate(10deg);
      transition: background var(--timing-med);
    }
    .coffee-handle {
      position: absolute;
      left: 94px;
      top: 30px;
      width: 22px;
      height: 36px;
      border: 4px solid var(--color-cup-border);
      border-radius: 40px 40px 60px 20px / 40px 40px 60px 20px;
      background: transparent;
      z-index: 2;
      transition: border var(--timing-med);
    }

    /* Der Füll-Container */
    .coffee-fill {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      background: var(--color-coffee-dark);
      /* NEU: Transition geändert für sanfteres Füllen/Leeren */
      transition: height 0.5s cubic-bezier(0.36, 0.58, 0.2, 0.9);
      z-index: 1;
      overflow: hidden;
      /* Wichtig für clip-path */
    }

    /* Die "schwappende" Oberfläche */
    .coffee-fill::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: var(--color-coffee-mid);
      z-index: 2;
      animation: wave 8s infinite linear;
    }
    
    @keyframes wave {
      0% {
        clip-path: polygon(
          0% 100%, 100% 100%, 100% 10%, 
          80% 8%, 60% 10%, 40% 12%, 20% 10%, 
          0% 8%
        );
      }
      50% {
        clip-path: polygon(
          0% 100%, 100% 100%, 100% 8%, 
          80% 10%, 60% 12%, 40% 10%, 20% 8%, 
          0% 10%
        );
      }
      100% {
        clip-path: polygon(
          0% 100%, 100% 100%, 100% 10%, 
          80% 8%, 60% 10%, 40% 12%, 20% 10%, 
          0% 8%
        );
      }
    }
    
    /* Tassen-Dampf */
    .coffee-steam {
      pointer-events: none;
      position: absolute; left: 50%; top: -24px; transform: translateX(-50%); width: 40px; height: 32px; opacity: 0.65; z-index: 4; display: none;
    }
    .steam-cloud {
      position: absolute; width: 16px; height: 22px; left: 0;
      border-radius: 9px 9px 13px 13px / 12px 12px 16px 16px; background: linear-gradient(180deg, #fff 60%, #ffffff33 100%); opacity: 0.75;
      animation: steamUp 2.2s infinite; filter: blur(0.5px);
    }
    .steam-cloud:nth-child(2) { left: 16px; width: 12px; height: 17px; opacity: 0.48;
      animation: steamUp 2.1s 0.9s infinite; }
    .steam-cloud:nth-child(3) { left: 24px; width: 10px; height: 14px; opacity: 0.4;
      animation: steamUp 2.5s 0.5s infinite; }

    /* --- 7. Kaffeestrahl (Dynamisch, L3) --- */
    
    /* ***** FIX 1 HIER: z-index auf 99 gesetzt, um Überdeckung zu vermeiden ***** */
    .coffee-stream {
      position: absolute;
      width: 8px; /* Dünner */
      left: 50%;
      /* JS setzt genaue Position */
      top: 0;
      /* JS setzt Position */
      height: 0;
      /* JS setzt Höhe */
      background: linear-gradient(to bottom, var(--color-coffee-light), var(--color-coffee-mid), var(--color-coffee-light));
      background-size: 100% 15px;
      border-radius: 4px;
      z-index: 99; /* HÖCHSTE EBENE */
      display: none;
      /* JS steuert */
      animation: stream-flow 0.3s linear infinite;
    }
    
    @keyframes stream-flow {
      0% { background-position: 0 0;
      }
      100% { background-position: 0 15px;
      }
    }

    /* Tropfen-Animation */
    /* ***** FIX 1 HIER: z-index auf 99 gesetzt, um Überdeckung zu vermeiden ***** */
    .coffee-drip {
      position: absolute;
      width: 6px;
      height: 10px;
      background: var(--color-coffee-mid);
      border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
      z-index: 99;
      /* HÖCHSTE EBENE */
      display: none;
      /* JS steuert */
      transform: scaleY(0.8);
    }
    .coffee-drip.is-dripping {
      display: block;
      animation: drip 0.5s ease-in forwards;
    }
    @keyframes drip {
      0% { transform: translateY(0) scaleY(0.8); opacity: 1;
      }
      80% { opacity: 1;
      }
      100% { transform: translateY(40px) scaleY(1.2); opacity: 0;
      }
    }

    /* --- 8. UI-Elemente (Timer, Status, Zyklen) --- */
    #timerDisplay {
      font-size: 3.2rem;
      font-weight: 700;
      margin: 10px 0;
      color: var(--color-text-primary);
      text-shadow: 0 2px 4px rgba(0,0,0,0.2);
      transition: color var(--timing-med);
    }
    .status {
      margin: 0 0 10px 0;
      font-weight: 600;
      min-height: 24px;
      color: var(--color-text-secondary);
      font-size: 1.1rem;
      transition: color var(--timing-med);
    }
    .cycle-tracker {
      margin: 10px 0;
    }
    .cycle-dot {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--color-cup-bg);
      border: 1px solid var(--color-cup-border);
      margin: 0 4px;
      transition: background 0.3s, border 0.3s;
    }
    .cycle-dot.filled {
      background: var(--color-text-secondary);
    }

    /* --- 9. Tasten (3D-Stil) --- */
    .button-group {
      margin-top: 10px;
    }
    button {
      background: var(--color-btn-primary);
      color: var(--color-text-primary);
      border: none;
      border-radius: 8px;
      padding: 12px 22px;
      font-size: 18px;
      font-family: var(--font-main);
      font-weight: 600;
      cursor: pointer;
      margin: 7px 6px 0 6px;
      box-shadow: 0 4px 0 var(--color-btn-primary-shadow);
      transition: background 0.2s, box-shadow 0.1s, transform 0.1s, color var(--timing-med);
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      background: #5b4735;
      box-shadow: 0 4px 0 #413226;
      transform: translateY(0) !important;
    }
    button:hover:enabled {
      background: var(--color-btn-primary-hover);
      transform: scale(1.03);
    }
    button:active:enabled {
      transform: translateY(2px) scale(0.98);
      box-shadow: 0 2px 0 var(--color-btn-primary-shadow);
    }

    /* Spezielle Tasten */
    #resetBtn, #settingsBtn, #muteBtn {
      background: var(--color-btn-secondary);
      box-shadow: 0 4px 0 var(--color-btn-secondary-shadow);
    }
    #resetBtn:hover:enabled, #settingsBtn:hover:enabled, #muteBtn:hover:enabled { background: var(--color-btn-secondary-hover);
    }
    #resetBtn:active:enabled, #settingsBtn:active:enabled, #muteBtn:active:enabled { box-shadow: 0 2px 0 var(--color-btn-secondary-shadow);
    }
    
    #repairBtn {
      background: var(--color-broken-main);
      box-shadow: 0 4px 0 var(--color-broken-shadow);
      border: none; color: #fff; display: none;
    }
    
    /* Icon-Tasten (SVG-Icons) */
    .icon-button {
      padding: 10px 12px;
    }
    .icon-button svg {
      width: 20px;
      height: 20px;
      fill: var(--color-text-primary);
      vertical-align: middle;
      pointer-events: none; /* Wichtig, damit Klick auf Button geht */
    }

    /* --- 10. "Kaputt"-Zustand --- */
    .coffee-machine.broken .machine-head,
    .coffee-machine.broken .machine-body {
      background: var(--color-broken-main);
      animation: shake 0.5s infinite;
      border-color: var(--color-broken-shadow);
    }
    .coffee-machine.broken .machine-head {
      box-shadow: 0 0 25px 10px var(--color-broken-glow), inset 0 0 10px #ffadad;
    }
    /* Glitch-Effekt auf Licht */
    .coffee-machine.broken .brew-light {
      animation: glitch-light 0.3s infinite;
    }
    @keyframes glitch-light {
      0% { background: var(--color-broken-main);
      box-shadow: 0 0 10px var(--color-broken-main); }
      30% { background: var(--color-brew-light-off); box-shadow: none;
      }
      60% { background: #ff0; box-shadow: 0 0 10px #ff0;
      }
      100% { background: var(--color-broken-main); box-shadow: 0 0 10px var(--color-broken-main);
      }
    }
    .container.is-broken {
      box-shadow: 0 8px 32px 0 var(--color-broken-glow);
    }
    @keyframes shake {
      0% { transform: translate(1px, 1px) rotate(0deg);
      }
      10% { transform: translate(-1px, -2px) rotate(-1deg);
      }
      20% { transform: translate(-3px, 0px) rotate(1deg);
      }
      30% { transform: translate(3px, 2px) rotate(0deg);
      }
      40% { transform: translate(1px, -1px) rotate(1deg);
      }
      50% { transform: translate(-1px, 2px) rotate(-1deg);
      }
      60% { transform: translate(-3px, 1px) rotate(0deg);
      }
      70% { transform: translate(3px, 1px) rotate(-1deg);
      }
      80% { transform: translate(-1px, -1px) rotate(1deg);
      }
      90% { transform: translate(1px, 2px) rotate(0deg);
      }
      100% { transform: translate(1px, -2px) rotate(-1deg);
      }
    }
    
    /* --- 11. Einstellungs-Panel (L3) --- */
    .settings-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transition: opacity var(--timing-fast) ease-in-out;
    }
    .settings-backdrop.is-visible {
      opacity: 1;
      pointer-events: all;
    }
    
    .settings-panel {
      position: fixed;
      top: 0;
      right: 0;
      width: 300px;
      height: 100%;
      background: var(--color-settings-bg);
      border-left: 2px solid var(--color-settings-border);
      box-shadow: -5px 0 25px rgba(0,0,0,0.2);
      z-index: 101;
      transform: translateX(100%);
      transition: transform var(--timing-fast) ease-in-out, background var(--timing-med), border var(--timing-med);
      padding: 20px;
      color: var(--color-text-primary);
    }
    .settings-panel.is-visible {
      transform: translateX(0);
    }
    
    .settings-panel h2 {
      margin-top: 0;
      color: var(--color-text-secondary);
      border-bottom: 2px solid var(--color-container-border);
      padding-bottom: 10px;
    }
    .settings-group {
      margin-bottom: 20px;
    }
    .settings-group label {
      display: block;
      margin-bottom: 5px;
      font-weight: 600;
      color: var(--color-text-secondary);
    }
    .settings-group input, .settings-group select {
      width: 100%;
      padding: 8px;
      border-radius: 6px;
      border: 1px solid var(--color-settings-border);
      background: var(--color-settings-input-bg);
      color: var(--color-text-primary);
      font-family: var(--font-main);
      font-size: 16px;
    }
    
    #saveSettingsBtn {
      width: 100%;
    }

    /* --- 12. Globale UI-Steuerung --- */
    .global-controls {
      position: absolute;
      top: 15px;
      right: 15px;
      display: flex;
      gap: 10px;
      z-index: 20;
    }

    /* --- 13. Responsive Anpassungen --- */
    @media (max-width: 450px) {
      .container {
        padding: 20px 25px;
      }
      .global-controls {
        top: 10px;
        right: 10px;
      }
      .icon-button {
        padding: 8px 10px;
      }
      #timerDisplay { font-size: 2.8rem;
      }
      button { padding: 10px 18px; font-size: 16px;
      }
      .settings-panel { width: 100%;
      }
    }

  </style>
</head>
<body>

  <audio id="audio-start" src="path/to/your/start-work.mp3" preload="auto"></audio>
  <audio id="audio-brew" src="path/to/your/brewing.mp3" preload="auto"></audio>
  <audio id="audio-done" src="path/to/your/timer-done.mp3" preload="auto"></audio>
  <audio id="audio-break" src="path/to/your/machine-break.mp3" preload="auto"></audio>
  <audio id="audio-click" src="path/to/your/click.mp3" preload="auto"></audio>
  <audio id="audio-drip" src="path/to/your/drip.mp3" preload="auto"></audio>

  <div class="particles">
    <div class="particle"></div><div class="particle"></div><div class="particle"></div><div class="particle"></div><div class="particle"></div>
  </div>

  <div class="container" id="container">
    
    <div class="global-controls">
      <button id="settingsBtn" class="icon-button" aria-label="Einstellungen">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19.14, 12.94c0.04-0.3, 0.06-0.61, 0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14, 0.23-0.41, 0.12-0.61l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39, 0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4, 2.81C14.36, 2.59, 14.18, 2.4, 13.96, 2.4h-3.92c-0.22, 0-0.4, 0.19-0.44, 0.41L9.16, 5.57C8.57, 5.8, 8.04, 6.12, 7.54, 6.5L5.15, 5.54c-0.22-0.07-0.47, 0-0.59, 0.22L2.64, 9.08c-0.11, 0.2-0.06, 0.47, 0.12, 0.61l2.03, 1.58C4.74, 11.6, 4.72, 11.9, 4.72, 12.23c0, 0.32, 0.02, 0.64, 0.07, 0.94l-2.03, 1.58c-0.18, 0.14-0.23, 0.41-0.12, 0.61l1.92, 3.32c0.12, 0.22, 0.37, 0.29, 0.59, 0.22l2.39-0.96c0.5, 0.38, 1.03, 0.7, 1.62, 0.94l0.44, 2.76C9.6, 21.41, 9.78, 21.6, 10.04, 21.6h3.92c0.22, 0, 0.4-0.19, 0.44-0.41l0.44-2.76c0.59-0.23, 1.12-0.56, 1.62-0.94l2.39, 0.96c0.22, 0.07, 0.47, 0, 0.59-0.22l1.92-3.32c0.12-0.2-0.05-0.47-0.12-0.61L19.14, 12.94z M12, 15.6c-1.98, 0-3.6-1.62-3.6-3.6s1.62-3.6, 3.6-3.6s3.6, 1.62, 3.6, 3.6S13.98, 15.6, 12, 15.6z"></path></svg>
      </button>
    </div>

    <div class="coffee-machine" id="coffeeMachine">
      <div class="machine-head"></div>
      <div class="machine-body">
        <div class="brew-light"></div>
      </div>
      <div class="machine-base"></div>
      <div class="machine-spout" id="machineSpout"></div>
      <div class="machine-steam" id="machineSteam">
        <div class="machine-steam-cloud"></div>
        <div 
class="machine-steam-cloud"></div>
        <div class="machine-steam-cloud"></div>
      </div>
    </div>
    
    <div class="coffee-stream" id="coffeeStream"></div>
    <div class="coffee-drip" id="coffeeDrip"></div>
    
    <div class="coffee-cup" aria-label="Kaffeetasse" id="coffeeCup">
      <div class="coffee-handle"></div>
      <div class="coffee-fill" id="coffeeFill"></div> 
      <div class="coffee-steam" id="coffeeSteam">
        <div class="steam-cloud"></div>
        <div class="steam-cloud"></div>
        <div class="steam-cloud"></div>
 
      </div>
    </div>
    
    <div id="timerDisplay" aria-live="polite">25:00</div>
    <div class="status" id="statusMsg" aria-live="polite">Bereit für die Arbeit?</div>
    
    <div class="cycle-tracker" id="cycleTracker">
      <span class="cycle-dot"></span><span class="cycle-dot"></span><span class="cycle-dot"></span><span class="cycle-dot"></span>
    </div>

    <div class="button-group">
      <button id="mainBtn">Start</button>
      <button id="pauseBtn" disabled>Pause</button>
      <button id="resetBtn">Reset</button>
    </div>
    <div>
      <button id="repairBtn">Reparieren</button>
    </div>
 
  </div>

  <div class="settings-backdrop" id="settingsBackdrop"></div>
  <div class="settings-panel" id="settingsPanel">
    <h2>Einstellungen</h2>
    
    <div class="settings-group">
      <label for="theme-select">Theme</label>
      <select id="theme-select">
        <option value="theme-dark">Dark Roast</option>
        <option value="theme-light">Light Roast</option>
      </select>
    </div>

    <div class="settings-group">
      <label for="work-minutes">Arbeitszeit (Minuten)</label>
      <input type="number" id="work-minutes" min="1" value="25">
    </div>

    <div class="settings-group">
  
      <label for="short-break-minutes">Kurze Pause (Minuten)</label>
      <input type="number" id="short-break-minutes" min="1" value="5">
    </div>

    <div class="settings-group">
      <label for="long-break-minutes">Lange Pause (Minuten)</label>
      <input type="number" id="long-break-minutes" min="1" value="15">
    </div>

    <button id="saveSettingsBtn" class="icon-button">Speichern & Schließen</button>
  </div>

<script>
  /**
   * Ultimate Coffee Pomodoro Timer (Level 6.1 - Final Polish)
   * FIX 1: Kaffeestrahl startet 5px höher.
   * FIX 2: Asymmetrisches SVG-Icon für Einstellungen ersetzt.
   */
  class PomodoroTimer {
    constructor() {
      // --- 1. Konfiguration & Standardwerte ---
      this.config = {
        work: 25 * 60,
        shortBreak: 5 * 60,
        longBreak: 15 * 60,
        breakdownLimit: 20 * 60
      };

      // --- 2. Zustands-Variablen (State) ---
      this.state = {
        timer: null,
        currentTime: this.config.work,
        currentTimerDuration: this.config.work,
        isWorkPhase: true,
        isPaused: false,
        firstStart: true,
        cycleCount: 0,
        coffeeLevel: 100, // Startet bei 100%
   
        machineBroken: false,
        breakCheckStartTime: null,
        isMuted: false
      };
      
      // --- 3. DOM-Elemente ---
      this.elements = {
        container: document.getElementById('container'),
        coffeeFill: document.getElementById('coffeeFill'),
        coffeeSteam: document.getElementById('coffeeSteam'),
        timerDisplay: document.getElementById('timerDisplay'),
        statusMsg: document.getElementById('statusMsg'),
        mainBtn: document.getElementById('mainBtn'),
        pauseBtn: document.getElementById('pauseBtn'),
        resetBtn: document.getElementById('resetBtn'),
        repairBtn: document.getElementById('repairBtn'),
       
        coffeeMachine: document.getElementById('coffeeMachine'),
        machineSteam: document.getElementById('machineSteam'),
        machineSpout: document.getElementById('machineSpout'),
        coffeeStream: document.getElementById('coffeeStream'),
        coffeeDrip: document.getElementById('coffeeDrip'),
        coffeeCup: document.getElementById('coffeeCup'),
        cycleTracker: document.getElementById('cycleTracker'),
        
        // Einstellungen (L3)
        settingsBtn: document.getElementById('settingsBtn'),
        settingsPanel: document.getElementById('settingsPanel'),
     
        settingsBackdrop: document.getElementById('settingsBackdrop'),
        saveSettingsBtn: document.getElementById('saveSettingsBtn'),
        themeSelect: document.getElementById('theme-select'),
        workInput: document.getElementById('work-minutes'),
        shortBreakInput: document.getElementById('short-break-minutes'),
        longBreakInput: document.getElementById('long-break-minutes'),

        // Mute (L3)
        muteBtn: document.getElementById('muteBtn'),
        iconUnmuted: document.getElementById('icon-unmuted'),
        iconMuted: document.getElementById('icon-muted')
      };
      // --- 4. Audio-Elemente ---
      this.audio = {
        start: document.getElementById('audio-start'),
        brew: document.getElementById('audio-brew'),
        done: document.getElementById('audio-done'),
        break: document.getElementById('audio-break'),
        click: document.getElementById('audio-click'),
        drip: document.getElementById('audio-drip')
      };
      // --- 5. Initialisierung ---
      this.bindEvents();
      this.init();
    }

    /**
     * Bindet alle Event-Listener.
     */
    bindEvents() {
      this.elements.mainBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.toggleMainBtn();
      });
      this.elements.pauseBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.togglePauseBtn();
      });
      this.elements.resetBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.resetTimer();
      });
      this.elements.repairBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.repairMachine();
      });
      // L3 Event-Listener
      this.elements.settingsBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.toggleSettings(true);
      });
      this.elements.settingsBackdrop.addEventListener('click', () => this.toggleSettings(false));
      this.elements.saveSettingsBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.saveSettings();
      });
      this.elements.muteBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.toggleMute();
      });
      this.elements.themeSelect.addEventListener('change', () => this.applyTheme());
    }

    /**
     * Initialisiert den Timer beim Laden.
     */
    init() {
      // Gespeichertes Theme laden
      const savedTheme = localStorage.getItem('pomodoroTheme') || 'theme-dark';
      document.documentElement.className = savedTheme;
      this.elements.themeSelect.value = savedTheme;

      // Zeiten aus Config in UI laden
      this.elements.workInput.value = this.config.work / 60;
      this.elements.shortBreakInput.value = this.config.shortBreak / 60;
      this.elements.longBreakInput.value = this.config.longBreak / 60;
      
      this.state.currentTime = this.config.work;
      this.state.currentTimerDuration = this.config.work;
      this.state.coffeeLevel = 100; // Startet voll

      this.updateTimerDisplay(this.state.currentTime);
      this.updateCoffeeFill();
      this.updateCycleTracker();
      this.setCupSteaming(false); // Startet nicht dampfend
      this.setMachineWorking(false);
      this.showCoffeeStream(false);
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = true;
    }

    // --- 6. Kern-Timer-Logik ---

    /**
     * Der Haupt-Tick, wird jede Sekunde ausgeführt.
     */
    tick() {
      if (this.state.isPaused || this.state.machineBroken) return;

      this.state.currentTime--;
      this.updateTimerDisplay(this.state.currentTime);

      if (this.state.isWorkPhase) {
        // --- ARBEITSPHASE ---
        // Kaffeestand leert sich während der Arbeit
        this.state.coffeeLevel = Math.max(0, (this.state.currentTime / this.state.currentTimerDuration) * 100);
        this.updateCoffeeFill();

      } else {
        // --- PAUSENPHASE (NEUE LOGIK) ---
        // Kaffeestand füllt sich während der Pause
        const timeElapsed = this.state.currentTimerDuration - this.state.currentTime;
        // Sicherstellen, dass die Dauer nicht 0 ist, um NaN zu vermeiden
        const duration = this.state.currentTimerDuration || 1; 
        const progress = Math.min(1, timeElapsed / duration);
        this.state.coffeeLevel = Math.max(0, progress * 100);
        this.updateCoffeeFill();
        
        // Kaffeestrahl-Logik
        if (progress < 1) {
          this.showCoffeeStream(true);
          this.updateStreamPosition(); // Strahl dynamisch anpassen
        } else {
          this.showCoffeeStream(false);
        }

        // Maschine stoppen, wenn Tasse voll ist (auch wenn Pause weiterläuft)
        // (Prüft, ob Maschine 'is-working', um dies nur einmal auszulösen)
        if (progress >= 1 && this.elements.coffeeMachine.classList.contains('is-working')) {
          this.setMachineWorking(false);
          this.setCupSteaming(true);
          this.playDripAnimation(); // Spielt Tropfen ab, wenn voll
        }
      }

      // Prüft, ob die Maschine kaputt geht (während der Pause)
      if (!this.state.isWorkPhase && this.state.breakCheckStartTime) {
        const breakDuration = (Date.now() - this.state.breakCheckStartTime) / 1000;
        if (breakDuration > this.config.breakdownLimit) {
          this.breakMachine();
          return;
        }
      }

      // Timer ist abgelaufen, Phasen-Wechsel
      if (this.state.currentTime < 0) {
        this.transitionState();
      }
    }

    startTimer() {
      if (this.state.timer) clearInterval(this.state.timer);
      this.state.timer = setInterval(() => this.tick(), 1000);
    }

    stopTimer() {
      if (this.state.timer) clearInterval(this.state.timer);
      this.state.timer = null;
    }

    /**
     * Wechselt zwischen Arbeits- und Pausenphase.
     */
    transitionState() {
      this.stopTimer();
      this.playAudio('done');
      
      // Stoppe Füll-Animationen (Strahl/Maschine) sofort
      this.showCoffeeStream(false);
      this.setMachineWorking(false); // Stoppt Maschine in jedem Fall

      if (this.state.isWorkPhase) {
        // --- Von Arbeit ZU Pause ---
        this.state.cycleCount++;
        this.state.isWorkPhase = false;
        this.state.breakCheckStartTime = Date.now();
        
        if (this.state.cycleCount % 4 === 0) {
          this.state.currentTime = this.config.longBreak;
          this.elements.statusMsg.textContent = "Lange Pause! Kaffee wird gebrüht...";
        } else {
          this.state.currentTime = this.config.shortBreak;
          this.elements.statusMsg.textContent = "Kurze Pause. Kaffee wird gebrüht...";
        }
        this.state.currentTimerDuration = this.state.currentTime;
        this.elements.mainBtn.textContent = "Pause überspringen";
        
        // Tasse vor dem Füllen leeren
        this.state.coffeeLevel = 0;
        this.updateCoffeeFill(); // Tasse sofort leeren
        
        this.setMachineWorking(true); // Maschine AN
        this.setCupSteaming(false); // Leere Tasse dampft nicht
        this.showCoffeeStream(true); // Strahl AN
        this.updateStreamPosition(); // Strahl positionieren
        this.playAudio('brew');
        
      } else {
        // --- Von Pause ZU Arbeit ---
        this.state.isWorkPhase = true;
        this.state.breakCheckStartTime = null;
        this.state.currentTime = this.config.work;
        this.state.currentTimerDuration = this.config.work;
        this.elements.statusMsg.textContent = "Arbeitsphase: Lernen";
        this.elements.mainBtn.textContent = "Pause einlegen";
        
        // Tasse ist jetzt 100% voll (wird von tick() erledigt, aber hier zur Sicherheit)
        this.state.coffeeLevel = 100;
        this.updateCoffeeFill();
        
        this.setMachineWorking(false);
        this.setCupSteaming(false); // Tasse dampft nur am Ende der Pause
        this.playAudio('start');
      }
      
      this.updateTimerDisplay(this.state.currentTime);
      this.updateCycleTracker();
      this.startTimer();
    }

    // --- 7. Tasten-Aktionen & Event-Handler ---

    toggleMainBtn() {
      if (this.state.machineBroken) return;
      this.state.isPaused = false;

      // Erster Start überhaupt
      if (this.state.firstStart) {
        this.state.firstStart = false;
        this.elements.mainBtn.textContent = "Pause einlegen";
        this.elements.pauseBtn.disabled = false;
        this.elements.resetBtn.disabled = false;
        this.playAudio('start');
        this.startTimer();
        return;
      }

      // Timer läuft (Arbeit ODER Pause) -> Phase überspringen
      if (this.state.timer && !this.state.isPaused) {
        this.transitionState();
        return;
      } 
      
      // Timer war pausiert (Jetzt: Fortsetzen)
      this.elements.pauseBtn.disabled = false;
      this.elements.mainBtn.textContent = this.state.isWorkPhase ? "Pause einlegen" : "Pause überspringen";
      this.elements.statusMsg.textContent = this.state.isWorkPhase ? "Arbeitsphase: Lernen" : "Pause läuft...";
      
      // Animationen wieder aufnehmen
      if (!this.state.isWorkPhase) {
          // Pause (Brühvorgang) wird fortgesetzt
          if (this.state.coffeeLevel < 100) {
            // Tasse ist noch nicht voll
            this.setMachineWorking(true);
            this.showCoffeeStream(true);
          } else {
            // Tasse ist bereits voll
            this.setMachineWorking(false);
            this.showCoffeeStream(false);
            this.setCupSteaming(true);
          }
      }
      
      this.startTimer();
    }

    togglePauseBtn() {
      if (this.state.machineBroken || this.state.firstStart) return;

      this.state.isPaused = true;
      this.stopTimer();
      
      this.elements.statusMsg.textContent = "Timer pausiert.";
      this.elements.pauseBtn.disabled = true;
      this.elements.mainBtn.textContent = this.state.isWorkPhase ? "Weiter lernen" : "Pause fortsetzen";
      
      // Visuelle Effekte pausieren
      this.setMachineWorking(false);
      this.showCoffeeStream(false); // Strahl stoppen
      this.setCupSteaming(false);
    }

    resetTimer(applySettings = false) {
      if (this.state.machineBroken) return;
      
      this.stopTimer();

      this.state.isWorkPhase = true;
      this.state.isPaused = false;
      this.state.firstStart = true;
      this.state.cycleCount = 0;
      this.state.currentTime = this.config.work;
      this.state.currentTimerDuration = this.config.work;
      this.state.coffeeLevel = 100; // Zurücksetzen auf voll
      this.state.breakCheckStartTime = null;

      // UI zurücksetzen
      this.updateTimerDisplay(this.state.currentTime);
      this.updateCoffeeFill();
      this.updateCycleTracker();
      this.setMachineWorking(false);
      this.setCupSteaming(false);
      this.showCoffeeStream(false);
      this.elements.statusMsg.textContent = applySettings ? "Einstellungen gespeichert. Bereit?" : "Bereit für die Arbeit?";
      this.elements.mainBtn.textContent = "Start";
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = true;
    }

    breakMachine() {
      this.state.machineBroken = true;
      this.stopTimer();
      this.playAudio('break');

      this.elements.coffeeMachine.classList.add('broken');
      this.elements.container.classList.add('is-broken');
      this.setMachineWorking(false);
      this.setCupSteaming(false);
      this.showCoffeeStream(false);

      this.elements.statusMsg.textContent = "Maschine überhitzt! Reparieren.";
      this.elements.mainBtn.disabled = true;
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = true;
      this.elements.repairBtn.style.display = 'inline-block';
    }

    repairMachine() {
      this.state.machineBroken = false;
      this.elements.coffeeMachine.classList.remove('broken');
      this.elements.container.classList.remove('is-broken');
      this.elements.repairBtn.style.display = 'none';
      
      this.elements.mainBtn.disabled = false;
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = false;
      
      this.resetTimer();
      this.elements.statusMsg.textContent = "Maschine repariert. Starte eine neue Session.";
    }

    // --- 8. Visuelle Hilfsfunktionen (L3/L5) ---
    
    /**
     * Berechnet die Position des Kaffeestrahls von der Tülle
     * bis zur aktuellen Kaffeeoberfläche.
     */
    updateStreamPosition() {
      // Breche ab, wenn der Strahl nicht sichtbar sein soll
      if (this.elements.coffeeStream.style.display === 'none' || this.state.coffeeLevel >= 100) {
        this.showCoffeeStream(false); // Sicherheitshalber Strahl ausblenden
        return;
      }
      
      const containerRect = this.elements.container.getBoundingClientRect();
      const cupRect = this.elements.coffeeCup.getBoundingClientRect();
      const spoutRect = this.elements.machineSpout.getBoundingClientRect();
      
      // Absolute Positionen
      const containerTop = containerRect.top + window.scrollY;
      
      // Position der Tüllen-Unterkante (relativ zum Dokument)
      const spoutBottom = spoutRect.bottom;
      
      // Kaffee-Oberfläche berechnen (relativ zum Dokument)
      // (Fügt 2px Puffer hinzu, damit der Strahl die Welle berührt)
      const fillHeight = (this.state.coffeeLevel / 100) * (cupRect.height - 2); 
      const fillTopAbsolute = cupRect.bottom - fillHeight; // Oberkante des Kaffees

      // Positionen relativ zum Container
      // FIX: Strahl startet 5px höher (negativer Offset)
      const streamTop = (spoutBottom - containerRect.top) - 5;
      const streamEnd = fillTopAbsolute - containerRect.top;
      
      let streamHeight = streamEnd - streamTop;
      
      // Strahl-Position
      const spoutCenterX = spoutRect.left + (spoutRect.width / 2) - containerRect.left;
      
      if (streamHeight > 0) {
        this.elements.coffeeStream.style.top = `${streamTop}px`;
        this.elements.coffeeStream.style.height = `${streamHeight}px`;
        this.elements.coffeeStream.style.left = `${spoutCenterX - 4}px`; // 4 = hälfte der Strahlbreite (8px)
      } else {
        // Wenn Tasse fast voll ist, Strahl ausblenden
        this.showCoffeeStream(false);
      }
    }
    
    /**
     * Zeigt den Kaffeestrahl (oder blendet ihn aus).
     */
    showCoffeeStream(on) {
      this.elements.coffeeStream.style.display = on ? 'block' : 'none';
    }

    /**
     * Spielt die "Nachtropfen"-Animation ab.
     */
    playDripAnimation() {
      const containerRect = this.elements.container.getBoundingClientRect();
      const spoutRect = this.elements.machineSpout.getBoundingClientRect();
      
      const dripTop = spoutRect.bottom - containerRect.top;
      const dripLeft = spoutRect.left + (spoutRect.width / 2) - containerRect.left - 3;
      // 3 = hälfte Tropfenbreite
      
      this.elements.coffeeDrip.style.top = `${dripTop}px`;
      this.elements.coffeeDrip.style.left = `${dripLeft}px`;
      
      // Animation durch Klasse auslösen
      this.elements.coffeeDrip.classList.remove('is-dripping');
      
      // Kurzer Timeout, um "reflow" zu erzwingen, falls Klasse schon da war
      setTimeout(() => {
        this.elements.coffeeDrip.classList.add('is-dripping');
        this.playAudio('drip');
      }, 10);
    }

    setMachineWorking(isWorking) {
      this.elements.coffeeMachine.classList.toggle('is-working', isWorking);
    }

    setCupSteaming(steaming) {
      this.elements.coffeeSteam.style.display = steaming ? 'block' : 'none';
    }

    updateCoffeeFill() {
      this.elements.coffeeFill.style.height = `${Math.max(0, Math.min(100, this.state.coffeeLevel))}%`;
    }

    updateTimerDisplay(seconds) {
      // Stellt sicher, dass 00:00 angezeigt wird, nicht negative Zahlen
      const displaySeconds = Math.max(0, seconds);
      let m = Math.floor(displaySeconds / 60);
      let s = displaySeconds % 60;
      this.elements.timerDisplay.textContent = `${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
    }

    updateCycleTracker() {
      const dots = this.elements.cycleTracker.querySelectorAll('.cycle-dot');
      dots.forEach((dot, index) => {
        dot.classList.toggle('filled', index < (this.state.cycleCount % 4));
      });
      
      // Alle füllen, wenn 4. Zyklus erreicht ist
      if (this.state.cycleCount > 0 && this.state.cycleCount % 4 === 0) {
        dots.forEach(dot => dot.classList.add('filled'));
      }
    }

    // --- 9. Neue L3-Funktionen (Settings, Mute, Theme) ---

    toggleSettings(show) {
      this.elements.settingsPanel.classList.toggle('is-visible', show);
      this.elements.settingsBackdrop.classList.toggle('is-visible', show);
    }

    saveSettings() {
      // Eingaben validieren und in Sekunden umrechnen
      const workMin = parseInt(this.elements.workInput.value) || 25;
      const shortMin = parseInt(this.elements.shortBreakInput.value) || 5;
      const longMin = parseInt(this.elements.longBreakInput.value) || 15;

      this.config.work = workMin * 60;
      this.config.shortBreak = shortMin * 60;
      this.config.longBreak = longMin * 60;
      
      // UI aktualisieren und Timer zurücksetzen
      this.elements.workInput.value = workMin;
      this.elements.shortBreakInput.value = shortMin;
      this.elements.longBreakInput.value = longMin;
      
      this.toggleSettings(false);
      this.resetTimer(true); // 'true' für spezielle Reset-Nachricht
    }
    
    toggleMute() {
      this.state.isMuted = !this.state.isMuted;
      this.elements.iconUnmuted.style.display = this.state.isMuted ? 'none' : 'block';
      this.elements.iconMuted.style.display = this.state.isMuted ? 'block' : 'none';
    }

    applyTheme() {
      const selectedTheme = this.elements.themeSelect.value;
      document.documentElement.className = selectedTheme;
      localStorage.setItem('pomodoroTheme', selectedTheme);
    }

    playAudio(soundId) {
      if (this.state.isMuted) return;
      try {
        const sound = this.audio[soundId];
        if (sound) {
          sound.currentTime = 0;
          sound.play().catch(e => console.log("Audio-Wiedergabe blockiert: ", e));
        }
      } catch (e) {
        console.error("Audio-Fehler: ", e);
      }
    }
  }

  // Initialisiere die App, sobald das DOM geladen ist.
  document.addEventListener('DOMContentLoaded', () => {
    const timerApp = new PomodoroTimer();
  });
  
</script>
</body>
</html>
            """
        elif mode == "Popup":
            self.html = r"""
            <!DOCTYPE html>
<html lang="de" class="theme-dark"> <head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ultimate Coffee Pomodoro Timer</title>
  <style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
    /* --- 1. CSS-Variablen (Themes & Basis) --- */
    :root {
      --font-main: 'Poppins', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      /* Basis-Timing */
      --timing-fast: 0.2s;
      --timing-med: 0.4s;
    }

    /* Theme "Dark Roast" (Standard) */
    :root.theme-dark {
      --color-bg: #2e2118;
      --color-bg-gradient: radial-gradient(ellipse at center, #413023 0%, #2e2118 100%);
      --color-text-primary: #f3eada;
      --color-text-secondary: #f6d6ad;
      --color-container-bg: rgba(46, 33, 24, 0.75);
      --color-container-border: rgba(243, 234, 218, 0.15);
      --color-container-shadow: rgba(18, 12, 7, 0.37);
      
      --color-machine-body: #505050;
      --color-machine-accent: #333;
      --color-machine-shine: #777;
      --color-machine-base: #222;
      --color-brew-light-off: #333;
      --color-brew-light-on: #4eff81;
      
      --color-cup-border: #6b4c3b;
      --color-cup-bg: #221a14;
      --color-cup-shine: rgba(255, 255, 255, 0.05);

      --color-coffee-dark: #6d4a2f;
      --color-coffee-mid: #8b5e3c;
      --color-coffee-light: #a1703a;

      --color-btn-primary: #6b4c3b;
      --color-btn-primary-shadow: #4b2e0e;
      --color-btn-primary-hover: #8b6a4f;
      --color-btn-secondary: #5a5a5a;
      --color-btn-secondary-shadow: #333;
      --color-btn-secondary-hover: #777;
      
      --color-settings-bg: #36271b;
      --color-settings-border: #6b4c3b;
      --color-settings-input-bg: #2e2118;

      --color-broken-main: #b44f4f;
      --color-broken-shadow: #721a1a;
      --color-broken-glow: #ff4d4d;
    }

    /* Theme "Light Roast" */
    :root.theme-light {
      --color-bg: #f4f0e9;
      --color-bg-gradient: radial-gradient(ellipse at center, #ffffff 0%, #f4f0e9 100%);
      --color-text-primary: #3d2c1f;
      --color-text-secondary: #6b4c3b;
      --color-container-bg: rgba(255, 255, 255, 0.75);
      --color-container-border: rgba(61, 44, 31, 0.15);
      --color-container-shadow: rgba(61, 44, 31, 0.15);
      
      --color-machine-body: #c0c0c0;
      --color-machine-accent: #9e9e9e;
      --color-machine-shine: #f0f0f0;
      --color-machine-base: #777;
      --color-brew-light-off: #a0a0a0;
      --color-brew-light-on: #00e05a;
      
      --color-cup-border: #bcaaa4;
      --color-cup-bg: #ffffff;
      --color-cup-shine: rgba(0, 0, 0, 0.03);

      --color-coffee-dark: #6d4a2f;
      --color-coffee-mid: #8b5e3c;
      --color-coffee-light: #a1703a;

      --color-btn-primary: #8d6e63;
      --color-btn-primary-shadow: #5f4339;
      --color-btn-primary-hover: #a1887f;
      --color-btn-secondary: #9e9e9e;
      --color-btn-secondary-shadow: #707070;
      --color-btn-secondary-hover: #b0b0b0;
      
      --color-settings-bg: #fdfaf6;
      --color-settings-border: #d7ccc8;
      --color-settings-input-bg: #f4f0e9;

      --color-broken-main: #d32f2f;
      --color-broken-shadow: #9a0007;
      --color-broken-glow: #ff6659;
    }

    /* --- 2. Grund-Layout & Body --- */
    *, *::before, *::after {
      box-sizing: border-box;
    }

    body {
      background: var(--color-bg);
      background-image: var(--color-bg-gradient);
      color: var(--color-text-primary);
      font-family: var(--font-main);
      margin: 0;
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      flex-direction: column;
      padding: 20px;
      transition: background var(--timing-med), color var(--timing-med);
      overflow-x: hidden;
    }

    /* Subtile Hintergrund-Partikel */
    .particles {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: -1;
      pointer-events: none;
    }
    .particle {
      position: absolute;
      background: var(--color-text-secondary);
      border-radius: 50%;
      opacity: 0;
      animation: floatUp 20s infinite linear;
    }
    .particle:nth-child(1) { width: 5px; height: 5px; left: 10%; animation-duration: 15s;
      animation-delay: 1s; }
    .particle:nth-child(2) { width: 3px; height: 3px; left: 30%; animation-duration: 25s; animation-delay: 5s;
    }
    .particle:nth-child(3) { width: 6px; height: 6px; left: 50%; animation-duration: 18s; animation-delay: 3s;
    }
    .particle:nth-child(4) { width: 4px; height: 4px; left: 70%; animation-duration: 22s; animation-delay: 8s;
    }
    .particle:nth-child(5) { width: 3px; height: 3px; left: 90%; animation-duration: 30s; animation-delay: 2s;
    }
    
    @keyframes floatUp {
      0% { transform: translateY(100vh) translateX(0);
      opacity: 0; }
      10% { opacity: 0.1;
      }
      90% { opacity: 0.05;
      }
      100% { transform: translateY(-10vh) translateX(20px); opacity: 0;
      }
    }

    /* --- 3. Haupt-Container --- */
    .container {
      background: var(--color-container-bg);
      border: 1px solid var(--color-container-border);
      border-radius: 24px;
      padding: 30px 40px;
      box-shadow: 0 8px 32px 0 var(--color-container-shadow);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      max-width: 420px;
      width: 100%;
      text-align: center;
      position: relative;
      z-index: 10;
      transition: background var(--timing-med), border var(--timing-med), box-shadow var(--timing-med);
    }
    
    /* --- 4. Kaffeemaschine (Redesign Level 3) --- */
    .coffee-machine {
      margin: 0 auto 10px auto;
      width: 150px; /* Breiter */
      height: 160px;
      position: relative;
      z-index: 10;
      /* Maschine ist auf Ebene 10 */
      filter: drop-shadow(0 4px 5px rgba(0,0,0,0.3));
    }
    
    /* Maschinen-Kopf (integrierter Deckel) */
    .machine-head {
      width: 100%;
      height: 40px;
      position: absolute;
      top: 0;
      background: linear-gradient(to right, var(--color-machine-accent) 0%, var(--color-machine-body) 20%, var(--color-machine-shine) 50%, var(--color-machine-body) 80%, var(--color-machine-accent) 100%);
      border-radius: 16px 16px 0 0;
      border: 2px solid var(--color-machine-accent);
      border-bottom: none;
      box-shadow: inset 0 2px 4px rgba(255,255,255,0.1);
    }
    /* Glanz-Effekt */
    .machine-head::after {
      content: '';
      position: absolute;
      top: 4px;
      left: 10%;
      width: 80%;
      height: 4px;
      background: rgba(255,255,255,0.2);
      border-radius: 2px;
    }
    
    /* Maschinen-Körper */
    .machine-body {
      width: 140px;
      /* Schmaler als Kopf */
      height: 120px;
      position: absolute;
      top: 40px;
      /* Direkt unter Kopf */
      left: 5px;
      background: var(--color-machine-body);
      border-left: 2px solid var(--color-machine-accent);
      border-right: 2px solid var(--color-machine-accent);
    }

    /* Wassertank (Pseudo-Element) */
    .machine-body::before {
      content: '';
      position: absolute;
      top: 10px;
      right: 10px;
      width: 30px;
      height: 80px;
      background: rgba(180, 210, 255, 0.2);
      border: 2px solid rgba(255,255,255,0.1);
      border-radius: 4px;
      box-shadow: inset 0 1px 3px rgba(0,0,0,0.2);
    }
    
    /* Maschinen-Basis */
    .machine-base {
      width: 100%;
      height: 20px;
      background: var(--color-machine-base);
      position: absolute;
      bottom: -18px; /* Überlappt mit Körper */
      border-radius: 0 0 12px 12px;
      border: 2px solid var(--color-machine-base);
      box-shadow: 0 4px 0 #111;
    }

    /* "Brühlicht" */
    .brew-light {
      width: 12px;
      height: 12px;
      background: var(--color-brew-light-off);
      border-radius: 50%;
      position: absolute;
      bottom: 15px;
      left: 15px;
      border: 2px solid #222;
      transition: background 0.3s, box-shadow 0.3s;
    }

    /* Maschinen-Ausguss */
    .machine-spout {
      width: 24px;
      height: 30px; /* Kürzer */
      background: var(--color-machine-accent);
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      bottom: -10px;
      /* Hängt aus dem Körper */
      border-radius: 0 0 8px 8px;
      z-index: 14;
      /* Tülle ist auf Ebene 14 */
      border: 2px solid #222;
    }
    
    /* Maschinen-Dampf */
    .machine-steam {
      pointer-events: none;
      position: absolute; left: 50%; top: -10px; width: 36px; height: 32px; opacity: 0.8; z-index: 4; display: none; transform: translateX(-50%);
    }
    .machine-steam-cloud {
      position: absolute; width: 10px; height: 20px; left: 0;
      border-radius: 10px 10px 13px 13px / 12px 12px 16px 16px; background: linear-gradient(180deg, #fff 60%, #ffffff3a 100%); opacity: 0.75;
      animation: steamUp 2.2s infinite; filter: blur(0.5px);
    }
    .machine-steam-cloud:nth-child(2) { left: 13px; width: 8px; height: 14px; opacity: 0.55;
      animation: steamUp 2s 1s infinite; }
    .machine-steam-cloud:nth-child(3) { left: 23px; width: 7px; height: 11px; opacity: 0.38;
      animation: steamUp 2.3s 0.4s infinite; }
    
    @keyframes steamUp {
      0% { transform: translateY(0) scale(1);
      opacity: 0.7;}
      100% { transform: translateY(-20px) scale(1.1);
      opacity: 0;}
    }

    /* --- 5. "Maschine arbeitet"-Zustände --- */
    .coffee-machine.is-working .machine-body {
      animation: machineVibrate 0.18s infinite linear;
    }
    .coffee-machine.is-working .brew-light {
      background: var(--color-brew-light-on);
      box-shadow: 0 0 10px 2px var(--color-brew-light-on), inset 0 0 2px #fff;
      animation: pulse 1s infinite;
    }
    .coffee-machine.is-working .machine-steam {
      display: block;
    }
    
    @keyframes machineVibrate {
      0%{transform: translateX(0) translateY(0);} 18%{transform: translateX(1px) translateY(-1px);} 31%{transform: translateX(-1px) translateY(1px);} 50%{transform: translateX(0.7px) translateY(0);} 62%{transform: translateX(-1px) translateY(-1px);} 100% {transform: translateX(0) translateY(0);}
    }
    @keyframes pulse {
      0% { opacity: 1;
      } 50% { opacity: 0.6; } 100% { opacity: 1;
      }
    }
    
    /* --- 6. Kaffeetasse & Füllung (L3 Wellen) --- */
    .coffee-cup {
      margin: 40px auto 10px auto;
      /* Mehr Abstand zur Maschine */
      width: 100px;
      height: 90px;
      border: 4px solid var(--color-cup-border);
      border-radius: 0 0 50px 50px;
      position: relative;
      overflow: hidden;
      background: var(--color-cup-bg);
      box-sizing: border-box;
      z-index: 5;
      /* Tasse ist auf Ebene 5 */
      box-shadow: 0 4px 8px rgba(0,0,0,0.2), inset 0 3px 5px rgba(0,0,0,0.3);
      transition: border var(--timing-med), background var(--timing-med);
    }
    /* Tassen-Glanz */
    .coffee-cup::after {
      content: '';
      position: absolute;
      top: 5px;
      left: 5px;
      width: 86px;
      height: 40px;
      border-radius: 0 0 40px 40px;
      background: var(--color-cup-shine);
      transform: rotate(10deg);
      transition: background var(--timing-med);
    }
    .coffee-handle {
      position: absolute;
      left: 94px;
      top: 30px;
      width: 22px;
      height: 36px;
      border: 4px solid var(--color-cup-border);
      border-radius: 40px 40px 60px 20px / 40px 40px 60px 20px;
      background: transparent;
      z-index: 2;
      transition: border var(--timing-med);
    }

    /* Der Füll-Container */
    .coffee-fill {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      background: var(--color-coffee-dark);
      /* NEU: Transition geändert für sanfteres Füllen/Leeren */
      transition: height 0.5s cubic-bezier(0.36, 0.58, 0.2, 0.9);
      z-index: 1;
      overflow: hidden;
      /* Wichtig für clip-path */
    }

    /* Die "schwappende" Oberfläche */
    .coffee-fill::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: var(--color-coffee-mid);
      z-index: 2;
      animation: wave 8s infinite linear;
    }
    
    @keyframes wave {
      0% {
        clip-path: polygon(
          0% 100%, 100% 100%, 100% 10%, 
          80% 8%, 60% 10%, 40% 12%, 20% 10%, 
          0% 8%
        );
      }
      50% {
        clip-path: polygon(
          0% 100%, 100% 100%, 100% 8%, 
          80% 10%, 60% 12%, 40% 10%, 20% 8%, 
          0% 10%
        );
      }
      100% {
        clip-path: polygon(
          0% 100%, 100% 100%, 100% 10%, 
          80% 8%, 60% 10%, 40% 12%, 20% 10%, 
          0% 8%
        );
      }
    }
    
    /* Tassen-Dampf */
    .coffee-steam {
      pointer-events: none;
      position: absolute; left: 50%; top: -24px; transform: translateX(-50%); width: 40px; height: 32px; opacity: 0.65; z-index: 4; display: none;
    }
    .steam-cloud {
      position: absolute; width: 16px; height: 22px; left: 0;
      border-radius: 9px 9px 13px 13px / 12px 12px 16px 16px; background: linear-gradient(180deg, #fff 60%, #ffffff33 100%); opacity: 0.75;
      animation: steamUp 2.2s infinite; filter: blur(0.5px);
    }
    .steam-cloud:nth-child(2) { left: 16px; width: 12px; height: 17px; opacity: 0.48;
      animation: steamUp 2.1s 0.9s infinite; }
    .steam-cloud:nth-child(3) { left: 24px; width: 10px; height: 14px; opacity: 0.4;
      animation: steamUp 2.5s 0.5s infinite; }

    /* --- 7. Kaffeestrahl (Dynamisch, L3) --- */
    
    /* ***** FIX 1 HIER: z-index auf 99 gesetzt, um Überdeckung zu vermeiden ***** */
    .coffee-stream {
      position: absolute;
      width: 8px; /* Dünner */
      left: 50%;
      /* JS setzt genaue Position */
      top: 0;
      /* JS setzt Position */
      height: 0;
      /* JS setzt Höhe */
      background: linear-gradient(to bottom, var(--color-coffee-light), var(--color-coffee-mid), var(--color-coffee-light));
      background-size: 100% 15px;
      border-radius: 4px;
      z-index: 99; /* HÖCHSTE EBENE */
      display: none;
      /* JS steuert */
      animation: stream-flow 0.3s linear infinite;
    }
    
    @keyframes stream-flow {
      0% { background-position: 0 0;
      }
      100% { background-position: 0 15px;
      }
    }

    /* Tropfen-Animation */
    /* ***** FIX 1 HIER: z-index auf 99 gesetzt, um Überdeckung zu vermeiden ***** */
    .coffee-drip {
      position: absolute;
      width: 6px;
      height: 10px;
      background: var(--color-coffee-mid);
      border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
      z-index: 99;
      /* HÖCHSTE EBENE */
      display: none;
      /* JS steuert */
      transform: scaleY(0.8);
    }
    .coffee-drip.is-dripping {
      display: block;
      animation: drip 0.5s ease-in forwards;
    }
    @keyframes drip {
      0% { transform: translateY(0) scaleY(0.8); opacity: 1;
      }
      80% { opacity: 1;
      }
      100% { transform: translateY(40px) scaleY(1.2); opacity: 0;
      }
    }

    /* --- 8. UI-Elemente (Timer, Status, Zyklen) --- */
    #timerDisplay {
      font-size: 3.2rem;
      font-weight: 700;
      margin: 10px 0;
      color: var(--color-text-primary);
      text-shadow: 0 2px 4px rgba(0,0,0,0.2);
      transition: color var(--timing-med);
    }
    .status {
      margin: 0 0 10px 0;
      font-weight: 600;
      min-height: 24px;
      color: var(--color-text-secondary);
      font-size: 1.1rem;
      transition: color var(--timing-med);
    }
    .cycle-tracker {
      margin: 10px 0;
    }
    .cycle-dot {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--color-cup-bg);
      border: 1px solid var(--color-cup-border);
      margin: 0 4px;
      transition: background 0.3s, border 0.3s;
    }
    .cycle-dot.filled {
      background: var(--color-text-secondary);
    }

    /* --- 9. Tasten (3D-Stil) --- */
    .button-group {
      margin-top: 10px;
    }
    button {
      background: var(--color-btn-primary);
      color: var(--color-text-primary);
      border: none;
      border-radius: 8px;
      padding: 12px 22px;
      font-size: 18px;
      font-family: var(--font-main);
      font-weight: 600;
      cursor: pointer;
      margin: 7px 6px 0 6px;
      box-shadow: 0 4px 0 var(--color-btn-primary-shadow);
      transition: background 0.2s, box-shadow 0.1s, transform 0.1s, color var(--timing-med);
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      background: #5b4735;
      box-shadow: 0 4px 0 #413226;
      transform: translateY(0) !important;
    }
    button:hover:enabled {
      background: var(--color-btn-primary-hover);
      transform: scale(1.03);
    }
    button:active:enabled {
      transform: translateY(2px) scale(0.98);
      box-shadow: 0 2px 0 var(--color-btn-primary-shadow);
    }

    /* Spezielle Tasten */
    #resetBtn, #settingsBtn, #muteBtn {
      background: var(--color-btn-secondary);
      box-shadow: 0 4px 0 var(--color-btn-secondary-shadow);
    }
    #resetBtn:hover:enabled, #settingsBtn:hover:enabled, #muteBtn:hover:enabled { background: var(--color-btn-secondary-hover);
    }
    #resetBtn:active:enabled, #settingsBtn:active:enabled, #muteBtn:active:enabled { box-shadow: 0 2px 0 var(--color-btn-secondary-shadow);
    }
    
    #repairBtn {
      background: var(--color-broken-main);
      box-shadow: 0 4px 0 var(--color-broken-shadow);
      border: none; color: #fff; display: none;
    }
    
    /* Icon-Tasten (SVG-Icons) */
    .icon-button {
      padding: 10px 12px;
    }
    .icon-button svg {
      width: 20px;
      height: 20px;
      fill: var(--color-text-primary);
      vertical-align: middle;
      pointer-events: none; /* Wichtig, damit Klick auf Button geht */
    }

    /* --- 10. "Kaputt"-Zustand --- */
    .coffee-machine.broken .machine-head,
    .coffee-machine.broken .machine-body {
      background: var(--color-broken-main);
      animation: shake 0.5s infinite;
      border-color: var(--color-broken-shadow);
    }
    .coffee-machine.broken .machine-head {
      box-shadow: 0 0 25px 10px var(--color-broken-glow), inset 0 0 10px #ffadad;
    }
    /* Glitch-Effekt auf Licht */
    .coffee-machine.broken .brew-light {
      animation: glitch-light 0.3s infinite;
    }
    @keyframes glitch-light {
      0% { background: var(--color-broken-main);
      box-shadow: 0 0 10px var(--color-broken-main); }
      30% { background: var(--color-brew-light-off); box-shadow: none;
      }
      60% { background: #ff0; box-shadow: 0 0 10px #ff0;
      }
      100% { background: var(--color-broken-main); box-shadow: 0 0 10px var(--color-broken-main);
      }
    }
    .container.is-broken {
      box-shadow: 0 8px 32px 0 var(--color-broken-glow);
    }
    @keyframes shake {
      0% { transform: translate(1px, 1px) rotate(0deg);
      }
      10% { transform: translate(-1px, -2px) rotate(-1deg);
      }
      20% { transform: translate(-3px, 0px) rotate(1deg);
      }
      30% { transform: translate(3px, 2px) rotate(0deg);
      }
      40% { transform: translate(1px, -1px) rotate(1deg);
      }
      50% { transform: translate(-1px, 2px) rotate(-1deg);
      }
      60% { transform: translate(-3px, 1px) rotate(0deg);
      }
      70% { transform: translate(3px, 1px) rotate(-1deg);
      }
      80% { transform: translate(-1px, -1px) rotate(1deg);
      }
      90% { transform: translate(1px, 2px) rotate(0deg);
      }
      100% { transform: translate(1px, -2px) rotate(-1deg);
      }
    }
    
    /* --- 11. Einstellungs-Panel (L3) --- */
    .settings-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transition: opacity var(--timing-fast) ease-in-out;
    }
    .settings-backdrop.is-visible {
      opacity: 1;
      pointer-events: all;
    }
    
    .settings-panel {
      position: fixed;
      top: 0;
      right: 0;
      width: 300px;
      height: 100%;
      background: var(--color-settings-bg);
      border-left: 2px solid var(--color-settings-border);
      box-shadow: -5px 0 25px rgba(0,0,0,0.2);
      z-index: 101;
      transform: translateX(100%);
      transition: transform var(--timing-fast) ease-in-out, background var(--timing-med), border var(--timing-med);
      padding: 20px;
      color: var(--color-text-primary);
    }
    .settings-panel.is-visible {
      transform: translateX(0);
    }
    
    .settings-panel h2 {
      margin-top: 0;
      color: var(--color-text-secondary);
      border-bottom: 2px solid var(--color-container-border);
      padding-bottom: 10px;
    }
    .settings-group {
      margin-bottom: 20px;
    }
    .settings-group label {
      display: block;
      margin-bottom: 5px;
      font-weight: 600;
      color: var(--color-text-secondary);
    }
    .settings-group input, .settings-group select {
      width: 100%;
      padding: 8px;
      border-radius: 6px;
      border: 1px solid var(--color-settings-border);
      background: var(--color-settings-input-bg);
      color: var(--color-text-primary);
      font-family: var(--font-main);
      font-size: 16px;
    }
    
    #saveSettingsBtn {
      width: 100%;
    }

    /* --- 12. Globale UI-Steuerung --- */
    .global-controls {
      position: absolute;
      top: 15px;
      right: 15px;
      display: flex;
      gap: 10px;
      z-index: 20;
    }

    /* --- 13. Responsive Anpassungen --- */
    @media (max-width: 450px) {
      .container {
        padding: 20px 25px;
      }
      .global-controls {
        top: 10px;
        right: 10px;
      }
      .icon-button {
        padding: 8px 10px;
      }
      #timerDisplay { font-size: 2.8rem;
      }
      button { padding: 10px 18px; font-size: 16px;
      }
      .settings-panel { width: 100%;
      }
    }

  </style>
</head>
<body>

  <audio id="audio-start" src="path/to/your/start-work.mp3" preload="auto"></audio>
  <audio id="audio-brew" src="path/to/your/brewing.mp3" preload="auto"></audio>
  <audio id="audio-done" src="path/to/your/timer-done.mp3" preload="auto"></audio>
  <audio id="audio-break" src="path/to/your/machine-break.mp3" preload="auto"></audio>
  <audio id="audio-click" src="path/to/your/click.mp3" preload="auto"></audio>
  <audio id="audio-drip" src="path/to/your/drip.mp3" preload="auto"></audio>

  <div class="particles">
    <div class="particle"></div><div class="particle"></div><div class="particle"></div><div class="particle"></div><div class="particle"></div>
  </div>

  <div class="container" id="container">
    
    <div class="global-controls">
      <button id="settingsBtn" class="icon-button" aria-label="Einstellungen">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19.14, 12.94c0.04-0.3, 0.06-0.61, 0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14, 0.23-0.41, 0.12-0.61l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39, 0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4, 2.81C14.36, 2.59, 14.18, 2.4, 13.96, 2.4h-3.92c-0.22, 0-0.4, 0.19-0.44, 0.41L9.16, 5.57C8.57, 5.8, 8.04, 6.12, 7.54, 6.5L5.15, 5.54c-0.22-0.07-0.47, 0-0.59, 0.22L2.64, 9.08c-0.11, 0.2-0.06, 0.47, 0.12, 0.61l2.03, 1.58C4.74, 11.6, 4.72, 11.9, 4.72, 12.23c0, 0.32, 0.02, 0.64, 0.07, 0.94l-2.03, 1.58c-0.18, 0.14-0.23, 0.41-0.12, 0.61l1.92, 3.32c0.12, 0.22, 0.37, 0.29, 0.59, 0.22l2.39-0.96c0.5, 0.38, 1.03, 0.7, 1.62, 0.94l0.44, 2.76C9.6, 21.41, 9.78, 21.6, 10.04, 21.6h3.92c0.22, 0, 0.4-0.19, 0.44-0.41l0.44-2.76c0.59-0.23, 1.12-0.56, 1.62-0.94l2.39, 0.96c0.22, 0.07, 0.47, 0, 0.59-0.22l1.92-3.32c0.12-0.2-0.05-0.47-0.12-0.61L19.14, 12.94z M12, 15.6c-1.98, 0-3.6-1.62-3.6-3.6s1.62-3.6, 3.6-3.6s3.6, 1.62, 3.6, 3.6S13.98, 15.6, 12, 15.6z"></path></svg>
      </button>
    </div>

    <div class="coffee-machine" id="coffeeMachine">
      <div class="machine-head"></div>
      <div class="machine-body">
        <div class="brew-light"></div>
      </div>
      <div class="machine-base"></div>
      <div class="machine-spout" id="machineSpout"></div>
      <div class="machine-steam" id="machineSteam">
        <div class="machine-steam-cloud"></div>
        <div 
class="machine-steam-cloud"></div>
        <div class="machine-steam-cloud"></div>
      </div>
    </div>
    
    <div class="coffee-stream" id="coffeeStream"></div>
    <div class="coffee-drip" id="coffeeDrip"></div>
    
    <div class="coffee-cup" aria-label="Kaffeetasse" id="coffeeCup">
      <div class="coffee-handle"></div>
      <div class="coffee-fill" id="coffeeFill"></div> 
      <div class="coffee-steam" id="coffeeSteam">
        <div class="steam-cloud"></div>
        <div class="steam-cloud"></div>
        <div class="steam-cloud"></div>
 
      </div>
    </div>
    
    <div id="timerDisplay" aria-live="polite">25:00</div>
    <div class="status" id="statusMsg" aria-live="polite">Bereit für die Arbeit?</div>
    
    <div class="cycle-tracker" id="cycleTracker">
      <span class="cycle-dot"></span><span class="cycle-dot"></span><span class="cycle-dot"></span><span class="cycle-dot"></span>
    </div>

    <div class="button-group">
      <button id="mainBtn">Start</button>
      <button id="pauseBtn" disabled>Pause</button>
      <button id="resetBtn">Reset</button>
    </div>
    <div>
      <button id="repairBtn">Reparieren</button>
    </div>
 
  </div>

  <div class="settings-backdrop" id="settingsBackdrop"></div>
  <div class="settings-panel" id="settingsPanel">
    <h2>Einstellungen</h2>
    
    <div class="settings-group">
      <label for="theme-select">Theme</label>
      <select id="theme-select">
        <option value="theme-dark">Dark Roast</option>
        <option value="theme-light">Light Roast</option>
      </select>
    </div>

    <div class="settings-group">
      <label for="work-minutes">Arbeitszeit (Minuten)</label>
      <input type="number" id="work-minutes" min="1" value="25">
    </div>

    <div class="settings-group">
  
      <label for="short-break-minutes">Kurze Pause (Minuten)</label>
      <input type="number" id="short-break-minutes" min="1" value="5">
    </div>

    <div class="settings-group">
      <label for="long-break-minutes">Lange Pause (Minuten)</label>
      <input type="number" id="long-break-minutes" min="1" value="15">
    </div>

    <button id="saveSettingsBtn" class="icon-button">Speichern & Schließen</button>
  </div>

<script>
  /**
   * Ultimate Coffee Pomodoro Timer (Level 6.1 - Final Polish)
   * FIX 1: Kaffeestrahl startet 5px höher.
   * FIX 2: Asymmetrisches SVG-Icon für Einstellungen ersetzt.
   */
  class PomodoroTimer {
    constructor() {
      // --- 1. Konfiguration & Standardwerte ---
      this.config = {
        work: 25 * 60,
        shortBreak: 5 * 60,
        longBreak: 15 * 60,
        breakdownLimit: 20 * 60
      };

      // --- 2. Zustands-Variablen (State) ---
      this.state = {
        timer: null,
        currentTime: this.config.work,
        currentTimerDuration: this.config.work,
        isWorkPhase: true,
        isPaused: false,
        firstStart: true,
        cycleCount: 0,
        coffeeLevel: 100, // Startet bei 100%
   
        machineBroken: false,
        breakCheckStartTime: null,
        isMuted: false
      };
      
      // --- 3. DOM-Elemente ---
      this.elements = {
        container: document.getElementById('container'),
        coffeeFill: document.getElementById('coffeeFill'),
        coffeeSteam: document.getElementById('coffeeSteam'),
        timerDisplay: document.getElementById('timerDisplay'),
        statusMsg: document.getElementById('statusMsg'),
        mainBtn: document.getElementById('mainBtn'),
        pauseBtn: document.getElementById('pauseBtn'),
        resetBtn: document.getElementById('resetBtn'),
        repairBtn: document.getElementById('repairBtn'),
       
        coffeeMachine: document.getElementById('coffeeMachine'),
        machineSteam: document.getElementById('machineSteam'),
        machineSpout: document.getElementById('machineSpout'),
        coffeeStream: document.getElementById('coffeeStream'),
        coffeeDrip: document.getElementById('coffeeDrip'),
        coffeeCup: document.getElementById('coffeeCup'),
        cycleTracker: document.getElementById('cycleTracker'),
        
        // Einstellungen (L3)
        settingsBtn: document.getElementById('settingsBtn'),
        settingsPanel: document.getElementById('settingsPanel'),
     
        settingsBackdrop: document.getElementById('settingsBackdrop'),
        saveSettingsBtn: document.getElementById('saveSettingsBtn'),
        themeSelect: document.getElementById('theme-select'),
        workInput: document.getElementById('work-minutes'),
        shortBreakInput: document.getElementById('short-break-minutes'),
        longBreakInput: document.getElementById('long-break-minutes'),

        // Mute (L3)
        muteBtn: document.getElementById('muteBtn'),
        iconUnmuted: document.getElementById('icon-unmuted'),
        iconMuted: document.getElementById('icon-muted')
      };
      // --- 4. Audio-Elemente ---
      this.audio = {
        start: document.getElementById('audio-start'),
        brew: document.getElementById('audio-brew'),
        done: document.getElementById('audio-done'),
        break: document.getElementById('audio-break'),
        click: document.getElementById('audio-click'),
        drip: document.getElementById('audio-drip')
      };
      // --- 5. Initialisierung ---
      this.bindEvents();
      this.init();
    }

    /**
     * Bindet alle Event-Listener.
     */
    bindEvents() {
      this.elements.mainBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.toggleMainBtn();
      });
      this.elements.pauseBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.togglePauseBtn();
      });
      this.elements.resetBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.resetTimer();
      });
      this.elements.repairBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.repairMachine();
      });
      // L3 Event-Listener
      this.elements.settingsBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.toggleSettings(true);
      });
      this.elements.settingsBackdrop.addEventListener('click', () => this.toggleSettings(false));
      this.elements.saveSettingsBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.saveSettings();
      });
      this.elements.muteBtn.addEventListener('click', () => {
        this.playAudio('click');
        this.toggleMute();
      });
      this.elements.themeSelect.addEventListener('change', () => this.applyTheme());
    }

    /**
     * Initialisiert den Timer beim Laden.
     */
    init() {
      // Gespeichertes Theme laden
      const savedTheme = localStorage.getItem('pomodoroTheme') || 'theme-dark';
      document.documentElement.className = savedTheme;
      this.elements.themeSelect.value = savedTheme;

      // Zeiten aus Config in UI laden
      this.elements.workInput.value = this.config.work / 60;
      this.elements.shortBreakInput.value = this.config.shortBreak / 60;
      this.elements.longBreakInput.value = this.config.longBreak / 60;
      
      this.state.currentTime = this.config.work;
      this.state.currentTimerDuration = this.config.work;
      this.state.coffeeLevel = 100; // Startet voll

      this.updateTimerDisplay(this.state.currentTime);
      this.updateCoffeeFill();
      this.updateCycleTracker();
      this.setCupSteaming(false); // Startet nicht dampfend
      this.setMachineWorking(false);
      this.showCoffeeStream(false);
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = true;
    }

    // --- 6. Kern-Timer-Logik ---

    /**
     * Der Haupt-Tick, wird jede Sekunde ausgeführt.
     */
    tick() {
      if (this.state.isPaused || this.state.machineBroken) return;

      this.state.currentTime--;
      this.updateTimerDisplay(this.state.currentTime);

      if (this.state.isWorkPhase) {
        // --- ARBEITSPHASE ---
        // Kaffeestand leert sich während der Arbeit
        this.state.coffeeLevel = Math.max(0, (this.state.currentTime / this.state.currentTimerDuration) * 100);
        this.updateCoffeeFill();

      } else {
        // --- PAUSENPHASE (NEUE LOGIK) ---
        // Kaffeestand füllt sich während der Pause
        const timeElapsed = this.state.currentTimerDuration - this.state.currentTime;
        // Sicherstellen, dass die Dauer nicht 0 ist, um NaN zu vermeiden
        const duration = this.state.currentTimerDuration || 1; 
        const progress = Math.min(1, timeElapsed / duration);
        this.state.coffeeLevel = Math.max(0, progress * 100);
        this.updateCoffeeFill();
        
        // Kaffeestrahl-Logik
        if (progress < 1) {
          this.showCoffeeStream(true);
          this.updateStreamPosition(); // Strahl dynamisch anpassen
        } else {
          this.showCoffeeStream(false);
        }

        // Maschine stoppen, wenn Tasse voll ist (auch wenn Pause weiterläuft)
        // (Prüft, ob Maschine 'is-working', um dies nur einmal auszulösen)
        if (progress >= 1 && this.elements.coffeeMachine.classList.contains('is-working')) {
          this.setMachineWorking(false);
          this.setCupSteaming(true);
          this.playDripAnimation(); // Spielt Tropfen ab, wenn voll
        }
      }

      // Prüft, ob die Maschine kaputt geht (während der Pause)
      if (!this.state.isWorkPhase && this.state.breakCheckStartTime) {
        const breakDuration = (Date.now() - this.state.breakCheckStartTime) / 1000;
        if (breakDuration > this.config.breakdownLimit) {
          this.breakMachine();
          return;
        }
      }

      // Timer ist abgelaufen, Phasen-Wechsel
      if (this.state.currentTime < 0) {
        this.transitionState();
      }
    }

    startTimer() {
      if (this.state.timer) clearInterval(this.state.timer);
      this.state.timer = setInterval(() => this.tick(), 1000);
    }

    stopTimer() {
      if (this.state.timer) clearInterval(this.state.timer);
      this.state.timer = null;
    }

    /**
     * Wechselt zwischen Arbeits- und Pausenphase.
     */
    transitionState() {
      this.stopTimer();
      this.playAudio('done');
      
      // Stoppe Füll-Animationen (Strahl/Maschine) sofort
      this.showCoffeeStream(false);
      this.setMachineWorking(false); // Stoppt Maschine in jedem Fall

      if (this.state.isWorkPhase) {
        // --- Von Arbeit ZU Pause ---
        this.state.cycleCount++;
        this.state.isWorkPhase = false;
        this.state.breakCheckStartTime = Date.now();
        
        if (this.state.cycleCount % 4 === 0) {
          this.state.currentTime = this.config.longBreak;
          this.elements.statusMsg.textContent = "Lange Pause! Kaffee wird gebrüht...";
        } else {
          this.state.currentTime = this.config.shortBreak;
          this.elements.statusMsg.textContent = "Kurze Pause. Kaffee wird gebrüht...";
        }
        this.state.currentTimerDuration = this.state.currentTime;
        this.elements.mainBtn.textContent = "Pause überspringen";
        
        // Tasse vor dem Füllen leeren
        this.state.coffeeLevel = 0;
        this.updateCoffeeFill(); // Tasse sofort leeren
        
        this.setMachineWorking(true); // Maschine AN
        this.setCupSteaming(false); // Leere Tasse dampft nicht
        this.showCoffeeStream(true); // Strahl AN
        this.updateStreamPosition(); // Strahl positionieren
        this.playAudio('brew');
        
      } else {
        // --- Von Pause ZU Arbeit ---
        this.state.isWorkPhase = true;
        this.state.breakCheckStartTime = null;
        this.state.currentTime = this.config.work;
        this.state.currentTimerDuration = this.config.work;
        this.elements.statusMsg.textContent = "Arbeitsphase: Lernen";
        this.elements.mainBtn.textContent = "Pause einlegen";
        
        // Tasse ist jetzt 100% voll (wird von tick() erledigt, aber hier zur Sicherheit)
        this.state.coffeeLevel = 100;
        this.updateCoffeeFill();
        
        this.setMachineWorking(false);
        this.setCupSteaming(false); // Tasse dampft nur am Ende der Pause
        this.playAudio('start');
      }
      
      this.updateTimerDisplay(this.state.currentTime);
      this.updateCycleTracker();
      this.startTimer();
    }

    // --- 7. Tasten-Aktionen & Event-Handler ---

    toggleMainBtn() {
      if (this.state.machineBroken) return;
      this.state.isPaused = false;

      // Erster Start überhaupt
      if (this.state.firstStart) {
        this.state.firstStart = false;
        this.elements.mainBtn.textContent = "Pause einlegen";
        this.elements.pauseBtn.disabled = false;
        this.elements.resetBtn.disabled = false;
        this.playAudio('start');
        this.startTimer();
        return;
      }

      // Timer läuft (Arbeit ODER Pause) -> Phase überspringen
      if (this.state.timer && !this.state.isPaused) {
        this.transitionState();
        return;
      } 
      
      // Timer war pausiert (Jetzt: Fortsetzen)
      this.elements.pauseBtn.disabled = false;
      this.elements.mainBtn.textContent = this.state.isWorkPhase ? "Pause einlegen" : "Pause überspringen";
      this.elements.statusMsg.textContent = this.state.isWorkPhase ? "Arbeitsphase: Lernen" : "Pause läuft...";
      
      // Animationen wieder aufnehmen
      if (!this.state.isWorkPhase) {
          // Pause (Brühvorgang) wird fortgesetzt
          if (this.state.coffeeLevel < 100) {
            // Tasse ist noch nicht voll
            this.setMachineWorking(true);
            this.showCoffeeStream(true);
          } else {
            // Tasse ist bereits voll
            this.setMachineWorking(false);
            this.showCoffeeStream(false);
            this.setCupSteaming(true);
          }
      }
      
      this.startTimer();
    }

    togglePauseBtn() {
      if (this.state.machineBroken || this.state.firstStart) return;

      this.state.isPaused = true;
      this.stopTimer();
      
      this.elements.statusMsg.textContent = "Timer pausiert.";
      this.elements.pauseBtn.disabled = true;
      this.elements.mainBtn.textContent = this.state.isWorkPhase ? "Weiter lernen" : "Pause fortsetzen";
      
      // Visuelle Effekte pausieren
      this.setMachineWorking(false);
      this.showCoffeeStream(false); // Strahl stoppen
      this.setCupSteaming(false);
    }

    resetTimer(applySettings = false) {
      if (this.state.machineBroken) return;
      
      this.stopTimer();

      this.state.isWorkPhase = true;
      this.state.isPaused = false;
      this.state.firstStart = true;
      this.state.cycleCount = 0;
      this.state.currentTime = this.config.work;
      this.state.currentTimerDuration = this.config.work;
      this.state.coffeeLevel = 100; // Zurücksetzen auf voll
      this.state.breakCheckStartTime = null;

      // UI zurücksetzen
      this.updateTimerDisplay(this.state.currentTime);
      this.updateCoffeeFill();
      this.updateCycleTracker();
      this.setMachineWorking(false);
      this.setCupSteaming(false);
      this.showCoffeeStream(false);
      this.elements.statusMsg.textContent = applySettings ? "Einstellungen gespeichert. Bereit?" : "Bereit für die Arbeit?";
      this.elements.mainBtn.textContent = "Start";
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = true;
    }

    breakMachine() {
      this.state.machineBroken = true;
      this.stopTimer();
      this.playAudio('break');

      this.elements.coffeeMachine.classList.add('broken');
      this.elements.container.classList.add('is-broken');
      this.setMachineWorking(false);
      this.setCupSteaming(false);
      this.showCoffeeStream(false);

      this.elements.statusMsg.textContent = "Maschine überhitzt! Reparieren.";
      this.elements.mainBtn.disabled = true;
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = true;
      this.elements.repairBtn.style.display = 'inline-block';
    }

    repairMachine() {
      this.state.machineBroken = false;
      this.elements.coffeeMachine.classList.remove('broken');
      this.elements.container.classList.remove('is-broken');
      this.elements.repairBtn.style.display = 'none';
      
      this.elements.mainBtn.disabled = false;
      this.elements.pauseBtn.disabled = true;
      this.elements.resetBtn.disabled = false;
      
      this.resetTimer();
      this.elements.statusMsg.textContent = "Maschine repariert. Starte eine neue Session.";
    }

    // --- 8. Visuelle Hilfsfunktionen (L3/L5) ---
    
    /**
     * Berechnet die Position des Kaffeestrahls von der Tülle
     * bis zur aktuellen Kaffeeoberfläche.
     */
    updateStreamPosition() {
      // Breche ab, wenn der Strahl nicht sichtbar sein soll
      if (this.elements.coffeeStream.style.display === 'none' || this.state.coffeeLevel >= 100) {
        this.showCoffeeStream(false); // Sicherheitshalber Strahl ausblenden
        return;
      }
      
      const containerRect = this.elements.container.getBoundingClientRect();
      const cupRect = this.elements.coffeeCup.getBoundingClientRect();
      const spoutRect = this.elements.machineSpout.getBoundingClientRect();
      
      // Absolute Positionen
      const containerTop = containerRect.top + window.scrollY;
      
      // Position der Tüllen-Unterkante (relativ zum Dokument)
      const spoutBottom = spoutRect.bottom;
      
      // Kaffee-Oberfläche berechnen (relativ zum Dokument)
      // (Fügt 2px Puffer hinzu, damit der Strahl die Welle berührt)
      const fillHeight = (this.state.coffeeLevel / 100) * (cupRect.height - 2); 
      const fillTopAbsolute = cupRect.bottom - fillHeight; // Oberkante des Kaffees

      // Positionen relativ zum Container
      // FIX: Strahl startet 5px höher (negativer Offset)
      const streamTop = (spoutBottom - containerRect.top) - 5;
      const streamEnd = fillTopAbsolute - containerRect.top;
      
      let streamHeight = streamEnd - streamTop;
      
      // Strahl-Position
      const spoutCenterX = spoutRect.left + (spoutRect.width / 2) - containerRect.left;
      
      if (streamHeight > 0) {
        this.elements.coffeeStream.style.top = `${streamTop}px`;
        this.elements.coffeeStream.style.height = `${streamHeight}px`;
        this.elements.coffeeStream.style.left = `${spoutCenterX - 4}px`; // 4 = hälfte der Strahlbreite (8px)
      } else {
        // Wenn Tasse fast voll ist, Strahl ausblenden
        this.showCoffeeStream(false);
      }
    }
    
    /**
     * Zeigt den Kaffeestrahl (oder blendet ihn aus).
     */
    showCoffeeStream(on) {
      this.elements.coffeeStream.style.display = on ? 'block' : 'none';
    }

    /**
     * Spielt die "Nachtropfen"-Animation ab.
     */
    playDripAnimation() {
      const containerRect = this.elements.container.getBoundingClientRect();
      const spoutRect = this.elements.machineSpout.getBoundingClientRect();
      
      const dripTop = spoutRect.bottom - containerRect.top;
      const dripLeft = spoutRect.left + (spoutRect.width / 2) - containerRect.left - 3;
      // 3 = hälfte Tropfenbreite
      
      this.elements.coffeeDrip.style.top = `${dripTop}px`;
      this.elements.coffeeDrip.style.left = `${dripLeft}px`;
      
      // Animation durch Klasse auslösen
      this.elements.coffeeDrip.classList.remove('is-dripping');
      
      // Kurzer Timeout, um "reflow" zu erzwingen, falls Klasse schon da war
      setTimeout(() => {
        this.elements.coffeeDrip.classList.add('is-dripping');
        this.playAudio('drip');
      }, 10);
    }

    setMachineWorking(isWorking) {
      this.elements.coffeeMachine.classList.toggle('is-working', isWorking);
    }

    setCupSteaming(steaming) {
      this.elements.coffeeSteam.style.display = steaming ? 'block' : 'none';
    }

    updateCoffeeFill() {
      this.elements.coffeeFill.style.height = `${Math.max(0, Math.min(100, this.state.coffeeLevel))}%`;
    }

    updateTimerDisplay(seconds) {
      // Stellt sicher, dass 00:00 angezeigt wird, nicht negative Zahlen
      const displaySeconds = Math.max(0, seconds);
      let m = Math.floor(displaySeconds / 60);
      let s = displaySeconds % 60;
      this.elements.timerDisplay.textContent = `${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
    }

    updateCycleTracker() {
      const dots = this.elements.cycleTracker.querySelectorAll('.cycle-dot');
      dots.forEach((dot, index) => {
        dot.classList.toggle('filled', index < (this.state.cycleCount % 4));
      });
      
      // Alle füllen, wenn 4. Zyklus erreicht ist
      if (this.state.cycleCount > 0 && this.state.cycleCount % 4 === 0) {
        dots.forEach(dot => dot.classList.add('filled'));
      }
    }

    // --- 9. Neue L3-Funktionen (Settings, Mute, Theme) ---

    toggleSettings(show) {
      this.elements.settingsPanel.classList.toggle('is-visible', show);
      this.elements.settingsBackdrop.classList.toggle('is-visible', show);
    }

    saveSettings() {
      // Eingaben validieren und in Sekunden umrechnen
      const workMin = parseInt(this.elements.workInput.value) || 25;
      const shortMin = parseInt(this.elements.shortBreakInput.value) || 5;
      const longMin = parseInt(this.elements.longBreakInput.value) || 15;

      this.config.work = workMin * 60;
      this.config.shortBreak = shortMin * 60;
      this.config.longBreak = longMin * 60;
      
      // UI aktualisieren und Timer zurücksetzen
      this.elements.workInput.value = workMin;
      this.elements.shortBreakInput.value = shortMin;
      this.elements.longBreakInput.value = longMin;
      
      this.toggleSettings(false);
      this.resetTimer(true); // 'true' für spezielle Reset-Nachricht
    }
    
    toggleMute() {
      this.state.isMuted = !this.state.isMuted;
      this.elements.iconUnmuted.style.display = this.state.isMuted ? 'none' : 'block';
      this.elements.iconMuted.style.display = this.state.isMuted ? 'block' : 'none';
    }

    applyTheme() {
      const selectedTheme = this.elements.themeSelect.value;
      document.documentElement.className = selectedTheme;
      localStorage.setItem('pomodoroTheme', selectedTheme);
    }

    playAudio(soundId) {
      if (this.state.isMuted) return;
      try {
        const sound = this.audio[soundId];
        if (sound) {
          sound.currentTime = 0;
          sound.play().catch(e => console.log("Audio-Wiedergabe blockiert: ", e));
        }
      } catch (e) {
        console.error("Audio-Fehler: ", e);
      }
    }
  }

  // Initialisiere die App, sobald das DOM geladen ist.
  document.addEventListener('DOMContentLoaded', () => {
    const timerApp = new PomodoroTimer();
  });
  
</script>
</body>
</html>
            """
        self.browser.setHtml(self.html)