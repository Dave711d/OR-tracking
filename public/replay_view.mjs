export const ROLE_LABELS = {
  table_operator: "Table op",
  access_operator: "Access",
  device_prep: "Device",
  imaging: "Imaging",
  anesthesia: "Anes",
  entry_supply: "Supply",
};

export const TAVR_STAGE_PROGRESS = [
  { key: "room_prep_drape", label: "Room prep / drape" },
  { key: "access_sheathing", label: "Access / sheathing" },
  { key: "angio_alignment_crossing", label: "Angio alignment / crossing" },
  { key: "bav_optional", label: "Balloon valvuloplasty" },
  { key: "valve_delivery_positioning", label: "Valve delivery / positioning" },
  { key: "valve_deployment", label: "Valve deployment" },
  { key: "post_deploy_assessment", label: "Post-deploy assessment" },
  { key: "closure_finish", label: "Closure / finish" },
];

const TAVR_STAGE_PROGRESS_LOOKUP = new Map(
  TAVR_STAGE_PROGRESS.map((stage, index) => [stage.key, { ...stage, index }]),
);

const CORE_STAGE_CONTACT_MIN_SECONDS = 0.4;
const CORE_STAGE_CONTACT_MIN_FRAMES = 12;
const MAX_STAGE_ROSTER_BRIEF_PEOPLE = 3;
const SCORE_VERIFICATION_GROUPS = [
  {
    label: "Stage verification",
    checks: [
      ["stage_score", "stage"],
      ["stage_evidence_score", "evidence"],
      ["procedure_status_score", "status"],
    ],
  },
  {
    label: "Table person verification",
    checks: [
      ["table_person_interval_score", "intervals"],
      ["table_person_status_score", "status"],
    ],
  },
  {
    label: "Operator snapshot",
    checks: [["operator_snapshot_score", "snapshot"]],
  },
];

export function normalizeEvaluationPayload(payload, demoMeta = {}) {
  const tavr = payload.tavr || {};
  const events = [
    ...asArray(tavr.procedure_event_timeline).map((event) => ({
      ...event,
      source_table: event.source || "procedure_event_timeline",
    })),
    ...asArray(tavr.table_transition_events).map((event) => ({
      ...event,
      source_table: "table_transition_events",
    })),
  ].sort((a, b) => (
    eventTimeSeconds(a) - eventTimeSeconds(b) ||
    String(a.event_type || "").localeCompare(String(b.event_type || ""))
  ));

  return {
    caseName: payload.case || "evaluated_tavr_case",
    demoLabel: demoMeta.label || String(payload.case || "evaluated TAVR case").replaceAll("_", " "),
    scoreSummary: payload.score_summary || {},
    timebase: payload.timebase || asArray(tavr.timebase_summary)[0] || null,
    status: asArray(tavr.procedure_status_summary)[0] || null,
    statusSnapshots: asArray(tavr.operator_status_snapshots),
    packets: asArray(tavr.operator_stage_packet),
    team: asArray(tavr.table_team_summary),
    identities: asArray(tavr.table_identity_groups),
    presenceIntervals: asArray(tavr.table_presence_intervals),
    stageCoverage: asArray(tavr.stage_table_coverage),
    stageRosters: asArray(tavr.stage_roster_summary),
    milestones: asArray(tavr.procedure_milestones),
    qualityFlags: asArray(tavr.quality_flags),
    events,
  };
}

