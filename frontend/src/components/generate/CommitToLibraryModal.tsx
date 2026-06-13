import { useState, useEffect } from 'react'
import { getLibraryScopes, commitToLibrary, type LibraryScope, type CommitDraft } from '../../api/client'

interface Props {
  draft: CommitDraft
  onClose: () => void
  onSuccess: () => void
}

export function CommitToLibraryModal({ draft, onClose, onSuccess }: Props) {
  const [scopes, setScopes] = useState<LibraryScope[]>([])
  const [loading, setLoading] = useState(true)
  const [committing, setCommitting] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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
    try {
      await commitToLibrary({ draft, action: 'replace', library_key: selectedKey })
      onSuccess()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : '入库失败')
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.4)' }} onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-white rounded-2xl shadow-2xl w-[420px] max-h-[80vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-5 pb-3 border-b border-slate-100">
          <h3 className="text-[16px] font-bold text-slate-800">选择入库目标</h3>
          <p className="text-[12px] text-slate-400 mt-1">将当前工艺规程保存到知识库</p>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-slate-400 text-[13px]">
              <span className="w-4 h-4 border-2 border-slate-200 border-t-flame-500 rounded-full animate-spin mr-2" />
              加载中...
            </div>
          ) : error ? (
            <div className="text-red-500 text-[13px] text-center py-4">{error}</div>
          ) : scopes.length === 0 ? (
            <div className="text-slate-400 text-[13px] text-center py-8">暂无可用知识库</div>
          ) : (
            <div className="flex flex-col gap-2">
              {scopes.map(scope => (
                <button
                  key={scope.library_key}
                  onClick={() => setSelectedKey(scope.library_key)}
                  className={`flex items-center gap-3 p-3 rounded-xl border-2 text-left transition-colors ${
                    selectedKey === scope.library_key
                      ? 'border-flame-400 bg-flame-50/50'
                      : 'border-slate-100 hover:border-slate-200 bg-white'
                  }`}
                >
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                    selectedKey === scope.library_key ? 'border-flame-500' : 'border-slate-300'
                  }`}>
                    {selectedKey === scope.library_key && <div className="w-2 h-2 rounded-full bg-flame-500" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-slate-700">{scope.library_name}</div>
                    <div className="text-[11px] text-slate-400">
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
        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3">
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
}
