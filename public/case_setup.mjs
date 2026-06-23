export const ROLE_TYPE_OPTIONS = [
  {
    id: "interventional_cardiologist",
    label: "Interventional cardiologist",
    skillSets: ["Structural heart", "TAVR access", "Fluoroscopy-led intervention"],
  },
  {
    id: "cardiac_surgeon",
    label: "Cardiac surgeon",
    skillSets: ["Open cardiac surgery", "Surgical bailout", "Valve exposure"],
  },
  {
    id: "vascular_surgeon",
    label: "Vascular surgeon",
    skillSets: ["Vascular access", "Endovascular repair", "Peripheral bailout"],
  },
  {
    id: "anaesthesia",
    label: "Anaesthesia",
    skillSets: ["Airway", "Haemodynamics", "Line placement"],
  },
  {
    id: "nursing",
    label: "Nursing / circulating team",
    skillSets: ["Room setup", "Counts", "Specimen and equipment flow"],
  },
  {
    id: "imaging",
    label: "Imaging",
    skillSets: ["C-arm", "Fluoroscopy", "Image acquisition"],
  },
];

export const CASE_ROLE_OPTIONS = [
  { id: "case_lead", label: "Case lead" },
  { id: "primary_operator", label: "Primary operator" },
  { id: "access_operator", label: "Access operator" },
  { id: "surgical_operator", label: "Surgical operator" },
  { id: "vascular_operator", label: "Vascular operator" },
  { id: "anaesthetist", label: "Anaesthetist" },
  { id: "imaging_operator", label: "Imaging operator" },
  { id: "circulator", label: "Circulator" },
  { id: "device_prep", label: "Device prep" },
  { id: "handover", label: "Handover" },
];

export const TASK_KIND_OPTIONS = [
  { id: "event", label: "Event" },
  { id: "role", label: "Role" },
  { id: "task", label: "Task" },
  { id: "handover", label: "Handover" },
];

