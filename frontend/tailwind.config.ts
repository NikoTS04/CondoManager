import type { Config } from "tailwindcss";

// Tokens del sistema de diseño (ver DESIGN.md §4). No usar colores arbitrarios en componentes.
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#f0fdf4",
          100: "#dcfce7",
          200: "#bbf7d0",
          500: "#22c55e",
          600: "#16a34a",
          700: "#15803d",
          800: "#166534",
          900: "#14532d",
        },
        ink: "#0f172a",
        muted: "#475569",
        line: "#e2e8f0",
        surface: "#ffffff",
        canvas: "#f8fafc",
        success: { 50: "#ecfdf5", 200: "#a7f3d0", 600: "#059669", 700: "#047857", 800: "#065f46" },
        warning: { 50: "#fffbeb", 200: "#fde68a", 600: "#d97706", 700: "#b45309", 800: "#92400e" },
        danger: { 50: "#fff1f2", 200: "#fecdd3", 600: "#e11d48", 700: "#be123c", 800: "#9f1239" },
        info: { 50: "#eff6ff", 200: "#bfdbfe", 600: "#2563eb", 700: "#1d4ed8", 800: "#1e40af" },
        audit: { 50: "#f5f3ff", 200: "#ddd6fe", 600: "#7c3aed", 700: "#6d28d9", 800: "#5b21b6" },
      },
    },
  },
  plugins: [],
};
export default config;
