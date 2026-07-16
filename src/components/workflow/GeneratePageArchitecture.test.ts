import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("GeneratePage delegates transport and stream ownership to the v1 controller", async () => {
  const source = await readFile(new URL("../pages/GeneratePage.tsx", import.meta.url), "utf8");

  for (const forbidden of ["fetch(", "new EventSource", "setInterval(", "marked(", "?token="]) {
    assert.equal(source.includes(forbidden), false, `must not contain ${forbidden}`);
  }

  assert.match(source, /controller\.loadPreview/);
  assert.match(source, /Promise\.all/);
  assert.match(source, /reachedStepForSnapshot/);
  assert.match(source, /followLatest/);
  assert.equal(/connection\}[\s\S]*seq|seq[\s\S]*connection\}/.test(source), false);
});
