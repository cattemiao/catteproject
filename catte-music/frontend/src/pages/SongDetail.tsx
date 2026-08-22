import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, Disc, ExternalLink, ListMusic, Music, Pause, Play, Podcast, Radar, RefreshCw, Share2, ShieldCheck, Sparkles } from 'lucide-react'
import { authApi, emotionApi, neteaseApi, shareApi, songsApi } from '../api/client'
import { loadMusicKit } from '../utils/musicKit'
import type { FeedbackData, MusicBrainzData, PredictionData, RadarData, ReviewData, SongOut } from '../types'

// p5.js 粒子背景懒加载：不阻塞首屏
const ParticleBg = lazy(() => import('../components/ParticleBg'))

declare global {
  interface Window {
    MusicKit: any
  }
}

interface AlbumTrack {
  id: string
  title: string
  artist: string
  duration_ms?: number
  track_number?: number
  preview_url?: string | null
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function fmtDuration(ms: number): string {
  const m = Math.floor(ms / 60000)
  const s = Math.floor((ms % 60000) / 1000)
  return `${m}:${String(s).padStart(2, '0')}`
}

/** 从 raw_meta 提取 Apple Music / 网易云的补充字段（发行日期、曲目数、流派） */
function extractMeta(song: SongOut): { releaseDate?: string; trackCount?: number; genres: string[] } {
  const raw = song.raw_meta ?? {}
  const attrs =
    raw.attributes && typeof raw.attributes === 'object' ? raw.attributes : raw
  if (song.platform === 'netease') {
    // 网易云：专辑发行时间在 al.publishTime（毫秒时间戳）
    const publish = raw.al?.publishTime
    if (typeof publish === 'number' && publish > 0) {
      return { releaseDate: new Date(publish).toISOString().slice(0, 10), genres: [] }
    }
    return { genres: [] }
  }
  return {
    releaseDate: attrs.releaseDate,
    trackCount: attrs.trackCount,
    genres: Array.isArray(attrs.genreNames) ? attrs.genreNames : [],
  }
}

export default function SongDetail() {
  const { id } = useParams<{ id: string }>()
  const [song, setSong] = useState<SongOut | null>(null)
  const [radar, setRadar] = useState<RadarData | null>(null)
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [review, setReview] = useState<ReviewData | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [sharing, setSharing] = useState(false)
  const [shared, setShared] = useState(false)
  const [meId, setMeId] = useState<number | null>(null) // 当前登录用户 id（用于判断是否可分享）
  const [albumTracks, setAlbumTracks] = useState<AlbumTrack[]>([])
  const [albumLoading, setAlbumLoading] = useState(false)
  const [trackAudio, setTrackAudio] = useState<string | null>(null)
  const [trackPlaying, setTrackPlaying] = useState(false)
  // 整张播放模式：当前播放的曲目索引（null 表示未处于整张播放）
  const [playQueueIndex, setPlayQueueIndex] = useState<number | null>(null)
  // 网易云曲目行按需获取到的试听 URL 缓存（key 为 netease_id）
  const [trackUrls, setTrackUrls] = useState<Record<string, string>>({})
  const [loadingTrackId, setLoadingTrackId] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [seeking, setSeeking] = useState(false)
  const [useMusicKit, setUseMusicKit] = useState(false)
  const [musicKitAuthorized, setMusicKitAuthorized] = useState(false)
  const [feedback, setFeedback] = useState<FeedbackData | null>(null)
  const [musicBrainz, setMusicBrainz] = useState<MusicBrainzData | null>(null)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const progressRef = useRef<HTMLInputElement | null>(null)
  const musicKitRef = useRef<any>(null)

  // Check MusicKit availability（按需加载，失败静默回退到 preview）
  useEffect(() => {
    let cancelled = false
    loadMusicKit()
      .then((mk) => {
        if (cancelled) return
        try {
          const instance = mk.getInstance()
          if (instance && instance.isAuthorized) {
            setMusicKitAuthorized(true)
            musicKitRef.current = instance
          }
        } catch { /* MusicKit not configured */ }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!id) return
    const songId = Number(id)
    songsApi.get(songId).then(({ data }) => {
      setSong(data)
      if (data.preview_url) setPreviewUrl(data.preview_url)
    }).catch(() => {})
    emotionApi.getRadar(songId).then(({ data }) => setRadar(data)).catch(() => {})
    emotionApi.getSongEmotion(songId).then(({ data }) => setPrediction(data)).catch(() => {})
    songsApi.getReview(songId).then(({ data }) => setReview(data)).catch(() => {})
    songsApi.getFeedback(songId).then(({ data }) => setFeedback(data)).catch(() => {})
    songsApi.getMusicBrainz(songId).then(({ data }) => setMusicBrainz(data)).catch(() => {})
    // 恢复分享按钮状态：已分享过的内容刷新后仍显示「已分享」
    shareApi.status(songId).then(({ data }) => setShared(data.shared)).catch(() => {})
  }, [id])

  // 当前登录用户 id：判断歌曲是否属于自己（别人的内容不显示分享按钮）
  useEffect(() => {
    authApi.me().then(({ data }) => setMeId(data.id)).catch(() => {})
  }, [])

  // MusicKit player event listeners
  useEffect(() => {
    const mk = musicKitRef.current
    if (!mk) return

    const onTimeChange = (evt: any) => {
      if (!seeking) setCurrentTime(evt.currentPlaybackTime || 0)
    }
    const onDurationChange = (evt: any) => {
      setDuration(evt.duration || 0)
    }
    const onStateChange = (evt: any) => {
      const state = evt.state
      setPlaying(state === 2 || state === 3 || state === 8) // playing, waiting, seeking
    }

    mk.player.addEventListener('playbackTimeDidChange', onTimeChange)
    mk.player.addEventListener('playbackDurationDidChange', onDurationChange)
    mk.player.addEventListener('playbackStateDidChange', onStateChange)

    // Initial values
    setCurrentTime(mk.player.currentPlaybackTime || 0)
    setDuration(mk.player.currentPlaybackDuration || 0)

    return () => {
      mk.player.removeEventListener('playbackTimeDidChange', onTimeChange)
      mk.player.removeEventListener('playbackDurationDidChange', onDurationChange)
      mk.player.removeEventListener('playbackStateDidChange', onStateChange)
    }
  }, [seeking])

  // HTML5 audio time update
  const handleTimeUpdate = useCallback(() => {
    const audio = audioRef.current
    if (audio && !seeking) {
      setCurrentTime(audio.currentTime)
    }
  }, [seeking])

  const handleLoadedMetadata = useCallback(() => {
    const audio = audioRef.current
    if (audio) setDuration(audio.duration || 0)
  }, [])

  const emotionColor = prediction?.color || '#a855f7'

  const fetchPreview = async () => {
    if (!id) return
    setPreviewLoading(true)
    try {
      let url: string | null = null
      // 网易云歌曲优先尝试网易云官方试听音频，失败时回退 Apple Music 预览
      if (song?.platform === 'netease') {
        try {
          const { data } = await neteaseApi.preview(Number(id))
          url = data.preview_url
        } catch { /* 回退 Apple Music */ }
      }
      if (!url) {
        const { data } = await songsApi.getPreview(Number(id))
        url = data.preview_url
      }
      setPreviewUrl(url)
      setTimeout(() => {
        audioRef.current?.play().then(() => setPlaying(true)).catch(() => {})
      }, 500)
    } catch (err: any) {
      alert(err?.response?.data?.detail || '该歌曲暂无预览音频')
    } finally {
      setPreviewLoading(false)
    }
  }

  const playFullSong = async () => {
    if (!song?.apple_music_id || !musicKitRef.current) return
    const mk = musicKitRef.current
    try {
      setUseMusicKit(true)
      await mk.setQueue({ song: song.apple_music_id })
      await mk.play()
    } catch (err: any) {
      // If MusicKit fails (no subscription, etc.), fall back to preview
      setUseMusicKit(false)
      alert('完整播放失败（需要 Apple Music 订阅），请尝试预览播放')
    }
  }

  const togglePlay = () => {
    if (useMusicKit && musicKitRef.current) {
      const mk = musicKitRef.current
      if (playing) {
        mk.pause()
      } else {
        mk.play()
      }
      return
    }
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
    } else {
      audio.play().catch(() => setPlaying(false))
    }
    setPlaying(!playing)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value)
    setCurrentTime(time)
    setSeeking(true)
  }

