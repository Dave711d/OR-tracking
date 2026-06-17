const input = document.querySelector("#videoInput");
const video = document.querySelector("#sourceVideo");
const overlay = document.querySelector("#overlayCanvas");
const emptyState = document.querySelector("#emptyState");
const playButton = document.querySelector("#playButton");
const syntheticButton = document.querySelector("#syntheticButton");
const resetButton = document.querySelector("#resetButton");
const sensitivityInput = document.querySelector("#sensitivity");
const cellSizeInput = document.querySelector("#cellSize");
const stageMetric = document.querySelector("#stageMetric");
const countMetric = document.querySelector("#countMetric");
const tableSideMetric = document.querySelector("#tableSideMetric");
const tableRoster = document.querySelector("#tableRoster");
const activityMetric = document.querySelector("#activityMetric");
const elapsedMetric = document.querySelector("#elapsedMetric");
const entryZone = document.querySelector("#entryZone");
const accessZone = document.querySelector("#accessZone");
const tableZone = document.querySelector("#tableZone");
const tableLeftZone = document.querySelector("#tableLeftZone");
const tableRightZone = document.querySelector("#tableRightZone");
const anesZone = document.querySelector("#anesZone");
const imagingZone = document.querySelector("#imagingZone");
const deviceZone = document.querySelector("#deviceZone");
const tableOperatorRole = document.querySelector("#tableOperatorRole");
const accessOperatorRole = document.querySelector("#accessOperatorRole");
const devicePrepRole = document.querySelector("#devicePrepRole");
const imagingRole = document.querySelector("#imagingRole");
const anesthesiaRole = document.querySelector("#anesthesiaRole");
const entryRole = document.querySelector("#entryRole");
const sparkline = document.querySelector("#sparkline");

const ctx = overlay.getContext("2d");
const sparkCtx = sparkline.getContext("2d");
const work = document.createElement("canvas");
const workCtx = work.getContext("2d", { willReadFrequently: true });

const TAVR_STAGES = [
  {
    key: "room_prep_drape",
    label: "Room prep / drape",
    duration: 5,
    activity: 30,
    pace: 1.05,
    roles: ["device_prep", "anesthesia", "entry_supply"],
  },
  {
    key: "access_sheathing",
    label: "Access / sheathing",
    duration: 5,
    activity: 40,
    pace: 1.2,
    roles: ["access_operator", "table_operator", "anesthesia", "entry_supply"],
  },
  {
    key: "angio_alignment_crossing",
    label: "Angio alignment / crossing",
    duration: 5,
    activity: 36,
    pace: 0.9,
    roles: ["table_operator", "imaging", "anesthesia"],
  },
  {
    key: "bav_optional",
    label: "Balloon valvuloplasty",
    duration: 4,
    activity: 42,
    pace: 0.75,
    roles: ["table_operator", "imaging", "anesthesia"],
  },
  {
    key: "valve_delivery_positioning",
    label: "Valve delivery / positioning",
    duration: 5,
    activity: 44,
    pace: 1.1,
    roles: ["device_prep", "table_operator", "imaging", "anesthesia"],
  },
  {
    key: "valve_deployment",
    label: "Valve deployment",
    duration: 4,
    activity: 46,
    pace: 1.35,
    roles: ["table_operator", "imaging", "anesthesia"],
  },
  {
    key: "post_deploy_assessment",
    label: "Post-deploy assessment",
    duration: 5,
    activity: 28,
    pace: 0.75,
    roles: ["table_operator", "imaging", "anesthesia"],
  },
  {
    key: "closure_finish",
    label: "Closure / finish",
    duration: 5,
    activity: 34,
    pace: 1,
    roles: ["access_operator", "table_operator", "entry_supply"],
  },
];

const ZONES = [
  { key: "entry", label: "entry", x0: 0, y0: 0, x1: 0.16, y1: 1 },
  { key: "access", label: "access", x0: 0.22, y0: 0.58, x1: 0.5, y1: 0.98 },
  { key: "table", label: "table", x0: 0.3, y0: 0.24, x1: 0.7, y1: 0.82 },
  { key: "table_left", label: "table L", x0: 0.22, y0: 0.22, x1: 0.42, y1: 0.78 },
  { key: "table_right", label: "table R", x0: 0.58, y0: 0.22, x1: 0.78, y1: 0.78 },
  { key: "anesthesia", label: "anesthesia", x0: 0.72, y0: 0, x1: 1, y1: 0.34 },
  { key: "imaging", label: "imaging", x0: 0.42, y0: 0, x1: 0.76, y1: 0.24 },
  { key: "device_table", label: "device", x0: 0, y0: 0, x1: 0.28, y1: 0.35 },
];

