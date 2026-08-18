import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { QRCodeCanvas } from 'qrcode.react'
import { Disc, Music, RefreshCw, Podcast, Search, TrendingUp, Trash2 } from 'lucide-react'
import { neteaseApi, songsApi } from '../api/client'
import ParticleBg from '../components/ParticleBg'
import type { SongOut } from '../types'

const PAGE_SIZE = 20

export default function NeteaseHome() {
  const [bound, setBound] = useState(false)
  const [nickname, setNickname] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [qrContent, setQrContent] = useState('')
  const [qrMsg, setQrMsg] = useState('')
  const [qrState, setQrState] = useState<'idle' | 'loading' | 'waiting' | 'success' | 'error'>('idle')
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [songs, setSongs] = useState<SongOut[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [searchQ, setSearchQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [clearMsg, setClearMsg] = useState('')
  const pollTimer = useRef<number | null>(null)

  const loadSongs = (targetPage = 1) => {
    // 拉取网易云平台的歌曲
    songsApi.list({ page: targetPage, size: PAGE_SIZE, platform: 'netease' })
      .then(({ data }) => {
        setSongs(data.items)
        setTotal(data.total)
        setPage(targetPage)
      })
      .catch(() => {})
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const clearNetease = async () => {
    if (!window.confirm('确定清空已导入的网易云歌曲吗？清空后可重新同步。')) return
    setClearing(true)
    setClearMsg('')
    try {
      const { data } = await songsApi.clear('netease')
      setSongs([])
      setPage(1)
      setTotal(0)
      setClearMsg(`已清空 ${data.deleted} 首，可重新同步`)
    } catch {
      setClearMsg('清空失败，请重试')
    } finally {
      setClearing(false)
    }
  }

  const refreshStatus = async () => {
    try {
      const { data } = await neteaseApi.status()
      setBound(data.bound)
      if (data.bound) {
        setNickname(data.nickname || '')
        setAvatarUrl(data.avatar_url || '')
      }
    } catch {
      // 未登录或网络问题
    }
  }

  useEffect(() => {
    refreshStatus()
    loadSongs()
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current)
    }
  }, [])

  const startQr = async () => {
    setQrState('loading')
    setQrMsg('')
    try {
      const { data } = await neteaseApi.createQr()
      if (data.error || !data.key) {
        setQrState('error')
        setQrMsg(data.error || '获取二维码失败')
        return
      }
      setQrContent(data.content)
      setQrState('waiting')
      setQrMsg('请使用网易云音乐 App 扫码登录')
      // 轮询扫码状态
      if (pollTimer.current) window.clearInterval(pollTimer.current)
      pollTimer.current = window.setInterval(async () => {
        const { data: st } = await neteaseApi.checkQr(data.key).catch(() => ({ data: null }))
        if (!st) return
        setQrMsg(st.message)
        if (st.code === 803) {
          setQrState('success')
          setQrMsg(`欢迎，${st.nickname || '网易云用户'}！`)
          setNickname(st.nickname || '')
          setAvatarUrl(st.avatar_url || '')
          setBound(true)
          if (pollTimer.current) window.clearInterval(pollTimer.current)
          setQrContent('')
          setTimeout(() => loadSongs(), 300)
        } else if (st.code === 800) {
          setQrState('error')
          if (pollTimer.current) window.clearInterval(pollTimer.current)
        }
      }, 2500)
    } catch {
      setQrState('error')
      setQrMsg('获取二维码失败，请重试')
    }
  }

  const syncRecent = async () => {
    setSyncing(true)
    setSyncMsg('')
    try {
      // 第一步：最近播放
      const { data: recent } = await neteaseApi.syncRecent(10)
      // 第二步：音乐库（收藏的专辑 + 收藏的歌单）
      const { data: lib } = await neteaseApi.library(100)
      setSyncMsg(
        `同步成功！新增最近播放 ${recent.synced} 首 + 音乐库（专辑 ${lib.albums.length} 张、歌单 ${lib.playlists.length} 个）`,
      )
      loadSongs()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '同步失败，请重试'
      setSyncMsg(msg)
    } finally {
      setSyncing(false)
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQ.trim()) return
    setSearching(true)
    try {
      const { data } = await neteaseApi.search(searchQ, 10)
      setSongs(data)
      setTotal(0) // 搜索结果不分页，隐藏翻页
    } catch {
      setSyncMsg('搜索失败，请重试')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="relative">
      <ParticleBg color="#ef4444" />

      {/* Hero */}
      <section className="text-center py-12 mb-8">
        <div className="inline-flex items-center gap-2 mb-3">
          <Podcast className="w-6 h-6 text-red-400" />
          <span className="text-sm font-medium text-red-400 tracking-widest">NETEASE MUSIC</span>
        </div>
        <h1 className="font-display text-3xl sm:text-5xl font-extrabold mb-4">
          <span className="text-gradient">听见你的网易云情绪</span>
        </h1>
        <p className="text-slate-400 max-w-xl mx-auto">
          扫码绑定网易云账号，用 AI 解析你的听歌情绪，可视化呈现听歌画像
        </p>

        {!bound ? (
          <div className="mt-6 flex justify-center">
            {qrState === 'idle' || qrState === 'loading' || qrState === 'error' ? (
              <button onClick={startQr} disabled={qrState === 'loading'} className="btn-neon disabled:opacity-50">
                <RefreshCw className={`w-4 h-4 ${qrState === 'loading' ? 'animate-spin' : ''}`} />
                扫码登录网易云
              </button>
            ) : (
              <div className="glass p-6 rounded-2xl inline-block">
                <div className="bg-white p-3 rounded-xl w-[180px] h-[180px] mx-auto">
                  <QRCodeCanvas value={qrContent} size={156} />
                </div>
                <p className={`mt-3 text-sm ${qrMsg.includes('失败') || qrMsg.includes('过期') ? 'text-red-400' : 'text-slate-300'}`}>
                  {qrMsg}
                </p>
                <button onClick={startQr} className="text-xs text-slate-500 hover:text-white mt-2">
                  刷新二维码
                </button>
              </div>
            )}
            {qrState === 'error' && qrMsg && (
              <p className="mt-3 text-sm text-red-400 w-full text-center">{qrMsg}</p>
            )}
          </div>
        ) : (
          <div className="mt-6 flex flex-col items-center gap-4">
            <div className="flex items-center gap-3">
              {avatarUrl && (
                <img src={avatarUrl} alt={nickname} className="w-10 h-10 rounded-full object-cover border-2 border-red-500/50" />
              )}
              <div className="text-left">
                <p className="text-white font-medium">{nickname || '网易云用户'}</p>
                <p className="text-xs text-green-400">已绑定</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={syncRecent} disabled={syncing} className="btn-neon disabled:opacity-50">
                <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
                {syncing ? '同步中...' : '同步最近播放'}
              </button>
              <button onClick={startQr} className="px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white hover:border-red-500/40 transition-all">
                重新扫码
              </button>
            </div>
            {syncMsg && (
              <p className={`text-sm ${syncMsg.includes('成功') ? 'text-neon-cyan' : 'text-red-400'}`}>
                {syncMsg}
              </p>
            )}
          </div>
        )}
      </section>

      {/* 搜索网易云歌曲 */}
      <section className="mb-10">
        <form onSubmit={handleSearch} className="flex items-center gap-2 max-w-md mx-auto">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/5 border border-white/10
                         focus:border-red-500/50 focus:outline-none focus:ring-2 focus:ring-red-500/20
                         transition-all text-white placeholder:text-slate-600"
              placeholder="搜索网易云歌曲（无需登录）"
            />
          </div>
          <button type="submit" disabled={searching} className="px-4 py-2.5 rounded-xl bg-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/30 transition-all disabled:opacity-50">
            搜索
          </button>
        </form>
      </section>

      {/* 网易云歌曲列表 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl font-bold flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-red-400" />
            网易云音乐库
          </h2>
          <button
            onClick={clearNetease}
            disabled={clearing || songs.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-xs font-medium hover:bg-red-500/25 hover:border-red-500/50 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Trash2 className={`w-3.5 h-3.5 ${clearing ? 'animate-pulse' : ''}`} />
            {clearing ? '清空中…' : '清空'}
          </button>
        </div>
        {clearMsg && (
          <p className="text-xs mb-4 text-neon-cyan">{clearMsg}</p>
        )}
        {songs.length === 0 ? (
          <p className="text-slate-500 text-sm py-8 text-center">
            {bound ? '暂无歌曲，点击上方"同步最近播放"拉取听歌记录' : '绑定账号并同步后，这里将展示你的网易云听歌记录'}
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {songs.map((song) => (
              <NeteaseSongCard key={song.id} song={song} />
            ))}
          </div>
        )}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-center gap-4 mt-8">
            <button
              onClick={() => loadSongs(page - 1)}
              disabled={page <= 1}
              className="px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white hover:border-red-500/40 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              上一页
            </button>
            <span className="text-sm text-slate-500">
              第 {page} / {totalPages} 页 · 共 {total} 首
            </span>
            <button
              onClick={() => loadSongs(page + 1)}
              disabled={page >= totalPages}
              className="px-4 py-2 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white hover:border-red-500/40 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              下一页
            </button>
          </div>
        )}
      </section>
    </div>
  )
}

function NeteaseSongCard({ song }: { song: SongOut }) {
  return (
    <Link to={`/song/${song.id}`} className="card group cursor-pointer">
      <div className="aspect-square rounded-xl bg-gradient-to-br from-red-500/30 to-neon-purple/20 mb-3 flex items-center justify-center group-hover:shadow-[0_0_25px_rgba(239,68,68,0.3)] transition-all overflow-hidden relative">
        {song.artwork_url ? (
          <img
            src={song.artwork_url}
            alt={song.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <Music className="w-10 h-10 text-white/40 group-hover:scale-110 transition-transform" />
        )}
        <span className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-red-500/80 text-[10px] text-white font-medium">
          网易云
        </span>
      </div>
      <h3 className="font-medium text-sm truncate group-hover:text-red-400 transition-colors flex items-center gap-1">
        {song.type === 'albums' ? <Disc className="w-3.5 h-3.5 text-red-400/60 flex-shrink-0" /> : <Music className="w-3.5 h-3.5 text-red-400/60 flex-shrink-0" />}
        {song.title}
      </h3>
      <p className="text-xs text-slate-500 truncate">{song.artist}</p>
    </Link>
  )
}
