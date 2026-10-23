#!/usr/bin/env python3
"""Cắt ảnh GUI thật theo crops.json và thêm chú thích; không vẽ lại dữ liệu đo."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]


def render(raw_dir, output_dir):
    spec = json.loads((ROOT / 'docs/images/crops.json').read_text(encoding='utf-8'))
    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = font_manager.findfont('DejaVu Sans')
    title_font = ImageFont.truetype(font_path, 38)
    caption_font = ImageFont.truetype(font_path, 27)
    footer_font = ImageFont.truetype(font_path, 21)
    records = []
    for shot in spec['screenshots']:
        raw = raw_dir / shot['raw_file']
        with Image.open(raw) as original:
            bounds = shot['crop_xyxy']
            if not (0 <= bounds[0] < bounds[2] <= original.width and
                    0 <= bounds[1] < bounds[3] <= original.height):
                raise ValueError('Vùng cắt vượt ảnh: ' + raw.name)
            region = original.convert('RGB').crop(bounds)
            size = list(original.size)
        header, footer = 122, 44
        result = Image.new('RGB', (region.width, region.height + header + footer), '#eef4fa')
        result.paste(region, (0, header))
        draw = ImageDraw.Draw(result)
        for text, y, font in [(shot['title'], 15, title_font),
                              (shot['caption'], 72, caption_font)]:
            if draw.textlength(text, font=font) > region.width - 48:
                raise ValueError('Chú thích quá dài: ' + raw.name)
            draw.text((24, y), text, font=font, fill='#16354d')
        draw.text((24, result.height - 33),
                  'Ảnh GUI thật · Copyright © 2026 HALA Academy · MIT',
                  font=footer_font, fill='#16354d')
        target = output_dir / shot['image']
        result.save(target, optimize=True)
        capture = ROOT / shot['capture']
        metadata = json.loads(capture.read_text(encoding='utf-8'))
        raw_capture = capture.with_suffix('.bin')
        capture_hash = hashlib.sha256(raw_capture.read_bytes()).hexdigest()
        if capture_hash != metadata['raw_sha256']:
            raise ValueError('Capture sai SHA256: ' + str(capture))
        records.append({**shot, 'raw_size': size,
                        'raw_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
                        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                        'size': list(result.size), 'capture_sha256': capture_hash})
    report = {
        'date': '2026-10-23', 'platform': 'macOS Apple Silicon; Python 3.14.6/Tk',
        'method': 'CUA native window screenshot; exact pixel crop; added captions outside crop; no waveform or UI text redrawn',
        'raw_storage': 'Development review archive outside public repository; raw hashes retained here',
        'gui_sha256': hashlib.sha256((ROOT/'host/gui.py').read_bytes()).hexdigest(),
        'screenshots': records,
    }
    (output_dir / 'provenance.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Đã xuất {len(records)} ảnh PNG có provenance vào {output_dir}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', required=True, type=Path, help='Thư mục ảnh gốc do CUA chụp')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/images', help='Thư mục ảnh xuất')
    args = parser.parse_args()
    render(args.raw_dir, args.output)
