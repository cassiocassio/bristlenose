// Two outputs Figma loads: dist/code.js (the main-thread code, one file) and
// dist/ui.html (the panel, with its script inlined — the plugin declares no
// network access, so nothing may load from anywhere else).
import { build } from "esbuild";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const common = { bundle: true, target: "es2017", logLevel: "warning", legalComments: "none" };

mkdirSync("dist", { recursive: true });
await build({ ...common, entryPoints: ["src/code.ts"], outfile: "dist/code.js", format: "iife" });

const ui = await build({ ...common, entryPoints: ["src/ui.ts"], write: false, format: "iife" });
// A literal "</script" inside the bundle would end the inline block early.
const script = ui.outputFiles[0].text.replace(/<\/script/gi, "<\\/script");
const html = readFileSync("src/ui.html", "utf8").replace("<!-- script -->", `<script>${script}</script>`);
if (html === readFileSync("src/ui.html", "utf8")) throw new Error("ui.html has no <!-- script --> marker");
writeFileSync("dist/ui.html", html);
