from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import random
import re
import math

try:
    # Optional: use combat EV for clearing Ancients if provided
    from .combat import score_combat
except Exception:
    score_combat = None

# =============================
# Public API
# =============================

@dataclass
class ExplorationEV:
    expected_value_vp: float
    notes: str

def exploration_ev(query: Dict[str, Any]) -> ExplorationEV:
    """
    Robust Monte Carlo exploration EV.
    Inputs (all optional except 'bag'):
      query = {
        "ring": 2,
        "bag": {"ancient":3, "monolith":1, "money2":4, "science2":4, "materials2":4},
        # How many tiles you draw and choose 1 from
        "draws": 1,                     # default 1 (set 2 or 3 if tech allows)
        "n_sims": 5000,
        "seed": 123,
        # Placement feasibility
        "p_connect_default": 0.70,      # chance drawn tile connects on the chosen edge (no WH Generator)
        "p_connect_by_category": {},    # overrides per category
        "wormhole_generator": False,    # if True, connection is guaranteed
        "discs_available": 1,           # if 0 and require_disc_to_claim=True, no immediate colonization EV
        "require_disc_to_claim": True,
        # Colonization capability
        "colony_ships": {"yellow": 1, "blue": 1, "brown": 1, "wild": 0},
        # Economy valuation (VP per round per colonized planet of each color)
        "vp_per_income": {"yellow": 0.20, "blue": 0.20, "brown": 0.20},
        "horizon_rounds": 3,            # project income this many rounds
        "discount": 0.90,               # per-round discount
        # Endgame / one-time values
        "monolith_vp": 3.0,
        "endgame_weight": 0.5,          # weight monolith VP toward present EV
        "discovery_vp": 1.0,            # if a category is flagged with discovery, value of the chit
        "discard_reward_vp": 0.0,       # value if you discard all draws (set >0 if using a house rule/variant)
        # Ancients modeling
        "ancient_block_penalty": 0.6,   # penalty for tile being blocked by Ancients in near-term
        "prob_clear_by_horizon": 0.40,  # chance you clear Ancients within horizon
        # Optional detailed fight EV if you intend to clear: will call combat.score_combat if provided
        "ancient_combat_query": None,   # dict accepted by combat.score_combat()
        "ancient_fallback_ev": -0.3,    # if no combat query or combat module missing, use this EV
        # Category feature overrides (see _parse_category for defaults)
        # e.g., "category_overrides": {"money2":{"discovery":True}, "ancient":{"money":0,"science":0,"materials":0}}
        "category_overrides": {},
      }
    Returns:
      ExplorationEV(expected_value_vp, notes_json)
    """
    cfg = _Config.from_query(query)
    rng = random.Random(cfg.seed)

    # Precompute PV factor per round for income
    pv = _present_value_factor(cfg.horizon_rounds, cfg.discount)

    # Monte Carlo over draws without replacement
    total_ev = 0.0
    pick_counts: Counter[str] = Counter()
    pick_scores: defaultdict[str, float] = defaultdict(float)

    for _ in range(cfg.n_sims):
        drawn = _weighted_sample_without_replacement(cfg.bag, cfg.draws, rng)
        # Evaluate each drawn category
        best_score = cfg.discard_reward_vp
        best_cat = None
        for cat in drawn:
            td = _tile_from_category(cat, cfg.category_overrides)
            score = _score_tile(td, cfg, pv, rng)
            if score > best_score:
                best_score = score
                best_cat = cat
        total_ev += best_score
        if best_cat is not None:
            pick_counts[best_cat] += 1
            pick_scores[best_cat] += best_score

    n = max(1, cfg.n_sims)
    avg_ev = total_ev / n

    # Build concise notes
    top = pick_counts.most_common(5)
    summary = {
        "ring": cfg.ring,
        "avg_ev": round(avg_ev, 3),
        "draws": cfg.draws,
        "connect_default": cfg.p_connect_default,
        "wormhole_generator": cfg.wormhole_generator,
        "pv_factor": round(pv, 3),
        "top_picks": [
            {"category": c, "pick_rate": round(cnt/n, 3), "avg_score": round(pick_scores[c]/max(1,cnt), 3)}
            for c, cnt in top
        ],
        "bag_size": sum(cfg.bag.values()),
    }
    return ExplorationEV(expected_value_vp=avg_ev, notes=_safe_json(summary))

# =============================
# Internal config and helpers
# =============================

