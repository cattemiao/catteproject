export interface SongOut {
  id: number
  apple_music_id: string
  platform?: string
  netease_id?: string | null
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

// 多源共识反馈
export interface SampleComment {
  content: string
  like: number
  emotion: string
}

export interface SourceVote {
  source: string
  emotion: string
  confidence: number
  weight: number
  weighted_score: number
}

export interface ConsensusResult {
  consensus_emotion: string
  confidence: number
  agreement_level: string
  vote_detail: SourceVote[]
  weighted_score: Record<string, number>
  ai_matches_consensus: boolean
  suggestions: string[]
}

export interface AutoCorrection {
  corrected: boolean
  reason?: string
  previous_emotion?: string
  previous_confidence?: number
  new_emotion?: string
  new_confidence?: number
  confidence_gap?: number
  agreement_level?: string
  source?: string
}

export interface FeedbackSources {
  bilibili_styles: { primary_style?: string; style_counts?: Record<string, number> } & Record<string, any> | null
  bilibili_comments: { primary_emotion?: string; sample_comments?: SampleComment[] } & Record<string, any> | null
  netease: { primary_emotion?: string; sample_comments?: SampleComment[] } & Record<string, any> | null
  editorial_scores: Record<string, number> | null
  ai_prediction: Record<string, any> | null
}

export interface FeedbackData {
  sources: FeedbackSources
  consensus: ConsensusResult
  auto_correction: AutoCorrection | null
  updated_at: string
}

// 风格推荐
export interface StyleRecommendation {
  song: SongOut
  reason: string
  matched_genres: string[]
  matched_emotion: string | null
  score: number
}

export interface StyleRecommendResult {
  preference: {
    top_genres: [string, number][]
    top_emotion: string | null
    fav_count: number
  } | null
  recommendations: StyleRecommendation[]
}