export const CASE_SETUP_DATABASE = {
  hospitals: [
    {
      id: "muh",
      code: "MUH",
      name: "Macquarie University Hospital",
    },
  ],
  locations: [
    {
      id: "muh-cath-lab",
      hospitalId: "muh",
      name: "Cath Lab",
      capabilityTags: ["Structural heart", "Endovascular", "Fluoroscopy"],
    },
    {
      id: "muh-ot11",
      hospitalId: "muh",
      name: "OT11",
      capabilityTags: ["Cardiac surgery", "Hybrid support"],
    },
    {
      id: "muh-ot10",
      hospitalId: "muh",
      name: "OT10",
      capabilityTags: ["Vascular surgery", "General operating theatre"],
    },
  ],
  proceduralists: [
    {
      id: "martin-ng",
      displayName: "Martin Ng",
      roleType: "interventional_cardiologist",
      specialty: "Cardiologist",
      skillSets: ["Structural heart", "TAVR access", "Coronary and valve intervention"],
      defaultCaseRoles: ["case_lead", "primary_operator", "access_operator"],
    },
    {
      id: "david-dsilva",
      displayName: "David Dsilva",
      roleType: "anaesthesia",
      specialty: "Anaesthetist",
      skillSets: ["Anaesthesia", "Haemodynamic management", "Airway and line management"],
      defaultCaseRoles: ["anaesthetist"],
    },
    {
      id: "bridget-prior",
      displayName: "Bridget Prior",
      roleType: "anaesthesia",
      specialty: "Anaesthetist",
      skillSets: ["Anaesthesia", "Perioperative monitoring", "Airway and line management"],
      defaultCaseRoles: ["anaesthetist"],
    },
    {
      id: "michael-vallely",
      displayName: "Michael Vallely",
      roleType: "cardiac_surgeon",
      specialty: "Cardiac surgeon",
      skillSets: ["Cardiac surgery", "Valve surgery", "Surgical bailout"],
      defaultCaseRoles: ["case_lead", "surgical_operator"],
    },
    {
      id: "walid-mohabbat",
      displayName: "Walid Mohabbat",
      roleType: "vascular_surgeon",
      specialty: "Vascular surgeon",
      skillSets: ["Vascular access", "Endovascular repair", "Peripheral bailout"],
      defaultCaseRoles: ["case_lead", "vascular_operator", "access_operator"],
    },
  ],
  cases: [
    {
      id: "tavr-structural-heart",
      name: "TAVR / structural heart",
      defaultLocationId: "muh-cath-lab",
      defaultProceduralistIds: ["martin-ng", "david-dsilva"],
      expectedRoleTypes: ["interventional_cardiologist", "anaesthesia"],
      tasks: [
        {
          id: "tavr-brief",
          kind: "handover",
          label: "Case briefing and room readiness",
          caseRole: "case_lead",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
          plannedMinute: 0,
        },
        {
          id: "tavr-anaesthetic-ready",
          kind: "task",
          label: "Anaesthetic readiness and monitoring",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "david-dsilva",
          plannedMinute: 3,
        },
        {
          id: "tavr-patient-in",
          kind: "event",
          label: "Patient in room",
          caseRole: "circulator",
          requiredRoleType: "nursing",
          assigneeId: "",
          plannedMinute: 5,
        },
        {
          id: "tavr-access",
          kind: "task",
          label: "Access and sheathing",
          caseRole: "access_operator",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
          plannedMinute: 14,
        },
        {
          id: "tavr-deploy",
          kind: "event",
          label: "Valve deployment readiness",
          caseRole: "primary_operator",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
          plannedMinute: 28,
        },
        {
          id: "tavr-closure",
          kind: "task",
          label: "Closure and patient out",
          caseRole: "access_operator",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
          plannedMinute: 45,
        },
      ],
    },
    {
      id: "cardiac-surgery",
      name: "Cardiac surgery / valve support",
      defaultLocationId: "muh-ot11",
      defaultProceduralistIds: ["michael-vallely", "bridget-prior"],
      expectedRoleTypes: ["cardiac_surgeon", "anaesthesia"],
      tasks: [
        {
          id: "cardiac-brief",
          kind: "handover",
          label: "Surgical briefing and perfusion readiness",
          caseRole: "case_lead",
          requiredRoleType: "cardiac_surgeon",
          assigneeId: "michael-vallely",
          plannedMinute: 0,
        },
        {
          id: "cardiac-anaesthesia",
          kind: "task",
          label: "Anaesthesia induction and line readiness",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "bridget-prior",
          plannedMinute: 4,
        },
        {
          id: "cardiac-patient-in",
          kind: "event",
          label: "Patient in room",
          caseRole: "circulator",
          requiredRoleType: "nursing",
          assigneeId: "",
          plannedMinute: 8,
        },
        {
          id: "cardiac-incision",
          kind: "task",
          label: "Incision and exposure",
          caseRole: "surgical_operator",
          requiredRoleType: "cardiac_surgeon",
          assigneeId: "michael-vallely",
          plannedMinute: 28,
        },
        {
          id: "cardiac-bypass",
          kind: "event",
          label: "Bypass / valve phase",
          caseRole: "surgical_operator",
          requiredRoleType: "cardiac_surgeon",
          assigneeId: "michael-vallely",
          plannedMinute: 55,
        },
        {
          id: "cardiac-close",
          kind: "task",
          label: "Closure and handover",
          caseRole: "handover",
          requiredRoleType: "cardiac_surgeon",
          assigneeId: "michael-vallely",
          plannedMinute: 120,
        },
      ],
    },
    {
      id: "vascular-endovascular",
      name: "Vascular / endovascular repair",
      defaultLocationId: "muh-ot10",
      defaultProceduralistIds: ["walid-mohabbat", "david-dsilva"],
      expectedRoleTypes: ["vascular_surgeon", "anaesthesia"],
      tasks: [
        {
          id: "vascular-brief",
          kind: "handover",
          label: "Vascular briefing and imaging check",
          caseRole: "case_lead",
          requiredRoleType: "vascular_surgeon",
          assigneeId: "walid-mohabbat",
          plannedMinute: 0,
        },
        {
          id: "vascular-anaesthesia",
          kind: "task",
          label: "Anaesthetic monitoring and access support",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "david-dsilva",
          plannedMinute: 4,
        },
        {
          id: "vascular-patient-in",
          kind: "event",
          label: "Patient in room",
          caseRole: "circulator",
          requiredRoleType: "nursing",
          assigneeId: "",
          plannedMinute: 6,
        },
        {
          id: "vascular-access",
          kind: "task",
          label: "Femoral access and wire position",
          caseRole: "vascular_operator",
          requiredRoleType: "vascular_surgeon",
          assigneeId: "walid-mohabbat",
          plannedMinute: 18,
        },
        {
          id: "vascular-device",
          kind: "event",
          label: "Device deployment",
          caseRole: "vascular_operator",
          requiredRoleType: "vascular_surgeon",
          assigneeId: "walid-mohabbat",
          plannedMinute: 42,
        },
        {
          id: "vascular-closure",
          kind: "task",
          label: "Access closure and recovery handover",
          caseRole: "handover",
          requiredRoleType: "vascular_surgeon",
          assigneeId: "walid-mohabbat",
          plannedMinute: 70,
        },
      ],
    },
  ],
};

