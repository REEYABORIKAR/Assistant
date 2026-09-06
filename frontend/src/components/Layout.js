import React from 'react';
import Sidebar from './Sidebar';

const Layout = ({ children }) => {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-deep-navy text-slate-100 font-sans antialiased">
      {/* Authoritative Global Sidebar */}
      <Sidebar />

      {/* Main View Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-gradient-to-br from-deep-navy via-slate-950 to-dark-navy">
        {children}
      </div>
    </div>
  );
};

export default Layout;
