// GOPHER hero: an exploded exterior view that assembles as the page scrolls through the hero.
//
// Unlike the MOSAIC site, no model data is sent to the browser. The hero is a sequence of flat
// pre-rendered images (assets/hero/f00.webp = exploded ... last = assembled) drawn on a 2D canvas.
// To change the number of frames, re-render them and edit FRAMES below.

const FRAMES = 28;
const canvas = document.getElementById("wire");
const ctx = canvas.getContext("2d");
const stage = canvas.parentElement;
const hero = document.getElementById("hero");

const frames = new Array(FRAMES).fill(null);   // loaded Image objects
let target = 0;      // frame the scroll position asks for (fractional)
let current = 0;     // frame being shown, eased toward target
let shown = -1;      // index last drawn, so we only redraw on change

function frameUrl(i) { return "assets/hero/f" + String(i).padStart(2, "0") + ".webp"; }

function loadFrame(i) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => { frames[i] = img; resolve(); };
    img.onerror = () => reject(new Error("frame " + i));
    img.src = frameUrl(i);
  });
}

// nearest frame that has finished loading, searching outward from i
function nearestLoaded(i) {
  for (let d = 0; d < FRAMES; d++) {
    if (frames[i - d]) return i - d;
    if (frames[i + d]) return i + d;
  }
  return -1;
}

function draw(force) {
  const i = nearestLoaded(Math.round(current));
  if (i < 0 || (i === shown && !force)) return;
  shown = i;
  const w = canvas.width, h = canvas.height, img = frames[i];
  const s = Math.min(w / img.width, h / img.height);     // fit inside, keep proportions
  const dw = img.width * s, dh = img.height * s;
  ctx.clearRect(0, 0, w, h);
  ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
}

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(stage.clientWidth * dpr);
  canvas.height = Math.round(stage.clientHeight * dpr);
  draw(true);
}
window.addEventListener("resize", resize);

// scroll in the hero drives assembly: top = exploded, end of hero = assembled
function smoothstep(t, a, b) { t = Math.min(1, Math.max(0, (t - a) / (b - a))); return t * t * (3 - 2 * t); }
function onScroll() {
  const range = hero.offsetHeight - window.innerHeight;
  const t = range > 0 ? Math.min(1, Math.max(0, window.scrollY / range)) : 0;
  target = smoothstep(t, 0.05, 0.85) * (FRAMES - 1);
}
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();
current = target;                    // start at the state the page was opened in

let last = performance.now();
function animate(now = performance.now()) {
  requestAnimationFrame(animate);
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  current += (target - current) * Math.min(1, dt * 7);
  draw(false);
}

// show the frame the page opened on first, then fetch the rest in the background
const first = Math.round(target);
loadFrame(first)
  .then(() => {
    stage.classList.add("ready");
    document.getElementById("model-status").hidden = true;   // do not rely on the CSS fade alone
    resize();
    animate();
    for (let i = 0; i < FRAMES; i++) if (i !== first) loadFrame(i).then(() => draw(true)).catch(() => {});
  })
  .catch((err) => {
    document.getElementById("model-status").textContent = "Image failed to load: " + err.message;
  });
