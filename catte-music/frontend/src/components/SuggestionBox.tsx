import { useEffect, useState } from 'react'
import { Check, MessageSquareText, Send, X } from 'lucide-react'
import { suggestionApi } from '../api/client'

export default function SuggestionBox() {
  const [open, setOpen] = useState(false)
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  // 成功提示 3 秒后自动消失
  useEffect(() => {
    if (!success) return
    const timer = setTimeout(() => setSuccess(false), 3000)
    return () => clearTimeout(timer)
  }, [success])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return
    setSubmitting(true)
    setError('')
    setSuccess(false)
    try {
      await suggestionApi.create(content.trim())
      setContent('')
      setSuccess(true)
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
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-all"
        title="意见投稿"
      >
        <MessageSquareText className="w-4 h-4 text-neon-cyan" />
        <span className="hidden sm:inline">意见</span>
      </button>

      {/* 弹窗 */}
      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center pt-16 px-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-2xl bg-midnight/95 backdrop-blur-xl border border-white/10 shadow-[0_0_50px_rgba(168,85,247,0.15)]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <h3 className="font-display font-bold flex items-center gap-2 text-white">
                <MessageSquareText className="w-5 h-5 text-neon-purple" />
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
            <form onSubmit={submit} className="px-5 py-4">
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                maxLength={1000}
                rows={3}
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10
                           focus:border-neon-purple/50 focus:outline-none focus:ring-2
                           focus:ring-neon-purple/20 transition-all text-white text-sm
                           placeholder:text-slate-600 resize-none"
                placeholder="写下你的意见或建议…（登录后可投稿）"
              />
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs text-slate-500">{content.length}/1000</span>
                <button
                  type="submit"
                  disabled={submitting || !content.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium
                             bg-gradient-to-r from-neon-purple/20 to-neon-blue/20 text-white
                             border border-neon-purple/30 hover:border-neon-purple/60
                             transition-all disabled:opacity-40"
                >
                  <Send className="w-3.5 h-3.5 text-neon-cyan" />
                  {submitting ? '提交中…' : '投稿'}
                </button>
              </div>
              {error && (
                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mt-2">
                  {error}
                </p>
              )}
              {success && (
                <p className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 mt-2 flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5" />
                  投稿成功，感谢你的反馈！
                </p>
              )}
            </form>
          </div>
        </div>
      )}
    </>
  )
}