const ROLE_LABELS = {
  table_operator: "Table op",
  access_operator: "Access",
  device_prep: "Device",
  imaging: "Imaging",
  anesthesia: "Anes",
  entry_supply: "Supply",
};

const ROLE_COLORS = {
  table_operator: "#37d6a3",
  access_operator: "#55a7ff",
  device_prep: "#ffcc66",
  imaging: "#6ee7ff",
  anesthesia: "#c79cff",
  entry_supply: "#ff8f7a",
  motion: "#37d6a3",
};

const ROLE_FILLS = {
  table_operator: "rgba(55, 214, 163, 0.14)",
  access_operator: "rgba(85, 167, 255, 0.14)",
  device_prep: "rgba(255, 204, 102, 0.16)",
  imaging: "rgba(110, 231, 255, 0.14)",
  anesthesia: "rgba(199, 156, 255, 0.16)",
  entry_supply: "rgba(255, 143, 122, 0.16)",
  motion: "rgba(55, 214, 163, 0.12)",
};

const TABLE_SIDE_ZONES = new Set(["access", "table", "table_left", "table_right"]);
const TABLE_SIDE_ROLES = new Set(["access_operator", "table_operator"]);
const ROLE_ZONE_PRIORITY = [
  "access",
  "device_table",
  "imaging",
  "anesthesia",
  "table_left",
  "table_right",
  "table",
  "entry",
];
const SYNTHETIC_CYCLE_SECONDS = TAVR_STAGES.reduce(
  (total, stage) => total + stage.duration,
  0,
);

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
  video.hidden = false;
  video.load();
  emptyState.hidden = true;
  resetMetrics();
});

playButton.addEventListener("click", () => {
  if (!video.src || video.hidden) return;
  if (video.paused) {
    video.play();
    tick();
  } else {
    video.pause();
  }
});

syntheticButton.addEventListener("click", () => {
  cancelAnimationFrame(rafId);
  syntheticMode = true;
  syntheticStartedAt = performance.now();
  video.pause();
  video.hidden = true;
  emptyState.hidden = true;
  resetMetrics({ keepSyntheticMode: true });
  tick();
});

resetButton.addEventListener("click", () => {
  cancelAnimationFrame(rafId);
  video.hidden = false;
  resetMetrics();
  if (!video.src) emptyState.hidden = false;
});
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

  drawOverlay(boxes, activity, { label: "Uploaded review", progress: 0 });
  updateMetrics(boxes, activity, video.currentTime, "Uploaded review");
}

function analyzeSyntheticFrame() {
  const elapsed = (performance.now() - syntheticStartedAt) / 1000;
  const stage = getTavrStage(elapsed);
  const boxes = buildSyntheticTavrBoxes(elapsed, stage);
  const activity = Math.round(stage.activity + 14 * oscillate(elapsed, stage.pace));
  activityHistory.push(activity);
  if (activityHistory.length > 80) activityHistory.shift();
  drawOverlay(boxes, activity, stage);
  updateMetrics(boxes, activity, elapsed, stage.label);
}

function getTavrStage(elapsed) {
  let stageSecond = elapsed % SYNTHETIC_CYCLE_SECONDS;
  for (const stage of TAVR_STAGES) {
    if (stageSecond < stage.duration) {
      return { ...stage, progress: stageSecond / stage.duration };
    }
    stageSecond -= stage.duration;
  }
  return { ...TAVR_STAGES[0], progress: 0 };
}