export function replayOperatorProjection(payload, demoMeta = {}, snapshotIndex = null) {
  const demo = normalizeEvaluationPayload(payload, demoMeta);
  const status = snapshotIndex === null || snapshotIndex === undefined
    ? (demo.status || {})
    : (replaySnapshotAt(demo, snapshotIndex) || demo.status || {});
  const latestPacket = packetForStatus(demo.packets, status);
  const stageLabel = status.current_stage_label || latestPacket?.stage_label || demo.caseName;
  const currentTable = currentTableSnapshot(status);
  const effectiveTable = effectiveTableSnapshot(status);
  const effectiveSource = effectiveTable.source;
  const effectiveCount = effectiveTable.count;
  const selectedStageRoster = stageRosterForStatus(demo.stageRosters, status, latestPacket);
  const tableBriefRows = stageTableBriefRows(
    status,
    latestPacket,
    demo.milestones,
    selectedStageRoster,
  );

  return {
    caseName: demo.caseName,
    demoLabel: demo.demoLabel,
    stageMetric: `${stageLabel} (${status.evidence_level || "evaluated"})`,
    trackedStaffMetric: String(demo.team.length || currentTable.count),
    tableSideMetric: String(currentTable.count),
    elapsedMetric: status.clip_end_s === undefined
      ? "n/a"
      : `${Number(status.clip_end_s).toFixed(1)}s`,
    stageTableBriefRows: tableBriefRows,
    tablePresenceRows: [
      {
        label: "Current room view",
        value: tableSnapshotSummary(currentTable, "at table"),
        context: currentTable.count ? "current" : "empty",
      },
      {
        label: "Stage table context",
        value: tableSnapshotSummary(effectiveTable, "effective"),
        context: effectiveTable.count ? "effective" : "empty",
      },
    ],
    tableRosterItems: currentTable.rows.length
      ? currentTable.rows.slice(0, 5).map((row) => (
        `${currentTable.sourceLabel}: ${rosterPersonLabel(row)} ` +
        `${ROLE_LABELS[row.table_team_role] || row.table_team_role}`
      ))
      : ["None"],
    effectiveTableRosterItems: effectiveTable.rows.length
      ? effectiveTable.rows.slice(0, 5).map((row) => (
        `${effectiveTable.sourceLabel}: ${rosterPersonLabel(row)} ` +
        `${ROLE_LABELS[row.table_team_role] || row.table_team_role}`
      ))
      : [],
    currentTable: {
      count: currentTable.count,
      source: currentTable.source,
      sourceLabel: currentTable.sourceLabel,
      canonicalIds: asArray(status.current_table_canonical_ids),
    },
    effectiveTable: {
      count: effectiveCount,
      source: effectiveSource,
      sourceLabel: effectiveTable.sourceLabel,
      canonicalIds: effectiveTable.canonicalIds,
      label: `${effectiveCount} staff; ${effectiveTable.sourceLabel}; ` +
        `${formatPersonIds(status.effective_table_canonical_ids)}`,
    },
    operatorPacketEffective: latestPacket ? {
      count: latestPacket.effective_table_count ?? effectiveCount,
      source: latestPacket.effective_table_source || effectiveSource,
      sourceLabel: tableSourceLabel(latestPacket.effective_table_source || effectiveSource),
      canonicalIds: asArray(
        latestPacket.effective_table_canonical_ids ||
        status.effective_table_canonical_ids,
      ),
    } : null,
    scoreVerificationRows: scoreVerificationRows(demo.scoreSummary, status),
  };
}

export function scoreVerificationRows(scoreSummary = {}, status = {}) {
  const rows = SCORE_VERIFICATION_GROUPS.flatMap((group) => {
    const parts = group.checks.flatMap(([key, label]) => {
      const score = numericScore(scoreSummary[key]);
      return score === null ? [] : [{ label, score }];
    });
    if (!parts.length) return [];
    return [{
      label: group.label,
      value: parts.map((part) => `${part.label} ${formatVerificationScore(part.score)}`).join("; "),
      tone: parts.every((part) => part.score >= 1) ? "current" : "warn",
    }];
  });

  const tablePersonScored = [
    scoreSummary.table_person_interval_score,
    scoreSummary.table_person_status_score,
  ].some((score) => numericScore(score) !== null);
  if (tablePersonScored && noTableStatusVerified(status)) {
    rows.push({
      label: "No-table verification",
      value: "0 current/effective/last/peak staff",
      tone: "current",
    });
  }

  return rows;
}

