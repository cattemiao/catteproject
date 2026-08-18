import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowLeft,
  BarChart3,
  BrainCircuit,
  Check,
  Eye,
  KeyRound,
  Loader2,
  MessageSquare,
  Music2,
  ShieldCheck,
  Trash2,
  Users,
} from 'lucide-react'
import { adminApi, type AdminSuggestionOut, type AdminUserOut, type DashboardData } from '../api/client'
import { getCurrentUsername } from '../utils/auth'

type Tab = 'dashboard' | 'users' | 'suggestions'

const platformBadge = (hasApple: boolean, hasNetease: boolean) => {
  const items: string[] = []
  if (hasApple) items.push('Apple Music')
  if (hasNetease) items.push('网易云')
  return items.length ? items.join(' / ') : '—'
}

export default function Admin() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('dashboard')

  // 权限守卫：仅 admin 账号可进入
  useEffect(() => {
    if (getCurrentUsername() !== 'admin') {
      navigate('/', { replace: true })
    }
  }, [navigate])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-neon-purple/20 shadow-[0_0_20px_rgba(168,85,247,0.4)]">
            <ShieldCheck className="w-6 h-6 text-neon-cyan" />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-gradient">管理后台</h1>
            <p className="text-slate-400 text-sm">站点统计与用户、意见数据管理</p>
          </div>
        </div>
        <Link
          to="/"
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/5 transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          返回首页
        </Link>
      </div>

      {/* Tab 切换 */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 w-fit overflow-x-auto">
        <button
          onClick={() => setTab('dashboard')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
            tab === 'dashboard'
              ? 'bg-neon-purple/20 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <BarChart3 className="w-4 h-4 text-neon-cyan" />
          Dashboard
        </button>
        <button
          onClick={() => setTab('users')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
            tab === 'users'
              ? 'bg-neon-purple/20 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Users className="w-4 h-4 text-neon-cyan" />
          用户管理
        </button>
        <button
          onClick={() => setTab('suggestions')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
            tab === 'suggestions'
              ? 'bg-neon-purple/20 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <MessageSquare className="w-4 h-4 text-neon-cyan" />
          意见管理
        </button>
      </div>

      {tab === 'dashboard' ? <DashboardPanel /> : tab === 'users' ? <UserPanel /> : <SuggestionPanel />}
    </div>
  )
}

/* ───────────────────────── 用户管理 ───────────────────────── */

function UserPanel() {
  const [users, setUsers] = useState<AdminUserOut[] | null>(null)
  const [error, setError] = useState('')
  // 重置密码弹窗
  const [resetTarget, setResetTarget] = useState<AdminUserOut | null>(null)
  const [newPassword, setNewPassword] = useState('')
  // 删除确认弹窗
  const [deleteTarget, setDeleteTarget] = useState<AdminUserOut | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const { data } = await adminApi.users()
      setUsers(data)
    } catch {
      setError('加载用户列表失败')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const confirmReset = async () => {
    if (!resetTarget) return
    if (newPassword.length < 6) {
      setError('新密码至少 6 位')
      return
    }
    setBusy(true)
    try {
      await adminApi.resetPassword(resetTarget.id, newPassword)
      setResetTarget(null)
      setNewPassword('')
    } catch {
      setError('密码重置失败')
    } finally {
      setBusy(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setBusy(true)
    try {
      await adminApi.deleteUser(deleteTarget.id)
      setDeleteTarget(null)
      await load()
    } catch {
      setError('删除用户失败')
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return <p className="text-red-400 text-sm">{error}</p>
  }
  if (!users) {
    return <p className="text-slate-400 text-sm py-8 text-center">加载中…</p>
  }

  return (
    <>
      <div className="glass rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-white/10">
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">用户名</th>
                <th className="px-4 py-3 font-medium">绑定平台</th>
                <th className="px-4 py-3 font-medium text-right">歌曲</th>
                <th className="px-4 py-3 font-medium text-right">收藏</th>
                <th className="px-4 py-3 font-medium text-right">意见</th>
                <th className="px-4 py-3 font-medium">注册时间</th>
                <th className="px-4 py-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                    暂无注册用户
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                    <td className="px-4 py-3 text-slate-400">{u.id}</td>
                    <td className="px-4 py-3 text-white font-medium">{u.username}</td>
                    <td className="px-4 py-3 text-slate-300">
                      {platformBadge(u.has_apple_music, u.has_netease)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">{u.song_count}</td>
                    <td className="px-4 py-3 text-right text-slate-300">{u.favorite_count}</td>
                    <td className="px-4 py-3 text-right text-slate-300">{u.suggestion_count}</td>
                    <td className="px-4 py-3 text-slate-400">{u.created_at || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setResetTarget(u)}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-neon-purple/20 text-neon-cyan hover:bg-neon-purple/30 transition-all"
                        >
                          <KeyRound className="w-3.5 h-3.5" />
                          重置密码
                        </button>
                        <button
                          onClick={() => setDeleteTarget(u)}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <p className="text-xs text-slate-500">
        提示：删除用户会同时删除其同步的歌曲、情绪分析、收藏等全部数据，且不可恢复。
      </p>

      {/* 重置密码弹窗 */}
      {resetTarget && (
        <Modal onClose={() => setResetTarget(null)}>
          <h3 className="font-display font-bold text-lg mb-1">重置密码</h3>
          <p className="text-sm text-slate-400 mb-4">
            为用户 <span className="text-white font-medium">{resetTarget.username}</span> 设置新密码
          </p>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="新密码（至少 6 位）"
            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:border-neon-purple/60 mb-4"
          />
          <div className="flex justify-end gap-2">
            <ModalBtn onClick={() => setResetTarget(null)}>取消</ModalBtn>
            <ModalBtn primary onClick={confirmReset} disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              确认重置
            </ModalBtn>
          </div>
        </Modal>
      )}

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <Modal onClose={() => setDeleteTarget(null)}>
          <h3 className="font-display font-bold text-lg mb-1 text-red-400">确认删除用户</h3>
          <p className="text-sm text-slate-400 mb-4">
            将删除用户 <span className="text-white font-medium">{deleteTarget.username}</span>
            （{deleteTarget.song_count} 首歌曲、{deleteTarget.favorite_count} 条收藏、
            {deleteTarget.suggestion_count} 条意见）及其全部关联数据，此操作不可恢复。
          </p>
          <div className="flex justify-end gap-2">
            <ModalBtn onClick={() => setDeleteTarget(null)}>取消</ModalBtn>
            <ModalBtn danger onClick={confirmDelete} disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              确认删除
            </ModalBtn>
          </div>
        </Modal>
      )}
    </>
  )
}

/* ───────────────────────── 意见管理 ───────────────────────── */

function SuggestionPanel() {
  const [suggestions, setSuggestions] = useState<AdminSuggestionOut[] | null>(null)
  const [error, setError] = useState('')
  const [editTarget, setEditTarget] = useState<AdminSuggestionOut | null>(null)
  const [editContent, setEditContent] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AdminSuggestionOut | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const { data } = await adminApi.suggestions()
      setSuggestions(data)
    } catch {
      setError('加载意见列表失败')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const confirmEdit = async () => {
    if (!editTarget) return
    const content = editContent.trim()
    if (!content) {
      setError('内容不能为空')
      return
    }
    setBusy(true)
    try {
      await adminApi.updateSuggestion(editTarget.id, content)
      setEditTarget(null)
      await load()
    } catch {
      setError('意见修改失败')
    } finally {
      setBusy(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setBusy(true)
    try {
      await adminApi.deleteSuggestion(deleteTarget.id)
      setDeleteTarget(null)
      await load()
    } catch {
      setError('意见删除失败')
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return <p className="text-red-400 text-sm">{error}</p>
  }
  if (!suggestions) {
    return <p className="text-slate-400 text-sm py-8 text-center">加载中…</p>
  }

  return (
    <>
      <div className="space-y-3">
        {suggestions.length === 0 ? (
          <div className="glass rounded-2xl py-10 text-center text-slate-500 text-sm">
            暂无用户提交的意见
          </div>
        ) : (
          suggestions.map((s) => (
            <div key={s.id} className="glass rounded-2xl p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="text-xs text-slate-500">#{s.id}</span>
                  <span className="text-sm font-medium text-neon-cyan">{s.username}</span>
                  <span className="text-xs text-slate-500">{s.created_at || '—'}</span>
                </div>
                <p className="text-sm text-white/90 whitespace-pre-wrap break-words">{s.content}</p>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  onClick={() => {
                    setEditTarget(s)
                    setEditContent(s.content)
                  }}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-neon-purple/20 text-neon-cyan hover:bg-neon-purple/30 transition-all"
                >
                  <KeyRound className="w-3.5 h-3.5" />
                  修改
                </button>
                <button
                  onClick={() => setDeleteTarget(s)}
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  删除
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* 修改意见弹窗 */}
      {editTarget && (
        <Modal onClose={() => setEditTarget(null)}>
          <h3 className="font-display font-bold text-lg mb-1">修改意见</h3>
          <p className="text-sm text-slate-400 mb-4">
            来自 <span className="text-white font-medium">{editTarget.username}</span> 的意见 #{editTarget.id}
          </p>
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:border-neon-purple/60 mb-4 resize-none"
          />
          <div className="flex justify-end gap-2">
            <ModalBtn onClick={() => setEditTarget(null)}>取消</ModalBtn>
            <ModalBtn primary onClick={confirmEdit} disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
              保存
            </ModalBtn>
          </div>
        </Modal>
      )}

      {/* 删除意见确认弹窗 */}
      {deleteTarget && (
        <Modal onClose={() => setDeleteTarget(null)}>
          <h3 className="font-display font-bold text-lg mb-1 text-red-400">确认删除意见</h3>
          <p className="text-sm text-slate-400 mb-4">
            将删除来自 <span className="text-white font-medium">{deleteTarget.username}</span> 的意见
            #{deleteTarget.id}，此操作不可恢复。
          </p>
          <div className="flex justify-end gap-2">
            <ModalBtn onClick={() => setDeleteTarget(null)}>取消</ModalBtn>
            <ModalBtn danger onClick={confirmDelete} disabled={busy}>
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              确认删除
            </ModalBtn>
          </div>
        </Modal>
      )}
    </>
  )
}

/* ───────────────────────── 通用弹窗 ───────────────────────── */

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="glass w-full max-w-md p-6 rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

function ModalBtn({
  children,
  onClick,
  primary,
  danger,
  disabled,
}: {
  children: React.ReactNode
  onClick: () => void
  primary?: boolean
  danger?: boolean
  disabled?: boolean
}) {
  const base =
    'flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50'
  const color = danger
    ? 'bg-red-500/15 text-red-400 hover:bg-red-500/25'
    : primary
      ? 'bg-neon-purple/25 text-white hover:bg-neon-purple/35 shadow-[0_0_15px_rgba(168,85,247,0.3)]'
      : 'bg-white/5 text-slate-300 hover:bg-white/10'
  return (
    <button className={`${base} ${color}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  )
}

/* ───────────────────────── Dashboard 统计 ───────────────────────── */

function DashboardPanel() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi
      .dashboard()
      .then(({ data }) => setData(data))
      .catch(() => setError('加载统计数据失败'))
  }, [])

  if (error) {
    return <p className="text-red-400 text-sm">{error}</p>
  }
  if (!data) {
    return <p className="text-slate-400 text-sm py-8 text-center">加载中…</p>
  }

  const cards = [
    { label: '注册用户', value: data.total_users, icon: Users, color: 'text-neon-cyan', bg: 'bg-neon-cyan/10' },
    { label: '总访问量', value: data.total_visits, icon: Eye, color: 'text-neon-purple', bg: 'bg-neon-purple/10' },
    { label: '同步歌曲', value: data.total_songs, icon: Music2, color: 'text-neon-amber', bg: 'bg-neon-amber/10' },
    { label: 'AI 分析次数', value: data.total_analyses, icon: BrainCircuit, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  ]

  // 歌曲按平台分组：platform -> [{type, count}]
  const platformGroups = new Map<string, { label: string; value: number }[]>()
  for (const row of data.songs_by_platform) {
    const key = row.platform === 'apple' ? 'Apple Music' : row.platform === 'netease' ? '网易云' : row.platform
    if (!platformGroups.has(key)) platformGroups.set(key, [])
    platformGroups.get(key)!.push({ label: row.type, value: row.count })
  }

  const daily = (rows: { date: string; count: number }[]) =>
    rows.map((r) => ({ label: r.date.slice(5), value: r.count }))

  // 七维指标中文名与颜色
  const dimMeta: Record<string, { label: string; color: string }> = {
    loudness: { label: '响度', color: '#f43f5e' },
    high_freq: { label: '高频', color: '#f97316' },
    rhythm: { label: '节奏', color: '#fbbf24' },
    soundstage: { label: '声场', color: '#22d3ee' },
    layering: { label: '层次', color: '#a855f7' },
    soothing: { label: '舒缓', color: '#34d399' },
    prosody: { label: '韵律', color: '#ec4899' },
  }

  const dims = data.emotion_dimensions.map((d) => ({
    label: dimMeta[d.dimension]?.label ?? d.dimension,
    value: d.avg,
    color: dimMeta[d.dimension]?.color ?? '#a855f7',
    hint: `${d.count} 首样本`,
  }))

  return (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="glass rounded-2xl p-4 flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${bg}`}>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <div className="min-w-0">
              <div className="text-2xl font-bold text-white leading-tight">{value}</div>
              <div className="text-xs text-slate-400 truncate">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* 访问量 & AI 分析趋势 */}
      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="网站访问量（近 14 天）" subtitle={`累计 ${data.total_visits} 次访问`}>
          <BarChart data={daily(data.visits_by_day)} color="#22d3ee" />
        </ChartCard>
        <ChartCard title="AI 情绪分析（近 14 天）" subtitle={`累计 ${data.total_analyses} 次分析`}>
          <BarChart data={daily(data.analysis_by_day)} color="#a855f7" />
        </ChartCard>
      </div>

      {/* 歌曲平台分布 & 情绪分布 */}
      <div className="grid lg:grid-cols-2 gap-4">
        <ChartCard title="歌曲平台分布" subtitle="按平台与内容类型统计">
          {data.songs_by_platform.length === 0 ? (
            <EmptyChart />
          ) : (
            <div className="space-y-5">
              {[...platformGroups.entries()].map(([platform, rows]) => (
                <div key={platform}>
                  <div className="flex items-center gap-1.5 mb-2">
                    <Activity className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-xs font-medium text-slate-400">{platform}</span>
                  </div>
                  <BarChart
                    data={rows}
                    color={platform === 'Apple Music' ? '#22d3ee' : '#f87171'}
                    height={120}
                  />
                </div>
              ))}
            </div>
          )}
        </ChartCard>
        <ChartCard title="情绪分析结果分布" subtitle="按情绪分类统计">
          {data.emotion_distribution.length === 0 ? (
            <EmptyChart />
          ) : (
            <BarChart
              data={data.emotion_distribution.map((e) => ({ label: e.name, value: e.count, color: e.color }))}
              height={200}
            />
          )}
        </ChartCard>
      </div>

      {/* 情绪七维指标 */}
      <ChartCard title="情绪七维指标统计" subtitle="AI 分析结果的平均分（0-100）">
        {dims.length === 0 ? (
          <EmptyChart />
        ) : (
          <BarChart data={dims} height={200} />
        )}
      </ChartCard>
    </div>
  )
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <div className="glass rounded-2xl p-5">
      <h3 className="font-display font-bold text-white">{title}</h3>
      {subtitle && <p className="text-xs text-slate-400 mb-4">{subtitle}</p>}
      {children}
    </div>
  )
}

function EmptyChart() {
  return <p className="text-sm text-slate-500 py-10 text-center">暂无数据</p>
}

/** 纯 CSS 纵向柱状图（无第三方依赖）。 */
function BarChart({
  data,
  color = '#a855f7',
  height = 160,
}: {
  data: { label: string; value: number; color?: string; hint?: string }[]
  color?: string
  height?: number
}) {
  const max = Math.max(...data.map((d) => d.value), 1)
  return (
    <div className="flex items-end gap-1.5" style={{ height }}>
      {data.map((d) => (
        <div
          key={d.label}
          className="flex-1 flex flex-col items-center justify-end gap-1 h-full min-w-0"
          title={`${d.label}: ${d.value}${d.hint ? `（${d.hint}）` : ''}`}
        >
          <span className="text-[10px] text-slate-400 leading-none">
            {d.value > 0 ? d.value : ''}
          </span>
          <div
            className="w-full rounded-t-md transition-all duration-500"
            style={{
              height: `${d.value > 0 ? Math.max((d.value / max) * 100, 4) : 2}%`,
              background: d.color ?? color,
              opacity: d.value > 0 ? 0.9 : 0.15,
            }}
          />
          <span className="text-[10px] text-slate-500 leading-none truncate w-full text-center">
            {d.label}
          </span>
        </div>
      ))}
    </div>
  )
}