function buildSyntheticTavrBoxes(elapsed, stage) {
  const boxes = [
    {
      id: "T1",
      role: "table_operator",
      x: 0.37 + 0.05 * oscillate(elapsed, 0.28),
      y: 0.5 + 0.03 * oscillate(elapsed + 0.4, 0.36),
      w: 0.08,
      h: 0.22,
    },
    {
      id: "T2",
      role: "table_operator",
      label: "Table 2",
      x: 0.60 - 0.04 * oscillate(elapsed + 0.8, 0.26),
      y: 0.43 + 0.04 * oscillate(elapsed + 1.3, 0.34),
      w: 0.08,
      h: 0.21,
    },
    {
      id: "A1",
      role: "access_operator",
      x: 0.31 + 0.04 * oscillate(elapsed + 2.4, 0.22),
      y: 0.70 + 0.02 * oscillate(elapsed + 0.2, 0.42),
      w: 0.09,
      h: 0.18,
    },
    {
      id: "AN1",
      role: "anesthesia",
      x: 0.80 + 0.03 * oscillate(elapsed + 0.9, 0.18),
      y: 0.18 + 0.04 * oscillate(elapsed + 1.8, 0.3),
      w: 0.08,
      h: 0.2,
    },
    {
      id: "S1",
      role: "entry_supply",
      x: 0.05 + 0.08 * oscillate(elapsed + 1.6, 0.3),
      y: 0.42 + 0.12 * oscillate(elapsed + 0.5, 0.2),
      w: 0.08,
      h: 0.21,
    },
    {
      id: "D1",
      role: "device_prep",
      x: 0.13 + 0.04 * oscillate(elapsed + 0.3, 0.24),
      y: 0.18 + 0.02 * oscillate(elapsed + 1.1, 0.36),
      w: 0.08,
      h: 0.2,
    },
    {
      id: "I1",
      role: "imaging",
      x: 0.54 + 0.04 * oscillate(elapsed + 2.3, 0.28),
      y: 0.13 + 0.02 * oscillate(elapsed + 0.7, 0.3),
      w: 0.08,
      h: 0.21,
    },
  ];

  return boxes
    .filter((box) => stage.roles.includes(box.role))
    .map((box) => ({
      ...box,
      tableSide: TABLE_SIDE_ROLES.has(box.role),
    }));
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

function drawOverlay(boxes, activity, stage = null) {
  const rect = overlay.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  drawZones(rect.width, rect.height);
  drawStageBanner(stage, rect.width);
  ctx.lineWidth = 2;
  ctx.font = "700 13px Inter, system-ui, sans-serif";

  boxes.forEach((box, index) => {
    const x = box.x * rect.width;
    const y = box.y * rect.height;
    const w = box.w * rect.width;
    const h = box.h * rect.height;
    const roleKey = box.role || "motion";
    const label = box.label || ROLE_LABELS[roleKey] || `M${index + 1}`;
    const labelY = Math.max(18, y - 6);
    const labelWidth = Math.ceil(ctx.measureText(label).width) + 12;

    ctx.strokeStyle = ROLE_COLORS[roleKey] || ROLE_COLORS.motion;
    ctx.fillStyle = ROLE_FILLS[roleKey] || ROLE_FILLS.motion;
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "rgba(8, 11, 14, 0.78)";
    ctx.fillRect(x, labelY - 14, labelWidth, 18);
    ctx.fillStyle = "#f3f7fb";
    ctx.fillText(label, x + 6, labelY);
  });

  drawSparkline(activity);
}

function drawZones(width, height) {
  ctx.save();
  ctx.strokeStyle = "rgba(85, 167, 255, 0.72)";
  ctx.fillStyle = "rgba(85, 167, 255, 0.08)";
  ctx.font = "700 12px Inter, system-ui, sans-serif";
  ZONES.forEach((zone) => {
    const x = zone.x0 * width;
    const y = zone.y0 * height;
    const w = (zone.x1 - zone.x0) * width;
    const h = (zone.y1 - zone.y0) * height;
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = "rgba(243, 247, 251, 0.85)";
    ctx.fillText(zone.label, x + 8, y + 18);
    ctx.fillStyle = "rgba(85, 167, 255, 0.08)";
  });
  ctx.restore();
}

function drawStageBanner(stage, width) {
  if (!stage?.label || width < 80) return;

  const label = `TAVR: ${stage.label}`;
  ctx.save();
  ctx.font = "700 13px Inter, system-ui, sans-serif";
  const bannerWidth = Math.min(width - 24, Math.max(156, ctx.measureText(label).width + 28));
  if (bannerWidth <= 0) {
    ctx.restore();
    return;
  }

  ctx.fillStyle = "rgba(8, 11, 14, 0.82)";
  ctx.fillRect(12, 12, bannerWidth, 32);
  ctx.fillStyle = "#f3f7fb";
  ctx.fillText(label, 24, 33);
  ctx.fillStyle = "#37d6a3";
  ctx.fillRect(12, 42, Math.max(0, bannerWidth * (stage.progress || 0)), 2);
  ctx.restore();
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

function updateMetrics(boxes, activity, elapsedSeconds, stageLabel = "Uploaded review") {
  const summary = summarizeBoxes(boxes);
  stageMetric.textContent = stageLabel;
  countMetric.textContent = String(boxes.length);
  tableSideMetric.textContent = String(summary.tableSide);
  activityMetric.textContent = String(activity);
  elapsedMetric.textContent = `${elapsedSeconds.toFixed(1)}s`;
  renderTableRoster(summary.tableRoster);
  entryZone.textContent = String(summary.zones.entry);
  accessZone.textContent = String(summary.zones.access);
  tableZone.textContent = String(summary.zones.table);
  tableLeftZone.textContent = String(summary.zones.table_left);
  tableRightZone.textContent = String(summary.zones.table_right);
  anesZone.textContent = String(summary.zones.anesthesia);
  imagingZone.textContent = String(summary.zones.imaging);
  deviceZone.textContent = String(summary.zones.device_table);
  tableOperatorRole.textContent = String(summary.roles.table_operator);
  accessOperatorRole.textContent = String(summary.roles.access_operator);
  devicePrepRole.textContent = String(summary.roles.device_prep);
  imagingRole.textContent = String(summary.roles.imaging);
  anesthesiaRole.textContent = String(summary.roles.anesthesia);
  entryRole.textContent = String(summary.roles.entry_supply);
}

function summarizeBoxes(boxes) {
  const summary = {
    tableSide: 0,
    zones: {
      entry: 0,
      access: 0,
      table: 0,
      table_left: 0,
      table_right: 0,
      anesthesia: 0,
      imaging: 0,
      device_table: 0,
    },
    roles: {
      table_operator: 0,
      access_operator: 0,
      device_prep: 0,
      imaging: 0,
      anesthesia: 0,
      entry_supply: 0,
    },
    tableRoster: [],
  };

  boxes.forEach((box, index) => {
    const zoneKeys = getZoneKeys(box);
    const roleKey = box.role || inferRoleFromZones(zoneKeys);
    const inferredTableSide = zoneKeys.some((zoneKey) => TABLE_SIDE_ZONES.has(zoneKey));
    const isTableSide = box.tableSide ?? inferredTableSide;

    zoneKeys.forEach((zoneKey) => {
      if (summary.zones[zoneKey] !== undefined) summary.zones[zoneKey] += 1;
    });
    if (roleKey && summary.roles[roleKey] !== undefined) summary.roles[roleKey] += 1;
    if (isTableSide) {
      summary.tableSide += 1;
      summary.tableRoster.push({
        id: box.id || `M${index + 1}`,
        role: roleKey || "motion",
      });
    }
  });

  return summary;
}

function getZoneKeys(box) {
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  return ZONES.filter(
    ({ x0, y0, x1, y1 }) => cx >= x0 && cx <= x1 && cy >= y0 && cy <= y1,
  ).map((zone) => zone.key);
}

function inferRoleFromZones(zoneKeys) {
  const primaryZone = ROLE_ZONE_PRIORITY.find((zoneKey) => zoneKeys.includes(zoneKey));
  if (primaryZone === "access") return "access_operator";
  if (primaryZone === "device_table") return "device_prep";
  if (primaryZone === "imaging") return "imaging";
  if (primaryZone === "anesthesia") return "anesthesia";
  if (primaryZone === "table" || primaryZone === "table_left" || primaryZone === "table_right") {
    return "table_operator";
  }
  if (primaryZone === "entry") return "entry_supply";
  return null;
}

function renderTableRoster(roster) {
  tableRoster.replaceChildren();
  if (!roster.length) {
    const item = document.createElement("li");
    item.textContent = "None";
    tableRoster.append(item);
    return;
  }
  roster.forEach(({ id, role }) => {
    const item = document.createElement("li");
    const roleLabel = ROLE_LABELS[role] || role;
    item.textContent = `${id} - ${roleLabel}`;
    tableRoster.append(item);
  });
}

function resetMetrics(options = {}) {
  if (!options.keepSyntheticMode) syntheticMode = false;
  previousFrame = null;
  activityHistory = [];
  stageMetric.textContent = "Idle";
  countMetric.textContent = "0";
  tableSideMetric.textContent = "0";
  renderTableRoster([]);
  activityMetric.textContent = "0";
  elapsedMetric.textContent = "0.0s";
  entryZone.textContent = "0";
  accessZone.textContent = "0";
  tableZone.textContent = "0";
  tableLeftZone.textContent = "0";
  tableRightZone.textContent = "0";
  anesZone.textContent = "0";
  imagingZone.textContent = "0";
  deviceZone.textContent = "0";
  tableOperatorRole.textContent = "0";
  accessOperatorRole.textContent = "0";
  devicePrepRole.textContent = "0";
  imagingRole.textContent = "0";
  anesthesiaRole.textContent = "0";
  entryRole.textContent = "0";
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  sparkCtx.clearRect(0, 0, sparkline.width, sparkline.height);
}

function luminance(data, index) {
  return data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114;
}

function oscillate(value, speed) {
  return (Math.sin(value * Math.PI * 2 * speed) + 1) / 2;
}
