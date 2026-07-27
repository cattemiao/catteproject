import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Home from './pages/Home'
import SongDetail from './pages/SongDetail'
import Favorites from './pages/Favorites'
import LyricsGallery from './pages/LyricsGallery'
import Layout from './components/Layout'

function ProtectedLayout() {
  const token = localStorage.getItem('catte_token')
  if (!token) return <Navigate to="/login" replace />
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/song/:id" element={<SongDetail />} />
        <Route path="/song/:id/lyrics" element={<LyricsGallery />} />
        <Route path="/favorites" element={<Favorites />} />
      </Routes>
    </Layout>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/*" element={<ProtectedLayout />} />
    </Routes>
  )
}
