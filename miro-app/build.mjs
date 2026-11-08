// The app as static files for https://bristlenose.app/miro/ — dist/ is copied there whole.
// index.html is the app URL Miro loads unseen; app.html is the panel. Each script and the
// stylesheet are referenced with ?v=<sha8> of their bytes: the site lets a stamped URL be cached
// for a year and asks again for anything unstamped (the website's root .htaccess).
import { build } from "esbuild";
import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const common = { bundle: true, target: "es2019", format: "iife", logLevel: "warning", legalComments: "none", minify: true };
const v = (bytes) => createHash("sha256").update(bytes).digest("hex").slice(0, 8);

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist", { recursive: true });

const out = {};
for (const name of ["app", "index"]) {
  const res = await build({ ...common, entryPoints: [`src/${name}.ts`], write: false });
  out[name] = res.outputFiles[0].contents;
  writeFileSync(`dist/${name}.js`, out[name]);
}
const css = readFileSync("src/app.css");
writeFileSync("dist/app.css", css);

const stamp = (file, marks) => {
  let html = readFileSync(`src/${file}`, "utf8");
  for (const [mark, value] of Object.entries(marks)) {
    if (!html.includes(mark)) throw new Error(`${file} has no ${mark}`);
    html = html.replace(mark, value);
  }
  writeFileSync(`dist/${file}`, html);
};
stamp("app.html", { __CSS_V__: v(css), __APP_V__: v(out.app) });
stamp("index.html", { __INDEX_V__: v(out.index) });
copyFileSync("hosting/.htaccess", "dist/.htaccess");
