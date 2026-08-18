import { lazy, Suspense, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Disc, Music, TrendingUp, Sparkles, Compass, Trash2 } from 'lucide-react'
import { songsApi, appleMusicApi, recommendApi, authApi } from '../api/client'
import { loadMusicKit } from '../utils/musicKit'
import type { SongOut, StyleRecommendResult } from '../types'

// p5.js 粒子背景懒加载：不阻塞首屏
const ParticleBg = lazy(() => import('../components/ParticleBg'))

export default function Home() {
  const [songs, setSongs] = useState<SongOut[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [recs, setRecs] = useState<SongOut[]>([])
  const [styleRecs, setStyleRecs] = useState<StyleRecommendResult | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [clearing, setClearing] = useState(false)
  const [clearMsg, setClearMsg] = useState('')

  const PAGE_SIZE = 12
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // 音乐库分页加载（Apple Music 页只展示 Apple 平台导入的歌曲）
  useEffect(() => {
    songsApi.list({ page, size: PAGE_SIZE, platform: 'apple' })
      .then(({ data }) => {
        setSongs(data.items)
        setTotal(data.total)
      })
      .catch(() => {})
  }, [page])

  // 推荐区仅加载一次
  useEffect(() => {
    recommendApi.get(6, { platform: 'apple' }).then(({ data }) => setRecs(data)).catch(() => {})
    recommendApi.getStyle(6, { platform: 'apple' }).then(({ data }) => setStyleRecs(data)).catch(() => {})
  }, [])

  const clearApple = async () => {
    if (!window.confirm('确定清空已导入的 Apple Music 歌曲吗？清空后可点击上方按钮重新同步。')) return
    setClearing(true)
    setClearMsg('')
    try {
      const { data } = await songsApi.clear('apple')
      setSongs([])
      setPage(1)
      setTotal(0)
      setRecs([])
      setStyleRecs(null)
      setClearMsg(`已清空 ${data.deleted} 首，可重新同步`)
    } catch {
      setClearMsg('清空失败，请重试')
    } finally {
      setClearing(false)
    }
  }

  const syncAppleMusic = async () => {
    setSyncing(true)
    setSyncMsg('')
    try {
      // 1. 获取 Developer Token
      const { data: config } = await authApi.appleMusicConfig()

      // 2. 按需加载并配置 MusicKit JS
      const MusicKit = await loadMusicKit()
      await MusicKit.configure({
        developerToken: config.developer_token,
        app: { name: config.app_name, build: config.build },
      })

      // 3. 弹窗授权，获取 Music User Token
      const music = MusicKit.getInstance()
      const musicUserToken = await music.authorize()
      if (!musicUserToken) {
        setSyncMsg('授权已取消')
        return
      }

      // 4. 回传 Music User Token 给后端存储
      await authApi.appleMusicCallback(musicUserToken)

      // 5. 同步最近播放记录（Apple 限制 limit ≤ 10）
      await appleMusicApi.recent(10)

      // 6. 分页同步资料库专辑（每页最多 100，可拉全量）
      const { data: lib } = await appleMusicApi.library(300)
      setSyncMsg(`同步成功！新增最近播放 + ${lib.total} 张专辑`)
      setTimeout(() => location.reload(), 800)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        '同步失败，请重试'
      setSyncMsg(msg)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="relative">
      <Suspense fallback={null}><ParticleBg color="#a855f7" /></Suspense>

      {/* Hero */}
      <section className="text-center py-12 mb-8">
        <h1 className="font-display text-3xl sm:text-5xl font-extrabold mb-4">
          <span className="text-gradient">看见你的音乐情绪</span>
        </h1>
        <p className="text-slate-400 max-w-xl mx-auto">
          用 AI 解析每首歌的情绪，用粒子与雷达图可视化呈现你的听歌画像
        </p>
        <button
          onClick={syncAppleMusic}
          disabled={syncing}
          className="btn-neon mt-6 disabled:opacity-50"
        >
          <Sparkles className="w-4 h-4" />
          {syncing ? '同步中...' : '同步 Apple Music 听歌记录'}
        </button>
        {syncMsg && (
          <p className={`mt-3 text-sm ${syncMsg.includes('成功') ? 'text-neon-cyan' : 'text-red-400'}`}>
            {syncMsg}
          </p>
        )}
      </section>

      {/* 推荐区 */}
      {recs.length > 0 && (
        <section className="mb-10">
          <h2 className="font-display text-xl font-bold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-neon-amber" />
            为你推荐
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {recs.map((song) => (
              <SongCard key={song.id} song={song} />
            ))}
          </div>
        </section>
      )}

      {/* 风格相似推荐区 */}
      {styleRecs && styleRecs.recommendations.length > 0 && (
        <section className="mb-10">
          <h2 className="font-display text-xl font-bold mb-2 flex items-center gap-2">
            <Compass className="w-5 h-5 text-neon-purple" />
            风格相似推荐
          </h2>
          {styleRecs.preference && (
            <p className="text-sm text-slate-400 mb-4">
              你偏爱风格：
              {styleRecs.preference.top_genres.map(([genre, count]) => (
                <span key={genre} className="ml-1.5 inline-block px-2 py-0.5 rounded bg-neon-purple/10 text-neon-purple text-xs">
                  {genre} ×{count}
                </span>
              ))}
              {styleRecs.preference.top_emotion && (
                <span className="ml-1.5 inline-block px-2 py-0.5 rounded bg-neon-pink/10 text-neon-pink text-xs">
                  {styleRecs.preference.top_emotion}
                </span>
              )}
            </p>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {styleRecs.recommendations.map(({ song, reason }) => (
              <div key={song.id} className="flex flex-col">
                <SongCard song={song} />
                <p className="text-xs text-slate-500 mt-1.5 leading-relaxed line-clamp-2">
                  {reason}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 全部歌曲 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl font-bold flex items-center gap-2">
            <Music className="w-5 h-5 text-neon-cyan" />
            音乐库
          </h2>
          <button
            onClick={clearApple}
            disabled={clearing || songs.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 border border-white/10 hover:border-red-500/40 transition-all disabled:opacity-40 disabled:hover:text-slate-400 disabled:hover:bg-transparent disabled:hover:border-white/10"
          >
            <Trash2 className={`w-4 h-4 ${clearing ? 'animate-pulse' : ''}`} />
            {clearing ? '清空中…' : '清空'}
          </button>
        </div>
        {clearMsg && (
          <p className={`text-sm mb-3 ${clearMsg.includes('成功') || clearMsg.includes('清空') ? 'text-neon-cyan' : 'text-red-400'}`}>
            {clearMsg}
          </p>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {songs.map((song) => (
            <SongCard key={song.id} song={song} />
          ))}
        </div>
        {songs.length === 0 && (
          <p className="text-sm text-slate-500 text-center py-8">
            暂无歌曲，点击上方按钮同步 Apple Music 听歌记录
          </p>
        )}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg text-sm text-slate-300 hover:text-white border border-white/10 hover:border-neon-purple/40 transition-all disabled:opacity-40 disabled:hover:text-slate-300 disabled:hover:border-white/10"
            >
              上一页
            </button>
            <span className="text-sm text-slate-400">
              第 {page} / {totalPages} 页 · 共 {total} 首
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg text-sm text-slate-300 hover:text-white border border-white/10 hover:border-neon-purple/40 transition-all disabled:opacity-40 disabled:hover:text-slate-300 disabled:hover:border-white/10"
            >
              下一页
            </button>
          </div>
        )}
      </section>
    </div>
  )
}

function SongCard({ song }: { song: SongOut }) {
  const isAlbum = song.type === 'albums'
  return (
    <Link to={`/song/${song.id}`} className="card group cursor-pointer">
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
        ) : (
          <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
        )}
      </div>
      <h3 className="font-medium text-sm truncate group-hover:text-neon-cyan transition-colors flex items-center gap-1">
        {isAlbum && <Disc className="w-3.5 h-3.5 text-neon-purple/60 flex-shrink-0" />}
        {!isAlbum && <Music className="w-3.5 h-3.5 text-neon-cyan/60 flex-shrink-0" />}
        {song.title}
      </h3>
      <p className="text-xs text-slate-500 truncate">{song.artist}</p>
    </Link>
  )
}
