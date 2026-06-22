import { BrowserTableIdentityTracker } from "./browser_identity.mjs";
import {
  ROLE_LABELS,
  asArray,
  currentTableSnapshot,
  effectiveTableSnapshot,
  eventTimeSeconds,
  focusedReplayEvents,
  formatPersonId,
  formatPersonIds,
  normalizeEvaluationPayload,
  operatorAnswerRows,
  operatorAnswerRowsFromSnapshots,
  packetForStatus,
  replayClockLabel,
  replaySnapshotAt,
  replaySnapshotLabel,
  rosterPersonLabel,
  scoreVerificationRows,
  stageRosterForStatus,
  stageTableBriefRows,
  stageTableBriefRowsFromSnapshots,
  tableSourceLabel,
  tableSnapshotSummary,
} from "./replay_view.mjs";

const input = document.querySelector("#videoInput");
const video = document.querySelector("#sourceVideo");
const overlay = document.querySelector("#overlayCanvas");
const emptyState = document.querySelector("#emptyState");
const playButton = document.querySelector("#playButton");
const liveCameraButton = document.querySelector("#liveCameraButton");
const stopLiveButton = document.querySelector("#stopLiveButton");
const liveStreamUrlInput = document.querySelector("#liveStreamUrl");
const liveStreamButton = document.querySelector("#liveStreamButton");
const liveStatus = document.querySelector("#liveStatus");
const syntheticButton = document.querySelector("#syntheticButton");
const evaluationDemoSelect = document.querySelector("#evaluationDemoSelect");
const evaluationDemoButton = document.querySelector("#evaluationDemoButton");
const evaluationSnapshotRange = document.querySelector("#evaluationSnapshotRange");
const evaluationSnapshotLabel = document.querySelector("#evaluationSnapshotLabel");
const resetButton = document.querySelector("#resetButton");
const staticFallbackInput = document.querySelector("#staticFallback");
const initialStageInput = document.querySelector("#initialStage");
const sensitivityInput = document.querySelector("#sensitivity");
const cellSizeInput = document.querySelector("#cellSize");
const stageMetric = document.querySelector("#stageMetric");
const countMetric = document.querySelector("#countMetric");
const tableSideMetric = document.querySelector("#tableSideMetric");
const operatorAnswer = document.querySelector("#operatorAnswer");
const videoWorkflow = document.querySelector("#videoWorkflow");
const workflowEventList = document.querySelector("#workflowEventList");
const stageTableBrief = document.querySelector("#stageTableBrief");
const tablePresenceSummary = document.querySelector("#tablePresenceSummary");
const tableRoster = document.querySelector("#tableRoster");
const operatorPacket = document.querySelector("#operatorPacket");
const procedureStatus = document.querySelector("#procedureStatus");
const statusSnapshotList = document.querySelector("#statusSnapshotList");
const tableTeamList = document.querySelector("#tableTeamList");
const tableIdentityList = document.querySelector("#tableIdentityList");
const stageCoverageList = document.querySelector("#stageCoverageList");
const stageRosterList = document.querySelector("#stageRosterList");
const milestoneList = document.querySelector("#milestoneList");
const eventTimelineList = document.querySelector("#eventTimelineList");
const qualityFlagList = document.querySelector("#qualityFlagList");
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

const WORKFLOW_ROLE_LABELS = {
  table_operator: "Proceduralist",
  access_operator: "Proceduralist",
  device_prep: "Device prep",
  imaging: "Imaging operator",
  anesthesia: "Anaesthetist",
  entry_supply: "Circulator",
  motion: "Motion",
};

const PATIENT_STATE_LABELS = {
  waiting_outside: "Patient out of room",
  entering_room: "Patient entering room",
  in_room: "Patient in room",
  on_table: "Patient on table",
  in_room_unverified: "Patient in room - view unavailable",
  leaving_room: "Patient leaving room",
  out_of_room: "Patient out of room",
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
const TAVR_STAGE_LOOKUP = new Map(
  TAVR_STAGES.map((stage, index) => [stage.key, { ...stage, index }]),
);
const BROWSER_STAGE_MIN_SECONDS = 1.0;
const BROWSER_STAGE_MIN_CONFIDENCE = 0.42;
const BROWSER_STAGE_ADVANCE_MARGIN = 0.06;
const BROWSER_NON_ROOM_COLORFULNESS_THRESHOLD = 8.0;
const BROWSER_RECENT_TABLE_HOLD_SECONDS = 5.0;
const EVALUATION_DEMOS = [
  {
    id: "sentara_900_room_to_fluoro_low_motion",
    label: "900s access weak support",
    url: "/demo-data/sentara-900-evaluation.json",
  },
  {
    id: "sentara_1800_mixed_room",
    label: "1800s deployment table hold",
    url: "/demo-data/sentara-1800-evaluation.json",
    default: true,
  },
  {
    id: "synthetic_full_tavr_workflow",
    label: "Full synthetic workflow",
    url: "/demo-data/synthetic-full-tavr-evaluation.json",
  },
  {
    id: "sentara_2400_fluoro_negative",
    label: "2400s fluoro held context",
    url: "/demo-data/sentara-2400-evaluation.json",
  },
  {
    id: "sentara_2700_room_post",
    label: "2700s closure weak support",
    url: "/demo-data/sentara-2700-evaluation.json",
  },
  {
    id: "sentara_900_static_table_fallback",
    label: "900s static fallback review",
    url: "/demo-data/sentara-900-static-fallback-evaluation.json",
  },
];

let previousFrame = null;
let activityHistory = [];
let browserIdentityTracker = new BrowserTableIdentityTracker();
let tableTeam = new Map();
let stageCoverage = new Map();
let stageRosterSegments = [];
let currentStageRosterSegment = null;
let milestoneProgress = new Map();
let currentMilestoneKey = null;
let lastObservedTableSnapshot = null;
let workflowState = initialWorkflowState();
let workflowEvents = [];
let currentEvaluationReplay = null;
let uploadedStageIndex = 0;
let uploadedStageStartedAt = 0;
let rafId = null;
let syntheticMode = false;
let syntheticStartedAt = 0;
let evaluationReplayRequestId = 0;
let liveMode = false;
let liveStartedAt = 0;
let liveMediaStream = null;
let activeObjectUrl = null;
let frameReadBlocked = false;

populateInitialStageOptions();
populateEvaluationDemoOptions();
scheduleDemoAutostart();

input.addEventListener("change", () => {
  const file = input.files?.[0];
  if (!file) return;
  stopLiveSource();
  revokeActiveObjectUrl();
  const url = URL.createObjectURL(file);
  activeObjectUrl = url;
  syntheticMode = false;
  liveMode = false;
  video.srcObject = null;
  video.src = url;
  video.hidden = false;
  video.load();
  emptyState.hidden = true;
  resetMetrics();
  setLiveStatus("Uploaded file ready");
});

playButton.addEventListener("click", () => {
  if (!hasVideoSource() || video.hidden) return;
  if (video.paused) {
    playVideoSource().catch(() => {});
  } else {
    video.pause();
  }
});

liveCameraButton.addEventListener("click", startLiveCamera);
liveStreamButton.addEventListener("click", startLiveStreamUrl);
stopLiveButton.addEventListener("click", () => {
  cancelAnimationFrame(rafId);
  stopLiveSource();
  video.pause();
  resetMetrics();
  syncEmptyStateToVideoSource();
});

syntheticButton.addEventListener("click", () => {
  cancelAnimationFrame(rafId);
  stopLiveSource();
  syntheticMode = true;
  syntheticStartedAt = performance.now();
  video.pause();
  video.hidden = true;
  emptyState.hidden = true;
  resetMetrics({ keepSyntheticMode: true });
  tick();
});

evaluationDemoButton.addEventListener("click", loadEvaluationDemo);
evaluationSnapshotRange.addEventListener("input", () => {
  if (!currentEvaluationReplay) return;
  renderEvaluationReplaySnapshot(
    currentEvaluationReplay,
    Number(evaluationSnapshotRange.value),
  );
});

resetButton.addEventListener("click", () => {
  cancelAnimationFrame(rafId);
  video.hidden = false;
  if (liveMode) {
    liveStartedAt = performance.now();
    resetMetrics({ keepLiveMode: true });
    playVideoSource().catch(() => {});
  } else {
    resetMetrics();
  }
  syncEmptyStateToVideoSource();
});
initialStageInput.addEventListener("change", () => {
  resetMetrics({ keepSyntheticMode: syntheticMode, keepLiveMode: liveMode });
  if (syntheticMode || liveMode) {
    cancelAnimationFrame(rafId);
    tick();
  }
});
video.addEventListener("play", tick);
video.addEventListener("pause", () => cancelAnimationFrame(rafId));
video.addEventListener("loadedmetadata", resizeOverlay);
window.addEventListener("resize", resizeOverlay);

async function loadEvaluationDemo() {
  const requestId = ++evaluationReplayRequestId;
  const demoMeta = selectedEvaluationDemo();
  cancelAnimationFrame(rafId);
  stopLiveSource();
  syntheticMode = false;
  video.pause();
  resetMetrics({ keepEvaluationReplayRequest: true });
  video.hidden = true;
  emptyState.hidden = false;
  setEmptyState("Loading evaluated demo", demoMeta.label);

  try {
    const response = await fetch(demoMeta.url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    if (requestId !== evaluationReplayRequestId) return;
    renderEvaluationReplay(normalizeEvaluationPayload(payload, demoMeta));
  } catch (error) {
    if (requestId !== evaluationReplayRequestId) return;
    setEmptyState("Demo artifact unavailable", String(error.message || error));
    procedureStatus.replaceChildren();
    appendInfoRow(procedureStatus, "Replay", "failed", { tone: "warn" });
  }
}

function renderEvaluationReplay(demo) {
  currentEvaluationReplay = demo;
  const defaultStatus = demo.statusSnapshots.at(-1) || demo.status || {};
  renderReplayVideoWorkflow(
    defaultStatus,
    demo,
    safePacketForStatus(demo.packets, defaultStatus),
  );
  const selectedIndex = setupEvaluationScrubber(demo);

  renderBackendTableTeam(demo.team);
  renderBackendTableIdentities(demo.identities);
  renderBackendStageCoverage(demo.stageCoverage);
  renderBackendProcedureMilestones(demo.milestones);
  renderBackendQualityFlags(demo.qualityFlags);
  renderEvaluationReplaySnapshot(demo, selectedIndex);
}

function renderEvaluationReplaySnapshot(demo, snapshotIndex = null) {
  const status = replaySnapshotAt(demo, snapshotIndex) || demo.status || {};
  const selectedIndex = selectedSnapshotIndex(demo, snapshotIndex);
  const packet = safePacketForStatus(demo.packets, status);
  const stageRoster = stageRosterForStatus(demo.stageRosters, status, packet);
  const stageLabel = status.current_stage_label || packet?.stage_label || demo.caseName;
  const tableSnapshot = currentTableSnapshot(status);
  const tableCount = tableSnapshot.count;
  const teamCount = demo.team.length || tableCount;

  clearCanvas();
  setEmptyState(
    "Evaluated TAVR demo loaded",
    `${demo.demoLabel}; ${replaySnapshotLabel(status, selectedIndex, demo.statusSnapshots.length)}`,
  );
  stageMetric.textContent = `${stageLabel} (${status.evidence_level || "evaluated"})`;
  countMetric.textContent = String(teamCount);
  tableSideMetric.textContent = String(tableCount);
  activityMetric.textContent = "replay";
  elapsedMetric.textContent = replayClockLabel(status);

  updateEvaluationScrubberLabel(demo, selectedIndex, status);
  renderReplayVideoWorkflow(status, demo, packet);
  renderOperatorAnswer(operatorAnswerRows(status, packet, stageRoster, demo.milestones));
  renderStageTableBrief(stageTableBriefRows(status, packet, demo.milestones, stageRoster));
  renderBackendTableRoster(status, demo.presenceIntervals);
  renderProcedureStatus(status, demo);
  renderBackendStatusSnapshots(demo.statusSnapshots, selectedIndex);
  renderBackendOperatorPacket(demo.packets, status);
  renderBackendStageRoster(demo.stageRosters, stageRoster);
  renderBackendProcedureEvents(demo.events, status);
}

function populateInitialStageOptions() {
  TAVR_STAGES.forEach((stage) => {
    const option = document.createElement("option");
    option.value = stage.key;
    option.textContent = stage.label;
    initialStageInput.append(option);
  });
}

function populateEvaluationDemoOptions() {
  EVALUATION_DEMOS.forEach((demo) => {
    const option = document.createElement("option");
    option.value = demo.id;
    option.textContent = demo.label;
    option.selected = Boolean(demo.default);
    evaluationDemoSelect.append(option);
  });
}

function selectedEvaluationDemo() {
  return (
    EVALUATION_DEMOS.find((demo) => demo.id === evaluationDemoSelect.value) ||
    EVALUATION_DEMOS.find((demo) => demo.default) ||
    EVALUATION_DEMOS[0]
  );
}

function safePacketForStatus(packets, status) {
  try {
    return packetForStatus(packets, status);
  } catch (error) {
    console.error("Replay packet lookup failed", error);
    return asArray(packets).at(-1) || null;
  }
}

function scheduleDemoAutostart() {
  const search = window.location?.search || "";
  if (!search) return;
  const params = new URLSearchParams(search);
  const demoMode = params.get("demo");
  if (!demoMode) return;
  const schedule = window.setTimeout || globalThis.setTimeout;
  schedule(() => {
    if (demoMode === "synthetic") {
      syntheticButton.click();
    }
  }, 0);
}

function setupEvaluationScrubber(demo) {
  const snapshotCount = demo.statusSnapshots.length;
  const selectedIndex = Math.max(0, snapshotCount - 1);
  evaluationSnapshotRange.disabled = snapshotCount <= 0;
  evaluationSnapshotRange.min = "0";
  evaluationSnapshotRange.max = String(Math.max(0, snapshotCount - 1));
  evaluationSnapshotRange.value = String(selectedIndex);
  updateEvaluationScrubberLabel(
    demo,
    selectedIndex,
    replaySnapshotAt(demo, selectedIndex) || demo.status || {},
  );
  return selectedIndex;
}

function updateEvaluationScrubberLabel(demo, selectedIndex, status) {
  evaluationSnapshotRange.value = String(selectedIndex);
  evaluationSnapshotLabel.textContent = replaySnapshotLabel(
    status,
    selectedIndex,
    demo.statusSnapshots.length,
  );
}

function selectedSnapshotIndex(demo, requestedIndex) {
  const snapshotCount = demo.statusSnapshots.length;
  if (!snapshotCount) return 0;
  const numeric = Number(requestedIndex);
  if (!Number.isFinite(numeric)) return snapshotCount - 1;
  return Math.min(Math.max(Math.round(numeric), 0), snapshotCount - 1);
}

function resetEvaluationScrubber() {
  currentEvaluationReplay = null;
  evaluationSnapshotRange.disabled = true;
  evaluationSnapshotRange.min = "0";
  evaluationSnapshotRange.max = "0";
  evaluationSnapshotRange.value = "0";
  evaluationSnapshotLabel.textContent = "No replay loaded";
}

async function startLiveCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setLiveStatus("Camera API unavailable in this browser", true);
    setEmptyState("Live camera unavailable", "Use HTTPS or a browser with getUserMedia support.");
    emptyState.hidden = false;
    return;
  }

  cancelAnimationFrame(rafId);
  stopLiveSource();
  revokeActiveObjectUrl();
  setLiveStatus("Requesting camera...");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: "environment",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    liveMediaStream = stream;
    liveMode = true;
    liveStartedAt = performance.now();
    frameReadBlocked = false;
    video.pause();
    video.removeAttribute("src");
    video.srcObject = stream;
    video.hidden = false;
    video.muted = true;
    video.playsInline = true;
    emptyState.hidden = true;
    resetMetrics({ keepLiveMode: true });
    setLiveStatus("Live camera running");
    await playVideoSource();
  } catch (error) {
    stopLiveSource();
    setLiveStatus(`Camera failed: ${error.message || error}`, true);
    setEmptyState("Live camera failed", String(error.message || error));
    emptyState.hidden = false;
  }
}

