import { Routes, Route } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { Activity } from 'lucide-react'
import HealthBar from './components/HealthBar'
import Dashboard from './pages/Dashboard'
import IncidentDetail from './pages/IncidentDetail'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Navbar */}
      <header className="border-b border-gray-800 bg-gray-950 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-white font-bold text-sm">
            <Activity size={18} className="text-red-500" />
            IMS · Incident Management System
          </Link>
          <HealthBar />
        </div>
      </header>

      {/* Main */}
      <main className="flex-1">
        <Routes>
          <Route path="/"                 element={<Dashboard />} />
          <Route path="/incidents/:id"    element={<IncidentDetail />} />
        </Routes>
      </main>

      <footer className="text-center text-xs text-gray-700 py-4 border-t border-gray-900">
        Zeotap · Infrastructure / SRE Intern Assignment · Aman
      </footer>
    </div>
  )
}
