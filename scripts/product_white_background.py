#!/usr/bin/env python3
"""元画像をトーンカーブで白化した下地に、元画素の商品を重ねる共有CLI。"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

VERSION = 'original-over-white-curve-v1'


def render(original, mask, knee=160, white_point=235):
    if not 0 <= knee < white_point <= 255:
        raise ValueError('0 <= knee < white-point <= 255 を指定してください')
    if mask.size != original.size:
        raise ValueError('マスクと元画像のサイズが異なります。同じ構図・サイズが必要です')
    rgb = np.asarray(original.convert('RGB'), dtype=np.float32)
    # Dark tones remain unchanged; lift the shoulder and clip studio gray to white.
    mapped = np.where(rgb <= knee, rgb,
                      knee + (rgb-knee)*(255-knee)/(white_point-knee))
    base = Image.fromarray(np.rint(np.clip(mapped, 0, 255)).astype('uint8'), 'RGB')
    body = original.convert('RGBA')
    body.putalpha(mask.convert('L'))
    result = Image.alpha_composite(base.convert('RGBA'), body).convert('RGB')
    return base, body, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--mask', type=Path, help='白=商品・黒=背景のL画像、または切り抜きRGBAのアルファ')
    parser.add_argument('--knee', type=float, default=160)
    parser.add_argument('--white-point', type=float, default=235)
    args = parser.parse_args()
    with Image.open(args.source) as opened:
        original = ImageOps.exif_transpose(opened).convert('RGB')
    if args.mask:
        with Image.open(args.mask) as opened:
            oriented = ImageOps.exif_transpose(opened)
            mask = oriented.getchannel('A') if oriented.mode == 'RGBA' else oriented.convert('L')
    else:
        # Reuse the application's U2NetP; no generated/redrawn product pixels.
        from cutout_worker import infer_alpha
        mask = infer_alpha(original)
    base, body, result = render(original, mask, args.knee, args.white_point)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    original.save(args.output_dir/'original.png')
    mask.save(args.output_dir/'mask.png')
    base.save(args.output_dir/'base-white.png')
    body.save(args.output_dir/'product.png')
    result.save(args.output_dir/'white.png')
    metadata = {'version': VERSION, 'source': str(args.source.resolve()),
                'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
                'mask_source': str(args.mask.resolve()) if args.mask else 'U2NetP',
                'knee': args.knee, 'white_point': args.white_point,
                'size': list(original.size), 'curve_points': [[0,0], [args.knee,args.knee], [args.white_point,255], [255,255]],
                'composition': 'original RGB with product alpha over tone-mapped full original'}
    (args.output_dir/'recipe.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    print(args.output_dir/'white.png')


if __name__ == '__main__':
    main()
