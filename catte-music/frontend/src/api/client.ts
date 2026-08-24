import axios from 'axios'
import type { MusicBrainzData, PredictionData, RadarData, ReviewData, SongListOut, SongOut, PreviewData, StyleRecommendResult, UserOut, ShareOut, LikeOut } from '../types'
import { getToken, clearToken } from '../utils/auth'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      clearToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export const authApi = {
  register: (username: string, password: string) =>
    client.post('/auth/register', { username, password }),
  login: (username: string, password: string) =>
    client.post<{ access_token: string; is_admin?: boolean }>('/auth/login', { username, password }),
  me: () => client.get<UserOut>('/auth/me'),
  changePassword: (oldPassword: string, newPassword: string) =>
    client.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword }),
  appleMusicConfig: () =>
    client.get<{ developer_token: string; app_name: string; build: string }>('/auth/apple-music/config'),
  appleMusicCallback: (musicUserToken: string) =>
    client.post('/auth/apple-music/callback', { music_user_token: musicUserToken }),
}

export const songsApi = {
  list: (params?: { q?: string; page?: number; size?: number; platform?: string }) =>
    client.get<SongListOut>('/songs', { params }),
  clear: (platform: string) => client.delete<{ deleted: number; platform: string }>('/songs', { params: { platform } }),
  get: (id: number) => client.get<SongOut>(`/songs/${id}`),
  getPreview: (id: number) => client.get<PreviewData>(`/songs/${id}/preview`),
  getReview: (id: number) => client.get<ReviewData>(`/songs/${id}/review`),
  getAlbumTracks: (songId: number) =>
    client.get(`/songs/${songId}/album-tracks`),
  getMusicBrainz: (songId: number) =>
    client.get<MusicBrainzData>(`/songs/${songId}/musicbrainz`),
  
  getFeedback: (songId: number) =>
    client.post(`/songs/${songId}/feedback`),
}

export const emotionApi = {
  list: () => client.get('/emotions'),
  getSongEmotion: (songId: number) => client.get<PredictionData>(`/songs/${songId}/emotion`),
  getRadar: (songId: number) => client.get<RadarData>(`/songs/${songId}/radar`),
  analyze: (songId: number) => client.post<PredictionData>(`/songs/${songId}/analyze`),
}

export const appleMusicApi = {
  recent: (limit = 10) => client.get('/apple-music/recent', { params: { limit } }),
  heavyRotation: (limit = 10) => client.get('/apple-music/heavy-rotation', { params: { limit } }),
  library: (maxAlbums = 300) => client.get('/apple-music/library', { params: { max_albums: maxAlbums } }),
  search: (q: string, limit = 10) => client.get('/apple-music/search', { params: { q, limit } }),
}

export const neteaseApi = {
  createQr: () => client.post<{ key: string; content: string; error?: string }>('/netease/qr'),
  checkQr: (key: string) =>
    client.get<{ code: number; message: string; nickname?: string; avatar_url?: string }>(`/netease/qr/${key}`),
  status: () => client.get<{ bound: boolean; nickname?: string; avatar_url?: string; uid?: string }>('/netease/status'),
  syncRecent: (limit = 10) => client.post(`/netease/sync`, null, { params: { limit } }),
  library: (limit = 100) => client.get(`/netease/library`, { params: { limit } }),
  search: (q: string, limit = 10) => client.get('/netease/search', { params: { q, limit } }),
  preview: (songId: number) => client.get<PreviewData>(`/netease/preview/${songId}`),
  trackUrl: (neteaseId: string) => client.get<PreviewData>('/netease/track-url', { params: { netease_id: neteaseId } }),
}

export const recommendApi = {
  get: (limit = 6, params?: { platform?: string }) =>
    client.get<ShareOut[]>('/recommend', { params: { limit, ...params } }),
  getStyle: (limit = 6, params?: { platform?: string }) =>
    client.get<StyleRecommendResult>('/recommend/style', { params: { limit, ...params } }),
}

