import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Office from './pages/Office'
import Proposals from './pages/Proposals'
import Crons from './pages/Crons'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/office"
          element={
            <ProtectedRoute>
              <Office />
            </ProtectedRoute>
          }
        />
        <Route
          path="/proposals"
          element={
            <ProtectedRoute>
              <Proposals />
            </ProtectedRoute>
          }
        />
        <Route
          path="/crons"
          element={
            <ProtectedRoute>
              <Crons />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/office" replace />} />
        <Route path="*" element={<Navigate to="/office" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
