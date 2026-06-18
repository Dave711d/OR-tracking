import assert from "node:assert/strict";
import { test } from "node:test";

import { BrowserTableIdentityTracker } from "../public/browser_identity.mjs";

function row(rawId, cx, cy = 0.5, role = "table_operator") {
  const w = 0.04;
  const h = 0.16;
  return {
    rawId,
    id: rawId,
    role,
    x: cx - w / 2,
    y: cy - h / 2,
    w,
    h,
  };
}

test("browser identity tracker preserves people through crossing fragments", () => {
  const tracker = new BrowserTableIdentityTracker();
  const first = tracker.update([row("A", 0.12), row("B", 0.22)], 0.0);
  tracker.update([row("A", 0.145), row("B", 0.195)], 0.1);
  tracker.update([row("A", 0.17), row("B", 0.17, 0.505)], 0.2);
  tracker.update([], 0.3);
  const crossed = tracker.update([row("C", 0.145), row("D", 0.195)], 0.4);
  const final = tracker.update([row("C", 0.12), row("D", 0.22)], 0.5);

  const personA = first[0].id;
  const personB = first[1].id;

  assert.equal(crossed[0].id, personB);
  assert.equal(crossed[1].id, personA);
  assert.equal(final[0].id, personB);
  assert.equal(final[1].id, personA);
  assert.deepEqual(
    tracker.groups().map((group) => group.rawIds),
    [
      ["A", "D"],
      ["B", "C"],
    ],
  );
});

test("browser identity tracker keeps raw id reuse sticky", () => {
  const tracker = new BrowserTableIdentityTracker();
  const first = tracker.update([row("T1", 0.4)], 0.0);
  const second = tracker.update([row("T1", 0.405)], 0.1);

  assert.equal(second[0].id, first[0].id);
  assert.deepEqual(tracker.groups()[0].rawIds, ["T1"]);
  assert.equal(tracker.groups()[0].frames, 2);
});

test("browser identity tracker reset starts identities from P1", () => {
  const tracker = new BrowserTableIdentityTracker();
  tracker.update([row("A", 0.2)], 0.0);
  tracker.reset();
  const afterReset = tracker.update([row("B", 0.8)], 0.0);

  assert.equal(afterReset[0].id, "P1");
  assert.deepEqual(tracker.groups()[0].rawIds, ["B"]);
});
