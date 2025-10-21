# scripts/pro_sci_calculator_html.py
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):  # Default Light
        super().__init__()
        self.setWindowTitle("Wissenschaftlicher Taschenrechner")
        self.resize(600, 800)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        # HTML UI
        if mode == "Window":
            self.html = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Minesweeper (Win95 Style)</title>
<style>
  /* --- Farbpalette Windows 95 --- */
  :root{
    --win-gray:#c0c0c0;
    --win-dark:#404040;
    --win-mid:#808080;
    --win-light:#ffffff;
    --panel:#bdbdbd;
    --lcd-bg:#3a0000;
    --lcd-fg:#ff2b2b;
    --cell-face:#bdbdbd;
    --cell-deep:#9e9e9e;
    --n1:#0000ff; --n2:#008000; --n3:#ff0000;
    --n4:#000080; --n5:#800000; --n6:#008080;
    --n7:#000000; --n8:#808080;
  }

  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; background:#2e2e2e; display:flex; align-items:center; justify-content:center;
    font-family: "Tahoma", "MS Sans Serif", system-ui, sans-serif; user-select:none;
  }

  .win95-window{
    background:var(--win-gray);
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
    padding:8px; min-width:320px; max-width:95vw; border-radius:2px;
  }

  .titlebar{
    background:linear-gradient(#000080,#000060);
    color:#fff; padding:4px 8px; font-weight:700; margin-bottom:8px;
    display:flex; justify-content:space-between; align-items:center;
  }
  .titlebar .buttons{display:flex; gap:4px}
  .tb-btn{
    width:16px;height:16px;background:#c0c0c0;border:2px solid #404040;
    box-shadow: inset -1px -1px 0 var(--win-mid), inset 1px 1px 0 var(--win-light);
  }

  .panel{
    background:var(--panel);
    padding:6px;
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
    display:grid; grid-template-columns: 1fr auto 1fr; align-items:center; gap:6px; margin-bottom:6px;
  }
  .lcd{
    justify-self:start;
    display:inline-block; min-width:64px; text-align:right;
    padding:2px 4px;
    background:var(--lcd-bg); color:var(--lcd-fg);
    font-family: "Lucida Console", "Courier New", monospace;
    font-weight:900; font-size:22px; line-height:1;
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 #200000, inset 2px 2px 0 #5c0000;
  }
  .smiley{
    justify-self:center; width:34px;height:34px; font-size:20px; line-height:1;
    background:var(--win-gray);
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
    display:grid; place-items:center; cursor:pointer;
  }
  .toolbar{
    display:flex; gap:6px; align-items:center; margin-bottom:6px;
  }
  select, button{
    font: 13px "MS Sans Serif", Tahoma, sans-serif;
    padding:3px 6px; background:var(--win-gray); cursor:pointer;
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
  }

  .board-wrap{
    background:var(--panel); padding:6px;
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
  }

  .board{
    display:grid; gap:0;
    background:var(--win-mid);
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
  }

  .cell{
    width:24px; height:24px; display:grid; place-items:center; font-weight:700; font-size:16px;
    background:var(--cell-face);
    border-right:1px solid var(--win-light);
    border-bottom:1px solid var(--win-light);
    border-left:1px solid var(--win-mid);
    border-top:1px solid var(--win-mid);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
    cursor:pointer;
  }
  .cell:active{filter:brightness(.96)}
  .cell.revealed{
    background:#d6d6d6;
    box-shadow: inset 1px 1px 0 var(--win-mid), inset -1px -1px 0 var(--win-light);
    cursor:default;
    border:1px solid var(--win-mid);
  }
  .cell.flag::after{content:"⚑"; font-size:16px; color:#000; filter:drop-shadow(0 0 0 #f00); }
  .cell.mine::after{content:"●"; color:#000; font-size:14px}
  .bang{background:#ff6961 !important}

  .n1{color:var(--n1)} .n2{color:var(--n2)} .n3{color:var(--n3)}
  .n4{color:var(--n4)} .n5{color:var(--n5)} .n6{color:var(--n6)}
  .n7{color:var(--n7)} .n8{color:var(--n8)}

  .footer{margin-top:6px; color:#222; font-size:12px; opacity:.9}
</style>
</head>
<body>
  <div class="win95-window" id="app">
    <div class="titlebar">
      <div>Minesweeper</div>
      <div class="buttons"><div class="tb-btn"></div><div class="tb-btn"></div><div class="tb-btn"></div></div>
    </div>

    <div class="toolbar">
      <label>Schwierigkeit:
        <select id="difficulty">
          <option value="9x9x10">Beginner (9×9, 10)</option>
          <option value="16x16x40">Intermediate (16×16, 40)</option>
          <option value="16x30x99">Experte (16×30, 99)</option>
          <option value="custom">Custom…</option>
        </select>
      </label>
      <span id="custom" style="display:none">
        R:<input id="rows" type="number" min="5" max="40" value="9" style="width:56px">
        C:<input id="cols" type="number" min="5" max="50" value="9" style="width:56px">
        M:<input id="mines" type="number" min="1" value="10" style="width:68px">
      </span>
      <button id="new">Neu</button>
    </div>

    <div class="panel">
      <div class="lcd" id="mineCount">010</div>
      <div class="smiley" id="smiley" title="Neu">🙂</div>
      <div class="lcd" id="timer">000</div>
    </div>

    <div class="board-wrap">
      <div class="board" id="board" role="grid" aria-label="Minesweeper"></div>
    </div>

    <div class="footer">Links: aufdecken • Rechtsklick/Langdruck: Flagge • Doppelklick auf Zahl: chord</div>
  </div>

<script>
(()=>{
  // --- State ---
  let R=9,C=9,M=10;
  let grid=[]; // {mine, revealed, flagged, adj}
  let started=false, finished=false;
  let time=0, tId=null, flags=0;

  const board = document.getElementById('board');
  const mineEl = document.getElementById('mineCount');
  const timeEl = document.getElementById('timer');
  const face = document.getElementById('smiley');
  const diffSel = document.getElementById('difficulty');
  const customWrap = document.getElementById('custom');
  const rowsInp = document.getElementById('rows');
  const colsInp = document.getElementById('cols');
  const minesInp= document.getElementById('mines');

  const idx=(r,c)=> r*C + c;
  const inB=(r,c)=> r>=0 && r<R && c>=0 && c<C;
  const neigh=(r,c)=> {
    const a=[];
    for(let dr=-1;dr<=1;dr++)
      for(let dc=-1;dc<=1;dc++){
        if(dr||dc){ const nr=r+dr, nc=c+dc; if(inB(nr,nc)) a.push([nr,nc]); }
      }
    return a;
  };
  const pad3=n=>String(n).padStart(3,'0');
  const setLCD=()=>{ mineEl.textContent=pad3(M-flags); timeEl.textContent=pad3(time); };

  function startTimer(){ if(tId) return; tId=setInterval(()=>{ time++; timeEl.textContent=pad3(time); },1000); }
  function stopTimer(){ clearInterval(tId); tId=null; }

  function buildUI(){
    board.style.gridTemplateColumns=`repeat(${C}, 24px)`;
    board.innerHTML='';
    for(let r=0;r<R;r++){
      for(let c=0;c<C;c++){
        const el=document.createElement('div');
        el.className='cell';
        el.dataset.r=r; el.dataset.c=c;
        attach(el);
        board.appendChild(el);
      }
    }
  }

  function reset(keepDims=false){
    stopTimer(); time=0; started=false; finished=false; flags=0; face.textContent='🙂';
    if(!keepDims){
      const v=diffSel.value;
      if(v!=='custom'){
        [R,C,M]=v.split('x').map(Number);
      }else{
        R=clamp(+rowsInp.value,5,40);
        C=clamp(+colsInp.value,5,50);
        const maxM=Math.max(1,R*C-9);
        M=clamp(+minesInp.value||10,1,maxM);
      }
    }else if(diffSel.value==='custom'){
      R=clamp(+rowsInp.value,5,40); C=clamp(+colsInp.value,5,50);
      M=clamp(+minesInp.value,1,R*C-9);
    }
    grid=Array.from({length:R*C},()=>({mine:false,revealed:false,flagged:false,adj:0}));
    buildUI(); setLCD();
  }

  const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));

  // Minen erst nach erstem Klick setzen (First Click Safe + Nachbarschaft)
  function placeMines(sr,sc){
    const banned=new Set([idx(sr,sc), ...neigh(sr,sc).map(([r,c])=>idx(r,c))]);
    let placed=0;
    while(placed<M){
      const r=(Math.random()*R)|0, c=(Math.random()*C)|0, k=idx(r,c);
      if(banned.has(k) || grid[k].mine) continue;
      grid[k].mine=true; placed++;
    }
    // Adjazenzen
    for(let r=0;r<R;r++){
      for(let c=0;c<C;c++){
        const k=idx(r,c);
        if(grid[k].mine) continue;
        grid[k].adj = neigh(r,c).reduce((a,[nr,nc])=> a + (grid[idx(nr,nc)].mine?1:0),0);
      }
    }
  }

  function cellEl(r,c){ return board.children[idx(r,c)]; }

  function reveal(r,c){
    if(!inB(r,c)) return;
    const k=idx(r,c), cell=grid[k], el=cellEl(r,c);
    if(cell.revealed || cell.flagged || finished) return;

    if(!started){ placeMines(r,c); started=true; startTimer(); }

    if(cell.mine){
      el.classList.add('revealed','mine','bang');
      lose(r,c); return;
    }

    cell.revealed=true; el.classList.add('revealed');
    if(cell.adj>0){
      el.textContent=cell.adj; el.classList.add('n'+cell.adj);
    }else{
      for(const [nr,nc] of neigh(r,c)) reveal(nr,nc);
    }
    checkWin();
  }

  function toggleFlag(r,c){
    if(finished) return;
    const k=idx(r,c), cell=grid[k], el=cellEl(r,c);
    if(cell.revealed) return;
    cell.flagged=!cell.flagged;
    el.classList.toggle('flag', cell.flagged);
    flags += cell.flagged?1:-1; mineEl.textContent=pad3(M-flags);
    checkWin();
  }

  function chord(r,c){
    const k=idx(r,c), cell=grid[k];
    if(!cell.revealed || cell.adj===0) return;
    const ns=neigh(r,c);
    const f=ns.reduce((a,[nr,nc])=> a+(grid[idx(nr,nc)].flagged?1:0),0);
    if(f===cell.adj){
      for(const [nr,nc] of ns) if(!grid[idx(nr,nc)].flagged) reveal(nr,nc);
    }
  }

  function lose(br,bc){
    finished=true; stopTimer(); face.textContent='😵';
    for(let r=0;r<R;r++){
      for(let c=0;c<C;c++){
        const k=idx(r,c), cell=grid[k], el=cellEl(r,c);
        if(cell.mine) el.classList.add('mine','revealed');
        else if(!cell.revealed){
          if(cell.adj>0){ el.textContent=cell.adj; el.classList.add('revealed','n'+cell.adj); }
          else el.classList.add('revealed');
        }
        if(cell.flagged && !cell.mine){ el.textContent='×'; el.style.color='#a00'; el.classList.add('revealed'); }
      }
    }
    cellEl(br,bc).classList.add('bang');
  }

  function checkWin(){
    if(finished) return;
    let hidden=0;
    for(const c of grid) if(!c.revealed) hidden++;
    if(hidden===M){ finished=true; stopTimer(); face.textContent='😎';
      // zeige Minen
      for(let r=0;r<R;r++) for(let c=0;c<C;c++){
        const k=idx(r,c), cell=grid[k]; if(cell.mine) cellEl(r,c).classList.add('mine','revealed');
      }
    }
  }

  // --- UI Events ---
  function attach(el){
    const r=+el.dataset.r, c=+el.dataset.c;
    let longT=null, didLong=false;

    el.addEventListener('mousedown', ()=>{ if(!finished) face.textContent='😮'; });
    el.addEventListener('mouseup',   ()=>{ if(!finished) face.textContent='🙂'; });

    el.addEventListener('click', e=>{
      if(didLong){ didLong=false; return; }
      const cell=grid[idx(r,c)];
      if(e.detail===2 && cell.revealed) chord(r,c);
      else if(!cell.flagged) reveal(r,c);
    });

    el.addEventListener('contextmenu', e=>{ e.preventDefault(); toggleFlag(r,c); });

    // Touch: long press -> flag
    el.addEventListener('touchstart', e=>{
      didLong=false;
      longT=setTimeout(()=>{ toggleFlag(r,c); didLong=true; },450);
    }, {passive:true});
    el.addEventListener('touchend', e=>{
      if(longT){ clearTimeout(longT); longT=null; }
      if(!didLong){
        const cell=grid[idx(r,c)];
        if(!cell.flagged) reveal(r,c);
      }
    }, {passive:true});
  }

  document.getElementById('new').addEventListener('click', ()=> reset(false));
  face.addEventListener('click', ()=> reset(true));
  diffSel.addEventListener('change', ()=>{
    customWrap.style.display = diffSel.value==='custom' ? 'inline-block' : 'none';
  });

  [rowsInp,colsInp].forEach(inp=> inp?.addEventListener('change', ()=>{
    rowsInp.value=clamp(+rowsInp.value||9,5,40);
    colsInp.value=clamp(+colsInp.value||9,5,50);
    const maxM=Math.max(1, (+rowsInp.value)*(+colsInp.value)-9);
    minesInp.value=clamp(+minesInp.value||10,1,maxM);
  }));
  minesInp?.addEventListener('change', ()=>{
    const maxM=Math.max(1, (+rowsInp.value)*(+colsInp.value)-9);
    minesInp.value=clamp(+minesInp.value||10,1,maxM);
  });

  document.addEventListener('keydown', e=>{
    if(e.key==='r' || e.key==='R') reset(true);
  });

  // --- Init ---
  reset(false);
})();
</script>
</body>
</html>
        """
        elif mode == "Popup":
            self.html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Minesweeper – Fixed 10x16 Fullscreen</title>
<style>
  :root{
    --win-gray:#c0c0c0;
    --win-dark:#404040;
    --win-mid:#808080;
    --win-light:#ffffff;
    --panel:#bdbdbd;
    --cell-face:#bdbdbd;
    --n1:#0000ff; --n2:#008000; --n3:#ff0000;
    --n4:#000080; --n5:#800000; --n6:#008080;
    --n7:#000000; --n8:#808080;
  }

  html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#2e2e2e;display:flex;justify-content:center;align-items:center;}
  .board-wrap{width:100%;height:100%;display:flex;justify-content:center;align-items:center;}
  .board{
    display:grid; gap:0;
    background:var(--win-mid);
    border:2px solid var(--win-dark);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
  }
  .cell{
    display:grid; place-items:center; font-weight:700;
    background:var(--cell-face);
    border-right:1px solid var(--win-light);
    border-bottom:1px solid var(--win-light);
    border-left:1px solid var(--win-mid);
    border-top:1px solid var(--win-mid);
    box-shadow: inset -2px -2px 0 var(--win-mid), inset 2px 2px 0 var(--win-light);
    cursor:pointer;
  }
  .cell.revealed{
    background:#d6d6d6;
    box-shadow: inset 1px 1px 0 var(--win-mid), inset -1px -1px 0 var(--win-light);
    cursor:default;
    border:1px solid var(--win-mid);
  }
  .cell.flag::after{content:"⚑"; font-size:16px; color:#000;}
  .cell.mine::after{content:"●"; color:#000; font-size:14px;}
  .bang{background:#ff6961 !important;}
  .n1{color:var(--n1)} .n2{color:var(--n2)} .n3{color:var(--n3)}
  .n4{color:var(--n4)} .n5{color:var(--n5)} .n6{color:var(--n6)}
  .n7{color:var(--n7)} .n8{color:var(--n8)}
</style>
</head>
<body>
<div class="board-wrap">
  <div class="board" id="board"></div>
</div>

<script>
(()=>{
  const R=16, C=10, M=35; // Höhe x Breite
  let grid=[], started=false, finished=false, flags=0, time=0, tId=null;

  const board=document.getElementById('board');

  function resizeCells(){
    const wrap = board.parentElement.getBoundingClientRect();
    const size = Math.floor(Math.min(wrap.width/C, wrap.height/R));
    board.style.gridTemplateColumns=`repeat(${C}, ${size}px)`;
    board.style.gridTemplateRows=`repeat(${R}, ${size}px)`;
    for(const el of board.children){el.style.width=el.style.height=size+'px';}
  }

  window.addEventListener('resize', resizeCells);

  const idx=(r,c)=> r*C+c;
  const inB=(r,c)=> r>=0 && r<R && c>=0 && c<C;
  const neigh=(r,c)=> { const a=[]; for(let dr=-1;dr<=1;dr++) for(let dc=-1;dc<=1;dc++) if(dr||dc){ const nr=r+dr,nc=c+dc; if(inB(nr,nc)) a.push([nr,nc]);} return a; }

  const buildUI=()=>{
    board.innerHTML='';
    for(let r=0;r<R;r++){
      for(let c=0;c<C;c++){
        const el=document.createElement('div');
        el.className='cell';
        el.dataset.r=r; el.dataset.c=c;
        attach(el);
        board.appendChild(el);
      }
    }
    resizeCells();
  }

  const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));

  function placeMines(sr,sc){
    const banned=new Set([idx(sr,sc), ...neigh(sr,sc).map(([r,c])=>idx(r,c))]);
    let placed=0;
    while(placed<M){
      const r=(Math.random()*R)|0, c=(Math.random()*C)|0, k=idx(r,c);
      if(banned.has(k) || grid[k].mine) continue;
      grid[k].mine=true; placed++;
    }
    for(let r=0;r<R;r++) for(let c=0;c<C;c++){
      const k=idx(r,c);
      if(grid[k].mine) continue;
      grid[k].adj=neigh(r,c).reduce((a,[nr,nc])=>a+(grid[idx(nr,nc)].mine?1:0),0);
    }
  }

  function cellEl(r,c){return board.children[idx(r,c)];}

  function reveal(r,c){
    if(!inB(r,c)) return;
    const k=idx(r,c), cell=grid[k], el=cellEl(r,c);
    if(cell.revealed||cell.flagged||finished) return;
    if(!started){placeMines(r,c); started=true;}
    if(cell.mine){el.classList.add('revealed','mine','bang'); lose(); return;}
    cell.revealed=true; el.classList.add('revealed');
    if(cell.adj>0){el.textContent=cell.adj; el.classList.add('n'+cell.adj);}
    else for(const [nr,nc] of neigh(r,c)) reveal(nr,nc);
    checkWin();
  }

  function toggleFlag(r,c){
    if(finished) return;
    const k=idx(r,c), cell=grid[k], el=cellEl(r,c);
    if(cell.revealed) return;
    cell.flagged=!cell.flagged;
    el.classList.toggle('flag',cell.flagged);
    flags += cell.flagged?1:-1;
    checkWin();
  }

  function chord(r,c){
    const k=idx(r,c), cell=grid[k];
    if(!cell.revealed || cell.adj===0) return;
    const ns=neigh(r,c);
    const f=ns.reduce((a,[nr,nc])=>a+(grid[idx(nr,nc)].flagged?1:0),0);
    if(f===cell.adj) for(const [nr,nc] of ns) if(!grid[idx(nr,nc)].flagged) reveal(nr,nc);
  }

  function lose(){ finished=true; stopTimer(); for(let r=0;r<R;r++) for(let c=0;c<C;c++){ const k=idx(r,c), cell=grid[k], el=cellEl(r,c); if(cell.mine) el.classList.add('mine','revealed'); } }
  function checkWin(){ if(finished) return; let hidden=0; for(const c of grid) if(!c.revealed) hidden++; if(hidden===M){ finished=true; stopTimer(); for(let r=0;r<R;r++) for(let c=0;c<C;c++){ const k=idx(r,c), cell=grid[k]; if(cell.mine) cellEl(r,c).classList.add('mine','revealed');}}}

  function attach(el){
    const r=+el.dataset.r, c=+el.dataset.c;
    let longT=null, didLong=false;
    el.addEventListener('click', e=>{if(didLong){didLong=false;return;} const cell=grid[idx(r,c)]; if(e.detail===2 && cell.revealed) chord(r,c); else if(!cell.flagged) reveal(r,c);});
    el.addEventListener('contextmenu', e=>{e.preventDefault(); toggleFlag(r,c);});
    el.addEventListener('touchstart', e=>{didLong=false; longT=setTimeout(()=>{ toggleFlag(r,c); didLong=true; },450);},{passive:true});
    el.addEventListener('touchend', e=>{if(longT){clearTimeout(longT); longT=null;} if(!didLong){const cell=grid[idx(r,c)]; if(!cell.flagged) reveal(r,c);}}, {passive:true});
  }

  function startTimer(){if(tId)return;tId=setInterval(()=>time++,1000);}
  function stopTimer(){clearInterval(tId);tId=null;}

  function reset(){
    stopTimer(); time=0; started=false; finished=false; flags=0;
    grid=Array.from({length:R*C},()=>({mine:false,revealed:false,flagged:false,adj:0}));
    buildUI();
  }

  document.addEventListener('keydown', e=>{if(e.key==='r'||e.key==='R') reset();});

  reset();
})();
</script>
</body>
</html>
"""
        self.browser.setHtml(self.html)
