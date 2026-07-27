import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowLeft, Image, Music, Sparkles } from 'lucide-react'
import { songsApi } from '../api/client'

interface LyricsSegment {
  index: number
  lyrics: string
  image_prompt: string
  image_url?: string | null
}

interface LyricsData {
  song_id: number
  title: string
  artist: string
  artwork_url?: string | null
  emotion: string
  raw_lyrics: string
  source: string
  gallery: LyricsSegment[]
}

export default function LyricsGallery() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<LyricsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeSegment, setActiveSegment] = useState(0)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    songsApi.getLyrics(Number(id))
      .then(({ data }) => setData(data as LyricsData))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-20 text-slate-400">
        <p>歌词数据不可用</p>
        <p className="text-sm mt-2 text-slate-500">该歌曲可能暂无歌词信息</p>
      </div>
    )
  }

  const segment = data.gallery[activeSegment]

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button
          onClick={() => window.history.back()}
          className="glass p-2 rounded-xl hover:border-neon-purple/50 transition-all"
        >
          <ArrowLeft className="w-5 h-5 text-slate-400" />
        </button>
        <div className="flex-1">
          <h1 className="font-display text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Image className="w-5 h-5 text-neon-purple" />
            AI 歌词配图
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {data.title} — {data.artist}
          </p>
          {data.emotion && (
            <span className="inline-flex items-center gap-1 mt-1 text-xs text-neon-purple">
              <Sparkles className="w-3 h-3" />
              AI 情绪：{data.emotion}
            </span>
          )}
        </div>
      </div>

      {data.gallery.length === 0 ? (
        <div className="text-center py-20 text-slate-500">
          <Music className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p>{data.source === 'unavailable' ? 'Apple Music 未提供该歌曲歌词' : '暂无歌词段落'}</p>
        </div>
      ) : (
        <div className="grid lg:grid-cols-2 gap-6">
          {/* 左侧：配图 */}
          <div className="glass p-4 rounded-2xl flex flex-col items-center justify-center min-h-[300px]">
            {segment?.image_url ? (
              <img
                src={segment.image_url}
                alt={`${data.title} 配图`}
                className="max-w-full max-h-[400px] rounded-xl object-cover"
              />
            ) : data.artwork_url ? (
              <img
                src={data.artwork_url}
                alt={data.title}
                className="max-w-full max-h-[400px] rounded-xl object-cover shadow-[0_0_40px_rgba(168,85,247,0.3)]"
              />
            ) : (
              <div className="flex flex-col items-center gap-3 text-slate-500">
                <Image className="w-16 h-16 opacity-30" />
                <p className="text-sm">配图待生成</p>
                <p className="text-xs text-slate-600 max-w-xs text-center leading-relaxed">
                  接入 AI 图像生成 API（如 Stable Diffusion / Replicate）后可自动生成对应意境的配图
                </p>
              </div>
            )}
          </div>

          {/* 右侧：歌词段落 */}
          <div className="glass p-6 rounded-2xl">
            <h3 className="font-display text-sm font-bold text-slate-400 mb-4 uppercase tracking-wider">
              歌词段落
            </h3>
            <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
              {data.gallery.map((seg) => (
                <button
                  key={seg.index}
                  onClick={() => setActiveSegment(seg.index)}
                  className={`w-full text-left p-4 rounded-xl transition-all border ${
                    activeSegment === seg.index
                      ? 'bg-neon-purple/10 border-neon-purple/40 shadow-[0_0_15px_rgba(168,85,247,0.2)]'
                      : 'bg-white/[0.02] border-transparent hover:bg-white/[0.04] hover:border-white/10'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-mono ${
                      activeSegment === seg.index ? 'text-neon-purple' : 'text-slate-500'
                    }`}>
                      #{seg.index + 1}
                    </span>
                    <span className="text-xs text-slate-600">
                      {seg.lyrics.split('\n').length} 行
                    </span>
                  </div>
                  <p className={`text-sm leading-relaxed whitespace-pre-line ${
                    activeSegment === seg.index ? 'text-white' : 'text-slate-400'
                  }`}>
                    {seg.lyrics.slice(0, 200)}{seg.lyrics.length > 200 ? '...' : ''}
                  </p>
                </button>
              ))}
            </div>

            {/* AI 图片 Prompt */}
            {segment && (
              <div className="mt-6 pt-4 border-t border-white/5">
                <p className="text-xs text-slate-500 mb-2 font-medium">AI 图片生成提示词</p>
                <p className="text-xs text-slate-400 leading-relaxed bg-black/20 rounded-lg p-3 font-mono">
                  {segment.image_prompt}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}