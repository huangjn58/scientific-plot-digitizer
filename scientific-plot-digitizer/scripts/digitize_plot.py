#!/usr/bin/env python3
"""Digitize simple scientific XY plot images after axis calibration."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError("Color must be #RRGGBB.")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))


def parse_roi(text: str | None) -> list[int] | None:
    if not text:
        return None
    parts = [int(float(p.strip())) for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("--roi must be left,top,right,bottom")
    return parts


def load_calibration(path: Path, roi_override: list[int] | None) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        cal = json.load(f)
    for key in ("x1", "x2", "y1", "y2"):
        if key not in cal or "pixel" not in cal[key] or "value" not in cal[key]:
            raise ValueError(f"Calibration is missing {key}.pixel or {key}.value")
    cal["x_scale"] = cal.get("x_scale", "linear")
    cal["y_scale"] = cal.get("y_scale", "linear")
    if roi_override is not None:
        cal["roi"] = roi_override
    return cal


def transform_axis(pixel: float, p1: float, v1: float, p2: float, v2: float, scale: str) -> float:
    if p1 == p2:
        raise ValueError("Calibration pixel coordinates must not be identical.")
    t = (pixel - p1) / (p2 - p1)
    if scale == "linear":
        return v1 + t * (v2 - v1)
    if scale == "log10":
        if v1 <= 0 or v2 <= 0:
            raise ValueError("Log10 calibration values must be positive.")
        lv1 = math.log10(v1)
        lv2 = math.log10(v2)
        return 10 ** (lv1 + t * (lv2 - lv1))
    raise ValueError(f"Unsupported scale: {scale}")


def pixel_to_data(x: float, y: float, cal: dict[str, Any]) -> tuple[float, float]:
    x1p = cal["x1"]["pixel"][0]
    x2p = cal["x2"]["pixel"][0]
    y1p = cal["y1"]["pixel"][1]
    y2p = cal["y2"]["pixel"][1]
    xv = transform_axis(x, x1p, float(cal["x1"]["value"]), x2p, float(cal["x2"]["value"]), cal["x_scale"])
    yv = transform_axis(y, y1p, float(cal["y1"]["value"]), y2p, float(cal["y2"]["value"]), cal["y_scale"])
    return xv, yv


def build_mask(rgb: np.ndarray, args: argparse.Namespace) -> np.ndarray:
    if args.mode == "color":
        target = np.array(parse_hex_color(args.target), dtype=np.int32)
        diff = rgb.astype(np.int32) - target
        return np.sqrt(np.sum(diff * diff, axis=2)) <= args.tolerance
    if args.mode == "dark":
        return np.max(rgb, axis=2) <= args.threshold
    if args.mode == "non-white":
        return np.min(255 - rgb, axis=2) >= args.threshold
    raise ValueError(f"Unsupported mode: {args.mode}")


def group_line(mask: np.ndarray, left: int, top: int, cal: dict[str, Any], stat: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return rows
    for local_x in sorted(set(xs.tolist())):
        column_y = ys[xs == local_x]
        if stat == "median":
            local_y = float(np.median(column_y))
        elif stat == "mean":
            local_y = float(np.mean(column_y))
        elif stat == "min":
            local_y = float(np.min(column_y))
        elif stat == "max":
            local_y = float(np.max(column_y))
        else:
            raise ValueError(f"Unsupported line stat: {stat}")
        px = float(left + local_x)
        py = float(top + local_y)
        xval, yval = pixel_to_data(px, py, cal)
        rows.append({"x": xval, "y": yval, "pixel_x": px, "pixel_y": py})
    return rows


def connected_components(mask: np.ndarray, min_area: int) -> list[dict[str, float]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[dict[str, float]] = []
    neighbors = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            visited[y, x] = True
            coords: list[tuple[int, int]] = []
            while q:
                cx, cy = q.popleft()
                coords.append((cx, cy))
                for dx, dy in neighbors:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        q.append((nx, ny))
            if len(coords) < min_area:
                continue
            arr = np.array(coords, dtype=float)
            components.append(
                {
                    "area": float(len(coords)),
                    "cx": float(np.mean(arr[:, 0])),
                    "cy": float(np.mean(arr[:, 1])),
                    "min_x": float(np.min(arr[:, 0])),
                    "max_x": float(np.max(arr[:, 0])),
                    "min_y": float(np.min(arr[:, 1])),
                    "max_y": float(np.max(arr[:, 1])),
                }
            )
    components.sort(key=lambda c: (c["cx"], c["cy"]))
    return components


def group_scatter(mask: np.ndarray, left: int, top: int, cal: dict[str, Any], min_area: int) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for idx, comp in enumerate(connected_components(mask, min_area), start=1):
        px = left + comp["cx"]
        py = top + comp["cy"]
        xval, yval = pixel_to_data(px, py, cal)
        rows.append(
            {
                "id": float(idx),
                "x": xval,
                "y": yval,
                "pixel_x": px,
                "pixel_y": py,
                "area_px": comp["area"],
            }
        )
    return rows


def group_bars(mask: np.ndarray, left: int, top: int, cal: dict[str, Any], min_area: int) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    baseline_y = float(cal["y1"]["pixel"][1])
    for idx, comp in enumerate(connected_components(mask, min_area), start=1):
        px = left + (comp["min_x"] + comp["max_x"]) / 2.0
        top_px = top + comp["min_y"]
        bottom_px = top + comp["max_y"]
        xval, y_top = pixel_to_data(px, top_px, cal)
        _, y_bottom = pixel_to_data(px, bottom_px, cal)
        _, y_base = pixel_to_data(px, baseline_y, cal)
        rows.append(
            {
                "id": float(idx),
                "x": xval,
                "y_top": y_top,
                "y_bottom": y_bottom,
                "height_from_baseline": y_top - y_base,
                "pixel_x": px,
                "pixel_y_top": top_px,
                "pixel_y_bottom": bottom_px,
                "area_px": comp["area"],
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_excel(path: Path, rows: list[dict[str, float]]) -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Excel export requires pandas and openpyxl.") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(path, index=False)


def draw_overlay(image: Image.Image, mask: np.ndarray, rows: list[dict[str, float]], roi: list[int], path: Path) -> None:
    overlay = image.convert("RGBA")
    left, top, _, _ = roi
    color_layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    mask_image = Image.fromarray((mask.astype(np.uint8) * 150), mode="L")
    red = Image.new("RGBA", mask_image.size, (255, 0, 0, 120))
    color_layer.paste(red, (left, top), mask_image)
    overlay = Image.alpha_composite(overlay, color_layer)
    draw = ImageDraw.Draw(overlay)
    for row in rows:
        px = row.get("pixel_x")
        py = row.get("pixel_y", row.get("pixel_y_top"))
        if px is None or py is None:
            continue
        draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(0, 220, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    overlay.convert("RGB").save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Digitize simple scientific XY plot images.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--calibration", required=True, type=Path, help="Calibration JSON path.")
    parser.add_argument("--output", required=True, type=Path, help="CSV output path.")
    parser.add_argument("--excel", type=Path, help="Optional Excel output path.")
    parser.add_argument("--overlay", type=Path, help="Optional QA overlay image path.")
    parser.add_argument("--metadata", type=Path, help="Optional extraction metadata JSON path.")
    parser.add_argument("--roi", help="Override ROI as left,top,right,bottom.")
    parser.add_argument("--mode", choices=["color", "dark", "non-white"], default="color")
    parser.add_argument("--target", default="#d62728", help="Target color for --mode color.")
    parser.add_argument("--tolerance", type=float, default=35.0, help="RGB Euclidean color tolerance.")
    parser.add_argument("--threshold", type=int, default=90, help="Threshold for dark/non-white modes.")
    parser.add_argument("--trace", choices=["line", "scatter", "bars"], default="line")
    parser.add_argument("--line-stat", choices=["median", "mean", "min", "max"], default="median")
    parser.add_argument("--min-area", type=int, default=8, help="Minimum connected-component area.")
    args = parser.parse_args()

    cal = load_calibration(args.calibration, parse_roi(args.roi))
    image = Image.open(args.image).convert("RGB")
    width, height = image.size
    roi = cal.get("roi", [0, 0, width, height])
    if len(roi) != 4:
        raise ValueError("ROI must be [left, top, right, bottom].")
    left, top, right, bottom = [int(v) for v in roi]
    left, top = max(0, left), max(0, top)
    right, bottom = min(width, right), min(height, bottom)
    if left >= right or top >= bottom:
        raise ValueError("Invalid ROI after clipping to image bounds.")
    roi = [left, top, right, bottom]

    crop = np.array(image.crop((left, top, right, bottom)))
    mask = build_mask(crop, args)
    if args.trace == "line":
        rows = group_line(mask, left, top, cal, args.line_stat)
    elif args.trace == "scatter":
        rows = group_scatter(mask, left, top, cal, args.min_area)
    else:
        rows = group_bars(mask, left, top, cal, args.min_area)

    write_csv(args.output, rows)
    if args.excel:
        write_excel(args.excel, rows)
    if args.overlay:
        draw_overlay(image, mask, rows, roi, args.overlay)
    if args.metadata:
        meta = {
            "image": str(args.image),
            "output": str(args.output),
            "rows": len(rows),
            "mode": args.mode,
            "trace": args.trace,
            "roi": roi,
            "calibration": cal,
            "notes": "Digitized values are estimates derived from raster image pixels.",
        }
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
