import assert from "node:assert/strict";
import test from "node:test";

import { assertEvidenceClean, sanitizeEvidence } from "./evidence.ts";

test("recursively removes secret keys and redacts sensitive string values", () => {
  const clean = sanitizeEvidence({
    task: { id: "task-1", Authorization: "Bearer secret", nested: [{ token: "secret" }] },
    notes: ["safe", "https://private.example/asset", "/Users/alice/private/file.png", "/home/alice/private/file.png"],
  });
  const wire = JSON.stringify(clean);
  assert.deepEqual(clean, { task: { id: "task-1", nested: [{}] }, notes: ["safe", "[REDACTED]", "[REDACTED]", "[REDACTED]"] });
  assert.doesNotMatch(wire, /token|authorization|https?:\/\/|\/(?:Users|home)\//i);
  assert.doesNotThrow(() => assertEvidenceClean(clean));
  assert.throws(() => assertEvidenceClean({ value: "https://private.example" }), /Evidence QA/);
});
