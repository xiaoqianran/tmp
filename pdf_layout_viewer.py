"""单文件 Windows PDF 布局检查器：pip install PySide6 pdfplumber"""
import json
import sys
from pathlib import Path

import pdfplumber
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QImage, QKeySequence, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

STYLE = """
QWidget { font-family: 'Microsoft YaHei UI','Segoe UI'; font-size: 13px; color: #273348; }
QMainWindow, QWidget#root { background: #F4F6FA; }
QFrame#header, QFrame#panel { background: white; border: 1px solid #E4EAF2; }
QFrame#panel { border-radius: 12px; }
QLabel#brand { font-size: 18px; font-weight: 700; color: #15233A; }
QLabel#title { font-weight: 700; font-size: 14px; }
QLabel#muted { color: #7A8AA1; }
QPushButton { padding: 8px 13px; background: white; border: 1px solid #DEE5EF; border-radius: 8px; }
QPushButton:hover { background: #ECF2FC; }
QPushButton#primary { background: #356DE8; color: white; border-color: #356DE8; font-weight: 600; }
QPushButton:disabled { color: #ABB5C3; }
QLineEdit, QTextEdit { background: #F8FAFD; padding: 8px; border: 1px solid #E1E7F0; border-radius: 8px; }
QListWidget { background: white; border: none; outline: none; }
QListWidget::item { padding: 9px; border-bottom: 1px solid #F0F2F6; }
QListWidget::item:selected { background: #EAF1FF; color: #2353AF; }
QGraphicsView { background: #DFE6F0; border: none; }
QSplitter::handle { background: #F4F6FA; }
"""


def get_layout(page):
    def extract(items):
        return [
            {"text": item["text"].strip(),
             "bbox": [round(float(item[key]), 2) for key in ("x0", "top", "x1", "bottom")]}
            for item in items if item.get("text", "").strip()
        ]
    return {
        "page": page.page_number,
        "size": [page.width, page.height],
        "lines": extract(page.extract_text_lines(strip=True, return_chars=False)),
        "textboxes": extract(page.objects.get("textboxhorizontal", [])
                             + page.objects.get("textboxvertical", [])),
    }


def dropped_pdf(mime):
    for url in mime.urls():
        if url.isLocalFile():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".pdf" and path.is_file():
                return str(path)
    return None


