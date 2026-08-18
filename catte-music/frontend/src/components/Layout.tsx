import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Home, Heart, LogOut, Music, Podcast, User } from 'lucide-react'
import logo from '../../logo.png'
import SuggestionBox from './SuggestionBox'
import { clearToken, getCurrentUsername } from '../utils/auth'
import { songsApi } from '../api/client'

export default function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const username = getCurrentUsername()

  // 专辑详情页路径为 /song/:id，需按歌曲平台高亮对应导航
  const [songPlatform, setSongPlatform] = useState<string | null>(null)
  useEffect(() => {
    const match = location.pathname.match(/^\/song\/(\d+)/)
    if (match) {
      setSongPlatform(null)
      songsApi
        .get(Number(match[1]))
        .then(({ data }) => setSongPlatform(data.platform ?? 'apple'))
        .catch(() => setSongPlatform(null))
    } else {
      setSongPlatform(null)
    }
  }, [location.pathname])

  const songLoading = !!location.pathname.match(/^\/song\/(\d+)/) && songPlatform === null
  const isNetease = location.pathname.startsWith('/netease') || songPlatform === 'netease'

  const logout = () => {
    clearToken()
    navigate('/login')
  }

  const navItems = [
    { to: '/', icon: Home, label: '首页' },
    { to: '/favorites', icon: Heart, label: '收藏' },
  ]

  return (
    <div className="min-h-[100dvh] flex flex-col">
      {/* 顶部导航 */}
      <header className="glass sticky top-0 z-50 px-4 sm:px-8 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <img src={logo} alt="Catte Music" className="h-8 w-8 object-contain" />
          <span className="font-display font-bold text-lg text-gradient">Catte Music</span>
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2">
          {/* 平台切换 */}
          <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 mr-1 sm:mr-2">
            <Link
              to="/"
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                !isNetease && !songLoading
                  ? 'bg-neon-purple/20 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Music className="w-3.5 h-3.5 text-neon-cyan" />
              <span className="hidden sm:inline">Apple Music</span>
            </Link>
            <Link
              to="/netease"
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isNetease
                  ? 'bg-red-500/20 text-white shadow-[0_0_12px_rgba(239,68,68,0.3)]'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Podcast className="w-3.5 h-3.5 text-red-400" />
              <span className="hidden sm:inline">网易云</span>
            </Link>
          </div>
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-all
                ${location.pathname === to
                  ? 'bg-neon-purple/20 text-white shadow-[0_0_15px_rgba(168,85,247,0.3)]'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden sm:inline">{label}</span>
            </Link>
          ))}
          <SuggestionBox />
          {username && (
            <div className="hidden md:flex items-center gap-1.5 px-3 py-2 text-sm text-slate-300 ml-1 border-l border-white/10">
              {/* 仅桌面端（≥768px）显示用户名，移动端隐藏 */}
              <User className="w-4 h-4 text-neon-cyan flex-shrink-0" />
              <span className="max-w-[120px] truncate">{username}</span>
            </div>
          )}
          <button
            onClick={logout}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </nav>
      </header>

      {/* 主内容区 */}
      <main className="flex-1 px-4 sm:px-8 py-6 max-w-7xl mx-auto w-full">
        {children}
      </main>
    </div>
  )
}
