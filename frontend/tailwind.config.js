/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'deep-navy': '#070b14',
        'dark-navy': '#0a0e1a',
        'dark-blue': '#111827',
        'slate-card': '#131c31',
        'electric-blue': '#38bdf8',
        'brand-cyan': '#06b6d4',
        'glow-cyan': '#00f0ff',
        'subtle-purple': '#8b5cf6',
      },
      boxShadow: {
        'glow-cyan': '0 0 15px rgba(0, 240, 255, 0.2)',
        'glow-blue': '0 0 15px rgba(56, 189, 248, 0.25)',
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      },
    },
  },
  plugins: [],
}
