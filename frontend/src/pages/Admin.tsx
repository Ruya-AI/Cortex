import { useEffect, useState } from 'react';
import { fetchApi } from '../hooks/useApi';
import { AppSettings } from '../types';

interface AutomationRule {
  id: string;
  name: string;
  trigger: string;
  active: boolean;
}

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: '8px',
  border: '1px solid #dee2e6',
  padding: '20px',
};

const headingStyle: React.CSSProperties = {
  marginBottom: '16px',
  color: '#0f3460',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '13px',
  fontWeight: 500,
  marginBottom: '4px',
  color: '#333',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  border: '1px solid #dee2e6',
  borderRadius: '4px',
  fontSize: '14px',
  boxSizing: 'border-box',
};

const buttonStyle: React.CSSProperties = {
  padding: '8px 20px',
  background: '#0f3460',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: '13px',
};

const fieldGroupStyle: React.CSSProperties = {
  marginBottom: '12px',
};

export function Admin() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [rules, setRules] = useState<AutomationRule[]>([]);

  // GitHub credential form
  const [ghName, setGhName] = useState('');
  const [ghToken, setGhToken] = useState('');
  const [ghMsg, setGhMsg] = useState('');

  // Linear credential form
  const [linearName, setLinearName] = useState('');
  const [linearApiKey, setLinearApiKey] = useState('');
  const [linearTeamId, setLinearTeamId] = useState('');
  const [linearMsg, setLinearMsg] = useState('');

  // Repository form
  const [repoOwner, setRepoOwner] = useState('');
  const [repoName, setRepoName] = useState('');
  const [repoBranch, setRepoBranch] = useState('main');
  const [repoAutoFetch, setRepoAutoFetch] = useState(true);
  const [repoMsg, setRepoMsg] = useState('');

  // Notification settings
  const [slackWebhook, setSlackWebhook] = useState('');
  const [notifEmail, setNotifEmail] = useState('');
  const [notifMsg, setNotifMsg] = useState('');

  useEffect(() => {
    fetchApi<AppSettings>('/api/admin/settings')
      .then(data => setSettings(data))
      .catch(() => {})
      .finally(() => setLoading(false));

    fetchApi<{ items: AutomationRule[] }>('/api/automation/rules')
      .then(data => setRules(data.items || []))
      .catch(() => {});
  }, []);

  const submitGithub = () => {
    if (!ghName || !ghToken) return;
    fetchApi('/api/github/configs', {
      method: 'POST',
      body: JSON.stringify({ name: ghName, token: ghToken }),
    })
      .then(() => { setGhMsg('GitHub credential saved.'); setGhName(''); setGhToken(''); })
      .catch(() => setGhMsg('Failed to save GitHub credential.'));
  };

  const submitLinear = () => {
    if (!linearName || !linearApiKey) return;
    fetchApi('/api/linear/configs', {
      method: 'POST',
      body: JSON.stringify({ name: linearName, api_key: linearApiKey, team_id: linearTeamId }),
    })
      .then(() => { setLinearMsg('Linear credential saved.'); setLinearName(''); setLinearApiKey(''); setLinearTeamId(''); })
      .catch(() => setLinearMsg('Failed to save Linear credential.'));
  };

  const submitRepo = () => {
    if (!repoOwner || !repoName) return;
    fetchApi('/api/github/repos', {
      method: 'POST',
      body: JSON.stringify({ owner: repoOwner, repo: repoName, default_branch: repoBranch, auto_fetch: repoAutoFetch }),
    })
      .then(() => { setRepoMsg('Repository saved.'); setRepoOwner(''); setRepoName(''); setRepoBranch('main'); })
      .catch(() => setRepoMsg('Failed to save repository.'));
  };

  const submitNotifications = () => {
    fetchApi('/api/admin/settings', {
      method: 'PUT',
      body: JSON.stringify({ slack_webhook_url: slackWebhook, notification_email: notifEmail }),
    })
      .then(() => setNotifMsg('Notification settings saved.'))
      .catch(() => setNotifMsg('Failed to save notification settings.'));
  };

  const toggleRule = (rule: AutomationRule) => {
    fetchApi(`/api/automation/rules`, {
      method: 'PUT',
      body: JSON.stringify({ id: rule.id, active: !rule.active }),
    })
      .then(() => {
        setRules(prev => prev.map(r => r.id === rule.id ? { ...r, active: !r.active } : r));
      })
      .catch(() => {});
  };

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>Administration</h2>

      {loading ? <p style={{ color: '#999' }}>Loading settings...</p> : (
        <div style={{ display: 'grid', gap: '20px', gridTemplateColumns: '1fr 1fr' }}>
          {/* Feature Toggles */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>Feature Toggles</h3>
            {settings?.features && Object.entries(settings.features).map(([key, enabled]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{key}</span>
                <span style={{ color: enabled ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px' }}>
                  {enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
            ))}
          </div>

          {/* GitHub Credentials */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>GitHub Credentials</h3>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Name</label>
              <input style={inputStyle} value={ghName} onChange={e => setGhName(e.target.value)} placeholder="e.g. production" />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Token</label>
              <input style={inputStyle} type="password" value={ghToken} onChange={e => setGhToken(e.target.value)} placeholder="ghp_..." />
            </div>
            <button style={buttonStyle} onClick={submitGithub}>Save GitHub Credential</button>
            {ghMsg && <p style={{ fontSize: '13px', color: ghMsg.includes('Failed') ? '#dc3545' : '#28a745', marginTop: '8px' }}>{ghMsg}</p>}
          </div>

          {/* Linear Credentials */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>Linear Credentials</h3>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Name</label>
              <input style={inputStyle} value={linearName} onChange={e => setLinearName(e.target.value)} placeholder="e.g. engineering" />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>API Key</label>
              <input style={inputStyle} type="password" value={linearApiKey} onChange={e => setLinearApiKey(e.target.value)} placeholder="lin_api_..." />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Team ID</label>
              <input style={inputStyle} value={linearTeamId} onChange={e => setLinearTeamId(e.target.value)} placeholder="Team identifier" />
            </div>
            <button style={buttonStyle} onClick={submitLinear}>Save Linear Credential</button>
            {linearMsg && <p style={{ fontSize: '13px', color: linearMsg.includes('Failed') ? '#dc3545' : '#28a745', marginTop: '8px' }}>{linearMsg}</p>}
          </div>

          {/* Repository Configuration */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>Repository Configuration</h3>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Owner</label>
              <input style={inputStyle} value={repoOwner} onChange={e => setRepoOwner(e.target.value)} placeholder="e.g. Ruya-AI" />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Repository</label>
              <input style={inputStyle} value={repoName} onChange={e => setRepoName(e.target.value)} placeholder="e.g. Cortex" />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Branch</label>
              <input style={inputStyle} value={repoBranch} onChange={e => setRepoBranch(e.target.value)} placeholder="main" />
            </div>
            <div style={{ ...fieldGroupStyle, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input type="checkbox" checked={repoAutoFetch} onChange={e => setRepoAutoFetch(e.target.checked)} />
              <label style={{ fontSize: '13px', fontWeight: 500, color: '#333' }}>Auto-fetch PRs</label>
            </div>
            <button style={buttonStyle} onClick={submitRepo}>Save Repository</button>
            {repoMsg && <p style={{ fontSize: '13px', color: repoMsg.includes('Failed') ? '#dc3545' : '#28a745', marginTop: '8px' }}>{repoMsg}</p>}
          </div>

          {/* Automation Rules */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>Automation Rules</h3>
            {rules.length > 0 ? (
              rules.map(rule => (
                <div key={rule.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '14px' }}>{rule.name}</div>
                    <div style={{ fontSize: '12px', color: '#666' }}>{rule.trigger}</div>
                  </div>
                  <button
                    onClick={() => toggleRule(rule)}
                    style={{
                      padding: '4px 12px',
                      border: '1px solid',
                      borderColor: rule.active ? '#28a745' : '#dc3545',
                      borderRadius: '4px',
                      background: 'transparent',
                      color: rule.active ? '#28a745' : '#dc3545',
                      fontWeight: 600,
                      fontSize: '11px',
                      cursor: 'pointer',
                    }}
                  >
                    {rule.active ? 'ACTIVE' : 'INACTIVE'}
                  </button>
                </div>
              ))
            ) : (
              <p style={{ color: '#999', fontSize: '14px' }}>No automation rules configured.</p>
            )}
          </div>

          {/* Notification Settings */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>Notification Settings</h3>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Slack Webhook URL</label>
              <input style={inputStyle} value={slackWebhook} onChange={e => setSlackWebhook(e.target.value)} placeholder="https://hooks.slack.com/services/..." />
            </div>
            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Notification Email</label>
              <input style={inputStyle} type="email" value={notifEmail} onChange={e => setNotifEmail(e.target.value)} placeholder="alerts@example.com" />
            </div>
            <button style={buttonStyle} onClick={submitNotifications}>Save Notifications</button>
            {notifMsg && <p style={{ fontSize: '13px', color: notifMsg.includes('Failed') ? '#dc3545' : '#28a745', marginTop: '8px' }}>{notifMsg}</p>}
          </div>

          {/* Configuration Items */}
          <div style={cardStyle}>
            <h3 style={headingStyle}>Configuration</h3>
            {settings?.items && settings.items.length > 0 ? (
              settings.items.map(item => (
                <div key={item.key} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ fontWeight: 500, fontSize: '13px' }}>{item.key}</div>
                  <div style={{ fontSize: '12px', color: '#666' }}>{item.description || item.value || '(not set)'}</div>
                </div>
              ))
            ) : (
              <p style={{ color: '#999', fontSize: '14px' }}>No configuration items. Settings will appear here once configured.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
