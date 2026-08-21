import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Disc, Music, Radar, Sparkles } from 'lucide-react'
import { emotionApi, songsApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import EmotionRadar from '../components/EmotionRadar'
import type { PredictionData, RadarData, RadarDimension, SongOut } from '../types'

// 每个维度的三档详细解析（低/中/高），在音频特征基础上给出听觉层面的解读
const DIMENSION_INFO: {
  key: keyof RadarDimension
  label: string
  desc: string
  analysis: { low: string; mid: string; high: string }
}[] = [
  {
    key: 'loudness',
    label: '响度',
    desc: '声音的整体音量能量',
    analysis: {
      low: '整体音量收敛克制，弱音细节丰富，更强调氛围的铺垫而非直接的冲击力。',
      mid: '音量能量处于均衡区间，既有足够的力度支撑情绪，又不至于过于炸耳。',
      high: '能量感十足，听感冲击力强，情绪浓度被显著放大，表达非常直给。',
    },
  },
  {
    key: 'high_freq',
    label: '高频',
    desc: '高频段能量占比，决定明亮感',
    analysis: {
      low: '高频能量被弱化，音色偏暖偏暗，容易营造出沉浸、内敛的听感。',
      mid: '高频占比适中，明亮感与温暖感较为平衡，听起来通透而不刺耳。',
      high: '高频段能量突出，听感明亮通透，音色带有晶莹的光泽与空气感。',
    },
  },
  {
    key: 'rhythm',
    label: '节奏',
    desc: '节拍密度与律动强度',
    analysis: {
      low: '节拍稀疏舒缓，留白较多，强调呼吸感与情绪的延展。',
      mid: '节奏感适度，律动清晰但不喧宾夺主，能稳住听感的骨架。',
      high: '节拍密集、律动感强，具有明显的驱动力和推进感，让人忍不住随之摇摆。',
    },
  },
  {
    key: 'soundstage',
    label: '声场',
    desc: '左右声道分离与空间广度',
    analysis: {
      low: '声场相对集中，声音更加贴近耳畔，带来亲密、私密的聆听体验。',
      mid: '声场宽度适中，层次清楚但不刻意铺展，平衡了包裹感与清晰度。',
      high: '声像开阔，左右分离度大，空间感与环绕感极强，仿佛置身演出之中。',
    },
  },
  {
    key: 'layering',
    label: '层次',
    desc: '声部编排的复杂与丰富程度',
    analysis: {
      low: '编配精简克制，以单一主线撑起听感，专注而不杂乱。',
      mid: '编曲层次适度，主次分明，既能感受到细节又不显堆砌。',
      high: '声部编排丰富，多轨叠加带来立体丰满的听觉层次，值得反复细品。',
    },
  },
  {
    key: 'soothing',
    label: '舒缓',
    desc: '情绪上的放松与柔和程度',
    analysis: {
      low: '情绪张力较强，听感偏紧，带有明显的冲击感与压迫感。',
      mid: '情绪张力适中，放松与起伏并存，张弛有度。',
      high: '情绪非常松弛柔和，带来治愈、安定的听感，紧绷的神经也随之松开。',
    },
  },
  {
    key: 'prosody',
    label: '韵律',
    desc: '旋律起伏与音调变化',
    analysis: {
      low: '旋律线平缓，起伏克制，强调氛围的渲染而非旋律的强调。',
      mid: '旋律线稳定，起伏自然不夸张，流畅且耐听。',
      high: '旋律起伏大、音调变化丰富，富有歌唱性与叙事感，情绪随之流动。',
    },
  },
]

// 20 种情绪的一句话全貌解读
const EMOTION_SUMMARY: Record<string, string> = {
  甜蜜: '甜度满格的粉红泡泡，暖意直抵心底。',
  浪漫: '暧昧与心动交织，空气里都是温柔的试探。',
  治愈: '像午后阳光一样，轻柔地抚平褶皱的情绪。',
  悲伤: '沉入深海的安静，眼泪在旋律里慢慢蒸发。',
  孤独: '一个人的留白，孤独但并不狼狈。',
  深情: '克制又浓烈的告白，每一句都写进心里。',
  欢快: '不假思索的快乐，阳光、多巴胺与跳跃的节奏。',
  愤怒: '压抑不住的爆发，力道与躁动扑面而来。',
  宁静: '万物归于寂静，连呼吸都变得缓慢。',
  热血: '燃烧的引擎与沸腾的血液，燃点一触即发。',
  忧郁: '灰蓝色的心事，淡淡的失落绕成一圈雾。',
  激昂: '层层推进的情绪浪潮，由内而外喷薄而出。',
  松弛: '瘫进沙发的慵懒，世界慢下来也没关系。',
  梦幻: '半梦半醒的漂浮感，像糖纸折射出的光。',
  震撼: '声浪迎面压来的极致体验，感官被完全包裹。',
  舒缓: '水流般的抚触，紧绷的神经一点点松开。',
  自由: '无拘无束的奔跑感，风从耳边掠过。',
  空灵: '来自远方的回响，通透得仿佛没有重量。',
  狂野: '不加修饰的本能，原始而野性的冲动。',
  迷幻: '循环铺叠的漩涡，意识在声场里轻轻打转。',
}

const LEVEL_LABEL: Record<'low' | 'mid' | 'high', string> = {
  low: '偏低',
  mid: '均衡',
  high: '突出',
}

// 生成与主色对比鲜明的互补色，用于模板轮廓，避免与主题色混淆
function contrastColor(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  let h = 0
  let s = 0
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) * 60
    else if (max === g) h = ((b - r) / d + 2) * 60
    else h = ((r - g) / d + 4) * 60
  }
  h = (h + 180) % 360
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  let rr = 0, gg = 0, bb = 0
  if (h < 60) [rr, gg, bb] = [c, x, 0]
  else if (h < 120) [rr, gg, bb] = [x, c, 0]
  else if (h < 180) [rr, gg, bb] = [0, c, x]
  else if (h < 240) [rr, gg, bb] = [0, x, c]
  else if (h < 300) [rr, gg, bb] = [x, 0, c]
  else [rr, gg, bb] = [c, 0, x]
  const toHex = (v: number) =>
    Math.round((v + m) * 255).toString(16).padStart(2, '0')
  return `#${toHex(rr)}${toHex(gg)}${toHex(bb)}`
}

