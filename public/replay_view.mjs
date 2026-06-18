export const ROLE_LABELS = {
  table_operator: "Table op",
  access_operator: "Access",
  device_prep: "Device",
  imaging: "Imaging",
  anesthesia: "Anes",
  entry_supply: "Supply",
};

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
    stageCoverage: asArray(tavr.stage_table_coverage),
    stageRosters: asArray(tavr.stage_roster_summary),
    milestones: asArray(tavr.procedure_milestones),
    qualityFlags: asArray(tavr.quality_flags),
    events,
  };
}

export function replayOperatorProjection(payload, demoMeta = {}) {
  const demo = normalizeEvaluationPayload(payload, demoMeta);
  const status = demo.status || {};
  const latestPacket = latestOperatorPacket(demo.packets);
  const stageLabel = status.current_stage_label || latestPacket?.stage_label || demo.caseName;
  const currentTable = currentTableSnapshot(status);
  const effectiveSource = status.effective_table_source;
  const effectiveCount = status.effective_table_count ?? 0;

  return {
    caseName: demo.caseName,
    demoLabel: demo.demoLabel,
    stageMetric: `${stageLabel} (${status.evidence_level || "evaluated"})`,
    trackedStaffMetric: String(demo.team.length || currentTable.count),
    tableSideMetric: String(currentTable.count),
    elapsedMetric: status.clip_end_s === undefined
      ? "n/a"
      : `${Number(status.clip_end_s).toFixed(1)}s`,
    tableRosterItems: currentTable.rows.length
      ? currentTable.rows.slice(0, 5).map((row) => (
        `${currentTable.sourceLabel}: ${rosterPersonLabel(row)} ` +
        `${ROLE_LABELS[row.table_team_role] || row.table_team_role}`
      ))
      : ["None"],
    currentTable: {
      count: currentTable.count,
      source: currentTable.source,
      sourceLabel: currentTable.sourceLabel,
      canonicalIds: asArray(status.current_table_canonical_ids),
    },
    effectiveTable: {
      count: effectiveCount,
      source: effectiveSource,
      sourceLabel: tableSourceLabel(effectiveSource),
      canonicalIds: asArray(status.effective_table_canonical_ids),
      label: `${effectiveCount} staff; ${tableSourceLabel(effectiveSource)}; ` +
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
  };
}

export function eventTimeSeconds(event) {
  return Number(
    event.timestamp_s ??
    event.clip_timestamp_s ??
    event.clip_start_s ??
    event.source_timestamp_s ??
    event.source_start_s ??
    0,
  );
}

export function latestOperatorPacket(packets) {
  return packets.find((packet) => packet.is_current_stage) || packets[packets.length - 1] || null;
}

export function currentTableSnapshot(status = {}) {
  const rows = asArray(status.current_table_roster);
  const source = rows.length ? "current_room_view" : "current_room_view_empty";
  return {
    count: status.current_table_count ?? rows.length,
    rows,
    source,
    sourceLabel: tableSourceLabel(source),
    ageFromClipEndS: 0,
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
    : `Person ${canonicalId}`;
}

export function rosterPersonLabel(row = {}) {
  const person = row.canonical_table_label || formatPersonId(row.canonical_table_id);
  if (person === "none") return `ID ${row.track_id ?? "n/a"}`;
  return row.track_id === null || row.track_id === undefined
    ? person
    : `${person} (ID ${row.track_id})`;
}
