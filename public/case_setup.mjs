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
  { id: "preference", label: "Preference" },
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
  preferenceCards: [
    {
      id: "pref-martin-ng-tavr",
      ownerId: "martin-ng",
      caseId: "tavr-structural-heart",
      title: "Martin Ng TAVR preference card",
      summary: "Structural heart table workflow, access readiness, and deployment callouts.",
      timingAnchor: "Patient in room",
      items: [
        {
          id: "martin-tavr-access-side",
          label: "Right-side access tray and ultrasound ready",
          category: "setup",
          plannedMinute: -8,
          timingLabel: "8m before patient in room",
          caseRole: "access_operator",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
        },
        {
          id: "martin-tavr-wire-check",
          label: "Wire, sheath, and valve-size check before access",
          category: "equipment",
          plannedMinute: 10,
          timingLabel: "Before access and sheathing",
          caseRole: "primary_operator",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
        },
        {
          id: "martin-tavr-deploy-callout",
          label: "Deployment pause: imaging, anaesthesia, and table quiet",
          category: "workflow",
          plannedMinute: 26,
          timingLabel: "2m before valve deployment",
          caseRole: "primary_operator",
          requiredRoleType: "interventional_cardiologist",
          assigneeId: "martin-ng",
        },
      ],
    },
    {
      id: "pref-david-dsilva-tavr",
      ownerId: "david-dsilva",
      caseId: "tavr-structural-heart",
      title: "David Dsilva TAVR anaesthetic preference card",
      summary: "Haemodynamic preparation and rapid-pacing communication with timed readiness points.",
      timingAnchor: "Patient in room",
      items: [
        {
          id: "david-tavr-art-line",
          label: "Arterial line, vasoactive infusions, and pacing plan checked",
          category: "anaesthesia",
          plannedMinute: -6,
          timingLabel: "6m before patient in room",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "david-dsilva",
        },
        {
          id: "david-tavr-rapid-pacing",
          label: "Confirm rapid pacing readiness and deployment blood pressure target",
          category: "anaesthesia",
          plannedMinute: 24,
          timingLabel: "4m before valve deployment",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "david-dsilva",
        },
      ],
    },
    {
      id: "pref-bridget-prior-cardiac",
      ownerId: "bridget-prior",
      caseId: "cardiac-surgery",
      title: "Bridget Prior cardiac anaesthetic preference card",
      summary: "Induction, line, TOE, and bypass-readiness timing for cardiac theatre cases.",
      timingAnchor: "Patient in room",
      items: [
        {
          id: "bridget-cardiac-lines",
          label: "Central access, arterial line, and TOE probe readiness",
          category: "anaesthesia",
          plannedMinute: -5,
          timingLabel: "5m before patient in room",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "bridget-prior",
        },
        {
          id: "bridget-cardiac-bypass-ready",
          label: "Bypass readiness communication before valve phase",
          category: "anaesthesia",
          plannedMinute: 48,
          timingLabel: "7m before bypass / valve phase",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "bridget-prior",
        },
      ],
    },
    {
      id: "pref-michael-vallely-cardiac",
      ownerId: "michael-vallely",
      caseId: "cardiac-surgery",
      title: "Michael Vallely cardiac surgery preference card",
      summary: "Surgical exposure, bypass coordination, and closure sequencing.",
      timingAnchor: "Patient in room",
      items: [
        {
          id: "vallely-cardiac-bypass-brief",
          label: "Perfusion and exposure plan confirmed before incision",
          category: "workflow",
          plannedMinute: 18,
          timingLabel: "10m before incision",
          caseRole: "surgical_operator",
          requiredRoleType: "cardiac_surgeon",
          assigneeId: "michael-vallely",
        },
        {
          id: "vallely-cardiac-closure-plan",
          label: "Closure plan and recovery destination confirmed",
          category: "handover",
          plannedMinute: 105,
          timingLabel: "15m before closure handover",
          caseRole: "handover",
          requiredRoleType: "cardiac_surgeon",
          assigneeId: "michael-vallely",
        },
      ],
    },
    {
      id: "pref-walid-mohabbat-vascular",
      ownerId: "walid-mohabbat",
      caseId: "vascular-endovascular",
      title: "Walid Mohabbat vascular preference card",
      summary: "Access, wire, device, and closure preferences for endovascular workflow.",
      timingAnchor: "Patient in room",
      items: [
        {
          id: "walid-vascular-access-kit",
          label: "Access kit, wires, sheaths, and closure device opened",
          category: "equipment",
          plannedMinute: -4,
          timingLabel: "4m before patient in room",
          caseRole: "vascular_operator",
          requiredRoleType: "vascular_surgeon",
          assigneeId: "walid-mohabbat",
        },
        {
          id: "walid-vascular-device-pause",
          label: "Device deployment pause with imaging and anaesthesia confirmation",
          category: "workflow",
          plannedMinute: 38,
          timingLabel: "4m before device deployment",
          caseRole: "vascular_operator",
          requiredRoleType: "vascular_surgeon",
          assigneeId: "walid-mohabbat",
        },
      ],
    },
    {
      id: "pref-david-dsilva-vascular",
      ownerId: "david-dsilva",
      caseId: "vascular-endovascular",
      title: "David Dsilva vascular anaesthetic preference card",
      summary: "Haemodynamic monitoring and contrast/renal-risk coordination for vascular cases.",
      timingAnchor: "Patient in room",
      items: [
        {
          id: "david-vascular-monitoring",
          label: "Renal-risk, anticoagulation, and haemodynamic plan checked",
          category: "anaesthesia",
          plannedMinute: -3,
          timingLabel: "3m before patient in room",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "david-dsilva",
        },
        {
          id: "david-vascular-device-ready",
          label: "Blood pressure target and contrast-volume watch before deployment",
          category: "anaesthesia",
          plannedMinute: 34,
          timingLabel: "8m before device deployment",
          caseRole: "anaesthetist",
          requiredRoleType: "anaesthesia",
          assigneeId: "david-dsilva",
        },
      ],
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

export function preferenceCardById(preferenceCardId, database = CASE_SETUP_DATABASE) {
  return database.preferenceCards.find((card) => card.id === preferenceCardId) || null;
}

export function preferenceCardsForSetup(state, database = CASE_SETUP_DATABASE) {
  const selectedIds = new Set(state.proceduralistIds || []);
  return database.preferenceCards.filter((card) => (
    card.caseId === state.caseId && selectedIds.has(card.ownerId)
  ));
}

export function defaultPreferenceCardIds(state, database = CASE_SETUP_DATABASE) {
  return preferenceCardsForSetup(state, database).map((card) => card.id);
}

export function defaultCaseSetupState(database = CASE_SETUP_DATABASE) {
  const hospitalId = database.hospitals[0]?.id || "";
  const caseId = database.cases[0]?.id || "";
  const caseProfile = caseById(caseId, database);
  const locationId = caseProfile?.defaultLocationId || locationsForHospital(hospitalId, database)[0]?.id || "";
  const initialState = {
    hospitalId,
    locationId,
    caseId,
    proceduralistIds: [...(caseProfile?.defaultProceduralistIds || [])],
  };
  const preferenceCardIds = defaultPreferenceCardIds(initialState, database);
  return {
    hospitalId,
    locationId,
    caseId,
    proceduralistIds: [...(caseProfile?.defaultProceduralistIds || [])],
    preferenceCardIds,
    tasks: applyPreferenceCardsToTasks(
      cloneCaseTasks(caseId, database),
      preferenceCardIds,
      database,
    ),
  };
}

export function stateForCase(caseId, previousState = {}, database = CASE_SETUP_DATABASE) {
  const caseProfile = caseById(caseId, database) || database.cases[0];
  const hospitalId = previousState.hospitalId || database.hospitals[0]?.id || "";
  const locationId = caseProfile?.defaultLocationId || locationsForHospital(hospitalId, database)[0]?.id || "";
  const nextState = {
    ...previousState,
    hospitalId,
    locationId,
    caseId: caseProfile?.id || "",
    proceduralistIds: [...(caseProfile?.defaultProceduralistIds || [])],
  };
  const preferenceCardIds = defaultPreferenceCardIds(nextState, database);
  return {
    ...nextState,
    hospitalId,
    locationId,
    caseId: caseProfile?.id || "",
    proceduralistIds: [...(caseProfile?.defaultProceduralistIds || [])],
    preferenceCardIds,
    tasks: applyPreferenceCardsToTasks(
      cloneCaseTasks(caseProfile?.id, database),
      preferenceCardIds,
      database,
    ),
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

export function applyPreferenceCardsToTasks(
  tasks,
  preferenceCardIds,
  database = CASE_SETUP_DATABASE,
) {
  const selectedIds = new Set(preferenceCardIds || []);
  const existingById = new Map(tasks.map((task) => [task.id, task]));
  const retained = tasks.filter((task) => (
    !task.sourcePreferenceCardId || selectedIds.has(task.sourcePreferenceCardId)
  ));
  const retainedIds = new Set(retained.map((task) => task.id));
  const additions = [];
  selectedIds.forEach((cardId) => {
    const card = preferenceCardById(cardId, database);
    if (!card) return;
    card.items.forEach((item) => {
      const taskId = preferenceTaskId(card, item);
      if (retainedIds.has(taskId)) return;
      const existing = existingById.get(taskId);
      additions.push(normalizeCaseTask(existing || preferenceItemToTask(card, item)));
    });
  });
  return [...retained.map(normalizeCaseTask), ...additions]
    .sort((a, b) => a.plannedMinute - b.plannedMinute || a.label.localeCompare(b.label));
}

export function preferenceItemToTask(card, item) {
  return {
    id: preferenceTaskId(card, item),
    kind: "preference",
    label: item.label,
    caseRole: item.caseRole,
    requiredRoleType: item.requiredRoleType,
    assigneeId: item.assigneeId || card.ownerId,
    plannedMinute: item.plannedMinute,
    timingLabel: item.timingLabel,
    preferenceCategory: item.category,
    sourcePreferenceCardId: card.id,
    sourcePreferenceItemId: item.id,
  };
}

export function preferenceTaskId(card, item) {
  return `pref:${card.id}:${item.id}`;
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
    plannedMinute: Number.isFinite(plannedMinute) ? plannedMinute : 0,
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
  if (!selectedProceduralists(state, database).length) issues.push("Select at least one clinical profile");
  if (!state.tasks?.length) issues.push("Add at least one case event or task");
  return issues;
}

export function buildActiveCaseProfile(state, database = CASE_SETUP_DATABASE) {
  const caseProfile = caseById(state.caseId, database);
  const hospital = hospitalById(state.hospitalId, database);
  const location = locationById(state.locationId, database);
  const proceduralists = selectedProceduralists(state, database);
  const preferenceCards = (state.preferenceCardIds || [])
    .map((id) => preferenceCardById(id, database))
    .filter(Boolean);
  const tasks = [...(state.tasks || [])]
    .map(normalizeCaseTask)
    .sort((a, b) => a.plannedMinute - b.plannedMinute || a.label.localeCompare(b.label));
  return {
    hospital,
    location,
    caseProfile,
    proceduralists,
    preferenceCards,
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
