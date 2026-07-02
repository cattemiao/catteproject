/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 深色系主基调
        space: '#0a0a12',
        midnight: '#0f1729',
        // 霓虹点缀色
        neon: {
          purple: '#a855f7',
          blue: '#3b82f6',
          pink: '#ec4899',
          cyan: '#22d3ee',
          amber: '#fbbf24',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Montserrat', 'system-ui', 'sans-serif'],
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'flow': 'flow 3s linear infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        flow: {
          '0%': { backgroundPosition: '0% 50%' },
          '100%': { backgroundPosition: '200% 50%' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
}
