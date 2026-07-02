import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Music, TrendingUp, Sparkles } from 'lucide-react'
import { songsApi, appleMusicApi, recommendApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import type { SongOut } from '../types'

export default function Home() {
  const [songs, setSongs] = useState<SongOut[]>([])
  const [recs, setRecs] = useState<SongOut[]>([])

  useEffect(() => {
    songsApi.list({ size: 12 }).then(({ data }) => setSongs(data.items)).catch(() => {})
    recommendApi.get(6).then(({ data }) => setRecs(data)).catch(() => {})
  }, [])

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
          onClick={() => appleMusicApi.recent(20).then(() => location.reload())}
          className="btn-neon mt-6"
        >
          <Sparkles className="w-4 h-4" />
          同步 Apple Music 听歌记录
        </button>
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
  return (
    <Link to={`/song/${song.id}`} className="card group cursor-pointer">
      <div className="aspect-square rounded-xl bg-gradient-to-br from-neon-purple/30 to-neon-blue/20 mb-3 flex items-center justify-center group-hover:shadow-[0_0_25px_rgba(168,85,247,0.3)] transition-all">
        <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
      </div>
      <h3 className="font-medium text-sm truncate group-hover:text-neon-cyan transition-colors">
        {song.title}
      </h3>
      <p className="text-xs text-slate-500 truncate">{song.artist}</p>
    </Link>
  )
}
