"""Real-world PDF layout benchmark; no synthetic pages, no OCR."""
import modal
app=modal.App("native-pdf-layout-40")
volume=modal.Volume.from_name("pdf-table-benchmark")
image=modal.Image.debian_slim(python_version="3.11").pip_install("pdfplumber==0.11.7","pymupdf==1.26.5","pypdf==5.4.0")
ROOT="/benchmark/datasets/real_public_pdfs"
OUT="/benchmark/runs/native-layout-40-20261021"
NAMES=["ntp_tr600.pdf","ntp_tr602.pdf","ntp_tr598.pdf","ntp_tr603.pdf","ntp_tr601.pdf","ntp_tr599.pdf","ntp_tr606.pdf","ntp_tr604.pdf","ntp_tr605.pdf","who_annex6_legacy.pdf","epa_one_generation.pdf","epa_wil_female_summary.pdf","fda_nda_208558.pdf","fda_nda_210326.pdf","fda_nda_210598.pdf","epa_chemview_wil_acute_oral.pdf"]
@app.function(image=image,cpu=2,memory=4096,timeout=1500,max_containers=40,volumes={"/benchmark":volume})
def run(task):
 import pdfplumber,fitz,statistics,time,json,traceback
 from pathlib import Path
 name,shard,mod=task
 src=str(Path(ROOT)/name)
 out=Path(OUT);out.mkdir(parents=True,exist_ok=True)
 start=time.perf_counter();rows=[]
 try:
  with pdfplumber.open(src,laparams={}) as pdf,fitz.open(src) as fdoc:
   total=len(pdf.pages)
   for idx in range(shard,total,mod):
    t=time.perf_counter()
    try:
     p=pdf.pages[idx];fp=fdoc[idx]
     words=p.extract_words()
     lines=p.extract_text_lines(strip=True,return_chars=False)
     texts=p.objects.get("textboxhorizontal",[])
     lt=[{"text":str(z.get("text",""))[:800],"bbox":[round(float(z[k]),1) for k in ("x0","top","x1","bottom")]} for z in texts]
     fb=[{"text":str(b[4])[:800],"bbox":[round(float(v),1) for v in b[:4]]} for b in fp.get_text("blocks") if len(b)>6 and b[6]==0]
     # proxy signals only: cannot be used as GT of column recognition
     def intersect_pair(blocks):
      boxes=[b["bbox"] for b in blocks]
      count=0
      for i,a in enumerate(boxes):
       for b in boxes[i+1:]:
        ix=max(0,min(a[2],b[2])-max(a[0],b[0]))
        iy=max(0,min(a[3],b[3])-max(a[1],b[1]))
        if ix>2 and iy>2:count+=1
      return count
     rows.append({"page":idx+1,"size":[round(p.width,1),round(p.height,1)],"n_chars":len(p.chars),"n_words":len(words),"n_lines":len(lines),"n_lt":len(lt),"n_fitz":len(fb),"lt_overlap":intersect_pair(lt),"fitz_overlap":intersect_pair(fb),"lt":lt,"fitz":fb,"lines":[{"text":str(l.get("text",""))[:500],"bbox":[round(float(l[k]),1) for k in ("x0","top","x1","bottom")]} for l in lines],"ms":round(1000*(time.perf_counter()-t),1)})
    except Exception as e:rows.append({"page":idx+1,"error":repr(e)})
 except Exception as e:return {"file":name,"error":repr(e),"trace":traceback.format_exc()[:300]}
 (out/f"{Path(name).stem}_{shard}.json").write_text(json.dumps({"file":name,"shard":shard,"total_pages":total,"rows":rows},ensure_ascii=False),encoding="utf8")
 volume.commit()
 return {"file":name,"shard":shard,"pages":len(rows),"errors":sum("error" in r for r in rows),"seconds":round(time.perf_counter()-start,1),"boxes":sum(r.get("n_lt",0) for r in rows)}
@app.local_entrypoint()
def main():
 tasks=[(name,i,3) for name in NAMES for i in range(3)]
 print("JOBS",len(tasks),"MAX_CONTAINERS",40,flush=True)
 for result in run.map(tasks,order_outputs=False,return_exceptions=True):print("RESULT",result,flush=True)
