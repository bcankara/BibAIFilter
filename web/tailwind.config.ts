import type { Config } from "tailwindcss";

// BibAIFilter 2 palette — same family as BibexPy v2 (navy primary, matte statuses),
// with the blue and yellow of the BibAIFilter funnel logo as accents.
const navy = {
  50: "#f4f7fa", 100: "#e7edf4", 200: "#c9d6e5", 300: "#a2b8d0", 400: "#7593b5",
  500: "#51729a", 600: "#38597f", 700: "#264667", 800: "#173553", 900: "#0c2847", 950: "#081c32",
};
const sky = {
  50: "#f0f6fd", 100: "#dceafa", 200: "#bcd7f5", 300: "#8fbcee", 400: "#5e9de4",
  500: "#3d84d6", 600: "#2b6bbb", 700: "#245698", 800: "#22497d", 900: "#203e68", 950: "#152845",
};
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#f7f9fc", soft: "#eef2f7", card: "#ffffff" },
        ink: { DEFAULT: "#172033", soft: "#243049" },
        muted: "#5f6f85",
        border: "#d8dee8",
        brand: navy,
        accent: sky,
        sun: { DEFAULT: "#f2d64b", soft: "#fbf3c6", ink: "#6b5a06" },
        success: { DEFAULT: "#15803d", soft: "#ddefe2" },
        warning: { DEFAULT: "#a16207", soft: "#f3e8c8" },
        danger: { DEFAULT: "#b91c1c", soft: "#f8dcdc" },
      },
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgba(12,40,71,0.06), 0 1px 2px 0 rgba(12,40,71,0.04)",
        soft: "0 4px 12px -2px rgba(12,40,71,0.08)",
      },
    },
  },
  plugins: [],
};
export default config;
