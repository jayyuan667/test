export function sanitizeEvidence(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeEvidence);
  if (typeof value === "string" && (/https?:\/\//i.test(value) || /\/(?:Users|home)\//.test(value))) return "[REDACTED]";
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !/token|authorization|url|path/i.test(key))
      .map(([key, item]) => [key, sanitizeEvidence(item)]),
  );
}

export function assertEvidenceClean(value: unknown): void {
  const wire = JSON.stringify(value);
  if (/token|authorization|https?:\/\/|\/(?:Users|home)\//i.test(wire)) throw new Error("Evidence QA found sensitive content");
}

export function sanitizeEvent(event: Record<string, unknown>): unknown {
  return {
    seq: event.seq,
    type: event.type,
    phase: event.phase,
    progress: event.progress,
    timestamp: event.timestamp,
    payload: sanitizeEvidence(event.payload),
  };
}
