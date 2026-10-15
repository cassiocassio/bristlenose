import fs from 'node:fs';
const ROOT=new URL('../../bristlenose/theme/', import.meta.url).pathname;
const css=['tokens.css','tokens-typography.css','tokens-desktop.css'].map(f=>fs.readFileSync(ROOT+f,'utf8')).join('\n');
export const STACKS = {
  token:'var(--bn-font-mono)',
  web_nodl:"'Fira Code','Consolas',monospace",
  desk_nodl:"ui-monospace, monospace",
  rogue_inspector:"'SF Mono',ui-monospace,Menlo,Consolas,monospace",
  ref_sfmono:"'SF Mono'", ref_ui:'ui-monospace', ref_menlo:'Menlo', ref_courier:'Courier', ref_couriernew:"'Courier New'", ref_generic:'monospace', proposed:"ui-monospace, Menlo, Consolas, 'DejaVu Sans Mono', monospace",
};
export const SIZES=['micro','badge','caption','label','body'];
export const WEIGHTS=[300,370,400,420,490,500,520,590,600,700];
export const TEXT='p03 00:14:32 Login.tsx AaGg0O';
export const SCALES={web:'',desktop:'data-platform="desktop"',desktop_inter:'data-platform="desktop" data-typography="inter"'};
const D=process.argv[2];
for(const [sn,attr] of Object.entries(SCALES)){
  let rows='';
  for(const [k,st] of Object.entries(STACKS)) for(const s of SIZES) for(const w of WEIGHTS)
    rows+=`<div class="r"><span data-k="${k}|${s}|${w}" style="font-family:${st};font-size:var(--bn-text-${s});font-weight:${w}">${TEXT}</span></div>\n`;
  fs.writeFileSync(`${D}/p-${sn}.html`,`<!doctype html><html lang="en" ${attr}><head><meta charset=utf-8><style>${css}</style><style>html{-webkit-font-smoothing:antialiased}body{margin:0;background:#fff;color:#000}.r{height:40px;padding-left:8px;display:flex;align-items:center}span{white-space:nowrap;line-height:1}</style></head><body>${rows}</body></html>`);
}
