import axios from 'axios'
import type { MusicBrainzData, PredictionData, RadarData, ReviewData, SongListOut, SongOut, PreviewData, StyleRecommendResult, UserOut } from '../types'
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
    client.post<{ access_token: string }>('/auth/login', { username, password }),
  me: () => client.get<UserOut>('/auth/me'),
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
  favorite: (id: number) => client.post(`/songs/${id}/favorite`),
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
    client.get('/recommend', { params: { limit, ...params } }),
  getStyle: (limit = 6, params?: { platform?: string }) =>
    client.get<StyleRecommendResult>('/recommend/style', { params: { limit, ...params } }),
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

export default client