export function stageTableBriefRows(
  status = {},
  packet = null,
  milestones = [],
  stageRoster = null,
) {
  const stageLabel = status.current_stage_label || packet?.stage_label || "Stage n/a";
  const evidence = status.current_stage_evidence_status || status.evidence_level ||
    packet?.stage_evidence_status || packet?.evidence_level || "evidence n/a";
  const time = statusTimeSeconds(status);
  return stageTableBriefRowsFromSnapshots({
    stageLabel,
    evidenceLabel: String(evidence).replaceAll("_", " "),
    timeLabel: Number.isFinite(time) ? `clip ${formatSeconds(time)}` : "",
    progress: procedureProgressBrief(status, packet, milestones),
    stageRoster,
    currentTable: currentTableSnapshot(status),
    effectiveTable: effectiveTableSnapshot(status),
    handoff: packet ? {
      handoffType: packet.handoff_type,
      activeIds: packet.active_table_canonical_ids,
      continuedIds: packet.continued_canonical_table_ids,
      newIds: packet.new_canonical_table_ids,
      droppedIds: packet.dropped_canonical_table_ids,
    } : null,
  });
}

export function stageTableBriefRowsFromSnapshots({
  stageLabel = "Stage n/a",
  evidenceLabel = "",
  timeLabel = "",
  progress = null,
  stageRoster = null,
  currentTable = {},
  effectiveTable = null,
  handoff = null,
} = {}) {
  const current = normalizedTableSnapshot(currentTable);
  const effective = normalizedTableSnapshot(effectiveTable || current);
  const rows = [
    {
      kind: "stage",
      label: "Stage",
      value: stageLabel,
      detail: [evidenceLabel, timeLabel].filter(Boolean).join("; "),
      context: "current",
    },
    ...stageTableBriefProgressRows(progress),
    ...stageTableBriefHandoffRows(handoff),
    ...stageRosterBriefRows(stageRoster),
    {
      kind: "current",
      label: "Now visible",
      value: `${current.count} at table`,
      detail: tableSnapshotDetail(current),
      context: current.count ? "current" : "empty",
    },
    {
      kind: "effective",
      label: "Effective for stage",
      value: `${effective.count} effective`,
      detail: tableSnapshotDetail(effective),
      context: effective.count ? "effective" : "empty",
    },
  ];
  return rows.concat(stageTableBriefPersonRows(current, effective));
}

export function procedureProgressBrief(status = {}, packet = null, milestones = []) {
  const stageKey = status.current_stage || packet?.stage;
  const current = TAVR_STAGE_PROGRESS_LOOKUP.get(stageKey);
  if (!current) return null;

  const nextKey = status.next_stage || TAVR_STAGE_PROGRESS[current.index + 1]?.key;
  const next = nextKey ? TAVR_STAGE_PROGRESS_LOOKUP.get(nextKey) : null;
  const milestoneRows = asArray(milestones);
  const observedCount = milestoneRows.length
    ? milestoneRows.filter((row) => milestoneObserved(row)).length
    : current.index + 1;
  return {
    stageIndex: current.index,
    totalStages: TAVR_STAGE_PROGRESS.length,
    nextLabel: next?.label || "complete",
    observedCount,
    observedTotal: milestoneRows.length || TAVR_STAGE_PROGRESS.length,
  };
}

export function stageTableBriefProgressRows(progress = null) {
  if (!progress) return [];
  const stageIndex = Number(progress.stageIndex);
  const totalStages = Number(progress.totalStages || TAVR_STAGE_PROGRESS.length);
  const ordinal = Number.isFinite(stageIndex) ? stageIndex + 1 : null;
  const value = progress.value || (
    ordinal === null ? "stage n/a" : `${ordinal}/${totalStages} stages`
  );
  const observedCount = progress.observedCount;
  const observedTotal = progress.observedTotal || totalStages;
  const observedDetail = observedCount === null || observedCount === undefined
    ? ""
    : `observed ${observedCount}/${observedTotal}`;
  return [{
    kind: "progress",
    label: "Procedure progress",
    value,
    detail: [
      `next ${progress.nextLabel || "unknown"}`,
      observedDetail,
    ].filter(Boolean).join("; "),
    context: "current",
  }];
}

