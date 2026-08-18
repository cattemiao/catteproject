/**
 * 登录态管理：
 * - 使用 sessionStorage 而非 localStorage：登录态仅在当前标签页会话有效，
 *   新开标签页/浏览器窗口需重新登录，避免自动共享登录态。
 * - 本地解码 JWT 校验过期时间，过期即清除。
 */

const TOKEN_KEY = 'catte_token'

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY)
}

/** 本地校验 JWT 是否有效且未过期（无需请求后端） */
export function isTokenValid(): boolean {
  const token = getToken()
  if (!token) return false
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return typeof payload.exp === 'number' && payload.exp * 1000 > Date.now()
  } catch {
    return false
  }
}

/** 从本地 token 解码当前登录用户名（无 token 或解析失败返回空串） */
export function getCurrentUsername(): string {
  const token = getToken()
  if (!token) return ''
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return typeof payload.sub === 'string' ? payload.sub : ''
  } catch {
    return ''
  }
}
