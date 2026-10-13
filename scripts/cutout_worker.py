#!/usr/bin/env python3
"""被写体切り抜き専用の短寿命ワーカー。

Webサーバーと分離し、処理後にONNXモデルと推論バッファをOSへ返す。
"""
import argparse
import os
import tempfile
import urllib.request

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter, ImageOps

MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MAX_OUTPUT_EDGE = 1600


def clean_alpha(image):
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha = alpha.point(lambda v: 0 if v < 88 else (255 if v > 220 else int((v - 88) * 255 / 132)))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.45))
    rgba.putalpha(alpha)
    return rgba


def download(url, path):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response, open(path, "wb") as target:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)


def ensure_model():
    model_dir = os.environ.get("U2NET_HOME", os.path.expanduser("~/.u2net"))
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "u2netp.onnx")
    if not os.path.exists(model_path):
        temporary = model_path + ".download"
        download(MODEL_URL, temporary)
        os.replace(temporary, model_path)
    return model_path


def infer_alpha(image):
    """U2NetPを直接実行する。rembg/pymatting/numbaを読み込まずメモリを抑える。"""
    resized = image.resize((320, 320), Image.Resampling.LANCZOS)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
    tensor = ((array - mean) / std).transpose(2, 0, 1)[None, ...]
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(ensure_model(), sess_options=options, providers=["CPUExecutionProvider"])
    prediction = session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]
    minimum, maximum = float(prediction.min()), float(prediction.max())
    if maximum > minimum:
        prediction = (prediction - minimum) / (maximum - minimum)
    alpha = Image.fromarray((prediction * 255).astype(np.uint8), mode="L")
    return alpha.resize(image.size, Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--file")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fillin-cutout-") as tmpdir:
        source_path = args.file
        if args.url:
            source_path = os.path.join(tmpdir, "source-image")
            download(args.url, source_path)
        with Image.open(source_path) as opened:
            # JPEGは原寸展開前にデコーダへ縮小を指示する。高解像度原本でも
            # RGBA/RGBの巨大な複製を作らず、Renderの512MB枠内に収める。
            opened.draft("RGB", (MAX_OUTPUT_EDGE, MAX_OUTPUT_EDGE))
            opened.thumbnail((MAX_OUTPUT_EDGE, MAX_OUTPUT_EDGE), Image.Resampling.LANCZOS, reducing_gap=3.0)
            image = ImageOps.exif_transpose(opened).convert("RGB")
        alpha = infer_alpha(image)
        result = image.convert("RGBA")
        result.putalpha(alpha)
        result = clean_alpha(result)
        temporary_output = args.output + ".tmp.png"
        result.save(temporary_output, format="PNG", optimize=True)
        os.replace(temporary_output, args.output)


if __name__ == "__main__":
    main()
