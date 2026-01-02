module.exports = {
  content: [
    "./src/**/*.{ts,tsx,js,jsx,html}",
    "../media/panel.html"
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};