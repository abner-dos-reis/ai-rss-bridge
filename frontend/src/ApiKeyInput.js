import React, { useState } from 'react';

function ApiKeyInput({ provider, savedProviders, saveApiKey, deleteApiKey, theme, getInputStyle, getButtonStyle, configError, configSuccess, setConfigError, setConfigSuccess, onManage, keyCounts }) {
  const [inputValue, setInputValue] = useState('');

  const handleSave = async () => {
    if (inputValue.trim()) {
      await saveApiKey(provider.value, inputValue.trim());
      setInputValue('');
    }
  };

  const keyCount = keyCounts?.[provider.value] || 0;

  return (
    <div style={{ 
      marginBottom: 16, 
      padding: 12, 
      backgroundColor: theme === 'dark' ? '#1e1e1e' : '#ffffff', 
      borderRadius: 8, 
      border: `1px solid ${theme === 'dark' ? '#555' : '#ddd'}` 
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <strong>{provider.label}</strong>
        {savedProviders.includes(provider.value) && (
          <span style={{ color: '#28a745', fontSize: 12 }}>
            ✅ {keyCount} key{keyCount !== 1 ? 's' : ''} saved
          </span>
        )}
      </div>
      
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="password"
          placeholder={`Enter ${provider.label} API key`}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          style={{ ...getInputStyle(), flex: 1 }}
        />
        <button
          onClick={handleSave}
          style={{
            ...getButtonStyle(),
            backgroundColor: '#28a745',
            color: 'white'
          }}
        >
          Save
        </button>
        {savedProviders.includes(provider.value) && (
          <>
            <button
              onClick={() => onManage(provider.value)}
              style={{
                ...getButtonStyle(),
                backgroundColor: '#007cba',
                color: 'white'
              }}
            >
              Manage
            </button>
            <button
              onClick={() => deleteApiKey(provider.value)}
              style={{
                ...getButtonStyle(),
                backgroundColor: '#dc3545',
                color: 'white'
              }}
            >
              Delete All
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default ApiKeyInput;