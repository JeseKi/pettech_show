import { BrowserRouter as Router, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import ProfilePage from './pages/profile/ProfilePage'
import SecurityPage from './pages/profile/SecurityPage'
import DevicesPage from './pages/profile/DevicesPage'
import AdminManagementPage from './pages/admin/AdminManagementPage'
import LoginPage from './pages/auth/LoginPage'
import ConfirmPasswordChangePage from './pages/auth/ConfirmPasswordChangePage'
import RegisterPage from './pages/auth/RegisterPage'
import ResetPasswordPage from './pages/auth/ResetPasswordPage'
import OAuthAuthorizePage from './pages/auth/OAuthAuthorizePage'
import OAuthDeviceAuthorizePage from './pages/auth/OAuthDeviceAuthorizePage'
import LandingPage from './pages/landing/LandingPage'
import DashboardPage from './pages/dashboard/DashboardPage'
import ChatHomePage from './pages/chatHome'
import AiwikiPage from './pages/aiwiki'
import SeedMatrixPage from './pages/seedMatrix'
import DailyWriterPage from './pages/dailyWriter'
import InteractiveMoviePage from './pages/interactiveMovie'
import CapabilityEntryPage from './pages/capabilities/CapabilityEntryPage'
import { AuthProvider, RequireAdmin, RequireAuth } from './providers/AuthProvider'
import { RuntimeConfigProvider } from './providers/RuntimeConfigProvider'
import ThemeToggle from './components/theme/ThemeToggle'
import GestureControlSidebar from './components/gesture/GestureControlSidebar'
import { DAILY_WRITER_MODES, SEED_MATRIX_MODES, VISIBLE_CAPABILITY_ENTRIES } from './lib/workflowModes'

function ThemeToggleGate() {
  const location = useLocation()
  if (
    location.pathname === '/'
    || location.pathname === '/agents'
    || location.pathname.startsWith('/agents/chat/')
    || location.pathname === '/landing'
    || location.pathname === '/interactive-movie'
    || location.pathname === '/knowledge-base'
  ) {
    return null
  }
  return <ThemeToggle />
}

function GestureControlGate() {
  const location = useLocation()
  if (
    location.pathname === '/'
    || location.pathname === '/agents'
    || location.pathname.startsWith('/agents/chat/')
  ) {
    return null
  }
  return <GestureControlSidebar />
}

function LegacyChatSessionRedirect() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  return <Navigate to={sessionId ? `/agents/chat/${encodeURIComponent(sessionId)}` : '/agents'} replace />
}

export default function App() {
  return (
    <Router>
      <RuntimeConfigProvider>
        <AuthProvider>
          <>
            <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/landing" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
            <Route path="/profile/password-change/:token" element={<ConfirmPasswordChangePage />} />
            <Route
              path="/oauth/authorize"
              element={
                <RequireAuth>
                  <OAuthAuthorizePage />
                </RequireAuth>
              }
            />
            <Route
              path="/oauth/device"
              element={
                <RequireAuth>
                  <OAuthDeviceAuthorizePage />
                </RequireAuth>
              }
            />
            <Route
              path="/knowledge-base"
              element={
                <RequireAuth>
                  <AiwikiPage key="knowledge-base" mode="full" />
                </RequireAuth>
              }
            />
            <Route
              path="/interactive-movie"
              element={
                <RequireAuth>
                  <InteractiveMoviePage />
                </RequireAuth>
              }
            />
            <Route
              path="/agents"
              element={
                <RequireAuth>
                  <ChatHomePage />
                </RequireAuth>
              }
            />
            <Route
              path="/agents/chat/:sessionId"
              element={
                <RequireAuth>
                  <ChatHomePage />
                </RequireAuth>
              }
            />
            <Route path="/dashboard/chat/:sessionId" element={<LegacyChatSessionRedirect />} />
            <Route
              element={
              <RequireAuth>
                  <MainLayout />
                </RequireAuth>
              }
            >
              <Route path="/aiwiki" element={<Navigate to="/knowledge-base" replace />} />
              <Route path="/aiwiki/materials" element={<Navigate to="/knowledge-base" replace />} />
              <Route path="/aiwiki/search-assets" element={<Navigate to="/knowledge-base" replace />} />
              <Route path="/aiwiki/full" element={<Navigate to="/knowledge-base" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/seed-matrices" element={<Navigate to={SEED_MATRIX_MODES.standard.path} replace />} />
              <Route path="/seed-matrices/standard" element={<SeedMatrixPage key="seed-standard" mode="standard" />} />
              <Route path="/seed-matrices/batch" element={<SeedMatrixPage key="seed-batch" mode="batch" />} />
              <Route path="/seed-matrices/high-frequency" element={<SeedMatrixPage key="seed-high-frequency" mode="high-frequency" />} />
              <Route path="/seed-matrices/hook-driven" element={<SeedMatrixPage key="seed-hook-driven" mode="hook-driven" />} />
              <Route path="/daily-writer" element={<Navigate to={DAILY_WRITER_MODES.single.path} replace />} />
              <Route path="/daily-writer/single" element={<DailyWriterPage key="writer-single" mode="single" />} />
              <Route path="/daily-writer/batch" element={<DailyWriterPage key="writer-batch" mode="batch" />} />
              <Route path="/daily-writer/five-pack" element={<DailyWriterPage key="writer-five-pack" mode="five-pack" />} />
              {VISIBLE_CAPABILITY_ENTRIES.map((entry) => (
                <Route
                  key={entry.key}
                  path={entry.path}
                  element={<CapabilityEntryPage key={entry.key} entry={entry} />}
                />
              ))}
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/profile/security" element={<SecurityPage />} />
              <Route path="/profile/devices" element={<DevicesPage />} />
              <Route
                path="/admin"
                element={
                  <RequireAdmin>
                    <AdminManagementPage />
                  </RequireAdmin>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            <ThemeToggleGate />
            <GestureControlGate />
          </>
        </AuthProvider>
      </RuntimeConfigProvider>
    </Router>
  )
}
