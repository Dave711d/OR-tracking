import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import {
  eventTimeSeconds,
  normalizeEvaluationPayload,
  packetForStatus,
  replayOperatorProjection,
  replaySnapshotAt,
  replaySnapshotIndexForTime,
  replaySnapshotLabel,
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
  assert.deepEqual(view.tableRosterItems, ["None"]);
  assert.deepEqual(view.currentTable.canonicalIds, []);
  assert.equal(view.effectiveTable.count, 2);
  assert.equal(view.effectiveTable.source, "recent_room_view_hold");
  assert.equal(view.effectiveTable.sourceLabel, "recent room-view hold");
  assert.deepEqual(view.effectiveTable.canonicalIds, [8, 10]);
  assert.match(view.effectiveTable.label, /2 staff; recent room-view hold; people Person 8, Person 10/);
});

test("replay projection separates current visible person from current-stage effective roster", async () => {
  const payload = await demoPayload("synthetic-full-tavr-evaluation.json");
  const view = replayOperatorProjection(payload, { label: "Full synthetic workflow" });

  assert.equal(view.stageMetric, "Closure / finish (strong_visual_support)");
  assert.equal(view.tableSideMetric, "1");
  assert.deepEqual(view.currentTable.canonicalIds, [9]);
  assert.equal(view.currentTable.sourceLabel, "current room view");
  assert.equal(view.tableRosterItems.length, 1);
  assert.match(view.tableRosterItems[0], /Person 9/);
  assert.doesNotMatch(view.tableRosterItems.join(" "), /Person 10/);
  assert.equal(view.effectiveTable.count, 2);
  assert.equal(view.effectiveTable.source, "current_stage_recent_room_window");
  assert.equal(view.effectiveTable.sourceLabel, "current-stage recent room window");
  assert.deepEqual(view.effectiveTable.canonicalIds, [9, 10]);
  assert.deepEqual(view.operatorPacketEffective.canonicalIds, [9, 10]);
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