export const shareApi = {
  create: (songId: number, comment?: string) =>
    client.post<ShareOut>('/shares', { song_id: songId, comment }),
  like: (shareId: number) => client.post<LikeOut>(`/shares/${shareId}/like`),
  unlike: (shareId: number) => client.delete<LikeOut>(`/shares/${shareId}/like`),
  status: (songId: number) =>
    client.get<{ shared: boolean; share_id: number | null }>('/shares/status', { params: { song_id: songId } }),
}

export interface UserStatsOut {
  apple_songs: number
  apple_albums: number
  netease_songs: number
  netease_albums: number
  shares: number
  analyses: number
  emotion_distribution: { name: string; color: string; count: number }[]
  emotion_dimensions: { dimension: string; avg: number; count: number }[]
  top_emotion: string | null
  top_genres: [string, number][]
}

export const usersApi = {
  songs: (userId: number) => client.get<SongListOut>(`/users/${userId}/songs`),
  meStats: () => client.get<UserStatsOut>('/users/me/stats'),
}

export interface SuggestionOut {
  id: number
  username: string
  content: string
  created_at: string
}

export const suggestionApi = {
  list: () => client.get<SuggestionOut[]>('/suggestions'),
  create: (content: string) => client.post<SuggestionOut>('/suggestions', { content }),
}

// ───────────────────────── 管理后台 ─────────────────────────

export interface AdminUserOut {
  id: number
  username: string
  has_apple_music: boolean
  has_netease: boolean
  song_count: number
  favorite_count: number
  suggestion_count: number
  created_at: string
}

export interface AdminSuggestionOut {
  id: number
  user_id: number | null
  username: string
  content: string
  created_at: string
}

export interface DashboardStat {
  date: string
  count: number
}

export interface SongPlatformStat {
  platform: string
  type: string
  count: number
}

export interface EmotionDistStat {
  name: string
  color: string
  count: number
}

export interface EmotionDimensionStat {
  dimension: string
  avg: number
  count: number
}

export interface DashboardData {
  total_users: number
  total_songs: number
  total_analyses: number
  total_visits: number
  total_shares: number
  total_likes: number
  visits_by_day: DashboardStat[]
  analysis_by_day: DashboardStat[]
  shares_by_day: DashboardStat[]
  likes_by_day: DashboardStat[]
  songs_by_platform: SongPlatformStat[]
  emotion_distribution: EmotionDistStat[]
  emotion_dimensions: EmotionDimensionStat[]
}

export interface AdminSettingsOut {
  auto_analyze_threshold: number
  active_users: number
  pending_albums: number
  admin_password_set: boolean
}

export const adminApi = {
  users: () => client.get<AdminUserOut[]>('/admin/users'),
  deleteUser: (userId: number) => client.delete(`/admin/users/${userId}`),
  resetPassword: (userId: number, newPassword: string) =>
    client.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword }),
  suggestions: () => client.get<AdminSuggestionOut[]>('/admin/suggestions'),
  updateSuggestion: (suggestionId: number, content: string) =>
    client.patch<AdminSuggestionOut>(`/admin/suggestions/${suggestionId}`, { content }),
  deleteSuggestion: (suggestionId: number) =>
    client.delete(`/admin/suggestions/${suggestionId}`),
  dashboard: () => client.get<DashboardData>('/admin/stats/dashboard'),
  settings: () => client.get<AdminSettingsOut>('/admin/settings'),
  updateSettings: (autoAnalyzeThreshold: number) =>
    client.put<AdminSettingsOut>('/admin/settings', { auto_analyze_threshold: autoAnalyzeThreshold }),
  changePassword: (oldPassword: string, newPassword: string) =>
    client.post('/admin/settings/password', { old_password: oldPassword, new_password: newPassword }),
}

export const statsApi = {
  pageview: (path: string) => client.post('/stats/pageview', { path }),
}

export default client