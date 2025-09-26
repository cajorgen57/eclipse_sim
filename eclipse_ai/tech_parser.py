
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import os, json, re

from .game_models import TechDisplay

# Optional deps
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None   # type: ignore

try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore

# ==================================
# Config
# ==================================

@dataclass
class TechParseConfig:
    prefer_sidecar: bool = True
    enable_ocr: bool = True
    min_area: int = 2_000
    max_area_ratio: float = 0.2      # ignore huge rectangles
    rect_eps: float = 0.02           # approxPolyDP epsilon factor
    dedupe_similarity: float = 0.80  # Jaccard similarity to dedupe OCR strings
    # Fallback known tech tokens for normalization (subset; extend as needed)
    known_tokens: List[str] = field(default_factory=lambda: [
        "PLASMA CANNON", "POSITRON COMPUTER", "FUSION DRIVE", "GAUSS SHIELD",
        "ION CANNON", "ANTIMATTER CANNON", "ADVANCED MINING", "ADVANCED LABS",
        "WORMHOLE GENERATOR", "NANOROBOTS", "PHASE SHIELD", "IMPROVED HULL",
        "ELECTRONIC COUNTERMEASURES", "GLUON COMPUTER", "PLASMA MISSILES",
    ])

# ==================================
# Public API
# ==================================

def parse_tech(cal_img, config: Optional[TechParseConfig]=None) -> TechDisplay:
    """
    Parse the public tech display.
    Priority:
      1) Sidecar JSON: <image>.tech.json or <image>.annotations.json["tech_display"]
      2) OCR over detected rectangular tech tiles (OpenCV + pytesseract)
      3) Fallback minimal stub
    """
    cfg = config or TechParseConfig()

    # 1) Sidecar
    if cfg.prefer_sidecar:
        side = _load_sidecar(cal_img.path)
        if side:
            return _from_sidecar(side)

    # 2) OCR if possible
    if cfg.enable_ocr and cv2 is not None and np is not None and pytesseract is not None:
        try:
            img = cv2.imread(cal_img.path, cv2.IMREAD_COLOR)
            if img is not None:
                tiles = _detect_tile_rects(img, cfg)
                texts = _ocr_tiles(img, tiles)
                cleaned = _normalize_texts(texts, cfg.known_tokens)
                tiers = _infer_tiers_from_positions(tiles, img.shape[:2], cleaned)
                available = sorted(cleaned)
                return TechDisplay(available=available, tier_counts=tiers)
        except Exception:
            pass

    # 3) Fallback
    return TechDisplay(available=["Plasma Cannon","Fusion Drive","Positron Computer"], tier_counts={"I":6,"II":5,"III":4})

# ==================================
# Sidecar
# ==================================

def _sidecar_paths(img_path: str) -> List[str]:
    cands = [img_path + ".tech.json", img_path + ".annotations.json"]
    return [p for p in cands if os.path.exists(p)]

def _load_sidecar(img_path: str) -> Optional[Dict[str, Any]]:
    for p in _sidecar_paths(img_path):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            # If it's an annotations blob, extract subkey
            if p.endswith(".annotations.json") and isinstance(data, dict) and "tech_display" in data:
                return data["tech_display"]
            return data
        except Exception:
            continue
    return None

def _from_sidecar(data: Dict[str, Any]) -> TechDisplay:
    avail = list(data.get("available", []))
    tiers = dict(data.get("tier_counts", {}))
    # Ensure all three tiers exist
    for k in ("I","II","III"):
        tiers.setdefault(k, 0)
    return TechDisplay(available=avail, tier_counts=tiers)

# ==================================
# CV + OCR
# ==================================

def _detect_tile_rects(img, cfg: TechParseConfig) -> List[Tuple[int,int,int,int]]:
    """
    Return list of bounding boxes (x,y,w,h) for likely tech tiles.
    Approach: Canny -> contours -> quadrilateral-ish with reasonable aspect and area.
    """
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    edges = cv2.Canny(blur, 60, 180)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects: List[Tuple[int,int,int,int]] = []
    for c in cnts:
        area = cv2.contourArea(c)
        if area < cfg.min_area or area > cfg.max_area_ratio * (H*W):
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, cfg.rect_eps * peri, True)
        x,y,w,h = cv2.boundingRect(approx)
        aspect = w / float(h) if h>0 else 1.0
        # Tech tiles tend to be rectangular moderately wide
        if 1.2 <= aspect <= 3.5 and h >= 20 and w >= 40:
            rects.append((x,y,w,h))
    # Non-maximum suppression by IoU to dedupe overlapping rects
    rects = _nms(rects, iou_thresh=0.3)
    # Sort top-to-bottom, then left-to-right
    rects.sort(key=lambda r: (r[1], r[0]))
    return rects[:24]  # cap

def _nms(rects: List[Tuple[int,int,int,int]], iou_thresh: float=0.3) -> List[Tuple[int,int,int,int]]:
    out: List[Tuple[int,int,int,int]] = []
    for r in sorted(rects, key=lambda r: r[2]*r[3], reverse=True):
        keep = True
        for q in out:
            if _iou(r, q) > iou_thresh:
                keep = False
                break
        if keep:
            out.append(r)
    return out

def _iou(a, b) -> float:
    ax,ay,aw,ah = a
    bx,by,bw,bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax+aw, bx+bw), min(ay+ah, by+bh)
    iw, ih = max(0, x2-x1), max(0, y2-y1)
    inter = iw*ih
    union = aw*ah + bw*bh - inter
    return inter/union if union>0 else 0.0

def _ocr_tiles(img, rects: List[Tuple[int,int,int,int]]) -> List[Tuple[str, Tuple[int,int,int,int]]]:
    results: List[Tuple[str, Tuple[int,int,int,int]]] = []
    if pytesseract is None:
        return results
    for (x,y,w,h) in rects:
        roi = img[y:y+h, x:x+w]
        # preprocess for OCR
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # invert if mostly dark background
        if gray.mean() < 100:
            _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        config = "--psm 6 --oem 3 -l eng"
        try:
            txt = pytesseract.image_to_string(th, config=config)
        except Exception:
            txt = ""
        cleaned = _clean_text(txt)
        if cleaned:
            results.append((cleaned, (x,y,w,h)))
    return results

def _clean_text(t: str) -> str:
    t = t.upper()
    t = re.sub(r'[^A-Z ]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def _normalize_texts(texts: List[Tuple[str, Tuple[int,int,int,int]]], known_tokens: List[str]) -> List[str]:
    # Map OCR outputs to known tokens by simple containment or Jaccard similarity; else keep as-is
    out: List[str] = []
    for s, _ in texts:
        best = None
        best_sim = 0.0
        for k in known_tokens:
            sim = _jaccard(_token_set(s), _token_set(k))
            if sim > best_sim:
                best, best_sim = k, sim
        if best and best_sim >= 0.5:
            out.append(_title(best))
        else:
            out.append(_title(s))
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq

def _infer_tiers_from_positions(tiles: List[Tuple[int,int,int,int]], shape: Tuple[int,int], texts: List[str]) -> Dict[str, int]:
    H, W = shape
    # Partition by y-location band thirds: top=I, mid=II, low=III
    counts = {"I":0,"II":0,"III":0}
    for (_, y, _w, h) in tiles[:len(texts)]:
        cy = y + h/2.0
        if cy < H/3.0:
            counts["I"] += 1
        elif cy < 2*H/3.0:
            counts["II"] += 1
        else:
            counts["III"] += 1
    return counts

def _token_set(s: str) -> set:
    return set(_clean_text(s).split())

def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b) or 1
    return inter / union

def _title(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split())
