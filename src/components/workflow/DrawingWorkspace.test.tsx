import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { DrawingWorkspace } from "./DrawingWorkspace.tsx";
import { UploadWorkspace } from "./UploadWorkspace.tsx";

test("drawing workspace keeps the engineering drawing primary and exposes page controls", () => {
  const html = renderToStaticMarkup(
    <DrawingWorkspace
      drawing={{ name: "test.png", source_kind: "png", page_count: 2, preview_urls: [] }}
      previewUrls={["blob:one", "blob:two"]}
      activePage={0}
      onPageChange={() => {}}
    />,
  );

  assert.match(html, /alt="test\.png · 第 1 页"/);
  assert.match(html, /第 1 页 \/ 共 2 页/);
  assert.match(html, /aria-label="上一页"[^>]*disabled/);
  assert.match(html, /aria-label="下一页"/);
  assert.match(html, /放大查看/);
  assert.match(html, /<dialog/);
  assert.match(html, /关闭放大预览/);
});

test("upload workspace keeps the native file input and presents one primary action", () => {
  const file = new File([new Uint8Array(1536)], "法兰盘 Rev 3.pdf", { type: "application/pdf" });
  const html = renderToStaticMarkup(
    <UploadWorkspace file={file} busy={false} onFileChange={() => {}} onStart={() => {}} />,
  );

  assert.match(html, /type="file"/);
  assert.match(html, /accept="\.png,\.jpg,\.jpeg,\.pdf,\.dxf,\.prt"/);
  assert.match(html, /法兰盘 Rev 3\.pdf/);
  assert.match(html, /1\.5 KB/);
  assert.equal((html.match(/forge-upload__primary/g) ?? []).length, 1);
  assert.match(html, />开始解析<\/button>/);
});

test("workspaces leave URL ownership and persistence to their parent", async () => {
  const sources = await Promise.all([
    readFile(new URL("./DrawingWorkspace.tsx", import.meta.url), "utf8"),
    readFile(new URL("./UploadWorkspace.tsx", import.meta.url), "utf8"),
  ]);

  for (const source of sources) {
    assert.doesNotMatch(source, /\bfetch\s*\(/);
    assert.doesNotMatch(source, /localStorage/);
    assert.doesNotMatch(source, /createObjectURL/);
  }
});
