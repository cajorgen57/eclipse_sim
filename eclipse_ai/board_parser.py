from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import os, json, math

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # OpenCV optional
    cv2 = None  # type: ignore
    np = None   # type: ignore

from .game_models import MapState, Hex, Planet, Pieces

# ============================================================
# Config
# ============================================================

@dataclass
class BoardParseConfig:
    # Player color ranges in HSV for discs/cubes/ships. Tunable.
    hsv_ranges: Dict[str, Tuple[Tuple[int,int,int], Tuple[int,int,int]]] = field(default_factory=lambda: {
        # lower HSV, upper HSV
        "orange": ((5,  80, 60),  (25, 255, 255)),
        "blue":   ((90, 60, 60),  (130,255, 255)),
        "green":  ((40, 60, 60),  (85, 255, 255)),
        "purple": ((130,60, 60),  (160,255, 255)),
        "red1":   ((0,  80, 60),  (5,  255, 255)),
        "red2":   ((170,80, 60),  (180,255, 255)),
        "yellow": ((25, 80, 60),  (35, 255, 255)),
        "black":  ((0,   0,  0),  (180, 255, 50)),
        "white":  ((0,   0,180),  (180, 50, 255)),
    })
    # How many hex rings to project if grid hint missing
    default_rings: int = 2
    # Minimum contour area to consider as token
    min_token_area: int = 80
    # Use sidecar if present
    prefer_sidecar: bool = True

@dataclass
class GridHint:
    # Axial grid hint using pixel vectors
    origin: Tuple[float,float] = (0.0, 0.0)   # pixel coords for axial (q=0,r=0)
    q_vec: Tuple[float,float] = (80.0, 0.0)   # pixel delta for +q
    r_vec: Tuple[float,float] = (40.0, 70.0)  # pixel delta for +r
    rings: int = 2

# ============================================================
# Public API
# ============================================================

def parse_board(cal_img, config: Optional[BoardParseConfig]=None) -> MapState:
    """
    Board parser with three modes:
      1) Sidecar annotations (robust): <image_path>.annotations.json
      2) CV-assisted token detection if OpenCV available + optional grid hint in cal_img.metadata['grid_hint']
      3) Fallback: small demo map (keeps pipeline alive)

    Sidecar schema (preferred):
    {
      "hexes": [
        {
          "id": "H-010",
          "ring": 2,
          "wormholes": [0,2,4],
          "planets": [{"type":"yellow","colonized_by":"you"},{"type":"blue","colonized_by":null}],
          "pieces": [
            {"owner":"you","ships":{"interceptor":2},"starbase":0,"discs":1,"cubes":{"y":1,"b":0,"p":0}},
            {"owner":"blue","ships":{"cruiser":2},"discs":1}
          ]
        }
      ]
    }
    """
    cfg = config or BoardParseConfig()
    # 1) Sidecar
    if cfg.prefer_sidecar:
        data = _load_sidecar(cal_img.path)
        if data:
            return _mapstate_from_annotations(data)

    # 2) CV flow
    if cv2 is not None and np is not None:
        try:
            img = cv2.imread(cal_img.path, cv2.IMREAD_COLOR)
            if img is not None:
                grid = _grid_from_meta(cal_img.metadata) or _guess_grid(img.shape, cfg.default_rings)
                tokens = _detect_tokens(img, cfg)
                hex_centers, hex_ids, rings = _project_hex_centers(grid)
                hex_map: Dict[str, Hex] = {}
                # Initialize hexes
                for hid, (cx, cy), ring in zip(hex_ids, hex_centers, rings):
                    hex_map[hid] = Hex(id=hid, ring=ring, wormholes=[], planets=[], pieces={})
                # Assign tokens to nearest hex center
                for t in tokens:
                    hid = _nearest_hex_id((t["cx"], t["cy"]), hex_centers, hex_ids)
                    if hid is None:
                        continue
                    owner = t["owner"]
                    hx = hex_map[hid]
                    if owner not in hx.pieces:
                        hx.pieces[owner] = Pieces(ships={}, starbase=0, discs=0, cubes={})
                    p = hx.pieces[owner]
                    if t["kind"] == "disc":
                        p.discs += 1
                    elif t["kind"] == "cube":
                        # Heuristic: map cube color to resource initial; here we store generic
                        ckey = t.get("res_key","y")
                        p.cubes[ckey] = p.cubes.get(ckey, 0) + 1
                    elif t["kind"] == "ship":
                        cls = t.get("cls","interceptor")
                        p.ships[cls] = p.ships.get(cls, 0) + 1
                    elif t["kind"] == "starbase":
                        p.starbase += 1
                # Remove empty hexes
                hex_map = {k:v for k,v in hex_map.items() if v.pieces}
                if hex_map:
                    return MapState(hexes=hex_map)
        except Exception:
            pass

    # 3) Fallback demo
    hexes: Dict[str, Hex] = {}
    h = Hex(id="H-010", ring=2, wormholes=[0,2,4], planets=[Planet("yellow","you"), Planet("blue", None)])
    h.pieces["you"] = Pieces(ships={"interceptor":2}, discs=1, cubes={"y":1})
    h.pieces["blue"] = Pieces(ships={"cruiser":2}, discs=1)
    hexes[h.id] = h
    return MapState(hexes=hexes)

# ============================================================
# Sidecar annotations
# ============================================================

def _sidecar_path(image_path: str) -> Optional[str]:
    base = image_path
    if not os.path.exists(base):
        return None
    cand = base + ".annotations.json"
    return cand if os.path.exists(cand) else None

