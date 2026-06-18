export class BrowserTableIdentityTracker {
  constructor(options = {}) {
    this.maxGapSeconds = options.maxGapSeconds ?? 2.5;
    this.maxCentroidDistance = options.maxCentroidDistance ?? 0.22;
    this.maxAreaRatio = options.maxAreaRatio ?? 3.0;
    this.identities = new Map();
    this.nextIdentityNumber = 1;
  }

  reset() {
    this.identities = new Map();
    this.nextIdentityNumber = 1;
  }

  update(roster, elapsedSeconds) {
    const rows = roster.map((row, index) => normalizeRosterRow(row, index));
    const assignments = this.assignRows(rows, elapsedSeconds);
    const canonicalRows = [];

    rows.forEach((row, rowIndex) => {
      const identity = assignments.get(rowIndex);
      if (!identity) return;
      mergeIdentity(identity, row, elapsedSeconds);
      canonicalRows.push(canonicalRosterRow(identity, row));
    });

    return canonicalRows;
  }

  groups() {
    return [...this.identities.values()]
      .sort((a, b) => a.identityNumber - b.identityNumber)
      .map((identity) => ({
        id: identity.id,
        role: identity.role,
        rawIds: [...identity.rawIds].sort(),
        frames: identity.frames,
        firstSeen: identity.firstSeen,
        lastSeen: identity.lastSeen,
      }));
  }

  assignRows(rows, elapsedSeconds) {
    const identities = [...this.identities.values()];
    const candidatePairs = [];
    rows.forEach((row, rowIndex) => {
      identities.forEach((identity) => {
        const candidate = scoreCandidate(identity, row, elapsedSeconds, this);
        if (candidate) {
          candidatePairs.push({ rowIndex, identity, cost: candidate.cost });
        }
      });
    });
    candidatePairs.sort((a, b) => (
      a.cost - b.cost ||
      a.identity.identityNumber - b.identity.identityNumber ||
      a.rowIndex - b.rowIndex
    ));

    const assignments = new Map();
    const usedIdentities = new Set();
    candidatePairs.forEach(({ rowIndex, identity }) => {
      if (assignments.has(rowIndex) || usedIdentities.has(identity.id)) return;
      assignments.set(rowIndex, identity);
      usedIdentities.add(identity.id);
    });

    rows.forEach((row, rowIndex) => {
      if (assignments.has(rowIndex)) return;
      const identity = createIdentity(this.nextIdentityNumber, row, elapsedSeconds);
      this.nextIdentityNumber += 1;
      this.identities.set(identity.id, identity);
      assignments.set(rowIndex, identity);
    });

    return assignments;
  }
}

function normalizeRosterRow(row, index) {
  const rawId = String(row.rawId || row.id || `M${index + 1}`);
  const x = Number(row.x ?? 0);
  const y = Number(row.y ?? 0);
  const w = Number(row.w ?? 0);
  const h = Number(row.h ?? 0);
  return {
    ...row,
    rawId,
    role: row.role || "motion",
    x,
    y,
    w,
    h,
    cx: x + w / 2,
    cy: y + h / 2,
    area: Math.max(w * h, 0.0001),
    staticFallback: Boolean(row.staticFallback),
  };
}

function createIdentity(identityNumber, row, elapsedSeconds) {
  return {
    id: `P${identityNumber}`,
    identityNumber,
    role: row.role,
    rawIds: new Set(),
    frames: 0,
    firstSeen: elapsedSeconds,
    lastSeen: elapsedSeconds,
    cx: row.cx,
    cy: row.cy,
    area: row.area,
    vx: null,
    vy: null,
  };
}

function mergeIdentity(identity, row, elapsedSeconds) {
  const timeGap = elapsedSeconds - identity.lastSeen;
  if (timeGap > 0) {
    identity.vx = (row.cx - identity.cx) / timeGap;
    identity.vy = (row.cy - identity.cy) / timeGap;
  } else {
    identity.vx = null;
    identity.vy = null;
  }
  identity.role = row.role;
  identity.rawIds.add(row.rawId);
  identity.frames += 1;
  identity.firstSeen = Math.min(identity.firstSeen, elapsedSeconds);
  identity.lastSeen = Math.max(identity.lastSeen, elapsedSeconds);
  identity.cx = row.cx;
  identity.cy = row.cy;
  identity.area = row.area;
}

function canonicalRosterRow(identity, row) {
  return {
    ...row,
    id: identity.id,
    canonicalId: identity.id,
    rawId: row.rawId,
    rawIds: [...identity.rawIds].sort(),
  };
}

function scoreCandidate(identity, row, elapsedSeconds, options) {
  const timeGap = elapsedSeconds - identity.lastSeen;
  if (timeGap < 0 || timeGap > options.maxGapSeconds) return null;
  if (!rolesCompatible(identity.role, row.role)) return null;

  const centroidDistance = Math.hypot(identity.cx - row.cx, identity.cy - row.cy);
  if (centroidDistance > options.maxCentroidDistance) return null;

  const areaRatio = Math.max(identity.area, row.area) / Math.max(
    Math.min(identity.area, row.area),
    0.0001,
  );
  if (areaRatio > options.maxAreaRatio) return null;

  const projectedDistance = projectedCentroidDistance(identity, row, timeGap);
  const assignmentDistance = projectedDistance === null
    ? centroidDistance
    : projectedDistance + 2.0 * centroidDistance;
  const rawIdBonus = identity.rawIds.has(row.rawId) ? -0.05 : 0;
  return {
    cost: assignmentDistance + Math.max(timeGap, 0) * 0.01 + rawIdBonus,
  };
}

function projectedCentroidDistance(identity, row, timeGap) {
  if (identity.vx === null || identity.vy === null || timeGap <= 0) {
    return null;
  }
  const predictedCx = identity.cx + identity.vx * timeGap;
  const predictedCy = identity.cy + identity.vy * timeGap;
  return Math.hypot(predictedCx - row.cx, predictedCy - row.cy);
}

function rolesCompatible(firstRole, secondRole) {
  if (firstRole === secondRole) return true;
  const tableRoles = new Set(["access_operator", "table_operator"]);
  return tableRoles.has(firstRole) && tableRoles.has(secondRole);
}
