#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pro_snake_html.py
PyQt5 plugin that embeds the original Snake single-file HTML (kept exactly as provided).
"""

import sys
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("SNAKE v2")
        self.resize(700, 520)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)
        self.browser.setFocus()  # wichtig für Tastatursteuerung

        # The HTML is embedded exactly as provided by you (no changes).
        self.html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Snake – Single File</title>
<style>
  :root{
    --bg:#0e1320; --board:#0b1020; --grid:#1b2540;
    --snake:#4cd964; --snake-head:#2ab84a; --food:#ff6b6b;
    --text:#e8eefc; --muted:#9aa6c3; --accent:#7aa2f7;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; background:linear-gradient(135deg,#0b0f1a,#10172a);
    color:var(--text); font:15px/1.4 system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    display:grid; place-items:center; padding:18px;
  }
  .app{
    width:min(96vw,900px); background:#0e1423; border:1px solid #1f2a44; border-radius:14px; overflow:hidden;
    box-shadow:0 10px 30px rgba(0,0,0,.35);
  }
  header{
    display:grid; grid-template-columns:1fr auto 1fr; gap:10px; align-items:center;
    padding:12px 14px; background:#0c1322; border-bottom:1px solid #1f2a44;
  }
  h1{margin:0; font-size:16px; text-align:center; color:var(--muted); letter-spacing:.5px}
  .stats{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
  .chip{
    padding:6px 10px; background:#0b1220; border:1px solid #223154; border-radius:8px;
    min-width:90px; text-align:center; font-variant-numeric:tabular-nums; color:var(--accent)
  }
  .controls{display:flex; gap:8px; justify-content:flex-end; align-items:center; flex-wrap:wrap}
  select,button{
    background:#17213a; color:var(--text); border:1px solid #2a3550; border-radius:8px; padding:8px 10px;
    cursor:pointer; font-weight:600
  }
  button:hover{background:#213055}
  main{padding:14px}
  .board-wrap{
    background:var(--board); border:1px solid #1e2638; border-radius:12px; padding:10px;
    display:grid; place-items:center;
  }
  canvas{width:100%; height:auto; display:block; image-rendering:pixelated; background:#0a0f1f; border-radius:8px}
  .help{margin-top:10px; text-align:center; color:var(--muted); font-size:13px}
  .status{margin-top:10px; text-align:center}
  .ok{color:#4cd964; font-weight:700}
  .fail{color:#ff6b6b; font-weight:700}
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="stats">
      <div class="chip">Score: <span id="score">0</span></div>
      <div class="chip">Highscore: <span id="hiscore">0</span></div>
      <div class="chip">Speed: <span id="speed">1.00x</span></div>
    </div>
    <h1>Snake</h1>
    <div class="controls">
      <select id="sizeSel" title="Spielfeld">
        <option value="20x20">20 × 20</option>
        <option value="24x18" selected>24 × 18</option>
        <option value="32x20">32 × 20</option>
        <option value="40x24">40 × 24</option>
        <option value="custom">Custom…</option>
      </select>
      <button id="btnPause">Pause</button>
      <button id="btnReset">Neu</button>
    </div>
  </header>
  <main>
    <div class="board-wrap">
      <canvas id="game" width="960" height="720" aria-label="Snake Canvas"></canvas>
    </div>
    <div class="help">Steuerung: Pfeile oder WASD • <kbd>Leertaste</kbd>/<kbd>P</kbd> = Pause • <kbd>R</kbd> = Neustart</div>
    <div id="status" class="status" aria-live="polite"></div>
  </main>
</div>

<script>
(() => {
  // ==== DOM ====
  const cvs = document.getElementById('game');
  const ctx = cvs.getContext('2d');
  const scoreEl = document.getElementById('score');
  const hiscoreEl = document.getElementById('hiscore');
  const speedEl = document.getElementById('speed');
  const statusEl = document.getElementById('status');
  const btnPause = document.getElementById('btnPause');
  const btnReset = document.getElementById('btnReset');
  const sizeSel = document.getElementById('sizeSel');

  // ==== Config / State ====
  let COLS = 24, ROWS = 18;      // Grid
  let CELL = 32;                  // Pixel pro Zelle (wird beim Resize dynamisch skaliert)
  let tickBase = 140;             // ms pro Schritt (Basis)
  const speedRamp = 0.985;        // Multiplier pro gefressenes Food
  let tick = tickBase;            // aktuelles Taktintervall
  let runId = null, lastStep = 0;
  let paused = false, gameOver = false;
  let dir = {x:1,y:0}, nextDir = {x:1,y:0};
  let snake = [];                 // Array von Segmenten {x,y}
  let food = {x:0,y:0};
  let score = 0;
  const LSKEY = 'snake_hiscore_v1';

  // ==== Helpers ====
  const rnd = (n) => Math.floor(Math.random()*n);
  const clamp = (n,min,max)=>Math.max(min,Math.min(max,n));
  function setStatus(text, ok){
    statusEl.innerHTML = text ? `<span class="${ok?'ok':'fail'}">${text}</span>` : '';
  }
  function loadHiscore(){
    let v = parseInt(localStorage.getItem(LSKEY) || '0', 10);
    if (!Number.isFinite(v)) v = 0;
    hiscoreEl.textContent = v;
    return v;
  }
  function saveHiscore(v){
    localStorage.setItem(LSKEY, String(v));
    hiscoreEl.textContent = v;
  }

  // ==== Resize / Canvas Fit ====
  function fitCanvas(){
    // Ziel: integer multiples, damit Pixel sauber sind
    const wrap = cvs.parentElement.getBoundingClientRect();
    const maxW = Math.floor(wrap.width - 4);
    const maxH = Math.floor(maxW * (ROWS/COLS));
    // set internal resolution to grid size * cell size
    CELL = Math.floor(Math.min(maxW / COLS, (wrap.height||1000) / ROWS));
    if (CELL < 8) CELL = 8;
    cvs.width = COLS * CELL;
    cvs.height = ROWS * CELL;
    draw(true);
  }
  new ResizeObserver(fitCanvas).observe(cvs.parentElement);

  // ==== Game Setup ====
  function newGame(){
    gameOver = false; paused = false; setStatus('');
    dir = {x:1,y:0}; nextDir = {x:1,y:0};
    tick = tickBase;
    score = 0; scoreEl.textContent = '0'; speedEl.textContent = '1.00x';
    // Schlange mittig, Länge 4
    const sx = Math.floor(COLS/3), sy = Math.floor(ROWS/2);
    snake = [{x:sx, y:sy},{x:sx-1,y:sy},{x:sx-2,y:sy},{x:sx-3,y:sy}];
    placeFood();
    stopLoop(); startLoop();
    fitCanvas();
  }

  function placeFood(){
    let x,y,occupied;
    do {
      x = rnd(COLS); y = rnd(ROWS);
      occupied = snake.some(s => s.x===x && s.y===y);
    } while(occupied);
    food.x = x; food.y = y;
  }

  // ==== Game Loop ====
  function startLoop(){
    lastStep = performance.now();
    runId = requestAnimationFrame(loop);
  }
  function stopLoop(){
    if (runId) cancelAnimationFrame(runId);
    runId = null;
  }
  function loop(now){
    if (paused || gameOver){ runId = requestAnimationFrame(loop); return; }
    if (now - lastStep >= tick){
      step();
      lastStep = now;
    }
    draw();
    runId = requestAnimationFrame(loop);
  }

  function step(){
    // Richtung aktualisieren (keine 180°-Dreher)
    if ((nextDir.x !== -dir.x) || (nextDir.y !== -dir.y)) dir = nextDir;

    const head = snake[0];
    const nx = head.x + dir.x;
    const ny = head.y + dir.y;

    // Kollision mit Wand?
    if (nx < 0 || nx >= COLS || ny < 0 || ny >= ROWS){
      return die();
    }
    // Kollision mit sich selbst?
    if (snake.some((s,i)=> i>0 && s.x===nx && s.y===ny)){
      return die();
    }

    // bewegen
    snake.unshift({x:nx,y:ny});

    // Food?
    if (nx===food.x && ny===food.y){
      score += 1; scoreEl.textContent = String(score);
      // beschleunigen
      tick = Math.max(50, tick * speedRamp);
      const factor = (tickBase / tick).toFixed(2) + 'x';
      speedEl.textContent = factor;
      placeFood();
    } else {
      // letztes Segment entfernen (Schwanz)
      snake.pop();
    }
  }

  function die(){
    gameOver = true; setStatus('Game Over – R zum Neustart', false);
    const hs = parseInt(hiscoreEl.textContent,10)||0;
    if (score > hs) saveHiscore(score);
  }

  // ==== Rendering ====
  function draw(forceBg=false){
    // Hintergrund
    if (forceBg){
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--board') || '#0b1020';
      ctx.fillRect(0,0,cvs.width,cvs.height);
    } else {
      // leicht transparent übermalen für weiches Flimmern vermeiden
      ctx.fillStyle = 'rgba(11,16,32,0.9)';
      ctx.fillRect(0,0,cvs.width,cvs.height);
    }

    // Grid
    const gcol = getComputedStyle(document.documentElement).getPropertyValue('--grid') || '#1b2540';
    ctx.strokeStyle = gcol;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x=1;x<COLS;x++){
      ctx.moveTo(x*CELL+0.5, 0); ctx.lineTo(x*CELL+0.5, cvs.height);
    }
    for (let y=1;y<ROWS;y++){
      ctx.moveTo(0, y*CELL+0.5); ctx.lineTo(cvs.width, y*CELL+0.5);
    }
    ctx.stroke();

    // Food
    drawCell(food.x, food.y, getVar('--food'));

    // Snake
    for (let i=snake.length-1;i>=0;i--){
      const s = snake[i];
      const isHead = i===0;
      drawCell(s.x, s.y, isHead ? getVar('--snake-head') : getVar('--snake'));
      if (isHead) drawEyes(s.x, s.y);
    }
  }

  function getVar(name){
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function drawCell(x,y,color){
    const px = x*CELL, py = y*CELL, r = Math.max(4, Math.floor(CELL*0.2));
    ctx.fillStyle = color || '#4cd964';
    roundRect(px+1, py+1, CELL-2, CELL-2, r, true, false);
  }

  function roundRect(x,y,w,h,r,fill,stroke){
    const rr = Math.min(r, w/2, h/2);
    ctx.beginPath();
    ctx.moveTo(x+rr,y);
    ctx.arcTo(x+w,y,x+w,y+h,rr);
    ctx.arcTo(x+w,y+h,x,y+h,rr);
    ctx.arcTo(x,y+h,x,y,rr);
    ctx.arcTo(x,y,x+w,y,rr);
    if (fill) ctx.fill();
    if (stroke) ctx.stroke();
  }

  function drawEyes(x,y){
    // kleine Augen auf dem Head je nach Richtung
    const cx = x*CELL, cy = y*CELL, m = Math.max(2, Math.floor(CELL*0.1));
    const ex = dir.x * Math.floor(CELL*0.18), ey = dir.y * Math.floor(CELL*0.18);
    ctx.fillStyle = '#0b0f1a';
    const rx1 = cx + Math.floor(CELL*0.35) + ex;
    const ry1 = cy + Math.floor(CELL*0.3) + ey;
    const rx2 = cx + Math.floor(CELL*0.65) + ex;
    const ry2 = cy + Math.floor(CELL*0.3) + ey;
    ctx.beginPath(); ctx.arc(rx1, ry1, m, 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(rx2, ry2, m, 0, Math.PI*2); ctx.fill();
  }

  // ==== Input ====
  window.addEventListener('keydown', (e)=>{
    const k = e.key.toLowerCase();
    if (k==='arrowup' || k==='w'){ next(-0, -1); }
    else if (k==='arrowdown' || k==='s'){ next(0, 1); }
    else if (k==='arrowleft' || k==='a'){ next(-1, 0); }
    else if (k==='arrowright' || k==='d'){ next(1, 0); }
    else if (k==='p' || k===' '){ togglePause(); }
    else if (k==='r'){ resetGame(); }
  }, {passive:true});

  function next(dx,dy){
    nextDir = {x:dx, y:dy};
  }

  function togglePause(){
    if (gameOver) return;
    paused = !paused;
    setStatus(paused ? 'Pause' : '', true);
  }

  // ==== Controls ====
  btnPause.addEventListener('click', togglePause);
  btnReset.addEventListener('click', resetGame);
  sizeSel.addEventListener('change', onSizeChange);

  function onSizeChange(){
    if (sizeSel.value === 'custom'){
      const cw = +prompt('Breite (Spalten, 10–80)', '28');
      const ch = +prompt('Höhe (Zeilen, 10–60)', '20');
      if (!Number.isFinite(cw) || !Number.isFinite(ch) || cw<10 || ch<10 || cw>80 || ch>60){
        alert('Ungültig – behalte aktuelle Größe.');
        return;
      }
      COLS = cw; ROWS = ch;
    } else {
      const [w,h] = sizeSel.value.split('x').map(Number);
      COLS = w; ROWS = h;
    }
    resetGame();
  }

  function resetGame(){
    // Highscore bleibt; alles andere neu
    newGame();
  }

  // ==== Boot ====
  loadHiscore();
  newGame();
})();
</script>
</body>
</html>"""

        # Load the HTML into the QWebEngineView
        self.browser.setHtml(self.html)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PluginWidget()
    w.show()
    sys.exit(app.exec_())
