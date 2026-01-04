import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Pages
import SignIn from "./pages/SignIn";
import SuperAdminDashboard from "./pages/SuperAdminDashboard";
import Dashboard from "./pages/Dashboard";
import Inbox from "./pages/Inbox";
import Automations from "./pages/Automations";
import Chatbot from "./pages/Chatbot";
import Templates from "./pages/Templates";
import KnowledgeBase from "./pages/KnowledgeBase";
import Connections from "./pages/Connections";
import Settings from "./pages/Settings";
import Profile from "./pages/Profile";

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
                <Route path="tenants" element={<SuperAdminDashboard />} />
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
                <Route path="automations" element={<Automations />} />
                <Route path="chatbot" element={<Chatbot />} />
                <Route path="templates" element={<Templates />} />
                <Route path="kb" element={<KnowledgeBase />} />
                <Route path="settings/connections" element={<Connections />} />
                <Route path="settings/profile" element={<Profile />} />
                <Route path="settings" element={<Settings />} />
                <Route path="profile" element={<Profile />} />
              </Route>

              {/* Default redirect */}
              <Route path="*" element={<Navigate to="/sign-in" replace />} />
            </Routes>
          </BrowserRouter>
        </div>
      </RealtimeProvider>
    </ThemeProvider>
  );
}

export default App;
