/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        sentinel: {
          bg: '#0f1117',
          card: '#1a1d27',
          border: '#2a2d3a',
          accent: '#6366f1',
          green: '#22c55e',
          yellow: '#eab308',
          orange: '#f97316',
          red: '#ef4444',
        },
      },
    },
  },
  plugins: [],
}
