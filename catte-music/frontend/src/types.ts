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
  user_id?: number | null
}

export interface SongListOut {
  total: number
  items: SongOut[]
}

export interface UserOut {
  id: number
  username: string
  has_apple_music: boolean
  has_netease: boolean
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

// MusicBrainz 权威元数据
export interface MusicBrainzItem {
  mbid: string
  title: string
  artist?: string | null
  release_date?: string | null
  type?: string | null
  tags?: string[]
  rating?: number | null
  rating_votes?: number
  track_count?: number | null
  url?: string | null
}

export interface MusicBrainzData {
  found: boolean
  items: MusicBrainzItem[]
}

// 用户分享与互动
export interface ShareOut {
  id: number
  song: SongOut
  sharer_id: number
  sharer_username: string
  platform: string
  comment?: string | null
  like_count: number
  user_liked: boolean
  created_at: string
  // 分享歌曲的 AI 情绪名（最新预测），用于卡片徽章
  emotion?: string | null
  // 与当前用户情绪画像的相似度（推荐时计算），随机兜底项为 null
  similarity?: number | null
}

export interface LikeOut {
  share_id: number
  liked: boolean
  like_count: number
}