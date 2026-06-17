const input = document.querySelector("#videoInput");
const video = document.querySelector("#sourceVideo");
const overlay = document.querySelector("#overlayCanvas");
const emptyState = document.querySelector("#emptyState");
const playButton = document.querySelector("#playButton");
const syntheticButton = document.querySelector("#syntheticButton");
const resetButton = document.querySelector("#resetButton");
const sensitivityInput = document.querySelector("#sensitivity");
const cellSizeInput = document.querySelector("#cellSize");
const countMetric = document.querySelector("#countMetric");
const activityMetric = document.querySelector("#activityMetric");
const elapsedMetric = document.querySelector("#elapsedMetric");
const entryZone = document.querySelector("#entryZone");
const tableZone = document.querySelector("#tableZone");
const anesZone = document.querySelector("#anesZone");
const sparkline = document.querySelector("#sparkline");

const ctx = overlay.getContext("2d");
const sparkCtx = sparkline.getContext("2d");
const work = document.createElement("canvas");
const workCtx = work.getContext("2d", { willReadFrequently: true });

let previousFrame = null;
let activityHistory = [];
let rafId = null;
let syntheticMode = false;
let syntheticStartedAt = 0;

input.addEventListener("change", () => {
  const file = input.files?.[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  syntheticMode = false;
  video.src = url;
  video.load();
  emptyState.hidden = true;
  resetMetrics();
});

playButton.addEventListener("click", () => {
  if (!video.src) return;
  if (video.paused) {
    video.play();
    tick();
  } else {
    video.pause();
  }
});

syntheticButton.addEventListener("click", () => {
  syntheticMode = true;
  syntheticStartedAt = performance.now();
  video.pause();
  emptyState.hidden = true;
  resetMetrics({ keepSyntheticMode: true });
  tick();
});

resetButton.addEventListener("click", resetMetrics);
video.addEventListener("play", tick);
video.addEventListener("pause", () => cancelAnimationFrame(rafId));
video.addEventListener("loadedmetadata", resizeOverlay);
window.addEventListener("resize", resizeOverlay);

function tick() {
  resizeOverlay();
  if (syntheticMode) {
    analyzeSyntheticFrame();
    rafId = requestAnimationFrame(tick);
    return;
  }
  analyzeFrame();
  rafId = requestAnimationFrame(tick);
}

function resizeOverlay() {
  const rect = overlay.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  overlay.width = Math.max(1, Math.floor(rect.width * dpr));
  overlay.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function analyzeFrame() {
  if (video.readyState < 2 || video.paused || video.ended) return;

  const targetWidth = 320;
  const ratio = video.videoHeight / Math.max(video.videoWidth, 1);
  work.width = targetWidth;
  work.height = Math.max(1, Math.round(targetWidth * ratio));
  workCtx.drawImage(video, 0, 0, work.width, work.height);
  const image = workCtx.getImageData(0, 0, work.width, work.height);

  if (!previousFrame) {
    previousFrame = image;
    return;
  }

  const cellSize = Number(cellSizeInput.value);
  const sensitivity = Number(sensitivityInput.value);
  const cells = collectMotionCells(image, previousFrame, cellSize, sensitivity);
  const boxes = clusterCells(cells, cellSize, work.width, work.height);
  const activity = cells.length;
  previousFrame = image;
  activityHistory.push(activity);
  if (activityHistory.length > 80) activityHistory.shift();

  drawOverlay(boxes, activity);
  updateMetrics(boxes, activity, video.currentTime);
}

function analyzeSyntheticFrame() {
  const elapsed = (performance.now() - syntheticStartedAt) / 1000;
  const boxes = [
    {
      x: 0.12 + 0.22 * oscillate(elapsed, 0.42),
      y: 0.48,
      w: 0.09,
      h: 0.22,
    },
    {
      x: 0.67 - 0.14 * oscillate(elapsed + 1.1, 0.31),
      y: 0.28 + 0.08 * oscillate(elapsed, 0.7),
      w: 0.08,
      h: 0.20,
    },
    {
      x: 0.43 + 0.08 * oscillate(elapsed + 2.6, 0.6),
      y: 0.66,
      w: 0.10,
      h: 0.18,
    },
  ];
  const activity = Math.round(28 + 18 * oscillate(elapsed, 1.3));
  activityHistory.push(activity);
  if (activityHistory.length > 80) activityHistory.shift();
  drawOverlay(boxes, activity);
  updateMetrics(boxes, activity, elapsed);
}

function collectMotionCells(current, previous, cellSize, sensitivity) {
  const cells = [];
  const cols = Math.ceil(current.width / cellSize);
  const rows = Math.ceil(current.height / cellSize);

  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      let changed = 0;
      let sampled = 0;
      for (let y = row * cellSize; y < Math.min((row + 1) * cellSize, current.height); y += 4) {
        for (let x = col * cellSize; x < Math.min((col + 1) * cellSize, current.width); x += 4) {
          const index = (y * current.width + x) * 4;
          const currentLum = luminance(current.data, index);
          const previousLum = luminance(previous.data, index);
          if (Math.abs(currentLum - previousLum) > sensitivity) changed += 1;
          sampled += 1;
        }
      }
      if (sampled > 0 && changed / sampled > 0.18) {
        cells.push({ col, row });
      }
    }
  }

  return cells;
}

