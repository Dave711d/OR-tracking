import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import {
  effectiveTableSnapshot,
  eventTimeSeconds,
  focusedReplayEvents,
  normalizeEvaluationPayload,
  packetForStatus,
  replayOperatorProjection,
  replaySnapshotAt,
  replaySnapshotIndexForTime,
  replaySnapshotLabel,
  scoreVerificationRows,
  stageTableBriefHandoffRows,
  stageTableBriefRows,
  stageTableBriefRowsFromSnapshots,
  statusTimeSeconds,
  tableSourceLabel,
} from "../public/replay_view.mjs";

async function demoPayload(fileName) {
  return JSON.parse(
    await readFile(new URL(`../public/demo-data/${fileName}`, import.meta.url), "utf8"),
  );
}

test("replay projection keeps current table empty when only held evidence exists", async () => {
  const payload = await demoPayload("sentara-1800-evaluation.json");
  const view = replayOperatorProjection(payload, { label: "1800s deployment table hold" });

  assert.equal(view.stageMetric, "Valve deployment (strong_visual_support)");
  assert.equal(view.tableSideMetric, "0");
  assert.deepEqual(view.stageTableBriefRows.slice(0, 10).map((row) => row.label), [
    "Stage",
    "Procedure progress",
    "Stage handoff",
    "Stage roster",
    "Stage Person 8 (ID 18)",
    "Stage Person 1 (ID 1)",
    "Stage Person 2 (ID 2)",
    "Now visible",
    "Effective for stage",
    "Person 8 (ID 21)",
  ]);
  assert.equal(view.stageTableBriefRows[1].value, "6/8 stages");
  assert.match(view.stageTableBriefRows[1].detail, /next Post-deploy assessment/);
  assert.match(view.stageTableBriefRows[1].detail, /observed 2\/8/);
  assert.equal(view.stageTableBriefRows[2].value, "table roster started");
  assert.equal(view.stageTableBriefRows[3].value, "10 tracked; 6 core");
  assert.match(view.stageTableBriefRows[3].detail, /4 brief contacts/);
  assert.match(view.stageTableBriefRows[4].value, /core; Table op; 36f/);
  assert.match(view.stageTableBriefRows[4].detail, /24\.3s-26\.3s/);
  assert.match(view.stageTableBriefRows[0].detail, /clip 30\.0s/);
  assert.match(view.stageTableBriefRows[2].detail, /new Person 1/);
  assert.match(view.stageTableBriefRows[2].detail, /new .*Person 10/);
  assert.match(view.stageTableBriefRows[2].detail, /dropped none/);
  assert.equal(view.stageTableBriefRows[7].value, "0 at table");
  assert.equal(view.stageTableBriefRows[8].value, "2 effective");
  assert.match(view.stageTableBriefRows[9].value, /held; Table op/);
  assert.deepEqual(view.tableRosterItems, ["None"]);
  assert.deepEqual(view.tablePresenceRows.map((row) => row.label), [
    "Current room view",
    "Stage table context",
  ]);
  assert.match(view.tablePresenceRows[0].value, /0 at table; current room view empty; people none/);
  assert.match(view.tablePresenceRows[1].value, /2 effective; recent room-view hold; people Person 8, Person 10/);
  assert.equal(view.effectiveTableRosterItems.length, 2);
  assert.match(view.effectiveTableRosterItems[0], /recent room-view hold: Person 8/);
  assert.match(view.effectiveTableRosterItems[1], /recent room-view hold: Person 10/);
  assert.deepEqual(view.currentTable.canonicalIds, []);
  assert.equal(view.effectiveTable.count, 2);
  assert.equal(view.effectiveTable.source, "recent_room_view_hold");
  assert.equal(view.effectiveTable.sourceLabel, "recent room-view hold");
  assert.deepEqual(view.effectiveTable.canonicalIds, [8, 10]);
  assert.match(view.effectiveTable.label, /2 staff; recent room-view hold; people Person 8, Person 10/);
  assert.deepEqual(view.scoreVerificationRows.map((row) => row.label), [
    "Stage verification",
    "Table person verification",
    "Operator snapshot",
  ]);
  assert.match(
    view.scoreVerificationRows.find((row) => row.label === "Stage verification").value,
    /stage 100%; evidence 100%; status 100%/,
  );
  assert.match(
    view.scoreVerificationRows.find((row) => row.label === "Table person verification").value,
    /intervals 100%; status 100%/,
  );
});

