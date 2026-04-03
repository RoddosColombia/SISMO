/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      fontFamily: {
        "public-sans": ["Public Sans", "sans-serif"],
        inter:         ["Inter", "sans-serif"],
        montserrat:    ["Public Sans", "Montserrat", "sans-serif"],   // alias — design system prefers Public Sans
        "source-sans": ["Inter", "Source Sans 3", "sans-serif"],      // alias — design system prefers Inter
      },
      colors: {
        // ── Design system surface tiers ──────────────────────────────────────
        surface: {
          DEFAULT:           "#fcf9f8",
          bright:            "#fdf9f8",
          "container-lowest":"#ffffff",
          "container-low":   "#f6f3f2",
          container:         "#f0edec",
          "container-high":  "#eae7e6",
          "container-highest":"#e4e1e0",
        },
        // ── Legacy roddos tokens ─────────────────────────────────────────────
        roddos: {
          navy:         "#0F2A5C",
          "navy-hover": "#163A7A",
          "navy-dark":  "#0A1D40",
          gold:         "#C9A84C",
          "gold-hover": "#D4B65D",
          "gold-muted": "#E5D4A1",
          alegra:       "#00A9E0",
        },
        // ── shadcn/ui semantic tokens (referenced via CSS vars) ───────────────
        background:  "hsl(var(--background))",
        foreground:  "hsl(var(--foreground))",
        card: {
          DEFAULT:    "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT:    "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT:    "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT:    "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT:    "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT:    "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT:    "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input:  "hsl(var(--input))",
        ring:   "hsl(var(--ring))",
        chart: {
          1: "hsl(var(--chart-1))",
          2: "hsl(var(--chart-2))",
          3: "hsl(var(--chart-3))",
          4: "hsl(var(--chart-4))",
          5: "hsl(var(--chart-5))",
        },
      },
      borderRadius: {
        DEFAULT: "0.25rem",   // technical components
        sm:  "calc(var(--radius) - 4px)",
        md:  "calc(var(--radius) - 2px)",
        lg:  "var(--radius)",
        xl:  "0.75rem",       // containers
        "2xl": "1rem",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to:   { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to:   { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up":   "accordion-up 0.2s ease-out",
      },
      boxShadow: {
        // Ambient shadows per design spec
        "ambient-sm": "0 4px 24px rgba(28,27,31,0.06)",
        "ambient-md": "0 8px 40px rgba(28,27,31,0.08)",
        "ambient-lg": "0 12px 60px rgba(28,27,31,0.10)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
