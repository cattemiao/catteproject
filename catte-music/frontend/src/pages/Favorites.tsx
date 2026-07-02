import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Heart, Music } from 'lucide-react'
import { songsApi } from '../api/client'
import type { SongOut } from '../types'

export default function Favorites() {
  const [songs, setSongs] = useState<SongOut[]>([])

  useEffect(() => {
    // 收藏列表接口可扩展为 /api/favorites，这里暂复用歌曲列表
    songsApi.list({ size: 50 }).then(({ data }) => setSongs(data.items)).catch(() => {})
  }, [])

  return (
    <div>
      <h1 className="font-display text-2xl font-bold mb-6 flex items-center gap-2">
        <Heart className="w-6 h-6 text-neon-pink" />
        我的收藏
      </h1>

      {songs.length === 0 ? (
        <div className="text-center text-slate-500 py-20">
          <Music className="w-12 h-12 mx-auto mb-4 opacity-40" />
          <p>还没有收藏的歌曲</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {songs.map((song) => (
            <Link key={song.id} to={`/song/${song.id}`} className="card group cursor-pointer">
              <div className="aspect-square rounded-xl bg-gradient-to-br from-neon-pink/30 to-neon-purple/20 mb-3 flex items-center justify-center">
                <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
              </div>
              <h3 className="font-medium text-sm truncate group-hover:text-neon-cyan transition-colors">
                {song.title}
              </h3>
              <p className="text-xs text-slate-500 truncate">{song.artist}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
