"""CPU-only PP-DocLayout-M ONNX table localization; no OCR or table structure parsing."""
from functools import lru_cache
from pathlib import Path

import numpy as np
import cv2
import pypdfium2 as pdfium

from .rapid_layout_self import ModelType, RapidLayout, RapidLayoutInput

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "pp_doclayout_m.onnx"


@lru_cache(maxsize=1)
def detector():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"ONNX 模型不存在：{MODEL_PATH}")
    return RapidLayout(RapidLayoutInput(
        model_type=ModelType.PP_DOCLAYOUT_M,
        model_dir_or_path=str(MODEL_PATH),
        conf_thresh=0.10,
    ))


def find_tables(path: Path, page_number: int, threshold: float = 0.5):
    with pdfium.PdfDocument(str(path)) as pdf:
        page = pdf[page_number - 1]
        width, height = page.get_size()
        image = cv2.cvtColor(np.asarray(page.render(scale=2).to_pil().convert("RGB")), cv2.COLOR_RGB2BGR)
    result = detector()([image])[0]
    scale_x = width / image.shape[1]
    scale_y = height / image.shape[0]
    tables = []
    for box, label, score in zip(result.boxes or [], result.class_names or [], result.scores or []):
        if str(label).lower() != "table" or float(score) < threshold:
            continue
        x0, y0, x1, y1 = map(float, box)
        tables.append({
            "bbox": [round(x0 * scale_x, 2), round(y0 * scale_y, 2),
                     round(x1 * scale_x, 2), round(y1 * scale_y, 2)],
            "text": f"Table {len(tables) + 1} · confidence {score:.3f}",
            "score": round(float(score), 4),
            "data": [],
        })
    return tables
