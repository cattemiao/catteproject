import { useEffect, useState } from 'react'
import { MessageSquareText, Send, X } from 'lucide-react'
import { suggestionApi, type SuggestionOut } from '../api/client'

export default function SuggestionBox() {
  const [open, setOpen] = useState(false)
  const [list, setList] = useState<SuggestionOut[]>([])
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await suggestionApi.list()
      setList(data)
    } catch {
      setError('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) load()
  }, [open])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const { data } = await suggestionApi.create(content.trim())
      setList((prev) => [data, ...prev])
      setContent('')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '提交失败，请先登录'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      {/* 触发按钮 */}
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-neon-cyan hover:bg-neon-cyan/10 transition-all"
        title="意见投稿"
      >
        <MessageSquareText className="w-4 h-4" />
        <span className="hidden sm:inline">意见</span>
      </button>

      {/* 弹窗 */}
      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center pt-16 px-4 bg-black/50 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="glass w-full max-w-lg rounded-2xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <h3 className="font-display font-bold flex items-center gap-2">
                <MessageSquareText className="w-5 h-5 text-neon-cyan" />
                意见投稿箱
              </h3>
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 投稿表单 */}
            <form onSubmit={submit} className="px-5 py-4 border-b border-white/10">
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                maxLength={1000}
                rows={3}
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10
                           focus:border-neon-cyan/50 focus:outline-none focus:ring-2
                           focus:ring-neon-cyan/20 transition-all text-white text-sm
                           placeholder:text-slate-600 resize-none"
                placeholder="写下你的意见或建议…（登录后可投稿）"
              />
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-slate-600">{content.length}/1000</span>
                <button
                  type="submit"
                  disabled={submitting || !content.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium
                             bg-neon-cyan/15 text-neon-cyan border border-neon-cyan/30
                             hover:bg-neon-cyan/25 transition-all disabled:opacity-40"
                >
                  <Send className="w-3.5 h-3.5" />
                  {submitting ? '提交中…' : '投稿'}
                </button>
              </div>
              {error && (
                <p className="text-xs text-red-400 mt-2">{error}</p>
              )}
            </form>

            {/* 投稿列表（所有人可见） */}
            <div className="px-5 py-4 max-h-[320px] overflow-y-auto">
              {loading ? (
                <p className="text-sm text-slate-500 text-center py-4">加载中…</p>
              ) : list.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-4">
                  暂无投稿，快来抢沙发
                </p>
              ) : (
                <div className="space-y-3">
                  {list.map((s) => (
                    <div key={s.id} className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-neon-cyan">{s.username}</span>
                        <span className="text-xs text-slate-600">{s.created_at}</span>
                      </div>
                      <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
                        {s.content}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
