"""本地 PDF Layout API。生产模式同时提供 frontend/dist 静态页面。"""
import tempfile
import uuid
from pathlib import Path

import pdfplumber
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PDF Layout Inspector", docs_url="/api/docs")
storage = tempfile.TemporaryDirectory(prefix="pdf-layout-")
documents = {}
MAX_BYTES = 150 * 1024 * 1024


def layout_items(objects):
    return [
        {
            "text": item["text"].strip(),
            "bbox": [round(float(item[key]), 2) for key in ("x0", "top", "x1", "bottom")],
        }
        for item in objects
        if item.get("text", "").strip()
    ]


def detect_tables(page, strategy):
    """返回表格检测框及抽取内容；单张表格失败不影响其他策略。"""
    settings = {"vertical_strategy": strategy, "horizontal_strategy": strategy}
    tables = page.find_tables(table_settings=settings)
    return [
        {
            "bbox": [round(float(v), 2) for v in table.bbox],
            "text": f"Table {index + 1} · {len(table.rows)} rows",
            "data": table.extract(),
        }
        for index, table in enumerate(tables)
    ]


@app.get("/api/documents/{document_id}/pages/{number}/camelot/{strategy}")
def camelot_tables(document_id: str, number: int, strategy: str):
    if strategy not in {"stream", "network", "lattice", "hybrid"}:
        raise HTTPException(400, "不支持的 Camelot 策略")
    record = documents.get(document_id)
    if not record:
        raise HTTPException(404, "PDF 不存在，请重新打开")
    path, pages = record
    if not 1 <= number <= pages:
        raise HTTPException(404, "页码超出范围")
    try:
        import camelot
        with pdfplumber.open(path) as pdf:
            height = float(pdf.pages[number - 1].height)
        result = camelot.read_pdf(str(path), pages=str(number), flavor=strategy, suppress_stdout=True)
        tables = []
        for index, table in enumerate(result):
            x0, y0, x1, y1 = map(float, table._bbox)
            data = table.df.fillna("").astype(str).values.tolist()
            tables.append({
                "bbox": [round(x0, 2), round(height - y1, 2), round(x1, 2), round(height - y0, 2)],
                "text": f"Table {index + 1} · {len(data)} rows",
                "data": data,
            })
        return {"tables": tables}
    except Exception as exc:
        raise HTTPException(422, f"Camelot {strategy} 解析失败：{exc}") from exc


@app.post("/api/documents")
async def upload_pdf(file: UploadFile = File(...)):
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(400, "只支持 PDF 文件")

    document_id = uuid.uuid4().hex
    path = Path(storage.name) / f"{document_id}.pdf"
    try:
        size = 0
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "PDF 不能超过 150 MB")
                output.write(chunk)
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            if pages == 0:
                raise ValueError("PDF 没有页面")
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"无法读取 PDF：{exc}") from exc
    finally:
        await file.close()

    documents[document_id] = (path, pages)
    return {"id": document_id, "pages": pages, "filename": Path(file.filename).name}


@app.get("/api/documents/{document_id}/pages/{number}")
def page_layout(document_id: str, number: int):
    record = documents.get(document_id)
    if not record:
        raise HTTPException(404, "PDF 不存在，请重新打开")
    path, pages = record
    if not 1 <= number <= pages:
        raise HTTPException(404, "页码超出范围")
    try:
        with pdfplumber.open(path, laparams={}) as pdf:
            page = pdf.pages[number - 1]
            return {
                "page": number,
                "size": [page.width, page.height],
                "lines": layout_items(page.extract_text_lines(strip=True, return_chars=False)),
                "textboxes": layout_items(
                    page.objects.get("textboxhorizontal", []) + page.objects.get("textboxvertical", [])
                ),
                "tables": {
                    "lines": detect_tables(page, "lines"),
                    "text": detect_tables(page, "text"),
                },
            }
    except Exception as exc:
        raise HTTPException(422, f"无法解析页面：{exc}") from exc


@app.delete("/api/documents/{document_id}")
def close_pdf(document_id: str):
    record = documents.pop(document_id, None)
    if record:
        record[0].unlink(missing_ok=True)
    return {"ok": True}


dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse)
    def index():
        return "请先运行 cd frontend && npm install && npm run build"
