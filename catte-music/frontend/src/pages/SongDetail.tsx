import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Heart, Play, Sparkles } from 'lucide-react'
import { emotionApi, songsApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import EmotionRadar from '../components/EmotionRadar'
import type { PredictionData, RadarData, SongOut } from '../types'

export default function SongDetail() {
  const { id } = useParams<{ id: string }>()
  const [song, setSong] = useState<SongOut | null>(null)
  const [radar, setRadar] = useState<RadarData | null>(null)
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [favLoading, setFavLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    const songId = Number(id)
    songsApi.get(songId).then(({ data }) => setSong(data)).catch(() => {})
    emotionApi.getRadar(songId).then(({ data }) => setRadar(data)).catch(() => {})
    emotionApi.getSongEmotion(songId).then(({ data }) => setPrediction(data)).catch(() => {})
  }, [id])

  const emotionColor = prediction?.color || '#a855f7'

  const toggleFavorite = async () => {
    if (!song) return
    setFavLoading(true)
    try {
      await songsApi.favorite(song.id)
    } finally {
      setFavLoading(false)
    }
  }

  return (
    <div className="relative min-h-[calc(100dvh-64px)]">
      <ParticleBg color={emotionColor} />

      <div className="grid lg:grid-cols-2 gap-8 items-start pt-4">
        {/* 左侧：封面与信息 */}
        <div className="text-center lg:text-left">
          <div
            className="aspect-square max-w-sm mx-auto rounded-2xl mb-6 flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${emotionColor}40, ${emotionColor}10)`,
              boxShadow: `0 0 50px ${emotionColor}30`,
            }}
          >
            <Play className="w-16 h-16 text-white/60" />
          </div>

          {song && (
            <>
              <h1 className="font-display text-2xl sm:text-3xl font-bold mb-2">{song.title}</h1>
              <p className="text-slate-400 mb-4">{song.artist}</p>
              {song.album && <p className="text-slate-500 text-sm">{song.album}</p>}
            </>
          )}

          {/* 情绪标签 */}
          {prediction && (
            <div className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-full"
              style={{
                background: `${emotionColor}20`,
                border: `1px solid ${emotionColor}50`,
              }}
            >
              <Sparkles className="w-4 h-4" style={{ color: emotionColor }} />
              <span className="font-medium" style={{ color: emotionColor }}>
                {prediction.emotion}
              </span>
              <span className="text-slate-500 text-sm">
                · 置信度 {(prediction.confidence * 100).toFixed(0)}%
              </span>
            </div>
          )}

          <div className="flex items-center justify-center lg:justify-start gap-3 mt-6">
            <button className="btn-neon">
              <Play className="w-4 h-4" />
              播放
            </button>
            <button
              onClick={toggleFavorite}
              disabled={favLoading}
              className="glass px-4 py-3 rounded-xl hover:border-neon-pink/50 transition-all"
            >
              <Heart className="w-5 h-5 text-neon-pink" />
            </button>
          </div>
        </div>

        {/* 右侧：雷达图 */}
        <div className="glass p-6 lg:p-8">
          <h2 className="font-display text-lg font-bold mb-4 text-center">情绪雷达图</h2>
          {radar ? (
            <EmotionRadar dimensions={radar.dimensions} color={radar.color} />
          ) : (
            <div className="text-center text-slate-500 py-20">
              <p>暂无情绪分析数据</p>
              <p className="text-sm mt-1">需先对该歌曲进行 AI 分析</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