async function startLiveStreamUrl() {
  const streamUrl = liveStreamUrlInput.value.trim();
  if (!streamUrl) {
    setLiveStatus("Enter a browser-playable HTTPS stream URL", true);
    liveStreamUrlInput.focus();
    return;
  }

  cancelAnimationFrame(rafId);
  stopLiveSource();
  revokeActiveObjectUrl();
  liveMode = true;
  liveStartedAt = performance.now();
  frameReadBlocked = false;
  video.pause();
  video.srcObject = null;
  video.crossOrigin = "anonymous";
  video.src = streamUrl;
  video.hidden = false;
  video.muted = true;
  video.playsInline = true;
  video.load();
  emptyState.hidden = true;
  resetMetrics({ keepLiveMode: true });
  setLiveStatus("Opening live stream...");
  await playVideoSource().then(
    () => setLiveStatus("Live stream running"),
    (error) => {
      setLiveStatus(`Stream playback blocked: ${error.message || error}`, true);
      setEmptyState("Stream playback blocked", String(error.message || error));
      emptyState.hidden = false;
    },
  );
}

function stopLiveSource() {
  const wasLiveUrl = liveMode && !liveMediaStream && video.src && !activeObjectUrl;
  if (liveMediaStream) {
    liveMediaStream.getTracks().forEach((track) => track.stop());
  }
  liveMediaStream = null;
  liveMode = false;
  frameReadBlocked = false;
  stopLiveButton.disabled = true;
  video.srcObject = null;
  if (wasLiveUrl) {
    video.removeAttribute("src");
    video.load();
  }
  setLiveStatus("Live source idle");
}

function revokeActiveObjectUrl() {
  if (activeObjectUrl) URL.revokeObjectURL(activeObjectUrl);
  activeObjectUrl = null;
}

async function playVideoSource() {
  if (!hasVideoSource()) return;
  emptyState.hidden = true;
  try {
    await video.play();
    cancelAnimationFrame(rafId);
    tick();
  } catch (error) {
    setLiveStatus(`Playback blocked: ${error.message || error}`, true);
    throw error;
  }
}

function hasVideoSource() {
  return Boolean(video.src || video.srcObject);
}

function sourceElapsedSeconds() {
  if (liveMode) return Math.max(0, (performance.now() - liveStartedAt) / 1000);
  const currentTime = Number(video.currentTime);
  return Number.isFinite(currentTime) ? currentTime : 0;
}

function setLiveStatus(message, isWarning = false) {
  liveStatus.textContent = message;
  liveStatus.dataset.tone = isWarning ? "warn" : (liveMode ? "current" : "idle");
  stopLiveButton.disabled = !liveMode;
}

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
  if (frameReadBlocked) return;

  const targetWidth = 320;
  const ratio = video.videoHeight / Math.max(video.videoWidth, 1);
  work.width = targetWidth;
  work.height = Math.max(1, Math.round(targetWidth * ratio));
  let image;
  try {
    workCtx.drawImage(video, 0, 0, work.width, work.height);
    image = workCtx.getImageData(0, 0, work.width, work.height);
  } catch (error) {
    frameReadBlocked = true;
    setLiveStatus("Stream pixels blocked by browser CORS; use a CORS-enabled stream", true);
    setEmptyState("Stream visible but not analyzable", "Enable CORS on the stream or use Live camera.");
    return;
  }

  if (!previousFrame) {
    previousFrame = image;
    return;
  }

  const cellSize = Number(cellSizeInput.value);
  const sensitivity = Number(sensitivityInput.value);
  const viewColorfulness = frameColorfulness(image);
  const nonRoomView = viewColorfulness < BROWSER_NON_ROOM_COLORFULNESS_THRESHOLD;
  const cells = collectMotionCells(image, previousFrame, cellSize, sensitivity);
  let boxes = clusterCells(cells, cellSize, work.width, work.height);
  let staticTableUsed = false;
  if (nonRoomView) {
    boxes = [];
  } else if (staticFallbackInput.checked && !hasTableSideBox(boxes)) {
    const staticBoxes = collectStaticTableBoxes(image);
    if (staticBoxes.length) {
      boxes = dedupeBoxes([...boxes, ...staticBoxes]).slice(0, 12);
      staticTableUsed = boxes.some((box) => box.staticFallback);
    }
  }
  const activity = cells.length;
  previousFrame = image;
  activityHistory.push(activity);
  if (activityHistory.length > 80) activityHistory.shift();
  const elapsedSeconds = sourceElapsedSeconds();
  const stage = estimateUploadedTavrStage(boxes, activity, elapsedSeconds, {
    stageHoldReason: nonRoomView
      ? "non_room_view"
      : (staticTableUsed ? "static_table_fallback" : null),
    viewColorfulness,
  });

  drawOverlay(boxes, activity, stage);
  updateMetrics(boxes, activity, elapsedSeconds, stage);
}

