# PDF Layout Inspector

Windows CPU 单机 PDF 布局检查器：Vue 3 + PDF.js + FastAPI + pdfplumber/pdfminer.six。零 GPU、零 Modal、无 CDN，服务器默认仅监听 `127.0.0.1`。

## 安装（Windows）

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

浏览器打开 **http://127.0.0.1:8767**。安装依赖后也可运行 `start.bat`。需要 Python 3.11+、Node.js 20.19+（仅安装/构建前端时使用）。

开发模式：一个终端启动上面的 uvicorn，另一个终端 `cd frontend && npm run dev`（Vite 代理 /api）。

## 能力

- 拖入本地 PDF 或选择文件，上传到本地 FastAPI（不传外网）。
- PDF.js 使用浏览器直接绘制 PDF；Python 解析每页 **Text Lines** 与 **LTTextBox**，独立叠框。
- 双击/点击框，或在右侧搜索、选择文字块；查看原始文字与坐标。
- `Ctrl+滚轮` 围绕鼠标缩放，适应窗口与 100%。
- `A/D` 或 `←/→` 翻页，`W/S` 或 `↑/↓` 在当前 PDF 页面竖向滚动。
- 导出当前页 JSON。

端到端回归：先启动 uvicorn，再在 `frontend` 运行 `npm run test:e2e`。测试使用仓库自带的 3 页 PDF 和本机 Chrome/Edge（不下载浏览器），覆盖上传、PDF.js 渲染、Ctrl+滚轮、WASD、翻页、搜索、导出和 HTML5 拖放。若测试服务端口不是 8765，可设置 `TEST_URL=http://127.0.0.1:端口` 环境变量。

PDF 文件保存在系统临时目录：打开新文件时删除上一个 PDF，服务器进程退出时清理所有剩余文件。不提供 OCR，也不自行重新实现文字行分组算法。

## 说明

当前叠框坐标基于 PDF 页面原生坐标；旋转页或特殊 CropBox 页面仍可能需要额外校准。此工具展示布局候选，不计算字段/值配对准确率。