export function roleTypeLabel(roleType) {
  return ROLE_TYPE_OPTIONS.find((role) => role.id === roleType)?.label || roleType || "Unspecified";
}

export function caseRoleLabel(caseRole) {
  return CASE_ROLE_OPTIONS.find((role) => role.id === caseRole)?.label || caseRole || "Unspecified";
}

export function taskKindLabel(kind) {
  return TASK_KIND_OPTIONS.find((item) => item.id === kind)?.label || kind || "Task";
}

export function locationsForHospital(hospitalId, database = CASE_SETUP_DATABASE) {
  return database.locations.filter((location) => location.hospitalId === hospitalId);
}

export function hospitalById(hospitalId, database = CASE_SETUP_DATABASE) {
  return database.hospitals.find((hospital) => hospital.id === hospitalId) || null;
}

export function locationById(locationId, database = CASE_SETUP_DATABASE) {
  return database.locations.find((location) => location.id === locationId) || null;
}

export function caseById(caseId, database = CASE_SETUP_DATABASE) {
  return database.cases.find((caseProfile) => caseProfile.id === caseId) || null;
}

export function proceduralistById(proceduralistId, database = CASE_SETUP_DATABASE) {
  return database.proceduralists.find((person) => person.id === proceduralistId) || null;
}

export function defaultCaseSetupState(database = CASE_SETUP_DATABASE) {
  const hospitalId = database.hospitals[0]?.id || "";
  const caseId = database.cases[0]?.id || "";
  const caseProfile = caseById(caseId, database);
  const locationId = caseProfile?.defaultLocationId || locationsForHospital(hospitalId, database)[0]?.id || "";
  return {
    hospitalId,
    locationId,
    caseId,
    proceduralistIds: [...(caseProfile?.defaultProceduralistIds || [])],
    tasks: cloneCaseTasks(caseId, database),
  };
}

export function stateForCase(caseId, previousState = {}, database = CASE_SETUP_DATABASE) {
  const caseProfile = caseById(caseId, database) || database.cases[0];
  const hospitalId = previousState.hospitalId || database.hospitals[0]?.id || "";
  const locationId = caseProfile?.defaultLocationId || locationsForHospital(hospitalId, database)[0]?.id || "";
  return {
    ...previousState,
    hospitalId,
    locationId,
    caseId: caseProfile?.id || "",
    proceduralistIds: [...(caseProfile?.defaultProceduralistIds || [])],
    tasks: cloneCaseTasks(caseProfile?.id, database),
  };
}

