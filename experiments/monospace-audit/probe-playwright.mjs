// Ink per (engine, scale, stack, size, weight) from DOM screenshots at 2x. Usage: node probe-playwright.mjs <pages-dir>
// Caveat (measured 15 Oct 2026): Chromium's fullPage capture resizes the viewport, and while it does,
// Chromium's generic `monospace` draws Menlo instead of Courier. So the Chromium rows for a stack that
// falls through to the generic (web_nodl, desk_nodl) were drawn in Menlo here. Ink percentages are the
// same shape for both faces (Regular to 500, Bold from 520). Identify faces with face-check.mjs, which
// does not resize, or with CDP CSS.getPlatformFontsForNode.
import { createRequire } from 'node:module';
const { chromium, webkit } = createRequire(new URL('../../e2e/package.json', import.meta.url))('playwright');
import zlib from 'node:zlib'; import fs from 'node:fs'; import crypto from 'node:crypto';
const D=process.argv[2];
function decode(buf){let p=8,w,h,ct,idat=[];while(p<buf.length){const len=buf.readUInt32BE(p),type=buf.toString('ascii',p+4,p+8),d=buf.subarray(p+8,p+8+len);if(type==='IHDR'){w=d.readUInt32BE(0);h=d.readUInt32BE(4);ct=d[9];}else if(type==='IDAT')idat.push(d);else if(type==='IEND')break;p+=12+len;}
 const bpp=ct===6?4:3,raw=zlib.inflateSync(Buffer.concat(idat)),stride=w*bpp,out=Buffer.alloc(h*stride);let prev=Buffer.alloc(stride);
 for(let y=0;y<h;y++){const f=raw[y*(stride+1)],line=raw.subarray(y*(stride+1)+1,(y+1)*(stride+1)),cur=out.subarray(y*stride,(y+1)*stride);
  for(let x=0;x<stride;x++){const a=x>=bpp?cur[x-bpp]:0,b=prev[x],c=x>=bpp?prev[x-bpp]:0;let v=line[x];
   if(f===1)v+=a;else if(f===2)v+=b;else if(f===3)v+=(a+b)>>1;else if(f===4){const pp=a+b-c,pa=Math.abs(pp-a),pb=Math.abs(pp-b),pc=Math.abs(pp-c);v+=(pa<=pb&&pa<=pc)?a:(pb<=pc?b:c);}cur[x]=v&255;}prev=cur;}
 return {w,h,bpp,data:out};}
const out=[];
for (const [en,eng] of [['pw-webkit',webkit],['pw-chromium',chromium]]){
  const b=await eng.launch(); const pg=await (await b.newContext({deviceScaleFactor:2,viewport:{width:700,height:900}})).newPage();
  for (const sn of ['web','desktop','desktop_inter']){
    await pg.goto(`file://${D}/p-${sn}.html`); await pg.evaluate(()=>document.fonts.ready);
    const boxes=await pg.evaluate(()=>[...document.querySelectorAll('span[data-k]')].map(e=>{const r=e.getBoundingClientRect();return {k:e.dataset.k,x:r.x,y:r.y+scrollY,w:r.width,px:getComputedStyle(e).fontSize}}));
    
    const sh=decode(await pg.screenshot({fullPage:true}));
    for(const bx of boxes){const top=Math.floor(bx.y/40)*40;const x0=0,x1=sh.w,y0=top*2,y1=(top+40)*2;let ink=0;const h=crypto.createHash('md5');
      for(let y=y0;y<y1;y++){const row=sh.data.subarray(y*sh.w*sh.bpp,(y+1)*sh.w*sh.bpp);h.update(row);for(let i=0;i<row.length;i+=sh.bpp)ink+=255-(row[i]*0.299+row[i+1]*0.587+row[i+2]*0.114);}
      const [k,s,w]=bx.k.split('|');out.push({engine:en,scale:sn,stack:k,size:s,px:bx.px,weight:+w,width:+bx.w.toFixed(2),ink:Math.round(ink/255),hash:h.digest('hex').slice(0,10)});}
  }
  await b.close();
}
fs.writeFileSync(`${D}/res-pw.json`,JSON.stringify(out)); console.log(out.length);