function analyzeSyntheticFrame() {
  const elapsed = (performance.now() - syntheticStartedAt) / 1000;
  const stage = getTavrStage(elapsed);
  const boxes = buildSyntheticTavrBoxes(elapsed, stage);
  const activity = Math.round(stage.activity + 14 * oscillate(elapsed, stage.pace));
  activityHistory.push(activity);
  if (activityHistory.length > 80) activityHistory.shift();
  drawOverlay(boxes, activity, stage);
  updateMetrics(boxes, activity, elapsed, stage);
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

function estimateUploadedTavrStage(boxes, activity, elapsedSeconds, options = {}) {
  if (elapsedSeconds < uploadedStageStartedAt) {
    uploadedStageIndex = selectedInitialStageIndex();
    uploadedStageStartedAt = elapsedSeconds;
  }
  const summary = summarizeBoxes(boxes);
  const signals = tavrStageSignals(summary, boxes.length, activity);
  const scores = scoreTavrStages(signals, elapsedSeconds);
  const stageHoldReason = options.stageHoldReason || null;
  const stageObservable = !stageHoldReason;
  const previousIndex = uploadedStageIndex;
  if (stageObservable) {
    uploadedStageIndex = chooseTavrStageIndex(scores, elapsedSeconds);
    if (uploadedStageIndex !== previousIndex) {
      uploadedStageStartedAt = elapsedSeconds;
    }
  }

  const stage = TAVR_STAGES[uploadedStageIndex];
  const confidence = stageObservable
    ? Math.min(0.95, Math.max(...Object.values(scores)))
    : 0.2;
  const progress = Math.min(
    1,
    Math.max(0, (elapsedSeconds - uploadedStageStartedAt) / Math.max(stage.duration, 1)),
  );
  return {
    ...stage,
    confidence,
    progress,
    stageObservable,
    stageHoldReason,
    viewColorfulness: options.viewColorfulness,
  };
}

function selectedInitialStageIndex() {
  const index = TAVR_STAGES.findIndex((stage) => stage.key === initialStageInput.value);
  return index >= 0 ? index : 0;
}

function tavrStageSignals(summary, peopleCount, activity) {
  const tableCount = summary.zones.table +
    summary.zones.table_left +
    summary.zones.table_right +
    summary.zones.access;
  return {
    table: Math.min(tableCount / 3, 1),
    access: Math.min(summary.zones.access / 2, 1),
    imaging: Math.min(summary.zones.imaging / 2, 1),
    device: Math.min(summary.zones.device_table / 2, 1),
    anesthesia: Math.min(summary.zones.anesthesia / 2, 1),
    stillness: Math.max(0, 1 - Math.min(activity / 60, 1)),
    crowd: Math.min(peopleCount / 5, 1),
  };
}

function scoreTavrStages(signals, elapsedSeconds) {
  const earlyBonus = elapsedSeconds < 1.2 ? 0.14 : 0;
  const lateBonus = elapsedSeconds > 8 ? 0.08 : 0;
  return {
    room_prep_drape: 0.32 + 0.28 * signals.device + 0.18 * signals.anesthesia + earlyBonus,
    access_sheathing: 0.24 + 0.42 * signals.access + 0.18 * signals.table,
    angio_alignment_crossing: 0.22 + 0.38 * signals.imaging + 0.16 * signals.table,
    bav_optional: 0.18 + 0.30 * signals.imaging + 0.24 * signals.stillness + 0.16 * signals.table,
    valve_delivery_positioning: (
      0.20 + 0.32 * signals.device + 0.26 * signals.table + 0.16 * signals.imaging
    ),
    valve_deployment: 0.16 + 0.32 * signals.stillness + 0.26 * signals.table + 0.20 * signals.imaging,
    post_deploy_assessment: 0.20 + 0.34 * signals.imaging + 0.18 * signals.anesthesia + 0.08 * signals.table,
    closure_finish: 0.18 + 0.38 * signals.access + 0.16 * signals.stillness + lateBonus,
  };
}

function chooseTavrStageIndex(scores, elapsedSeconds) {
  const currentStage = TAVR_STAGES[uploadedStageIndex];
  const currentScore = scores[currentStage.key] || 0;
  if (elapsedSeconds - uploadedStageStartedAt < BROWSER_STAGE_MIN_SECONDS) {
    return uploadedStageIndex;
  }

  const nextIndex = Math.min(uploadedStageIndex + 1, TAVR_STAGES.length - 1);
  const nextStage = TAVR_STAGES[nextIndex];
  const nextScore = scores[nextStage.key] || 0;
  if (nextStage.key === "bav_optional") {
    const deliveryIndex = TAVR_STAGE_LOOKUP.get("valve_delivery_positioning").index;
    const deliveryScore = scores.valve_delivery_positioning || 0;
    if (
      deliveryScore >= BROWSER_STAGE_MIN_CONFIDENCE &&
      deliveryScore > currentScore + BROWSER_STAGE_ADVANCE_MARGIN &&
      deliveryScore > nextScore + 0.05
    ) {
      return deliveryIndex;
    }
  }
  if (
    nextIndex > uploadedStageIndex &&
    nextScore >= BROWSER_STAGE_MIN_CONFIDENCE &&
    nextScore > currentScore + BROWSER_STAGE_ADVANCE_MARGIN
  ) {
    return nextIndex;
  }
  return uploadedStageIndex;
}

function buildSyntheticTavrBoxes(elapsed, stage) {
  const boxes = [
    {
      id: "T1",
      role: "table_operator",
      label: "Proceduralist",
      x: 0.37 + 0.05 * oscillate(elapsed, 0.28),
      y: 0.5 + 0.03 * oscillate(elapsed + 0.4, 0.36),
      w: 0.08,
      h: 0.22,
    },
    {
      id: "T2",
      role: "table_operator",
      label: "Proceduralist 2",
      x: 0.60 - 0.04 * oscillate(elapsed + 0.8, 0.26),
      y: 0.43 + 0.04 * oscillate(elapsed + 1.3, 0.34),
      w: 0.08,
      h: 0.21,
    },
    {
      id: "A1",
      role: "access_operator",
      label: "Proceduralist access",
      x: 0.31 + 0.04 * oscillate(elapsed + 2.4, 0.22),
      y: 0.70 + 0.02 * oscillate(elapsed + 0.2, 0.42),
      w: 0.09,
      h: 0.18,
    },
    {
      id: "AN1",
      role: "anesthesia",
      label: "Anaesthetist",
      x: 0.80 + 0.03 * oscillate(elapsed + 0.9, 0.18),
      y: 0.18 + 0.04 * oscillate(elapsed + 1.8, 0.3),
      w: 0.08,
      h: 0.2,
    },
    {
      id: "S1",
      role: "entry_supply",
      label: "Circulator",
      x: 0.05 + 0.08 * oscillate(elapsed + 1.6, 0.3),
      y: 0.42 + 0.12 * oscillate(elapsed + 0.5, 0.2),
      w: 0.08,
      h: 0.21,
    },
    {
      id: "D1",
      role: "device_prep",
      label: "Device prep",
      x: 0.13 + 0.04 * oscillate(elapsed + 0.3, 0.24),
      y: 0.18 + 0.02 * oscillate(elapsed + 1.1, 0.36),
      w: 0.08,
      h: 0.2,
    },
    {
      id: "I1",
      role: "imaging",
      label: "Imaging operator",
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

function frameColorfulness(image) {
  if (!image?.data?.length) return 0;
  let redGreenTotal = 0;
  let yellowBlueTotal = 0;
  const stride = 4;
  const sampleStep = Math.max(1, Math.floor((image.width * image.height) / 24000));
  let samples = 0;
  for (let pixel = 0; pixel < image.width * image.height; pixel += sampleStep) {
    const index = pixel * stride;
    const red = image.data[index];
    const green = image.data[index + 1];
    const blue = image.data[index + 2];
    redGreenTotal += Math.abs(red - green);
    yellowBlueTotal += Math.abs(0.5 * (red + green) - blue);
    samples += 1;
  }
  if (!samples) return 0;
  const redGreen = redGreenTotal / samples;
  const yellowBlue = yellowBlueTotal / samples;
  return Math.hypot(redGreen, yellowBlue);
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

function collectStaticTableBoxes(image) {
  return ZONES
    .filter((zone) => TABLE_SIDE_ZONES.has(zone.key))
    .map((zone) => staticBoxForZone(image, zone))
    .filter(Boolean)
    .map((box, index) => ({
      ...box,
      id: `ST${index + 1}`,
      role: inferRoleFromZones(getZoneKeys(box)) || "table_operator",
      label: "Static table",
      tableSide: true,
      staticFallback: true,
    }));
}

function staticBoxForZone(image, zone) {
  const x0 = Math.max(0, Math.floor(zone.x0 * image.width));
  const y0 = Math.max(0, Math.floor(zone.y0 * image.height));
  const x1 = Math.min(image.width, Math.ceil(zone.x1 * image.width));
  const y1 = Math.min(image.height, Math.ceil(zone.y1 * image.height));
  let minX = x1;
  let minY = y1;
  let maxX = x0;
  let maxY = y0;
  let hits = 0;
  let samples = 0;

  for (let y = y0; y < y1; y += 4) {
    for (let x = x0; x < x1; x += 4) {
      const index = (y * image.width + x) * 4;
      const red = image.data[index];
      const green = image.data[index + 1];
      const blue = image.data[index + 2];
      const maxChannel = Math.max(red, green, blue);
      const minChannel = Math.min(red, green, blue);
      const saturation = maxChannel - minChannel;
      samples += 1;
      if (saturation < 42 || maxChannel > 238 || maxChannel < 32) continue;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
      hits += 1;
    }
  }

  if (hits < 18 || samples <= 0 || hits / samples > 0.38) return null;
  const pixelWidth = Math.max(1, maxX - minX + 4);
  const pixelHeight = Math.max(1, maxY - minY + 4);
  const zoneArea = Math.max(1, (x1 - x0) * (y1 - y0));
  const boxArea = pixelWidth * pixelHeight;
  const aspectRatio = pixelWidth / Math.max(pixelHeight, 1);
  if (boxArea < 240 || boxArea > zoneArea * 0.38) return null;
  if (aspectRatio < 0.18 || aspectRatio > 2.25) return null;

  return {
    x: minX / image.width,
    y: minY / image.height,
    w: pixelWidth / image.width,
    h: pixelHeight / image.height,
  };
}

function hasTableSideBox(boxes) {
  return boxes.some((box) => (
    getZoneKeys(box).some((zoneKey) => TABLE_SIDE_ZONES.has(zoneKey))
  ));
}

function dedupeBoxes(boxes) {
  const deduped = [];
  boxes
    .slice()
    .sort((a, b) => (b.w * b.h) - (a.w * a.h))
    .forEach((box) => {
      const overlapsExisting = deduped.some((kept) => (
        normalizedDistance(box, kept) < 0.09 || boxIou(box, kept) > 0.18
      ));
      if (overlapsExisting) {
        return;
      }
      deduped.push(box);
    });
  return deduped;
}

function normalizedDistance(a, b) {
  const ax = a.x + a.w / 2;
  const ay = a.y + a.h / 2;
  const bx = b.x + b.w / 2;
  const by = b.y + b.h / 2;
  return Math.hypot(ax - bx, ay - by);
}

function boxIou(a, b) {
  const left = Math.max(a.x, b.x);
  const top = Math.max(a.y, b.y);
  const right = Math.min(a.x + a.w, b.x + b.w);
  const bottom = Math.min(a.y + a.h, b.y + b.h);
  if (right <= left || bottom <= top) return 0;
  const intersection = (right - left) * (bottom - top);
  const union = a.w * a.h + b.w * b.h - intersection;
  return union > 0 ? intersection / union : 0;
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
    const label = box.label || WORKFLOW_ROLE_LABELS[roleKey] || ROLE_LABELS[roleKey] || `M${index + 1}`;
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

  drawPatientOverlay(stage, rect.width, rect.height);
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

function drawPatientOverlay(stage, width, height) {
  const state = workflowState.patientState || deriveSyntheticPatientState(stage);
  if (!stage || state === "waiting_outside" || state === "out_of_room") return;

  const position = patientOverlayPosition(stage, state);
  const x = position.x * width;
  const y = position.y * height;
  const w = position.w * width;
  const h = position.h * height;
  const label = state === "in_room_unverified" ? "Patient held" : "Patient";

  ctx.save();
  ctx.setLineDash([7, 5]);
  ctx.strokeStyle = "#ffcc66";
  ctx.fillStyle = "rgba(255, 204, 102, 0.12)";
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, w, h);
  ctx.fillRect(x, y, w, h);
  ctx.setLineDash([]);
  ctx.fillStyle = "rgba(8, 11, 14, 0.82)";
  ctx.fillRect(x, Math.max(8, y - 22), 96, 19);
  ctx.fillStyle = "#ffcc66";
  ctx.font = "700 12px Inter, system-ui, sans-serif";
  ctx.fillText(label, x + 8, Math.max(21, y - 8));
  ctx.restore();
}

function patientOverlayPosition(stage, state) {
  if (state === "entering_room") {
    return { x: 0.08, y: 0.52, w: 0.12, h: 0.28 };
  }
  if (state === "leaving_room") {
    return { x: 0.10, y: 0.64, w: 0.12, h: 0.24 };
  }
  if (stage?.key === "closure_finish") {
    return { x: 0.36, y: 0.52, w: 0.28, h: 0.15 };
  }
  return { x: 0.39, y: 0.42, w: 0.25, h: 0.14 };
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

function updateMetrics(boxes, activity, elapsedSeconds, stageInput = "Uploaded review") {
  const stage = normalizeStage(stageInput);
  const summary = canonicalizeBrowserSummary(summarizeBoxes(boxes), elapsedSeconds);
  const tableSnapshot = updateBrowserTableSnapshot(summary, elapsedSeconds, stage);
  const currentTable = currentBrowserTableSnapshot(summary, elapsedSeconds);
  const currentWorkflow = updateVideoWorkflowState({
    stage,
    summary,
    currentTable,
    tableSnapshot,
    elapsedSeconds,
  });
  stageMetric.textContent = stage.confidence === undefined
    ? stage.label
    : `${stage.label} (${stage.confidence.toFixed(2)})`;
  countMetric.textContent = String(boxes.length);
  tableSideMetric.textContent = String(currentTable.count);
  activityMetric.textContent = String(activity);
  elapsedMetric.textContent = `${elapsedSeconds.toFixed(1)}s`;
  updateStageRoster(stage, summary.tableRoster, elapsedSeconds);
  updateProcedureMilestones(stage, summary.tableRoster, summary.tableSide, elapsedSeconds);
  const evidenceLabel = stage.stageHoldReason
    ? stage.stageHoldReason.replaceAll("_", " ")
    : `confidence ${formatNumber(stage.confidence)}`;
  const progress = browserProcedureProgressBrief(stage.key);
  const handoff = browserStageHandoffBrief(currentStageRosterSegment);
  renderOperatorAnswer(operatorAnswerRowsFromSnapshots({
    stageLabel: stage.label,
    evidenceLabel,
    progress,
    currentTable,
    effectiveTable: tableSnapshot,
    handoff,
    currentView: stage.stageHoldReason ? "non-room/held" : "room",
    trackingAvailable: !stage.stageHoldReason,
    qualityFlags: operatorQualityFlags(stage, summary, tableSnapshot),
  }));
  renderVideoWorkflow(currentWorkflow);
  renderWorkflowEvents();
  renderStageTableBrief(stageTableBriefRowsFromSnapshots({
    stageLabel: stage.label,
    evidenceLabel,
    timeLabel: `${formatSeconds(elapsedSeconds)}`,
    progress,
    currentTable,
    effectiveTable: tableSnapshot,
    handoff,
  }));
  renderTableRoster(currentTable, tableSnapshot);
  updateTableTeam(summary.tableRoster, elapsedSeconds, stage);
  renderBrowserTableIdentities();
  updateStageCoverage(stage, summary.tableRoster, elapsedSeconds);
  renderOperatorPacket(stage, summary, elapsedSeconds, tableSnapshot);
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

function normalizeStage(stageInput) {
  if (typeof stageInput === "string") {
    return { key: stageInput.toLowerCase().replaceAll(/\s+/g, "_"), label: stageInput };
  }
  return {
    ...stageInput,
    key: stageInput.key || stageInput.label.toLowerCase().replaceAll(/\s+/g, "_"),
    label: stageInput.label,
  };
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
        rawId: box.id || `M${index + 1}`,
        role: roleKey || "motion",
        x: box.x,
        y: box.y,
        w: box.w,
        h: box.h,
        staticFallback: Boolean(box.staticFallback),
      });
    }
  });

  return summary;
}

function canonicalizeBrowserSummary(summary, elapsedSeconds) {
  const tableRoster = browserIdentityTracker.update(summary.tableRoster, elapsedSeconds);
  return {
    ...summary,
    tableSide: tableRoster.length,
    tableRoster,
  };
}

function currentBrowserTableSnapshot(summary, elapsedSeconds) {
  const rows = copyBrowserRoster(summary.tableRoster || []);
  return {
    rows,
    count: rows.length,
    source: rows.length ? "current_room_view" : "current_room_view_empty",
    observedAt: elapsedSeconds,
    ageSeconds: 0,
  };
}

function updateBrowserTableSnapshot(summary, elapsedSeconds, stage) {
  if (summary.tableRoster.length) {
    const rows = copyBrowserRoster(summary.tableRoster);
    const snapshot = {
      rows,
      count: rows.length,
      source: "current_room_view",
      observedAt: elapsedSeconds,
      ageSeconds: 0,
    };
    lastObservedTableSnapshot = snapshot;
    return snapshot;
  }

  const heldRows = copyBrowserRoster(lastObservedTableSnapshot?.rows || []);
  const heldAge = lastObservedTableSnapshot
    ? Math.max(0, elapsedSeconds - lastObservedTableSnapshot.observedAt)
    : null;

  if (stage.stageHoldReason === "non_room_view") {
    return heldRows.length
      ? {
        rows: heldRows,
        count: heldRows.length,
        source: "last_observed_room_view",
        observedAt: lastObservedTableSnapshot.observedAt,
        ageSeconds: heldAge,
      }
      : {
        rows: [],
        count: 0,
        source: "no_room_table_evidence",
        observedAt: null,
        ageSeconds: null,
      };
  }

  if (heldRows.length && heldAge !== null && heldAge <= BROWSER_RECENT_TABLE_HOLD_SECONDS) {
    return {
      rows: heldRows,
      count: heldRows.length,
      source: "recent_room_view_hold",
      observedAt: lastObservedTableSnapshot.observedAt,
      ageSeconds: heldAge,
    };
  }

  return {
    rows: [],
    count: 0,
    source: "current_room_view_empty",
    observedAt: elapsedSeconds,
    ageSeconds: 0,
  };
}

function initialWorkflowState() {
  return {
    patientState: "waiting_outside",
    patientSeenInRoom: false,
    stageKey: null,
    roomView: "idle",
    seenRoleEvents: new Set(),
    tableRosterKey: "",
    sourceLabel: "idle",
  };
}

function updateVideoWorkflowState({
  stage,
  summary,
  currentTable,
  tableSnapshot,
  elapsedSeconds,
}) {
  const roomView = stage.stageHoldReason === "non_room_view" ? "non-room" : "room";
  const trackingAvailable = !stage.stageHoldReason;
  const sourceLabel = currentVideoSourceLabel();
  const patientState = derivePatientState(stage, summary, currentTable, tableSnapshot);
  const events = [];

  if (workflowState.stageKey && stage.key !== workflowState.stageKey) {
    events.push({
      time: elapsedSeconds,
      code: "procedure_stage_changed",
      label: "Procedure stage changed",
      detail: stage.label,
      tone: "current",
    });
  }
  if (workflowState.roomView !== "idle" && roomView !== workflowState.roomView) {
    events.push({
      time: elapsedSeconds,
      code: "room_view_changed",
      label: "Room view changed",
      detail: roomView === "room" ? "Room camera visible" : "Room view unavailable / fluoroscopy",
      tone: roomView === "room" ? "current" : "warn",
    });
  }
  if (patientState !== workflowState.patientState) {
    events.push(patientWorkflowEvent(patientState, elapsedSeconds));
  } else if (!workflowEvents.length && patientState === "waiting_outside") {
    events.push(patientWorkflowEvent(patientState, elapsedSeconds));
  }

  [
    ["anaesthetist_detected", "anesthesia", "Anaesthetist visible"],
    ["proceduralist_detected", "table_operator", "Proceduralist visible"],
    ["access_proceduralist_detected", "access_operator", "Access proceduralist visible"],
    ["imaging_operator_detected", "imaging", "Imaging operator visible"],
    ["circulator_detected", "entry_supply", "Circulator / entry activity visible"],
  ].forEach(([code, role, label]) => {
    if ((summary.roles[role] || 0) <= 0 || workflowState.seenRoleEvents.has(code)) return;
    workflowState.seenRoleEvents.add(code);
    events.push({
      time: elapsedSeconds,
      code,
      label,
      detail: `${WORKFLOW_ROLE_LABELS[role] || role} detected`,
      tone: "current",
    });
  });

  const tableRosterKey = (currentTable.rows || [])
    .map((row) => row.id)
    .sort()
    .join(",");
  if (tableRosterKey !== workflowState.tableRosterKey) {
    events.push({
      time: elapsedSeconds,
      code: "table_roster_changed",
      label: "Table roster changed",
      detail: tableRosterKey ? `active IDs ${tableRosterKey}` : "table-side roster cleared",
      tone: tableRosterKey ? "current" : "quiet",
    });
  }

  workflowState = {
    ...workflowState,
    patientState,
    patientSeenInRoom: workflowState.patientSeenInRoom || [
      "entering_room",
      "in_room",
      "on_table",
      "in_room_unverified",
      "leaving_room",
    ].includes(patientState),
    stageKey: stage.key,
    roomView,
    tableRosterKey,
    sourceLabel,
  };

  if (events.length) {
    workflowEvents.push(...events);
    workflowEvents = workflowEvents.slice(-40);
  }

  return {
    patientState,
    patientLabel: PATIENT_STATE_LABELS[patientState] || patientState,
    patientConfidence: patientWorkflowConfidence(patientState, {
      trackingAvailable,
      currentTableCount: currentTable.count,
      effectiveTableCount: tableSnapshot.count,
      peopleCount: summary.tableRoster.length,
    }),
    roomView,
    trackingAvailable,
    sourceLabel,
    anaesthetistCount: summary.roles.anesthesia || 0,
    proceduralistCount: (summary.roles.table_operator || 0) + (summary.roles.access_operator || 0),
    tableCount: currentTable.count,
    effectiveTableCount: tableSnapshot.count,
    latestEvent: events.at(-1) || workflowEvents.at(-1) || null,
  };
}

function derivePatientState(stage, summary, currentTable, tableSnapshot) {
  if (stage.stageHoldReason === "non_room_view") {
    return workflowState.patientSeenInRoom || tableSnapshot.count > 0
      ? "in_room_unverified"
      : workflowState.patientState;
  }
  if (
    stage.key === "closure_finish" &&
    workflowState.patientSeenInRoom &&
    currentTable.count === 0 &&
    (summary.roles.entry_supply || 0) > 0
  ) {
    return "leaving_room";
  }
  if (
    stage.key === "closure_finish" &&
    workflowState.patientSeenInRoom &&
    currentTable.count === 0 &&
    tableSnapshot.count === 0
  ) {
    return "out_of_room";
  }
  if (currentTable.count > 0) return "on_table";
  const stageIndex = TAVR_STAGE_LOOKUP.get(stage.key)?.index ?? 0;
  if (
    workflowState.patientSeenInRoom ||
    stageIndex > 0 ||
    (summary.roles.anesthesia || 0) > 0 ||
    (summary.roles.access_operator || 0) > 0 ||
    (summary.roles.table_operator || 0) > 0
  ) {
    return "in_room";
  }
  if ((summary.roles.entry_supply || 0) > 0 || deriveSyntheticPatientState(stage) === "entering_room") {
    return "entering_room";
  }
  return "waiting_outside";
}

function deriveSyntheticPatientState(stage) {
  if (!stage || !syntheticMode) return "waiting_outside";
  if (stage.key === "room_prep_drape" && (stage.progress || 0) < 0.18) return "waiting_outside";
  if (stage.key === "room_prep_drape" && (stage.progress || 0) < 0.45) return "entering_room";
  if (stage.key === "closure_finish" && (stage.progress || 0) > 0.78) return "leaving_room";
  return "in_room";
}

function patientWorkflowConfidence(patientState, facts) {
  if (patientState === "in_room_unverified") return facts.effectiveTableCount ? 0.42 : 0.25;
  if (facts.currentTableCount > 0) return 0.86;
  if (!facts.trackingAvailable) return 0.25;
  if (facts.peopleCount > 0) return 0.68;
  return ["waiting_outside", "out_of_room"].includes(patientState) ? 0.55 : 0.5;
}

function patientWorkflowEvent(patientState, elapsedSeconds) {
  const detail = {
    waiting_outside: "No patient-room evidence yet",
    entering_room: "Entry-zone activity before table evidence",
    in_room: "Room workflow evidence indicates patient present",
    on_table: "Table-side procedural evidence indicates patient on table",
    in_room_unverified: "Holding room-state while room view is unavailable",
    leaving_room: "Closure with entry activity and no active table roster",
    out_of_room: "Closure complete with no active table roster",
  }[patientState] || "Patient room state changed";
  const code = {
    waiting_outside: "patient_out_of_room",
    entering_room: "patient_entering_room",
    in_room: "patient_in_room",
    on_table: "patient_on_table",
    in_room_unverified: "patient_room_status_held",
    leaving_room: "patient_leaving_room",
    out_of_room: "patient_out_of_room",
  }[patientState] || "patient_state_changed";
  return {
    time: elapsedSeconds,
    code,
    label: PATIENT_STATE_LABELS[patientState] || patientState,
    detail,
    tone: patientState === "in_room_unverified" ? "warn" : "current",
  };
}

function currentVideoSourceLabel() {
  if (syntheticMode) return "synthetic video";
  if (liveMode && liveMediaStream) return "live camera feed";
  if (liveMode) return "live stream URL";
  if (hasVideoSource()) return "uploaded video";
  return "idle";
}

function copyBrowserRoster(roster) {
  return roster.map(({ id, rawId, rawIds, role, staticFallback }) => ({
    id,
    rawId,
    rawIds: rawIds || (rawId ? [rawId] : [id]),
    role,
    staticFallback: Boolean(staticFallback),
  }));
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

function updateStageCoverage(stage, roster, elapsedSeconds) {
  roster.forEach(({ id, role }) => {
    const key = `${stage.key}:${id}`;
    const item = stageCoverage.get(key) || {
      stageKey: stage.key,
      stageLabel: stage.label,
      id,
      role,
      frames: 0,
      firstSeen: elapsedSeconds,
      lastSeen: elapsedSeconds,
    };
    item.role = role;
    item.frames += 1;
    item.firstSeen = Math.min(item.firstSeen, elapsedSeconds);
    item.lastSeen = Math.max(item.lastSeen, elapsedSeconds);
    stageCoverage.set(key, item);
  });
  renderStageCoverage();
}

function updateTableTeam(roster, elapsedSeconds, stage) {
  const currentIds = new Set(roster.map(({ id }) => id));
  roster.forEach(({ id, role, rawId, rawIds }) => {
    const item = tableTeam.get(id) || {
      id,
      role,
      rawIds: new Set(),
      frames: 0,
      firstSeen: elapsedSeconds,
      lastSeen: elapsedSeconds,
      stages: new Map(),
      status: "active_current",
    };
    item.role = role;
    (rawIds || [rawId || id]).forEach((value) => item.rawIds.add(value));
    item.frames += 1;
    item.firstSeen = Math.min(item.firstSeen, elapsedSeconds);
    item.lastSeen = Math.max(item.lastSeen, elapsedSeconds);
    item.stages.set(stage.label, (item.stages.get(stage.label) || 0) + 1);
    item.status = "active_current";
    tableTeam.set(id, item);
  });

  tableTeam.forEach((item) => {
    if (currentIds.has(item.id)) {
      item.status = "active_current";
    } else if (elapsedSeconds - item.lastSeen <= 5) {
      item.status = "recent_last_observed";
    } else {
      item.status = "historical_seen";
    }
  });
  renderTableTeam();
}

function renderTableTeam() {
  tableTeamList.replaceChildren();
  const statusOrder = {
    active_current: 0,
    recent_last_observed: 1,
    historical_seen: 2,
  };
  const items = [...tableTeam.values()]
    .sort((a, b) => (
      statusOrder[a.status] - statusOrder[b.status] ||
      b.lastSeen - a.lastSeen ||
      b.frames - a.frames ||
      a.id.localeCompare(b.id)
    ))
    .slice(0, 8);

  if (!items.length) {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = "None yet";
    row.append(label);
    tableTeamList.append(row);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    const roleLabel = ROLE_LABELS[item.role] || item.role;
    const stageLabel = dominantStageLabel(item.stages);
    const rawLabel = item.rawIds?.size
      ? `; raw ${compactIdList([...item.rawIds].sort(), 4)}`
      : "";
    row.dataset.status = item.status.replaceAll("_", "-");
    label.textContent = `${item.id} ${roleLabel}: ${statusLabel(item.status)}`;
    value.textContent = `${item.frames}f${rawLabel}; last ${item.lastSeen.toFixed(1)}s; ${stageLabel}`;
    row.append(label, value);
    tableTeamList.append(row);
  });
}

function renderBrowserTableIdentities() {
  tableIdentityList.replaceChildren();
  const groups = browserIdentityTracker.groups().slice(0, 8);
  if (!groups.length) {
    appendInfoRow(tableIdentityList, "None yet", "");
    return;
  }

  groups.forEach((group) => {
    appendInfoRow(
      tableIdentityList,
      `${group.id} ${ROLE_LABELS[group.role] || group.role}`,
      `${group.frames}f; raw ${compactIdList(group.rawIds, 4)}; last ${group.lastSeen.toFixed(1)}s`,
    );
  });
  appendOverflowRow(tableIdentityList, browserIdentityTracker.groups().length, groups.length, "identities");
}

function renderStageCoverage() {
  stageCoverageList.replaceChildren();
  const items = [...stageCoverage.values()]
    .sort((a, b) => b.frames - a.frames || a.firstSeen - b.firstSeen)
    .slice(0, 8);

  if (!items.length) {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = "None yet";
    row.append(label);
    stageCoverageList.append(row);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    label.textContent = `${item.stageLabel}: ${item.id} ${ROLE_LABELS[item.role] || item.role}`;
    value.textContent = `${item.frames}f ${item.firstSeen.toFixed(1)}-${item.lastSeen.toFixed(1)}s`;
    row.append(label, value);
    stageCoverageList.append(row);
  });
}

function updateStageRoster(stage, roster, elapsedSeconds) {
  if (!currentStageRosterSegment || currentStageRosterSegment.stageKey !== stage.key) {
    currentStageRosterSegment = createStageRosterSegment(
      stage,
      roster,
      elapsedSeconds,
      currentStageRosterSegment,
    );
    stageRosterSegments.push(currentStageRosterSegment);
  }

  updateStageRosterSegment(currentStageRosterSegment, roster, elapsedSeconds);
  renderStageRosterSummary();
}

function createStageRosterSegment(stage, roster, elapsedSeconds, previousSegment) {
  const activeIds = roster.map(({ id }) => id);
  const activeIdSet = new Set(activeIds);
  const previousActiveIds = previousSegment ? previousSegment.activeIds : [];
  const previousActiveIdSet = new Set(previousActiveIds);
  const continuedIds = activeIds.filter((id) => previousActiveIdSet.has(id));
  const newIds = activeIds.filter((id) => !previousActiveIdSet.has(id));
  const droppedIds = previousActiveIds.filter((id) => !activeIdSet.has(id));

  return {
    stageKey: stage.key,
    stageLabel: stage.label,
    startSeen: elapsedSeconds,
    lastSeen: elapsedSeconds,
    frames: 0,
    peakTableCount: 0,
    activeIds: [],
    continuedIds,
    newIds,
    droppedIds,
    handoffType: classifyStageRosterHandoff(
      previousSegment,
      activeIds,
      continuedIds,
      newIds,
      droppedIds,
    ),
    rosterStats: new Map(),
  };
}

function updateStageRosterSegment(segment, roster, elapsedSeconds) {
  segment.frames += 1;
  segment.lastSeen = elapsedSeconds;
  segment.peakTableCount = Math.max(segment.peakTableCount, roster.length);
  segment.activeIds = roster.map(({ id }) => id);

  roster.forEach(({ id, role }) => {
    const item = segment.rosterStats.get(id) || {
      id,
      role,
      frames: 0,
      firstSeen: elapsedSeconds,
      lastSeen: elapsedSeconds,
    };
    item.role = role;
    item.frames += 1;
    item.firstSeen = Math.min(item.firstSeen, elapsedSeconds);
    item.lastSeen = Math.max(item.lastSeen, elapsedSeconds);
    segment.rosterStats.set(id, item);
  });
}

function classifyStageRosterHandoff(previousSegment, activeIds, continuedIds, newIds, droppedIds) {
  if (!previousSegment) {
    return activeIds.length ? "initial_table_roster" : "initial_no_table_evidence";
  }
  if (!activeIds.length && !droppedIds.length) return "no_table_evidence";
  if (!activeIds.length) return "table_cleared";
  if (!previousSegment.activeIds.length) return "table_roster_started";
  if (newIds.length && droppedIds.length) return "roster_changed";
  if (newIds.length) return "roster_added";
  if (droppedIds.length) return "roster_removed";
  return continuedIds.length ? "roster_continued" : "table_roster_started";
}

function renderStageRosterSummary() {
  stageRosterList.replaceChildren();
  const items = stageRosterSegments.slice(-8).reverse();

  if (!items.length) {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = "None yet";
    row.append(label);
    stageRosterList.append(row);
    return;
  }

  items.forEach((segment) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    const activeIds = compactIdList(segment.activeIds);
    const newIds = compactIdList(segment.newIds);
    const droppedIds = compactIdList(segment.droppedIds);

    row.dataset.handoff = segment.handoffType.replaceAll("_", "-");
    label.textContent = `${segment.stageLabel}: ${handoffLabel(segment.handoffType)}`;
    value.textContent = (
      `${segment.startSeen.toFixed(1)}-${segment.lastSeen.toFixed(1)}s; ` +
      `peak ${segment.peakTableCount}; active ${activeIds}; +${newIds}; -${droppedIds}`
    );
    row.append(label, value);
    stageRosterList.append(row);
  });
}

