import { BrowserRouter as Router, Navigate, Route, Routes, useParams } from 'react-router-dom'
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
import PersonalAiwikiPage from './pages/personalAiwiki'
import InteractiveMoviePage from './pages/interactiveMovie'
import PublicInteractiveMoviePlayer from './pages/interactiveMovie/PublicInteractiveMoviePlayer'
import CapabilityEntryPage from './pages/capabilities/CapabilityEntryPage'
import GestureControlPage from './pages/gestureControl'
import { AuthProvider, RequireAdmin, RequireAuth } from './providers/AuthProvider'
import { RuntimeConfigProvider } from './providers/RuntimeConfigProvider'
import { GestureControlProvider } from './components/gesture/GestureControlProvider'
import { GESTURE_CONTROL_TOOL, PERSONAL_AIWIKI_TOOL, VISIBLE_CAPABILITY_ENTRIES } from './lib/workflowModes'

function LegacyChatSessionRedirect() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  return <Navigate to={sessionId ? `/agents/chat/${encodeURIComponent(sessionId)}` : '/agents'} replace />
}

export default function App() {
  return (
    <Router>
      <RuntimeConfigProvider>
        <AuthProvider>
          <GestureControlProvider>
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
                  path="/content-growth"
                  element={
                    <RequireAuth>
                      <AiwikiPage key="content-growth" mode="full" />
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
                <Route path="/interactive-movie/play/:projectId" element={<PublicInteractiveMoviePlayer />} />
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
                  <Route path={PERSONAL_AIWIKI_TOOL.path} element={<PersonalAiwikiPage />} />
                  <Route path={GESTURE_CONTROL_TOOL.path} element={<GestureControlPage />} />
                  <Route path="/seed-matrices" element={<Navigate to="/content-growth?stage=strategy&strategyMode=standard" replace />} />
                  <Route path="/seed-matrices/standard" element={<Navigate to="/content-growth?stage=strategy&strategyMode=standard" replace />} />
                  <Route path="/seed-matrices/batch" element={<Navigate to="/content-growth?stage=strategy&strategyMode=batch" replace />} />
                  <Route path="/seed-matrices/high-frequency" element={<Navigate to="/content-growth?stage=strategy&strategyMode=high-frequency" replace />} />
                  <Route path="/seed-matrices/hook-driven" element={<Navigate to="/content-growth?stage=strategy&strategyMode=hook-driven" replace />} />
                  <Route path="/daily-writer" element={<Navigate to="/content-growth?stage=production&writerMode=single" replace />} />
                  <Route path="/daily-writer/single" element={<Navigate to="/content-growth?stage=production&writerMode=single" replace />} />
                  <Route path="/daily-writer/batch" element={<Navigate to="/content-growth?stage=production&writerMode=batch" replace />} />
                  <Route path="/daily-writer/five-pack" element={<Navigate to="/content-growth?stage=production&writerMode=five-pack" replace />} />
                  <Route path="/social-cards" element={<Navigate to="/content-growth?stage=social" replace />} />
                  <Route path="/social-card-videos" element={<Navigate to="/content-growth?stage=video" replace />} />
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
            </>
          </GestureControlProvider>
        </AuthProvider>
      </RuntimeConfigProvider>
    </Router>
  )
}
