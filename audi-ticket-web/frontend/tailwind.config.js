/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'audi': {
          'dark': '#1a1a2e',
          'darker': '#16213e',
          'accent': '#0f3460',
          'red': '#e94560'
        }
      }
    },
  },
  plugins: [],
}
