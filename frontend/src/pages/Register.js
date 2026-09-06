import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const Register = () => {
  const { register, loading } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: '',
    password: '',
    name: '',
    confirmPassword: '',
    termsAccepted: true,
    privacyAccepted: true
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (form.password.length < 12) {
      setError('Password must be at least 12 characters long and contain uppercase, lowercase, number, and symbol.');
      return;
    }

    try {
      await register({
        name: form.name,
        email: form.email,
        password: form.password,
        confirm_password: form.confirmPassword,
        terms_accepted: form.termsAccepted,
        privacy_accepted: form.privacyAccepted
      });
      setSuccess('Registration successful! Redirecting to sign in...');
      setTimeout(() => navigate('/login'), 1500);
    } catch (err) {
      const detail = err.response?.data?.detail || err.response?.data?.error?.message || 'Registration failed. Check password requirements (12+ chars, uppercase, number, symbol).';
      if (detail === 'account could not be created') {
        setError('An account with this email already exists. Click "Sign In" below to log in.');
      } else {
        setError(detail);
      }
    }
  };

  return (
    <div className="min-h-screen w-screen flex flex-col items-center justify-center bg-deep-navy relative overflow-hidden p-4">
      {/* Background Glow Blobs */}
      <div className="absolute top-1/4 right-1/3 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md glass-card p-8 relative z-10 space-y-6 border border-cyan-500/30 shadow-[0_0_50px_rgba(0,0,0,0.6)]">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-[0_0_20px_rgba(0,240,255,0.4)] mx-auto mb-3">
            <span className="text-slate-950 font-black text-2xl">R</span>
          </div>
          <h1 className="text-2xl font-extrabold tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-sky-200 to-blue-400">
            REFYNE
          </h1>
          <p className="text-xs text-slate-400 font-medium">Create your Enterprise Workspace Account</p>
        </div>

        {error && (
          <div className="bg-rose-500/15 border border-rose-500/30 text-rose-300 rounded-lg p-3 text-xs flex items-center space-x-2">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-lg p-3 text-xs flex items-center space-x-2">
            <span>✅</span>
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              Full Name
            </label>
            <input
              type="text"
              id="name"
              name="name"
              className="glass-input w-full text-sm"
              value={form.name}
              onChange={handleChange}
              required
              placeholder="Dhiraj Parida"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              Email Address
            </label>
            <input
              type="email"
              id="email"
              name="email"
              className="glass-input w-full text-sm"
              value={form.email}
              onChange={handleChange}
              required
              placeholder="paridadhiraj20@gmail.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              Password <span className="text-[10px] text-slate-400 normal-case">(12+ chars, uppercase, number, symbol)</span>
            </label>
            <input
              type="password"
              id="password"
              name="password"
              className="glass-input w-full text-sm"
              value={form.password}
              onChange={handleChange}
              required
              minLength={12}
              placeholder="e.g. Refyne@2026Secure!"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-xs font-semibold text-slate-300 mb-1.5 uppercase tracking-wide">
              Confirm Password
            </label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              className="glass-input w-full text-sm"
              value={form.confirmPassword}
              onChange={handleChange}
              required
              minLength={12}
              placeholder="e.g. Refyne@2026Secure!"
            />
          </div>

          <div className="space-y-2 pt-1">
            <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                name="termsAccepted"
                checked={form.termsAccepted}
                onChange={handleChange}
                className="rounded border-slate-700 bg-slate-900 text-cyan-400 focus:ring-cyan-400"
              />
              <span>I accept the Terms of Service</span>
            </label>
            <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                name="privacyAccepted"
                checked={form.privacyAccepted}
                onChange={handleChange}
                className="rounded border-slate-700 bg-slate-900 text-cyan-400 focus:ring-cyan-400"
              />
              <span>I accept the Privacy Policy</span>
            </label>
          </div>

          <button type="submit" disabled={loading} className="glass-button w-full py-3 mt-2 font-bold text-sm">
            {loading ? 'Creating Account...' : 'Register Workspace'}
          </button>
        </form>

        <div className="text-center pt-2 border-t border-slate-800">
          <p className="text-xs text-slate-400">
            Already registered?{' '}
            <a href="/login" className="text-cyan-400 font-semibold hover:underline hover:text-cyan-300">
              Sign In
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Register;