@dataclass
class _Config:
    ring: int
    bag: Dict[str, float]
    draws: int
    n_sims: int
    seed: int
    p_connect_default: float
    p_connect_by_category: Dict[str, float]
    wormhole_generator: bool
    discs_available: int
    require_disc_to_claim: bool
    colony_ships: Dict[str, int]
    vp_per_income: Dict[str, float]
    horizon_rounds: int
    discount: float
    monolith_vp: float
    endgame_weight: float
    discovery_vp: float
    discard_reward_vp: float
    ancient_block_penalty: float
    prob_clear_by_horizon: float
    ancient_combat_query: Optional[Dict[str, Any]]
    ancient_fallback_ev: float
    category_overrides: Dict[str, Dict[str, Any]]

    @classmethod
    def from_query(cls, q: Dict[str, Any]) -> "_Config":
        bag = {k: float(v) for k, v in q.get("bag", {}).items() if float(v) > 0}
        ring = int(q.get("ring", 2))
        draws = int(q.get("draws", 1))
        n_sims = int(q.get("n_sims", 5000))
        seed = int(q.get("seed", 123))
        p_def = float(q.get("p_connect_default", 0.70))
        p_by = dict(q.get("p_connect_by_category", {}))
        whg = bool(q.get("wormhole_generator", False))
        discs = int(q.get("discs_available", 1))
        req_disc = bool(q.get("require_disc_to_claim", True))
        colony = {k:int(v) for k,v in q.get("colony_ships", {"yellow":1,"blue":1,"brown":1,"wild":0}).items()}
        vpincome = {"yellow":0.20,"blue":0.20,"brown":0.20}
        vpincome.update({k: float(v) for k, v in q.get("vp_per_income", {}).items()})
        horizon = int(q.get("horizon_rounds", 3))
        disc = float(q.get("discount", 0.90))
        mono = float(q.get("monolith_vp", 3.0))
        endw = float(q.get("endgame_weight", 0.5))
        disc_vp = float(q.get("discard_reward_vp", 0.0))
        discov = float(q.get("discovery_vp", 1.0))
        anc_pen = float(q.get("ancient_block_penalty", 0.6))
        p_clear = float(q.get("prob_clear_by_horizon", 0.40))
        anc_q = q.get("ancient_combat_query", None)
        anc_fb = float(q.get("ancient_fallback_ev", -0.3))
        overrides = dict(q.get("category_overrides", {}))
        return cls(
            ring=ring, bag=bag, draws=draws, n_sims=n_sims, seed=seed,
            p_connect_default=p_def, p_connect_by_category=p_by, wormhole_generator=whg,
            discs_available=discs, require_disc_to_claim=req_disc, colony_ships=colony,
            vp_per_income=vpincome, horizon_rounds=horizon, discount=disc,
            monolith_vp=mono, endgame_weight=endw, discovery_vp=discov,
            discard_reward_vp=disc_vp, ancient_block_penalty=anc_pen,
            prob_clear_by_horizon=p_clear, ancient_combat_query=anc_q,
            ancient_fallback_ev=anc_fb, category_overrides=overrides
        )

@dataclass
class _TileDesc:
    category: str
    money: int = 0       # yellow planets
    science: int = 0     # blue planets
    materials: int = 0   # brown planets
    wild: int = 0        # wild planets
    ancient: bool = False
    monolith: bool = False
    discovery: bool = False

def _present_value_factor(h: int, d: float) -> float:
    # PV of 1 unit per round for h rounds with discount d
    if h <= 0: return 0.0
    if abs(d - 1.0) < 1e-9:
        return float(h)
    return (1.0 - d**h) / (1.0 - d)

def _safe_json(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, separators=(',',':'))
    except Exception:
        return str(obj)

# =============================
# Sampling
# =============================

def _weighted_sample_without_replacement(weights: Dict[str, float], k: int, rng: random.Random) -> List[str]:
    """
    Efraimidis-Spirakis method for weighted sampling without replacement.
    Weights can be non-integers. Returns up to k unique categories.
    """
    items = [(cat, max(0.0, float(w))) for cat, w in weights.items() if w > 0]
    if not items or k <= 0:
        return []
    k = min(k, len(items))
    keys = []
    for cat, w in items:
        if w <= 0:
            continue
        u = rng.random()
        # Larger weights -> larger key
        key = u**(1.0 / w)
        keys.append((key, cat))
    keys.sort(reverse=True)  # take top-k
    return [cat for _, cat in keys[:k]]

# =============================
# Category parsing
# =============================

_RES_ALIASES = {
    "money":"money", "credit":"money", "yellow":"money", "y":"money",
    "science":"science", "blue":"science", "b":"science",
    "materials":"materials", "brown":"materials", "m":"materials", "r":"materials",
    "wild":"wild", "w":"wild"
}

def _tile_from_category(cat: str, overrides: Dict[str, Dict[str, Any]]) -> _TileDesc:
    base = _parse_category(cat)
    # Apply overrides
    ov = overrides.get(cat, {})
    for k, v in ov.items():
        if hasattr(base, k):
            setattr(base, k, v)
    return base

