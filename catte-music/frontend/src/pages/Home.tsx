import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Disc, Music, TrendingUp, Sparkles, Compass } from 'lucide-react'
import { songsApi, appleMusicApi, recommendApi, authApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import type { SongOut, StyleRecommendResult } from '../types'

// MusicKit JS 全局类型
declare global {
  interface Window {
    MusicKit: any
  }
}

export default function Home() {
  const [songs, setSongs] = useState<SongOut[]>([])
  const [recs, setRecs] = useState<SongOut[]>([])
  const [styleRecs, setStyleRecs] = useState<StyleRecommendResult | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')

  useEffect(() => {
    songsApi.list({ size: 12 }).then(({ data }) => setSongs(data.items)).catch(() => {})
    recommendApi.get(6).then(({ data }) => setRecs(data)).catch(() => {})
    recommendApi.getStyle(6).then(({ data }) => setStyleRecs(data)).catch(() => {})
  }, [])

  const syncAppleMusic = async () => {
    setSyncing(true)
    setSyncMsg('')
    try {
      // 1. 获取 Developer Token
      const { data: config } = await authApi.appleMusicConfig()

      // 2. 配置 MusicKit JS
      const MusicKit = window.MusicKit
      if (!MusicKit) {
        setSyncMsg('MusicKit JS 未加载，请刷新页面重试')
        return
      }
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
      setSyncMsg('同步成功！')
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
      <ParticleBg color="#a855f7" />

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
        <h2 className="font-display text-xl font-bold mb-4 flex items-center gap-2">
          <Music className="w-5 h-5 text-neon-cyan" />
          音乐库
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {songs.map((song) => (
            <SongCard key={song.id} song={song} />
          ))}
        </div>
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
