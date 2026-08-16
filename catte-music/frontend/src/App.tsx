import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

import Layout from './components/Layout'

// 路由级代码分割：p5.js（粒子/雷达）等重依赖只在实际进入页面时加载
const Login = lazy(() => import('./pages/Login'))
const Home = lazy(() => import('./pages/Home'))
const NeteaseHome = lazy(() => import('./pages/NeteaseHome'))
const SongDetail = lazy(() => import('./pages/SongDetail'))
const SongRadar = lazy(() => import('./pages/SongRadar'))
const Favorites = lazy(() => import('./pages/Favorites'))

function PageLoader() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center text-slate-400">
      加载中…
    </div>
  )
}

function ProtectedLayout() {
  const token = localStorage.getItem('catte_token')
  if (!token) return <Navigate to="/login" replace />
  return (
    <Layout>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/netease" element={<NeteaseHome />} />
          <Route path="/song/:id" element={<SongDetail />} />
          <Route path="/song/:id/radar" element={<SongRadar />} />
          <Route path="/favorites" element={<Favorites />} />
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
    </Suspense>
  )
}
