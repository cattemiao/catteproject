import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截器：自动携带 JWT
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('catte_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 跳转登录
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('catte_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default client

// —— API 方法封装 ——

export const authApi = {
  register: (username: string, password: string) =>
    client.post('/auth/register', { username, password }),
  login: (username: string, password: string) =>
    client.post('/auth/login', { username, password }),
  me: () => client.get('/auth/me'),
  appleMusicConfig: () => client.get('/auth/apple-music/config'),
  appleMusicCallback: (token: string) =>
    client.post('/auth/apple-music/callback', { music_user_token: token }),
}

export const songsApi = {
  list: (params?: { q?: string; page?: number; size?: number }) =>
    client.get('/songs', { params }),
  get: (id: number) => client.get(`/songs/${id}`),
  favorite: (id: number) => client.post(`/songs/${id}/favorite`),
  unfavorite: (id: number) => client.delete(`/songs/${id}/favorite`),
}

export const emotionApi = {
  list: () => client.get('/emotions'),
  getSongEmotion: (songId: number) => client.get(`/songs/${songId}/emotion`),
  getRadar: (songId: number) => client.get(`/songs/${songId}/radar`),
}

export const recommendApi = {
  get: (limit?: number) => client.get('/recommend', { params: { limit } }),
}

export const appleMusicApi = {
  recent: (limit?: number) =>
    client.get('/apple-music/recent', { params: { limit } }),
  heavyRotation: () => client.get('/apple-music/heavy-rotation'),
  rate: (songAppleId: string, rating: number) =>
    client.post(`/apple-music/rating/${songAppleId}`, null, {
      params: { rating },
    }),
}
