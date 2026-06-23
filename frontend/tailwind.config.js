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
        teal: '#0E7C86',
        'teal-soft': '#13929E',
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
    },
  },
  plugins: [],
}
