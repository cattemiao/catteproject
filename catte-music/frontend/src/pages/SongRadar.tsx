import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Disc, Music, Radar, Sparkles } from 'lucide-react'
import { emotionApi, songsApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import EmotionRadar from '../components/EmotionRadar'
import type { PredictionData, RadarData, SongOut } from '../types'

const DIMENSION_INFO: { key: string; label: string; desc: string }[] = [
  { key: 'loudness', label: '响度', desc: '声音的整体音量能量' },
  { key: 'high_freq', label: '高频', desc: '高频段能量占比，决定明亮感' },
  { key: 'rhythm', label: '节奏', desc: '节拍密度与律动强度' },
  { key: 'soundstage', label: '声场', desc: '左右声道分离与空间广度' },
  { key: 'layering', label: '层次', desc: '声部编排的复杂与丰富程度' },
  { key: 'soothing', label: '舒缓', desc: '情绪上的放松与柔和程度' },
  { key: 'prosody', label: '韵律', desc: '旋律起伏与音调变化' },
]

export default function SongRadar() {
  const { id } = useParams<{ id: string }>()
  const [song, setSong] = useState<SongOut | null>(null)
  const [radar, setRadar] = useState<RadarData | null>(null)
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    const songId = Number(id)
    Promise.all([
      songsApi.get(songId).then(({ data }) => setSong(data)),
      emotionApi.getRadar(songId).then(({ data }) => setRadar(data)),
      emotionApi.getSongEmotion(songId).then(({ data }) => setPrediction(data)),
    ])
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  const color = radar?.color || prediction?.color || '#a855f7'

  return (
    <div className="relative min-h-[calc(100dvh-64px)]">
      <ParticleBg color={color} />

      <div className="max-w-4xl mx-auto pt-4">
        {/* 返回按钮 */}
        <Link
          to={`/song/${id}`}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-all mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          返回歌曲详情
        </Link>

        {/* 歌曲信息头 */}
        {song && (
          <div className="flex items-center gap-4 mb-8">
            <div
              className="w-16 h-16 rounded-xl overflow-hidden flex items-center justify-center flex-shrink-0"
              style={{
                background: song.artwork_url ? 'transparent' : `linear-gradient(135deg, ${color}40, ${color}10)`,
                boxShadow: `0 0 25px ${color}30`,
              }}
            >
              {song.artwork_url ? (
                <img src={song.artwork_url} alt={song.title} className="w-full h-full object-cover" />
              ) : (
                <Music className="w-7 h-7 text-white/50" />
              )}
            </div>
            <div className="min-w-0">
              <h1 className="font-display text-xl sm:text-2xl font-bold truncate flex items-center gap-2">
                {song.type === 'albums'
                  ? <Disc className="w-5 h-5 text-neon-purple/70 flex-shrink-0" />
                  : <Music className="w-5 h-5 text-neon-cyan/70 flex-shrink-0" />}
                {song.title}
              </h1>
              <p className="text-slate-400 text-sm truncate">{song.artist}</p>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                  style={{ background: `${color}20`, border: `1px solid ${color}50`, color }}
                >
                  <Sparkles className="w-3 h-3" />
                  {prediction?.emotion || radar?.emotion || '未分析'}
                </span>
                {prediction && (
                  <span className="text-xs text-slate-500">
                    置信度 {(prediction.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <div className="glass p-10 text-center text-slate-400">加载中...</div>
        ) : radar ? (
          <>
            {/* 大尺寸雷达图 */}
            <div className="glass p-6 sm:p-10 rounded-2xl mb-6">
              <h2 className="font-display text-lg font-bold mb-2 text-center flex items-center justify-center gap-2">
                <Radar className="w-5 h-5" style={{ color }} />
                情绪雷达图
              </h2>
              <p className="text-center text-slate-500 text-sm mb-4">
                {song?.title} · 情绪画像全维度解读
              </p>
              <EmotionRadar dimensions={radar.dimensions} color={radar.color} maxSize={560} />
            </div>

            {/* 维度详情 */}
            <div className="glass p-6 rounded-2xl">
              <h3 className="font-display font-bold mb-4">维度解读</h3>
              <div className="grid sm:grid-cols-2 gap-3">
                {DIMENSION_INFO.map((d) => {
                  const value = radar.dimensions[d.key as keyof RadarData['dimensions']] ?? 0
                  return (
                    <div key={d.key} className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm font-medium text-slate-200">{d.label}</span>
                        <span className="text-sm font-bold tabular-nums" style={{ color }}>
                          {Math.round(value)}
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden mb-1.5">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${value}%`,
                            background: `linear-gradient(90deg, ${color}66, ${color})`,
                            boxShadow: `0 0 8px ${color}80`,
                          }}
                        />
                      </div>
                      <p className="text-xs text-slate-500">{d.desc}</p>
                    </div>
                  )
                })}
              </div>
            </div>
          </>
        ) : (
          <div className="glass p-14 rounded-2xl text-center">
            <Radar className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <p className="text-slate-300 font-medium mb-1">暂无情绪分析数据</p>
            <p className="text-sm text-slate-500 mb-6">
              返回歌曲详情页，点击「AI 情绪分析」按钮即可生成专属情绪雷达图
            </p>
            <Link
              to={`/song/${id}`}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-neon-purple/30 hover:border-neon-purple/60 transition-all"
            >
              <Sparkles className="w-4 h-4 text-neon-purple" />
              去分析
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
