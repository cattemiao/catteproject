import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowLeft,
  BarChart3,
  BrainCircuit,
  Disc,
  KeyRound,
  Loader2,
  Podcast,
  Save,
  Share2,
  Sparkles,
} from 'lucide-react'
import { authApi, usersApi, type UserStatsOut } from '../api/client'
import { getCurrentUsername } from '../utils/auth'

type Tab = 'dashboard' | 'settings'

// 七维指标的中文名与展示颜色（与管理后台保持一致）
const DIM_META: Record<string, { label: string; color: string }> = {
  loudness: { label: '响度', color: 'text-rose-400' },
  high_freq: { label: '高频', color: 'text-orange-400' },
  rhythm: { label: '节奏', color: 'text-yellow-400' },
  soundstage: { label: '声场', color: 'text-cyan-400' },
  layering: { label: '层次', color: 'text-purple-400' },
  soothing: { label: '舒缓', color: 'text-emerald-400' },
  prosody: { label: '韵律', color: 'text-pink-400' },
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
}: {
  label: string
  value: number
  icon: any
  color: string
  bg: string
}) {
  return (
    <div className="glass rounded-2xl p-4 flex items-center gap-3">
      <div className={`p-2.5 rounded-xl ${bg}`}>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs text-slate-400">{label}</div>
      </div>
    </div>
  )
}

function DashboardTab() {
  const [stats, setStats] = useState<UserStatsOut | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const { data } = await usersApi.meStats()
      setStats(data)
    } catch {
      setError('加载统计数据失败')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (!stats) {
    return <p className="text-slate-400 text-sm py-8 text-center">{error || '加载中…'}</p>
  }

  const maxEmotion = Math.max(1, ...stats.emotion_distribution.map((e) => e.count))

  return (
    <div className="space-y-6">
      {/* 音乐库统计 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Apple Music 专辑/歌单" value={stats.apple_albums} icon={Disc} color="text-sky-400" bg="bg-sky-400/10" />
        <StatCard label="网易云专辑/歌单" value={stats.netease_albums} icon={Podcast} color="text-red-400" bg="bg-red-400/10" />
        <StatCard label="分享" value={stats.shares} icon={Share2} color="text-emerald-400" bg="bg-emerald-400/10" />
        <StatCard label="AI 分析" value={stats.analyses} icon={BrainCircuit} color="text-purple-400" bg="bg-purple-400/10" />
      </div>

      {/* 整体音乐风格 */}
      <div className="glass rounded-2xl p-5">
        <h3 className="font-display font-bold text-white flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-neon-cyan" />
          整体音乐风格
        </h3>
        {stats.top_emotion ? (
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium text-white"
                  style={{ background: '#a855f720', border: '1px solid #a855f750' }}>
              <Sparkles className="w-3.5 h-3.5 text-neon-cyan" />
              {stats.top_emotion}
            </span>
            {stats.top_genres.map(([genre, count]) => (
              <span key={genre}
                    className="text-xs px-2 py-0.5 rounded-full border border-slate-500/40 text-slate-300 bg-white/5">
                {genre} {count}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 mt-2">暂无可统计的音乐风格，先在首页同步/分析一些歌曲吧。</p>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* 情绪分布 */}
        <div className="glass rounded-2xl p-5">
          <h3 className="font-display font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-neon-cyan" />
            情绪分布
          </h3>
          {stats.emotion_distribution.length === 0 ? (
            <p className="text-xs text-slate-500 mt-2">暂无情绪分析数据</p>
          ) : (
            stats.emotion_distribution.map((e) => (
              <div key={e.name} className="mt-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-300">{e.name}</span>
                  <span className="text-slate-500">{e.count} 首</span>
                </div>
                <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(e.count / maxEmotion) * 100}%`, background: e.color }}
                  />
                </div>
              </div>
            ))
          )}
        </div>

        {/* 七维平均画像 */}
        <div className="glass rounded-2xl p-5">
          <h3 className="font-display font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-neon-cyan" />
            声学七维画像
          </h3>
          <p className="text-[11px] text-slate-500 mt-1 mb-2">基于已分析歌曲的平均值</p>
          {stats.emotion_dimensions.map((d) => {
            const meta = DIM_META[d.dimension] ?? { label: d.dimension, color: 'text-slate-300' }
            return (
              <div key={d.dimension} className="mt-3">
                <div className="flex justify-between text-sm mb-1">
                  <span className={meta.color}>{meta.label}</span>
                  <span className="text-slate-500">{d.avg}</span>
                </div>
                <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-purple"
                    style={{ width: `${Math.min(100, d.avg)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function SettingsTab() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const changePassword = async () => {
    setError('')
    setMsg('')
    if (!oldPassword) {
      setError('请输入原密码')
      return
    }
    if (newPassword.length < 6) {
      setError('新密码至少 6 位')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致')
      return
    }
    setBusy(true)
    try {
      await authApi.changePassword(oldPassword, newPassword)
      setMsg('密码修改成功，下次登录请使用新密码')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: any) {
      setError(err?.response?.data?.detail || '密码修改失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="glass rounded-2xl p-5 max-w-2xl">
      <h3 className="font-display font-bold text-white flex items-center gap-2">
        <KeyRound className="w-5 h-5 text-neon-cyan" />
        修改密码
      </h3>
      <p className="text-xs text-slate-400 mb-4 mt-1">定期修改密码以保障账号安全。</p>
      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
      {msg && <p className="text-emerald-400 text-sm mb-3">{msg}</p>}
      <div className="flex flex-col gap-3 max-w-md">
        <input
          type="password"
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
          placeholder="原密码"
          className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:border-neon-purple/60"
        />
        <input
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="新密码（至少 6 位）"
          className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:border-neon-purple/60"
        />
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="确认新密码"
          className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:border-neon-purple/60"
        />
      </div>
      <button
        onClick={changePassword}
        disabled={busy}
        className="mt-4 flex w-32 justify-center items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-neon-purple/25 text-white hover:bg-neon-purple/35 shadow-[0_0_15px_rgba(168,85,247,0.3)] transition-all disabled:opacity-50"
      >
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
        修改密码
      </button>
    </div>
  )
}

export default function UserSettings() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('dashboard')
  const username = getCurrentUsername()
  const isAdmin = username === 'admin'

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="font-display font-bold text-2xl text-white">我的设置</h1>
          <p className="text-sm text-slate-400 mt-0.5">@{username} 的音乐数据总览与账号设置</p>
        </div>
      </div>

      {isAdmin && (
        <p className="text-sm text-amber-400 bg-amber-400/10 border border-amber-400/30 rounded-lg px-4 py-2">
          当前为管理员账号，数据总览与修改密码功能对管理员不可用，请前往管理后台操作。
        </p>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={() => setTab('dashboard')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
            tab === 'dashboard'
              ? 'bg-neon-purple/20 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <BarChart3 className="w-4 h-4 text-neon-cyan" />
          数据总览
        </button>
        <button
          onClick={() => setTab('settings')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
            tab === 'settings'
              ? 'bg-neon-purple/20 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <KeyRound className="w-4 h-4 text-neon-cyan" />
          账号设置
        </button>
      </div>

      {isAdmin ? null : tab === 'dashboard' ? <DashboardTab /> : <SettingsTab />}
    </div>
  )
}
