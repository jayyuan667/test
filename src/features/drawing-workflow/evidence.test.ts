import assert from "node:assert/strict";
import test from "node:test";

import { assertEvidenceClean, sanitizeEvidence } from "./evidence.ts";

test("recursively removes secret keys and redacts sensitive string values", () => {
  const clean = sanitizeEvidence({
    task: {
      id: "task-1",
      Authorization: "Bearer secret",
      nested: [{ token: "secret", accessToken: "secret", password: "p@ss", api_key: "key", cookie: "sid=x", credential: "cred" }],
      previewUrl: "s3://private-bucket/object",
      filePath: String.raw`D:\private\drawing.png`,
    },
    notes: [
      "safe",
      "https://private.example/asset",
      "/Users/alice/private/file.png",
      "/home/alice/private/file.png",
      String.raw`C:\Users\alice\private\file.png`,
      "Authorization: Bearer abc.def",
    ],
  });
  const wire = JSON.stringify(clean);
  assert.deepEqual(clean, {
    task: { id: "task-1", nested: [{}] },
    notes: ["safe", "[REDACTED]", "[REDACTED]", "[REDACTED]", "[REDACTED]", "[REDACTED]"],
  });
  assert.doesNotMatch(wire, /token|authorization|password|api[_-]?key|cookie|credential|bearer\s|https?:\/\/|\/(?:Users|home)\/|[A-Z]:\\Users\\/i);
  assert.doesNotThrow(() => assertEvidenceClean(clean));
  for (const unsafe of [
    { value: "https://private.example" },
    { password: "p@ss" },
    { apiKey: "key" },
    { accessToken: "token" },
    { previewUrl: "s3://private-bucket/object" },
    { filePath: String.raw`D:\private\drawing.png` },
    { cookie: "sid=x" },
    { credential: "cred" },
    { note: "Bearer abc.def" },
    { file: String.raw`C:\Users\alice\secret.txt` },
  ]) assert.throws(() => assertEvidenceClean(unsafe), /Evidence QA/);
});
