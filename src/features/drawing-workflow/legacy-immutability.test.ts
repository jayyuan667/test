import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("legacy fallback remains at the reviewed characterization hash", async () => {
  const source = await readFile(new URL("../../components/pages/LegacyGeneratePage.tsx", import.meta.url));
  assert.equal(createHash("sha256").update(source).digest("hex"), "69feb74549796fc0a325198e5c66f9460a4ef81fadccd4eb5fc7df48fa4a45a7");
});
