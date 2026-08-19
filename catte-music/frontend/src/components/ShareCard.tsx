import { Link } from 'react-router-dom'
import { Disc, Heart, Music, Sparkles } from 'lucide-react'
import type { ShareOut } from '../types'

interface ShareCardProps {
  share: ShareOut
  liking?: boolean
  onToggleLike: (share: ShareOut) => void
}

/** 分享卡片：专辑信息 + AI 情绪徽章 + 分享者 + 点赞按钮。 */
export default function ShareCard({ share, liking, onToggleLike }: ShareCardProps) {
  const song = share.song
  const isAlbum = song.type === 'albums'
  const isPlaylist = song.type === 'playlists'
  const hasSim = typeof share.similarity === 'number' && share.similarity > 0.5
  const simPct = typeof share.similarity === 'number' ? Math.round(share.similarity * 100) : 0

  return (
    <div className="card group flex flex-col">
      {/* 封面：点击进入详情 */}
      <Link to={`/song/${song.id}`} className="block">
        <div className="aspect-square rounded-xl bg-gradient-to-br from-neon-purple/30 to-neon-blue/20 mb-3 flex items-center justify-center group-hover:shadow-[0_0_25px_rgba(168,85,247,0.3)] transition-all overflow-hidden relative">
          {song.artwork_url ? (
            <img
              src={song.artwork_url}
              alt={song.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy"
            />
          ) : isAlbum ? (
            <Disc className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
          ) : isPlaylist ? (
            <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
          ) : (
            <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
          )}
        </div>
      </Link>

      {/* 标题 */}
      <Link to={`/song/${song.id}`} className="block">
        <h3 className="font-medium text-sm truncate group-hover:text-neon-cyan transition-colors">
          {song.title}
        </h3>
        <p className="text-xs text-slate-500 truncate">{song.artist}</p>
      </Link>

      {/* 徽章行：情绪 + 口味相似度 */}
      {(share.emotion || hasSim) && (
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          {share.emotion && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-neon-pink/10 text-neon-pink text-[10px]">
              <Sparkles className="w-3 h-3" />
              {share.emotion}
            </span>
          )}
          {hasSim && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-neon-cyan/10 text-neon-cyan text-[10px]">
              与你口味相近 {simPct}%
            </span>
          )}
        </div>
      )}

      {/* 分享语 */}
      {share.comment && (
        <p className="text-xs text-slate-400 mt-2 leading-relaxed line-clamp-2">
          “{share.comment}”
        </p>
      )}

      {/* 底部：分享者 + 点赞 */}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-white/5">
        <Link
          to={`/users/${share.sharer_id}`}
          className="text-xs text-slate-400 hover:text-neon-cyan transition-colors truncate"
          onClick={(e) => e.stopPropagation()}
        >
          由 <span className="font-medium">@{share.sharer_username}</span> 分享
        </Link>
        <button
          onClick={() => onToggleLike(share)}
          disabled={liking}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs border transition-all disabled:opacity-50"
          style={
            share.user_liked
              ? { color: '#f43f5e', borderColor: 'rgba(244,63,94,0.4)' }
              : { color: '#94a3b8', borderColor: 'rgba(255,255,255,0.1)' }
          }
        >
          <Heart className={`w-3.5 h-3.5 ${share.user_liked ? 'fill-current' : ''}`} />
          {share.like_count}
        </button>
      </div>
    </div>
  )
}
