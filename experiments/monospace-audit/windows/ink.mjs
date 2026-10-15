import zlib from 'node:zlib'; import fs from 'node:fs';
const buf=fs.readFileSync(process.argv[2]);
let p=8,w,h,ct,idat=[];while(p<buf.length){const len=buf.readUInt32BE(p),type=buf.toString('ascii',p+4,p+8),d=buf.subarray(p+8,p+8+len);if(type==='IHDR'){w=d.readUInt32BE(0);h=d.readUInt32BE(4);ct=d[9];}else if(type==='IDAT')idat.push(d);else if(type==='IEND')break;p+=12+len;}
const bpp=ct===6?4:3,raw=zlib.inflateSync(Buffer.concat(idat)),stride=w*bpp,out=Buffer.alloc(h*stride);let prev=Buffer.alloc(stride);
for(let y=0;y<h;y++){const f=raw[y*(stride+1)],line=raw.subarray(y*(stride+1)+1,(y+1)*(stride+1)),cur=out.subarray(y*stride,(y+1)*stride);
 for(let x=0;x<stride;x++){const a=x>=bpp?cur[x-bpp]:0,b=prev[x],c=x>=bpp?prev[x-bpp]:0;let v=line[x];
  if(f===1)v+=a;else if(f===2)v+=b;else if(f===3)v+=(a+b)>>1;else if(f===4){const pp=a+b-c,pa=Math.abs(pp-a),pb=Math.abs(pp-b),pc=Math.abs(pp-c);v+=(pa<=pb&&pa<=pc)?a:(pb<=pc?b:c);}cur[x]=v&255;}prev=cur;}
const rowH=Math.round(h/ (h/120)); const inks=[];
for(let r=0;r<16;r++){let s=0;for(let y=r*120;y<(r+1)*120&&y<h;y++)for(let x=0;x<w;x++){const i=(y*w+x)*bpp;s+=255-(out[i]*0.299+out[i+1]*0.587+out[i+2]*0.114);}inks.push(s);}
console.log('png',w,'x',h);
const W=[400,520,540,550,551,560,580,600];
for(const [g,name] of [[0,'Consolas'],[1,'Cascadia Mono']]){const b=inks[g*8];console.log(name.padEnd(14),W.map((wt,j)=>`${wt}:${((inks[g*8+j]/b-1)*100).toFixed(0)}%`).join('  '));}
