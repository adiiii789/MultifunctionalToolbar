# scripts/pro_sci_calculator_html.py
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView


class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):  # Default Light
        super().__init__()
        self.setWindowTitle("Zombies – Waves + Shop + Maps + Boss (v4)")
        self.resize(1000, 800)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        # HTML UI (komplett eingebettet)
        if mode == "Window":
            self.html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zombies – Waves + Shop + Maps + Boss (v4)</title>
<style>
  :root{--bg:#0b0f18;--panel:#0e1424;--muted:#9aa6c3;--text:#e8eefc;--accent:#7aa2f7;--ok:#4cd964;--warn:#ffb020;--bad:#ff6b6b;--grid:#1b2540;}
  *{box-sizing:border-box} html,body{height:100%}
  body{margin:0;background:linear-gradient(135deg,#0a0f17,#0f1526);color:var(--text);
    font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;display:grid;place-items:center;padding:16px;}
  .app{width:min(96vw,1100px);background:var(--panel);border:1px solid #1f2a44;border-radius:14px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.35)}
  header{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:10px;padding:12px 14px;background:#0c1322;border-bottom:1px solid #1f2a44}
  h1{margin:0;text-align:center;font-size:16px;color:var(--muted);letter-spacing:.5px}
  .stats,.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .chip{padding:6px 10px;background:#0b1220;border:1px solid #223154;border-radius:8px;font-variant-numeric:tabular-nums;min-width:86px;text-align:center}
  .chip.ok{color:var(--ok)} .chip.bad{color:var(--bad)} .chip.ac{color:var(--accent)}
  button{background:#17213a;color:var(--text);border:1px solid #2a3550;border-radius:8px;padding:8px 10px;cursor:pointer;font-weight:600}
  button:hover{background:#213055}
  main{padding:12px}
  .board-wrap{background:#0a0f1f;border:1px solid #1e2638;border-radius:12px;padding:10px;display:grid;place-items:center}
  canvas{width:100%;height:auto;display:block;background:#0a0f1f;border-radius:8px}
  .help{margin-top:8px;color:var(--muted);text-align:center;font-size:13px}
  .status{margin-top:10px;text-align:center}
  .ok{color:var(--ok);font-weight:700} .fail{color:var(--bad);font-weight:700}
  .modal{position:fixed;inset:0;display:none;place-items:center;background:rgba(0,0,0,.55);padding:16px}
  .modal.show{display:grid}
  .card{width:min(95vw,900px);background:#0e1424;border:1px solid #223154;border-radius:12px;padding:16px}
  .card h2{margin:0 0 10px 0;font-size:18px}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .section{background:#111934;border:1px solid #27345a;border-radius:12px;padding:12px}
  .weapons,.shop{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:8px}
  .wbtn,.sbtn,.opt{display:flex;flex-direction:column;gap:6px;padding:10px;background:#0f1836;border:1px solid #2a3a66;border-radius:10px;cursor:pointer}
  .wbtn.disabled,.sbtn.disabled,.opt.disabled{opacity:.5;cursor:not-allowed}
  .wbtn h3,.sbtn h3{margin:0;font-size:15px}
  .meta{color:var(--muted);font-size:12px} .price{color:#ffd166;font-weight:700}
  .flex{display:flex;gap:8px;align-items:center;justify-content:space-between}
  .grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="stats">
      <div class="chip">❤️ HP: <span id="hp">100</span></div>
      <div class="chip ac">🔫 Waffe: <span id="weaponName">Pistole</span></div>
      <div class="chip">🧟 Verbl.: <span id="left">0</span></div>
    </div>
    <h1>Zombies – Wave Survival</h1>
    <div class="controls">
      <div class="chip">🗺️ Map: <span id="mapName">–</span></div>
      <div class="chip">⚙️ Stufe: <span id="diffName">–</span></div>
      <div class="chip">🌊 Welle: <span id="wave">0</span></div>
      <div class="chip">⭐ Punkte: <span id="score">0</span></div>
      <button id="pauseBtn">Pause</button>
      <button id="restartBtn">Neu</button>
    </div>
  </header>
  <main>
    <div class="board-wrap">
      <canvas id="game" width="960" height="600" aria-label="Zombies Canvas"></canvas>
    </div>
    <div class="help">WASD: bewegen • Maus: zielen • Linksklick: schießen • P: Pause • R: Reset</div>
    <div id="status" class="status" aria-live="polite"></div>
  </main>
</div>

<!-- Setup -->
<div id="setupModal" class="modal">
  <div class="card">
    <h2>Setup – Map & Schwierigkeit</h2>
    <div class="grid2">
      <div class="section"><h3>Map auswählen</h3><div id="mapOpts" class="weapons"></div></div>
      <div class="section"><h3>Schwierigkeit</h3><div id="diffOpts" class="weapons"></div></div>
    </div>
  </div>
</div>

<!-- Intermission -->
<div id="interModal" class="modal">
  <div class="card">
    <h2>Intermission – Shop & Waffenwahl</h2>
    <div class="flex"><div>Welle: <strong id="imWave">1</strong></div><div>Punkte: <strong id="imScore">0</strong></div></div>
    <div class="row">
      <div class="section"><h3>Shop</h3><div id="shopList" class="shop"></div></div>
      <div class="section"><h3>Waffe wählen</h3><div id="weaponList" class="weapons"></div></div>
    </div>
  </div>
</div>

<script>
(()=>{
// ===== DOM / Utils =====
const cvs = document.getElementById('game'), ctx = cvs.getContext('2d');
const ui = { hp, weaponName, left, wave, score, status, pauseBtn, restartBtn, inter: interModal, setup: setupModal,
             weaponList, shopList, imWave, imScore, mapOpts, diffOpts, mapName, diffName };
const W=()=>cvs.width, H=()=>cvs.height, TAU=Math.PI*2;
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const dist2=(x1,y1,x2,y2)=>{const dx=x2-x1, dy=y2-y1; return dx*dx+dy*dy;};
const rand=(a,b)=>Math.random()*(b-a)+a;
const deepCopy = o => JSON.parse(JSON.stringify(o));

// ===== Balancing =====
const PRICE_FACTOR = 1.5; // Shop-Preissteigerung/Kauf

// ===== Settings =====
const DIFFS = {
  easy:   {name:'Easy',   enemyHP:0.85, enemySPD:0.9, enemyDMG:0.85, spawn:1.05, scoreMul:0.9,  bossHP:1.10, bossDMG:1.30},
  normal: {name:'Normal', enemyHP:1.00, enemySPD:1.0, enemyDMG:1.00, spawn:1.00, scoreMul:1.0,  bossHP:1.30, bossDMG:1.60},
  hard:   {name:'Hard',   enemyHP:1.25, enemySPD:1.1, enemyDMG:1.25, spawn:0.9,  scoreMul:1.15, bossHP:1.50, bossDMG:2.00},
};
let currentDiff=null;

const MAPS = [
  { id:'arena', name:'Arena', desc:'Keine Hindernisse', build:(w,h)=>[] },
  { id:'depot', name:'Depot', desc:'Mittlere Deckungen', build:(w,h)=>[
      r(w*0.20,h*0.35,w*0.10,h*0.30), r(w*0.45,h*0.15,w*0.10,h*0.25), r(w*0.70,h*0.45,w*0.12,h*0.32),
  ]},
  { id:'park', name:'Park', desc:'Symmetrische Inseln', build:(w,h)=>[
      r(w*0.15,h*0.20,w*0.14,h*0.18), r(w*0.71,h*0.20,w*0.14,h*0.18), r(w*0.33,h*0.60,w*0.14,h*0.20), r(w*0.52,h*0.60,w*0.14,h*0.20),
  ]},
  { id:'maze', name:'Labyrinth', desc:'Engere Korridore', build:(w,h)=>[
      r(w*0.10,h*0.25,w*0.55,h*0.08), r(w*0.35,h*0.25,w*0.08,h*0.40), r(w*0.35,h*0.57,w*0.45,h*0.08), r(w*0.72,h*0.35,w*0.08,h*0.30),
  ]},
];
let currentMap={id:null,name:null,obstacles:[]};

// ===== State =====
let running=false, paused=false, gameOver=false;
let last=0, scoreVal=0, waveNum=0, enemiesLeft=0;
const playerBase={ r:16, speed:240, hpMax:100 };
const player={ x:W()/2, y:H()/2, r:playerBase.r, speed:playerBase.speed, vx:0, vy:0, hp:playerBase.hpMax, hpMax:playerBase.hpMax, inv:0 };
let bullets=[], enemies=[], particles=[], enemyBullets=[];
let mouse={x:W()/2,y:H()/2,down:false}, keys={}, currentWeapon=null, canShootAt=0, BULLET_LIFE=0.9;
let isBossWave=false, activeBoss=null;

// ===== Weapons (mehr & spätere Unlocks) =====
const BASE_WEAPONS = [
  { id:'pistol',   name:'Pistole',      unlockWave:1,  dmg:20, speed:820,  spread:0.01, fireDelay:220, pierce:1, pellets:1, color:'#7aa2f7', barrel:{len:18,th:7, tip:'#a4c4ff'} },
  { id:'smg',      name:'SMG',          unlockWave:4,  dmg:12, speed:900,  spread:0.07, fireDelay:90,  pierce:1, pellets:1, color:'#9be49d', barrel:{len:20,th:8, tip:'#c8f7c9'} },
  { id:'shotgun',  name:'Schrot',       unlockWave:6,  dmg:12, speed:820,  spread:0.22,fireDelay:600, pierce:1, pellets:7, color:'#ffd166', barrel:{len:22,th:10, tip:'#ffe39a'} },
  { id:'burst',    name:'Burst 3x',     unlockWave:8,  dmg:14, speed:950,  spread:0.018,fireDelay:360, pierce:1, pellets:3, color:'#b3e5ff', barrel:{len:22,th:7, tip:'#e0f6ff'} },
  { id:'lmg',      name:'LMG',          unlockWave:10, dmg:16, speed:900,  spread:0.055,fireDelay:110, pierce:1, pellets:1, color:'#ffa86e', barrel:{len:24,th:9, tip:'#ffd1b5'} },
  { id:'autosg',   name:'Auto-Schrot',  unlockWave:14, dmg:10, speed:820,  spread:0.25, fireDelay:300, pierce:1, pellets:6, color:'#ffe08a', barrel:{len:22,th:11, tip:'#fff0bd'} },
  { id:'rifle',    name:'Gewehr',       unlockWave:12, dmg:35, speed:1100, spread:0.015,fireDelay:150, pierce:1, pellets:1, color:'#ffadad', barrel:{len:28,th:6, tip:'#ffc7c7'} },
  { id:'minigun',  name:'Minigun',      unlockWave:18, dmg:10, speed:980,  spread:0.09, fireDelay:55,  pierce:1, pellets:1, color:'#bdb9ff', barrel:{len:26,th:10, tip:'#dedcff'} },
  { id:'rail',     name:'Railgun',      unlockWave:20, dmg:120,speed:1600, spread:0,    fireDelay:900, pierce:3, pellets:1, color:'#ff6b6b', barrel:{len:34,th:6, tip:'#ffd1d1'} },
  { id:'sniper',   name:'Sniper',       unlockWave:30, dmg:260,speed:1700, spread:0.004,fireDelay:1100,pierce:2, pellets:1, color:'#a0ffb3', barrel:{len:34,th:5, tip:'#d6ffdf'} },
];
let WEAPONS = deepCopy(BASE_WEAPONS);

// ===== Shop (dynamische Preise) =====
const SHOP_BASE = [
  { id:'hp',     name:'HP-Pack (+35)',            basePrice:60,  apply:()=>{ player.hp = clamp(player.hp+35,0,player.hpMax); ui.hp.textContent=Math.round(player.hp); } },
  { id:'hpmax',  name:'Max-HP +20',               basePrice:120, apply:()=>{ player.hpMax+=20; player.hp+=20; ui.hp.textContent=Math.round(player.hp); } },
  { id:'firerate',name:'Feuerrate +15%',          basePrice:130, apply:()=>{ WEAPONS.forEach(w=>w.fireDelay=Math.max(45, Math.round(w.fireDelay*0.85))); } },
  { id:'damage', name:'Schaden +20%',             basePrice:160, apply:()=>{ WEAPONS.forEach(w=>w.dmg=Math.round(w.dmg*1.2)); } },
  { id:'speed',  name:'Movespeed +12%',           basePrice:140, apply:()=>{ player.speed=Math.round(player.speed*1.12); } },
  { id:'pierce', name:'Durchschlag +1 (alle)',    basePrice:200, apply:()=>{ WEAPONS.forEach(w=>w.pierce+=1); } },
  { id:'mag',    name:'Extra-Mag (Bullets +)',    basePrice:90,  apply:()=>{ BULLET_LIFE = Math.min(BULLET_LIFE+0.15, 1.6); } },
];
let SHOP = SHOP_BASE.map(x=>({ ...x, timesBought:0 }));
const priceOf=i=>Math.round(i.basePrice*Math.pow(PRICE_FACTOR,i.timesBought));

// ===== Enemies =====
const BASE_TYPES = {
  walker:{name:'Walker',hp:40, speed:70,  r:16,dmg:10,score:10,color:'#7aa2f7'},
  runner:{name:'Runner',hp:30, speed:135, r:13,dmg:18,score:14,color:'#6ce17c'}, // etwas mehr dmg
  tank:  {name:'Tank',  hp:150,speed:50,  r:22,dmg:28,score:26,color:'#ffb020'},
};
function scaledType(kind){
  const b=BASE_TYPES[kind]||BASE_TYPES.walker;
  return { name:b.name,r:b.r,color:b.color,score:b.score,
    hp:Math.round(b.hp*(currentDiff?.enemyHP||1)),
    speed:b.speed*(currentDiff?.enemySPD||1),
    dmg:b.dmg*(currentDiff?.enemyDMG||1),
  };
}
function enemyMixForWave(w){
  if (w%5===0) return []; // Boss-Wave (bleibt alle 5)
  const base=7+Math.floor(w*1.9);
  const clampF=(x,min,max)=>Math.max(min,Math.min(max,x));
  const mix=[];
  const tWalker=Math.floor(base*clampF(0.65-w*0.02,0.25,0.7));
  const tRunner=Math.floor(base*clampF(0.25+w*0.03,0.1,0.5));
  const tTank  =Math.floor(base*clampF(0.10+w*0.02,0.05,0.35));
  for(let i=0;i<tWalker;i++) mix.push('walker');
  for(let i=0;i<tRunner;i++) mix.push('runner');
  for(let i=0;i<tTank;i++)   mix.push('tank');
  while(mix.length<base) mix.push('walker');
  return mix;
}

// ===== Bosses (wie v3, belassen – schon härter) =====
const BOSS_TYPES = [
  { id:'behemoth', name:'Behemoth', color:'#d16d6d', r:40, baseHP:2200, dmg:24, score:320,
    attack:(b,dt,now)=>{ b.cool1-=dt; if (b.cool1<=0){ radialBurst(b, 28, 420, 7, 12); b.cool1=2.0; } } },
  { id:'sentinel', name:'Sentinel', color:'#8b7ad1', r:36, baseHP:1900, dmg:20, score:300,
    attack:(b,dt,now)=>{ b.phase=(b.phase||0)+dt*2.2; b.cool1-=dt; if (b.cool1<=0){ dualSpiral(b, 9, 440, b.phase, 6); b.cool1=0.28; } } },
  { id:'hunter', name:'Hunter', color:'#7ad19f', r:34, baseHP:1700, dmg:28, score:330,
    attack:(b,dt,now)=>{ b.cool1-=dt; if (b.cool1<=0){ coneSpray(b, 7, 520, 0.6, 6); b.cool1=1.0; }
                         b.cool2-=dt; if (b.cool2<=0){ dashTowardPlayer(b, 360, 0.35); b.cool2=4.0; } } },
  { id:'necro', name:'Necro', color:'#b0e35c', r:38, baseHP:1800, dmg:22, score:330,
    attack:(b,dt,now)=>{ b.cool1-=dt; if (b.cool1<=0){ smallBurst(b, 14, 380, 6); b.cool1=1.6; }
                         b.cool2-=dt; if (b.cool2<=0){ summonAdds(5); b.cool2=5.5; } } },
  { id:'warden', name:'Warden', color:'#c090ff', r:38, baseHP:2100, dmg:26, score:350,
    attack:(b,dt,now)=>{ b.phase=(b.phase||0)+dt*1.6; b.cool1-=dt; if (b.cool1<=0){ rotatingWall(b, 6, 420, b.phase, 8); b.cool1=0.22; } } },
  { id:'artillery', name:'Artillery', color:'#ff9f6e', r:35, baseHP:2000, dmg:30, score:360,
    attack:(b,dt,now)=>{ b.cool1-=dt; if (b.cool1<=0){ aimedVolley(b, 4, 500, 0.10, 7); b.cool1=1.1; }
                         b.cool2-=dt; if (b.cool2<=0){ radialBurst(b, 12, 350, 8, 16); b.cool2=2.6; } } },
];
function isFree(x, y, r){
  return !collidesAnyCircle(x, y, r) &&
         x>=r && x<=W()-r && y>=r && y<=H()-r;
}
function findFreeCircle(r, minDistFromPlayer=120, tries=400){
  for(let i=0;i<tries;i++){
    const x = rand(r, W()-r);
    const y = rand(r, H()-r);
    if (!isFree(x,y,r)) continue;
    if (minDistFromPlayer>0 && Math.hypot(x-player.x, y-player.y) < minDistFromPlayer) continue;
    return {x,y};
  }
  // Fallback: versuche am Rand zu spawnen
  for(let i=0;i<tries;i++){
    const side = (Math.random()*4)|0;
    const margin = r+6;
    let x=rand(r, W()-r), y=rand(r, H()-r);
    if (side===0){ x = margin; } else if (side===1){ x = W()-margin; }
    else if (side===2){ y = margin; } else { y = H()-margin; }
    if (isFree(x,y,r)) return {x,y};
  }
  // Notfalls Mittelpunkt (wird gleich „rausgeschoben“)
  return {x: W()/2, y: H()/2};
}
function resolveFromObstacles(ent, iterations=6){
  // Schiebe Kreise aus Rechtecken heraus
  for(let k=0;k<iterations;k++){
    let moved = false;
    for(const o of currentMap.obstacles){
      // Nächster Punkt im Rechteck
      const nx = clamp(ent.x, o.x, o.x+o.w);
      const ny = clamp(ent.y, o.y, o.y+o.h);
      const dx = ent.x - nx, dy = ent.y - ny;
      const d2 = dx*dx + dy*dy, r = ent.r;
      if (d2 < r*r - 0.5){ // überlappt
        const d = Math.sqrt(Math.max(0.0001, d2));
        const ux = d ? dx/d : (Math.random()*2-1);
        const uy = d ? dy/d : (Math.random()*2-1);
        const push = (r - d) + 1.0;
        const tx = clamp(ent.x + ux*push, r, W()-r);
        const ty = clamp(ent.y + uy*push, r, H()-r);
        ent.x = tx; ent.y = ty;
        moved = true;
      }
    }
    if (!moved) break;
  }
}

function spawnBoss(){
  const def = BOSS_TYPES[(Math.random()*BOSS_TYPES.length)|0];
  const hp = Math.round(def.baseHP*(currentDiff?.bossHP||1)*(1+(waveNum/12)));
  const pos = findFreeCircle(def.r, 160); // nicht direkt neben dem Spieler

  const b = {
    boss:true, id:def.id, name:def.name,
    x:pos.x, y:pos.y, r:def.r, color:def.color,
    hp:hp, hpMax:hp,
    speed:72*(currentDiff?.enemySPD||1),
    dmg:def.dmg*(currentDiff?.bossDMG||1),
    score:def.score, vx:0, vy:0, cool1:1, cool2:2.2, phase:0
  };

  // Safety: falls trotz allem overlap -> rausdrücken
  resolveFromObstacles(b, 8);

  enemies.push(b);
  activeBoss = b;
  enemiesLeft = 1; ui.left.textContent = enemiesLeft;
  setStatus(`⚠️ Boss: ${b.name}`, true); setTimeout(()=>setStatus('',true), 1200);
}


// --- Boss-Projektil-Generatoren ---
function eb(x,y,vx,vy,dmg,life,r,color,home=0){ enemyBullets.push({x,y,vx,vy,dmg,life,r,color,home}); }
function radialBurst(boss,count,speed,radius=6,dmgMul=12){ for(let i=0;i<count;i++){ const a=i*(TAU/count); eb(boss.x,boss.y,Math.cos(a)*speed,Math.sin(a)*speed,dmgMul*(currentDiff?.bossDMG||1),2.2,radius,'#ff7575'); } }
function smallBurst(boss,count,speed,radius=5){ for(let i=0;i<count;i++){ const a=i*(TAU/count); eb(boss.x,boss.y,Math.cos(a)*speed,Math.sin(a)*speed,10*(currentDiff?.bossDMG||1),1.8,radius,'#b7ff7a'); } }
function dualSpiral(boss,rays,speed,offset,radius=6){ for(let i=0;i<rays;i++){ const a1=offset+i*(TAU/rays),a2=offset+TAU/2+i*(TAU/rays); eb(boss.x,boss.y,Math.cos(a1)*speed,Math.sin(a1)*speed,12*(currentDiff?.bossDMG||1),2.0,radius,'#c2b5ff'); eb(boss.x,boss.y,Math.cos(a2)*speed,Math.sin(a2)*speed,12*(currentDiff?.bossDMG||1),2.0,radius,'#c2b5ff'); } }
function aimedVolley(boss,count,speed,spread,radius=6){ const base=Math.atan2(player.y-boss.y,player.x-boss.x); for(let i=0;i<count;i++){ const a=base+(i-(count-1)/2)*spread; eb(boss.x,boss.y,Math.cos(a)*speed,Math.sin(a)*speed,16*(currentDiff?.bossDMG||1),2.0,radius,'#7affb6'); } }
function coneSpray(boss,shots,speed,coneWidth,radius=6){ const base=Math.atan2(player.y-boss.y,player.x-boss.x); for(let i=0;i<shots;i++){ const t=(i/(shots-1))-0.5; const a=base+t*coneWidth; eb(boss.x,boss.y,Math.cos(a)*speed,Math.sin(a)*speed,14*(currentDiff?.bossDMG||1),1.9,radius,'#7ae3ff'); } }
function rotatingWall(boss,segments,speed,phase,radius=7){ const start=phase,end=phase+Math.PI; for(let i=0;i<segments;i++){ const a=start+(i/(segments-1))*(end-start); eb(boss.x,boss.y,Math.cos(a)*speed,Math.sin(a)*speed,14*(currentDiff?.bossDMG||1),2.3,radius,'#ffa8a8'); } }
function dashTowardPlayer(boss,dashSpeed,time){ const a=Math.atan2(player.y-boss.y,player.x-boss.x); boss.vx=Math.cos(a)*dashSpeed; boss.vy=Math.sin(a)*dashSpeed; setTimeout(()=>{boss.vx=0;boss.vy=0;}, time*1000); }
function summonAdds(n){ const kinds=['walker','runner']; for(let i=0;i<n;i++) spawnEnemy(kinds[(Math.random()*kinds.length)|0]); }

// ===== Geometry / Obstacles =====
function r(x,y,w,h){ return {x:Math.floor(x), y:Math.floor(y), w:Math.floor(w), h:Math.floor(h)}; }
function circleIntersectsRect(cx,cy,cr,rect){ const nx=clamp(cx,rect.x,rect.x+rect.w), ny=clamp(cy,rect.y,rect.y+rect.h); const dx=cx-nx,dy=cy-ny; return (dx*dx+dy*dy)<=cr*cr; }
function pointInRect(px,py,rect){ return px>=rect.x && px<=rect.x+rect.w && py>=rect.y && py<=rect.y+rect.h; }
function collidesAnyCircle(x,y,r){ for(const o of currentMap.obstacles){ if(circleIntersectsRect(x,y,r,o)) return true; } return false; }
function collidesAnyPoint(x,y){ for(const o of currentMap.obstacles){ if(pointInRect(x,y,o)) return true; } return false; }
function tryMoveCircle(ent,nx,ny){ if(!collidesAnyCircle(nx,ny,ent.r)){ent.x=nx;ent.y=ny;return;} if(!collidesAnyCircle(nx,ent.y,ent.r)){ent.x=nx;return;} if(!collidesAnyCircle(ent.x,ny,ent.r)){ent.y=ny;return;} }

// ===== UI – Setup =====
let pickedMap=false,pickedDiff=false;
function maybeStart(){ pickedMap=!!currentMap.name; pickedDiff=!!currentDiff; if(pickedMap&&pickedDiff){ ui.setup.classList.remove('show'); openIntermission(); } }
function openSetup(){
  ui.mapName.textContent='–'; ui.diffName.textContent='–'; currentMap={id:null,name:null,obstacles:[]}; currentDiff=null; pickedMap=false;pickedDiff=false;
  ui.mapOpts.innerHTML=''; MAPS.forEach(m=>{ const b=document.createElement('button'); b.className='opt'; b.innerHTML=`<h3>${m.name}</h3><div class="meta">${m.desc}</div>`;
    b.addEventListener('click',()=>{ currentMap.id=m.id; currentMap.name=m.name; currentMap.obstacles=m.build(W(),H()); ui.mapName.textContent=m.name; maybeStart(); }); ui.mapOpts.appendChild(b); });
  ui.diffOpts.innerHTML=''; Object.values(DIFFS).forEach(d=>{ const b=document.createElement('button'); b.className='opt';
    b.innerHTML=`<h3>${d.name}</h3><div class="meta">HP ${Math.round(d.enemyHP*100)}%, Speed ${Math.round(d.enemySPD*100)}%, DMG ${Math.round(d.enemyDMG*100)}% | BossDMG ${Math.round(d.bossDMG*100)}%</div>`;
    b.addEventListener('click',()=>{ currentDiff=d; ui.diffName.textContent=d.name; maybeStart(); }); ui.diffOpts.appendChild(b); });
  ui.setup.classList.add('show');
}

// ===== Shop Rendering =====
function renderShop(){
  ui.shopList.innerHTML='';
  SHOP.forEach(item=>{
    const currentPrice=priceOf(item);
    const btn=document.createElement('button'); btn.className='sbtn';
    btn.innerHTML=`<h3>${item.name}</h3><div class="flex"><span class="meta">Käufe: ${item.timesBought}</span><span class="price">-${currentPrice}⭐</span></div>`;
    btn.addEventListener('click',()=>{ const cost=priceOf(item); if(scoreVal<cost) return;
      scoreVal-=cost; ui.score.textContent=scoreVal; ui.imScore.textContent=scoreVal; item.apply(); item.timesBought++; renderShop(); });
    ui.shopList.appendChild(btn);
  });
}

// ===== Intermission =====
function openIntermission(){
  ui.imWave.textContent=waveNum+1; ui.imScore.textContent=scoreVal; renderShop();
  ui.weaponList.innerHTML=''; const unlockedWave=Math.max(1,waveNum||1);
  WEAPONS.forEach(w=>{
    const unlocked=unlockedWave>=w.unlockWave;
    const btn=document.createElement('button'); btn.className='wbtn'+(unlocked?'':' disabled');
    btn.innerHTML=`<h3>${w.name} ${unlocked?'':`🔒 Welle ${w.unlockWave}`}</h3>
      <div class="meta">DMG ${w.dmg}, Rate ${Math.round(1000/w.fireDelay)}/s, Pierce ${w.pierce}${w.pellets>1?`, Schrot ${w.pellets}`:''}</div>`;
    if(unlocked) btn.addEventListener('click',()=>{ setWeapon(w.id); closeIntermission(true); });
    ui.weaponList.appendChild(btn);
  });
  ui.inter.classList.add('show');
}
function closeIntermission(startNext){ ui.inter.classList.remove('show'); if(startNext){ if(spawnQueue.length===0&&enemiesLeft===0) startWave(); running=true; paused=false; last=performance.now(); requestAnimationFrame(loop);} }
function setWeapon(id){ currentWeapon=WEAPONS.find(w=>w.id===id)||WEAPONS[0]; ui.weaponName.textContent=currentWeapon.name; canShootAt=0; }

// ===== Waves =====
let spawnQueue=[], spawnTimer=0;
function startWave(){
  waveNum++; ui.wave.textContent=waveNum;
  isBossWave=(waveNum%5===0);
  enemiesLeft=0; enemyBullets.length=0; activeBoss=null;
  if(isBossWave){ spawnQueue=['__BOSS__']; enemiesLeft=1; ui.left.textContent=enemiesLeft; }
  else{ spawnQueue=enemyMixForWave(waveNum); enemiesLeft=spawnQueue.length; ui.left.textContent=enemiesLeft; }
  spawnTimer=0;
}
function onWaveCleared(){ setStatus(`Welle ${waveNum} geschafft!`,true); running=false; paused=true; setTimeout(()=>{ setStatus('',true); openIntermission(); },250); }

// ===== Entities =====
function spawnEnemy(kind){
  if(kind==='__BOSS__'){ spawnBoss(); return; }
  const margin=46, t=scaledType(kind); let x,y,tries=0;
  do{ const side=(Math.random()*4)|0;
      if(side===0){ x=-margin; y=rand(0,H()); } else if(side===1){ x=W()+margin; y=rand(0,H()); }
      else if(side===2){ x=rand(0,W()); y=-margin; } else { x=rand(0,W()); y=H()+margin; }
      tries++; if(tries>50) break;
  }while(collidesAnyCircle(x,y,t.r));
  enemies.push({kind,x,y,r:t.r,hp:t.hp,hpMax:t.hp,speed:t.speed,dmg:t.dmg,color:BASE_TYPES[kind].color});
}
function shoot(x,y,angle){
  const w=currentWeapon||WEAPONS[0];
  for(let i=0;i<w.pellets;i++){
    const a=angle+(w.spread?rand(-w.spread,w.spread):0);
    bullets.push({x,y,vx:Math.cos(a)*w.speed,vy:Math.sin(a)*w.speed,dmg:w.dmg,life:BULLET_LIFE,pierce:w.pierce,color:w.color});
  }
}
function hitEnemy(e,dmg){
  e.hp-=dmg;
  if(e.hp<=0){
    const base=e.boss?(activeBoss?.score||300):(BASE_TYPES[e.kind]?.score||10);
    scoreVal+=Math.round(base*(currentDiff?.scoreMul||1)); ui.score.textContent=scoreVal;
    for(let i=0;i<10;i++) particles.push({x:e.x,y:e.y,vx:rand(-90,90),vy:rand(-90,90),life:0.45,color:'#b33a3a'});
    enemies.splice(enemies.indexOf(e),1); if(e.boss) activeBoss=null;
    enemiesLeft=Math.max(0,enemiesLeft-1); ui.left.textContent=enemiesLeft;
    if(enemiesLeft===0 && spawnQueue.length===0 && enemies.length===0) onWaveCleared();
  }else{
    particles.push({x:e.x,y:e.y,vx:rand(-28,28),vy:rand(-28,28),life:0.16,color:'#b33a3a'});
  }
}

// === SCHADEN: getrennt für Kontakt (DPS) vs. Projektil (Hit mit i-Frames) ===
function damagePlayerHit(d){ // Projektile / einmalige Treffer
  if(player.inv>0) return;
  player.hp = clamp(player.hp - d, 0, player.hpMax);
  ui.hp.textContent = Math.round(player.hp);
  player.inv = 0.35; // i-Frames NUR hier
  if(player.hp<=0){ gameOver=true; running=false; paused=false; setStatus('Game Over – R für Neustart',false); }
}
function damagePlayerContact(dps, dt){ // Körperkontakt – KEINE i-Frames
  if (dps<=0) return;
  player.hp = clamp(player.hp - dps*dt, 0, player.hpMax);
  ui.hp.textContent = Math.round(player.hp);
  if(player.hp<=0){ gameOver=true; running=false; paused=false; setStatus('Game Over – R für Neustart',false); }
}

// ===== Input =====
cvs.addEventListener('mousemove',e=>{ const r=cvs.getBoundingClientRect(); mouse.x=(e.clientX-r.left)*(cvs.width/r.width); mouse.y=(e.clientY-r.top)*(cvs.height/r.height); });
cvs.addEventListener('mousedown',()=>{ mouse.down=true; }); window.addEventListener('mouseup',()=>{ mouse.down=false; });
window.addEventListener('keydown',e=>{ const k=e.key.toLowerCase(); keys[k]=true; if(k==='p'||k===' ') togglePause(); else if(k==='r') resetGame(); });
window.addEventListener('keyup',e=>{ keys[e.key.toLowerCase()]=false; });
ui.pauseBtn.addEventListener('click',togglePause); ui.restartBtn.addEventListener('click',resetGame);

// ===== Game control / Loop =====
function startGame(){ running=true; paused=false; gameOver=false; setStatus(''); if(waveNum===0) startWave(); last=performance.now(); requestAnimationFrame(loop); }
function togglePause(){ if(gameOver) return; paused=!paused; setStatus(paused?'Pause':'',true); if(!paused&&!running){ running=true; last=performance.now(); requestAnimationFrame(loop);} }

// harter Reset
function hardResetUpgrades(){ WEAPONS=deepCopy(BASE_WEAPONS); player.speed=playerBase.speed; player.hpMax=playerBase.hpMax; player.hp=player.hpMax; BULLET_LIFE=0.9; SHOP=SHOP_BASE.map(x=>({...x,timesBought:0})); }
function resetGame(){
  scoreVal=0; waveNum=0; enemiesLeft=0; isBossWave=false; activeBoss=null;
  enemies.length=0; bullets.length=0; particles.length=0; enemyBullets.length=0; spawnQueue.length=0;
  player.x=W()/2; player.y=H()/2; player.vx=0; player.vy=0; player.inv=0;
  hardResetUpgrades();
  ui.score.textContent='0'; ui.wave.textContent='0'; ui.left.textContent='0'; ui.hp.textContent=Math.round(player.hp);
  setWeapon('pistol'); setStatus(''); running=false; paused=false; gameOver=false; openSetup();
}
function setStatus(t,ok){ ui.status.innerHTML = t ? `<span class="${ok?'ok':'fail'}">${t}</span>` : ''; }

function loop(now){
  if(!running) return;
  const dt=Math.min(0.033,(now-last)/1000); last=now;
  if(!paused && !gameOver){
    updateSpawns(dt); update(dt,now); draw();
  }
  requestAnimationFrame(loop);
}

// ===== Spawns / Shooting =====
function updateSpawns(dt){
  if(spawnQueue.length===0) return;
  spawnTimer -= dt;
  if(spawnTimer<=0){
    const burst=Math.min(3,spawnQueue.length);
    for(let i=0;i<burst;i++) spawnEnemy(spawnQueue.shift());
    spawnTimer = Math.max(0.25,(1.2-waveNum*0.05)*(currentDiff?.spawn||1));
  }
}
function handleShooting(now){
  if(!mouse.down||!currentWeapon) return;
  if(now<canShootAt) return;
  const dx=mouse.x-player.x, dy=mouse.y-player.y, ang=Math.atan2(dy,dx);
  const mx=player.x+Math.cos(ang)*(player.r+6), my=player.y+Math.sin(ang)*(player.r+6);
  shoot(mx,my,ang);
  canShootAt = now + currentWeapon.fireDelay;
  particles.push({x:mx,y:my,vx:Math.cos(ang)*220,vy:Math.sin(ang)*220,life:0.07,color:'#ffd166'});
}

// ===== Update =====
function update(dt, now){
  // movement
  const up=keys['w']||keys['arrowup'], dn=keys['s']||keys['arrowdown'], lt=keys['a']||keys['arrowleft'], rt=keys['d']||keys['arrowright'];
  let ax=0, ay=0; if(up) ay--; if(dn) ay++; if(lt) ax--; if(rt) ax++;
  const len=Math.hypot(ax,ay)||1; ax/=len; ay/=len;
  player.vx=ax*player.speed; player.vy=ay*player.speed;
  const nx=clamp(player.x+player.vx*dt, player.r, W()-player.r), ny=clamp(player.y+player.vy*dt, player.r, H()-player.r);
  tryMoveCircle(player,nx,ny);
  if(player.inv>0) player.inv-=dt;

  handleShooting(performance.now());

  // player bullets
  for(let i=bullets.length-1;i>=0;i--){
    const b=bullets[i]; b.x+=b.vx*dt; b.y+=b.vy*dt; b.life-=dt;
    if(collidesAnyPoint(b.x,b.y)){ bullets.splice(i,1); continue; }
    if(b.life<=0||b.x<-30||b.x>W()+30||b.y<-30||b.y>H()+30){ bullets.splice(i,1); continue; }
    for(let j=enemies.length-1;j>=0&&i<bullets.length;j--){
      const e=enemies[j], rr=e.r+4;
      if(dist2(b.x,b.y,e.x,e.y)<=rr*rr){ hitEnemy(e,b.dmg); b.pierce--; particles.push({x:b.x,y:b.y,vx:rand(-36,36),vy:rand(-36,36),life:0.12,color:b.color}); if(b.pierce<=0){ bullets.splice(i,1);} break; }
    }
  }

  // enemies & bosses movement + Kontakt-Schaden
  for(let i=enemies.length-1;i>=0;i--){
    const e=enemies[i];
    if(e.boss){
      if(e.vx||e.vy){ const nx=clamp(e.x+e.vx*dt,e.r,W()-e.r), ny=clamp(e.y+e.vy*dt,e.r,H()-e.r); tryMoveCircle(e,nx,ny); }
      else{ const dx=player.x-e.x, dy=player.y-e.y, d=Math.hypot(dx,dy)||1; const sp=e.speed*0.6; tryMoveCircle(e, clamp(e.x+(dx/d)*sp*dt,e.r,W()-e.r), clamp(e.y+(dy/d)*sp*dt,e.r,H()-e.r)); }
      const def=BOSS_TYPES.find(x=>x.id===e.id); if(def&&def.attack) def.attack(e,dt,now); resolveFromObstacles(e, 2);
    } else {
      const dx=player.x-e.x, dy=player.y-e.y, d=Math.hypot(dx,dy)||1;
      const sp=e.speed; tryMoveCircle(e, clamp(e.x+(dx/d)*sp*dt,e.r,W()-e.r), clamp(e.y+(dy/d)*sp*dt,e.r,H()-e.r));
    }
    const minD=player.r+e.r-2;
    if(dist2(player.x,player.y,e.x,e.y)<=minD*minD){
      // KONTAKT-SCHADEN (DPS, stapelbar mit mehreren Gegnern)
      const dps = (e.boss? e.dmg*1.5 : e.dmg);
      damagePlayerContact(dps, dt);
    }
  }

  // enemy bullets -> Treffer-Schaden (mit i-Frames)
  for(let i=enemyBullets.length-1;i>=0;i--){
    const b=enemyBullets[i];
    b.x+=b.vx*dt; b.y+=b.vy*dt; b.life-=dt;
    if(collidesAnyPoint(b.x,b.y) || b.life<=0 || b.x<-60||b.x>W()+60||b.y<-60||b.y>H()+60){ enemyBullets.splice(i,1); continue; }
    const r=(b.r||4)+player.r;
    if(dist2(b.x,b.y,player.x,player.y)<=r*r){ damagePlayerHit(b.dmg); enemyBullets.splice(i,1); }
  }

  // particles
  for(let i=particles.length-1;i>=0;i--){ const p=particles[i]; p.x+=p.vx*dt; p.y+=p.vy*dt; p.life-=dt; if(p.life<=0) particles.splice(i,1); }
}

// ===== Drawing =====
function draw(){
  ctx.fillStyle='#0a0f1f'; ctx.fillRect(0,0,W(),H());
  ctx.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--grid').trim()||'#1b2540';
  ctx.lineWidth=1; ctx.beginPath(); for(let x=0;x<W();x+=40){ ctx.moveTo(x+0.5,0); ctx.lineTo(x+0.5,H()); } for(let y=0;y<H();y+=40){ ctx.moveTo(0,y+0.5); ctx.lineTo(W(),y+0.5); } ctx.stroke();

  for(const o of currentMap.obstacles){ ctx.fillStyle='#111a30'; ctx.strokeStyle='#2b3a63'; ctx.lineWidth=2; ctx.fillRect(o.x,o.y,o.w,o.h); ctx.strokeRect(o.x+0.5,o.y+0.5,o.w-1,o.h-1); }

  const grd=ctx.createRadialGradient(W()/2,H()/2,Math.min(W(),H())*0.2,W()/2,H()/2,Math.max(W(),H())); grd.addColorStop(0,'rgba(0,0,0,0)'); grd.addColorStop(1,'rgba(0,0,0,0.25)'); ctx.fillStyle=grd; ctx.fillRect(0,0,W(),H());

  for(const b of bullets){ ctx.save(); ctx.translate(b.x,b.y); ctx.fillStyle='#0006'; ctx.beginPath(); ctx.arc(2,2,3,0,TAU); ctx.fill(); ctx.fillStyle=b.color||'#7aa2f7'; ctx.beginPath(); ctx.arc(0,0,3,0,TAU); ctx.fill(); ctx.restore(); }
  for(const eb of enemyBullets){ ctx.fillStyle=eb.color||'#ff8888'; ctx.beginPath(); ctx.arc(eb.x,eb.y,(eb.r||4),0,TAU); ctx.fill(); }

  for(const e of enemies){ e.boss?drawBoss(e):drawZombie(e); }
  drawPlayer();

  for(const p of particles){ ctx.fillStyle=p.color||'#fff'; ctx.globalAlpha=Math.max(0,Math.min(1,p.life*3)); ctx.fillRect(p.x,p.y,3,3); ctx.globalAlpha=1; }

  if(activeBoss){
    const pad=24,w=W()-pad*2,h=12,frac=clamp(activeBoss.hp/activeBoss.hpMax,0,1);
    ctx.fillStyle='#0008'; ctx.fillRect(pad,12,w,h); ctx.fillStyle='#ff6b6b'; ctx.fillRect(pad,12,w*frac,h);
    ctx.fillStyle='#e8eefc'; ctx.font='12px system-ui'; ctx.textAlign='center'; ctx.fillText(`${activeBoss.name}`, W()/2, 22);
  }
}
function drawPlayer(){
  const ang=Math.atan2(mouse.y-player.y,mouse.x-player.x);
  ctx.save(); ctx.translate(player.x,player.y); ctx.rotate(ang);
  ctx.fillStyle='rgba(0,0,0,0.35)'; round(-player.r+3,-player.r+6,player.r*2,player.r*2,10,true);
  ctx.fillStyle=player.inv>0 ? '#a0b5ff' : '#e8eefc'; round(-player.r,-player.r,player.r*2,player.r*2,10,true);
  const w=currentWeapon||WEAPONS[0], br=w.barrel;
  ctx.fillStyle='#2b3350'; round(-10,-6,14,12,4,true);
  ctx.fillStyle='#7aa2f7'; round(0,-br.th/2,br.len,br.th,4,true);
  ctx.fillStyle=br.tip; round(br.len-4,-br.th*0.35,6,br.th*0.7,3,true);
  ctx.restore();
}
function drawZombie(e){
  ctx.save();
  ctx.fillStyle='rgba(0,0,0,0.35)'; round(e.x-e.r+3,e.y-e.r+6,e.r*2,e.r*2,8,true);
  if(e.kind==='walker'){ ctx.fillStyle='#223a7a'; round(e.x-e.r,e.y-e.r,e.r*2,e.r*2,8,true);
    ctx.fillStyle=BASE_TYPES.walker.color; ctx.beginPath(); ctx.arc(e.x,e.y-e.r*0.9,e.r*0.7,0,TAU); ctx.fill();
    ctx.fillStyle='#0b0f1a'; ctx.beginPath(); ctx.arc(e.x-4,e.y-e.r*1.05,2,0,TAU); ctx.fill(); ctx.beginPath(); ctx.arc(e.x+4,e.y-e.r*1.05,2,0,TAU); ctx.fill();
  } else if(e.kind==='runner'){ ctx.fillStyle='#1e6a3a'; round(e.x-e.r*0.9,e.y-e.r*0.9,e.r*1.8,e.r*1.8,10,true);
    ctx.fillStyle=BASE_TYPES.runner.color; ctx.beginPath(); ctx.arc(e.x+2,e.y-e.r*0.9,e.r*0.6,0,TAU); ctx.fill();
    ctx.fillStyle='#8cf0a0'; ctx.fillRect(e.x-e.r*0.8,e.y+e.r*0.3,e.r*1.6,4);
  } else { ctx.fillStyle='#7a4a16'; round(e.x-e.r,e.y-e.r,e.r*2,e.r*2,6,true);
    ctx.strokeStyle='#ffcf70'; ctx.lineWidth=4; ctx.beginPath(); ctx.arc(e.x,e.y,e.r*0.85,0,TAU); ctx.stroke();
    ctx.fillStyle=BASE_TYPES.tank.color; ctx.beginPath(); ctx.arc(e.x,e.y-e.r*0.7,e.r*0.7,0,TAU); ctx.fill();
  }
  const w=e.r*2,hpw=w*clamp(e.hp/e.hpMax,0,1); ctx.fillStyle='#0007'; ctx.fillRect(e.x-e.r,e.y-e.r-9,w,5); ctx.fillStyle='#4cd964'; ctx.fillRect(e.x-e.r,e.y-e.r-9,hpw,5);
  ctx.restore();
}
function drawBoss(b){
  ctx.save();
  ctx.fillStyle='rgba(0,0,0,0.45)'; round(b.x-b.r+4,b.y-b.r+8,b.r*2,b.r*2,10,true);
  ctx.fillStyle=b.color; round(b.x-b.r,b.y-b.r,b.r*2,b.r*2,10,true);
  ctx.strokeStyle='#fff8'; ctx.lineWidth=3; ctx.beginPath(); ctx.arc(b.x,b.y,b.r*0.5,0,TAU); ctx.stroke();
  ctx.fillStyle='#0b0f1a'; ctx.beginPath(); ctx.arc(b.x-6,b.y-b.r*0.4,3,0,TAU); ctx.fill(); ctx.beginPath(); ctx.arc(b.x+6,b.y-b.r*0.4,3,0,TAU); ctx.fill();
  ctx.restore();
}
function round(x,y,w,h,r,fill=true){ const rr=Math.min(r,w/2,h/2); ctx.beginPath(); ctx.moveTo(x+rr,y);
  ctx.arcTo(x+w,y,x+w,y+h,rr); ctx.arcTo(x+w,y+h,x,y+h,rr); ctx.arcTo(x,y+h,x,y,rr); ctx.arcTo(x,y,x+w,y,rr); if(fill) ctx.fill(); else ctx.stroke(); }

// ===== Start / Modals =====
ui.inter.addEventListener('click',()=>{}); ui.setup.addEventListener('click',()=>{});
function boot(){ setWeapon('pistol'); openSetup(); }
boot(); startGame();

})();
</script>
</body>
</html>
"""
        elif mode == "Popup":
            self.html = """<!DOCTYPE html>
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
