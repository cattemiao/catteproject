import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Music, Sparkles } from 'lucide-react'
import { authApi } from '../api/client'

type Mode = 'login' | 'register'

export default function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await authApi.register(username, password)
      }
      const { data } = await authApi.login(username, password)
      localStorage.setItem('catte_token', data.access_token)
      navigate('/')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '请求失败，请重试'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[100dvh] flex items-center justify-center px-4 relative overflow-hidden">
      {/* 静态渐变占位（Step 2.5 接入 ParticleBg） */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-space via-midnight to-space" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-neon-purple/20 rounded-full blur-[120px] -z-10 animate-float" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-neon-cyan/15 rounded-full blur-[120px] -z-10 animate-float" style={{ animationDelay: '2s' }} />

      {/* 登录卡片 */}
      <div className="glass w-full max-w-md p-8 shadow-[0_0_50px_rgba(168,85,247,0.2)]">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="p-2 rounded-xl bg-neon-purple/20 shadow-[0_0_20px_rgba(168,85,247,0.4)]">
              <Music className="w-7 h-7 text-neon-cyan" />
            </div>
          </div>
          <h1 className="font-display text-2xl font-bold text-gradient">Catte Music</h1>
          <p className="text-slate-400 text-sm mt-1 flex items-center justify-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-neon-amber" />
            AI 音乐情绪可视化与探索平台
          </p>
        </div>

        {/* 切换标签 */}
        <div className="flex gap-2 mb-6 p-1 rounded-xl bg-white/5">
          {(['login', 'register'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === m
                  ? 'bg-gradient-to-r from-neon-purple to-neon-blue text-white shadow-[0_0_15px_rgba(168,85,247,0.4)]'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {m === 'login' ? '登录' : '注册'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={2}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10
                         focus:border-neon-purple/50 focus:outline-none focus:ring-2
                         focus:ring-neon-purple/20 transition-all text-white placeholder:text-slate-600"
              placeholder="输入用户名"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10
                         focus:border-neon-purple/50 focus:outline-none focus:ring-2
                         focus:ring-neon-purple/20 transition-all text-white placeholder:text-slate-600"
              placeholder="至少 6 位"
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button type="submit" disabled={loading} className="btn-neon w-full disabled:opacity-50">
            {loading ? '处理中...' : mode === 'login' ? '登录' : '注册并登录'}
          </button>
        </form>
      </div>
    </div>
  )
}
