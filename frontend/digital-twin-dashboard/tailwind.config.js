/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Space Grotesk", "sans-serif"],
        body: ["IBM Plex Sans", "sans-serif"],
      },
      boxShadow: {
        glow: "0 10px 40px rgba(14, 165, 233, 0.25)",
      },
      backgroundImage: {
        mesh: "radial-gradient(circle at 20% 20%, rgba(14,165,233,0.25), transparent 45%), radial-gradient(circle at 80% 0%, rgba(249,115,22,0.2), transparent 45%), radial-gradient(circle at 30% 100%, rgba(16,185,129,0.12), transparent 40%)",
      },
    },
  },
  plugins: [],
};
