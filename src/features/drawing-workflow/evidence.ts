const SENSITIVE_KEY = /(?:^|[_-])(?:access[_-]?key|api[_-]?key|authorization|cookie|credential|password|passphrase|private[_-]?key|secret|session|token|url|path)(?:$|[_-])/i;
const SENSITIVE_VALUE = /https?:\/\/|\/(?:Users|home)\/|[A-Z]:\\Users\\|\bBearer\s+\S+/i;

export function sanitizeEvidence(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeEvidence);
  if (typeof value === "string" && SENSITIVE_VALUE.test(value)) return "[REDACTED]";
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !SENSITIVE_KEY.test(key))
      .map(([key, item]) => [key, sanitizeEvidence(item)]),
  );
}

export function assertEvidenceClean(value: unknown): void {
  if (typeof value === "string") {
    if (SENSITIVE_VALUE.test(value)) throw new Error("Evidence QA found sensitive content");
    return;
  }
  if (Array.isArray(value)) {
    value.forEach(assertEvidenceClean);
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (SENSITIVE_KEY.test(key)) throw new Error("Evidence QA found sensitive content");
    assertEvidenceClean(item);
  }
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
