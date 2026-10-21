"""Windows CPU PDF layout viewer. Install: pip install PySide6 pdfplumber"""
import json
import sys
from pathlib import Path

import pdfplumber
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)


def extract(page):
    def collect(objects):
        return [
            {"text": o["text"].strip(), "bbox": [float(o[k]) for k in ("x0", "top", "x1", "bottom")]}
            for o in objects if o.get("text", "").strip()
        ]
    return {
        "page": page.page_number,
        "lines": collect(page.extract_text_lines(strip=True, return_chars=False)),
        "textboxes": collect(page.objects.get("textboxhorizontal", [])
                             + page.objects.get("textboxvertical", [])),
    }


class Viewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1200, 800)
        self.setWindowTitle("PDF Layout — pdfplumber vs pdfminer.six")
        self.pdf = None
        self.data = None
        self.index = 0
        self.boxes = []

        toolbar = QHBoxLayout()
        self.info = QLabel("打开一个 PDF")
        for title, action in (
            ("打开 PDF", self.open_pdf), ("上一页", lambda: self.turn(-1)),
            ("下一页", lambda: self.turn(1)), ("导出 JSON", self.export),
        ):
            button = QPushButton(title)
            button.clicked.connect(action)
            toolbar.addWidget(button)
        toolbar.addWidget(self.info, 1)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.items = QListWidget()
        self.items.currentRowChanged.connect(self.select)
        self.detail = QTextEdit(readOnly=True)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("红框：pdfplumber 行；蓝框：pdfminer LTTextBox"))
        side_layout.addWidget(self.items, 3)
        side_layout.addWidget(self.detail, 2)

        split = QSplitter()
        split.addWidget(self.view)
        split.addWidget(side)
        split.setSizes([800, 400])
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addLayout(toolbar)
        root_layout.addWidget(split)
        self.setCentralWidget(root)

    def open_pdf(self, filename=None):
        if not filename:
            filename, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if not filename:
            return
        try:
            pdf = pdfplumber.open(filename, laparams={})
            if not pdf.pages:
                raise ValueError("空 PDF")
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", str(exc))
            return
        if self.pdf:
            self.pdf.close()
        self.pdf, self.filename, self.index = pdf, filename, 0
        self.show_page()

    def turn(self, step):
        if self.pdf:
            self.index = max(0, min(self.index + step, len(self.pdf.pages) - 1))
            self.show_page()

    def show_page(self):
        if not self.pdf:
            return
        try:
            page = self.pdf.pages[self.index]
            self.data = extract(page)
            image = page.to_image(resolution=144).original.convert("RGBA")
            qimage = QImage(image.tobytes(), image.width, image.height,
                            QImage.Format.Format_RGBA8888).copy()
            self.scene.clear()
            self.scene.addPixmap(QPixmap.fromImage(qimage))
            self.boxes.clear()
            self.items.clear()
            for source, color in (("lines", "#e34444"), ("textboxes", "#267bf2")):
                for item in self.data[source]:
                    x0, y0, x1, y1 = item["bbox"]
                    rect = self.scene.addRect(x0*2, y0*2, (x1-x0)*2, (y1-y0)*2,
                                              QPen(QColor(color), 1.5))
                    self.boxes.append((item, rect, color))
                    preview = item["text"].replace("\n", " ")[:80]
                    self.items.addItem(f"[{source}] {preview}")
            self.info.setText(f"{Path(self.filename).name} | {self.index+1}/{len(self.pdf.pages)}")
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as exc:
            QMessageBox.warning(self, "解析失败", str(exc))

    def select(self, index):
        if index < 0 or index >= len(self.boxes):
            return
        for _, rect, color in self.boxes:
            rect.setPen(QPen(QColor(color), 1.5))
        item, rect, _ = self.boxes[index]
        rect.setPen(QPen(QColor("#ffcc00"), 3))
        self.view.centerOn(rect)
        self.detail.setPlainText(item["text"] + "\n\nBBox: " + str(item["bbox"]))

    def export(self):
        if not self.data:
            return
        name = f"{Path(self.filename).stem}_page_{self.index+1}.json"
        target, _ = QFileDialog.getSaveFileName(self, "保存 JSON", name, "JSON (*.json)")
        if target:
            Path(target).write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def closeEvent(self, event):
        if self.pdf:
            self.pdf.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Viewer()
    if len(sys.argv) > 1:
        window.open_pdf(sys.argv[1])
    window.show()
    sys.exit(app.exec())
