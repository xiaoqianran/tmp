"""Fetch the exact PP-DocLayout-M ONNX used in the RapidDoc benchmark, once."""
import hashlib
import urllib.request
from pathlib import Path

URL = "https://www.modelscope.cn/models/RapidAI/RapidDoc/resolve/v1.0.0/layout/PP-DocLayout-M/pp_doclayout_m.onnx"
SHA256 = "2e5997712f69e2db59e78fc837e0e3ee9e71cba4d41fa57125e438950f37196d"
TARGET = Path(__file__).resolve().parents[1] / "models" / "pp_doclayout_m.onnx"


def verify(path):
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return digest == SHA256


def main():
    if verify(TARGET):
        print("[OK] PP-DocLayout-M ONNX exists")
        return
    TARGET.parent.mkdir(exist_ok=True)
    temp = TARGET.with_suffix(".download")
    try:
        print("[INFO] Downloading PP-DocLayout-M ONNX (22.4 MiB)...")
        urllib.request.urlretrieve(URL, temp)
        if not verify(temp):
            raise RuntimeError("Model SHA-256 verification failed")
        temp.replace(TARGET)
    finally:
        temp.unlink(missing_ok=True)
    print("[OK] PP-DocLayout-M ONNX ready")


if __name__ == "__main__":
    main()
