import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CASE_SETUP_DATABASE,
  addCaseTask,
  assigneeSkillWarning,
  buildActiveCaseProfile,
  defaultCaseSetupState,
  locationsForHospital,
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
  assert.deepEqual(profile.proceduralists.map((person) => person.displayName), ["Martin Ng"]);
  assert.equal(profile.tasks.length, 5);
  assert.equal(validateCaseSetup(state).length, 0);
});

test("case changes reseed location, proceduralists, and default task plan", () => {
  const cardiac = stateForCase("cardiac-surgery", defaultCaseSetupState());
  const profile = buildActiveCaseProfile(cardiac);

  assert.equal(profile.location.name, "OT11");
  assert.deepEqual(profile.proceduralists.map((person) => person.displayName), ["Michael Vallely"]);
  assert.match(profile.tasks.map((task) => task.label).join(" "), /Incision and exposure/);
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
