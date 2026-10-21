"""单文件 PDF Layout 调试器。Windows CPU；pip install PySide6 pdfplumber"""
import json
import sys
from pathlib import Path

import pdfplumber
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QKeySequence, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGraphicsScene,
    QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

STYLE = """
QWidget { font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: #233047; }
QMainWindow, QWidget#root { background: #F4F6FA; }
QFrame#header { background: #FFFFFF; border-bottom: 1px solid #E5E9F0; }
QFrame#panel { background: #FFFFFF; border: 1px solid #E5E9F0; border-radius: 12px; }
QLabel#brand { font-size: 19px; font-weight: 700; color: #111C31; }
QLabel#section { font-size: 14px; font-weight: 700; color: #1B2B45; }
QLabel#muted { color: #8190A6; font-size: 12px; }
QLabel#filename { font-weight: 600; color: #24334A; }
QPushButton { padding: 8px 13px; background: #FFFFFF; border: 1px solid #DEE5EF; border-radius: 8px; }
QPushButton:hover { background: #F1F5FB; border-color: #BECDE1; }
QPushButton:pressed { background: #E8EFFA; }
QPushButton#primary { background: #356DE8; border-color: #356DE8; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #245BD6; }
QPushButton:disabled { color: #B1BBCA; background: #F6F8FB; }
QLineEdit, QComboBox { padding: 8px 10px; background: #F9FAFC; border: 1px solid #E0E6EF; border-radius: 8px; }
QLineEdit:focus { border-color: #7CA6F6; }
QListWidget { background: #FFFFFF; border: none; outline: none; }
QListWidget::item { padding: 10px 10px; border-bottom: 1px solid #F0F2F6; }
QListWidget::item:selected { background: #EDF3FF; color: #234FA6; border-radius: 6px; }
QListWidget::item:hover { background: #F5F8FF; }
QTextEdit { background: #F8FAFD; border: 1px solid #EBEFF5; border-radius: 8px; padding: 9px; }
QCheckBox { spacing: 7px; }
QSplitter::handle { background: transparent; width: 10px; }
QGraphicsView { border: none; background: #DDE4EF; }
"""


def read_layout(page):
    def convert(objects):
        return [
            {"text": obj.get("text", "").strip(),
             "bbox": [round(float(obj[k]), 2) for k in ("x0", "top", "x1", "bottom")]}
            for obj in objects if obj.get("text", "").strip()
        ]
    return {
        "page": page.page_number,
        "size": [page.width, page.height],
        "lines": convert(page.extract_text_lines(strip=True, return_chars=False)),
        "textboxes": convert(page.objects.get("textboxhorizontal", [])
                             + page.objects.get("textboxvertical", [])),
    }


