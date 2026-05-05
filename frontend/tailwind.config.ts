import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        gift: {
          50: '#fdf6ee',
          100: '#faebd6',
          200: '#f5d2a8',
          300: '#efb470',
          400: '#e8903a',
          500: '#e2721a',
          600: '#d35a10',
          700: '#af430f',
          800: '#8c3614',
          900: '#722e13',
          950: '#3d1407',
        },
        warm: {
          50: '#fdfbf7',
          100: '#faf4ea',
          200: '#f4e5cc',
          300: '#ecd0a3',
          400: '#e2b472',
          500: '#d9974a',
          600: '#ca7c32',
          700: '#a86129',
          800: '#884f27',
          900: '#6f4124',
          950: '#3c2010',
        },
        blush: {
          50: '#fef5f5',
          100: '#fee8e8',
          200: '#fed5d5',
          300: '#fcb2b2',
          400: '#f88282',
          500: '#f05252',
          600: '#de2727',
          700: '#bb1d1d',
          800: '#9b1c1c',
          900: '#7f1d1d',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        display: ['var(--font-playfair)', 'Georgia', 'serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