const getLevel = (value: number): 'low' | 'mid' | 'high' =>
  value >= 67 ? 'high' : value <= 33 ? 'low' : 'mid'

const LABEL_MAP = Object.fromEntries(DIMENSION_INFO.map((d) => [d.key, d.label])) as Record<
  keyof RadarDimension,
  string
>

export default function SongRadar() {
  const { id } = useParams<{ id: string }>()
  const [song, setSong] = useState<SongOut | null>(null)
  const [radar, setRadar] = useState<RadarData | null>(null)
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)

  // 直接在当前页面触发 AI 分析，成功后刷新雷达数据
  const handleAnalyze = async () => {
    if (!id || analyzing) return
    setAnalyzing(true)
    try {
      const { data } = await emotionApi.analyze(Number(id))
      setPrediction(data)
      const radarRes = await emotionApi.getRadar(Number(id))
      setRadar(radarRes.data)
    } catch (err: any) {
      alert(err?.response?.data?.detail || '分析失败')
    } finally {
      setAnalyzing(false)
    }
  }

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
  const emotion = prediction?.emotion || radar?.emotion || ''
  // 模板轮廓使用与主题色互补的高对比色
  const templateColor = radar?.template ? contrastColor(color) : '#e2e8f0'

  // 按数值排序各维度，用于整体解析中的强弱特征
  const dimEntries = radar
    ? (Object.entries(radar.dimensions) as [keyof RadarDimension, number][]).sort(
        (a, b) => b[1] - a[1],
      )
    : []
  const strongest = dimEntries.slice(0, 2)
  const weakest = dimEntries.slice(-1)[0]

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
                {prediction ? (
                  // 与歌曲详情页一致的完整情绪展示：主情绪 + 置信度 + 次情绪徽章
                  <div
                    className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full"
                    style={{ background: `${color}20`, border: `1px solid ${color}50` }}
                  >
                    <Sparkles className="w-3.5 h-3.5" style={{ color }} />
                    <span className="text-sm font-medium" style={{ color }}>
                      {prediction.emotion}
                      {prediction.fuzzy && (
                        <span className="ml-1.5 text-xs text-amber-400">· 情绪模糊</span>
                      )}
                    </span>
                    <span className="text-xs text-slate-500">
                      · 置信度 {(prediction.confidence * 100).toFixed(0)}%
                    </span>
                    {prediction.top_emotions && prediction.top_emotions.length > 1 && (
                      <span className="flex items-center gap-1.5">
                        {prediction.top_emotions.slice(1).map((t) => (
                          <span
                            key={t.name}
                            className="text-xs px-2 py-0.5 rounded-full border border-slate-500/40 text-slate-300"
                            style={{ background: `${t.color}18` }}
                          >
                            {t.name} {(t.prob * 100).toFixed(0)}%
                          </span>
                        ))}
                      </span>
                    )}
                  </div>
                ) : (
                  <span
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                    style={{ background: `${color}20`, border: `1px solid ${color}50`, color }}
                  >
                    <Sparkles className="w-3 h-3" />
                    {emotion || '未分析'}
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
              {radar.template && (
                <div className="flex items-center justify-center gap-5 mb-4 text-xs text-slate-400">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="w-5 h-1 rounded-full"
                      style={{ background: `linear-gradient(90deg, ${color}66, ${color})` }}
                    />
                    歌曲实测画像
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="w-5 border-t-2 border-dashed"
                      style={{ borderColor: templateColor }}
                    />
                    {radar.emotion} 标准模板
                  </span>
                </div>
              )}
              <EmotionRadar
                dimensions={radar.dimensions}
                color={radar.color}
                maxSize={560}
                template={radar.template}
                templateColor={templateColor}
              />
            </div>

            {/* 整体情绪解析 */}
            <div className="glass p-6 rounded-2xl mb-6">
              <h3 className="font-display font-bold mb-1">整体情绪解析</h3>
              <p className="text-sm text-slate-500 mb-4">
                综合主情绪标签与多维音频特征生成的听觉画像
              </p>

              {/* 多标签情绪占比 */}
              {prediction?.top_emotions && prediction.top_emotions.length > 0 && (
                <div className="mb-5 space-y-2">
                  {prediction.top_emotions.map((e) => (
                    <div key={e.name} className="flex items-center gap-2 text-sm">
                      <span className="w-10 flex-shrink-0 text-slate-400 truncate">{e.name}</span>
                      <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${e.prob * 100}%`,
                            background: `linear-gradient(90deg, ${e.color}66, ${e.color})`,
                          }}
                        />
                      </div>
                      <span className="w-10 text-right tabular-nums text-slate-500">
                        {(e.prob * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* 主情绪一句话解读 */}
              <div className="flex items-start gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/5 mb-4">
                <Sparkles className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color }} />
                <p className="text-sm leading-relaxed text-slate-300">
                  <span className="font-medium" style={{ color }}>
                    {emotion}：
                  </span>
                  {EMOTION_SUMMARY[emotion] || `这首歌呈现出明显的「${emotion}」气质。`}
                  {prediction && ` AI 对该判断的置信度为 ${(prediction.confidence * 100).toFixed(0)}%。`}
                  {prediction?.fuzzy && '（多标签边界较模糊，存在多重情绪交织的可能。）'}
                </p>
              </div>

              {/* 强弱特征总结 */}
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
                  <p className="text-xs font-medium text-slate-400 mb-1.5">最突出的特征</p>
                  <p className="text-sm leading-relaxed text-slate-300">
                    「{strongest.map(([k, v]) => `${LABEL_MAP[k]} ${Math.round(v)}`).join(' · ')}」是
                    这首歌情绪最鲜明的支点，构成了整体听感的第一印象。
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
                  <p className="text-xs font-medium text-slate-400 mb-1.5">最克制的特征</p>
                  <p className="text-sm leading-relaxed text-slate-300">
                    {weakest
                      ? `${LABEL_MAP[weakest[0]]}（${Math.round(weakest[1])}）最为克制，为整体听感留出了呼吸与留白的空间。`
                      : ''}
                  </p>
                </div>
              </div>
            </div>

            {/* 维度详情 */}
            <div className="glass p-6 rounded-2xl">
              <h3 className="font-display font-bold mb-1">维度解读</h3>
              <p className="text-sm text-slate-500 mb-4">每个维度的数值区间对应不同的听觉感受</p>
              <div className="grid sm:grid-cols-2 gap-3">
                {DIMENSION_INFO.map((d) => {
                  const value = radar.dimensions[d.key] ?? 0
                  const level = getLevel(value)
                  const tplValue = radar.template?.[d.key] ?? null
                  const tplLevel = tplValue !== null ? getLevel(tplValue) : null
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
                      {/* 主情绪模板在该维度的画像对比 */}
                      {tplValue !== null && (
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className="w-14 flex-shrink-0 text-[11px] text-slate-500 truncate"
                            title={`${emotion} 标准模板`}
                          >
                            {emotion}模板
                          </span>
                          <div className="flex-1 h-1 rounded-full bg-white/5 overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${tplValue}%`,
                                background: templateColor,
                                opacity: 0.85,
                              }}
                            />
                          </div>
                          <span
                            className="w-7 text-right text-[11px] font-semibold tabular-nums"
                            style={{ color: templateColor }}
                          >
                            {Math.round(tplValue)}
                          </span>
                        </div>
                      )}
                      <p className="text-xs text-slate-500">{d.desc}</p>
                      <div className="mt-2 pt-2 border-t border-white/5 space-y-1.5">
                        <p className="text-xs leading-relaxed text-slate-400">
                          <span className="font-medium" style={{ color }}>
                            实测·{LEVEL_LABEL[level]}：
                          </span>
                          {d.analysis[level]}
                        </p>
                        {tplValue !== null && tplLevel && (
                          <p className="text-[11px] leading-relaxed text-slate-500">
                            <span className="font-medium" style={{ color: templateColor }}>
                              「{emotion}」典型画像：
                            </span>
                            {d.analysis[tplLevel]}
                          </p>
                        )}
                      </div>
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
              点击下方按钮，AI 将分析试听音频并生成专属情绪雷达图
            </p>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-neon-purple/30 hover:border-neon-purple/60 transition-all disabled:opacity-60"
            >
              <Sparkles className="w-4 h-4 text-neon-purple" />
              {analyzing ? '分析中...' : '去分析'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
