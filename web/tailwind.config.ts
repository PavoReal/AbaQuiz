import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,html}", "./views/**/*.html"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#2563EB",
          hover: "#1D4ED8",
        },
        // Chart colors
        chart: {
          1: "#3B82F6",
          2: "#06B6D4",
          3: "#8B5CF6",
          4: "#EC4899",
          5: "#F97316",
        },
      },
      fontFamily: {
        display: ['"IBM Plex Mono"', "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
} satisfies Config;
