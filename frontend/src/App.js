import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' }
});

// Add auth token to requests
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [authPage, setAuthPage] = useState('login');
  const [cliData, setCLIData] = useState(null);

  // Auth forms
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [signupForm, setSignupForm] = useState({ username: '', email: '', password: '' });

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const response = await api.get('/auth/verify');
        setUser(response.data.user);
      } catch (err) {
        localStorage.removeItem('token');
      }
    }
    setLoading(false);
  };

  const login = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await api.post('/auth/login', loginForm);
      localStorage.setItem('token', response.data.access_token);
      setUser(response.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    }
  };

  const signup = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await api.post('/auth/signup', signupForm);
      localStorage.setItem('token', response.data.access_token);
      setUser(response.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed');
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
    setCLIData(null);
  };

  const requestCLI = async () => {
    setError('');
    try {
      const response = await api.post('/cli/request');
      setCLIData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create CLI session');
    }
  };

  const checkCLIStatus = async () => {
    if (!user) return;
    try {
      const response = await api.get(`/cli/status/${user.username}`);
      if (response.data.exists) {
        setCLIData({ container_info: response.data.container_info });
      }
    } catch (err) {
      console.log('No active CLI session');
    }
  };

  const terminateCLI = async () => {
    if (!user) return;
    try {
      await api.delete(`/cli/terminate/${user.username}`);
      setCLIData(null);
    } catch (err) {
      setError('Failed to terminate CLI session');
    }
  };

  useEffect(() => {
    if (user) {
      checkCLIStatus();
    }
  }, [user]);


  // Poll /cli/status/{username} every 20 seconds while terminal is open
  useEffect(() => {
    if (user && cliData?.container_info) {
      const interval = setInterval(() => {
        checkCLIStatus();
      }, 20000); // 20 seconds
      return () => clearInterval(interval);
    }
  }, [user, cliData?.container_info]);

  if (loading) return <div className="loading">Loading...</div>;

  if (!user) {
    return (
      <div className="container">
        <div className="auth-form">
          <h1>🚀 Unified CLI System</h1>
          
          {error && <div className="error">{error}</div>}
          
          <div className="tabs">
            <button 
              className={authPage === 'login' ? 'active' : ''} 
              onClick={() => setAuthPage('login')}
            >
              Login
            </button>
            <button 
              className={authPage === 'signup' ? 'active' : ''} 
              onClick={() => setAuthPage('signup')}
            >
              Signup
            </button>
          </div>

          {authPage === 'login' ? (
            <form onSubmit={login}>
              <input
                type="text"
                placeholder="Username"
                value={loginForm.username}
                onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                required
              />
              <button type="submit">Login</button>
            </form>
          ) : (
            <form onSubmit={signup}>
              <input
                type="text"
                placeholder="Username"
                value={signupForm.username}
                onChange={(e) => setSignupForm({...signupForm, username: e.target.value})}
                required
              />
              <input
                type="email"
                placeholder="Email"
                value={signupForm.email}
                onChange={(e) => setSignupForm({...signupForm, email: e.target.value})}
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={signupForm.password}
                onChange={(e) => setSignupForm({...signupForm, password: e.target.value})}
                required
              />
              <button type="submit">Sign Up</button>
            </form>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <header>
        <h1>🖥️ Multi User CLI System</h1>
        <div className="header-right">
          <span>Welcome, {user.username}!</span>
          <button onClick={logout} className="logout-btn">Logout</button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}

      <div className="main-content">
        <div className="card">
          <h3>🖥️ CLI Access</h3>
          {cliData?.container_info ? (
            <div className="cli-active">
              <div className="container-info">
                <p>✅ CLI session active</p>
                <p><strong>Container:</strong> {cliData.container_info.container_name}</p>
                <p><strong>Port:</strong> {cliData.container_info.port}</p>
                <button onClick={terminateCLI} className="danger">Terminate Session</button>
              </div>
              
              <div className="terminal-container">
                <div className="terminal-frame">
                  <iframe 
                    src={cliData.container_info.url}
                    title="CLI Terminal"
                    width="100%"
                    height="600"
                    style={{border: '1px solid #ccc', borderRadius: '4px'}}
                  />
                </div>
                {cliData.dashboard_url && (
                  <div className="dashboard-frame" style={{marginTop: '2rem'}}>
                    <h4>📊 Your Container Dashboard</h4>
                    <iframe
                      src={`http://localhost:3000${cliData.dashboard_url}?orgId=1&kiosk`}
                      title="User Dashboard"
                      width="100%"
                      height="600"
                      style={{border: '1px solid #ccc', borderRadius: '4px'}}
                      allowFullScreen
                    />
                  </div>
                )}
                <div className="tips">
                  <h4>💡 Tips:</h4>
                  <ul>
                    <li>Files in /workspace persist between sessions</li>
                    <li>Session auto-terminates after 30 minutes of inactivity</li>
                    <li>Resource limits: 128MB RAM, 0.5 CPU cores</li>
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <div className="cli-inactive">
              <p>No active CLI session</p>
              <button onClick={requestCLI} className="primary">Request CLI Access</button>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}

export default App;
