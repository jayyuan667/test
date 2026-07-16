"use client";

import { useRef } from "react";

import type { TaskSnapshot } from "@/features/drawing-workflow/types";

interface DrawingWorkspaceProps {
  drawing: TaskSnapshot["drawing"];
  previewUrls: string[];
  activePage: number;
  onPageChange: (page: number) => void;
}

export function DrawingWorkspace({ drawing, previewUrls, activePage, onPageChange }: DrawingWorkspaceProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const pageCount = Math.max(drawing.page_count, previewUrls.length, 1);
  const currentPage = Math.min(Math.max(activePage, 0), pageCount - 1);
  const previewUrl = previewUrls[currentPage];
  const alt = `${drawing.name || "工程图纸"} · 第 ${currentPage + 1} 页`;

  function closeDialog() {
    dialogRef.current?.close();
  }

  return (
    <section className="forge-drawing" aria-labelledby="forge-drawing-title">
      <header className="forge-drawing__header">
        <div>
          <p className="forge-eyebrow">DRAWING / PREVIEW</p>
          <h2 id="forge-drawing-title">{drawing.name || "工程图纸"}</h2>
        </div>
        <button
          className="forge-drawing__expand"
          type="button"
          disabled={!previewUrl}
          onClick={() => dialogRef.current?.showModal()}
        >
          放大查看
        </button>
      </header>

      <figure className="forge-drawing__figure">
        {previewUrl ? (
          // The parent supplies transient object URLs, so Next image optimization is not applicable.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt={alt} />
        ) : (
          <div className="forge-drawing__placeholder" role="img" aria-label={`${alt}，预览生成中`}>
            预览生成中
          </div>
        )}
        <figcaption>{alt}</figcaption>
      </figure>

      <nav className="forge-drawing__pagination" aria-label="图纸分页">
        <button
          type="button"
          aria-label="上一页"
          disabled={currentPage === 0}
          onClick={() => onPageChange(currentPage - 1)}
        >
          上一页
        </button>
        <output aria-live="polite">第 {currentPage + 1} 页 / 共 {pageCount} 页</output>
        <button
          type="button"
          aria-label="下一页"
          disabled={currentPage >= pageCount - 1}
          onClick={() => onPageChange(currentPage + 1)}
        >
          下一页
        </button>
      </nav>

      <dialog
        ref={dialogRef}
        className="forge-drawing-dialog"
        aria-label={`${drawing.name || "工程图纸"}放大预览`}
        onCancel={closeDialog}
      >
        <div className="forge-drawing-dialog__toolbar">
          <span>{alt}</span>
          <button type="button" aria-label="关闭放大预览" onClick={closeDialog}>关闭</button>
        </div>
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt={alt} />
        ) : null}
      </dialog>
    </section>
  );
}
