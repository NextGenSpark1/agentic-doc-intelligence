/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: '#1E3A5F',
        'navy-deep': '#16293F',
        'navy-soft': '#2C4F78',
        // Named "teal" throughout the codebase but intentionally set to brand blue
        // to match the NextGen Spark logo (#2563EB). Renaming the token would
        // require touching hundreds of class names — changing the value here is enough.
        teal: '#1558D4',
        'teal-soft': '#2D6FE0',
        red: '#B4232A',
        'red-bg': '#FBEDED',
        amber: '#C77A12',
        'amber-bg': '#FBF1E2',
        green: '#2E7D52',
        'green-bg': '#E9F3EE',
        canvas: '#E9EBEE',
        'canvas-deep': '#DEE1E6',
        panel: '#FFFFFF',
        'panel-2': '#F6F7F9',
        'panel-3': '#EEF0F3',
        border: '#D5DAE1',
        'border-strong': '#C2C9D2',
        text: '#2A2E35',
        'text-mid': '#525862',
        'text-mute': '#878E99',
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      spacing: {
        '13': '3.25rem', // 52px — used for top navbar bar height
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [],
}