function clusterCells(cells, cellSize, width, height) {
  const key = (cell) => `${cell.col}:${cell.row}`;
  const pending = new Map(cells.map((cell) => [key(cell), cell]));
  const boxes = [];

  for (const start of cells) {
    if (!pending.has(key(start))) continue;
    const stack = [start];
    pending.delete(key(start));
    let minCol = start.col;
    let maxCol = start.col;
    let minRow = start.row;
    let maxRow = start.row;

    while (stack.length) {
      const cell = stack.pop();
      minCol = Math.min(minCol, cell.col);
      maxCol = Math.max(maxCol, cell.col);
      minRow = Math.min(minRow, cell.row);
      maxRow = Math.max(maxRow, cell.row);
      for (const next of neighbors(cell)) {
        const nextKey = key(next);
        if (pending.has(nextKey)) {
          stack.push(pending.get(nextKey));
          pending.delete(nextKey);
        }
      }
    }

    const box = {
      x: (minCol * cellSize) / width,
      y: (minRow * cellSize) / height,
      w: ((maxCol - minCol + 1) * cellSize) / width,
      h: ((maxRow - minRow + 1) * cellSize) / height,
    };
    if (box.w * box.h > 0.006) boxes.push(box);
  }

  return boxes.slice(0, 12);
}

function neighbors(cell) {
  return [
    { col: cell.col + 1, row: cell.row },
    { col: cell.col - 1, row: cell.row },
    { col: cell.col, row: cell.row + 1 },
    { col: cell.col, row: cell.row - 1 },
  ];
}

function drawOverlay(boxes, activity) {
  const rect = overlay.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  drawZones(rect.width, rect.height);
  ctx.lineWidth = 2;
  ctx.font = "700 13px Inter, system-ui, sans-serif";

  boxes.forEach((box, index) => {
    const x = box.x * rect.width;
    const y = box.y * rect.height;
    const w = box.w * rect.width;
    const h = box.h * rect.height;
    ctx.strokeStyle = "#37d6a3";
    ctx.fillStyle = "rgba(55, 214, 163, 0.12)";
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "#f3f7fb";
    ctx.fillText(`M${index + 1}`, x + 7, Math.max(18, y - 6));
  });

  drawSparkline(activity);
}

function drawZones(width, height) {
  const zones = [
    ["entry", 0, 0, 0.22, 1],
    ["table", 0.3, 0.24, 0.7, 0.82],
    ["anesthesia", 0.7, 0, 1, 0.42],
  ];
  ctx.strokeStyle = "rgba(85, 167, 255, 0.72)";
  ctx.fillStyle = "rgba(85, 167, 255, 0.08)";
  ctx.font = "700 12px Inter, system-ui, sans-serif";
  zones.forEach(([name, x0, y0, x1, y1]) => {
    const x = x0 * width;
    const y = y0 * height;
    const w = (x1 - x0) * width;
    const h = (y1 - y0) * height;
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "rgba(243, 247, 251, 0.85)";
    ctx.fillText(name, x + 8, y + 18);
    ctx.fillStyle = "rgba(85, 167, 255, 0.08)";
  });
}

function drawSparkline(activity) {
  const width = sparkline.width;
  const height = sparkline.height;
  sparkCtx.clearRect(0, 0, width, height);
  sparkCtx.fillStyle = "#10171d";
  sparkCtx.fillRect(0, 0, width, height);
  sparkCtx.strokeStyle = "#37d6a3";
  sparkCtx.lineWidth = 3;
  sparkCtx.beginPath();
  const max = Math.max(...activityHistory, 1);
  activityHistory.forEach((value, index) => {
    const x = (index / Math.max(activityHistory.length - 1, 1)) * width;
    const y = height - (value / max) * (height - 12) - 6;
    if (index === 0) sparkCtx.moveTo(x, y);
    else sparkCtx.lineTo(x, y);
  });
  sparkCtx.stroke();
}

function updateMetrics(boxes, activity, elapsedSeconds) {
  countMetric.textContent = String(boxes.length);
  activityMetric.textContent = String(activity);
  elapsedMetric.textContent = `${elapsedSeconds.toFixed(1)}s`;
  const zoneCounts = { entry: 0, table: 0, anes: 0 };
  boxes.forEach((box) => {
    const cx = box.x + box.w / 2;
    const cy = box.y + box.h / 2;
    if (cx <= 0.22) zoneCounts.entry += 1;
    if (cx >= 0.3 && cx <= 0.7 && cy >= 0.24 && cy <= 0.82) zoneCounts.table += 1;
    if (cx >= 0.7 && cy <= 0.42) zoneCounts.anes += 1;
  });
  entryZone.textContent = String(zoneCounts.entry);
  tableZone.textContent = String(zoneCounts.table);
  anesZone.textContent = String(zoneCounts.anes);
}

function resetMetrics(options = {}) {
  if (!options.keepSyntheticMode) syntheticMode = false;
  previousFrame = null;
  activityHistory = [];
  countMetric.textContent = "0";
  activityMetric.textContent = "0";
  elapsedMetric.textContent = "0.0s";
  entryZone.textContent = "0";
  tableZone.textContent = "0";
  anesZone.textContent = "0";
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  sparkCtx.clearRect(0, 0, sparkline.width, sparkline.height);
}

function luminance(data, index) {
  return data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114;
}

function oscillate(value, speed) {
  return (Math.sin(value * Math.PI * 2 * speed) + 1) / 2;
}
