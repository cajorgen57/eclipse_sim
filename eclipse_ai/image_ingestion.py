from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
import os

# Optional deps
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None   # type: ignore

try:
    from PIL import Image, ExifTags  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ExifTags = None  # type: ignore

@dataclass
class CalibratedImage:
    path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CalibrationConfig:
    save_rectified: bool = True
    save_suffix: str = ".rectified.png"
    rings_guess: int = 3  # for grid_hint estimation
    use_aruco: bool = True
    aruco_dict: str = "DICT_4X4_50"  # used if OpenCV contrib available
    # Lighting normalization
    normalize_lighting: bool = True
    # White balance: simple gray-world gain
    white_balance: bool = True

def load_and_calibrate(image_path: str, fiducials: Optional[List[Tuple[float, float]]]=None, config: Optional[CalibrationConfig]=None) -> CalibratedImage:
    """
    Load an image, correct EXIF orientation, optionally normalize lighting and color,
    and rectify perspective using provided fiducials or detected board corners.
    Returns a CalibratedImage with metadata including a 'grid_hint' for hex projection.

    Parameters
    ----------
    image_path: str
        Path to the board photo.
    fiducials: list of (x,y)
        Optional four corner points in pixels. Any order; will be sorted to TL, TR, BR, BL.
    config: CalibrationConfig
        Tuning switches. Defaults are conservative.

    Metadata Keys
    -------------
    - rectified: bool
    - rectification_method: "fiducials"|"aruco"|"contour"|"none"
    - homography: 3x3 list (if rectified)
    - size: (height,width)
    - lighting_normalized: bool
    - white_balance: bool
    - grid_hint: {"origin":(x,y),"q_vec":(dx,dy),"r_vec":(dx,dy),"rings":int}
    - warnings: [str]
    """
    cfg = config or CalibrationConfig()
    meta: Dict[str, Any] = {
        "rectified": False,
        "rectification_method": "none",
        "lighting_normalized": False,
        "white_balance": False,
        "homography": None,
        "size": None,
        "grid_hint": None,
        "warnings": [],
        "notes": "",
    }

    # Fast path: if OpenCV missing, return stub with size from PIL if available
    if cv2 is None or np is None:
        meta["notes"] = "OpenCV not available; returning unmodified image."
        if Image is not None:
            try:
                with Image.open(image_path) as im:
                    meta["size"] = (im.height, im.width)
            except Exception:
                pass
        meta["grid_hint"] = _guess_grid_hint(meta.get("size"), cfg.rings_guess)
        return CalibratedImage(path=image_path, metadata=meta)

    # Read with EXIF orientation fix if possible
    img = _read_image_exif_corrected(image_path)
    if img is None:
        meta["warnings"].append("Failed to read image; returning stub.")
        return CalibratedImage(path=image_path, metadata=meta)

    meta["size"] = (img.shape[0], img.shape[1])

    # White balance
    if cfg.white_balance:
        img, gains = _gray_world_white_balance(img)
        meta["white_balance"] = True
        meta["wb_gains"] = gains

    # Lighting normalization
    if cfg.normalize_lighting:
        img = _clahe_normalize(img)
        meta["lighting_normalized"] = True

    # Rectification
    rectified_img = None
    H = None
    if fiducials and len(fiducials) >= 4:
        corners = _order_corners(np.array(fiducials, dtype=np.float32))
        rectified_img, H = _warp_to_rect(img, corners)
        meta["rectified"] = True
        meta["rectification_method"] = "fiducials"
    elif cfg.use_aruco and _aruco_available():
        try:
            detected = _detect_aruco_board_corners(img, cfg.aruco_dict)
            if detected is not None:
                corners = _order_corners(detected)
                rectified_img, H = _warp_to_rect(img, corners)
                meta["rectified"] = True
                meta["rectification_method"] = "aruco"
        except Exception as e:  # pragma: no cover
            meta["warnings"].append(f"ArUco detection failed: {e}")
    if rectified_img is None:
        # Fallback: find largest quadrilateral contour
        quad = _largest_quad_contour(img)
        if quad is not None:
            corners = _order_corners(quad)
            rectified_img, H = _warp_to_rect(img, corners)
            meta["rectified"] = True
            meta["rectification_method"] = "contour"

    # Save rectified image if produced
    out_path = image_path
    if rectified_img is not None and cfg.save_rectified:
        base, ext = os.path.splitext(image_path)
        out_path = base + cfg.save_suffix
        cv2.imwrite(out_path, rectified_img)
        img = rectified_img  # downstream size uses rectified
        meta["size"] = (img.shape[0], img.shape[1])

    # Homography metadata
    if H is not None:
        meta["homography"] = H.tolist()

    # Grid hint estimation
    meta["grid_hint"] = _guess_grid_hint(meta["size"], cfg.rings_guess)

    return CalibratedImage(path=out_path, metadata=meta)

# ------------------------
# Helpers
# ------------------------