export function stageRosterForStatus(stageRosters = [], status = {}, packet = null) {
  const rows = asArray(stageRosters);
  if (!rows.length) return null;
  const packetSegment = packet?.stage_segment_index;
  if (packetSegment !== null && packetSegment !== undefined) {
    const match = rows.find((row) => Number(row.stage_segment_index) === Number(packetSegment));
    if (match) return match;
  }

  const stage = status.current_stage || packet?.stage;
  const time = statusTimeSeconds(status);
  const inTime = (row) => {
    const start = row.clip_start_s ?? row.start_s;
    const end = row.clip_end_s ?? row.end_s;
    if (start === null || start === undefined || end === null || end === undefined) {
      return false;
    }
    return time >= Number(start) - 0.12 && time <= Number(end) + 0.12;
  };
  if (stage) {
    return (
      rows.find((row) => row.stage === stage && inTime(row)) ||
      rows.find((row) => row.stage === stage) ||
      rows[rows.length - 1]
    );
  }
  return rows.find(inTime) || rows[rows.length - 1];
}

export function stageRosterBriefRows(stageRoster = null) {
  if (!stageRoster) return [];
  const roster = asArray(stageRoster.active_table_roster);
  const activeCount = Number(
    stageRoster.canonical_table_identity_count ??
    stageRoster.active_table_track_count ??
    roster.length,
  ) || 0;
  const coreRoster = roster.filter((row) => stageRosterContactIsCore(row));
  const coreCount = coreRoster.length;
  const briefCount = Math.max(0, roster.length - coreCount);
  const peakCount = Number(stageRoster.peak_table_count ?? 0) || 0;
  const trackingRate = stageRoster.tracking_available_rate;
  const lead = coreRoster[0] || roster[0] || null;
  const stageRows = [{
    kind: "stage_roster",
    label: "Stage roster",
    value: `${activeCount} tracked; ${coreCount} core`,
    detail: [
      `peak ${peakCount}`,
      Number.isFinite(Number(trackingRate))
        ? `tracking ${formatPercent(Number(trackingRate))}`
        : "",
      lead ? `lead ${formatRosterPersonLabel(lead)}` : "",
      briefCount ? `${briefCount} brief contacts` : "",
    ].filter(Boolean).join("; "),
    context: activeCount ? "handoff" : "empty",
  }];

  const contactRows = (coreRoster.length ? coreRoster : roster)
    .slice(0, MAX_STAGE_ROSTER_BRIEF_PEOPLE)
    .map(stageRosterPersonBriefRow);
  return stageRows.concat(contactRows);
}

export function stageTableBriefHandoffRows(handoff = null) {
  if (!handoff) return [];
  const handoffType = handoff.handoffType || handoff.handoff_type || "unknown";
  const activeIds = asArray(handoff.activeIds ?? handoff.active_table_canonical_ids);
  const continuedIds = asArray(
    handoff.continuedIds ?? handoff.continued_canonical_table_ids,
  );
  const newIds = asArray(handoff.newIds ?? handoff.new_canonical_table_ids);
  const droppedIds = asArray(handoff.droppedIds ?? handoff.dropped_canonical_table_ids);
  const withinStageEntryIds = asArray(
    handoff.withinStageEntryIds ??
    handoff.within_stage_entry_canonical_table_ids,
  );
  const withinStageExitIds = asArray(
    handoff.withinStageExitIds ??
    handoff.within_stage_exit_canonical_table_ids,
  );
  const hasAnyPeople = activeIds.length || continuedIds.length ||
    newIds.length || droppedIds.length ||
    withinStageEntryIds.length || withinStageExitIds.length;
  return [{
    kind: "handoff",
    label: "Stage handoff",
    value: handoffLabel(handoffType),
    detail: [
      formatBriefPersonIds(continuedIds, "continued"),
      formatBriefPersonIds(newIds, "new"),
      formatBriefPersonIds(droppedIds, "dropped"),
      formatBriefPersonIds(withinStageEntryIds, "entered"),
      formatBriefPersonIds(withinStageExitIds, "exited"),
    ].join("; "),
    context: hasAnyPeople ? "handoff" : "empty",
  }];
}