function browserStageHandoffBrief(segment = null) {
  if (!segment) return null;
  return {
    handoffType: segment.handoffType,
    activeIds: segment.activeIds,
    continuedIds: segment.continuedIds,
    newIds: segment.newIds,
    droppedIds: segment.droppedIds,
  };
}

function browserProcedureProgressBrief(stageKey) {
  const stageMeta = TAVR_STAGE_LOOKUP.get(stageKey);
  if (!stageMeta) return null;
  const nextStage = TAVR_STAGES[stageMeta.index + 1];
  const observedCount = TAVR_STAGES.reduce(
    (count, stage) => count + Number(milestoneProgress.has(stage.key)),
    0,
  );
  return {
    stageIndex: stageMeta.index,
    totalStages: TAVR_STAGES.length,
    nextLabel: nextStage?.label || "complete",
    observedCount,
    observedTotal: TAVR_STAGES.length,
  };
}

function renderOperatorPacket(stage = null, summary = null, elapsedSeconds = 0, tableSnapshot = null) {
  operatorPacket.replaceChildren();
  if (!stage || !summary) {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = "No stage packet yet";
    row.append(label);
    operatorPacket.append(row);
    return;
  }

  const segment = currentStageRosterSegment;
  const activeIds = compactIdList(summary.tableRoster.map(({ id }) => id), 6);
  const effectiveRows = tableSnapshot?.rows || summary.tableRoster;
  const effectiveIds = compactIdList(effectiveRows.map(({ id }) => id), 6);
  const lead = summary.tableRoster[0] || effectiveRows[0];
  const leadLabel = lead ? `${lead.id} ${ROLE_LABELS[lead.role] || lead.role}` : "none";
  const nextStage = nextTavrStage(stage.key);
  const flags = operatorQualityFlags(stage, summary, tableSnapshot);
  const effectiveAge = tableSnapshot?.ageSeconds === null || tableSnapshot?.ageSeconds === undefined
    ? ""
    : `; age ${formatSeconds(tableSnapshot.ageSeconds)}`;
  const rows = [
    {
      label: "Current stage",
      value: `${stage.label} @ ${elapsedSeconds.toFixed(1)}s`,
      tone: "current",
    },
    {
      label: "Evidence",
      value: `${operatorEvidenceLevel(stage, summary)}; confidence ${operatorConfidence(stage)}`,
    },
    {
      label: "Table handoff",
      value: handoffLabel(segment?.handoffType || "initial_no_table_evidence"),
      handoff: segment?.handoffType || "initial_no_table_evidence",
    },
    {
      label: "Current table",
      value: `${summary.tableSide} staff; IDs ${activeIds}`,
    },
    {
      label: "Effective table",
      value: `${tableSnapshot?.count ?? summary.tableSide} staff; ${tableSourceLabel(tableSnapshot?.source)}; IDs ${effectiveIds}${effectiveAge}`,
    },
    {
      label: "Lead / next",
      value: `${leadLabel}; next ${nextStage?.label || "complete"}`,
    },
    {
      label: "Flags",
      value: flags.length ? flags.join(", ") : "none",
      tone: flags.length ? "warn" : "quiet",
    },
  ];

  rows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    if (item.tone) row.dataset.tone = item.tone;
    if (item.handoff) row.dataset.handoff = item.handoff.replaceAll("_", "-");
    label.textContent = item.label;
    value.textContent = item.value;
    row.append(label, value);
    operatorPacket.append(row);
  });
}

