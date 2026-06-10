/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  corePlugins: {
    /*
     * preflight 关闭 — 不注入 Tailwind CSS Reset，
     * 让现有 globals.css 的自定义样式完整保留，零冲突。
     * 混合模式：新组件用 Tailwind utility，旧组件保持原 CSS class。
     */
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        /* 映射项目已有的品牌色，让 Tailwind 可引用 */
        brand: {
          DEFAULT: '#3551d8',
          hover:   '#2a44c2',
          soft:    '#eef1fc',
        },
        danger:  '#dc2626',
        success: '#0f9d58',
        warning: '#d97706',
      },
      borderRadius: {
        xl: '10px',  /* 与已有 cp-panel border-radius 对齐 */
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 8px rgba(0,0,0,0.08)',
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
