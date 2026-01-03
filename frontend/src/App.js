import React from "react";
import "./App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Pages
import SignIn from "./pages/SignIn";
import SuperAdminDashboard from "./pages/SuperAdminDashboard";
import Inbox from "./pages/Inbox";
import Connections from "./pages/Connections";
import Settings from "./pages/Settings";

// Layout
import MainLayout from "./components/Layout/MainLayout";

// Store
import { useAuthStore } from "./store/authStore";

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
    <div className="App">
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
            <Route index element={<Navigate to="/app/inbox" replace />} />
            <Route path="inbox" element={<Inbox />} />
            <Route path="settings/connections" element={<Connections />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/sign-in" replace />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
