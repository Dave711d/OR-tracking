import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CASE_SETUP_DATABASE,
  addCaseTask,
  applyPreferenceCardsToTasks,
  assigneeSkillWarning,
  buildActiveCaseProfile,
  defaultCaseSetupState,
  defaultPreferenceCardIds,
  locationsForHospital,
  preferenceCardsForSetup,
  proceduralistById,
  removeCaseTask,
  roleTypeLabel,
  stateForCase,
  updateCaseTask,
  validateCaseSetup,
} from "../public/case_setup.mjs";

test("case setup database seeds MUH rooms and proceduralist role types", () => {
  assert.deepEqual(
    CASE_SETUP_DATABASE.hospitals.map((hospital) => hospital.code),
    ["MUH"],
  );
  assert.deepEqual(
    locationsForHospital("muh").map((location) => location.name),
    ["Cath Lab", "OT11", "OT10"],
  );
  assert.deepEqual(
    CASE_SETUP_DATABASE.proceduralists.map((person) => [
      person.displayName,
      roleTypeLabel(person.roleType),
    ]),
    [
      ["Martin Ng", "Interventional cardiologist"],
      ["David Dsilva", "Anaesthesia"],
      ["Bridget Prior", "Anaesthesia"],
      ["Michael Vallely", "Cardiac surgeon"],
      ["Walid Mohabbat", "Vascular surgeon"],
    ],
  );
});

test("default setup opens a MUH Cath Lab structural heart case with editable tasks", () => {
  const state = defaultCaseSetupState();
  const profile = buildActiveCaseProfile(state);

  assert.equal(profile.hospital.code, "MUH");
  assert.equal(profile.location.name, "Cath Lab");
  assert.equal(profile.caseProfile.name, "TAVR / structural heart");
  assert.deepEqual(profile.proceduralists.map((person) => person.displayName), [
    "Martin Ng",
    "David Dsilva",
  ]);
  assert.deepEqual(
    profile.preferenceCards.map((card) => card.id),
    ["pref-martin-ng-tavr", "pref-david-dsilva-tavr"],
  );
  assert.equal(profile.tasks.length, 11);
  assert.ok(profile.tasks.some((task) => task.assigneeId === "david-dsilva"));
  assert.ok(profile.tasks.some((task) => task.id === "pref:pref-david-dsilva-tavr:david-tavr-art-line"));
  assert.equal(validateCaseSetup(state).length, 0);
});

test("case changes reseed location, proceduralists, and default task plan", () => {
  const cardiac = stateForCase("cardiac-surgery", defaultCaseSetupState());
  const profile = buildActiveCaseProfile(cardiac);

  assert.equal(profile.location.name, "OT11");
  assert.deepEqual(profile.proceduralists.map((person) => person.displayName), [
    "Michael Vallely",
    "Bridget Prior",
  ]);
  assert.match(profile.tasks.map((task) => task.label).join(" "), /Incision and exposure/);
  assert.deepEqual(
    profile.preferenceCards.map((card) => card.id),
    ["pref-bridget-prior-cardiac", "pref-michael-vallely-cardiac"],
  );
  assert.ok(profile.tasks.some((task) => task.assigneeId === "bridget-prior"));
});

test("workflow preference cards are matched to selected case and clinical team", () => {
  const state = defaultCaseSetupState();
  const cards = preferenceCardsForSetup(state);

  assert.deepEqual(cards.map((card) => card.title), [
    "Martin Ng TAVR preference card",
    "David Dsilva TAVR anaesthetic preference card",
  ]);
  assert.deepEqual(defaultPreferenceCardIds(state), cards.map((card) => card.id));
  assert.equal(cards[0].items[0].timingLabel, "8m before patient in room");
  assert.equal(cards[1].items[0].plannedMinute, -6);
});

test("preference card task merge can remove cards and preserve edits for selected cards", () => {
  const state = defaultCaseSetupState();
  const davidTaskId = "pref:pref-david-dsilva-tavr:david-tavr-rapid-pacing";
  const martinOnly = applyPreferenceCardsToTasks(state.tasks, ["pref-martin-ng-tavr"]);

  assert.equal(martinOnly.some((task) => task.id === davidTaskId), false);

  const edited = updateCaseTask(state.tasks, davidTaskId, { plannedMinute: 21 });
  const retained = applyPreferenceCardsToTasks(edited, state.preferenceCardIds);
  assert.equal(retained.find((task) => task.id === davidTaskId).plannedMinute, 21);
});

test("task editor helpers can retime, reassign, add, and remove case tasks", () => {
  const state = defaultCaseSetupState();
  const taskId = state.tasks.find((task) => task.label === "Access and sheathing").id;
  let tasks = updateCaseTask(state.tasks, taskId, {
    plannedMinute: 22,
    assigneeId: "martin-ng",
  });
  assert.equal(tasks.find((task) => task.id === taskId).plannedMinute, 22);

  tasks = addCaseTask(tasks, {
    label: "Extra wire check",
    plannedMinute: 31,
    assigneeId: "martin-ng",
  });
  assert.equal(tasks.at(-1).label, "Extra wire check");

  tasks = removeCaseTask(tasks, taskId);
  assert.equal(tasks.some((task) => task.id === taskId), false);
});

test("skill mismatch warning flags reassignment outside proceduralist role type", () => {
  const state = defaultCaseSetupState();
  const deployment = state.tasks.find((task) => task.id === "tavr-deploy");
  const surgeon = proceduralistById("michael-vallely");

  assert.match(
    assigneeSkillWarning(deployment, surgeon),
    /Cardiac surgeon.*Interventional cardiologist/,
  );
});
