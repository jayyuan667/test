import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("DashboardScene uses Three-compatible color values", async () => {
  const source = await readFile(new URL("./DashboardScene.tsx", import.meta.url), "utf8");

  assert.equal(source.includes("#e0782820"), false);
  assert.equal(source.includes("#e0782810"), false);
});

test("FluidCursorWebGL does not use deprecated THREE.Clock", async () => {
  const source = await readFile(new URL("./FluidCursorWebGL.tsx", import.meta.url), "utf8");

  assert.equal(source.includes("new THREE.Clock()"), false);
});