function renderProcedureStatus(status = null, demo = null) {
  procedureStatus.replaceChildren();
  if (!status) {
    appendInfoRow(procedureStatus, "No procedure status yet", "");
    return;
  }

  appendInfoRow(
    procedureStatus,
    currentStageStatusLabel(status.current_stage_status, status.current_stage_evidence_status),
    `${status.current_stage_label || "unknown"}; ${stageEvidenceLabel(status.current_stage_evidence_status || status.evidence_level)}`,
    { tone: "current" },
  );
  appendInfoRow(
    procedureStatus,
    "Current view",
    `${status.current_view || "unknown"}; tracking ${yesNo(status.tracking_available)}`,
  );
  appendInfoRow(
    procedureStatus,
    "Clock",
    formatClockRange(status, demo?.timebase),
  );
  appendInfoRow(
    procedureStatus,
    "Effective table",
    `${status.effective_table_count ?? 0} staff; ${tableSourceLabel(status.effective_table_source)}; ${formatPersonIds(status.effective_table_canonical_ids)}`,
  );
  appendInfoRow(
    procedureStatus,
    "Last observed",
    `${status.last_observed_table_count ?? 0} staff; ${formatPersonIds(status.last_observed_table_canonical_ids)}; age ${formatSeconds(status.last_observed_age_from_clip_end_s)}`,
  );
  appendInfoRow(
    procedureStatus,
    "Peak table",
    `${status.peak_table_count ?? 0} staff; ${formatPersonIds(status.peak_table_canonical_ids)}; raw ${formatIdList(status.peak_table_track_ids)}`,
  );
  scoreVerificationRows(demo?.scoreSummary, status).forEach((row) => {
    appendInfoRow(procedureStatus, row.label, row.value, { tone: row.tone });
  });
}

function renderVideoWorkflow(state = null) {
  videoWorkflow.replaceChildren();
  const current = state || {
    patientLabel: "Patient out of room",
    patientConfidence: 0,
    roomView: "idle",
    trackingAvailable: false,
    sourceLabel: currentVideoSourceLabel(),
    anaesthetistCount: 0,
    proceduralistCount: 0,
    tableCount: 0,
    effectiveTableCount: 0,
    latestEvent: null,
  };

  appendInfoRow(
    videoWorkflow,
    "Patient",
    `${current.patientLabel}; confidence ${formatNumber(current.patientConfidence)}`,
    { tone: current.patientLabel?.includes("unavailable") ? "warn" : "current" },
  );
  appendInfoRow(
    videoWorkflow,
    "Source",
    `${current.sourceLabel}; room view ${current.roomView}; tracking ${current.trackingAvailable ? "yes" : "no"}`,
    { tone: current.trackingAvailable ? "current" : "quiet" },
  );
  appendInfoRow(
    videoWorkflow,
    "Tracked roles",
    `${current.anaesthetistCount} anaesthetist; ${current.proceduralistCount} proceduralist`,
  );
  appendInfoRow(
    videoWorkflow,
    "Table context",
    `${current.tableCount} visible; ${current.effectiveTableCount} effective`,
  );
  appendInfoRow(
    videoWorkflow,
    "Latest event",
    current.latestEvent
      ? `${formatSeconds(current.latestEvent.time)} ${current.latestEvent.label}`
      : "none",
    { tone: current.latestEvent?.tone || "quiet" },
  );
}

function renderWorkflowEvents() {
  workflowEventList.replaceChildren();
  const visible = workflowEvents.slice(-8).reverse();
  if (!visible.length) {
    appendInfoRow(workflowEventList, "None yet", "");
    return;
  }
  visible.forEach((event) => {
    appendInfoRow(
      workflowEventList,
      `${formatSeconds(event.time)} ${event.label}`,
      event.detail,
      { tone: event.tone },
    );
  });
}

function renderReplayVideoWorkflow(status = {}, demo = null, packet = null) {
  try {
    const currentTable = currentTableSnapshot(status);
    const effectiveTable = effectiveTableSnapshot(status);
    const patientState = replayPatientState(status, currentTable, effectiveTable);
    const roleCounts = replayRoleCounts(status, demo, packet);
    const replayEvents = replayWorkflowEvents(status, demo, patientState);
    workflowEvents = replayEvents;
    workflowState = {
      ...workflowState,
      patientState,
      patientSeenInRoom: patientState !== "waiting_outside" && patientState !== "out_of_room",
      stageKey: status.current_stage || packet?.stage || null,
      roomView: status.current_view || "replay",
      tableRosterKey: (currentTable.canonicalIds || []).join(","),
      sourceLabel: "evaluated stock footage",
    };
    renderVideoWorkflow({
      patientState,
      patientLabel: PATIENT_STATE_LABELS[patientState] || patientState,
      patientConfidence: patientWorkflowConfidence(patientState, {
        trackingAvailable: Boolean(status.tracking_available),
        currentTableCount: currentTable.count,
        effectiveTableCount: effectiveTable.count,
        peopleCount: roleCounts.proceduralistCount + roleCounts.anaesthetistCount,
      }),
      roomView: status.current_view || "replay",
      trackingAvailable: Boolean(status.tracking_available),
      sourceLabel: "evaluated stock footage",
      anaesthetistCount: roleCounts.anaesthetistCount,
      proceduralistCount: roleCounts.proceduralistCount,
      tableCount: currentTable.count,
      effectiveTableCount: effectiveTable.count,
      latestEvent: replayEvents.at(-1) || null,
    });
    renderWorkflowEvents();
  } catch (error) {
    console.error("Replay workflow render failed", error);
    renderReplayVideoWorkflowFallback(status);
  }
}

function renderReplayVideoWorkflowFallback(status = {}) {
  const currentCount = Number(status.current_table_count || 0);
  const effectiveCount = Number(status.effective_table_count || 0);
  const patientState = status.tracking_available === false && effectiveCount > 0
    ? "in_room_unverified"
    : (currentCount > 0 ? "on_table" : (effectiveCount > 0 ? "in_room" : "in_room"));
  const time = statusTimeSeconds(status) || 0;
  workflowEvents = [{
    time,
    code: "patient_state_replayed",
    label: PATIENT_STATE_LABELS[patientState] || patientState,
    detail: "Derived from evaluated stock-footage status snapshot",
    tone: patientState === "in_room_unverified" ? "warn" : "current",
  }];
  workflowState = {
    ...workflowState,
    patientState,
    patientSeenInRoom: patientState !== "waiting_outside" && patientState !== "out_of_room",
    stageKey: status.current_stage || null,
    roomView: status.current_view || "replay",
    tableRosterKey: "",
    sourceLabel: "evaluated stock footage",
  };
  renderVideoWorkflow({
    patientState,
    patientLabel: PATIENT_STATE_LABELS[patientState] || patientState,
    patientConfidence: patientWorkflowConfidence(patientState, {
      trackingAvailable: Boolean(status.tracking_available),
      currentTableCount: currentCount,
      effectiveTableCount: effectiveCount,
      peopleCount: Number(status.peak_table_count || effectiveCount || currentCount || 0),
    }),
    roomView: status.current_view || "replay",
    trackingAvailable: Boolean(status.tracking_available),
    sourceLabel: "evaluated stock footage",
    anaesthetistCount: 0,
    proceduralistCount: Number(status.effective_table_count || status.current_table_count || 0),
    tableCount: currentCount,
    effectiveTableCount: effectiveCount,
    latestEvent: workflowEvents.at(-1),
  });
  renderWorkflowEvents();
}

