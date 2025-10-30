import React, { useState, useEffect } from 'react';

function ManageApiKeys({ provider, theme, onClose }) {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadKeys = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/config/api-keys/${provider}/all`);
      const data = await res.json();
      
      if (res.ok) {
        setKeys(data.keys || []);
      } else {
        setError(data.error || 'Failed to load keys');
      }
    } catch (err) {
      setError('Error connecting to server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, [provider]);

  const handleDelete = async (fullKey) => {
    if (!confirm('Are you sure you want to delete this API key?')) {
      return;
    }

    try {
      const res = await fetch(`/api/config/api-keys/${provider}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: fullKey })
      });

      if (res.ok) {
        setSuccess('API key deleted successfully');
        loadKeys();
        setTimeout(() => setSuccess(''), 3000);
      } else {
        const data = await res.json();
        setError(data.error || 'Failed to delete key');
      }
    } catch (err) {
      setError('Error connecting to server');
    }
  };

  const getCardStyle = () => ({
    padding: 16,
    marginBottom: 16,
    backgroundColor: theme === 'dark' ? '#2d2d2d' : '#f8f9fa',
    borderRadius: 8,
    border: `1px solid ${theme === 'dark' ? '#555' : '#dee2e6'}`
  });

  const getModalStyle = () => ({
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000
  });

  const getModalContentStyle = () => ({
    backgroundColor: theme === 'dark' ? '#1e1e1e' : '#ffffff',
    padding: 32,
    borderRadius: 8,
    maxWidth: 600,
    width: '90%',
    maxHeight: '80vh',
    overflow: 'auto'
  });

  return (
    <div style={getModalStyle()} onClick={onClose}>
      <div style={getModalContentStyle()} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ marginTop: 0 }}>
          Manage API Keys - {provider.charAt(0).toUpperCase() + provider.slice(1)}
        </h2>

        {loading && <p>Loading...</p>}

        {error && (
          <div style={{
            padding: 12,
            marginBottom: 16,
            backgroundColor: theme === 'dark' ? '#4f1d1d' : '#f8d7da',
            color: theme === 'dark' ? '#ff6b6b' : '#721c24',
            borderRadius: 4
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{
            padding: 12,
            marginBottom: 16,
            backgroundColor: theme === 'dark' ? '#0d4f3c' : '#d4edda',
            color: theme === 'dark' ? '#28a745' : '#155724',
            borderRadius: 4
          }}>
            {success}
          </div>
        )}

        {!loading && keys.length === 0 && (
          <p style={{ color: theme === 'dark' ? '#888' : '#666' }}>
            No API keys saved for this provider yet.
          </p>
        )}

        {keys.length > 0 && (
          <div>
            <p style={{ color: theme === 'dark' ? '#888' : '#666', marginBottom: 16 }}>
              Total keys: {keys.length}
            </p>
            {keys.map((keyInfo, index) => (
              <div key={index} style={getCardStyle()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontFamily: 'monospace', fontSize: 14 }}>
                      Key #{index + 1}: {keyInfo.masked}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(keyInfo.full)}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: 4,
                      cursor: 'pointer',
                      marginLeft: 12
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              backgroundColor: theme === 'dark' ? '#2d2d2d' : '#f0f0f0',
              color: theme === 'dark' ? 'white' : 'black',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default ManageApiKeys;
