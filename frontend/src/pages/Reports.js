import React from 'react';

const Reports = () => {
  return (
    <div className="flex-1 flex items-center justify-center p-8 bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
      <div className="glass-card max-w-lg p-10 text-center space-y-5 border border-cyan-500/30 shadow-[0_0_40px_rgba(0,240,255,0.15)]">
        <div className="w-20 h-20 rounded-2xl bg-slate-900 border border-cyan-500/40 mx-auto flex items-center justify-center text-4xl text-cyan-400 shadow-inner">
          📈
        </div>
        <h2 className="text-2xl font-extrabold text-slate-100">Reports & Analytics Coming Soon</h2>
        <p className="text-sm text-slate-400 leading-relaxed max-w-md mx-auto">
          Executive compliance summaries, requirement traceability matrix exports, risk trends, and automated PDF reporting suites will be available in an upcoming release.
        </p>
        <div className="pt-2">
          <span className="inline-block text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-950 text-cyan-300 border border-cyan-500/40 font-bold tracking-wider">
            STATUS: COMING_SOON
          </span>
        </div>
      </div>
    </div>
  );
};

export default Reports;
