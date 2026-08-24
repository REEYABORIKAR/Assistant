import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { UserPlus, LogIn, Sparkles } from 'lucide-react';

export function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');

    try {
      if (mode === 'signup') {
        if (!fullName.trim()) {
          throw new Error('Please enter your full name.');
        }
        if (password !== confirmPassword) {
          throw new Error('Passwords do not match.');
        }
        await register(email.trim(), password, fullName.trim());
      } else {
        await login(email.trim(), password);
      }
      navigate('/app/projects?create=true', { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Authentication failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center bg-[#0d1127] p-4 font-sans text-slate-100">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-violet-600 to-indigo-500 font-extrabold text-2xl text-white shadow-xl shadow-violet-500/20">
            <Sparkles size={24} />
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">REFYNE</h1>
          <p className="text-sm text-slate-400">AI-Powered Requirement Engineering Assistant</p>
        </div>

        {/* Card */}
        <div className="rounded-3xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-xl">
          {/* Mode Switcher */}
          <div className="mb-6 grid grid-cols-2 rounded-xl bg-slate-800/80 p-1 text-xs font-bold select-none">
            <button
              type="button"
              onClick={() => { setMode('signin'); setError(''); }}
              className={`flex items-center justify-center gap-2 rounded-lg py-2 transition ${
                mode === 'signin' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <LogIn size={14} /> Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode('signup'); setError(''); }}
              className={`flex items-center justify-center gap-2 rounded-lg py-2 transition ${
                mode === 'signup' ? 'bg-violet-600 text-white shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <UserPlus size={14} /> Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'signup' && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                  Full Name
                </label>
                <input
                  required
                  type="text"
                  placeholder="e.g. Reeya Borikar"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Email Address
              </label>
              <input
                required
                type="email"
                placeholder="you@example.com"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Password
              </label>
              <input
                required
                type="password"
                placeholder="••••••••"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>

            {mode === 'signup' && (
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                  Confirm Password
                </label>
                <input
                  required
                  type="password"
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                />
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs font-semibold text-rose-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="mt-2 w-full rounded-xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-600/30 transition hover:bg-violet-500 disabled:opacity-50"
            >
              {busy ? (mode === 'signup' ? 'Creating Account...' : 'Signing in...') : (mode === 'signup' ? 'Create Account' : 'Sign in')}
            </button>
          </form>

          {/* Toggle link */}
          <div className="mt-6 text-center text-xs text-slate-400">
            {mode === 'signin' ? (
              <p>
                Don't have an account?{' '}
                <button type="button" onClick={() => { setMode('signup'); setError(''); }} className="font-semibold text-violet-400 hover:underline">
                  Sign up
                </button>
              </p>
            ) : (
              <p>
                Already have an account?{' '}
                <button type="button" onClick={() => { setMode('signin'); setError(''); }} className="font-semibold text-violet-400 hover:underline">
                  Sign in
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
