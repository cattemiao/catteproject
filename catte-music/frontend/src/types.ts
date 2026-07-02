export interface SongOut {
  id: number
  apple_music_id: string
  title: string
  artist: string
  album?: string | null
  duration_ms?: number | null
}

export interface RadarData {
  song_id: number
  title: string
  emotion: string
  color: string
  dimensions: {
    loudness: number
    high_freq: number
    vocal: number
    rhythm: number
    soundstage: number
    space: number
    layering: number
  }
}

export interface PredictionData {
  song_id: number
  emotion: string
  color: string
  confidence: number
}