function replayPatientState(status, currentTable, effectiveTable) {
  if (status.tracking_available === false && effectiveTable.count > 0) {
    return "in_room_unverified";
  }
  if (currentTable.count > 0) return "on_table";
  if (effectiveTable.count > 0) return "in_room";
  if (status.current_stage === "room_prep_drape") return "entering_room";
  if (status.current_stage === "closure_finish") return "leaving_room";
  return "in_room";
}

function replayRoleCounts(status, demo, packet) {
  const roster = [
    ...asArray(status.current_table_roster),
    ...asArray(status.effective_table_roster),
    ...asArray(packet?.active_table_roster),
  ];
  const proceduralistCount = new Set(
    roster
      .filter((row) => ["table_operator", "access_operator"].includes(
        row.table_team_role || row.dominant_role,
      ))
      .map((row) => row.canonical_table_id || row.track_id || row.label),
  ).size || Number(status.effective_table_count || status.current_table_count || 0);
  const stageStaffing = asArray(demo?.tavr?.stage_staffing_summary);
  const anaesthetistCount = Math.max(
    ...stageStaffing.map((row) => Number(row.role_counts?.anesthesia || 0)),
    0,
  );
  return { proceduralistCount, anaesthetistCount };
}

function replayWorkflowEvents(status, demo, patientState) {
  const events = [{
    time: statusTimeSeconds(status) || 0,
    code: "patient_state_replayed",
    label: PATIENT_STATE_LABELS[patientState] || patientState,
    detail: "Derived from evaluated stock-footage status snapshot",
    tone: patientState === "in_room_unverified" ? "warn" : "current",
  }];
  if (status.current_stage_label) {
    events.push({
      time: statusTimeSeconds(status) || 0,
      code: "procedure_stage_replayed",
      label: "Procedure stage",
      detail: status.current_stage_label,
      tone: "current",
    });
  }
  if (status.current_view) {
    events.push({
      time: statusTimeSeconds(status) || 0,
      code: "room_view_replayed",
      label: "Room view",
      detail: `${status.current_view}; tracking ${yesNo(status.tracking_available)}`,
      tone: status.tracking_available ? "current" : "warn",
    });
  }
  const focused = focusedReplayEvents(demo?.events || [], status).rows.slice(-3);
  focused.forEach((event) => {
    events.push({
      time: eventTimeSeconds(event),
      code: event.event_type || "replay_event",
      label: String(event.event_type || "Replay event").replaceAll("_", " "),
      detail: event.label || event.stage_label || "evaluated event",
      tone: "quiet",
    });
  });
  return events;
}

function renderBackendStatusSnapshots(rows = [], selectedIndex = -1) {
  statusSnapshotList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(statusSnapshotList, "None yet", "");
    return;
  }

  const visibleRows = visibleSnapshotRows(rows, selectedIndex, 10);
  if (visibleRows[0]?.index > 0) {
    appendInfoRow(statusSnapshotList, "Earlier snapshots", `${visibleRows[0].index} hidden`, {
      tone: "quiet",
    });
  }
  visibleRows.forEach(({ row, index }) => {
    appendInfoRow(
      statusSnapshotList,
      `${formatClockPoint(row)} ${snapshotReasonLabel(row.snapshot_reason)}`,
      [
        row.current_stage_label || "stage n/a",
        stageEvidenceLabel(row.current_stage_evidence_status || row.evidence_level),
        `${row.effective_table_count ?? 0} staff`,
        tableSourceLabel(row.effective_table_source),
        formatPersonIds(row.effective_table_canonical_ids),
      ].join("; "),
      {
        tone: index === selectedIndex ||
          (selectedIndex < 0 && asArray(row.snapshot_reason).includes("clip_end"))
          ? "current"
          : undefined,
      },
    );
  });
  const hiddenAfter = rows.length - (visibleRows.at(-1)?.index ?? -1) - 1;
  if (hiddenAfter > 0) {
    appendInfoRow(statusSnapshotList, "Later snapshots", `${hiddenAfter} hidden`, {
      tone: "quiet",
    });
  }
}

function visibleSnapshotRows(rows, selectedIndex, maxVisible) {
  if (rows.length <= maxVisible) {
    return rows.map((row, index) => ({ row, index }));
  }
  const selected = selectedIndex >= 0
    ? Math.min(Math.max(selectedIndex, 0), rows.length - 1)
    : rows.length - 1;
  const start = Math.min(
    Math.max(selected - Math.floor(maxVisible / 2), 0),
    rows.length - maxVisible,
  );
  return rows.slice(start, start + maxVisible).map((row, offset) => ({
    row,
    index: start + offset,
  }));
}

function renderBackendOperatorPacket(packets = [], status = null) {
  operatorPacket.replaceChildren();
  const packet = packetForStatus(packets, status || {});
  if (!packet) {
    appendInfoRow(operatorPacket, "No stage packet yet", "");
    return;
  }
  const isSelectedStatusStage = status?.current_stage && packet.stage === status.current_stage;

  appendInfoRow(
    operatorPacket,
    backendPacketStageLabel(packet, isSelectedStatusStage),
    `${packet.stage_label} ${formatClockRange(packet, status)}`,
    { tone: packet.is_current_stage || isSelectedStatusStage ? "current" : undefined },
  );
  appendInfoRow(
    operatorPacket,
    "Evidence",
    `${evidenceSupportLabel(packet.evidence_level, packet.stage_evidence_status)}; confidence ${formatNumber(packet.mean_confidence)}`,
  );
  appendInfoRow(
    operatorPacket,
    "Table handoff",
    handoffLabel(packet.handoff_type || "unknown"),
    { handoff: packet.handoff_type },
  );
  appendInfoRow(
    operatorPacket,
    "Stage roster",
    `${packet.stage_table_track_count ?? packet.active_table_track_count ?? 0} tracked; ${formatPersonIds(
      packet.stage_table_canonical_ids || packet.active_table_canonical_ids,
    )}; raw ${formatIdList(packet.stage_table_track_ids || packet.active_table_track_ids)}`,
  );
  if ((packet.brief_table_track_count ?? packet.brief_table_track_ids?.length ?? 0) > 0) {
    appendInfoRow(
      operatorPacket,
      "Brief contacts",
      `${packet.brief_table_track_count ?? packet.brief_table_track_ids.length} contacts; ${formatPersonIds(
        packet.brief_table_canonical_ids,
      )}; raw ${formatIdList(packet.brief_table_track_ids)}`,
    );
  }
  appendInfoRow(
    operatorPacket,
    "Active now",
    `${packet.active_table_track_count ?? packet.effective_table_count ?? status?.effective_table_count ?? 0} active; ${formatPersonIds(
      packet.active_table_canonical_ids ||
        packet.effective_table_canonical_ids ||
        status?.effective_table_canonical_ids,
    )}; raw ${formatIdList(
      packet.active_table_track_ids || packet.effective_table_track_ids,
    )}`,
    { tone: "current" },
  );
  appendInfoRow(
    operatorPacket,
    "Canonical people",
    `${packet.canonical_table_identity_count ?? 0}; lead ${formatPersonId(packet.lead_canonical_table_id)} ${ROLE_LABELS[packet.lead_table_team_role] || packet.lead_table_team_role || ""}`,
  );
  appendInfoRow(
    operatorPacket,
    "Effective table",
    `${packet.effective_table_count ?? status?.effective_table_count ?? 0}; ${tableSourceLabel(packet.effective_table_source || status?.effective_table_source)}; ${formatPersonIds(packet.effective_table_canonical_ids || status?.effective_table_canonical_ids)}`,
  );
  appendInfoRow(
    operatorPacket,
    "Within-stage movement",
    [
      formatPersonIds(
        packet.within_stage_entry_canonical_table_ids,
        "entered people",
      ),
      `raw entry IDs ${formatIdList(packet.within_stage_entry_track_ids)}`,
      formatPersonIds(
        packet.within_stage_exit_canonical_table_ids,
        "exited people",
      ),
      `raw exit IDs ${formatIdList(packet.within_stage_exit_track_ids)}`,
    ].join("; "),
  );
  const flags = asArray(packet.quality_flag_codes);
  appendInfoRow(
    operatorPacket,
    "Flags",
    flags.length ? flags.join(", ") : "none",
    { tone: flags.length ? "warn" : "quiet" },
  );
}

function renderBackendTableRoster(status = {}, presenceIntervals = []) {
  tableRoster.replaceChildren();
  const currentTable = currentTableSnapshot(status);
  const effectiveTable = effectiveTableSnapshot(status);
  const currentRows = currentTable.rows;
  const effectiveRows = effectiveTable.rows;
  renderTablePresenceSummary(currentTable, effectiveTable);

  if (!currentRows.length) {
    appendRosterListItem("At table now", "None", "empty");
  } else {
    appendBackendRosterRows({
      rows: currentRows,
      sourceLabel: "At table now",
      ageFromClipEndS: currentTable.ageFromClipEndS,
      context: "current",
    });
  }

  if (hasDistinctEffectiveTable(currentTable, effectiveTable)) {
    appendBackendRosterRows({
      rows: effectiveRows,
      sourceLabel: `At table for stage (${effectiveTable.sourceLabel})`,
      ageFromClipEndS: effectiveTable.ageFromClipEndS,
      context: "effective",
    });
  }

  appendPresenceIntervalRows(presenceIntervals, status);

  if (!currentRows.length && !effectiveRows.length && !presenceIntervals.length) {
    return;
  }
}

function appendPresenceIntervalRows(presenceIntervals = [], status = {}) {
  const rows = presenceIntervalsForStatus(presenceIntervals, status);
  const visibleRows = rows.slice(0, 5);
  visibleRows.forEach((row) => {
    const role = ROLE_LABELS[row.table_team_role] || row.table_team_role || "role n/a";
    const rawIds = formatIdList(row.merged_track_ids || [row.track_id]);
    const frames = row.observed_table_frames ?? 0;
    appendRosterListItem(
      "Presence interval",
      `${rosterPersonLabel(row)} ${role}; ${presenceIntervalRange(row)}; ${frames}f; raw ${rawIds}`,
      "effective",
    );
  });
  appendOverflowListItem(tableRoster, rows.length, visibleRows.length, "presence intervals");
}

function presenceIntervalsForStatus(presenceIntervals = [], status = {}) {
  const rows = asArray(presenceIntervals);
  if (!rows.length) return [];
  const stage = status.current_stage;
  const selectedTime = Number(
    status.clip_timestamp_s ??
    status.clip_end_s ??
    status.timestamp_s ??
    status.end_s,
  );
  const matches = rows.filter((row) => (
    (stage && row.dominant_stage === stage) ||
    (Number.isFinite(selectedTime) && intervalContainsClipTime(row, selectedTime))
  ));
  const selectedRows = matches.length ? matches : rows;
  return selectedRows
    .slice()
    .sort((a, b) => (
      Math.abs(intervalMidpoint(a) - (Number.isFinite(selectedTime) ? selectedTime : intervalMidpoint(a))) -
      Math.abs(intervalMidpoint(b) - (Number.isFinite(selectedTime) ? selectedTime : intervalMidpoint(b))) ||
      Number(b.observed_table_frames || 0) - Number(a.observed_table_frames || 0) ||
      Number(a.canonical_table_id ?? a.track_id ?? 0) - Number(b.canonical_table_id ?? b.track_id ?? 0)
    ));
}

function intervalContainsClipTime(row = {}, clipTime) {
  const start = Number(row.clip_start_s ?? row.start_s);
  const end = Number(row.clip_end_s ?? row.end_s);
  return Number.isFinite(start) && Number.isFinite(end) && start <= clipTime && end >= clipTime;
}

function intervalMidpoint(row = {}) {
  const start = Number(row.clip_start_s ?? row.start_s ?? 0);
  const end = Number(row.clip_end_s ?? row.end_s ?? start);
  return (start + end) / 2;
}

function presenceIntervalRange(row = {}) {
  const start = Number(row.clip_start_s ?? row.start_s);
  const end = Number(row.clip_end_s ?? row.end_s);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "time n/a";
  return `${formatSeconds(start)}-${formatSeconds(end)}`;
}

function appendBackendRosterRows({ rows, sourceLabel, ageFromClipEndS, context }) {
  const visibleRows = rows.slice(0, 5);
  const ageSuffix = ageFromClipEndS === null || ageFromClipEndS === undefined
    ? ""
    : `; age ${formatSeconds(ageFromClipEndS)}`;
  visibleRows.forEach((row) => {
    appendRosterListItem(
      sourceLabel,
      `${rosterPersonLabel(row)} ${ROLE_LABELS[row.table_team_role] || row.table_team_role}${ageSuffix}`,
      context,
    );
  });
  appendOverflowListItem(tableRoster, rows.length, visibleRows.length, "people");
}