export function focusedReplayEvents(events = [], status = {}, maxVisible = 12) {
  const rows = asArray(events);
  if (!rows.length) {
    return { rows: [], hiddenBefore: 0, hiddenAfter: 0, focused: false };
  }

  const stage = status.current_stage || status.stage;
  const time = statusTimeSeconds(status);
  const candidates = stage
    ? rows.filter((event) => event.stage === stage)
    : rows;
  const scopedRows = candidates.length ? candidates : rows;
  const ranked = scopedRows
    .map((event, index) => ({
      event,
      index,
      time: eventTimeSeconds(event),
      priority: replayEventPriority(event),
    }))
    .sort((a, b) => (
      a.priority - b.priority ||
      Math.abs(a.time - time) - Math.abs(b.time - time) ||
      a.time - b.time ||
      a.index - b.index
    ));
  const selected = ranked
    .slice(0, Math.max(1, Number(maxVisible) || 12))
    .sort((a, b) => a.time - b.time || a.index - b.index);
  const selectedIndexes = new Set(selected.map((item) => item.index));
  const hiddenBefore = scopedRows.filter((event, index) => (
    !selectedIndexes.has(index) && eventTimeSeconds(event) < time
  )).length;
  const hiddenAfter = scopedRows.filter((event, index) => (
    !selectedIndexes.has(index) && eventTimeSeconds(event) >= time
  )).length;

  return {
    rows: selected.map((item) => item.event),
    hiddenBefore,
    hiddenAfter,
    focused: Boolean(stage || Number.isFinite(time)),
  };
}

export function eventTimeSeconds(event) {
  return Number(
    event.clip_timestamp_s ??
    event.clip_start_s ??
    event.timestamp_s ??
    event.source_timestamp_s ??
    event.source_start_s ??
    0,
  );
}

export function statusTimeSeconds(status = {}) {
  return Number(
    status.clip_timestamp_s ??
    status.clip_end_s ??
    status.clip_start_s ??
    status.timestamp_s ??
    status.source_timestamp_s ??
    status.source_end_s ??
    status.source_start_s ??
    0,
  );
}

function replayEventPriority(event = {}) {
  if (event.event_type === "stage_started") return 0;
  if (event.event_type === "table_handoff") return 1;
  return 2;
}

export function latestOperatorPacket(packets) {
  const rows = asArray(packets);
  return rows.find((packet) => packet.is_current_stage) || rows[rows.length - 1] || null;
}

export function packetForStatus(packets, status = {}) {
  const rows = asArray(packets);
  if (!rows.length) return null;
  const stage = status.current_stage;
  const time = statusTimeSeconds(status);
  const inTime = (packet) => {
    const start = packet.clip_start_s ?? packet.start_s ?? packet.timestamp_s;
    const end = packet.clip_end_s ?? packet.end_s ?? packet.timestamp_s;
    if (start === null || start === undefined || end === null || end === undefined) {
      return false;
    }
    return time >= Number(start) - 0.12 && time <= Number(end) + 0.12;
  };
  if (stage) {
    return (
      rows.find((packet) => packet.stage === stage && inTime(packet)) ||
      rows.find((packet) => packet.stage === stage) ||
      latestOperatorPacket(rows)
    );
  }
  return rows.find(inTime) || latestOperatorPacket(rows);
}

export function replaySnapshotAt(demo, index = null) {
  const snapshots = asArray(demo?.statusSnapshots);
  if (!snapshots.length) return demo?.status || null;
  if (index === null || index === undefined) return snapshots[snapshots.length - 1];
  const numeric = Number(index);
  const clamped = Number.isFinite(numeric)
    ? Math.min(Math.max(Math.round(numeric), 0), snapshots.length - 1)
    : snapshots.length - 1;
  return snapshots[clamped];
}

