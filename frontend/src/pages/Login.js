import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const Login = () => {
  const { login, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await login({ email, password });
      navigate('/chat');
    } catch (err) {
      setError('Invalid email or password');
    }
  };

  return (
    <div className="min-h-screen w-screen flex flex-col items-center justify-center bg-deep-navy relative overflow-hidden p-4">
      {/* Background Glow Blobs */}
      <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/3 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

      {/* Main Glass Login Card */}
      <div className="w-full max-w-md glass-card p-8 relative z-10 space-y-6 border border-cyan-500/30 shadow-[0_0_50px_rgba(0,0,0,0.6)]">
        {/* Brand Identity */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-[0_0_20px_rgba(0,240,255,0.4)] mx-auto mb-3">
            <span className="text-slate-950 font-black text-2xl">R</span>
          </div>
          <h1 className="text-2xl font-extrabold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-sky-200 to-blue-400">
            REFYNE
          </h1>
          <p className="text-xs text-slate-400 font-medium">Enterprise AI Requirement & Workflow Suite</p>
        </div>

        {error && (
          <div className="bg-rose-500/15 border border-rose-500/30 text-rose-300 rounded-lg p-3 text-xs flex items-center space-x-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              Email Address
            </label>
            <input
              type="email"
              id="email"
              className="glass-input w-full text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="user@enterprise.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              Password
            </label>
            <input
              type="password"
              id="password"
              className="glass-input w-full text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="glass-button w-full py-3 mt-2 font-bold text-sm"
          >
            {loading ? 'Authenticating...' : 'Sign In to REFYNE'}
          </button>
        </form>

        <div className="text-center pt-2 border-t border-slate-800">
          <p className="text-xs text-slate-400">
            Don't have an account?{' '}
            <a href="/register" className="text-cyan-400 font-semibold hover:underline hover:text-cyan-300">
              Create an Account
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;