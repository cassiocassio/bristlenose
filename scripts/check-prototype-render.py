#!/usr/bin/env python3
"""Render every codebook x every view of the v2 prototype and fail on a leak.

A static mockup has no test suite, and eyeballing one view does not exercise the
fixture's null fields. This drives BOOKS x {page, browse, review} through the real
render functions against a stub DOM and greps the emitted HTML for null,
undefined, NaN, [object Object] and thrown errors. Found two on 30 Aug: the floor
carries no tags/quotes fields, so both the page and the review header rendered
'undefined tags on undefined quotes'.

Usage: python3 scripts/check-prototype-render.py && node /tmp/h.js
"""

import pathlib

_HERE = pathlib.Path(__file__).resolve().parent.parent
s = (_HERE / 'docs' / 'mockups' / 'codebook-v2-prototype.html').read_text(encoding='utf-8')
i = s.rindex('<script>') + 8
j = s.rindex('</script>')
stub = """
const _out=[];
const mkEl=()=>new Proxy({_h:'',classList:{add(){},remove(){},toggle(){},contains(){return false}},style:{},dataset:{},children:[],
  appendChild(){},addEventListener(){},removeEventListener(){},setAttribute(){},getAttribute(){return null},
  closest(){return null},querySelector(){return mkEl()},querySelectorAll(){return []},focus(){},blur(){},remove(){},
  insertAdjacentHTML(){},scrollIntoView(){}},{
  get(t,k){ if(k==='innerHTML') return t._h; if(k==='textContent') return ''; if(k in t) return t[k];
            if(k==='offsetWidth'||k==='scrollHeight') return 100; return ()=>{}; },
  set(t,k,v){ if(k==='innerHTML'){t._h=v;_out.push(v);} else t[k]=v; return true; }});
const document={createElement:()=>({type:'',get switch(){return true}}),querySelector:()=>mkEl(),querySelectorAll:()=>[],
  addEventListener(){},getElementById:()=>mkEl(),body:mkEl(),documentElement:mkEl()};
const window={matchMedia:()=>({matches:false,addEventListener(){}}),addEventListener(){},getComputedStyle:()=>({getPropertyValue:()=>''})};
const requestAnimationFrame=f=>{}; const setTimeout=(f)=>{}; const localStorage={getItem:()=>null,setItem(){}};
"""
tail = """
for (const b of BOOKS) { for (const v of ['page','browse','review']) {
  try { sel=b.id; view=v; render(); } catch(e) { _out.push('THREW['+b.id+'/'+v+']: '+e.message); }
}}
const bad=[];
for (const h of _out) for (const w of ['null','undefined','NaN','[object Object]','THREW'])
  if (String(h).includes(w)) bad.push(w+' :: ...'+String(h).split(w)[0].slice(-95).replace(/\\s+/g,' ')+' >>'+w+'<<');
console.log(bad.length? [...new Set(bad)].join('\\n') : 'CLEAN - no null/undefined/NaN/throw in any book x view');
"""
pathlib.Path('/tmp/h.js').write_text(stub + s[i:j] + tail, encoding='utf-8')
