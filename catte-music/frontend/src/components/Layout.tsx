import { type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Home, Heart, LogOut, Music } from 'lucide-react'

export default function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()

  const logout = () => {
    localStorage.removeItem('catte_token')
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
          <Music className="w-6 h-6 text-neon-cyan" />
          <span className="font-display font-bold text-lg text-gradient">Catte Music</span>
        </Link>
        <nav className="flex items-center gap-1 sm:gap-2">
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
