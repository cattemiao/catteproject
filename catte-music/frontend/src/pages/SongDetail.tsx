import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Disc, Heart, Music, Pause, Play, Sparkles } from 'lucide-react'
import { emotionApi, songsApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import EmotionRadar from '../components/EmotionRadar'
import type { PredictionData, RadarData, ReviewData, SongOut } from '../types'

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

export default function SongDetail() {
  const { id } = useParams<{ id: string }>()
  const [song, setSong] = useState<SongOut | null>(null)
  const [radar, setRadar] = useState<RadarData | null>(null)
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [review, setReview] = useState<ReviewData | null>(null)
  const [favLoading, setFavLoading] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [albumTracks, setAlbumTracks] = useState<AlbumTrack[]>([])
  const [albumLoading, setAlbumLoading] = useState(false)
  const [trackAudio, setTrackAudio] = useState<string | null>(null)
  const [trackPlaying, setTrackPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [seeking, setSeeking] = useState(false)
  const [useMusicKit, setUseMusicKit] = useState(false)
  const [musicKitAuthorized, setMusicKitAuthorized] = useState(false)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const progressRef = useRef<HTMLInputElement | null>(null)
  const musicKitRef = useRef<any>(null)

  // Check MusicKit availability
  useEffect(() => {
    try {
      const mk = window.MusicKit
      if (mk) {
        const instance = mk.getInstance()
        if (instance && instance.isAuthorized) {
          setMusicKitAuthorized(true)
          musicKitRef.current = instance
        }
      }
    } catch { /* MusicKit not configured */ }
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
  }, [id])

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
      const { data } = await songsApi.getPreview(Number(id))
      setPreviewUrl(data.preview_url)
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

  const toggleFavorite = async () => {
    if (!song) return
    setFavLoading(true)
    try {
      await songsApi.favorite(song.id)
    } finally {
      setFavLoading(false)
    }
  }

  const isAlbum = song?.type === 'albums'

  const loadAlbumTracks = async () => {
    if (!id) return
    setAlbumLoading(true)
    try {
      const { data } = await songsApi.getAlbumTracks(Number(id))
      setAlbumTracks(data.tracks as AlbumTrack[])
    } catch (err: any) {
      alert(err?.response?.data?.detail || '加载曲目失败')
    } finally {
      setAlbumLoading(false)
    }
  }

  const playTrack = (url: string) => {
    setUseMusicKit(false)
    setTrackAudio(url)
    setTrackPlaying(true)
    setTimeout(() => {
      audioRef.current?.play().then(() => setTrackPlaying(true)).catch(() => {})
    }, 100)
  }

  // Load album tracks on mount if it's an album
  useEffect(() => {
    if (isAlbum) loadAlbumTracks()
  }, [isAlbum, id])

  const hasAudio = previewUrl || trackAudio || (musicKitAuthorized && song?.apple_music_id)

  return (
    <div className="relative min-h-[calc(100dvh-64px)]">
      <ParticleBg color={emotionColor} />

      {/* HTML5 audio for previews (hidden when using MusicKit) */}
      {!useMusicKit && (previewUrl || trackAudio) && (
        <audio
          ref={audioRef}
          src={trackAudio || previewUrl || undefined}
          onEnded={() => { setPlaying(false); setTrackPlaying(false) }}
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
            className="aspect-square max-w-sm mx-auto rounded-2xl mb-6 flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${emotionColor}40, ${emotionColor}10)`,
              boxShadow: `0 0 60px ${emotionColor}30`,
            }}
          >
            {isAlbum ? (
              <Disc className="w-16 h-16 text-white/50" />
            ) : (
              <Music className="w-16 h-16 text-white/50" />
            )}
          </div>

          {song && (
            <>
              {/* 歌名 */}
              <h1 className="font-display text-2xl sm:text-3xl font-bold mb-1">
                {isAlbum && <Disc className="w-5 h-5 inline mr-2 text-neon-purple/70" />}
                {!isAlbum && <Music className="w-5 h-5 inline mr-2 text-neon-cyan/70" />}
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

          {/* 情绪标签 */}
          {prediction ? (
            <div
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-full"
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
          ) : (
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-full text-sm border border-neon-purple/30 hover:border-neon-purple/60 transition-all"
            >
              <Sparkles className="w-4 h-4 text-neon-purple" />
              {analyzing ? '分析中...' : 'AI 情绪分析'}
            </button>
          )}

          {/* 评价（来自 Apple Music Editorial） */}
          {review && (
            <div className="glass mt-4 p-4 rounded-xl text-left">
              <p className="text-slate-300 text-sm leading-relaxed">{review.review}</p>
              <p className="text-slate-500 text-xs mt-2">— {review.source}</p>
            </div>
          )}

          {/* 播放 + 收藏按钮 */}
          <div className="flex flex-col items-center lg:items-start gap-3 mt-6">
            <div className="flex items-center gap-3">
              {useMusicKit ? (
                <button onClick={togglePlay} className="btn-neon">
                  {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  {playing ? '暂停' : '继续'}
                </button>
              ) : musicKitAuthorized && song?.apple_music_id ? (
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
              <button
                onClick={toggleFavorite}
                disabled={favLoading}
                className="glass px-4 py-3 rounded-xl hover:border-neon-pink/50 transition-all"
              >
                <Heart className="w-5 h-5 text-neon-pink" />
              </button>
            </div>

            {/* 进度条 */}
            {hasAudio && (previewUrl || trackAudio || useMusicKit) && (
              <div className="w-full max-w-sm mt-2">
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

        {/* 右侧：雷达图 */}
        <div className="glass p-6 lg:p-8">
          <h2 className="font-display text-lg font-bold mb-4 text-center">情绪雷达图</h2>
          {radar ? (
            <EmotionRadar dimensions={radar.dimensions} color={radar.color} />
          ) : (
            <div className="text-center text-slate-500 py-20">
              <p>暂无情绪分析数据</p>
              <p className="text-sm mt-1">点击「AI 情绪分析」按钮开始</p>
            </div>
          )}
        </div>
      </div>

      {/* 专辑曲目列表 */}
      {isAlbum && (
        <div className="mt-8 glass p-6">
          <h2 className="font-display text-lg font-bold mb-4 flex items-center gap-2">
            <Disc className="w-5 h-5 text-neon-purple" />
            专辑曲目
            {albumLoading && <span className="text-sm text-slate-500">加载中...</span>}
          </h2>
          {albumTracks.length > 0 ? (
            <div className="space-y-1">
              {albumTracks.map((track) => (
                <div
                  key={track.id}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.04] transition-all group"
                >
                  <span className="text-xs text-slate-500 w-6 text-right">
                    {track.track_number || '-'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate group-hover:text-neon-cyan transition-colors">
                      {track.title}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{track.artist}</p>
                  </div>
                  {track.duration_ms && (
                    <span className="text-xs text-slate-500">
                      {Math.floor(track.duration_ms / 60000)}:{String(Math.floor((track.duration_ms % 60000) / 1000)).padStart(2, '0')}
                    </span>
                  )}
                  {track.preview_url && (
                    <button
                      onClick={() => playTrack(track.preview_url!)}
                      className="p-2 rounded-lg hover:bg-neon-purple/10 transition-all"
                    >
                      {trackAudio === track.preview_url && trackPlaying ? (
                        <Pause className="w-4 h-4 text-neon-purple" />
                      ) : (
                        <Play className="w-4 h-4 text-slate-400 group-hover:text-neon-purple transition-colors" />
                      )}
                    </button>
                  )}
                </div>
              ))}
            </div>
          ) : !albumLoading ? (
            <p className="text-slate-500 text-center py-8">暂无曲目数据</p>
          ) : null}
        </div>
      )}
    </div>
  )
}