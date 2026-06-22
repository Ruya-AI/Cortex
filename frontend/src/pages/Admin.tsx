import { useEffect, useState } from 'react';
import { fetchApi } from '../hooks/useApi';
import { AppSettings } from '../types';

export function Admin() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<AppSettings>('/api/admin/settings')
      .then(data => setSettings(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>Administration</h2>

      {loading ? <p style={{ color: '#999' }}>Loading settings...</p> : (
        <div style={{ display: 'grid', gap: '20px', gridTemplateColumns: '1fr 1fr' }}>
          {/* Feature Toggles */}
          <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '20px' }}>
            <h3 style={{ marginBottom: '16px', color: '#0f3460' }}>Feature Toggles</h3>
            {settings?.features && Object.entries(settings.features).map(([key, enabled]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>{key}</span>
                <span style={{ color: enabled ? '#28a745' : '#dc3545', fontWeight: 600, fontSize: '12px' }}>
                  {enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
            ))}
          </div>

          {/* Configuration Items */}
          <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid #dee2e6', padding: '20px' }}>
            <h3 style={{ marginBottom: '16px', color: '#0f3460' }}>Configuration</h3>
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