export function replaySnapshotIndexForTime(demo, clipSeconds) {
  const snapshots = asArray(demo?.statusSnapshots);
  if (!snapshots.length) return 0;
  const target = Number(clipSeconds);
  if (!Number.isFinite(target)) return snapshots.length - 1;
  let selected = 0;
  snapshots.forEach((snapshot, index) => {
    if (eventTimeSeconds(snapshot) <= target + 0.0001) {
      selected = index;
    }
  });
  return selected;
}

export function replaySnapshotLabel(snapshot = {}, index = 0, total = 0) {
  const stage = snapshot.current_stage_label || snapshot.stage_label || "stage n/a";
  const reason = asArray(snapshot.snapshot_reason).join(", ") || "status";
  const prefix = total > 0 ? `${Number(index) + 1}/${total}` : `${Number(index) + 1}`;
  return `${prefix} - clip ${formatSeconds(eventTimeSeconds(snapshot))} - ${stage} (${reason})`;
}

export function currentTableSnapshot(status = {}) {
  const rows = asArray(status.current_table_roster);
  const source = rows.length ? "current_room_view" : "current_room_view_empty";
  return {
    count: status.current_table_count ?? rows.length,
    rows,
    source,
    sourceLabel: tableSourceLabel(source),
    canonicalIds: asArray(status.current_table_canonical_ids),
    ageFromClipEndS: 0,
  };
}

export function effectiveTableSnapshot(status = {}) {
  const rows = asArray(status.effective_table_roster);
  const source = status.effective_table_source || (
    rows.length ? "last_observed_room_view" : "no_room_table_evidence"
  );
  return {
    count: status.effective_table_count ?? rows.length,
    rows,
    source,
    sourceLabel: tableSourceLabel(source),
    canonicalIds: asArray(status.effective_table_canonical_ids),
    ageFromClipEndS: status.effective_table_age_from_clip_end_s ?? null,
  };
}

export function tableSourceLabel(source) {
  if (!source) return "source n/a";
  const labels = {
    current_room_view: "current room view",
    current_room_view_empty: "current room view empty",
    current_stage_recent_room_window: "current-stage recent room window",
    recent_room_view_hold: "recent room-view hold",
    last_observed_room_view: "last observed room view",
    no_room_table_evidence: "no room table evidence",
  };
  return labels[source] || String(source).replaceAll("_", " ");
}

export function tableSnapshotSummary(snapshot = {}, countLabel = "staff") {
  const normalized = normalizedTableSnapshot(snapshot);
  return `${normalized.count} ${countLabel}; ${tableSnapshotDetail(normalized)}`;
}

export function tableSnapshotPeople(snapshot = {}) {
  const canonicalIds = asArray(snapshot.canonicalIds);
  if (canonicalIds.length) return formatPersonIds(canonicalIds);
  const rows = asArray(snapshot.rows);
  if (!rows.length) return "people none";
  const visible = rows.slice(0, 4).map(snapshotRowPersonLabel);
  const overflow = rows.length > visible.length ? ` +${rows.length - visible.length}` : "";
  return `people ${visible.join(", ")}${overflow}`;
}

export function asArray(value) {
  return Array.isArray(value) ? value : [];
}

export function formatPersonIds(canonicalIds, prefix = "people") {
  const values = asArray(canonicalIds);
  return values.length
    ? `${prefix} ${values.map(formatPersonId).join(", ")}`
    : `${prefix} none`;
}

export function formatPersonId(canonicalId) {
  return canonicalId === null || canonicalId === undefined
    ? "none"
    : (isBrowserPersonId(canonicalId) ? String(canonicalId)
      : `Person ${canonicalId}`);
}

export function rosterPersonLabel(row = {}) {
  const person = row.canonical_table_label || formatPersonId(row.canonical_table_id);
  if (person === "none") return `ID ${row.track_id ?? "n/a"}`;
  return row.track_id === null || row.track_id === undefined
    ? person
    : `${person} (ID ${row.track_id})`;
}

