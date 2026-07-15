'use client'

import { useEffect, useRef, useState } from 'react'

import { createDrawingWorkflowController, type DrawingWorkflowController } from '@/features/drawing-workflow/controller'
import { workflowService } from '@/services'
import type { WorkflowFeature, WorkflowState } from '@/services'
import { LegacyGeneratePage } from './LegacyGeneratePage'

const useWorkflowV1 = process.env.NEXT_PUBLIC_USE_WORKFLOW_V1 !== 'false'
const activeTaskKey = 'forge-v1-active-task'

const phaseLabels: Record<string, string> = {
  upload: '上传图纸', drawing_analysis: '图纸解析', annotation: '特征标注',
  feature_review: '特征审阅', process_generation: '工艺生成', export: '导出', done: '已完成',
}

function V1GeneratePage() {
  const controllerRef = useRef<DrawingWorkflowController | null>(null)
  const [state, setState] = useState<WorkflowState>(() => ({ snapshot: null, operationsById: {}, operationOrder: [], lastSeq: 0, connection: 'idle', error: null }))
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  useEffect(() => {
    const controller = createDrawingWorkflowController(workflowService)
    controllerRef.current = controller
    const unsubscribe = controller.subscribe(setState)
    const savedTask = localStorage.getItem(activeTaskKey)
    if (savedTask) void controller.start(savedTask).catch((error: Error) => setMessage(error.message))
    return () => { unsubscribe(); controller.dispose(); controllerRef.current = null }
  }, [])

  useEffect(() => {
    const sourceUrl = state.snapshot?.drawing.preview_urls[0]
    const controller = controllerRef.current
    if (!sourceUrl || !controller) { setPreviewUrl(null); return }
    let active = true
    void controller.loadPreview(sourceUrl).then((url) => { if (active && url) setPreviewUrl(url) }).catch((error: Error) => { if (active) setMessage(error.message) })
    return () => { active = false }
  }, [state.snapshot?.drawing.preview_urls])

  const run = async (action: (controller: DrawingWorkflowController) => Promise<void>) => {
    const controller = controllerRef.current
    if (!controller) return
    setBusy(true); setMessage(null)
    try {
      await action(controller)
      const taskId = controller.getState().snapshot?.task.id
      if (taskId) localStorage.setItem(activeTaskKey, taskId)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '操作失败')
    } finally { setBusy(false) }
  }

  const snapshot = state.snapshot
  const operations = state.operationOrder.map((id) => state.operationsById[id]).filter(Boolean)
  const awaitingAnnotation = snapshot?.task.state === 'awaiting_annotation'
  const awaitingReview = snapshot?.task.state === 'awaiting_review'
  const completed = snapshot?.task.state === 'completed'

  return (
    <main data-testid="v1-workflow" style={{ padding: 'var(--content-py) var(--content-px)', display: 'grid', gap: 16 }}>
      <header>
        <div style={{ fontSize: 11, letterSpacing: '.08em', color: 'var(--accent)', fontWeight: 700 }}>AI 工艺编制 · V1</div>
        <h1 style={{ fontSize: 22, marginTop: 6 }}>工艺生成</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>上传零件图，审阅真实特征并生成结构化工艺。</p>
      </header>

      {!snapshot && <section style={cardStyle}>
        <label htmlFor="v1-drawing" style={{ display: 'block', fontSize: 13, fontWeight: 650, marginBottom: 10 }}>选择图纸</label>
        <input id="v1-drawing" data-testid="drawing-upload" type="file" accept=".png,.jpg,.jpeg,.pdf,.dxf,.prt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        {file && <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 10 }}>{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</div>}
        <button data-testid="start-analysis" style={buttonStyle} disabled={!file || busy} onClick={() => file && run((controller) => controller.upload(file))}>{busy ? '上传中…' : '开始解析'}</button>
      </section>}

      {snapshot && <>
        <section data-testid="workflow-status" style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div><div style={eyebrowStyle}>当前阶段</div><strong data-testid="workflow-phase" data-phase={snapshot.task.phase}>{phaseLabels[snapshot.task.phase] ?? snapshot.task.phase}</strong><span data-testid="workflow-state" style={{ display: 'none' }}>{snapshot.task.state}</span></div>
            <div><div style={eyebrowStyle}>任务 ID</div><code data-testid="task-id">{snapshot.task.id}</code></div>
            <div><div style={eyebrowStyle}>连接</div><span data-testid="workflow-connection">{state.connection} · seq {state.lastSeq}</span></div>
          </div>
          <div style={{ height: 5, background: 'var(--border)', borderRadius: 5, marginTop: 16 }}><div data-testid="workflow-progress" style={{ height: '100%', width: `${snapshot.task.progress}%`, background: 'var(--accent)', borderRadius: 5 }} /></div>
          <div data-testid="workflow-progress-value" style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>{snapshot.task.progress}%</div>
        </section>

        <section style={cardStyle}>
          {previewUrl && <figure style={{ margin: '0 0 16px' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img data-testid="drawing-preview" src={previewUrl} alt={snapshot.drawing.name} style={{ display: 'block', maxWidth: '100%', maxHeight: 420, objectFit: 'contain', borderRadius: 10, border: '1px solid var(--border)' }} />
            <figcaption style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>{snapshot.drawing.name} · {snapshot.drawing.page_count} 页</figcaption>
          </figure>}
          <div style={sectionTitleStyle}>结构化特征</div>
          <div data-testid="feature-list" style={{ display: 'grid', gap: 8 }}>
            {snapshot.features.map((feature) => <FeatureRow key={feature.id} feature={feature} previewUrl={previewUrl} />)}
            {snapshot.features.length === 0 && <span style={emptyStyle}>等待真实特征数据…</span>}
          </div>
          {awaitingAnnotation && <button data-testid="finalize-annotations" style={buttonStyle} disabled={busy} onClick={() => run((controller) => controller.finalizeAnnotations({ review_text: 'confirmed' }))}>确认标注</button>}
          {awaitingReview && <button data-testid="confirm-review" style={buttonStyle} disabled={busy} onClick={() => run((controller) => controller.submitReview({ review_text: snapshot.review.raw_text ?? '', features: snapshot.features }))}>确认审阅并生成工艺</button>}
        </section>

        <section style={cardStyle}>
          <div style={sectionTitleStyle}>结构化工艺</div>
          <div style={{ overflowX: 'auto' }}><table data-testid="operation-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead><tr>{['工序', '工种', '内容', '设备', '工时'].map((label) => <th key={label} style={cellStyle}>{label}</th>)}</tr></thead>
            <tbody>{operations.map((operation) => <tr data-testid="operation-row" key={operation.id}>
              <td style={cellStyle}>{operation.code}</td><td style={cellStyle}>{operation.trade ?? '未提供'}</td><td style={cellStyle}>{operation.content}</td>
              <td style={cellStyle}>{operation.equipment.length ? operation.equipment.join('、') : '未提供'}</td><td style={cellStyle}>{operation.duration_minutes === null ? '未提供' : `${operation.duration_minutes} min`}</td>
            </tr>)}</tbody>
          </table></div>
          {operations.length === 0 && <div style={emptyStyle}>等待结构化工艺…</div>}
          {completed && <a data-testid="download-export" href={workflowService.exportUrl(snapshot.task.id)} download style={{ ...buttonStyle, display: 'inline-block', textDecoration: 'none' }}>导出 PDF</a>}
        </section>
      </>}
      {(message || state.error) && <div role="alert" style={{ color: 'var(--danger)', fontSize: 13 }}>{message ?? state.error?.message}</div>}
    </main>
  )
}

function FeatureRow({ feature, previewUrl }: { feature: WorkflowFeature; previewUrl: string | null }) {
  return <article data-testid="feature-row" style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 10, display: 'grid', gridTemplateColumns: 'minmax(150px, 1fr) auto', gap: 8 }}>
    <div><strong>{feature.label}</strong><div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{feature.kind} · {feature.value ?? '未提供'}</div></div>
    <div style={{ textAlign: 'right', fontSize: 11 }}><div data-testid="feature-confidence">置信度：{feature.confidence === null ? '未提供' : `${Math.round(feature.confidence * 100)}%`}</div>{previewUrl ? <a data-testid="feature-source" href={previewUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>来源：{feature.source.method ?? '未提供'} / {feature.source.page === null ? '页码未提供' : `P${feature.source.page}`}</a> : <div data-testid="feature-source" style={{ color: 'var(--text-muted)', marginTop: 4 }}>来源：{feature.source.method ?? '未提供'} / {feature.source.page === null ? '页码未提供' : `P${feature.source.page}`}</div>}</div>
  </article>
}

const cardStyle: React.CSSProperties = { background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 14, padding: 18 }
const buttonStyle: React.CSSProperties = { marginTop: 14, border: 0, borderRadius: 9, padding: '9px 15px', background: 'var(--accent)', color: '#fff', cursor: 'pointer', fontWeight: 650, fontSize: 12 }
const eyebrowStyle: React.CSSProperties = { fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }
const sectionTitleStyle: React.CSSProperties = { fontSize: 14, fontWeight: 700, marginBottom: 12 }
const emptyStyle: React.CSSProperties = { color: 'var(--text-muted)', fontSize: 12, padding: '12px 0', display: 'block' }
const cellStyle: React.CSSProperties = { padding: '9px 10px', borderBottom: '1px solid var(--border)', textAlign: 'left' }

export function GeneratePage() { return useWorkflowV1 ? <V1GeneratePage /> : <LegacyGeneratePage /> }
