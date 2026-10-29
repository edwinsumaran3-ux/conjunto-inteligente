/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ops: {
          bg: "#0a0d12",
          panel: "#10151c",
          panel2: "#141a22",
          line: "#1d2530",
          linesoft: "#171d27",
          ink: "#dbe4ee",
          inkdim: "#7c8a9a",
          inkfaint: "#4b5768",
          accent: "#31d3d6",
          amber: "#e0a233",
          red: "#e0564f",
          green: "#3fbf7f",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SF Mono", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