function snapshotRowPersonLabel(row = {}) {
  if (
    row.canonical_table_label ||
    (row.canonical_table_id !== null && row.canonical_table_id !== undefined) ||
    (row.track_id !== null && row.track_id !== undefined)
  ) {
    return rosterPersonLabel(row);
  }
  return row.id || row.rawId || "person";
}

function normalizedTableSnapshot(snapshot = {}) {
  const rows = asArray(snapshot.rows);
  return {
    ...snapshot,
    rows,
    count: snapshot.count ?? rows.length,
    sourceLabel: snapshot.sourceLabel || tableSourceLabel(snapshot.source),
    canonicalIds: asArray(snapshot.canonicalIds),
  };
}

function tableSnapshotDetail(snapshot = {}) {
  const normalized = normalizedTableSnapshot(snapshot);
  return `${normalized.sourceLabel}; ${tableSnapshotPeople(normalized)}${tableSnapshotAgeSuffix(normalized)}`;
}

function tableSnapshotSourceDetail(snapshot = {}) {
  const normalized = normalizedTableSnapshot(snapshot);
  return `${normalized.sourceLabel}${tableSnapshotAgeSuffix(normalized)}`;
}

function tableSnapshotAgeSuffix(snapshot = {}) {
  const age = snapshot.ageFromClipEndS ?? snapshot.ageSeconds;
  return age === null || age === undefined ? "" : `; age ${formatSeconds(age)}`;
}

function stageRosterPersonBriefRow(row = {}) {
  const core = stageRosterContactIsCore(row);
  const frames = Number(row.observed_table_frames ?? 0) || 0;
  const roomCoverage = Number(row.room_coverage_ratio ?? row.coverage_ratio);
  const mergedIds = asArray(row.merged_track_ids);
  return {
    kind: "stage_roster_person",
    label: `Stage ${formatRosterPersonLabel(row)}`,
    value: [
      core ? "core" : "brief",
      tableBriefRoleLabel(row),
      `${frames}f`,
    ].filter(Boolean).join("; "),
    detail: [
      stageRosterClipRange(row),
      Number.isFinite(roomCoverage) ? `room ${formatPercent(roomCoverage)}` : "",
      mergedIds.length > 1 ? `raw ${mergedIds.join(", ")}` : "",
    ].filter(Boolean).join("; "),
    context: core ? "handoff" : "empty",
  };
}

function stageRosterContactIsCore(row = {}) {
  const frames = Number(row.observed_table_frames ?? 0) || 0;
  const start = Number(row.first_seen_clip_s);
  const end = Number(row.last_seen_clip_s);
  const dwellSeconds = Number.isFinite(start) && Number.isFinite(end)
    ? Math.max(0, end - start)
    : 0;
  return (
    frames >= CORE_STAGE_CONTACT_MIN_FRAMES ||
    dwellSeconds >= CORE_STAGE_CONTACT_MIN_SECONDS
  );
}

function stageRosterClipRange(row = {}) {
  const start = Number(row.first_seen_clip_s ?? row.first_seen_s);
  const end = Number(row.last_seen_clip_s ?? row.last_seen_s);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "";
  if (Math.abs(end - start) < 0.05) return formatSeconds(start);
  return `${formatSeconds(start)}-${formatSeconds(end)}`;
}

function formatRosterPersonLabel(row = {}) {
  return rosterPersonLabel(row);
}

function stageTableBriefPersonRows(current, effective) {
  const people = new Map();
  addBriefPeople(people, current, "current");
  addBriefPeople(people, effective, "effective");
  const rows = [...people.values()];
  const visibleRows = rows.slice(0, 5).map((person) => {
    const state = person.inCurrent && person.inEffective
      ? "now + effective"
      : (person.inCurrent ? "now" : "held");
    const source = person.inCurrent ? current : effective;
    return {
      kind: "person",
      label: person.label,
      value: `${state}; ${person.roleLabel}`,
      detail: tableSnapshotSourceDetail(source),
      context: person.inCurrent ? "current" : "effective",
    };
  });
  if (rows.length > visibleRows.length) {
    visibleRows.push({
      kind: "overflow",
      label: "More people",
      value: `+${rows.length - visibleRows.length}`,
      detail: "additional effective table people",
      context: "effective",
    });
  }
  return visibleRows;
}

