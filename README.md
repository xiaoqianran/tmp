# PDF Native Layout Benchmark

Real-world PDF page layout comparisons on Modal; this is an experiment, **not** a validated table or field-pair extraction model.

## Contents

- `benchmark.py`: `pdfplumber.extract_text_lines`, pdfminer.six `LTTextBox` (via `laparams={}`), and PyMuPDF text blocks on the same real PDF pages. Forty Modal containers maximum; 48 tasks for 16 documents.
- `summary.py`: merge stored results and produce a 96-page side-by-side HTML diagnostic gallery.
- `pdf2docx_pilot.py`: four two-page PDF-to-DOCX conversion probes to inspect paragraph and table structure.
- `summary.json` and `96_examples.html`: completed baseline report; no annotated layout ground truth.

## Requirements

Python 3.11+, `pip install modal`; authenticated Modal CLI; an existing Modal Volume `pdf-table-benchmark` with source PDFs under `datasets/real_public_pdfs/`.

Run from this directory:

```shell
modal run benchmark.py
modal run summary.py
modal run pdf2docx_pilot.py
```

The scripts currently reference the user's existing Modal Volume and dataset paths. For a different Modal account, first upload the PDFs to the expected Volume directory or change `ROOT`/`SRC`. No PDF data or credentials are bundled here.

**Interpretation:** The completed baseline processed 16 real PDFs (2,184 pages; 0 page errors). It found 80,504 pdfminer text blocks versus 36,205 PyMuPDF blocks. These counts are **not** detection accuracy metrics. Field-value pairing, irregular columns, and borderless table structure still require manual ground truth evaluation.

To access generated results, run `modal volume ls pdf-table-benchmark runs/native-layout-40-20261021` and `modal volume get` for individual files.
