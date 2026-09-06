import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { TenantProvider } from './contexts/TenantContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Chat from './pages/Chat';
import Projects from './pages/Projects';
import Documents from './pages/Documents';
import Workflows from './pages/Workflows';
import Requirements from './pages/Requirements';
import Risks from './pages/Risks';
import Reports from './pages/Reports';
import Integrations from './pages/Integrations';
import Approvals from './pages/Approvals';
import Admin from './pages/Admin';
import Dashboard from './pages/Dashboard';
import './styles.css';

function App() {
  return (
    <AuthProvider>
      <TenantProvider>
        <Router>
          <Routes>
            {/* Public Auth Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Authenticated Routes wrapped in Layout shell */}
            <Route path="/chat" element={<Layout><Chat /></Layout>} />
            <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
            <Route path="/projects" element={<Layout><Projects /></Layout>} />
            <Route path="/documents" element={<Layout><Documents /></Layout>} />
            <Route path="/workflows" element={<Layout><Workflows /></Layout>} />
            <Route path="/requirements" element={<Layout><Requirements /></Layout>} />
            <Route path="/risks" element={<Layout><Risks /></Layout>} />
            <Route path="/reports" element={<Layout><Reports /></Layout>} />
            <Route path="/integrations" element={<Layout><Integrations /></Layout>} />
            <Route path="/approvals" element={<Layout><Approvals /></Layout>} />
            <Route path="/admin" element={<Layout><Admin /></Layout>} />

            {/* Canonical landing page is /chat */}
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </Router>
      </TenantProvider>
    </AuthProvider>
  );
}

export default App;