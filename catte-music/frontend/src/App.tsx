import { lazy, Suspense, useEffect, useRef } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'

import Layout from './components/Layout'
import { isTokenValid, clearToken } from './utils/auth'
import { statsApi } from './api/client'

// 路由级代码分割：p5.js（粒子/雷达）等重依赖只在实际进入页面时加载
const Login = lazy(() => import('./pages/Login'))
const Home = lazy(() => import('./pages/Home'))
const NeteaseHome = lazy(() => import('./pages/NeteaseHome'))
const SongDetail = lazy(() => import('./pages/SongDetail'))
const SongRadar = lazy(() => import('./pages/SongRadar'))
const UserProfile = lazy(() => import('./pages/UserProfile'))
const UserSettings = lazy(() => import('./pages/UserSettings'))
const Admin = lazy(() => import('./pages/Admin'))

function PageLoader() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center text-slate-400">
      加载中…
    </div>
  )
}

function ProtectedLayout() {
  // token 不存在或已过期：清除并跳转登录页
  if (!isTokenValid()) {
    clearToken()
    return <Navigate to="/login" replace />
  }
  return (
    <Layout>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/netease" element={<NeteaseHome />} />
          <Route path="/song/:id" element={<SongDetail />} />
          <Route path="/song/:id/radar" element={<SongRadar />} />
          <Route path="/users/:id" element={<UserProfile />} />
          <Route path="/settings" element={<UserSettings />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={<ProtectedLayout />} />
      </Routes>
      <PageViewTracker />
    </Suspense>
  )
}

/** 页面访问上报：路由变化时记录一次访问（对 StrictMode 双执行去重）。 */
function PageViewTracker() {
  const location = useLocation()
  const lastRef = useRef<{ path: string; ts: number }>({ path: '', ts: 0 })

  useEffect(() => {
    const now = Date.now()
    // 同一路径 2 秒内不重复上报（React StrictMode 开发环境会重复触发 effect）
    if (location.pathname === lastRef.current.path && now - lastRef.current.ts < 2000) {
      return
    }
    lastRef.current = { path: location.pathname, ts: now }
    statsApi.pageview(location.pathname).catch(() => {})
  }, [location.pathname])

  return null
}