function renderTablePresenceSummary(currentTable = {}, effectiveTable = null) {
  const effective = effectiveTable || currentTable || { rows: [], count: 0 };
  tablePresenceSummary.replaceChildren();
  appendTablePresenceRow(
    "Current room view",
    currentTable,
    "at table",
    (currentTable.count ?? currentTable.rows?.length ?? 0) ? "current" : "empty",
  );
  appendTablePresenceRow(
    "Stage table context",
    effective,
    "effective",
    (effective.count ?? effective.rows?.length ?? 0) ? "effective" : "empty",
  );
}

function appendTablePresenceRow(labelText, snapshot, countLabel, context) {
  const row = document.createElement("div");
  const label = document.createElement("span");
  const value = document.createElement("b");
  row.dataset.context = context;
  label.textContent = labelText;
  value.textContent = tableSnapshotSummary(snapshot, countLabel);
  row.append(label, value);
  tablePresenceSummary.append(row);
}

function renderOperatorAnswer(rows = []) {
  operatorAnswer.replaceChildren();
  const answerRows = rows.length ? rows : [{
    kind: "stage",
    label: "Stage",
    value: "Idle",
    detail: "No procedure stage yet",
    context: "empty",
  }];
  answerRows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    const detail = document.createElement("em");
    row.dataset.kind = item.kind;
    row.dataset.context = item.context || "empty";
    label.textContent = item.label;
    value.textContent = item.value;
    detail.textContent = item.detail || "";
    row.append(label, value, detail);
    operatorAnswer.append(row);
  });
}

function renderStageTableBrief(rows = []) {
  stageTableBrief.replaceChildren();
  const briefRows = rows.length ? rows : [{
    kind: "stage",
    label: "Stage",
    value: "Idle",
    detail: "No procedure stage yet",
    context: "empty",
  }];
  briefRows.forEach((item) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    const detail = document.createElement("em");
    row.dataset.kind = item.kind;
    row.dataset.context = item.context || "empty";
    label.textContent = item.label;
    value.textContent = item.value;
    detail.textContent = item.detail || "";
    row.append(label, value, detail);
    stageTableBrief.append(row);
  });
}

function appendRosterListItem(label, value, context) {
  const item = document.createElement("li");
  item.textContent = `${label}: ${value}`;
  if (context) item.dataset.context = context;
  tableRoster.append(item);
}

function hasDistinctEffectiveTable(currentTable, effectiveTable) {
  if (!effectiveTable.rows.length) return false;
  const currentIds = currentTable.rows
    .map((row) => row.canonical_table_id ?? row.track_id)
    .join(",");
  const effectiveIds = effectiveTable.rows
    .map((row) => row.canonical_table_id ?? row.track_id)
    .join(",");
  return (
    !currentTable.rows.length ||
    currentIds !== effectiveIds ||
    currentTable.source !== effectiveTable.source
  );
}

function renderBackendTableTeam(rows = []) {
  tableTeamList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(tableTeamList, "None yet", "");
    return;
  }

  const visibleRows = rows.slice(0, 8);
  visibleRows.forEach((row) => {
    appendInfoRow(
      tableTeamList,
      `${rosterPersonLabel(row)} ${ROLE_LABELS[row.table_team_role] || row.table_team_role}`,
      `${row.observed_table_frames ?? 0}f; ${statusLabel(row.team_status)}; raw ${formatIdList(row.merged_track_ids)}; ${row.dominant_stage_label || "stage n/a"}`,
      { status: row.team_status },
    );
  });
  appendOverflowRow(tableTeamList, rows.length, visibleRows.length, "people");
}

function renderBackendTableIdentities(rows = []) {
  tableIdentityList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(tableIdentityList, "None yet", "");
    return;
  }

  const visibleRows = rows.slice(0, 8);
  visibleRows.forEach((row) => {
    const stageSummary = summarizeStageCounts(row.stage_counts);
    appendInfoRow(
      tableIdentityList,
      `${rosterPersonLabel(row)} ${ROLE_LABELS[row.table_team_role] || row.table_team_role}`,
      `${row.observed_table_frames ?? 0}f; raw ${formatIdList(row.merged_track_ids)}; ${stageSummary}`,
    );
  });
  appendOverflowRow(tableIdentityList, rows.length, visibleRows.length, "identities");
}

function renderBackendStageCoverage(rows = []) {
  stageCoverageList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(stageCoverageList, "None yet", "");
    return;
  }

  const visibleRows = rows.slice(0, 8);
  visibleRows.forEach((row) => {
    appendInfoRow(
      stageCoverageList,
      `${row.stage_label}: ${rosterPersonLabel(row)} ${ROLE_LABELS[row.table_team_role] || row.table_team_role}`,
      `${row.observed_table_frames ?? 0}f; stage ${formatPercent(row.coverage_ratio)}; room ${formatPercent(row.room_coverage_ratio)}; raw ${formatIdList(row.merged_track_ids || [row.track_id])}`,
    );
  });
  appendOverflowRow(stageCoverageList, rows.length, visibleRows.length, "coverage rows");
}

function renderBackendStageRoster(rows = [], selectedRoster = null) {
  stageRosterList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(stageRosterList, "None yet", "");
    return;
  }

  const selectedIndex = selectedRoster
    ? rows.findIndex((row) => sameStageRosterRow(row, selectedRoster))
    : -1;
  const visibleRows = selectedIndex >= 0
    ? [rows[selectedIndex]]
    : rows.slice().reverse();

  visibleRows.forEach((row) => {
    const selected = selectedIndex >= 0 && sameStageRosterRow(row, selectedRoster);
    appendInfoRow(
      stageRosterList,
      `${selected ? "Selected " : ""}${row.stage_label}: ${handoffLabel(row.handoff_type || "unknown")}`,
      stageRosterDetail(row),
      {
        handoff: row.handoff_type,
        tone: selected ? "current" : undefined,
      },
    );
  });
  if (selectedIndex >= 0) {
    if (selectedIndex > 0) {
      appendInfoRow(stageRosterList, "Earlier stage rosters", `${selectedIndex} hidden`, {
        tone: "quiet",
      });
    }
    const laterCount = rows.length - selectedIndex - 1;
    if (laterCount > 0) {
      appendInfoRow(stageRosterList, "Later stage rosters", `${laterCount} hidden`, {
        tone: "quiet",
      });
    }
  }
}

function sameStageRosterRow(row = {}, selected = {}) {
  const rowSegment = row.stage_segment_index;
  const selectedSegment = selected.stage_segment_index;
  if (rowSegment !== null && rowSegment !== undefined &&
      selectedSegment !== null && selectedSegment !== undefined) {
    return Number(rowSegment) === Number(selectedSegment);
  }
  return row.stage === selected.stage &&
    !timesDiffer(row.clip_start_s ?? row.start_s, selected.clip_start_s ?? selected.start_s);
}

function stageRosterDetail(row = {}) {
  return [
    `peak ${row.peak_table_count ?? 0}`,
    formatPersonIds(row.active_table_canonical_ids, "stage roster people"),
    formatPersonIds(row.brief_table_canonical_ids, "brief contacts"),
    formatPersonIds(row.continued_canonical_table_ids, "continued people"),
    formatPersonIds(row.new_canonical_table_ids, "new people"),
    formatPersonIds(row.dropped_canonical_table_ids, "dropped people"),
    formatPersonIds(
      row.within_stage_entry_canonical_table_ids,
      "entered people",
    ),
    `raw entry IDs ${formatIdList(row.within_stage_entry_track_ids)}`,
    formatPersonIds(
      row.within_stage_exit_canonical_table_ids,
      "exited people",
    ),
    `raw exit IDs ${formatIdList(row.within_stage_exit_track_ids)}`,
    `tracking ${formatPercent(row.tracking_available_rate)}`,
  ].join("; ");
}

function renderBackendProcedureMilestones(rows = []) {
  milestoneList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(milestoneList, "None yet", "");
    return;
  }

  rows.forEach((row) => {
    appendInfoRow(
      milestoneList,
      `${row.stage_label}: ${row.milestone_status || "not observed"}`,
      row.observed_in_clip
        ? `${formatSeconds(row.first_observed_s)}-${formatSeconds(row.last_observed_s)}; peak ${row.peak_table_count ?? 0}`
        : "not seen",
      { status: row.milestone_status },
    );
  });
}

function renderBackendProcedureEvents(rows = [], status = null) {
  eventTimelineList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(eventTimelineList, "None yet", "");
    return;
  }

  const focused = status ? focusedReplayEvents(rows, status, 12) : null;
  const visibleRows = focused?.rows?.length ? focused.rows : rows.slice(0, 12);
  if (focused?.hiddenBefore) {
    appendInfoRow(eventTimelineList, "Earlier selected-stage events", `${focused.hiddenBefore} hidden`, {
      tone: "quiet",
    });
  }
  visibleRows.forEach((row) => {
    appendInfoRow(
      eventTimelineList,
      `${formatClockPoint(row)} ${handoffLabel(row.event_type || "event")}`,
      `${row.stage_label || row.view || "context"}; ${eventTableDetail(row)}`,
      { source: row.source_table },
    );
  });
  if (focused?.hiddenAfter) {
    appendInfoRow(eventTimelineList, "Later selected-stage events", `${focused.hiddenAfter} hidden`, {
      tone: "quiet",
    });
  }
  if (!focused) {
    appendOverflowRow(eventTimelineList, rows.length, visibleRows.length, "events");
  }
}

function renderBackendQualityFlags(rows = []) {
  qualityFlagList.replaceChildren();
  if (!rows.length) {
    appendInfoRow(qualityFlagList, "None", "");
    return;
  }

  rows.forEach((row) => {
    appendInfoRow(
      qualityFlagList,
      row.code || "quality_flag",
      row.message || `ratio ${formatPercent(row.ratio)}`,
      { tone: "warn" },
    );
  });
}

function operatorEvidenceLevel(stage, summary) {
  const confidence = stage.confidence;
  if (stage.stageHoldReason === "non_room_view") {
    return "held non-room context";
  }
  if (stage.stageHoldReason === "static_table_fallback") {
    return "held static roster evidence";
  }
  if (summary.tableSide === 0 && confidence !== undefined && confidence < 0.25) {
    return "held/no table evidence";
  }
  if (confidence === undefined) {
    return summary.tableSide > 0 ? "demo visual support" : "demo context only";
  }
  if (confidence >= 0.6 && summary.tableSide > 0) return "strong visual support";
  if (confidence >= BROWSER_STAGE_MIN_CONFIDENCE) return "moderate visual support";
  return summary.tableSide > 0 ? "weak visual support" : "weak/no table evidence";
}

function operatorConfidence(stage) {
  return stage.confidence === undefined ? "demo" : stage.confidence.toFixed(2);
}

function operatorQualityFlags(stage, summary, tableSnapshot = null) {
  const flags = [];
  if (stage.confidence !== undefined && stage.confidence < BROWSER_STAGE_MIN_CONFIDENCE) {
    flags.push("low_stage_confidence");
  }
  if (!summary.tableRoster.length) {
    if (tableSnapshot?.rows?.length) {
      flags.push("no_current_table_roster_evidence");
      flags.push("table_roster_held_from_room_view");
    } else {
      flags.push("no_table_roster_evidence");
    }
  }
  if (
    summary.tableRoster.some(({ staticFallback }) => staticFallback) ||
    tableSnapshot?.rows?.some(({ staticFallback }) => staticFallback)
  ) {
    flags.push("static_table_fallback");
  }
  if (stage.stageHoldReason === "non_room_view") {
    flags.push("non_room_view");
    flags.push("stage_hold_non_room_view");
  }
  if (stage.stageHoldReason === "static_table_fallback") {
    flags.push("stage_hold_static_table_fallback");
  }
  return flags;
}

function nextTavrStage(stageKey) {
  const stageMeta = TAVR_STAGE_LOOKUP.get(stageKey);
  if (!stageMeta) return null;
  return TAVR_STAGES[stageMeta.index + 1] || null;
}

function updateProcedureMilestones(stage, roster, tableSideCount, elapsedSeconds) {
  const stageMeta = TAVR_STAGE_LOOKUP.get(stage.key);
  if (!stageMeta) {
    renderProcedureMilestones();
    return;
  }

  currentMilestoneKey = stage.key;
  const item = milestoneProgress.get(stage.key) || {
    stageKey: stage.key,
    stageLabel: stage.label,
    firstSeen: elapsedSeconds,
    lastSeen: elapsedSeconds,
    frames: 0,
    peakTableCount: 0,
    trackIds: new Set(),
  };
  item.frames += 1;
  item.firstSeen = Math.min(item.firstSeen, elapsedSeconds);
  item.lastSeen = Math.max(item.lastSeen, elapsedSeconds);
  item.peakTableCount = Math.max(item.peakTableCount, tableSideCount);
  roster.forEach(({ id }) => item.trackIds.add(id));
  milestoneProgress.set(stage.key, item);
  renderProcedureMilestones();
}