class PdfView(QGraphicsView):
    def __init__(self, scene, window):
        super().__init__(scene)
        self.owner = window
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                self.owner.zoom_by(1.15 if delta > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.pick(self.mapToScene(event.position().toPoint()))
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.owner.fit_mode and self.owner.data:
            self.owner.fit_page()


class Events(QObject):
    """一个事件入口处理所有子控件的 PDF 拖拽与非输入区导航。"""
    KEYS = {
        Qt.Key.Key_Left: ("h", -1), Qt.Key.Key_A: ("h", -1),
        Qt.Key.Key_Right: ("h", 1), Qt.Key.Key_D: ("h", 1),
        Qt.Key.Key_Up: ("v", -1), Qt.Key.Key_W: ("v", -1),
        Qt.Key.Key_Down: ("v", 1), Qt.Key.Key_S: ("v", 1),
    }

    def __init__(self, window):
        super().__init__(window)
        self.owner = window

    def eventFilter(self, obj, event):
        if not isinstance(obj, QWidget) or obj.window() is not self.owner:
            return False
        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            if not event.mimeData().hasUrls():
                return False
            filename = dropped_pdf(event.mimeData())
            if filename:
                event.acceptProposedAction()
                if event.type() == QEvent.Type.Drop:
                    self.owner.open_pdf(filename)
                return True
            event.ignore()
            return True
        if event.type() == QEvent.Type.KeyPress:
            focus = QApplication.focusWidget()
            if isinstance(focus, QLineEdit) or (
                isinstance(focus, QTextEdit) and not focus.isReadOnly()
            ):
                return False
            if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                movement = self.KEYS.get(event.key())
                if movement:
                    self.owner.pan(*movement)
                    return True
        return False


class Viewer(QMainWindow):
    COLORS = {"lines": "#F05D68", "textboxes": "#3983F5"}

    def __init__(self):
        super().__init__()
        self.resize(1350, 840)
        self.setMinimumSize(900, 550)
        self.setWindowTitle("PDF Layout Inspector")
        self.setAcceptDrops(True)
        self.pdf = None
        self.data = None
        self.page_index = 0
        self.zoom_factor = 1.0
        self.fit_mode = False
        self.entries = []

        root = QWidget(objectName="root")
        root.setAcceptDrops(True)
        body = QVBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(root)

        header = QFrame(objectName="header")
        top = QHBoxLayout(header)
        top.addWidget(QLabel("◈  PDF Layout Inspector", objectName="brand"))
        top.addStretch()
        self.name = QLabel("拖拽 PDF 到窗口，或点击打开", objectName="muted")
        top.addWidget(self.name)
        button = QPushButton("＋ 打开 PDF", objectName="primary")
        button.clicked.connect(lambda: self.open_pdf())
        top.addWidget(button)
        body.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 9, 16, 9)
        self.prev = QPushButton("上一页")
        self.next = QPushButton("下一页")
        self.prev.clicked.connect(lambda: self.turn(-1))
        self.next.clicked.connect(lambda: self.turn(1))
        self.page_label = QLabel("— / —")
        self.lines = QCheckBox("Text Lines")
        self.textboxes = QCheckBox("LTTextBox")
        self.lines.setChecked(True)
        self.textboxes.setChecked(True)
        self.lines.toggled.connect(self.redraw)
        self.textboxes.toggled.connect(self.redraw)
        self.fit_button = QPushButton("适应窗口")
        self.fit_button.clicked.connect(self.fit_page)
        self.actual_button = QPushButton("100%")
        self.actual_button.clicked.connect(lambda: self.set_zoom(1))
        self.zoom_label = QLabel("100%", objectName="muted")
        export = QPushButton("导出 JSON")
        export.clicked.connect(self.export)
        for widget in (self.prev, self.page_label, self.next, self.lines, self.textboxes):
            toolbar.addWidget(widget)
        toolbar.addStretch()
        for widget in (self.fit_button, self.actual_button, self.zoom_label, export):
            toolbar.addWidget(widget)
        body.addLayout(toolbar)
        self.export_button = export

        split = QSplitter()
        split.setChildrenCollapsible(False)
        body.addWidget(split, 1)
        self.scene = QGraphicsScene()
        self.view = PdfView(self.scene, self)
        self.scene.addText("将 PDF 拖放到这里\n\n或点击右上角打开 PDF").setDefaultTextColor(QColor("#8292AB"))
        self.scene.setSceneRect(0, 0, 700, 480)
        split.addWidget(self.view)

        side = QFrame(objectName="panel")
        side.setAcceptDrops(True)
        right = QVBoxLayout(side)
        right.addWidget(QLabel("布局元素", objectName="title"))
        self.stats = QLabel("等待 PDF…", objectName="muted")
        right.addWidget(self.stats)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索识别文字")
        self.search.textChanged.connect(self.filter_items)
        right.addWidget(self.search)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.select)
        right.addWidget(self.list, 3)
        right.addWidget(QLabel("完整内容与坐标", objectName="title"))
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        right.addWidget(self.detail, 2)
        right.addWidget(QLabel("红框 Text Lines  ·  蓝框 LTTextBox", objectName="muted"))
        split.addWidget(side)
        split.setSizes([900, 450])

        self.status = QLabel("  A/D 或 ←/→ 横移  ·  W/S 或 ↑/↓ 纵移  ·  Ctrl+滚轮缩放  ·  Alt+方向键翻页", objectName="muted")
        body.addWidget(self.status)
        for key, fn in (
            ("Ctrl+O", self.open_pdf), ("Ctrl+S", self.export),
            ("Ctrl+0", self.fit_page),
            ("Alt+Left", lambda: self.turn(-1)),
            ("Alt+Right", lambda: self.turn(1)),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(fn)
        self.events = Events(self)
        QApplication.instance().installEventFilter(self.events)
        self.update_buttons()

    def open_pdf(self, filename=None):
        if not filename or isinstance(filename, bool):
            filename, _ = QFileDialog.getOpenFileName(self, "选择 PDF", "", "PDF (*.pdf)")
        if not filename:
            return
        try:
            new_pdf = pdfplumber.open(filename, laparams={})
            if not new_pdf.pages:
                raise ValueError("PDF 没有页面")
            page = new_pdf.pages[0]
            new_data = get_layout(page)
            new_image = page.to_image(resolution=144).original.convert("RGBA")
        except Exception as exc:
            if "new_pdf" in locals():
                new_pdf.close()
            QMessageBox.warning(self, "打开失败", str(exc))
            return
        if self.pdf:
            self.pdf.close()
        self.pdf, self.filename = new_pdf, str(filename)
        self.page_index = 0
        self.search.clear()
        self.name.setText(Path(filename).name)
        self.name.setToolTip(str(filename))
        self.show_page(new_data, new_image)

    def show_page(self, data=None, image=None):
        if not self.pdf:
            return False
        try:
            if data is None:
                page = self.pdf.pages[self.page_index]
                data = get_layout(page)
                image = page.to_image(resolution=144).original.convert("RGBA")
            qimage = QImage(image.tobytes(), image.width, image.height,
                            QImage.Format.Format_RGBA8888).copy()
        except Exception as exc:
            QMessageBox.warning(self, "页面解析失败", str(exc))
            return False

        self.data = data
        self.list.blockSignals(True)
        self.list.clear()
        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(qimage))
        # The initial 700x480 placeholder must not remain as the scroll area.
        self.scene.setSceneRect(0, 0, image.width, image.height)
        self.entries.clear()
        for kind in ("lines", "textboxes"):
            for item in data[kind]:
                x0, y0, x1, y1 = item["bbox"]
                rect = self.scene.addRect(x0*2, y0*2, (x1-x0)*2, (y1-y0)*2)
                row = QListWidgetItem(f"{kind}  ·  {item['text'].replace(chr(10), ' ')[:75]}")
                self.entries.append((kind, item, rect))
                self.list.addItem(row)
        self.list.blockSignals(False)
        self.detail.clear()
        self.page_label.setText(f"{self.page_index+1} / {len(self.pdf.pages)}")
        self.stats.setText(f"{len(data['lines'])} 行   ·   {len(data['textboxes'])} 文本块")
        self.filter_items(self.search.text())
        self.redraw()
        if self.fit_mode:
            self.fit_page()
        else:
            self.set_zoom(self.zoom_factor)
        self.view.horizontalScrollBar().setValue(0)
        self.view.verticalScrollBar().setValue(0)
        self.update_buttons()
        return True

    def redraw(self):
        for kind, _, rect in self.entries:
            rect.setVisible(self.lines.isChecked() if kind == "lines" else self.textboxes.isChecked())
            rect.setPen(QPen(QColor(self.COLORS[kind]), 1.5))

    def filter_items(self, text):
        query = text.strip().lower()
        for index in range(self.list.count()):
            kind, item, _ = self.entries[index]
            self.list.item(index).setHidden(query not in item["text"].lower())

    def select(self, index):
        self.redraw()
        if index < 0 or index >= len(self.entries):
            return
        kind, item, rect = self.entries[index]
        if not rect.isVisible():
            (self.lines if kind == "lines" else self.textboxes).setChecked(True)
        rect.setPen(QPen(QColor("#F3AA30"), 3))
        self.view.centerOn(rect)
        self.detail.setPlainText(item["text"] + "\n\nBBox (pt): " + str(item["bbox"]))

    def pick(self, point):
        matches = []
        for index, (_, _, rect) in enumerate(self.entries):
            if rect.isVisible() and rect.rect().contains(point):
                matches.append((rect.rect().width()*rect.rect().height(), index))
        if matches:
            index = min(matches)[1]
            if self.list.item(index).isHidden():
                self.search.clear()
            self.list.setCurrentRow(index)
            self.list.scrollToItem(self.list.item(index))

    def turn(self, step):
        if self.pdf:
            new_index = max(0, min(self.page_index + step, len(self.pdf.pages)-1))
            if new_index != self.page_index:
                previous = self.page_index
                self.page_index = new_index
                if not self.show_page():
                    self.page_index = previous

    def pan(self, axis, direction):
        bar = self.view.horizontalScrollBar() if axis == "h" else self.view.verticalScrollBar()
        bar.setValue(bar.value() + direction * 90)

    def set_zoom(self, scale):
        if not self.data:
            return
        self.fit_mode = False
        self.zoom_factor = scale
        self.view.resetTransform()
        self.view.scale(scale, scale)
        self.zoom_label.setText(f"{round(scale*100)}%")

    def fit_page(self):
        if not self.data:
            return
        self.fit_mode = True
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.zoom_factor = self.view.transform().m11()
        self.zoom_label.setText(f"{round(self.zoom_factor*100)}%")

    def zoom_by(self, factor):
        scale = self.zoom_factor * factor
        if 0.2 <= scale <= 5:
            self.fit_mode = False
            self.zoom_factor = scale
            self.view.scale(factor, factor)
            self.zoom_label.setText(f"{round(scale*100)}%")

    def update_buttons(self):
        self.prev.setEnabled(self.pdf is not None and self.page_index > 0)
        self.next.setEnabled(self.pdf is not None and self.page_index < len(self.pdf.pages)-1)
        self.export_button.setEnabled(self.data is not None)

    def export(self):
        if not self.data:
            return
        name = f"{Path(self.filename).stem}_page_{self.page_index+1}.json"
        filename, _ = QFileDialog.getSaveFileName(self, "保存布局 JSON", name, "JSON (*.json)")
        if filename:
            Path(filename).write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.setText(f"  已导出：{filename}")

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self.events)
        if self.pdf:
            self.pdf.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    viewer = Viewer()
    if len(sys.argv) > 1:
        viewer.open_pdf(sys.argv[1])
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
