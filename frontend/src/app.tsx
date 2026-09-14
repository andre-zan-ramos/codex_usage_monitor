import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom'
import { Shell } from './components'
import { Dashboard } from './pages/dashboard'
import { ThreadDetail } from './pages/thread-detail'

function ThreadRoute() {
  const { id } = useParams()
  return <Shell>{id ? <ThreadDetail id={id} /> : <Dashboard />}</Shell>
}

export function App() {
  return <BrowserRouter><Routes><Route path="/" element={<Shell><Dashboard /></Shell>} /><Route path="/threads/:id" element={<ThreadRoute />} /></Routes></BrowserRouter>
}
