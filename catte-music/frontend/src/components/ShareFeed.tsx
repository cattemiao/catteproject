import { useEffect, useState } from 'react'
import { TrendingUp } from 'lucide-react'
import { recommendApi, shareApi } from '../api/client'
import type { ShareOut } from '../types'
import ShareCard from './ShareCard'

interface ShareFeedProps {
  limit?: number
  platform?: string
  accentClass?: string
}

/** 社区推荐流：完全来自其他用户的分享（情绪相近优先 + 点赞加权 + 随机兜底）。 */
export default function ShareFeed({ limit = 6, platform, accentClass = 'text-neon-amber' }: ShareFeedProps) {
  const [shares, setShares] = useState<ShareOut[]>([])
  const [loading, setLoading] = useState(true)
  const [likingId, setLikingId] = useState<number | null>(null)

  useEffect(() => {
    setLoading(true)
    recommendApi
      .get(limit, platform ? { platform } : undefined)
      .then(({ data }) => setShares(data))
      .catch(() => setShares([]))
      .finally(() => setLoading(false))
  }, [limit, platform])

  const handleToggleLike = async (share: ShareOut) => {
    setLikingId(share.id)
    // 乐观更新
    setShares((prev) =>
      prev.map((s) =>
        s.id === share.id
          ? { ...s, user_liked: !s.user_liked, like_count: s.like_count + (s.user_liked ? -1 : 1) }
          : s,
      ),
    )
    try {
      if (share.user_liked) {
        await shareApi.unlike(share.id)
      } else {
        await shareApi.like(share.id)
      }
    } catch {
      // 失败回滚
      setShares((prev) =>
        prev.map((s) =>
          s.id === share.id
            ? { ...s, user_liked: share.user_liked, like_count: share.like_count }
            : s,
        ),
      )
    } finally {
      setLikingId(null)
    }
  }

  return (
    <section className="mb-10">
      <h2 className="font-display text-xl font-bold mb-4 flex items-center gap-2">
        <TrendingUp className={`w-5 h-5 ${accentClass}`} />
        为你推荐
      </h2>
      {loading ? (
        <p className="text-sm text-slate-500 text-center py-8">推荐加载中…</p>
      ) : shares.length === 0 ? (
        <div className="text-center py-8 rounded-xl border border-white/5 bg-white/[0.02]">
          <p className="text-sm text-slate-500 mb-1">还没有其他用户分享的内容</p>
          <p className="text-xs text-slate-600">
            完成一次 AI 情绪分析后即可分享你的专辑/歌单，出现在大家的推荐里
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {shares.map((share) => (
            <ShareCard
              key={share.id}
              share={share}
              liking={likingId === share.id}
              onToggleLike={handleToggleLike}
            />
          ))}
        </div>
      )}
    </section>
  )
}
