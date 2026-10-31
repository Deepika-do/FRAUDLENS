
import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Upload,
  AlertTriangle,
  Shield,
  LogOut,
} from 'lucide-react';

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    try {
      setLoggingOut(true);

      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Logout failed');
      }

      navigate('/login', { replace: true });
    } catch {
      alert('Unable to log out. Please try again.');
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <Shield size={18} color="white" strokeWidth={2.5} />
          </div>
          <div>
            <div className="sidebar-logo-text">FraudLens</div>
            <div className="sidebar-logo-sub">GST Fraud Detection</div>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Navigation</div>

        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `sidebar-nav-item${isActive ? ' active' : ''}`
          }
        >
          <LayoutDashboard size={16} className="nav-icon" />
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/upload"
          className={({ isActive }) =>
            `sidebar-nav-item${isActive ? ' active' : ''}`
          }
        >
          <Upload size={16} className="nav-icon" />
          <span>Upload Invoices</span>
        </NavLink>

        <NavLink
          to="/results"
          className={({ isActive }) =>
            `sidebar-nav-item${isActive ? ' active' : ''}`
          }
        >
          <AlertTriangle size={16} className="nav-icon" />
          <span>Fraud Results</span>
        </NavLink>
      </nav>

      <div style={{ marginTop: 'auto' }}>
        <button
          type="button"
          className="sidebar-nav-item"
          onClick={handleLogout}
          disabled={loggingOut}
          style={{
            width: '100%',
            border: 'none',
            background: 'transparent',
            cursor: loggingOut ? 'wait' : 'pointer',
            textAlign: 'left',
            color: '#fca5a5',
          }}
        >
          <LogOut size={16} className="nav-icon" />
          <span>{loggingOut ? 'Logging out...' : 'Logout'}</span>
        </button>

        <div
          style={{
            padding: '12px 16px',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            fontSize: '11px',
            color: 'rgba(255,255,255,0.25)',
            lineHeight: 1.4,
          }}
        >
          v1.0 · Local build
          <br />
          For review purposes only
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