def _load_sidecar(image_path: str) -> Optional[Dict[str, Any]]:
    p = _sidecar_path(image_path)
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _mapstate_from_annotations(data: Dict[str, Any]) -> MapState:
    hex_map: Dict[str, Hex] = {}
    for hx in data.get("hexes", []):
        h = Hex(
            id=str(hx.get("id","H-000")),
            ring=int(hx.get("ring", 0)),
            wormholes=list(hx.get("wormholes", [])),
            planets=[Planet(p.get("type","yellow"), p.get("colonized_by")) for p in hx.get("planets", [])],
            pieces={}
        )
        for p in hx.get("pieces", []):
            owner = str(p.get("owner","unknown"))
            pieces = Pieces(
                ships=dict(p.get("ships", {})),
                starbase=int(p.get("starbase", 0)),
                discs=int(p.get("discs", 0)),
                cubes=dict(p.get("cubes", {})),
                discovery=int(p.get("discovery", 0)),
            )
            h.pieces[owner] = pieces
        hex_map[h.id] = h
    return MapState(hexes=hex_map)

# ============================================================
# Grid helpers
# ============================================================

def _grid_from_meta(meta: Dict[str, Any]) -> Optional[GridHint]:
    gh = meta.get("grid_hint") if isinstance(meta, dict) else None
    if not gh:
        return None
    try:
        origin = tuple(gh.get("origin", (0.0,0.0)))
        q_vec = tuple(gh.get("q_vec", (80.0,0.0)))
        r_vec = tuple(gh.get("r_vec", (40.0,70.0)))
        rings = int(gh.get("rings", 2))
        return GridHint(origin=origin, q_vec=q_vec, r_vec=r_vec, rings=rings)
    except Exception:
        return None

def _guess_grid(shape, rings: int) -> GridHint:
    h, w = shape[:2]
    # Rough guess: center the grid; set vectors based on image width
    scale = max(40.0, min(w, h) / 10.0)
    origin = (w/2.0, h/2.0)
    q_vec = (scale, 0.0)
    r_vec = (scale*0.5, scale*0.866)  # 60 degrees
    return GridHint(origin=origin, q_vec=q_vec, r_vec=r_vec, rings=rings)

def _project_hex_centers(grid: GridHint) -> Tuple[List[Tuple[float,float]], List[str], List[int]]:
    centers: List[Tuple[float,float]] = []
    ids: List[str] = []
    rings: List[int] = []
    # Axial coords within N rings
    N = grid.rings
    idx = 0
    for q in range(-N, N+1):
        r1 = max(-N, -q-N)
        r2 = min(N, -q+N)
        for r in range(r1, r2+1):
            x = grid.origin[0] + q*grid.q_vec[0] + r*grid.r_vec[0]
            y = grid.origin[1] + q*grid.q_vec[1] + r*grid.r_vec[1]
            centers.append((x, y))
            ids.append(f"H-{idx:03d}")
            rings.append(max(abs(q), abs(r), abs(-q-r)))
            idx += 1
    return centers, ids, rings

def _nearest_hex_id(pt: Tuple[float,float], centers: List[Tuple[float,float]], ids: List[str]) -> Optional[str]:
    if not centers:
        return None
    px, py = pt
    best_d2 = 1e18
    best_id = None
    for (cx, cy), hid in zip(centers, ids):
        d2 = (px - cx)**2 + (py - cy)**2
        if d2 < best_d2:
            best_d2 = d2
            best_id = hid
    return best_id

# ============================================================
# CV token detection
# ============================================================

def _detect_tokens(img, cfg: BoardParseConfig) -> List[Dict[str, Any]]:
    """
    Detect colored tokens using HSV thresholds + contour analysis.
    Returns a list of dicts: {"owner":<color_name>,"kind":"disc|cube|ship|starbase","cx":float,"cy":float,"cls":optional}
    """
    tokens: List[Dict[str, Any]] = []
    if cv2 is None or np is None:
        return tokens
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Build masks per color; red requires two ranges (red1, red2)
    color_masks: Dict[str, Any] = {}
    for name, (lo, hi) in cfg.hsv_ranges.items():
        lo_np = np.array(lo, dtype=np.uint8)
        hi_np = np.array(hi, dtype=np.uint8)
        mask = cv2.inRange(hsv, lo_np, hi_np)
        if name == "red2":
            # Merge with red1
            prev = color_masks.get("red1")
            color_masks["red"] = cv2.bitwise_or(prev, mask) if prev is not None else mask
        elif name != "red1":
            color_masks[name] = mask

    # For each color, find contours and classify rough shape
    for color_name, mask in color_masks.items():
        if mask is None:
            continue
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            if area < cfg.min_token_area:
                continue
            x,y,w,h = cv2.boundingRect(c)
            cx, cy = x + w/2.0, y + h/2.0
            # circularity to separate discs vs cubes
            perim = cv2.arcLength(c, True)
            circ = 0.0 if perim <= 0 else 4*math.pi*area/(perim*perim)
            aspect = w/float(h) if h>0 else 1.0
            kind = "ship"
            if 0.70 <= circ <= 1.25 and 0.8 <= aspect <= 1.25:
                kind = "disc"
            elif 0.3 <= circ < 0.7 and 0.85 <= aspect <= 1.35:
                kind = "cube"
            # Heuristic: very large circular-ish -> starbase
            if kind == "disc" and area > 6_000:
                kind = "starbase"

            tokens.append({"owner": color_name, "kind": kind, "cx": cx, "cy": cy})
    return tokens