  const commitSeek = (e: React.MouseEvent | React.TouchEvent) => {
    const time = parseFloat((e.target as HTMLInputElement).value)
    if (useMusicKit && musicKitRef.current) {
      musicKitRef.current.seekToTime(time)
    } else if (audioRef.current) {
      audioRef.current.currentTime = time
    }
    setSeeking(false)
  }

  const handleAnalyze = async () => {
    if (!id) return
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

  // 分享：仅已有 AI 分析结果时可用（后端同样校验）
  const handleShare = async () => {
    if (!song) return
    setSharing(true)
    try {
      await shareApi.create(song.id)
      setShared(true)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || ''
      if (detail.includes('已经分享过')) {
        setShared(true)
      } else {
        alert(detail || '分享失败，请重试')
      }
    } finally {
      setSharing(false)
    }
  }

  const isAlbum = song?.type === 'albums'
  const isPlaylist = song?.type === 'playlists'
  // 专辑/歌单均展示曲目列表
  const showTracks = isAlbum || isPlaylist
  // 基本信息补充字段（发行日期/曲目数/流派），渲染前提取一次
  const basicMeta = song ? extractMeta(song) : null

  const loadAlbumTracks = async (): Promise<AlbumTrack[]> => {
    if (!id) return []
    setAlbumLoading(true)
    try {
      const { data } = await songsApi.getAlbumTracks(Number(id))
      const tracks = data.tracks as AlbumTrack[]
      setAlbumTracks(tracks)
      return tracks
    } catch (err: any) {
      alert(err?.response?.data?.detail || '加载曲目失败')
      return []
    } finally {
      setAlbumLoading(false)
    }
  }

  const playTrackUrl = (url: string) => {
    setUseMusicKit(false)
    setTrackAudio(url)
    setTrackPlaying(true)
    setTimeout(() => {
      audioRef.current?.play().then(() => setTrackPlaying(true)).catch(() => {})
    }, 100)
  }

  // 播放专辑/歌单曲目：网易云歌曲按需获取试听 URL
  const playTrack = async (track: AlbumTrack) => {
    // 手动单曲播放，退出整张播放模式
    setPlayQueueIndex(null)
    let url = track.preview_url || trackUrls[track.id]
    if (!url && song?.platform === 'netease') {
      setLoadingTrackId(track.id)
      try {
        const { data } = await neteaseApi.trackUrl(track.id)
        url = data.preview_url
        setTrackUrls((prev) => ({ ...prev, [track.id]: url }))
      } catch (err: any) {
        alert(err?.response?.data?.detail || '获取试听失败')
        setLoadingTrackId(null)
        return
      }
      setLoadingTrackId(null)
    }
    if (url) playTrackUrl(url)
  }

  // 整张播放：播放指定索引的曲目（网易云按需获取试听 URL）
  const playQueueTrack = async (tracks: AlbumTrack[], index: number) => {
    const track = tracks[index]
    if (!track) return
    setPlayQueueIndex(index)
    let url = track.preview_url || trackUrls[track.id]
    if (!url && song?.platform === 'netease') {
      try {
        const { data } = await neteaseApi.trackUrl(track.id)
        url = data.preview_url
        setTrackUrls((prev) => ({ ...prev, [track.id]: url }))
      } catch {
        return // 该曲目无法获取试听，跳过
      }
    }
    if (url) playTrackUrl(url)
  }

  // 播放整张专辑/歌单：从第一首开始顺序播放
  const playAllTracks = async () => {
    setUseMusicKit(false)
    const tracks = albumTracks.length > 0 ? albumTracks : await loadAlbumTracks()
    if (tracks.length === 0) return
    await playQueueTrack(tracks, 0)
  }

  // 整张播放开关：播放中暂停，暂停后继续，否则从头开始
  const toggleAllPlay = () => {
    if (playQueueIndex != null && trackPlaying) {
      audioRef.current?.pause()
      setTrackPlaying(false)
    } else if (playQueueIndex != null) {
      audioRef.current?.play().then(() => setTrackPlaying(true)).catch(() => {})
    } else {
      void playAllTracks()
    }
  }

  // 曲目行按钮：再次点击正在播放的曲目则暂停
  const toggleTrack = (track: AlbumTrack) => {
    const url = track.preview_url || trackUrls[track.id]
    if (url && trackAudio === url && trackPlaying) {
      audioRef.current?.pause()
      setTrackPlaying(false)
      return
    }
    void playTrack(track)
  }

  // Load album/playlist tracks on mount
  useEffect(() => {
    if (showTracks) loadAlbumTracks()
  }, [showTracks, id])

  const hasAudio = previewUrl || trackAudio || (musicKitAuthorized && song?.apple_music_id)

  return (
    <div className="relative min-h-[calc(100dvh-64px)]">
      <Suspense fallback={null}><ParticleBg color={emotionColor} /></Suspense>

      {/* HTML5 audio for previews (hidden when using MusicKit) */}
      {!useMusicKit && (previewUrl || trackAudio) && (
        <audio
          ref={audioRef}
          src={trackAudio || previewUrl || undefined}
          onEnded={() => {
            setPlaying(false)
            setTrackPlaying(false)
            // 整张播放：自动续播下一首
            if (playQueueIndex != null) {
              const next = playQueueIndex + 1
              if (next < albumTracks.length) {
                void playQueueTrack(albumTracks, next)
              } else {
                setPlayQueueIndex(null)
              }
            }
          }}
          onPause={() => { setPlaying(false); setTrackPlaying(false) }}
          onPlay={() => { setPlaying(true); setTrackPlaying(true) }}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
        />
      )}

      <div className="grid lg:grid-cols-2 gap-8 items-start pt-4">
        {/* 左侧：封面与信息 */}
        <div className="text-center lg:text-left">
          {/* 封面 */}
          <div
            className="aspect-square max-w-sm mx-auto rounded-2xl mb-6 flex items-center justify-center overflow-hidden"
            style={{
              background: song?.artwork_url ? 'transparent' : `linear-gradient(135deg, ${emotionColor}40, ${emotionColor}10)`,
              boxShadow: `0 0 60px ${emotionColor}30`,
            }}
          >
            {song?.artwork_url ? (
              <img
                src={song.artwork_url}
                alt={song.title}
                className="w-full h-full object-cover"
              />
            ) : isAlbum ? (
              <Disc className="w-16 h-16 text-white/50" />
            ) : isPlaylist ? (
              <ListMusic className="w-16 h-16 text-white/50" />
            ) : (
              <Music className="w-16 h-16 text-white/50" />
            )}
          </div>

          {song && (
            <>
              {/* 歌名 */}
              <h1 className="font-display text-2xl sm:text-3xl font-bold mb-1">
                {isAlbum && <Disc className="w-5 h-5 inline mr-2 text-neon-purple/70" />}
                {isPlaylist && <ListMusic className="w-5 h-5 inline mr-2 text-red-400/70" />}
                {!isAlbum && !isPlaylist && <Music className="w-5 h-5 inline mr-2 text-neon-cyan/70" />}
                {song.title}
              </h1>
              <p className="text-slate-400 mb-1">{song.artist}</p>

              {/* 作者简介（一行） */}
              {song.artist_bio && (
                <p className="text-slate-500 text-xs mb-3 max-w-sm mx-auto lg:mx-0 leading-relaxed">
                  {song.artist_bio}
                </p>
              )}

              {song.album && <p className="text-slate-500 text-sm mb-1">{song.album}</p>}
              {song.duration_ms && (
                <p className="text-slate-500 text-xs">
                  {Math.floor(song.duration_ms / 60000)}:{String(Math.floor((song.duration_ms % 60000) / 1000)).padStart(2, '0')}
                </p>
              )}
            </>
          )}

          {/* 情绪标签 + AI 分析按钮（始终展示按钮，已有预测时可重新分析） */}
          <div className="flex items-center gap-2 mt-4 flex-wrap">
            {prediction && (
              <div
                className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 px-4 py-2 rounded-full"
                style={{
                  background: `${emotionColor}20`,
                  border: `1px solid ${emotionColor}50`,
                }}
              >
                <Sparkles className="w-4 h-4" style={{ color: emotionColor }} />
                <span className="font-medium whitespace-nowrap" style={{ color: emotionColor }}>
                  {prediction.emotion}
                </span>
                {prediction.fuzzy && (
                  <span className="text-xs text-amber-400 whitespace-nowrap">· 情绪模糊</span>
                )}
                <span className="text-slate-500 text-sm whitespace-nowrap">
                  · 置信度 {(prediction.confidence * 100).toFixed(0)}%
                </span>
                {/* v2 多标签：次情绪徽章 */}
                {prediction.top_emotions && prediction.top_emotions.length > 1 && (
                  <span className="flex flex-wrap items-center gap-1.5">
                    {prediction.top_emotions.slice(1).map((t) => (
                      <span
                        key={t.name}
                        className="text-xs px-2 py-0.5 rounded-full border border-slate-500/40 text-slate-300 whitespace-nowrap"
                        style={{ background: `${t.color}18` }}
                      >
                        {t.name} {(t.prob * 100).toFixed(0)}%
                      </span>
                    ))}
                  </span>
                )}
              </div>
            )}
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm border border-neon-purple/30 hover:border-neon-purple/60 transition-all"
            >
              <Sparkles className="w-4 h-4 text-neon-purple" />
              {analyzing ? '分析中...' : prediction ? '重新AI分析' : 'AI分析'}
            </button>
            {/* 分享：仅自己的内容且完成 AI 分析后可将专辑/歌单分享到社区推荐 */}
            {prediction && song?.user_id === meId && (
              <button
                onClick={handleShare}
                disabled={sharing || shared}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm border transition-all disabled:opacity-60 ${
                  shared
                    ? 'border-neon-cyan/40 text-neon-cyan'
                    : 'border-neon-pink/30 hover:border-neon-pink/60'
                }`}
              >
                <Share2 className={`w-4 h-4 ${shared ? 'text-neon-cyan' : 'text-neon-pink'}`} />
                {sharing ? '分享中...' : shared ? '已分享' : '分享推荐'}
              </button>
            )}
          </div>

          {/* 基本信息（MusicBrainz 卡片风格，来源 Apple Music / 网易云音乐） */}
          {review?.source === '基本信息' && song && (
            <div className="glass mt-4 p-4 rounded-xl text-left space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                  {song.type === 'albums' ? (
                    <Disc className="w-3.5 h-3.5 text-neon-cyan" />
                  ) : (
                    <Music className="w-3.5 h-3.5 text-neon-cyan" />
                  )}
                  基本信息
                </p>
                <span className="text-[10px] text-slate-500 flex items-center gap-1">
                  {song.platform === 'netease' ? (
                    <Podcast className="w-3 h-3 text-red-400" />
                  ) : (
                    <Music className="w-3 h-3 text-neon-cyan" />
                  )}
                  信息来自 {song.platform === 'netease' ? '网易云音乐' : 'Apple Music'}
                </span>
              </div>
              <div className="rounded-lg bg-white/[0.03] border border-white/5 p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium text-white truncate">{song.title}</p>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-cyan/10 text-neon-cyan flex-shrink-0">
                    {song.type === 'albums' ? '专辑' : song.type === 'playlists' ? '歌单' : '单曲'}
                  </span>
                </div>
                {song.artist && <p className="text-xs text-slate-500">{song.artist}</p>}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                  {song.album && <span>收录专辑：{song.album}</span>}
                  {song.duration_ms ? <span>时长：{fmtDuration(song.duration_ms)}</span> : null}
                  {basicMeta?.releaseDate && <span>发行日期：{basicMeta.releaseDate}</span>}
                  {basicMeta?.trackCount ? <span>曲目数：{basicMeta.trackCount}</span> : null}
                  {basicMeta && basicMeta.genres.length > 0 && (
                    <span>流派：{basicMeta.genres.join('、')}</span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 平台官方评价（Apple Music Editorial） */}
          {review && review.source !== '基本信息' && (
            <div className="glass mt-4 p-4 rounded-xl text-left">
              <p className="text-slate-300 text-sm leading-relaxed">{review.review}</p>
              <div className="flex items-center gap-1.5 mt-2">
                {song?.platform === 'netease' ? (
                  <Podcast className="w-3 h-3 text-red-400 flex-shrink-0" />
                ) : (
                  <Music className="w-3 h-3 text-neon-cyan flex-shrink-0" />
                )}
                <p className="text-slate-500 text-xs">
                  — {review.source}
                  <span className="text-slate-600">
                    {song?.platform === 'netease' ? ' · 来自 网易云音乐' : ' · 来自 Apple Music'}
                  </span>
                </p>
              </div>
            </div>
          )}

          {/* MusicBrainz 权威信息（位于多源公认度评估上方） */}
          {musicBrainz?.found && musicBrainz.items.length > 0 && (
            <div className="glass mt-4 p-4 rounded-xl text-left space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-neon-cyan" />
                  MusicBrainz 权威信息
                </p>
                <span className="text-[10px] text-slate-500">信息来自 MusicBrainz</span>
              </div>
              {musicBrainz.items.slice(0, 3).map((item) => (
                <div key={item.mbid} className="rounded-lg bg-white/[0.03] border border-white/5 p-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-white truncate">{item.title}</p>
                    {item.type && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-cyan/10 text-neon-cyan flex-shrink-0">
                        {item.type}
                      </span>
                    )}
                  </div>
                  {item.artist && <p className="text-xs text-slate-500">{item.artist}</p>}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    {item.release_date && <span>发行日期：{item.release_date}</span>}
                    {item.track_count != null && <span>曲目：{item.track_count} 首</span>}
                    {typeof item.rating === 'number' && (
                      <span>
                        评分：{item.rating} / 5{item.rating_votes ? `（${item.rating_votes} 票）` : ''}
                      </span>
                    )}
                  </div>
                  {item.tags && item.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {item.tags.map((t) => (
                        <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-neon-cyan hover:underline"
                    >
                      查看 MusicBrainz 页面
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* 多源公认度评估结果 */}
          {feedback?.consensus && (
            <div className="glass mt-4 p-4 rounded-xl text-left space-y-3">
              <p className="text-xs text-slate-400 font-medium">多源公认度评估</p>

              {/* 共识结果 */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold" style={{ color: emotionColor }}>
                  {feedback.consensus.consensus_emotion}
                </span>
                <span className="text-xs text-slate-500">
                  可信度 {(feedback.consensus.confidence * 100).toFixed(0)}%
                </span>
                <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${
                  feedback.consensus.agreement_level === '高' ? 'bg-green-500/20 text-green-400' :
                  feedback.consensus.agreement_level === '中' ? 'bg-yellow-500/20 text-yellow-400' :
                  feedback.consensus.agreement_level === '低' ? 'bg-red-500/20 text-red-400' :
                  'bg-slate-500/20 text-slate-400'
                }`}>
                  一致度：{feedback.consensus.agreement_level}
                </span>
                {feedback.consensus.ai_matches_consensus && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-neon-purple/10 text-neon-purple">
                    ✓ AI一致
                  </span>
                )}
              </div>

              {/* 各源投票明细 */}
              {feedback.consensus.vote_detail.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">投票明细：</p>
                  {feedback.consensus.vote_detail.map((v, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="w-16 text-slate-500">{v.source}</span>
                      <span className="font-medium text-slate-300 w-14">{v.emotion}</span>
                      <span className="text-slate-500 w-16">置信{(v.confidence * 100).toFixed(0)}%</span>
                      <span className="text-slate-600">权重{v.weight}</span>
                      <span className="text-slate-500 ml-auto">得分{v.weighted_score.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 加权总分排名 */}
              {Object.keys(feedback.consensus.weighted_score).length > 0 && (
                <div className="flex flex-wrap gap-1">
                  <span className="text-xs text-slate-500">加权排名：</span>
                  {Object.entries(feedback.consensus.weighted_score).slice(0, 5).map(([emotion, score]) => (
                    <span key={emotion} className="text-xs px-1.5 py-0.5 rounded bg-white/5 text-slate-400">
                      {emotion} {score.toFixed(2)}
                    </span>
                  ))}
                </div>
              )}

              {/* 自动纠正提示 */}
              {feedback.auto_correction?.corrected && (
                <div className="p-3 rounded-lg bg-neon-pink/10 border border-neon-pink/20">
                  <p className="text-xs text-neon-pink font-medium mb-1">
                    已自动纠正情绪标签
                  </p>
                  <p className="text-xs text-slate-400">
                    {feedback.auto_correction.previous_emotion}
                    （{((feedback.auto_correction.previous_confidence || 0) * 100).toFixed(0)}%）
                    → {feedback.auto_correction.new_emotion}
                    （{((feedback.auto_correction.new_confidence || 0) * 100).toFixed(0)}%）
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    差距：{((feedback.auto_correction.confidence_gap || 0) * 100).toFixed(0)}%
                  </p>
                </div>
              )}

              {/* 评论典例：B站 */}
              {(() => {
                const samples = feedback.sources.bilibili_comments?.sample_comments
                if (!samples || samples.length === 0) return null
                return (
                  <div>
                    <p className="text-xs text-slate-500 mb-1">B站评论典例：</p>
                    <div className="space-y-1.5">
                      {samples.map((c, i) => (
                        <div key={i} className="text-xs p-2 rounded bg-neon-cyan/5 border border-neon-cyan/10">
                          <p className="text-slate-300 leading-relaxed">「{c.content}」</p>
                          <p className="text-slate-600 mt-0.5">👍 {c.like} · 情绪：{c.emotion}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}

              {/* 评论典例：网易云 */}
              {(() => {
                const samples = feedback.sources.netease?.sample_comments
                if (!samples || samples.length === 0) return null
                return (
                  <div>
                    <p className="text-xs text-slate-500 mb-1">网易云评论典例：</p>
                    <div className="space-y-1.5">
                      {samples.map((c, i) => (
                        <div key={i} className="text-xs p-2 rounded bg-neon-pink/5 border border-neon-pink/10">
                          <p className="text-slate-300 leading-relaxed">「{c.content}」</p>
                          <p className="text-slate-600 mt-0.5">👍 {c.like} · 情绪：{c.emotion}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}

              {/* B站 & 网易云 源数据摘要 */}
              {feedback.sources && (
                <div className="flex flex-wrap gap-2 text-xs text-slate-500 pt-1 border-t border-white/5">
                  {feedback.sources.bilibili_styles?.primary_style && (
                    <span>B站标签：{feedback.sources.bilibili_styles.primary_style}</span>
                  )}
                  {feedback.sources.bilibili_comments?.primary_emotion && (
                    <span>B站评论：{feedback.sources.bilibili_comments.primary_emotion}</span>
                  )}
                  {feedback.sources.netease?.primary_emotion && (
                    <span>网易云：{feedback.sources.netease.primary_emotion}</span>
                  )}
                  {feedback.sources.ai_prediction?.emotion && (
                    <span>AI分析：{feedback.sources.ai_prediction.emotion}</span>
                  )}
                </div>
              )}

              {/* 建议 */}
              {feedback.consensus.suggestions?.length > 0 && (
                <div className="pt-2 border-t border-white/5">
                  <p className="text-xs text-slate-500 mb-1">建议：</p>
                  {feedback.consensus.suggestions.map((s, i) => (
                    <p key={i} className="text-xs text-slate-400 leading-relaxed">· {s}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 播放按钮 */}
          <div className="flex flex-col items-center lg:items-start gap-3 mt-6">
            <div className="flex items-center gap-3">
              {showTracks && song?.platform === 'netease' ? (
                <button onClick={toggleAllPlay} className="btn-neon">
                  {playQueueIndex != null && trackPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  {playQueueIndex != null && trackPlaying ? '暂停整张' : isAlbum ? '播放整张专辑' : '播放整个歌单'}
                </button>
              ) : song?.platform === 'netease' && !previewUrl && !useMusicKit ? (
                <button
                  onClick={fetchPreview}
                  disabled={previewLoading}
                  className="btn-neon"
                >
                  <Play className="w-4 h-4" />
                  {previewLoading ? '获取中...' : '试听'}
                </button>
              ) : useMusicKit ? (
                <button onClick={togglePlay} className="btn-neon">
                  {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  {playing ? '暂停' : '继续'}
                </button>
              ) : musicKitAuthorized && song?.apple_music_id && song?.platform !== 'netease' ? (
                <button onClick={playFullSong} className="btn-neon">
                  <Play className="w-4 h-4" />
                  播放整首
                </button>
              ) : previewUrl ? (
                <button onClick={togglePlay} className="btn-neon">
                  {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  {playing ? '暂停' : '试听'}
                </button>
              ) : (
                <button
                  onClick={fetchPreview}
                  disabled={previewLoading}
                  className="btn-neon"
                >
                  <Play className="w-4 h-4" />
                  {previewLoading ? '获取中...' : '试听'}
                </button>
              )}
            </div>

            {/* 进度条 */}
            {hasAudio && (previewUrl || trackAudio || useMusicKit) && (
              <div className="w-full max-w-sm mt-2">
                {/* 整张播放：当前曲目名 */}
                {playQueueIndex != null && albumTracks[playQueueIndex] && (
                  <p className="text-sm text-slate-300 truncate mb-1.5">
                    <span style={{ color: emotionColor }}>♪ </span>
                    {albumTracks[playQueueIndex].title}
                    <span className="text-xs text-slate-500"> - {albumTracks[playQueueIndex].artist}</span>
                  </p>
                )}
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 w-10 text-right tabular-nums">
                    {formatTime(currentTime)}
                  </span>
                  <input
                    ref={progressRef}
                    type="range"
                    min={0}
                    max={duration || 1}
                    step={0.1}
                    value={currentTime}
                    onChange={handleSeek}
                    onMouseUp={commitSeek}
                    onTouchEnd={commitSeek}
                    className="flex-1 h-1.5 rounded-full appearance-none cursor-pointer"
                    style={{
                      background: `linear-gradient(to right, ${emotionColor} ${(currentTime / (duration || 1)) * 100}%, rgba(255,255,255,0.1) ${(currentTime / (duration || 1)) * 100}%)`,
                      accentColor: emotionColor,
                    }}
                  />
                  <span className="text-xs text-slate-400 w-10 tabular-nums">
                    {formatTime(duration)}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 右侧：情绪雷达入口 */}
        <div className="glass p-6 lg:p-8">
          <h2 className="font-display text-lg font-bold mb-4 text-center">情绪雷达图</h2>
          {radar ? (
            <Link
              to={`/song/${id}/radar`}
              className="block group rounded-2xl border border-white/10 hover:border-white/25 bg-white/[0.03] hover:bg-white/[0.06] transition-all py-8 px-6 text-center"
            >
              <Radar className="w-6 h-6 mx-auto mb-2" style={{ color: radar.color }} />
              <p className="text-sm font-medium" style={{ color: radar.color }}>
                查看完整情绪雷达图
              </p>
              <p className="text-xs text-slate-500 mt-1">点击进入全维度情绪解读</p>
              <ChevronRight className="w-4 h-4 mx-auto mt-2 text-slate-500 transition-transform group-hover:translate-x-0.5" />
            </Link>
          ) : (
            <Link
              to={`/song/${id}/radar`}
              className="block rounded-2xl border border-dashed border-white/15 hover:border-neon-purple/40 bg-white/[0.02] hover:bg-white/[0.04] transition-all py-10 px-6 text-center group"
            >
              <Radar className="w-8 h-8 text-slate-600 group-hover:text-neon-purple mx-auto mb-2 transition-colors" />
              <p className="text-slate-400 text-sm mb-1">暂无情绪分析数据</p>
              <p className="text-xs text-slate-600 mb-3">点击「AI分析」按钮生成雷达图</p>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-neon-purple">
                情绪雷达入口
                <ChevronRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          )}
        </div>
      </div>

      {/* 专辑/歌单曲目列表 */}
      {showTracks && (
        <div className="mt-8 glass p-6">
          <h2 className="font-display text-lg font-bold mb-4 flex items-center gap-2">
            {isAlbum ? (
              <Disc className="w-5 h-5 text-neon-purple" />
            ) : (
              <ListMusic className="w-5 h-5 text-red-400" />
            )}
            {isPlaylist ? '歌单歌曲' : '专辑曲目'}
            {albumLoading && <span className="text-sm text-slate-500">加载中...</span>}
          </h2>
          {albumTracks.length > 0 ? (
            <div className="space-y-1">
              {albumTracks.map((track) => {
                const trackUrl = track.preview_url || trackUrls[track.id]
                const isCurrent = trackUrl && trackAudio === trackUrl && trackPlaying
                const isLoading = loadingTrackId === track.id
                // 网易云曲目始终显示播放按钮（按需获取试听）；Apple Music 仅在有预览时显示
                const canPlay = song?.platform === 'netease' || Boolean(trackUrl)
                return (
                  <div
                    key={track.id}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.04] transition-all group"
                  >
                    <span className="text-xs text-slate-500 w-6 text-right">
                      {track.track_number || '-'}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm truncate transition-colors ${isCurrent ? 'text-neon-purple' : 'group-hover:text-neon-cyan'}`}>
                        {track.title}
                      </p>
                      <p className="text-xs text-slate-500 truncate">{track.artist}</p>
                    </div>
                    {track.duration_ms && (
                      <span className="text-xs text-slate-500">
                        {Math.floor(track.duration_ms / 60000)}:{String(Math.floor((track.duration_ms % 60000) / 1000)).padStart(2, '0')}
                      </span>
                    )}
                    {canPlay && (
                      <button
                        onClick={() => toggleTrack(track)}
                        disabled={isLoading}
                        className="p-2 rounded-lg hover:bg-neon-purple/10 transition-all disabled:opacity-50"
                      >
                        {isLoading ? (
                          <RefreshCw className="w-4 h-4 animate-spin text-neon-purple" />
                        ) : isCurrent ? (
                          <Pause className="w-4 h-4 text-neon-purple" />
                        ) : (
                          <Play className="w-4 h-4 text-slate-400 group-hover:text-neon-purple transition-colors" />
                        )}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          ) : !albumLoading ? (
            <p className="text-slate-500 text-center py-8">暂无曲目数据</p>
          ) : null}
        </div>
      )}
    </div>
  )
}