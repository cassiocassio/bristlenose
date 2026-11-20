import re,sys,collections,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
out=Path(tempfile.mkdtemp())/"tp.xml"
subprocess.run(["xctrace","export","--input",sys.argv[1],"--xpath",'/trace-toc/run[1]/data/table[@schema="time-profile"]',"--output",str(out)],check=True,capture_output=True)
root=ET.parse(out).getroot(); ids={e.get("id"):e for e in root.iter() if e.get("id")}
res=lambda e: ids[e.get("ref")] if e.get("ref") else e
incl=collections.Counter(); leaf=collections.Counter(); par=collections.Counter(); main=0
for row in root.find(".//node").findall("row"):
    th=w=bt=None
    for c in row:
        c=res(c)
        if c.tag=="thread": th=c.get("fmt")
        elif c.tag=="weight": w=int(c.text)
        elif c.tag=="tagged-backtrace": bt=c
    if th and "Main Thread" in th and bt is not None:
        main+=w; fr=[res(f) for f in bt.findall("frame")]
        names=[f.get("name") or "?" for f in fr]
        for n in set(names): incl[n]+=w
        leaf[names[0]]+=w
        for i,n in enumerate(names):
            if "updateNSViewController" in n and i+1<len(names): par[names[i+1]]+=w; break
ms=lambda v: round(v/1e6)
print("main busy ms",ms(main))
print("--- top inclusive (ms) ---")
for n,v in incl.most_common(400):
    if re.search(r"WKWebView|WebKit|Representable|Toolbar|toolbar|safeArea|NSToolbar|NSSplitViewController|sizeThatFits|LayoutEngineBox|NSSplitView _|WebPage|WKWeb",n) and not "NSApplication" in n: print(ms(v), n[:150])
print("--- callers of ProjectSidebarOutline.updateNSViewController ---")
for n,v in par.most_common(6): print(ms(v), n[:150])
print("--- top leaf (self) ---")
for n,v in leaf.most_common(12): print(ms(v), n[:150])