test("replay projection surfaces scored no-table person verification", async () => {
  const payload = await demoPayload("sentara-900-evaluation.json");
  const view = replayOperatorProjection(payload, { label: "900s no-table negative" });

  assert.deepEqual(view.currentTable.canonicalIds, []);
  assert.equal(view.effectiveTable.count, 0);
  assert.deepEqual(view.effectiveTable.canonicalIds, []);
  assert.deepEqual(view.tableRosterItems, ["None"]);
  assert.deepEqual(view.scoreVerificationRows.map((row) => row.label), [
    "Stage verification",
    "Table person verification",
    "Operator snapshot",
    "No-table verification",
  ]);
  assert.match(
    view.scoreVerificationRows.find((row) => row.label === "Table person verification").value,
    /intervals 100%; status 100%/,
  );
  assert.equal(
    view.scoreVerificationRows.find((row) => row.label === "No-table verification").value,
    "0 current/effective/last/peak staff",
  );
  assert.equal(
    scoreVerificationRows(payload.score_summary, payload.tavr.procedure_status_summary[0]).at(-1).tone,
    "current",
  );
});

test("replay projection separates current visible person from current-stage effective roster", async () => {
  const payload = await demoPayload("synthetic-full-tavr-evaluation.json");
  const demo = normalizeEvaluationPayload(payload, { label: "Full synthetic workflow" });
  const view = replayOperatorProjection(payload, { label: "Full synthetic workflow" });

  assert.ok(demo.presenceIntervals.length >= 3);
  assert.deepEqual(
    demo.presenceIntervals
      .filter((row) => row.dominant_stage === "closure_finish")
      .map((row) => row.canonical_table_id),
    [9, 10],
  );
  assert.deepEqual(
    demo.presenceIntervals
      .filter((row) => row.dominant_stage === "closure_finish")
      .map((row) => row.merged_track_ids),
    [[22], [23]],
  );
  assert.equal(view.stageMetric, "Closure / finish (strong_visual_support)");
  assert.equal(view.tableSideMetric, "1");
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}; ${row.detail}`).join(" "), /Procedure progress: 8\/8 stages; next complete; observed 8\/8/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}; ${row.detail}`).join(" "), /Stage roster: 2 tracked; 2 core; peak 2; tracking 100%; lead Person 9/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}; ${row.detail}`).join(" "), /Stage Person 9 \(ID 22\): core; Access; 41f; 11\.6s-13\.3s; room 100%/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}`).join(" "), /Person 9.*now \+ effective/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}`).join(" "), /Person 10.*held/);
  assert.match(view.tablePresenceRows[0].value, /1 at table; current room view; people Person 9/);
  assert.match(view.tablePresenceRows[1].value, /2 effective; current-stage recent room window; people Person 9, Person 10/);
  assert.deepEqual(view.currentTable.canonicalIds, [9]);
  assert.equal(view.currentTable.sourceLabel, "current room view");
  assert.equal(view.tableRosterItems.length, 1);
  assert.match(view.tableRosterItems[0], /Person 9/);
  assert.doesNotMatch(view.tableRosterItems.join(" "), /Person 10/);
  assert.equal(view.effectiveTableRosterItems.length, 2);
  assert.match(view.effectiveTableRosterItems.join(" "), /Person 9/);
  assert.match(view.effectiveTableRosterItems.join(" "), /Person 10/);
  assert.equal(view.effectiveTable.count, 2);
  assert.equal(view.effectiveTable.source, "current_stage_recent_room_window");
  assert.equal(view.effectiveTable.sourceLabel, "current-stage recent room window");
  assert.deepEqual(view.effectiveTable.canonicalIds, [9, 10]);
  assert.deepEqual(view.operatorPacketEffective.canonicalIds, [9, 10]);
});

test("effective table snapshot exposes static fallback continuity roster", async () => {
  const payload = await demoPayload("sentara-900-static-fallback-evaluation.json");
  const demo = normalizeEvaluationPayload(payload, { label: "900s static fallback" });
  const snapshot = effectiveTableSnapshot(demo.status);
  const view = replayOperatorProjection(payload, { label: "900s static fallback" });

  assert.equal(snapshot.source, "last_observed_room_view");
  assert.equal(snapshot.sourceLabel, "last observed room view");
  assert.equal(snapshot.count, 3);
  assert.deepEqual(snapshot.canonicalIds, [1, 2, 3]);
  assert.deepEqual(view.currentTable.canonicalIds, []);
  assert.equal(stageTableBriefRows(demo.status)[1].value, "2/8 stages");
  assert.equal(stageTableBriefRows(demo.status)[2].value, "0 at table");
  assert.equal(stageTableBriefRows(demo.status)[3].value, "3 effective");
  assert.equal(view.stageTableBriefRows[3].value, "3 tracked; 2 core");
  assert.match(view.stageTableBriefRows[4].value, /core; Table op; 105f/);
  assert.match(view.stageTableBriefRows[4].detail, /0\.0s-4\.2s; room 83%/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}`).join(" "), /Person 1.*held/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}`).join(" "), /Person 2.*held/);
  assert.match(view.stageTableBriefRows.map((row) => `${row.label}: ${row.value}`).join(" "), /Person 3.*held/);
  assert.match(view.tablePresenceRows[0].value, /0 at table; current room view empty; people none/);
  assert.match(view.tablePresenceRows[1].value, /3 effective; last observed room view; people Person 1, Person 2, Person 3/);
  assert.equal(view.effectiveTableRosterItems.length, 3);
  assert.match(view.effectiveTableRosterItems.join(" "), /Person 1/);
  assert.match(view.effectiveTableRosterItems.join(" "), /Person 2/);
  assert.match(view.effectiveTableRosterItems.join(" "), /Person 3/);
});

test("evaluation replay normalization sorts events by clip-relative fallback time", () => {
  const demo = normalizeEvaluationPayload({
    case: "sort_smoke",
    tavr: {
      procedure_event_timeline: [
        { event_type: "late", clip_timestamp_s: 4.5 },
        { event_type: "early", clip_start_s: 1.25 },
      ],
      table_transition_events: [
        { event_type: "middle", timestamp_s: 3 },
      ],
    },
  });

  assert.deepEqual(
    demo.events.map((event) => event.event_type),
    ["early", "middle", "late"],
  );
  assert.equal(eventTimeSeconds({ clip_start_s: 2.5 }), 2.5);
  assert.equal(eventTimeSeconds({ timestamp_s: 1801, clip_timestamp_s: 1 }), 1);
  assert.equal(statusTimeSeconds({ clip_start_s: 0, clip_end_s: 29.963 }), 29.963);
});

test("replay snapshots select matching operator packets by stage and time", async () => {
  const payload = await demoPayload("synthetic-full-tavr-evaluation.json");
  const demo = normalizeEvaluationPayload(payload, { label: "Full synthetic workflow" });
  const first = replaySnapshotAt(demo, 0);
  const deploymentIndex = replaySnapshotIndexForTime(demo, 8.8);
  const deployment = replaySnapshotAt(demo, deploymentIndex);
  const final = replaySnapshotAt(demo);

  assert.equal(first.current_stage, "room_prep_drape");
  assert.equal(packetForStatus(demo.packets, first).stage, "room_prep_drape");
  assert.equal(deployment.current_stage, "valve_deployment");
  assert.equal(packetForStatus(demo.packets, deployment).stage, "valve_deployment");
  assert.equal(final.current_stage, "closure_finish");
  assert.equal(packetForStatus(demo.packets, final).stage, "closure_finish");
  assert.match(replaySnapshotLabel(deployment, deploymentIndex, demo.statusSnapshots.length), /Valve deployment/);
});

test("focused replay events stay scoped to the selected snapshot stage", async () => {
  const payload = await demoPayload("synthetic-full-tavr-evaluation.json");
  const demo = normalizeEvaluationPayload(payload, { label: "Full synthetic workflow" });
  const final = replaySnapshotAt(demo);
  const focused = focusedReplayEvents(demo.events, final, 12);
  const compact = focusedReplayEvents(demo.events, final, 3);

  assert.equal(final.current_stage, "closure_finish");
  assert.equal(focused.focused, true);
  assert.deepEqual(new Set(focused.rows.map((row) => row.stage)), new Set(["closure_finish"]));
  assert.deepEqual(
    focused.rows.map((row) => row.event_type),
    [
      "stage_started",
      "table_handoff",
      "table_present_at_stage_start",
      "table_present_at_stage_start",
      "table_exit",
      "table_peak",
      "table_present_at_stage_end",
    ],
  );
  assert.equal(focused.rows.find((row) => row.event_type === "table_handoff").handoff_type, "roster_changed");
  assert.equal(focused.rows.some((row) => row.stage === "access_sheathing"), false);
  assert.equal(compact.rows.length, 3);
  assert.equal(compact.rows[0].event_type, "stage_started");
  assert.equal(compact.rows[1].event_type, "table_handoff");
  assert.ok(compact.hiddenBefore > 0);
});

test("replay projection can represent an earlier selected snapshot", async () => {
  const payload = await demoPayload("synthetic-full-tavr-evaluation.json");
  const view = replayOperatorProjection(payload, { label: "Full synthetic workflow" }, 0);

  assert.equal(view.stageMetric, "Room prep / drape (moderate_visual_support)");
  assert.equal(view.tableSideMetric, "0");
  assert.equal(view.effectiveTable.source, "current_room_view_empty");
  assert.deepEqual(view.operatorPacketEffective.canonicalIds, []);
});

test("table source labels cover effective table continuity states", () => {
  assert.equal(
    tableSourceLabel("current_stage_recent_room_window"),
    "current-stage recent room window",
  );
  assert.equal(tableSourceLabel("recent_room_view_hold"), "recent room-view hold");
});

test("stage table brief formats browser handoff people without double person labels", () => {
  const rows = stageTableBriefRowsFromSnapshots({
    stageLabel: "Uploaded review",
    evidenceLabel: "confidence 0.8",
    timeLabel: "1.0s",
    progress: {
      stageIndex: 5,
      totalStages: 8,
      nextLabel: "Post-deploy assessment",
      observedCount: 6,
      observedTotal: 8,
    },
    currentTable: {
      count: 2,
      rows: [
        { id: "P1", role: "table_operator" },
        { id: "P2", role: "access_operator" },
      ],
      source: "current_room_view",
    },
    effectiveTable: {
      count: 2,
      rows: [
        { id: "P1", role: "table_operator" },
        { id: "P2", role: "access_operator" },
      ],
      source: "current_room_view",
    },
    handoff: {
      handoffType: "roster_added",
      activeIds: ["P1", "P2"],
      continuedIds: ["P1"],
      newIds: ["P2"],
      droppedIds: [],
      withinStageEntryIds: ["P2"],
      withinStageExitIds: ["P1"],
    },
  });
  const handoff = rows.find((row) => row.kind === "handoff");
  const progress = rows.find((row) => row.kind === "progress");

  assert.equal(progress.value, "6/8 stages");
  assert.equal(progress.detail, "next Post-deploy assessment; observed 6/8");
  assert.equal(handoff.value, "roster added");
  assert.equal(
    handoff.detail,
    "continued P1; new P2; dropped none; entered P2; exited P1",
  );
  assert.match(rows.map((row) => row.detail).join(" "), /people P1, P2/);
  assert.doesNotMatch(rows.map((row) => row.detail).join(" "), /Person P/);
});

test("stage handoff brief exposes canonical within-stage entry and exit people", () => {
  const rows = stageTableBriefHandoffRows({
    handoff_type: "roster_changed",
    active_table_canonical_ids: [1, 2],
    continued_canonical_table_ids: [1],
    new_canonical_table_ids: [2],
    dropped_canonical_table_ids: [],
    within_stage_entry_canonical_table_ids: [2],
    within_stage_exit_canonical_table_ids: [1],
  });

  assert.equal(rows[0].value, "roster changed");
  assert.match(rows[0].detail, /entered Person 2/);
  assert.match(rows[0].detail, /exited Person 1/);
});
