import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        mist: "#eef2ff",
        accent: "#0f766e",
        sand: "#f8fafc",
      },
    },
  },
  plugins: [],
};

export default config;
