import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AuthProvider } from "./auth/AuthProvider";
import { RequireAuth, RequireAnon } from "./auth/guards";
import { LandingPage } from "./pages/LandingPage";
import { ScannerPage } from "./pages/ScannerPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HowItWorksPage } from "./pages/HowItWorksPage";
import { ModelPerformancePage } from "./pages/ModelPerformancePage";
import { SecurityPrivacyPage } from "./pages/SecurityPrivacyPage";
import { AboutPage } from "./pages/AboutPage";
import { SettingsPage } from "./pages/SettingsPage";
import { LoginPage } from "./pages/auth/LoginPage";
import { SignupPage } from "./pages/auth/SignupPage";
import { ForgotPasswordPage } from "./pages/auth/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/auth/ResetPasswordPage";
import { AuthCallbackPage } from "./pages/auth/AuthCallbackPage";
import { NotFoundPage } from "./pages/NotFoundPage";

/* Route map:
   Public      /, /how-it-works, /model-performance, /security-privacy, /about
   Auth        /login, /signup, /forgot-password, /auth/callback, /auth/reset-password
   Private     /app, /app/scanner, /app/history, /app/history/:scanId,
               /app/model-performance, /app/how-it-works, /app/settings
   Legacy      /scanner, /dashboard, /history -> /app equivalents              */
export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <HashRouter>
          <Routes>
            {/* Public marketing / information pages */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/how-it-works" element={<HowItWorksPage />} />
            <Route path="/model-performance" element={<ModelPerformancePage />} />
            <Route path="/security-privacy" element={<SecurityPrivacyPage />} />
            <Route path="/about" element={<AboutPage />} />

            {/* Authentication pages (signed-in users are sent to /app) */}
            <Route
              path="/login"
              element={
                <RequireAnon>
                  <LoginPage />
                </RequireAnon>
              }
            />
            <Route
              path="/signup"
              element={
                <RequireAnon>
                  <SignupPage />
                </RequireAnon>
              }
            />
            <Route
              path="/forgot-password"
              element={
                <RequireAnon>
                  <ForgotPasswordPage />
                </RequireAnon>
              }
            />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="/auth/reset-password" element={<ResetPasswordPage />} />

            {/* Private workspace - backend enforces authorization too */}
            <Route
              path="/app"
              element={
                <RequireAuth>
                  <DashboardPage />
                </RequireAuth>
              }
            />
            <Route
              path="/app/scanner"
              element={
                <RequireAuth>
                  <ScannerPage />
                </RequireAuth>
              }
            />
            <Route
              path="/app/history"
              element={
                <RequireAuth>
                  <HistoryPage />
                </RequireAuth>
              }
            />
            <Route
              path="/app/history/:scanId"
              element={
                <RequireAuth>
                  <HistoryPage />
                </RequireAuth>
              }
            />
            <Route
              path="/app/model-performance"
              element={
                <RequireAuth>
                  <ModelPerformancePage />
                </RequireAuth>
              }
            />
            <Route
              path="/app/how-it-works"
              element={
                <RequireAuth>
                  <HowItWorksPage />
                </RequireAuth>
              }
            />
            <Route
              path="/app/settings"
              element={
                <RequireAuth>
                  <SettingsPage />
                </RequireAuth>
              }
            />

            {/* Legacy single-user routes -> private workspace equivalents */}
            <Route path="/scanner" element={<Navigate to="/app/scanner" replace />} />
            <Route path="/dashboard" element={<Navigate to="/app" replace />} />
            <Route path="/history" element={<Navigate to="/app/history" replace />} />

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </HashRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
