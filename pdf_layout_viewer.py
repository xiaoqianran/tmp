"""Windows CPU PDF layout inspector. Install: pip install pdfplumber
Run: python pdf_layout_viewer.py [document.pdf]
Uses Tkinter, Pillow and pypdfium2 (installed via pdfplumber dependencies).
No Modal, GPU, OCR, external network or project imports.
"""
from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import pdfplumber
    from PIL import ImageTk
except ImportError as exc:
    raise SystemExit("Install dependencies: pip install pdfplumber") from exc


def extract_layout(page) -> dict:
    """Two independent grouping views from the same pdfplumber page."""
    def box(item):
        return [round(float(item[key]), 2) for key in ("x0", "top", "x1", "bottom")]

    return {
        "page": page.page_number,
        "width": page.width,
        "height": page.height,
        "pdfplumber_lines": [
            {"text": row.get("text", ""), "bbox": box(row)}
            for row in page.extract_text_lines(strip=True, return_chars=False)
            if row.get("text", "").strip()
        ],
        "pdfminer_textboxes": [
            {"text": item.get("text", "").strip(), "bbox": box(item)}
            for name in ("textboxhorizontal", "textboxvertical")
            for item in page.objects.get(name, [])
            if item.get("text", "").strip()
        ],
    }


class LayoutViewer:
    COLORS = {"pdfplumber_lines": "#e35252", "pdfminer_textboxes": "#2686ff"}

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("PDF Layout: pdfplumber vs pdfminer LTTextBox (CPU)")
        root.geometry("1280x820")
        self.pdf = None
        self.path = None
        self.page_index = 0
        self.zoom = tk.DoubleVar(value=1.4)
        self.show_lines = tk.BooleanVar(value=True)
        self.show_boxes = tk.BooleanVar(value=True)
        self.layout = None
        self.photo = None
        self._canvas_image = None

        toolbar = ttk.Frame(root, padding=8)
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="打开 PDF", command=self.open_dialog).pack(side="left")
        ttk.Button(toolbar, text="上一页", command=lambda: self.change_page(-1)).pack(side="left", padx=3)
        ttk.Button(toolbar, text="下一页", command=lambda: self.change_page(1)).pack(side="left", padx=3)
        self.page_label = ttk.Label(toolbar, text="未选择 PDF")
        self.page_label.pack(side="left", padx=12)
        ttk.Checkbutton(toolbar, text="pdfplumber 行 (红)", variable=self.show_lines, command=self.redraw).pack(side="left")
        ttk.Checkbutton(toolbar, text="pdfminer 文本块 (蓝)", variable=self.show_boxes, command=self.redraw).pack(side="left", padx=8)
        ttk.Label(toolbar, text="缩放").pack(side="left")
        ttk.Combobox(toolbar, textvariable=self.zoom, values=[1.0, 1.4, 2.0, 2.5], state="readonly", width=5).pack(side="left", padx=4)
        ttk.Button(toolbar, text="刷新", command=self.show_page).pack(side="left")
        ttk.Button(toolbar, text="导出本页 JSON", command=self.export_json).pack(side="right")

        panel = ttk.Panedwindow(root, orient="horizontal")
        panel.pack(fill="both", expand=True)
        left = ttk.Frame(panel)
        right = ttk.Frame(panel)
        panel.add(left, weight=3)
        panel.add(right, weight=2)

        self.canvas = tk.Canvas(left, background="#666666", highlightthickness=0)
        vbar = ttk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        hbar = ttk.Scrollbar(left, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        ttk.Label(right, text="布局候选（选择条目定位）", padding=8).pack(anchor="w")
        self.tree = ttk.Treeview(right, columns=("type", "bbox"), show="tree headings", height=14)
        self.tree.heading("#0", text="内容")
        self.tree.heading("type", text="来源")
        self.tree.heading("bbox", text="BBox (pt)")
        self.tree.column("#0", width=240)
        self.tree.column("type", width=100)
        self.tree.column("bbox", width=170)
        tree_scroll = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="top", fill="both", expand=True, padx=8)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        ttk.Label(right, text="完整文字", padding=8).pack(anchor="w")
        self.detail = tk.Text(right, wrap="word", height=10)
        self.detail.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def open_dialog(self):
        filename = filedialog.askopenfilename(title="选择 PDF", filetypes=[("PDF", "*.pdf")])
        if filename:
            self.open_pdf(filename)

    def open_pdf(self, filename: str):
        try:
            new_pdf = pdfplumber.open(filename, laparams={})
            if not new_pdf.pages:
                raise ValueError("PDF 不包含页面")
        except Exception as exc:
            messagebox.showerror("无法打开 PDF", str(exc))
            return
        if self.pdf is not None:
            self.pdf.close()
        self.pdf = new_pdf
        self.path = Path(filename)
        self.page_index = 0
        self.show_page()

    def change_page(self, delta: int):
        if self.pdf is not None:
            target = min(max(0, self.page_index + delta), len(self.pdf.pages) - 1)
            if target != self.page_index:
                self.page_index = target
                self.show_page()

    def show_page(self):
        if self.pdf is None:
            return
        try:
            page = self.pdf.pages[self.page_index]
            self.layout = extract_layout(page)
            scale = float(self.zoom.get())
            rendered = page.to_image(resolution=72 * scale).original.convert("RGB")
            self.photo = ImageTk.PhotoImage(rendered)
            self.canvas.delete("all")
            self._canvas_image = self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
            self.canvas.configure(scrollregion=(0, 0, rendered.width, rendered.height))
            self.page_label.configure(
                text=f"{self.path.name} | {self.page_index + 1}/{len(self.pdf.pages)} | "
                     f"行 {len(self.layout['pdfplumber_lines'])} | LTTextBox {len(self.layout['pdfminer_textboxes'])}"
            )
            self.tree.delete(*self.tree.get_children())
            for source, title in [("pdfplumber_lines", "行"), ("pdfminer_textboxes", "LTTextBox")]:
                group = self.tree.insert("", "end", text=f"{title} ({len(self.layout[source])})", open=True)
                for idx, item in enumerate(self.layout[source]):
                    preview = item["text"].replace("\n", " ")[:65]
                    self.tree.insert(group, "end", iid=f"{source}:{idx}", text=preview,
                                     values=(title, str(item["bbox"])))
            self.redraw()
        except Exception as exc:
            messagebox.showerror("解析失败", f"第 {self.page_index + 1} 页：{exc}")

    def redraw(self):
        self.canvas.delete("overlay")
        if self.layout is None or self.photo is None:
            return
        scale = float(self.zoom.get())
        for source, enabled in [("pdfplumber_lines", self.show_lines.get()),
                                ("pdfminer_textboxes", self.show_boxes.get())]:
            if not enabled:
                continue
            for idx, item in enumerate(self.layout[source]):
                x0, y0, x1, y1 = (v * scale for v in item["bbox"])
                self.canvas.create_rectangle(x0, y0, x1, y1, outline=self.COLORS[source],
                                             width=2 if source == "pdfminer_textboxes" else 1,
                                             tags=("overlay", f"item:{source}:{idx}"))

    def on_select(self, _event=None):
        ids = self.tree.selection()
        if not ids or ":" not in ids[0] or self.layout is None:
            return
        source, index = ids[0].split(":", 1)
        item = self.layout[source][int(index)]
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", item["text"])
        self.redraw()
        scale = float(self.zoom.get())
        x0, y0, x1, y1 = (v * scale for v in item["bbox"])
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#ffff00", width=3, tags="overlay")
        region = self.canvas.cget("scrollregion").split()
        if len(region) == 4:
            width = float(region[2])
            height = float(region[3])
            self.canvas.xview_moveto(max(0.0, min(1.0, (x0 - 80) / max(width, 1))))
            self.canvas.yview_moveto(max(0.0, min(1.0, (y0 - 80) / max(height, 1))))

    def export_json(self):
        if self.layout is None:
            return
        target = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile=f"{self.path.stem}_page_{self.page_index + 1}.json"
        )
        if target:
            Path(target).write_text(json.dumps(self.layout, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self):
        if self.pdf is not None:
            self.pdf.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    viewer = LayoutViewer(root)
    if len(sys.argv) > 1:
        viewer.open_pdf(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    main()