function addBriefPeople(people, snapshot, source) {
  const normalized = normalizedTableSnapshot(snapshot);
  normalized.rows.forEach((row) => {
    const key = snapshotRowKey(row);
    const existing = people.get(key) || {
      label: snapshotRowPersonLabel(row),
      roleLabel: tableBriefRoleLabel(row),
      inCurrent: false,
      inEffective: false,
    };
    if (source === "current") existing.inCurrent = true;
    if (source === "effective") existing.inEffective = true;
    people.set(key, existing);
  });
}

function snapshotRowKey(row = {}) {
  if (row.canonical_table_id !== null && row.canonical_table_id !== undefined) {
    return `canonical:${row.canonical_table_id}`;
  }
  if (row.id !== null && row.id !== undefined) return `id:${row.id}`;
  if (row.track_id !== null && row.track_id !== undefined) return `track:${row.track_id}`;
  if (row.rawId !== null && row.rawId !== undefined) return `raw:${row.rawId}`;
  return JSON.stringify(row);
}

function tableBriefRoleLabel(row = {}) {
  const role = row.table_team_role || row.role;
  return ROLE_LABELS[role] || role || "role n/a";
}

function milestoneObserved(row = {}) {
  if (row.observed_in_clip !== null && row.observed_in_clip !== undefined) {
    return Boolean(row.observed_in_clip);
  }
  return !["not_observed_in_clip", "not_observed"].includes(
    String(row.milestone_status || ""),
  );
}

function formatBriefPersonIds(ids, prefix) {
  const values = asArray(ids);
  return values.length
    ? `${prefix} ${values.map(formatBriefPersonId).join(", ")}`
    : `${prefix} none`;
}

function formatBriefPersonId(id) {
  return isBrowserPersonId(id) ? String(id) : formatPersonId(id);
}

function isBrowserPersonId(id) {
  return typeof id === "string" && /^P\d+$/i.test(id);
}

function numericScore(value) {
  const score = Number(value);
  return Number.isFinite(score) ? score : null;
}

function formatVerificationScore(score) {
  return `${Math.round(score * 100)}%`;
}

function noTableStatusVerified(status = {}) {
  const snapshots = [
    tableStatusCount(
      status,
      "current_table_count",
      "current_table_canonical_ids",
      "current_table_roster",
    ),
    tableStatusCount(
      status,
      "effective_table_count",
      "effective_table_canonical_ids",
      "effective_table_roster",
    ),
    tableStatusCount(
      status,
      "last_observed_table_count",
      "last_observed_table_canonical_ids",
      "last_observed_table_roster",
    ),
    tableStatusCount(
      status,
      "peak_table_count",
      "peak_table_canonical_ids",
      "peak_table_roster",
    ),
  ];
  return snapshots.some((count) => count !== null) && snapshots.every((count) => count === 0);
}

function tableStatusCount(status = {}, countField, idsField, rosterField) {
  const ids = asArray(status[idsField]);
  const roster = asArray(status[rosterField]);
  const rawCount = status[countField];
  if (rawCount === null && ids.length === 0 && roster.length === 0) return null;
  if (rawCount === undefined && ids.length === 0 && roster.length === 0) return null;
  const numeric = Number(rawCount);
  if (Number.isFinite(numeric)) return Math.max(0, numeric, ids.length, roster.length);
  return Math.max(ids.length, roster.length);
}

function handoffLabel(handoffType) {
  return String(handoffType || "unknown").replaceAll("_", " ");
}

function formatSeconds(value) {
  return value === null || value === undefined ? "n/a" : `${Number(value).toFixed(1)}s`;
}

function formatPercent(value) {
  return `${Math.round(Number(value) * 100)}%`;
}
