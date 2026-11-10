/**
 * BibAIFilter 2 web interface.
 *  - `npm run dev`          → http://localhost:3000, talks to the API on 127.0.0.1:8765
 *  - `npm run build:static` → static export in out/, bundled into the Python package (_web/)
 * Pages use query strings (e.g. /run/?id=...) instead of dynamic routes, so the export
 * is a plain set of HTML files.
 */
const isStatic = process.env.BIBAIFILTER_BUILD_MODE === "static";
module.exports = {
  reactStrictMode: true,
  ...(isStatic && {
    output: "export",
    images: { unoptimized: true },
    trailingSlash: true,
    typescript: { ignoreBuildErrors: false },
    eslint: { ignoreDuringBuilds: true },
  }),
};
