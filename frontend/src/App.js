import React, { Suspense, lazy } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Loading Component
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-900">
    <div className="flex flex-col items-center gap-4">
      <div className="w-12 h-12 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin" />
      <p className="text-white/60">Carregando...</p>
    </div>
  </div>
);

// Lazy loaded Pages
const SignIn = lazy(() => import("./pages/SignIn"));
const SuperAdminDashboard = lazy(() => import("./pages/SuperAdminDashboard"));
const TenantsPage = lazy(() => import("./pages/TenantsPage"));
const PlansPage = lazy(() => import("./pages/PlansPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const MaintenancePage = lazy(() => import("./pages/MaintenancePage"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Inbox = lazy(() => import("./pages/Inbox"));
const Automations = lazy(() => import("./pages/Automations"));
const Templates = lazy(() => import("./pages/Templates"));
const KnowledgeBase = lazy(() => import("./pages/KnowledgeBase"));
const Connections = lazy(() => import("./pages/Connections"));
const Settings = lazy(() => import("./pages/Settings"));
const Profile = lazy(() => import("./pages/Profile"));
const Contacts = lazy(() => import("./pages/Contacts"));
const FlowBuilder = lazy(() => import("./pages/FlowBuilder"));

// Layout
import MainLayout from "./components/Layout/MainLayout";

// Store
import { useAuthStore } from "./store/authStore";

// Context
import { ThemeProvider } from "./context/ThemeContext";
import { RealtimeProvider } from "./context/RealtimeContext";

// Toast
import { GlassToaster } from "./components/ui/glass-toaster";

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    return <Navigate to={user?.role === 'superadmin' ? '/superadmin' : '/app/inbox'} replace />;
  }

  return children;
};

const PublicRoute = ({ children }) => {
  const { isAuthenticated, user } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to={user?.role === 'superadmin' ? '/superadmin' : '/app/inbox'} replace />;
  }

  return children;
};

function App() {
  return (
    <ThemeProvider>
      <RealtimeProvider>
        <div className="App">
          <GlassToaster />
          <BrowserRouter>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                {/* Public Routes */}
                <Route
                  path="/sign-in"
                  element={
                    <PublicRoute>
                      <SignIn />
                    </PublicRoute>
                  }
                />

                {/* SuperAdmin Routes */}
                <Route
                  path="/superadmin"
                  element={
                    <ProtectedRoute allowedRoles={['superadmin']}>
                      <MainLayout />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<SuperAdminDashboard />} />
                  <Route path="tenants" element={<TenantsPage />} />
                  <Route path="plans" element={<PlansPage />} />
                  <Route path="users" element={<UsersPage />} />
                  <Route path="maintenance" element={<MaintenancePage />} />
                  <Route path="*" element={<Navigate to="/superadmin" replace />} />
                </Route>

                {/* App Routes (Admin/Agent) */}
                <Route
                  path="/app"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'agent']}>
                      <MainLayout />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<Navigate to="/app/dashboard" replace />} />
                  <Route path="dashboard" element={<Dashboard />} />
                  <Route path="inbox" element={<Inbox />} />
                  <Route path="contacts" element={<Contacts />} />
                  <Route path="automations" element={<Automations />} />
                  <Route path="flows" element={<FlowBuilder />} />
                  <Route path="templates" element={<Templates />} />
                  <Route path="kb" element={<KnowledgeBase />} />
                  <Route
                    path="settings/connections"
                    element={
                      <ProtectedRoute allowedRoles={['admin']}>
                        <Connections />
                      </ProtectedRoute>
                    }
                  />
                  <Route path="settings/profile" element={<Profile />} />
                  <Route path="settings" element={<Settings />} />
                  <Route path="profile" element={<Profile />} />
                  <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
                </Route>

                {/* Default redirect */}
                <Route path="*" element={<Navigate to="/sign-in" replace />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </div>
      </RealtimeProvider>
    </ThemeProvider>
  );
}

export default App;
