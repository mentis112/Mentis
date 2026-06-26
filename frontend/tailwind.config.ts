import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        surface: "hsl(var(--surface))",
        border: "hsl(var(--border))",
        primary: "hsl(var(--primary))",
        secondary: "hsl(var(--secondary))",
        muted: "hsl(var(--muted))",
        accent: "hsl(var(--accent))",
        danger: "hsl(var(--danger))",
        destructive: "hsl(var(--danger))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        info: "hsl(var(--info))",
      },
      borderRadius: {
        xl: "1rem",
      },
      boxShadow: {
        panel: "0 18px 55px hsl(222 47% 11% / 0.10)",
        lift: "0 16px 36px hsl(222 47% 11% / 0.14)",
        glow: "0 0 0 1px hsl(var(--primary) / 0.14), 0 18px 42px hsl(var(--primary) / 0.12)",
      },
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "'IBM Plex Sans Arabic'", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
