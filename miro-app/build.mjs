// The app as static files for https://bristlenose.app/miro/ — dist/ is copied there whole.
// index.html is the app URL Miro loads unseen; app.html is the panel. Each script and the
// stylesheet are referenced with ?v=<sha8> of their bytes: the site lets a stamped URL be cached
// for a year and asks again for anything unstamped (the website's root .htaccess).
//
// Every served file opens with a provenance comment: where its source is, and the commit it was
// built from. The code is readable in any browser anyway; the comment says where to read it
// with its history, so a company's Miro admin can check what runs in their boards.
import { build } from "esbuild";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const git = (...args) => execFileSync("git", args, { encoding: "utf8" }).trim();
const commit = git("rev-parse", "HEAD");
// A build from uncommitted source says so, rather than naming a commit it doesn't match.
const dirty = git("status", "--porcelain", "--", ".") !== "";
const provenance = [
  "Bristlenose in-Miro app. Open source, AGPL-3.0.",
  "Source: https://github.com/cassiocassio/bristlenose/tree/main/miro-app",
  `Built from commit ${commit}${dirty ? ", with uncommitted changes" : ""}`,
];
const blockComment = `/*! ${provenance.join("\n    ")} */\n`;
const htmlComment = `<!-- ${provenance.join("\n     ")} -->\n`;

const common = { bundle: true, target: "es2019", format: "iife", logLevel: "warning", legalComments: "none", minify: true, banner: { js: blockComment.trimEnd() } };
const v = (bytes) => createHash("sha256").update(bytes).digest("hex").slice(0, 8);

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist", { recursive: true });

const out = {};
for (const name of ["app", "index"]) {
  const res = await build({ ...common, entryPoints: [`src/${name}.ts`], write: false });
  out[name] = res.outputFiles[0].contents;
  writeFileSync(`dist/${name}.js`, out[name]);
}
const css = Buffer.from(blockComment + readFileSync("src/app.css", "utf8"));
writeFileSync("dist/app.css", css);

const stamp = (file, marks) => {
  let html = readFileSync(`src/${file}`, "utf8");
  for (const [mark, value] of Object.entries(marks)) {
    if (!html.includes(mark)) throw new Error(`${file} has no ${mark}`);
    html = html.replace(mark, value);
  }
  writeFileSync(`dist/${file}`, htmlComment + html);
};
stamp("app.html", { __CSS_V__: v(css), __APP_V__: v(out.app) });
stamp("index.html", { __INDEX_V__: v(out.index) });
copyFileSync("hosting/.htaccess", "dist/.htaccess");