export function cloneCaseTasks(caseId, database = CASE_SETUP_DATABASE) {
  const caseProfile = caseById(caseId, database);
  return (caseProfile?.tasks || []).map((task) => ({ ...task }));
}

export function selectedProceduralists(state, database = CASE_SETUP_DATABASE) {
  return (state.proceduralistIds || [])
    .map((id) => proceduralistById(id, database))
    .filter(Boolean);
}

export function updateCaseTask(tasks, taskId, patch) {
  return tasks.map((task) => (
    task.id === taskId
      ? normalizeCaseTask({ ...task, ...patch })
      : task
  ));
}

export function addCaseTask(tasks, partial = {}) {
  return [
    ...tasks,
    normalizeCaseTask({
      id: nextTaskId(tasks),
      kind: "task",
      label: "New task",
      caseRole: "handover",
      requiredRoleType: "",
      assigneeId: "",
      plannedMinute: 0,
      ...partial,
    }),
  ];
}

export function removeCaseTask(tasks, taskId) {
  return tasks.filter((task) => task.id !== taskId);
}

export function normalizeCaseTask(task) {
  const plannedMinute = Number(task.plannedMinute);
  return {
    ...task,
    id: String(task.id || "task"),
    kind: TASK_KIND_OPTIONS.some((item) => item.id === task.kind) ? task.kind : "task",
    label: String(task.label || "Untitled task").trim() || "Untitled task",
    caseRole: CASE_ROLE_OPTIONS.some((role) => role.id === task.caseRole)
      ? task.caseRole
      : "handover",
    requiredRoleType: task.requiredRoleType || "",
    assigneeId: task.assigneeId || "",
    plannedMinute: Number.isFinite(plannedMinute) ? Math.max(0, plannedMinute) : 0,
  };
}

export function assigneeSkillWarning(task, assignee) {
  if (!task?.requiredRoleType || !assignee) return "";
  if (task.requiredRoleType === assignee.roleType) return "";
  return `${assignee.displayName} is ${roleTypeLabel(assignee.roleType)}; task expects ${roleTypeLabel(task.requiredRoleType)}`;
}

export function validateCaseSetup(state, database = CASE_SETUP_DATABASE) {
  const issues = [];
  if (!hospitalById(state.hospitalId, database)) issues.push("Select a hospital");
  if (!locationById(state.locationId, database)) issues.push("Select a location");
  if (!caseById(state.caseId, database)) issues.push("Select a case");
  if (!selectedProceduralists(state, database).length) issues.push("Select at least one proceduralist");
  if (!state.tasks?.length) issues.push("Add at least one case event or task");
  return issues;
}

export function buildActiveCaseProfile(state, database = CASE_SETUP_DATABASE) {
  const caseProfile = caseById(state.caseId, database);
  const hospital = hospitalById(state.hospitalId, database);
  const location = locationById(state.locationId, database);
  const proceduralists = selectedProceduralists(state, database);
  const tasks = [...(state.tasks || [])]
    .map(normalizeCaseTask)
    .sort((a, b) => a.plannedMinute - b.plannedMinute || a.label.localeCompare(b.label));
  return {
    hospital,
    location,
    caseProfile,
    proceduralists,
    tasks,
    title: [
      hospital?.code || hospital?.name,
      location?.name,
      caseProfile?.name,
    ].filter(Boolean).join(" / "),
    proceduralistLabel: proceduralists.map((person) => person.displayName).join(", ") || "No proceduralist selected",
  };
}

function nextTaskId(tasks) {
  const used = new Set(tasks.map((task) => task.id));
  let index = tasks.length + 1;
  let id = `custom-task-${index}`;
  while (used.has(id)) {
    index += 1;
    id = `custom-task-${index}`;
  }
  return id;
}
