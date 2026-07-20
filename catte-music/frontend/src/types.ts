export interface SongOut {
  id: number
  apple_music_id: string
  title: string
  artist: string
  album?: string | null
  duration_ms?: number | null
  preview_url?: string | null
  artwork_url?: string | null
  raw_meta?: Record<string, any> | null
  type?: string
  artist_bio?: string | null
}

export interface SongListOut {
  total: number
  items: SongOut[]
}

export interface PredictionData {
  song_id: number
  emotion: string
  color: string
  confidence: number
}

export interface RadarDimension {
  loudness: number
  high_freq: number
  rhythm: number
  soundstage: number
  layering: number
  soothing: number
  prosody: number
}

export interface RadarData {
  song_id: number
  title: string
  emotion: string
  color: string
  dimensions: RadarDimension
}

export interface ReviewData {
  source: string
  review: string
}

export interface PreviewData {
  preview_url: string
  title: string
  artist: string
}

export interface FavoriteOut {
  user_id: number
  song_id: number
  created_at: string
}