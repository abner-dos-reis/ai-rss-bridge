import React, { useState, useEffect } from 'react';
import ApiKeyInput from './ApiKeyInput';
import ManageApiKeys from './ManageApiKeys';

function App() {
  const [url, setUrl] = useState('');
  const [aiProvider, setAiProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [configError, setConfigError] = useState('');
  const [configSuccess, setConfigSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [feeds, setFeeds] = useState([]);
  const [activeTab, setActiveTab] = useState('generate');
  const [schedulerStatus, setSchedulerStatus] = useState({ running: false, api_keys_configured: [] });
  const [expandedFeeds, setExpandedFeeds] = useState({});
  const [autoUpdateKeys, setAutoUpdateKeys] = useState({
    openai: '',
    gemini: '',
    claude: '',
    perplexity: ''
  });
  const [theme, setTheme] = useState('light');
  const [savedProviders, setSavedProviders] = useState([]);
  const [keyCounts, setKeyCounts] = useState({});
  const [manageProvider, setManageProvider] = useState(null);
  
  // Login session states
  const [sessions, setSessions] = useState([]);
  const [loginSiteUrl, setLoginSiteUrl] = useState('');
  const [loginSiteName, setLoginSiteName] = useState('');
  const [loginCookies, setLoginCookies] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [loginSuccess, setLoginSuccess] = useState('');
  const [showManualCookies, setShowManualCookies] = useState(false);

  // Helper function para fazer fetch com tratamento de erros adequado
  const safeFetch = async (url, options = {}) => {
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type');
    
    // Se não for JSON, retornar erro
    if (!contentType || !contentType.includes('application/json')) {
      const textResponse = await response.text();
      console.error('Non-JSON response from', url, ':', textResponse.substring(0, 200));
      throw new Error(`Server returned ${response.status}: Expected JSON but got ${contentType || 'unknown type'}`);
    }
    
    return response.json();
  };

  const providers = [
    { value: 'openai', label: 'OpenAI (GPT)' },
    { value: 'gemini', label: 'Google Gemini' },
    { value: 'claude', label: 'Anthropic Claude' },
    { value: 'perplexity', label: 'Perplexity AI' }
  ];

  const loadFeeds = async () => {
    try {
      const res = await fetch('/api/feeds');
      const data = await res.json();
      const feedsWithItems = await Promise.all(
        (data.feeds || []).map(async (feed) => {
          try {
            const itemsRes = await fetch(`/api/feeds/${feed.id}/items`);
            if (itemsRes.ok) {
              const itemsData = await itemsRes.json();
              return { ...feed, items: itemsData.items || [] };
            }
          } catch (err) {
            console.error(`Error loading items for feed ${feed.id}:`, err);
          }
          return { ...feed, items: [] };
        })
      );
      setFeeds(feedsWithItems);
    } catch (err) {
      console.error('Error loading feeds:', err);
    }
  };

  const loadSchedulerStatus = async () => {
    try {
      const res = await fetch('/api/scheduler/status');
      const data = await res.json();
      setSchedulerStatus(data);
    } catch (err) {
      console.error('Error loading scheduler status:', err);
    }
  };

  const loadTheme = async () => {
    try {
      // Primeiro tenta carregar do localStorage
      const localTheme = localStorage.getItem('ai-rss-theme');
      if (localTheme) {
        setTheme(localTheme);
      }
      
      // Depois tenta carregar do backend
      const res = await fetch('/api/config/theme');
      const data = await res.json();
      if (data.theme && data.theme !== localTheme) {
        setTheme(data.theme);
        localStorage.setItem('ai-rss-theme', data.theme);
      }
    } catch (err) {
      console.error('Error loading theme:', err);
      // Se falhar, usa o localStorage ou padrão
      const localTheme = localStorage.getItem('ai-rss-theme') || 'light';
      setTheme(localTheme);
    }
  };

  const loadSavedProviders = async () => {
    console.log("Loading saved providers...");
    try {
      const res = await fetch('/api/config/api-keys');
      const data = await res.json();
      console.log("Saved providers response:", data);
      setSavedProviders(data.saved_providers || []);
      setKeyCounts(data.providers_info || {});
    } catch (err) {
      console.error('Error loading saved providers:', err);
      setSavedProviders([]);
      setKeyCounts({});
    }
  };
  
  const loadSessions = async () => {
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('Error loading sessions:', err);
      setSessions([]);
    }
  };

  const loadLastAiProvider = async () => {
    console.log("Loading last AI provider...");
    try {
      const res = await fetch('/api/config/last-ai-provider');
      const data = await res.json();
      console.log("Last AI provider response:", data);
      if (data.provider) {
        setAiProvider(data.provider);
      }
    } catch (err) {
      console.error('Error loading last AI provider:', err);
    }
  };

  const saveLastAiProvider = async (provider) => {
    console.log("Saving last AI provider:", provider);
    try {
      await fetch('/api/config/last-ai-provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider })
      });
      console.log("Last AI provider saved successfully");
    } catch (err) {
      console.error('Error saving last AI provider:', err);
    }
  };

  useEffect(() => {
    loadFeeds();
    loadSchedulerStatus();
    loadTheme();
    loadSavedProviders();
    loadLastAiProvider();
    loadSessions();
  }, []);

  useEffect(() => {
    // Apply theme to document body
    if (theme === 'dark') {
      document.body.style.backgroundColor = '#1e1e1e';
      document.body.style.color = '#ffffff';
    } else {
      document.body.style.backgroundColor = '#ffffff';
      document.body.style.color = '#000000';
    }
  }, [theme]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);
    setLoading(true);

    // Verificar se tem API key salva antes de tentar
    if (!savedProviders.includes(aiProvider)) {
      setError(`No API key saved for ${aiProvider}. Please save it in Config tab first.`);
      setLoading(false);
      return;
    }

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, ai_provider: aiProvider })
      });
      
      // Verificar se a resposta é JSON antes de parsear
      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const textResponse = await res.text();
        console.error('Non-JSON response:', textResponse.substring(0, 200));
        setError(`Server error: Expected JSON response but got ${contentType}. Check backend logs.`);
        setLoading(false);
        return;
      }
      
      const data = await res.json();
      
      if (res.status !== 200) {
        setError(data.error || 'Unknown error');
      } else {
        setResult(data);
        loadFeeds(); // Refresh feeds list
      }
    } catch (err) {
      console.error('API Error:', err);
      setError(`Error connecting to API: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const updateFeed = async (feedId) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/update/${feedId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      
      const data = await res.json();
      
      if (res.status === 200) {
        alert('Feed updated successfully!');
        loadFeeds();
      } else {
        setError(data.error || 'Update failed');
      }
    } catch (err) {
      setError('Error updating feed');
    } finally {
      setLoading(false);
    }
  };

  const reanalyzeFeed = async (feedId) => {
    if (!confirm('Re-analyze this feed with AI? This will update extraction patterns and may consume API tokens.')) {
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`/api/reanalyze/${feedId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      
      const data = await res.json();
      
      if (res.status === 200) {
        alert(`Feed re-analyzed successfully! Method: ${data.method}. Updated ${data.items_count} items.`);
        loadFeeds();
      } else {
        setError(data.error || 'Re-analysis failed');
      }
    } catch (err) {
      setError('Error re-analyzing feed');
    } finally {
      setLoading(false);
    }
  };

  const startScheduler = async () => {
    if (!savedProviders.includes(aiProvider)) {
      setError(`API key for ${aiProvider} not configured. Please save it in Config tab first.`);
      return;
    }

    setLoading(true);
    try {
      // Use all saved API keys for scheduler
      const api_keys = {};
      savedProviders.forEach(provider => {
        // The scheduler will use the saved keys from the backend
        api_keys[provider] = true; // Just indicate it's available
      });

      const res = await fetch('/api/scheduler/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_keys })
      });
      
      const data = await res.json();
      
      if (res.status === 200) {
        alert('Automatic updates started!');
        loadSchedulerStatus();
      } else {
        setError(data.error || 'Failed to start scheduler');
      }
    } catch (err) {
      setError('Error starting scheduler');
    } finally {
      setLoading(false);
    }
  };

  const stopScheduler = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/scheduler/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await res.json();
      
      if (res.status === 200) {
        alert('Automatic updates stopped!');
        loadSchedulerStatus();
      } else {
        setError(data.error || 'Failed to stop scheduler');
      }
    } catch (err) {
      setError('Error stopping scheduler');
    } finally {
      setLoading(false);
    }
  };

  const saveApiKey = async (provider, key) => {
    console.log(`Saving API key for ${provider}...`);
    setConfigError('');
    setConfigSuccess('');
    
    try {
      const res = await fetch('/api/config/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: key })
      });
      
      const data = await res.json();
      console.log("Save API key response:", res.status, data);
      
      if (res.status === 200) {
        setConfigSuccess(`✅ API key saved for ${provider}!`);
        loadSavedProviders();
      } else {
        setConfigError(data.error || 'Failed to save API key');
      }
    } catch (err) {
      console.error('Error saving API key:', err);
      setConfigError('Error connecting to server');
    }
  };

  const deleteApiKey = async (provider) => {
    if (!confirm(`Are you sure you want to delete ALL API keys for ${provider}?`)) {
      return;
    }
    
    setConfigError('');
    setConfigSuccess('');
    
    try {
      const res = await fetch(`/api/config/api-keys/${provider}`, {
        method: 'DELETE'
      });
      
      if (res.status === 200) {
        setConfigSuccess(`🗑️ All API keys deleted for ${provider}!`);
        loadSavedProviders();
      } else {
        const data = await res.json();
        setConfigError(data.error || 'Failed to delete API key');
      }
    } catch (err) {
      setConfigError('Error connecting to server');
    }
  };
  
  const handleManageKeys = (provider) => {
    setManageProvider(provider);
  };
  
  const closeManage = () => {
    setManageProvider(null);
    loadSavedProviders(); // Reload to update counts
  };

  const toggleTheme = async () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme); // Muda imediatamente na interface
    localStorage.setItem('ai-rss-theme', newTheme); // Salva no localStorage
    
    try {
      await fetch('/api/config/theme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme: newTheme })
      });
    } catch (err) {
      console.error('Error saving theme:', err);
      // Não mostra erro pro usuário, só salva no console
    }
  };

  const deleteFeed = async (feedId) => {
    if (!confirm('Are you sure you want to delete this feed?')) {
      return;
    }
    
    try {
      const res = await fetch(`/api/feeds/${feedId}`, {
        method: 'DELETE'
      });
      
      if (res.ok) {
        const data = await res.json();
        alert(data.message);
        loadFeeds(); // Recarregar a lista
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to delete feed');
      }
    } catch (err) {
      alert('Error connecting to server');
    }
  };

  const deleteAllFeeds = async () => {
    if (!confirm('Are you sure you want to delete ALL feeds? This action cannot be undone!')) {
      return;
    }
    
    try {
      const res = await fetch('/api/feeds', {
        method: 'DELETE'
      });
      
      if (res.ok) {
        const data = await res.json();
        alert(data.message);
        loadFeeds(); // Recarregar a lista
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to delete feeds');
      }
    } catch (err) {
      alert('Error connecting to server');
    }
  };
  
  // Session management functions
  const handleSaveSession = async () => {
    if (!loginSiteUrl) {
      setLoginError('Please enter a website URL');
      return;
    }
    
    setLoginError('');
    setLoginSuccess('');
    setLoginLoading(true);
    
    try {
      // Extract base URL
      const url = new URL(loginSiteUrl);
      const baseUrl = `${url.protocol}//${url.hostname}`;
      const siteName = loginSiteName || url.hostname;
      
      // Try to get cookies from manual input first, then try automatic
      let cookies = null;
      
      if (loginCookies.trim()) {
        // User provided manual cookies
        try {
          // Try to parse as JSON first
          cookies = JSON.parse(loginCookies);
        } catch {
          // If not JSON, parse as cookie string format
          cookies = {};
          loginCookies.split(';').forEach(cookie => {
            const [name, value] = cookie.trim().split('=');
            if (name && value) {
              cookies[name] = value;
            }
          });
        }
      } else {
        // Try to read cookies automatically (only works for same-origin)
        try {
          const cookieString = document.cookie;
          if (cookieString) {
            cookies = {};
            cookieString.split(';').forEach(cookie => {
              const [name, value] = cookie.trim().split('=');
              if (name && value) {
                cookies[name] = value;
              }
            });
          }
        } catch (e) {
          console.log('Could not access cookies automatically:', e);
        }
      }
      
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          site_url: baseUrl,
          site_name: siteName,
          cookies: cookies
        })
      });
      
      const data = await res.json();
      
      if (res.ok) {
        setLoginSuccess('✅ Session saved successfully! You can now generate feeds from this site.');
        setLoginSiteUrl('');
        setLoginSiteName('');
        setLoginCookies('');
        setShowManualCookies(false);
        loadSessions();
      } else {
        setLoginError(data.error || 'Failed to save session');
      }
    } catch (err) {
      setLoginError('Error connecting to server: ' + err.message);
    } finally {
      setLoginLoading(false);
    }
  };
  
  const handleDeleteSession = async (siteUrl) => {
    if (!confirm(`Are you sure you want to logout from ${siteUrl}?`)) {
      return;
    }
    
    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(siteUrl)}`, {
        method: 'DELETE'
      });
      
      if (res.ok) {
        loadSessions();
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to delete session');
      }
    } catch (err) {
      alert('Error connecting to server');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  const toggleShowMore = (feedId) => {
    setExpandedFeeds(prev => ({
      ...prev,
      [feedId]: !prev[feedId]
    }));
  };

  const renderArticleCards = (feedId, items) => {
    if (!items || items.length === 0) return null;
    
    const isExpanded = expandedFeeds[feedId];
    const itemsToShow = isExpanded ? items : items.slice(0, 10);
    
    return (
      <div style={{ marginTop: 16 }}>
        <h4 style={{ marginBottom: 12, color: theme === 'dark' ? '#fff' : '#333' }}>
          📰 Articles ({items.length})
        </h4>
        
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
          gap: 16, 
          marginBottom: 16 
        }}>
          {itemsToShow.map((item, index) => (
            <div key={index} style={{
              border: `1px solid ${theme === 'dark' ? '#444' : '#ddd'}`,
              borderRadius: 8,
              padding: 16,
              backgroundColor: theme === 'dark' ? '#2a2a2a' : '#f9f9f9',
              transition: 'transform 0.2s, box-shadow 0.2s',
              cursor: 'pointer'
            }}
            onClick={() => window.open(item.link, '_blank')}
            onMouseEnter={(e) => {
              e.target.style.transform = 'translateY(-2px)';
              e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
            }}
            onMouseLeave={(e) => {
              e.target.style.transform = 'translateY(0)';
              e.target.style.boxShadow = 'none';
            }}>
              
              {item.image && (
                <img 
                  src={item.image} 
                  alt={item.title}
                  style={{
                    width: '100%',
                    height: 150,
                    objectFit: 'cover',
                    borderRadius: 4,
                    marginBottom: 12
                  }}
                  onError={(e) => {
                    e.target.style.display = 'none';
                  }}
                />
              )}
              
              <h5 style={{
                margin: '0 0 8px 0',
                fontSize: 16,
                fontWeight: 'bold',
                color: theme === 'dark' ? '#fff' : '#333',
                lineHeight: 1.3
              }}>
                {item.title}
              </h5>
              
              <p style={{
                margin: '0 0 8px 0',
                fontSize: 14,
                color: theme === 'dark' ? '#ccc' : '#666',
                lineHeight: 1.4,
                display: '-webkit-box',
                WebkitLineClamp: 3,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden'
              }}>
                {item.description}
              </p>
              
              {item.pubDate && (
                <p style={{
                  margin: '0 0 12px 0',
                  fontSize: 12,
                  color: theme === 'dark' ? '#999' : '#888'
                }}>
                  📅 {item.pubDate}
                </p>
              )}
              
              {item.link && (
                <button
                  onClick={(e) => {
                    e.stopPropagation(); // Evita trigger do onClick do card
                    window.open(item.link, '_blank');
                  }}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#007cba',
                    color: 'white',
                    border: 'none',
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontSize: 12,
                    marginTop: 8,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.backgroundColor = '#0056b3';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.backgroundColor = '#007cba';
                  }}
                >
                  📖 Read Full Article
                </button>
              )}
            </div>
          ))}
        </div>
        
        {items.length > 10 && (
          <button
            onClick={() => toggleShowMore(feedId)}
            style={{
              padding: '8px 16px',
              backgroundColor: theme === 'dark' ? '#007cba' : '#007cba',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer'
            }}
          >
            {isExpanded ? '📤 Show Less' : `📥 Show More (${items.length - 10} more)`}
          </button>
        )}
      </div>
    );
  };

  const changeTab = (newTab) => {
    setActiveTab(newTab);
    // Limpar mensagens quando mudar de aba
    setError('');
    setConfigError('');
    setConfigSuccess('');
    setLoginError('');
    setLoginSuccess('');
  };

  // Theme styles
  const getContainerStyle = () => ({
    maxWidth: 800,
    margin: 'auto',
    padding: 32,
    backgroundColor: theme === 'dark' ? '#1e1e1e' : '#ffffff',
    color: theme === 'dark' ? '#ffffff' : '#000000',
    minHeight: '100vh'
  });

  const getInputStyle = () => ({
    width: '100%',
    padding: 8,
    marginTop: 4,
    backgroundColor: theme === 'dark' ? '#2d2d2d' : '#ffffff',
    color: theme === 'dark' ? '#ffffff' : '#000000',
    border: `1px solid ${theme === 'dark' ? '#555' : '#ccc'}`,
    borderRadius: 4
  });

  const getCardStyle = () => ({
    padding: 16,
    marginBottom: 16,
    backgroundColor: theme === 'dark' ? '#2d2d2d' : '#f8f9fa',
    borderRadius: 8,
    border: `1px solid ${theme === 'dark' ? '#555' : '#dee2e6'}`
  });

  const getButtonStyle = () => ({
    padding: '8px 16px',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer'
  });

  return (
    <div style={getContainerStyle()}>
      <style>{`
        @keyframes pulse {
          0% { opacity: 0.3; }
          50% { opacity: 0.8; }
          100% { opacity: 0.3; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes progress {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
      `}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h1>🤖 AI RSS Bridge</h1>
          <p>Generate RSS feeds from any website using AI</p>
        </div>
        <button
          onClick={toggleTheme}
          style={{
            ...getButtonStyle(),
            backgroundColor: theme === 'dark' ? '#007cba' : '#f0f0f0',
            color: theme === 'dark' ? 'white' : 'black'
          }}
        >
          {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
        </button>
      </div>

      {/* Tab Navigation */}
      <div style={{ marginBottom: 24 }}>
        <button 
          onClick={() => changeTab('generate')}
          style={{ 
            padding: '8px 16px', 
            marginRight: 8,
            backgroundColor: activeTab === 'generate' ? '#007cba' : (theme === 'dark' ? '#2d2d2d' : '#f0f0f0'),
            color: activeTab === 'generate' ? 'white' : (theme === 'dark' ? 'white' : 'black'),
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer'
          }}
        >
          Generate RSS
        </button>
        <button 
          onClick={() => changeTab('feeds')}
          style={{ 
            padding: '8px 16px',
            marginRight: 8,
            backgroundColor: activeTab === 'feeds' ? '#007cba' : (theme === 'dark' ? '#2d2d2d' : '#f0f0f0'),
            color: activeTab === 'feeds' ? 'white' : (theme === 'dark' ? 'white' : 'black'),
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer'
          }}
        >
          My Feeds ({feeds.length})
        </button>
        <button 
          onClick={() => changeTab('scheduler')}
          style={{ 
            padding: '8px 16px',
            marginRight: 8,
            backgroundColor: activeTab === 'scheduler' ? '#007cba' : (theme === 'dark' ? '#2d2d2d' : '#f0f0f0'),
            color: activeTab === 'scheduler' ? 'white' : (theme === 'dark' ? 'white' : 'black'),
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer'
          }}
        >
          Auto Update
        </button>
        <button 
          onClick={() => changeTab('config')}
          style={{ 
            padding: '8px 16px',
            marginRight: 8,
            backgroundColor: activeTab === 'config' ? '#007cba' : (theme === 'dark' ? '#2d2d2d' : '#f0f0f0'),
            color: activeTab === 'config' ? 'white' : (theme === 'dark' ? 'white' : 'black'),
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer'
          }}
        >
          ⚙️ Config
        </button>
        <button 
          onClick={() => changeTab('login')}
          style={{ 
            padding: '8px 16px',
            backgroundColor: activeTab === 'login' ? '#007cba' : (theme === 'dark' ? '#2d2d2d' : '#f0f0f0'),
            color: activeTab === 'login' ? 'white' : (theme === 'dark' ? 'white' : 'black'),
            border: 'none',
            borderRadius: 4,
            cursor: 'pointer'
          }}
        >
          🔐 Login Sessions
        </button>
      </div>

      {activeTab === 'generate' && (
        <div>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label>Website URL:</label>
              <input
                type="url"
                placeholder="https://example.com"
                value={url}
                onChange={e => setUrl(e.target.value)}
                style={getInputStyle()}
                required
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label>AI Provider:</label>
                          <select
              value={aiProvider}
              onChange={e => {
                const newProvider = e.target.value;
                setAiProvider(newProvider);
                saveLastAiProvider(newProvider);
              }}
              style={getInputStyle()}
              >
                {providers.map(provider => (
                  <option key={provider.value} value={provider.value}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ 
              marginBottom: 16, 
              padding: 12, 
              backgroundColor: theme === 'dark' ? '#0d4f3c' : '#d4edda',
              borderRadius: 8,
              border: `1px solid ${theme === 'dark' ? '#28a745' : '#c3e6cb'}`
            }}>
              <small style={{ color: theme === 'dark' ? '#c3e6cb' : '#155724', fontSize: 12 }}>
                {savedProviders.includes(aiProvider) 
                  ? `✅ Using saved API key for ${aiProvider}. Ready to generate!`
                  : `⚠️ No API key saved for ${aiProvider}. Please save it in Config tab first.`
                }
              </small>
            </div>

            <button 
              type="submit" 
              disabled={loading || !savedProviders.includes(aiProvider)}
              style={{ 
                padding: '12px 24px',
                backgroundColor: loading || !savedProviders.includes(aiProvider) ? '#ccc' : '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                cursor: loading || !savedProviders.includes(aiProvider) ? 'not-allowed' : 'pointer',
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              {loading && (
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '4px',
                  backgroundColor: 'rgba(255,255,255,0.3)',
                  animation: 'pulse 1.5s ease-in-out infinite'
                }} />
              )}
              {loading ? '🔄 Generating RSS Feed...' : 
               !savedProviders.includes(aiProvider) ? 'Save API Key in Config First' : 
               '📰 Generate RSS Feed'}
            </button>
          </form>

          {loading && (
            <div style={{ marginTop: 16 }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: 8
              }}>
                <div style={{
                  fontSize: 24,
                  marginRight: 8,
                  animation: 'spin 1s linear infinite'
                }}>⏳</div>
                <span style={{ color: theme === 'dark' ? '#fff' : '#333' }}>
                  Generating RSS feed... This may take a few seconds.
                </span>
              </div>
              <div style={{
                width: '100%',
                height: 8,
                backgroundColor: theme === 'dark' ? '#444' : '#e0e0e0',
                borderRadius: 4,
                overflow: 'hidden'
              }}>
                <div style={{
                  width: '100%',
                  height: '100%',
                  background: 'linear-gradient(90deg, #28a745, #20c997, #28a745)',
                  backgroundSize: '200% 100%',
                  animation: 'progress 2s ease-in-out infinite'
                }} />
              </div>
              <div style={{
                fontSize: 12,
                color: theme === 'dark' ? '#ccc' : '#666',
                marginTop: 4
              }}>
                🤖 AI is analyzing the website and extracting content...
              </div>
            </div>
          )}

          {error && (
            <div style={{ 
              color: theme === 'dark' ? '#ff6b6b' : 'red', 
              marginTop: 16, 
              padding: 12, 
              backgroundColor: theme === 'dark' ? '#4a1f1f' : '#ffe6e6',
              borderRadius: 4 
            }}>
              {error}
            </div>
          )}

          {result && (
            <div style={{ 
              marginTop: 16, 
              padding: 16, 
              backgroundColor: theme === 'dark' ? '#1e3a1e' : '#e6ffe6',
              borderRadius: 4,
              border: `1px solid ${theme === 'dark' ? '#28a745' : '#4caf50'}`
            }}>
              <h3 style={{ color: theme === 'dark' ? '#4caf50' : '#2e7d32' }}>🎉 RSS Feed Generated Successfully!</h3>
              <div style={{ 
                backgroundColor: theme === 'dark' ? '#0d2818' : '#f0f8f0',
                padding: '12px',
                borderRadius: '6px',
                marginBottom: '12px',
                border: `1px solid ${theme === 'dark' ? '#1e4b29' : '#c8e6c9'}`
              }}>
                <p style={{ color: theme === 'dark' ? '#e8f5e8' : '#1b5e20', margin: '0 0 8px 0' }}>
                  <strong>📰 Title:</strong> {result.title || 'Generated RSS Feed'}
                </p>
                <p style={{ color: theme === 'dark' ? '#e8f5e8' : '#1b5e20', margin: '0 0 8px 0' }}>
                  <strong>📝 Description:</strong> {result.description || 'Auto-generated RSS feed from website content'}
                </p>
                <p style={{ color: theme === 'dark' ? '#e8f5e8' : '#1b5e20', margin: '0' }}>
                  <strong>📊 Articles Found:</strong> {result.items_count} {result.items_count === 1 ? 'article' : 'articles'}
                </p>
              </div>
              
              <div style={{ marginTop: 12 }}>
                <strong style={{ color: theme === 'dark' ? '#e8f5e8' : '#1b5e20' }}>🔗 Your RSS Feed Link:</strong>
                <p style={{ 
                  fontSize: '12px', 
                  color: theme === 'dark' ? '#b0b0b0' : '#666',
                  margin: '4px 0 8px 0' 
                }}>
                  Copy this link to your RSS reader (Feedly, Inoreader, etc.) or RSS aggregator
                </p>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  marginTop: 4 
                }}>
                  <input
                    type="text"
                    value={`http://127.0.0.1:8895${result.rss_link}`}
                    readOnly
                    style={{ 
                      flex: 1, 
                      padding: 8, 
                      marginRight: 8,
                      fontFamily: 'monospace',
                      backgroundColor: theme === 'dark' ? '#2d2d2d' : 'white',
                      color: theme === 'dark' ? '#e0e0e0' : 'black',
                      border: `1px solid ${theme === 'dark' ? '#555' : '#ccc'}`
                    }}
                  />
                  <button
                    onClick={() => copyToClipboard(`http://127.0.0.1:8895${result.rss_link}`)}
                    style={{ 
                      padding: '8px 12px',
                      backgroundColor: '#007cba',
                      color: 'white',
                      border: 'none',
                      borderRadius: 4,
                      cursor: 'pointer'
                    }}
                  >
                    Copy
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'feeds' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2>Generated RSS Feeds</h2>
            {feeds.length > 0 && (
              <button
                onClick={deleteAllFeeds}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#dc3545',
                  color: 'white',
                  border: 'none',
                  borderRadius: 4,
                  cursor: 'pointer'
                }}
              >
                🗑️ Delete All Feeds
              </button>
            )}
          </div>
          {feeds.length === 0 ? (
            <p>No feeds generated yet. Go to "Generate RSS" tab to create your first feed.</p>
          ) : (
            <div>
              {feeds.map(feed => (
                <div key={feed.id} style={{ 
                  ...getCardStyle(),
                  border: `1px solid ${theme === 'dark' ? '#555' : '#ddd'}`
                }}>
                  <h3>{feed.title}</h3>
                  <p style={{ color: theme === 'dark' ? '#ccc' : '#666' }}>{feed.description}</p>
                  <p><strong>Source:</strong> <a href={feed.url} target="_blank" rel="noopener noreferrer" style={{ color: theme === 'dark' ? '#4dabf7' : '#007cba' }}>{feed.url}</a></p>
                  <p><strong>AI Provider:</strong> {feed.ai_provider}</p>
                  <p><strong>Created:</strong> {new Date(feed.created_at).toLocaleString()}</p>
                  <p><strong>Updated:</strong> {new Date(feed.updated_at).toLocaleString()}</p>
                  
                  <div style={{ marginTop: 12 }}>
                    <strong>RSS Link:</strong>
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      marginTop: 4,
                      marginBottom: 8,
                      flexWrap: 'wrap',
                      gap: '8px'
                    }}>
                      <input
                        type="text"
                        value={`http://127.0.0.1:8895${feed.rss_link}`}
                        readOnly
                        style={{ 
                          flex: '1 1 300px', 
                          minWidth: '250px',
                          padding: 8, 
                          fontFamily: 'monospace',
                          fontSize: 14 
                        }}
                      />
                      <div style={{ 
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '4px',
                        alignItems: 'center'
                      }}>
                        <button
                          onClick={() => copyToClipboard(`http://127.0.0.1:8895${feed.rss_link}`)}
                          style={{ 
                            padding: '6px 10px',
                            backgroundColor: '#007cba',
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            cursor: 'pointer',
                            fontSize: '12px',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          Copy
                        </button>
                        <button
                          onClick={() => window.open(`http://127.0.0.1:8895${feed.rss_link}`, '_blank')}
                          style={{ 
                            padding: '6px 10px',
                            backgroundColor: '#28a745',
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            cursor: 'pointer',
                            fontSize: '12px',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          📋 XML
                        </button>
                        <button
                          onClick={() => window.open(`http://127.0.0.1:8895${feed.rss_link}`, '_blank')}
                          style={{ 
                            padding: '6px 10px',
                            backgroundColor: '#17a2b8',
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            cursor: 'pointer',
                            fontSize: '12px',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          🔗 RSS
                        </button>
                        <button
                          onClick={() => reanalyzeFeed(feed.id)}
                          style={{ 
                            padding: '6px 10px',
                            backgroundColor: '#6f42c1',
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            cursor: 'pointer',
                            fontSize: '12px',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          🤖 Re-analyze
                        </button>
                        <button
                          onClick={() => deleteFeed(feed.id)}
                          style={{ 
                            padding: '6px 10px',
                            backgroundColor: '#dc3545',
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            cursor: 'pointer',
                            fontSize: '12px',
                            whiteSpace: 'nowrap'
                          }}
                        >
                          🗑️ Delete
                        </button>
                      </div>
                    </div>
                    
                                        <button 
                      onClick={() => updateFeed(feed.id)}
                      disabled={loading}
                      style={{ 
                        padding: '8px 16px',
                        backgroundColor: loading ? (theme === 'dark' ? '#555' : '#ccc') : '#ffc107',
                        color: loading ? (theme === 'dark' ? '#aaa' : '#666') : 'black',
                        border: 'none',
                        borderRadius: 4,
                        cursor: loading ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {loading ? 'Updating...' : 'Update Feed'}
                    </button>
                  </div>
                  {renderArticleCards(feed.id, feed.items)}
                </div>
              ))}
              
              {feeds.length > 0 && (
                <div style={{
                  marginTop: 24,
                  padding: 16,
                  backgroundColor: theme === 'dark' ? '#2d4a4a' : '#e3f2fd',
                  borderRadius: 8,
                  border: `1px solid ${theme === 'dark' ? '#4a7c7c' : '#b3e5fc'}`
                }}>
                  <h4 style={{ margin: '0 0 8px 0', color: theme === 'dark' ? '#4dd0e1' : '#0277bd' }}>
                    💡 Images Tip
                  </h4>
                  <p style={{ margin: 0, color: theme === 'dark' ? '#ccc' : '#666', fontSize: 14 }}>
                    If your feeds don't show images, click <strong>"Update Feed"</strong> to extract article images. 
                    Feeds created before the update need to be refreshed to include images.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'scheduler' && (
        <div>
          <h2>🕐 Automatic Updates</h2>
          <p>Configure automatic updates for your RSS feeds every hour.</p>
          
          <div style={{ 
            backgroundColor: theme === 'dark' ? '#2d2d2d' : '#f8f9fa', 
            padding: 16, 
            borderRadius: 8, 
            marginBottom: 24 
          }}>
            <h3 style={{ color: theme === 'dark' ? '#fff' : '#333' }}>Scheduler Status</h3>
            <p style={{ color: theme === 'dark' ? '#ccc' : '#666' }}><strong>Status:</strong> {schedulerStatus.running ? '🟢 Running' : '🔴 Stopped'}</p>
            {schedulerStatus.api_keys_configured.length > 0 && (
              <p style={{ color: theme === 'dark' ? '#ccc' : '#666' }}><strong>Configured providers:</strong> {schedulerStatus.api_keys_configured.join(', ')}</p>
            )}
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ color: theme === 'dark' ? '#fff' : '#333' }}>AI Provider for Updates:</label>
            <select
              value={aiProvider}
              onChange={e => setAiProvider(e.target.value)}
              style={{ 
                width: '100%', 
                padding: 8, 
                marginTop: 4,
                backgroundColor: theme === 'dark' ? '#2d2d2d' : '#ffffff',
                color: theme === 'dark' ? '#ffffff' : '#000000',
                border: `1px solid ${theme === 'dark' ? '#555' : '#ccc'}`,
                borderRadius: 4
              }}
            >
              {providers.map(provider => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </select>
            <small style={{ color: theme === 'dark' ? '#999' : '#666', fontSize: 12, display: 'block', marginTop: 4 }}>
              {savedProviders.includes(aiProvider) 
                ? '✅ API key configured in Config tab' 
                : '❌ API key not found. Please configure in Config tab first.'}
            </small>
          </div>

          <div style={{ display: 'flex', gap: 16 }}>
            <button
              onClick={startScheduler}
              disabled={loading || !savedProviders.includes(aiProvider) || schedulerStatus.running}
              style={{ 
                padding: '12px 24px',
                backgroundColor: (loading || !savedProviders.includes(aiProvider) || schedulerStatus.running) ? (theme === 'dark' ? '#555' : '#ccc') : '#28a745',
                color: (loading || !savedProviders.includes(aiProvider) || schedulerStatus.running) ? (theme === 'dark' ? '#aaa' : '#666') : 'white',
                border: 'none',
                borderRadius: 4,
                cursor: (loading || !savedProviders.includes(aiProvider) || schedulerStatus.running) ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Starting...' : 'Start Auto Updates'}
            </button>

            <button
              onClick={stopScheduler}
              disabled={loading || !schedulerStatus.running}
              style={{ 
                padding: '12px 24px',
                backgroundColor: (loading || !schedulerStatus.running) ? (theme === 'dark' ? '#555' : '#ccc') : '#dc3545',
                color: (loading || !schedulerStatus.running) ? (theme === 'dark' ? '#aaa' : '#666') : 'white',
                border: 'none',
                borderRadius: 4,
                cursor: (loading || !schedulerStatus.running) ? 'not-allowed' : 'pointer'
              }}
            >
              {loading ? 'Stopping...' : 'Stop Auto Updates'}
            </button>
          </div>

          <div style={{ 
            marginTop: 24,
            padding: 16,
            backgroundColor: theme === 'dark' ? '#2d4a2d' : '#e7f3ff',
            borderRadius: 8,
            border: `1px solid ${theme === 'dark' ? '#4a7c4a' : '#b3d9ff'}`
          }}>
            <h4 style={{ color: theme === 'dark' ? '#4dd0e1' : '#0277bd' }}>🧠 Smart Auto Update System:</h4>
            <ul style={{ margin: 0, paddingLeft: 20, color: theme === 'dark' ? '#ccc' : '#666' }}>
              <li><strong>🎯 AI Analysis (Once Only):</strong> When you generate RSS, AI analyzes the site and saves extraction "patterns"</li>
              <li><strong>⚡ Smart Updates (No AI):</strong> Auto updates use saved patterns to scrape without consuming API tokens</li>
              <li><strong>🔄 Auto Recovery:</strong> If scraping fails (site changed), system falls back to AI to rebuild patterns</li>
              <li><strong>💰 Cost Efficient:</strong> Most updates cost zero tokens - AI only when needed</li>
              <li><strong>🛠️ Manual Re-analyze:</strong> Use "Re-analyze with AI" button if site structure changes</li>
              <li><strong>⏰ Schedule:</strong> Runs every hour automatically using saved patterns</li>
            </ul>
          </div>
        </div>
      )}

      {activeTab === 'config' && (
        <div>
          <h2>⚙️ Configuration</h2>
          <p>Save your API keys securely (encrypted) for easier usage.</p>
          
          <div style={getCardStyle()}>
            <h3>🔑 API Keys Management</h3>
            
            {configError && (
              <div style={{ 
                padding: 12, 
                marginBottom: 16,
                backgroundColor: theme === 'dark' ? '#4a1f1f' : '#f8d7da',
                color: theme === 'dark' ? '#f5c6cb' : '#721c24',
                borderRadius: 8,
                border: `1px solid ${theme === 'dark' ? '#8b2635' : '#f5c6cb'}`
              }}>
                ❌ {configError}
              </div>
            )}
            
            {configSuccess && (
              <div style={{ 
                padding: 12, 
                marginBottom: 16,
                backgroundColor: theme === 'dark' ? '#1e4d3e' : '#d4edda',
                color: theme === 'dark' ? '#b8dacc' : '#155724',
                borderRadius: 8,
                border: `1px solid ${theme === 'dark' ? '#28a745' : '#c3e6cb'}`
              }}>
                {configSuccess}
              </div>
            )}
            
            {providers.map(provider => (
              <ApiKeyInput
                key={provider.value}
                provider={provider}
                savedProviders={savedProviders}
                saveApiKey={saveApiKey}
                deleteApiKey={deleteApiKey}
                theme={theme}
                getInputStyle={getInputStyle}
                getButtonStyle={getButtonStyle}
                configError={configError}
                configSuccess={configSuccess}
                setConfigError={setConfigError}
                setConfigSuccess={setConfigSuccess}
                onManage={handleManageKeys}
                keyCounts={keyCounts}
              />
            ))}
          </div>

          <div style={{ 
            ...getCardStyle(),
            marginTop: 24,
            backgroundColor: theme === 'dark' ? '#0d4f3c' : '#d4edda',
            border: `1px solid ${theme === 'dark' ? '#28a745' : '#c3e6cb'}`
          }}>
            <h4>🔐 Security Information:</h4>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li>API keys are encrypted before storage</li>
              <li>Keys are stored locally in the application database</li>
              <li>You can save multiple keys per provider for fallback</li>
              <li>If one key fails, the system will automatically try the next one</li>
              <li>You can delete saved keys anytime</li>
              <li>Saved keys will be used automatically when generating feeds</li>
            </ul>
          </div>
        </div>
      )}

      {activeTab === 'login' && (
        <div>
          <h2>🔐 Login Sessions</h2>
          <p style={{ color: theme === 'dark' ? '#bbb' : '#666' }}>
            Login to websites and save your session to access protected content.
          </p>

          {/* Add new session form */}
          <div style={getCardStyle()}>
            <h3>Login to Website</h3>
            
            <div style={{ marginBottom: 16 }}>
              <label>Website URL:</label>
              <input
                type="url"
                placeholder="https://www.deeplearning.ai/blog/"
                value={loginSiteUrl}
                onChange={e => setLoginSiteUrl(e.target.value)}
                style={getInputStyle()}
                required
              />
              <small style={{ color: theme === 'dark' ? '#888' : '#666', display: 'block', marginTop: 4 }}>
                Enter the full URL you want to access
              </small>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label>Site Name (optional):</label>
              <input
                type="text"
                placeholder="DeepLearning.AI Blog"
                value={loginSiteName}
                onChange={e => setLoginSiteName(e.target.value)}
                style={getInputStyle()}
              />
            </div>

            {loginError && (
              <div style={{ 
                padding: 12, 
                marginBottom: 16,
                backgroundColor: theme === 'dark' ? '#4f1d1d' : '#f8d7da',
                color: theme === 'dark' ? '#ff6b6b' : '#721c24',
                borderRadius: 4 
              }}>
                {loginError}
              </div>
            )}

            {loginSuccess && (
              <div style={{ 
                padding: 12, 
                marginBottom: 16,
                backgroundColor: theme === 'dark' ? '#0d4f3c' : '#d4edda',
                color: theme === 'dark' ? '#28a745' : '#155724',
                borderRadius: 4 
              }}>
                {loginSuccess}
              </div>
            )}

            <button
              onClick={() => {
                if (!loginSiteUrl) {
                  setLoginError('Please enter a website URL first');
                  return;
                }
                // Open website in new window
                const width = 1000;
                const height = 700;
                const left = (window.screen.width - width) / 2;
                const top = (window.screen.height - height) / 2;
                const loginWindow = window.open(
                  loginSiteUrl,
                  'LoginWindow',
                  `width=${width},height=${height},left=${left},top=${top},toolbar=yes,location=yes`
                );
                
                if (loginWindow) {
                  setLoginError('');
                  setLoginSuccess('✓ Login window opened! Log in there, then come back and click "Save Session"');
                } else {
                  setLoginError('Failed to open window. Please allow popups for this site.');
                }
              }}
              style={{
                ...getButtonStyle(),
                backgroundColor: '#007cba',
                color: 'white',
                width: '100%',
                marginBottom: 8
              }}
            >
              🌐 Open Website to Login
            </button>

            {showManualCookies && (
              <div style={{ marginBottom: 16, marginTop: 8 }}>
                <label>Manual Cookies (Advanced):</label>
                <textarea
                  placeholder='{"session_id": "abc123", "auth_token": "xyz789"} or cookie1=value1; cookie2=value2'
                  value={loginCookies}
                  onChange={e => setLoginCookies(e.target.value)}
                  style={{
                    ...getInputStyle(),
                    fontFamily: 'monospace',
                    fontSize: 12,
                    minHeight: 80,
                    resize: 'vertical'
                  }}
                />
                <small style={{ color: theme === 'dark' ? '#888' : '#666', display: 'block', marginTop: 4 }}>
                  Paste cookies from browser DevTools (F12 → Application → Cookies). 
                  Format: JSON object or cookie string
                </small>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button
                onClick={handleSaveSession}
                disabled={loginLoading}
                style={{
                  ...getButtonStyle(),
                  backgroundColor: loginLoading ? '#ccc' : '#28a745',
                  color: 'white',
                  flex: 1
                }}
              >
                {loginLoading ? 'Saving...' : '💾 Save Session (After Login)'}
              </button>
              
              <button
                onClick={() => setShowManualCookies(!showManualCookies)}
                style={{
                  ...getButtonStyle(),
                  backgroundColor: theme === 'dark' ? '#3d3d3d' : '#6c757d',
                  color: 'white',
                  flex: 'none',
                  padding: '8px 12px'
                }}
                title="Show manual cookie input for advanced users"
              >
                {showManualCookies ? '🔼 Hide' : '🔽 Advanced'}
              </button>
            </div>
          </div>

          {/* Logged in sessions list */}
          <div style={{ marginTop: 24 }}>
            <h3>Logged In Sessions ({sessions.length})</h3>
            {sessions.length === 0 ? (
              <div style={getCardStyle()}>
                <p style={{ margin: 0, color: theme === 'dark' ? '#888' : '#666' }}>
                  No login sessions saved yet. Add a session above to get started.
                </p>
              </div>
            ) : (
              sessions.map((session) => (
                <div key={session.id} style={getCardStyle()}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <div style={{ flex: 1 }}>
                      <h4 style={{ margin: '0 0 8px 0' }}>
                        {session.logged_in ? '✅ ' : '⚠️ '}
                        {session.site_name}
                      </h4>
                      <p style={{ margin: '4px 0', color: theme === 'dark' ? '#888' : '#666', fontSize: 14 }}>
                        {session.site_url}
                      </p>
                      <p style={{ 
                        margin: '4px 0', 
                        fontSize: 12, 
                        color: session.logged_in ? '#28a745' : '#dc3545' 
                      }}>
                        {session.logged_in ? 'Logged In' : 'Logged Out - Login Again'}
                      </p>
                      <p style={{ margin: '4px 0', color: theme === 'dark' ? '#666' : '#999', fontSize: 12 }}>
                        Last validated: {new Date(session.last_validated).toLocaleString()}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDeleteSession(session.site_url)}
                      style={{
                        ...getButtonStyle(),
                        backgroundColor: '#dc3545',
                        color: 'white'
                      }}
                    >
                      Logout
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Help section */}
          <div style={{ 
            ...getCardStyle(),
            marginTop: 24,
            backgroundColor: theme === 'dark' ? '#2d4150' : '#d1ecf1',
            border: `1px solid ${theme === 'dark' ? '#17a2b8' : '#bee5eb'}`
          }}>
            <h4>ℹ️ How to use Login Sessions:</h4>
            <ol style={{ margin: 0, paddingLeft: 20 }}>
              <li>Enter the website URL you want to access (e.g., https://www.deeplearning.ai/blog/)</li>
              <li>Click "🌐 Open Website to Login" - a new window will open</li>
              <li>Log in normally on that website</li>
              <li>Come back to this page and click "💾 Save Session"</li>
              <li>Now generate feeds from that website - it will use your login!</li>
            </ol>
            <p style={{ margin: '12px 0 0 0', fontSize: 14 }}>
              <strong>Note:</strong> If you see "🔒 Logged Out" in your RSS feed, 
              your session expired. Repeat the process to log in again.
            </p>
            <p style={{ margin: '8px 0 0 0', fontSize: 13, color: theme === 'dark' ? '#888' : '#666' }}>
              ⚠️ <strong>Technical limitation:</strong> Due to browser security (CORS), 
              automatic cookie capture only works for same-domain sites. 
              <br/>
              💡 <strong>For most sites:</strong> Click "🔽 Advanced" to manually paste cookies from browser DevTools (F12 → Application → Cookies).
            </p>
          </div>
        </div>
      )}
      
      {/* Manage API Keys Modal */}
      {manageProvider && (
        <ManageApiKeys
          provider={manageProvider}
          theme={theme}
          onClose={closeManage}
        />
      )}
    </div>
  );
}

export default App;
