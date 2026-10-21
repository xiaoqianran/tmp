import modal
app=modal.App("native-pdf-layout-summary")
vol=modal.Volume.from_name("pdf-table-benchmark")
image=modal.Image.debian_slim(python_version="3.11")
@app.function(image=image,cpu=2,memory=4096,timeout=300,volumes={"/benchmark":vol})
def merge():
 import json,statistics,collections,html
 from pathlib import Path
 root=Path("/benchmark/runs/native-layout-40-20261021")
 files=list(root.glob("*.json")); pages=[]; byfile=collections.defaultdict(list)
 for f in files:
  d=json.loads(f.read_text())
  for row in d["rows"]:
   pages.append(row);byfile[d["file"]].append(row)
 valid=[r for r in pages if "error" not in r]
 met={"files":len(byfile),"tasks":len(files),"pages":len(pages),"success":len(valid),"failures":len(pages)-len(valid),"chars":sum(r["n_chars"] for r in valid),"words":sum(r["n_words"] for r in valid),"lt_textboxes":sum(r["n_lt"] for r in valid),"fitz_textblocks":sum(r["n_fitz"] for r in valid),"page_median_ms":round(statistics.median(r["ms"] for r in valid),2),"page_p95_ms":round(sorted(r["ms"] for r in valid)[int(.95*(len(valid)-1))],2),"lt_overlap_pairs":sum(r["lt_overlap"] for r in valid),"fitz_overlap_pairs":sum(r["fitz_overlap"] for r in valid)}
 example=[]
 for file,items in sorted(byfile.items()):
  candidates=sorted((r for r in items if "error" not in r and r["n_chars"]>100),key=lambda r:abs(r["n_lt"]-r["n_fitz"]),reverse=True)
  for row in candidates[:6]:example.append({"file":file,**row})
 body=['<html><meta charset="utf-8"><title>Real PDF layout text block comparisons</title><style>body{font-family:Arial;margin:20px;background:#f6f7f8}section{padding:12px;background:white;margin:15px 0;border:1px solid #ddd} .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}pre{white-space:pre-wrap;font-size:11px;overflow:auto;max-height:360px}</style><h1>Real PDFs: 3 native layout views</h1><p>Diagnostic outputs; there is NO ground-truth two-column pairing score. LT = pdfminer.six LTTextBox; fitz = PyMuPDF native block, NOT pdf2docx.</p><pre>'+html.escape(json.dumps(met,indent=2))+'</pre>']
 for row in example[:96]:
  body.append('<section><h3>'+html.escape(row["file"])+' page '+str(row["page"])+'</h3><div class="grid">')
  for name,arr in [("pdfplumber lines",row["lines"]),("pdfminer LTTextBox",row["lt"]),("PyMuPDF blocks",row["fitz"])]:
   body.append('<div><b>'+name+' ('+str(len(arr))+')</b><pre>'+html.escape("\n".join(str(x["bbox"])+"  "+x["text"].replace("\n"," / ") for x in arr[:100]))+'</pre></div>')
  body.append('</div></section>')
 body.append('</html>')
 (root/"summary.json").write_text(json.dumps(met,indent=2),encoding="utf8")
 (root/"96_examples.html").write_text("".join(body),encoding="utf8")
 vol.commit()
 return {"metrics":met,"examples":len(example[:96]),"report":str(root/"96_examples.html"),"perfile":{f:len(x) for f,x in byfile.items()}}
@app.local_entrypoint()
def main():
 import json
 print("SUMMARY",json.dumps(merge.remote(),ensure_ascii=False),flush=True)
