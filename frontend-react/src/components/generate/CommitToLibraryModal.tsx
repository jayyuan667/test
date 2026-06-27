import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { getLibraryScopes, commitToLibrary, type LibraryScope, type CommitDraft, type RetrievalCheck } from '../../api/client'

interface Props {
  draft: CommitDraft
  onClose: () => void
  onSuccess: (message: string) => void
}

export function CommitToLibraryModal({ draft, onClose, onSuccess }: Props) {
  const [scopes, setScopes] = useState<LibraryScope[]>([])
  const [loading, setLoading] = useState(true)
  const [committing, setCommitting] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retrievalCheck, setRetrievalCheck] = useState<RetrievalCheck | null>(null)

  useEffect(() => {
    getLibraryScopes()
      .then(res => {
        setScopes(res.items)
        if (res.items.length > 0) setSelectedKey(res.items[0].library_key)
      })
      .catch(err => setError(err instanceof Error ? err.message : '获取库列表失败'))
      .finally(() => setLoading(false))
  }, [])

  const handleCommit = async () => {
    if (!selectedKey) return
    setCommitting(true)
    setError(null)
    setRetrievalCheck(null)
    try {
      const response = await commitToLibrary({ draft, action: 'replace', library_key: selectedKey })
      const check = response.retrieval_check || null
      if (!check || check.status === 'ok') {
        onSuccess(check ? `入库成功，检索自测通过，相似度 ${check.similarity.toFixed(2)}` : '入库成功')
        onClose()
        return
      }
      // skipped/failed → 保留弹窗显示 amber 状态卡，不塞进 error state
      setRetrievalCheck(check)
    } catch (err) {
      setError(err instanceof Error ? err.message : '入库失败')
    } finally {
      setCommitting(false)
    }
  }

  const modal = (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center" style={{ background: 'var(--modal-overlay)' }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="theme-surface-panel rounded-2xl shadow-2xl w-[90vw] max-w-[420px] max-h-[85vh] flex flex-col overflow-hidden border">
        {/* Header */}
        <div className="px-6 pt-5 pb-3 border-b" style={{ borderColor: 'var(--modal-subtle-border)' }}>
          <h3 className="text-[16px] font-bold" style={{ color: 'var(--text-primary)' }}>选择入库目标</h3>
          <p className="text-[12px] mt-1" style={{ color: 'var(--text-muted)' }}>将当前工艺规程保存到知识库</p>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-[13px]" style={{ color: 'var(--text-muted)' }}>
              <span className="w-4 h-4 border-2 border-slate-200 border-t-flame-500 rounded-full animate-spin mr-2" />
              加载中...
            </div>
          ) : error ? (
            <div className="text-red-500 text-[13px] text-center py-4">{error}</div>
          ) : retrievalCheck ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left">
              <div className="text-[13px] font-bold text-amber-700">
                {retrievalCheck.status === 'skipped' ? '入库成功，检索自测已跳过' : '入库成功，检索自测未命中'}
              </div>
              <div className="text-[12px] text-amber-700 mt-1">
                {retrievalCheck.reason || '请检查向量服务配置后重新检索。'}
              </div>
              <button className="btn btn-secondary !text-[12px] !mt-3" onClick={onClose}>关闭</button>
            </div>
          ) : scopes.length === 0 ? (
            <div className="text-[13px] text-center py-8" style={{ color: 'var(--text-muted)' }}>暂无可用知识库</div>
          ) : (
            <div className="flex flex-col gap-2">
              {scopes.map(scope => (
                <button
                  key={scope.library_key}
                  onClick={() => setSelectedKey(scope.library_key)}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors ${
                    selectedKey === scope.library_key
                      ? 'border-flame-400 bg-flame-50/50'
                      : 'bg-white'
                  }`}
                  style={selectedKey === scope.library_key ? undefined : { borderColor: 'var(--modal-subtle-border)' }}
                >
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    selectedKey === scope.library_key ? 'border-flame-500' : 'border-slate-300'
                  }`}>
                    {selectedKey === scope.library_key && <div className="w-2 h-2 rounded-full bg-flame-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>{scope.library_name}</div>
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {scope.scope_type === 'public' ? '公共库' : '私有库'}
                      {scope.record_count != null && ` · ${scope.record_count} 条记录`}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex items-center justify-end gap-3" style={{ borderColor: 'var(--modal-subtle-border)' }}>
          <button onClick={onClose} className="btn btn-ghost !text-[12px]">取消</button>
          <button
            onClick={handleCommit}
            disabled={!selectedKey || committing}
            className="btn btn-primary !text-[12px] !px-5"
          >
            {committing ? '入库中...' : '确认入库'}
          </button>
        </div>
      </div>
    </div>
  )

  // Portal to body to avoid parent overflow-hidden clipping
  return createPortal(modal, document.body)
}
