// MusicKit JS 按需加载：避免在 index.html 中同步加载国外 CDN 脚本阻塞首屏
let musicKitPromise: Promise<any> | null = null

const MUSICKIT_CDN_URL = 'https://js-cdn.music.apple.com/musickit/v1/musickit.js'

export function loadMusicKit(): Promise<any> {
  const existing = (window as unknown as { MusicKit?: any }).MusicKit
  if (existing) return Promise.resolve(existing)
  if (!musicKitPromise) {
    musicKitPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = MUSICKIT_CDN_URL
      s.async = true
      s.onload = () => {
        const mk = (window as unknown as { MusicKit?: any }).MusicKit
        if (mk) resolve(mk)
        else reject(new Error('MusicKit JS 未正确加载'))
      }
      s.onerror = () => reject(new Error('MusicKit JS 加载失败'))
      document.head.appendChild(s)
    })
  }
  return musicKitPromise
}