def _read_image_exif_corrected(path: str):
    """Read image and correct EXIF orientation if PIL available."""
    if Image is None:
        return cv2.imread(path, cv2.IMREAD_COLOR)
    try:
        with Image.open(path) as im:
            try:
                exif = im._getexif()
                if exif and ExifTags:
                    orientation_key = next((k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None)
                    if orientation_key and orientation_key in exif:
                        o = exif[orientation_key]
                        if o == 3:
                            im = im.rotate(180, expand=True)
                        elif o == 6:
                            im = im.rotate(270, expand=True)
                        elif o == 8:
                            im = im.rotate(90, expand=True)
            except Exception:
                pass
            # Convert to BGR for OpenCV
            im = im.convert('RGB')
            arr = np.array(im)[:, :, ::-1].copy()
            return arr
    except Exception:
        # Fallback to OpenCV read
        return cv2.imread(path, cv2.IMREAD_COLOR)

def _gray_world_white_balance(img):
    """Simple gray-world white balance. Returns corrected image and gains."""
    eps = 1e-6
    b, g, r = cv2.split(img)
    mb, mg, mr = float(b.mean()), float(g.mean()), float(r.mean())
    avg = (mb + mg + mr) / 3.0 + eps
    gb, gg, gr = avg / (mb + eps), avg / (mg + eps), avg / (mr + eps)
    b = cv2.multiply(b, gb)
    g = cv2.multiply(g, gg)
    r = cv2.multiply(r, gr)
    out = cv2.merge([np.clip(b,0,255).astype(np.uint8),
                     np.clip(g,0,255).astype(np.uint8),
                     np.clip(r,0,255).astype(np.uint8)])
    return out, (gb, gg, gr)

def _clahe_normalize(img):
    """Apply CLAHE to L channel in LAB space for local contrast normalization."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l2 = clahe.apply(l)
    lab2 = cv2.merge([l2, a, b])
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)

def _order_corners(pts: 'np.ndarray') -> 'np.ndarray':
    """Return 4x2 array ordered TL, TR, BR, BL from arbitrary four-point set."""
    if pts.shape[0] > 4:
        # take convex hull then choose 4 extreme points
        hull = cv2.convexHull(pts.reshape(-1,1,2))
        pts = hull.reshape(-1,2)
    # If still >4, select by k-means or extreme sums; here: extreme sums
    if pts.shape[0] != 4:
        sums = pts.sum(axis=1)
        diffs = (pts[:,0] - pts[:,1])
        tl = pts[np.argmin(sums)]
        br = pts[np.argmax(sums)]
        tr = pts[np.argmin(diffs)]
        bl = pts[np.argmax(diffs)]
        return np.array([tl, tr, br, bl], dtype=np.float32)
    # classic ordering
    s = pts.sum(axis=1)
    diff = (pts[:,0] - pts[:,1])
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

def _warp_to_rect(img, corners: 'np.ndarray'):
    """Perspective warp so that the quad maps to a rectangle with aspect proportional to input quad."""
    # compute width and height from distances
    (tl, tr, br, bl) = corners
    def d(a,b): return np.linalg.norm(a-b)
    width = int(max(d(tr, tl), d(br, bl)))
    height = int(max(d(bl, tl), d(br, tr)))
    width = max(1, width)
    height = max(1, height)
    dst = np.array([[0,0],[width-1,0],[width-1,height-1],[0,height-1]], dtype=np.float32)
    H = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    rectified = cv2.warpPerspective(img, H, (width, height), flags=cv2.INTER_LINEAR)
    return rectified, H

def _aruco_available() -> bool:
    return cv2 is not None and hasattr(cv2, "aruco")

def _detect_aruco_board_corners(img, dict_name: str = "DICT_4X4_50"):
    """Detect ArUco markers and infer outer quad from extreme marker corners if four corners exist."""
    if not _aruco_available():
        return None
    adict = getattr(cv2.aruco, dict_name, None)
    if adict is None:
        adict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(adict, cv2.aruco.DetectorParameters())
    corners, ids, _rej = detector.detectMarkers(img)
    if ids is None or len(corners) < 1:
        return None
    # Collect all corners and take convex hull
    pts = np.concatenate([c.reshape(-1,2) for c in corners], axis=0).astype(np.float32)
    hull = cv2.convexHull(pts.reshape(-1,1,2)).reshape(-1,2)
    # Approximate hull to 4-point polygon
    peri = cv2.arcLength(hull.reshape(-1,1,2), True)
    approx = cv2.approxPolyDP(hull.reshape(-1,1,2), 0.02*peri, True).reshape(-1,2)
    if approx.shape[0] >= 4:
        return approx[:4].astype(np.float32)
    return hull[:4].astype(np.float32) if hull.shape[0] >= 4 else None

def _largest_quad_contour(img):
    """Find largest quadrilateral contour using Canny + contour approximation."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edges = cv2.Canny(blur, 50, 150)
    # Dilate to close gaps
    kernel = np.ones((3,3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 10000:  # ignore tiny contours
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02*peri, True)
        if len(approx) == 4 and area > best_area:
            best = approx.reshape(-1,2)
            best_area = area
    return best

def _guess_grid_hint(size: Optional[Tuple[int,int]], rings: int) -> Dict[str, Any]:
    """Estimate a hex axial grid hint compatible with board_parser._grid_from_meta."""
    if not size:
        return {"origin": (0.0, 0.0), "q_vec": (80.0, 0.0), "r_vec": (40.0, 70.0), "rings": rings}
    h, w = size
    scale = max(40.0, min(w, h) / 10.0)
    origin = (w/2.0, h/2.0)
    q_vec = (scale, 0.0)
    r_vec = (scale*0.5, scale*0.866)  # 60 degrees
    return {"origin": origin, "q_vec": q_vec, "r_vec": r_vec, "rings": rings}
