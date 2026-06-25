export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div style={{
      background: '#fff3f3', border: '1px solid #f5c2c7', borderLeft: '4px solid #dc3545',
      borderRadius: '8px', padding: '14px 20px', marginBottom: '20px',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    }}>
      <div>
        <div style={{ fontWeight: 600, color: '#dc3545', fontSize: '14px', marginBottom: '2px' }}>Error</div>
        <div style={{ fontSize: '13px', color: '#842029' }}>{message}</div>
      </div>
      {onRetry && (
        <button onClick={onRetry} style={{
          padding: '6px 16px', background: '#dc3545', color: '#fff', border: 'none',
          borderRadius: '4px', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
        }}>Retry</button>
      )}
    </div>
  );
}
