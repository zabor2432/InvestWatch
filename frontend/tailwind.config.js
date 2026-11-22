/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "monospace"],
      },
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        raised: "rgb(var(--raised) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        fg: "rgb(var(--fg) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        risk: {
          low: "rgb(var(--risk-low) / <alpha-value>)",
          mid: "rgb(var(--risk-mid) / <alpha-value>)",
          high: "rgb(var(--risk-high) / <alpha-value>)",
        },
      },
      fontSize: { xs: ["12px", "16px"], sm: ["13px", "18px"] },
    },
  },
  plugins: [],
};