def _parse_category(cat: str) -> _TileDesc:
    td = _TileDesc(category=cat)
    s = cat.lower()
    # simple flags
    if "ancient" in s:
        td.ancient = True
    if "monolith" in s:
        td.monolith = True
    if "discovery" in s:
        td.discovery = True
    # tokenized counts like 'money2', 'science1_materials1', 'y1b1'
    tokens = re.split(r'[^a-z0-9]+', s)
    for tok in tokens:
        if not tok:
            continue
        # match <res><count>, e.g., money2, y1, blue3, wild1
        m = re.match(r'([a-z]+)(\d+)$', tok)
        if m:
            res_raw, cnt = m.group(1), int(m.group(2))
            res = _RES_ALIASES.get(res_raw)
            if res == "money":
                td.money += cnt
            elif res == "science":
                td.science += cnt
            elif res == "materials":
                td.materials += cnt
            elif res == "wild":
                td.wild += cnt
            continue
    return td

# =============================
# Scoring
# =============================

def _score_tile(td: _TileDesc, cfg: _Config, pv: float, rng: random.Random) -> float:
    """
    Score a tile's VP-equivalent EV given capabilities and weights.
    """
    # Placement feasibility via wormhole compatibility
    p_conn = 1.0 if cfg.wormhole_generator else cfg.p_connect_by_category.get(td.category, cfg.p_connect_default)

    # If no discs and claiming requires a disc, you can still place but cannot claim now => no immediate income EV
    can_claim_now = cfg.discs_available > 0 or not cfg.require_disc_to_claim

    # Planet counts available to colonize now. Ancients block colonization until cleared.
    money = td.money
    science = td.science
    materials = td.materials
    wild = td.wild

    # Colonization now if not ancient-blocked and you can claim
    colonize_now = {"money":0, "science":0, "materials":0}
    if can_claim_now and not td.ancient:
        colonize_now = _allocate_colony_ships(money, science, materials, wild, dict(cfg.colony_ships))

    income_ev = (
        colonize_now["money"]     * cfg.vp_per_income["yellow"] * pv
      + colonize_now["science"]   * cfg.vp_per_income["blue"]   * pv
      + colonize_now["materials"] * cfg.vp_per_income["brown"]  * pv
    )

    # Monolith endgame value (weighted to present)
    monolith_ev = cfg.monolith_vp * cfg.endgame_weight if td.monolith else 0.0

    # Discovery chit value if flagged (rare unless user overrides)
    discovery_ev = cfg.discovery_vp if td.discovery else 0.0

    # Connectivity bonus
    connectivity_ev = 0.15 * pv  # baseline bonus
    # Scale by planet presence as a proxy for tile "goodness"
    connectivity_ev *= 0.5 + 0.5 * min(1.0, (money+science+materials+wild)/3.0)

    # Ancients: apply near-term block penalty and optional future clear EV
    ancient_penalty = cfg.ancient_block_penalty if td.ancient else 0.0
    future_clear_ev = 0.0
    if td.ancient and cfg.prob_clear_by_horizon > 0.0:
        if cfg.ancient_combat_query and score_combat is not None:
            try:
                res = score_combat(cfg.ancient_combat_query)
                future_clear_ev = cfg.prob_clear_by_horizon * float(getattr(res, "expected_vp_swing", 0.0))
            except Exception:
                future_clear_ev = cfg.prob_clear_by_horizon * cfg.ancient_fallback_ev
        else:
            future_clear_ev = cfg.prob_clear_by_horizon * cfg.ancient_fallback_ev

    # Total EV if placed
    placed_ev = (income_ev + monolith_ev + discovery_ev + connectivity_ev + future_clear_ev - ancient_penalty)

    # Final EV: account for placement probability; compare to discard option
    place_ev = p_conn * placed_ev + (1.0 - p_conn) * cfg.discard_reward_vp

    return place_ev

def _allocate_colony_ships(money: int, science: int, materials: int, wild: int, ships: Dict[str,int]) -> Dict[str,int]:
    """
    Greedy allocation: use color-specific ships first, then wild ships to fill remaining.
    Returns colonized counts per resource color (money/science/materials). Wild planets can be claimed by any.
    """
    m = min(money, max(0, ships.get("yellow", 0)))
    b = min(science, max(0, ships.get("blue", 0)))
    r = min(materials, max(0, ships.get("brown", 0)))
    rem_y = money - m
    rem_b = science - b
    rem_r = materials - r
    # allocate wild planets using whichever color ships remain (yellow->blue->brown priority)
    wild_left = max(0, wild)
    for color_key, need in [("yellow", rem_y), ("blue", rem_b), ("brown", rem_r)]:
        if wild_left <= 0:
            break
        have = max(0, ships.get(color_key, 0) - (m if color_key=="yellow" else b if color_key=="blue" else r))
        take = min(need, have, wild_left)
        if color_key=="yellow": m += take
        elif color_key=="blue": b += take
        else: r += take
        wild_left -= take
    # Use wild colony ships to fill remaining across any planet types
    wships = max(0, ships.get("wild", 0))
    for need_key, need in [("yellow", money - m), ("blue", science - b), ("brown", materials - r)]:
        if wships <= 0:
            break
        take = min(need, wships)
        if need_key=="yellow": m += take
        elif need_key=="blue": b += take
        else: r += take
        wships -= take
    return {"money": m, "science": b, "materials": r}