function renderProcedureMilestones() {
  milestoneList.replaceChildren();
  const currentIndex = TAVR_STAGE_LOOKUP.get(currentMilestoneKey)?.index ?? -1;

  TAVR_STAGES.forEach((stage, index) => {
    const item = milestoneProgress.get(stage.key);
    const row = document.createElement("div");
    const label = document.createElement("span");
    const value = document.createElement("b");
    const status = getMilestoneStatus(stage.key, index, currentIndex, Boolean(item));

    row.dataset.status = status.key;
    label.textContent = `${stage.label}: ${status.label}`;
    value.textContent = item
      ? `${item.firstSeen.toFixed(1)}-${item.lastSeen.toFixed(1)}s; ` +
        `peak ${item.peakTableCount}; staff ${item.trackIds.size}`
      : "not seen";
    row.append(label, value);
    milestoneList.append(row);
  });
}

function getMilestoneStatus(stageKey, stageIndex, currentIndex, observed) {
  if (!observed) return { key: "not-observed", label: "not observed" };
  if (stageKey === currentMilestoneKey) return { key: "current", label: "current" };
  if (stageIndex < currentIndex || currentIndex < 0) {
    return { key: "observed-prior", label: "observed prior" };
  }
  return { key: "observed", label: "observed" };
}

function renderTableRoster(tableSnapshot, effectiveTableSnapshot = null) {
  tableRoster.replaceChildren();
  const roster = Array.isArray(tableSnapshot) ? tableSnapshot : (tableSnapshot?.rows || []);
  const currentTable = Array.isArray(tableSnapshot)
    ? { rows: tableSnapshot, count: tableSnapshot.length, source: tableSnapshot.length ? "current_room_view" : "current_room_view_empty" }
    : (tableSnapshot || { rows: [], count: 0, source: "current_room_view_empty" });
  renderTablePresenceSummary(currentTable, effectiveTableSnapshot || currentTable);

  if (!roster.length) {
    appendRosterListItem("At table now", "None", "empty");
  } else {
    renderBrowserRosterRows(roster, "At table now", tableSnapshot, "current");
  }

  if (effectiveTableSnapshot && hasDistinctBrowserTable(tableSnapshot, effectiveTableSnapshot)) {
    renderBrowserRosterRows(
      effectiveTableSnapshot.rows || [],
      `At table for stage (${tableSourceLabel(effectiveTableSnapshot.source)})`,
      effectiveTableSnapshot,
      "effective",
    );
  }
}

function renderBrowserRosterRows(roster, sourceLabel, tableSnapshot, context) {
  const ageSuffix = tableSnapshot?.ageSeconds === null || tableSnapshot?.ageSeconds === undefined
    ? ""
    : `; age ${formatSeconds(tableSnapshot.ageSeconds)}`;
  roster.forEach(({ id, role, rawIds }) => {
    const roleLabel = ROLE_LABELS[role] || role;
    const rawSuffix = rawIds?.length ? `; raw ${compactIdList(rawIds, 3)}` : "";
    appendRosterListItem(
      sourceLabel,
      `${id} - ${roleLabel}${rawSuffix}${ageSuffix}`,
      context,
    );
  });
}

function hasDistinctBrowserTable(currentTable, effectiveTable) {
  const currentRows = currentTable?.rows || [];
  const effectiveRows = effectiveTable?.rows || [];
  if (!effectiveRows.length) return false;
  const currentIds = currentRows.map((row) => row.id).join(",");
  const effectiveIds = effectiveRows.map((row) => row.id).join(",");
  return (
    !currentRows.length ||
    currentIds !== effectiveIds ||
    currentTable?.source !== effectiveTable?.source
  );
}

function dominantStageLabel(stages) {
  let bestLabel = "stage n/a";
  let bestCount = -1;
  stages.forEach((count, label) => {
    if (count > bestCount) {
      bestLabel = label;
      bestCount = count;
    }
  });
  return bestLabel;
}

function statusLabel(status) {
  if (status === "active_current") return "active";
  if (status === "recent_last_observed") return "recent";
  return "historical";
}

function handoffLabel(handoffType) {
  return handoffType.replaceAll("_", " ");
}

function snapshotReasonLabel(reason) {
  const reasons = asArray(reason);
  if (!reasons.length) return "status snapshot";
  return reasons.map((item) => handoffLabel(String(item))).join(" + ");
}

function stageEvidenceLabel(status) {
  if (!status) return "stage support n/a";
  const labels = {
    held_non_room_context: "held from non-room context",
    weak_visual_support: "weak visual support",
    moderate_visual_support: "moderate visual support",
    strong_visual_support: "strong visual support",
    held_non_room: "held non-room",
    unknown_stage_support: "unknown stage support",
  };
  return labels[status] || String(status).replaceAll("_", " ");
}

function currentStageStatusLabel(stageStatus, evidenceStatus) {
  if (stageStatus === "current_held_context" || evidenceStatus === "held_non_room_context") {
    return "Current held stage";
  }
  return "Current stage";
}

function backendPacketStageLabel(packet, isSelectedStatusStage) {
  if ((packet.is_current_stage || isSelectedStatusStage) && packet.stage_status === "current_held_context") {
    return "Current held stage";
  }
  if (packet.is_current_stage) return "Current stage";
  return isSelectedStatusStage ? "Replay stage" : "Observed stage";
}

function evidenceLevelLabel(level) {
  if (!level) return "evidence n/a";
  const labels = {
    held_non_room: "held non-room",
    weak_visual_support: "weak visual support",
    moderate_visual_support: "moderate visual support",
    strong_visual_support: "strong visual support",
  };
  return labels[level] || String(level).replaceAll("_", " ");
}

function evidenceSupportLabel(level, status) {
  const evidence = evidenceLevelLabel(level);
  const support = stageEvidenceLabel(status || level);
  return evidence === support ? evidence : `${evidence}; ${support}`;
}

function compactIdList(ids, maxVisible = 4) {
  if (!ids.length) return "none";
  const visible = ids.slice(0, maxVisible).join(",");
  const hidden = ids.length - maxVisible;
  return hidden > 0 ? `${visible}+${hidden}` : visible;
}

function appendInfoRow(container, labelText, valueText, options = {}) {
  const row = document.createElement("div");
  const label = document.createElement("span");
  const value = document.createElement("b");
  if (options.tone) row.dataset.tone = options.tone;
  if (options.handoff) row.dataset.handoff = String(options.handoff).replaceAll("_", "-");
  if (options.status) row.dataset.status = String(options.status).replaceAll("_", "-");
  if (options.source) row.dataset.source = String(options.source).replaceAll("_", "-");
  label.textContent = labelText;
  value.textContent = valueText;
  row.append(label);
  if (valueText !== "") row.append(value);
  container.append(row);
}

function appendOverflowRow(container, totalCount, visibleCount, itemLabel) {
  const hiddenCount = totalCount - visibleCount;
  if (hiddenCount <= 0) return;
  appendInfoRow(container, `+${hiddenCount} more`, `${totalCount} total ${itemLabel}`, {
    tone: "quiet",
  });
}

function appendOverflowListItem(container, totalCount, visibleCount, itemLabel) {
  const hiddenCount = totalCount - visibleCount;
  if (hiddenCount <= 0) return;
  const item = document.createElement("li");
  item.textContent = `+${hiddenCount} more (${totalCount} total ${itemLabel})`;
  container.append(item);
}

function formatSeconds(value) {
  return value === null || value === undefined ? "n/a" : `${Number(value).toFixed(1)}s`;
}

function formatClockRange(row = {}, fallback = {}) {
  const clipStart = firstDefined(row.clip_start_s, row.clip_timestamp_s, fallback?.clip_start_s);
  const clipEnd = firstDefined(row.clip_end_s, row.clip_timestamp_s, fallback?.clip_end_s);
  const sourceStart = firstDefined(row.source_start_s, row.start_s, row.timestamp_s, fallback?.source_start_s);
  const sourceEnd = firstDefined(row.source_end_s, row.end_s, row.timestamp_s, fallback?.source_end_s);
  const clipLabel = sameClockPoint(clipStart, clipEnd)
    ? `clip ${formatSeconds(clipStart)}`
    : `clip ${formatSeconds(clipStart)}-${formatSeconds(clipEnd)}`;
  if (!clockDiffers(clipStart, sourceStart) && !clockDiffers(clipEnd, sourceEnd)) {
    return clipLabel;
  }
  const sourceLabel = sameClockPoint(sourceStart, sourceEnd)
    ? `source ${formatSeconds(sourceStart)}`
    : `source ${formatSeconds(sourceStart)}-${formatSeconds(sourceEnd)}`;
  return `${clipLabel} / ${sourceLabel}`;
}

function formatClockPoint(row = {}) {
  const clip = firstDefined(row.clip_timestamp_s, row.clip_start_s, row.timestamp_s);
  const source = firstDefined(row.timestamp_s, row.source_timestamp_s, row.source_start_s);
  if (!clockDiffers(clip, source)) return formatSeconds(clip);
  return `${formatSeconds(clip)} / src ${formatSeconds(source)}`;
}

function firstDefined(...values) {
  return values.find((value) => value !== null && value !== undefined);
}

function sameClockPoint(first, second) {
  return first === null || first === undefined || second === null || second === undefined
    ? false
    : Math.abs(Number(first) - Number(second)) < 0.05;
}

function clockDiffers(first, second) {
  if (first === null || first === undefined || second === null || second === undefined) return false;
  return Math.abs(Number(first) - Number(second)) >= 0.05;
}

function formatNumber(value) {
  return value === null || value === undefined ? "n/a" : Number(value).toFixed(2);
}

function formatPercent(value) {
  return value === null || value === undefined ? "n/a" : `${Math.round(Number(value) * 100)}%`;
}

function formatIdList(ids, maxVisible = 6) {
  return compactIdList(asArray(ids), maxVisible);
}

function formatRosterPeople(roster = [], prefix = "people") {
  const rows = asArray(roster);
  const canonicalIds = rows
    .map((row) => row?.canonical_table_id)
    .filter((value) => value !== null && value !== undefined);
  if (canonicalIds.length) return formatPersonIds(canonicalIds, prefix);
  if (!rows.length) return `${prefix} none`;
  return `${prefix} ${rows.map((row) => rosterPersonLabel(row)).join(", ")}`;
}

function eventTableDetail(row = {}) {
  const roster = asArray(row.roster);
  if (roster.length) {
    const count = row.table_count ?? roster.length;
    return `table ${count}; ${formatRosterPeople(roster)}`;
  }
  if (row.canonical_table_id !== null && row.canonical_table_id !== undefined) {
    return `${rosterPersonLabel(row)} ${ROLE_LABELS[row.table_team_role] || row.table_team_role || ""}`;
  }
  if (row.table_count !== undefined) return `table ${row.table_count}; people none`;
  return `ID ${row.track_id ?? "n/a"} ${ROLE_LABELS[row.table_team_role] || row.table_team_role || ""}`;
}

function yesNo(value) {
  return value ? "yes" : "no";
}

function summarizeStageCounts(stageCounts = {}) {
  const entries = Object.entries(stageCounts);
  if (!entries.length) return "stage n/a";
  const [stageKey, frames] = entries.sort((a, b) => Number(b[1]) - Number(a[1]))[0];
  return `${TAVR_STAGE_LOOKUP.get(stageKey)?.label || stageKey} ${frames}f`;
}

function clearCanvas() {
  const rect = overlay.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  sparkCtx.clearRect(0, 0, sparkline.width, sparkline.height);
}

function setEmptyState(title, subtitle) {
  const titleNode = emptyState.querySelector("strong");
  const subtitleNode = emptyState.querySelector("span");
  if (titleNode) titleNode.textContent = title;
  if (subtitleNode) subtitleNode.textContent = subtitle;
}

function syncEmptyStateToVideoSource() {
  emptyState.hidden = hasVideoSource();
}

function resetMetrics(options = {}) {
  if (!options.keepEvaluationReplayRequest) evaluationReplayRequestId += 1;
  if (!options.keepSyntheticMode) syntheticMode = false;
  if (!options.keepLiveMode) liveMode = false;
  previousFrame = null;
  frameReadBlocked = false;
  activityHistory = [];
  browserIdentityTracker = new BrowserTableIdentityTracker();
  tableTeam = new Map();
  stageCoverage = new Map();
  stageRosterSegments = [];
  currentStageRosterSegment = null;
  milestoneProgress = new Map();
  currentMilestoneKey = null;
  lastObservedTableSnapshot = null;
  workflowState = initialWorkflowState();
  workflowEvents = [];
  resetEvaluationScrubber();
  uploadedStageIndex = selectedInitialStageIndex();
  uploadedStageStartedAt = sourceElapsedSeconds();
  stageMetric.textContent = "Idle";
  countMetric.textContent = "0";
  tableSideMetric.textContent = "0";
  setEmptyState("No video loaded", "Choose a local MP4, MOV, or M4V file.");
  renderTableRoster([]);
  renderOperatorAnswer();
  renderVideoWorkflow();
  renderWorkflowEvents();
  renderStageTableBrief();
  renderTableTeam();
  renderStageCoverage();
  renderStageRosterSummary();
  renderProcedureStatus();
  renderBackendStatusSnapshots();
  renderOperatorPacket();
  renderBackendTableIdentities();
  renderProcedureMilestones();
  renderBackendProcedureEvents();
  renderBackendQualityFlags();
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