class PdfView(QGraphicsView):
    """Ctrl + 滚轮绕鼠标缩放；普通滚轮仍然滚动页面。"""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.on_zoom = None
        self.on_pick = None

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            if self.on_zoom:
                self.on_zoom(factor)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.on_pick and event.button() == Qt.MouseButton.LeftButton:
            self.on_pick(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class Viewer(QMainWindow):
    COLORS = {"lines": "#F36565", "textboxes": "#4387F5"}
    TITLES = {"lines": "Text Line", "textboxes": "LTTextBox"}

    def __init__(self):
        super().__init__()
        self.resize(1400, 880)
        self.setMinimumSize(900, 570)
        self.setWindowTitle("PDF Layout Inspector")
        self.setAcceptDrops(True)
        self.pdf = None
        self.data = None
        self.page_index = 0
        self.entries = []
        self.scale = 2
        self.current_zoom = 1.0

        root = QWidget(objectName="root")
        body = QVBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.setCentralWidget(root)

        header = QFrame(objectName="header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 15, 24, 15)
        header_layout.setSpacing(12)
        header_layout.addWidget(QLabel("◈  PDF Layout", objectName="brand"))
        header_layout.addWidget(QLabel("INSPECTOR  /  CPU", objectName="muted"))
        header_layout.addStretch()
        self.file_label = QLabel("尚未打开文件", objectName="filename")
        header_layout.addWidget(self.file_label)
        self.open_btn = QPushButton("＋  打开 PDF", objectName="primary")
        self.open_btn.clicked.connect(self.open_pdf)
        header_layout.addWidget(self.open_btn)
        body.addWidget(header)

        controls = QHBoxLayout()
        controls.setContentsMargins(24, 14, 24, 14)
        controls.setSpacing(9)
        self.prev_btn = QPushButton("←")
        self.next_btn = QPushButton("→")
        self.prev_btn.clicked.connect(lambda: self.turn(-1))
        self.next_btn.clicked.connect(lambda: self.turn(1))
        self.page_label = QLabel("— / —")
        self.page_label.setMinimumWidth(86)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.page_label)
        controls.addWidget(self.next_btn)
        controls.addSpacing(18)
        self.lines_check = QCheckBox("Text Lines")
        self.boxes_check = QCheckBox("LTTextBox")
        self.lines_check.setChecked(True)
        self.boxes_check.setChecked(True)
        self.lines_check.toggled.connect(self.redraw)
        self.boxes_check.toggled.connect(self.redraw)
        controls.addWidget(self.lines_check)
        controls.addWidget(self.boxes_check)
        controls.addStretch()
        controls.addWidget(QLabel("缩放", objectName="muted"))
        self.zoom = QComboBox()
        self.zoom.addItems(["适应窗口", "75%", "100%", "125%", "150%", "200%"])
        self.zoom.currentIndexChanged.connect(self.apply_zoom)
        controls.addWidget(self.zoom)
        self.export_btn = QPushButton("导出 JSON")
        self.export_btn.clicked.connect(self.export)
        controls.addWidget(self.export_btn)
        body.addLayout(controls)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        body.addWidget(splitter, 1)
        viewer_panel = QFrame(objectName="panel")
        viewer_layout = QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        self.scene = QGraphicsScene()
        self.view = PdfView(self.scene)
        self.view.on_zoom = self.wheel_zoom
        self.view.on_pick = self.pick_at
        self.view.setRenderHints(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        viewer_layout.addWidget(self.view)
        splitter.addWidget(viewer_panel)

        side = QFrame(objectName="panel")
        side.setMinimumWidth(300)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.setSpacing(12)
        side_layout.addWidget(QLabel("布局元素", objectName="section"))
        self.count_label = QLabel("打开 PDF 后查看布局候选", objectName="muted")
        side_layout.addWidget(self.count_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索文字内容…")
        self.search.textChanged.connect(self.filter_items)
        side_layout.addWidget(self.search)
        self.items = QListWidget()
        self.items.currentItemChanged.connect(self.select_item)
        side_layout.addWidget(self.items, 3)
        side_layout.addWidget(QLabel("选中元素", objectName="section"))
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("点击上方文字元素，查看完整内容与坐标")
        side_layout.addWidget(self.detail, 2)
        legend = QLabel("●  红色：pdfplumber 行       ●  蓝色：pdfminer 文本块", objectName="muted")
        side_layout.addWidget(legend)
        splitter.addWidget(side)
        splitter.setSizes([920, 420])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.footer = QLabel("  就绪  ·  ←/A →/D 左右移动  ·  W/S 上下移动  ·  Alt+方向键翻页", objectName="muted")
        body.addWidget(self.footer)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_pdf)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.export)
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self.turn(-1))
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self.turn(1))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: self.zoom.setCurrentIndex(0))
        for key, horizontal, direction in (
            ("Left", True, -1), ("A", True, -1),
            ("Right", True, 1), ("D", True, 1),
            ("W", False, -1), ("S", False, 1),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(
                lambda h=horizontal, d=direction: self.pan(h, d)
            )
        self.update_buttons()

    def pan(self, horizontal, direction):
        # 搜索框和其他输入控件有焦点时，保留正常打字操作。
        if isinstance(QApplication.focusWidget(), (QLineEdit, QTextEdit, QComboBox)):
            return
        bar = self.view.horizontalScrollBar() if horizontal else self.view.verticalScrollBar()
        bar.setValue(bar.value() + direction * 90)

    def open_pdf(self, filename=None):
        if not filename or isinstance(filename, bool):
            filename, _ = QFileDialog.getOpenFileName(self, "打开 PDF", "", "PDF Files (*.pdf)")
        if not filename:
            return
        try:
            pdf = pdfplumber.open(filename, laparams={})
            if not pdf.pages:
                raise ValueError("PDF 没有页面")
        except Exception as exc:
            QMessageBox.warning(self, "无法打开 PDF", str(exc))
            return
        if self.pdf:
            self.pdf.close()
        self.pdf = pdf
        self.filename = filename
        self.page_index = 0
        self.file_label.setText(Path(filename).name)
        self.file_label.setToolTip(filename)
        self.search.clear()
        self.show_page()

    def update_buttons(self):
        self.prev_btn.setEnabled(bool(self.pdf and self.page_index > 0))
        self.next_btn.setEnabled(bool(self.pdf and self.page_index < len(self.pdf.pages) - 1))
        self.export_btn.setEnabled(self.data is not None)

    def turn(self, delta):
        if self.pdf:
            index = max(0, min(self.page_index + delta, len(self.pdf.pages) - 1))
            if index != self.page_index:
                self.page_index = index
                self.show_page()

    def show_page(self):
        if not self.pdf:
            return
        try:
            page = self.pdf.pages[self.page_index]
            data = read_layout(page)
            image = page.to_image(resolution=144).original.convert("RGBA")
            qimage = QImage(image.tobytes(), image.width, image.height,
                            QImage.Format.Format_RGBA8888).copy()
            self.data = data
            self.scene.clear()
            self.scene.addPixmap(QPixmap.fromImage(qimage))
            self.entries.clear()
            self.items.clear()
            self.detail.clear()
            for source in ("lines", "textboxes"):
                for item in data[source]:
                    x0, top, x1, bottom = item["bbox"]
                    rect = self.scene.addRect(x0*2, top*2, (x1-x0)*2, (bottom-top)*2)
                    row = QListWidgetItem(f"{self.TITLES[source]}   ·   {item['text'].replace(chr(10), ' ')[:85]}")
                    row.setData(Qt.ItemDataRole.UserRole, len(self.entries))
                    self.entries.append((source, item, rect))
                    self.items.addItem(row)
            self.page_label.setText(f"{self.page_index+1} / {len(self.pdf.pages)}")
            self.count_label.setText(f"{len(data['lines'])} 条文字行   ·   {len(data['textboxes'])} 个文本块")
            self.filter_items(self.search.text())
            self.redraw()
            self.apply_zoom()
            self.update_buttons()
            self.footer.setText(f"  第 {self.page_index+1} 页   ·   ←→ / A D 左右移动   ·   W S 上下移动   ·   Ctrl+滚轮缩放   ·   Alt+←→ 翻页")
        except Exception as exc:
            QMessageBox.warning(self, "页面解析失败", str(exc))

    def redraw(self):
        if not self.data:
            return
        for source, _, rect in self.entries:
            enabled = self.lines_check.isChecked() if source == "lines" else self.boxes_check.isChecked()
            rect.setVisible(enabled)
            color = QColor(self.COLORS[source])
            rect.setPen(QPen(color, 1.6 if source == "textboxes" else 1))
        selected = self.items.currentItem()
        if selected:
            self.highlight(selected.data(Qt.ItemDataRole.UserRole))

    def filter_items(self, value):
        keyword = value.strip().lower()
        for i in range(self.items.count()):
            row = self.items.item(i)
            index = row.data(Qt.ItemDataRole.UserRole)
            source, item, _ = self.entries[index]
            visible = keyword in item["text"].lower()
            row.setHidden(not visible)

    def select_item(self, current, previous):
        if previous:
            index = previous.data(Qt.ItemDataRole.UserRole)
            if 0 <= index < len(self.entries):
                source, _, rect = self.entries[index]
                rect.setPen(QPen(QColor(self.COLORS[source]), 1.6))
        if current:
            self.highlight(current.data(Qt.ItemDataRole.UserRole))

    def highlight(self, index):
        source, item, rect = self.entries[index]
        checkbox = self.lines_check if source == "lines" else self.boxes_check
        if not checkbox.isChecked():
            checkbox.setChecked(True)
        rect.setPen(QPen(QColor("#E9A23B"), 3))
        self.view.centerOn(rect)
        self.detail.setPlainText(item["text"] + "\n\nBBox (pt): " + str(item["bbox"]))

    def apply_zoom(self):
        if not self.data:
            return
        self.view.resetTransform()
        if self.zoom.currentIndex() == 0:
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            text = self.zoom.currentText().strip()
            try:
                factor = float(text.rstrip("%")) / 100
            except ValueError:
                factor = 1.0
            self.view.scale(factor, factor)
        self.current_zoom = self.view.transform().m11()

    def wheel_zoom(self, factor):
        if not self.data:
            return
        next_zoom = self.current_zoom * factor
        if not 0.2 <= next_zoom <= 5.0:
            return
        self.view.scale(factor, factor)
        self.current_zoom = next_zoom
        # 鼠标缩放后显示真实比例，不再错误地标记“适应窗口”。
        self.zoom.blockSignals(True)
        self.zoom.setEditable(True)
        self.zoom.setCurrentText(f"{round(next_zoom * 100)}%")
        self.zoom.blockSignals(False)

    def pick_at(self, position):
        """在预览上双击，选择最小的命中文字框。"""
        if not self.data:
            return
        hits = []
        for index, (source, item, rect) in enumerate(self.entries):
            if not rect.isVisible() or not rect.rect().contains(position):
                continue
            area = rect.rect().width() * rect.rect().height()
            hits.append((area, index))
        if hits:
            index = min(hits)[1]
            if self.items.item(index).isHidden():
                self.search.clear()
            self.items.setCurrentRow(index)
            self.items.scrollToItem(self.items.item(index))

    def export(self):
        if not self.data:
            return
        name = f"{Path(self.filename).stem}_page_{self.page_index+1}.json"
        filename, _ = QFileDialog.getSaveFileName(self, "导出 JSON", name, "JSON (*.json)")
        if filename:
            Path(filename).write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.footer.setText(f"  已导出：{filename}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")
            for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filename = url.toLocalFile()
            if filename.lower().endswith(".pdf"):
                self.open_pdf(filename)
                event.acceptProposedAction()
                break

    def closeEvent(self, event):
        if self.pdf:
            self.pdf.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Viewer()
    if len(sys.argv) > 1:
        window.open_pdf(sys.argv[1])
    window.show()
    sys.exit(app.exec())
