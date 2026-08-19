import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Disc, Music } from 'lucide-react'
import { usersApi } from '../api/client'
import type { SongOut } from '../types'

export default function UserProfile() {
  const { id } = useParams<{ id: string }>()
  const [songs, setSongs] = useState<SongOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError('')
    usersApi
      .songs(Number(id))
      .then(({ data }) => setSongs(data.items))
      .catch((err: any) => {
        setError(err?.response?.data?.detail || '加载失败')
      })
      .finally(() => setLoading(false))
  }, [id])

  return (
    <div className="relative">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        返回首页
      </Link>

      <h1 className="font-display text-2xl font-bold mb-1">
        用户 <span className="text-neon-cyan">@{id}</span> 的歌单
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        该用户同步/分析的专辑与播放列表，共 {songs.length} 个
      </p>

      {loading ? (
        <p className="text-sm text-slate-500 text-center py-10">加载中…</p>
      ) : error ? (
        <p className="text-sm text-red-400 text-center py-10">{error}</p>
      ) : songs.length === 0 ? (
        <p className="text-sm text-slate-500 text-center py-10">该用户还没有歌单</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {songs.map((song) => (
            <UserSongCard key={song.id} song={song} />
          ))}
        </div>
      )}
    </div>
  )
}

function UserSongCard({ song }: { song: SongOut }) {
  const isAlbum = song.type === 'albums'
  const isPlaylist = song.type === 'playlists'
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
        ) : isPlaylist ? (
          <Music className="w-10 h-10 text-red-400/40 group-hover:scale-110 transition-transform" />
        ) : (
          <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
        )}
      </div>
      <h3 className="font-medium text-sm truncate group-hover:text-neon-cyan transition-colors">
        {song.title}
      </h3>
      <p className="text-xs text-slate-500 truncate">{song.artist}</p>
      {isPlaylist && <p className="text-[10px] text-red-400/70 mt-1">歌单</p>}
    </Link>
  )
}
