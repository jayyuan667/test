"use client";

import type { ChangeEvent } from "react";

const ACCEPTED_DRAWINGS = ".png,.jpg,.jpeg,.pdf,.dxf,.prt";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface UploadWorkspaceProps {
  file: File | null;
  busy: boolean;
  onFileChange: (file: File | null) => void;
  onStart: () => void;
}

export function UploadWorkspace({ file, busy, onFileChange, onStart }: UploadWorkspaceProps) {
  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.currentTarget.files?.[0] ?? null);
  }

  return (
    <section className="forge-upload" aria-labelledby="forge-upload-title">
      <div className="forge-upload__heading">
        <p className="forge-eyebrow">INPUT / DRAWING</p>
        <h2 id="forge-upload-title">上传工程图纸</h2>
        <p>选择待解析的零件图，文件将在确认后进入识别流程。</p>
      </div>

      <div className="forge-upload__field">
        <label htmlFor="forge-drawing-file">选择图纸文件</label>
        <input
          id="forge-drawing-file"
          data-testid="drawing-upload"
          type="file"
          accept={ACCEPTED_DRAWINGS}
          disabled={busy}
          onChange={handleFileChange}
        />
        <p className="forge-upload__hint">支持 PNG、JPG、PDF、DXF 与 PRT</p>
      </div>

      <div className="forge-upload__selection" aria-live="polite">
        {file ? (
          <>
            <span className="forge-upload__filename">{file.name}</span>
            <span className="forge-upload__filesize">{formatFileSize(file.size)}</span>
          </>
        ) : (
          <span className="forge-upload__empty">尚未选择文件</span>
        )}
      </div>

      <button
        data-testid="start-analysis"
        className="forge-upload__primary"
        type="button"
        disabled={!file || busy}
        aria-busy={busy}
        onClick={onStart}
      >
        {busy ? "正在上传…" : "开始解析"}
      </button>
    </section>
  );
}
