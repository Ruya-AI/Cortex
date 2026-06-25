import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { QAExecutionPage } from './pages/QAExecution';
import { ExecutionDetail } from './pages/ExecutionDetail';
import { Reports } from './pages/Reports';
import { RuleReference } from './pages/RuleReference';
import { Admin } from './pages/Admin';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: '\u{1F4CA}' },
  { path: '/qa-execution', label: 'QA Execution', icon: '\u{1F50D}' },
  { path: '/reports', label: 'Reports', icon: '\u{1F4C4}' },
  { path: '/rules', label: 'Rule Reference', icon: '\u{1F4D6}' },
  { path: '/admin', label: 'Admin', icon: '⚙️' },
];

function NavSidebar() {
  const location = useLocation();
  return (
    <nav style={{
      width: '220px',
      background: '#1a1a2e',
      color: '#fff',
      padding: '20px 0',
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100vh',
    }}>
      <div style={{ padding: '0 20px 24px', borderBottom: '1px solid #333' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0 }}>Cortex</h1>
        <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>QA Platform</div>
      </div>
      <div style={{ marginTop: '16px' }}>
        {NAV_ITEMS.map(item => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 20px',
                color: isActive ? '#fff' : '#aaa',
                textDecoration: 'none',
                background: isActive ? '#0f3460' : 'transparent',
                fontSize: '14px',
                fontWeight: isActive ? 600 : 400,
                borderLeft: isActive ? '3px solid #4da6ff' : '3px solid transparent',
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
      <div style={{ marginTop: 'auto', padding: '16px 20px', fontSize: '11px', color: '#555' }}>
        Cortex QA Platform<br />
        Audit-only — does not modify code.
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex' }}>
        <NavSidebar />
        <main style={{ flex: 1, padding: '24px 32px', maxWidth: 'calc(100vw - 220px)', overflow: 'auto' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/qa-execution" element={<QAExecutionPage />} />
            <Route path="/qa-execution/:id" element={<ExecutionDetail />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/rules" element={<RuleReference />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
