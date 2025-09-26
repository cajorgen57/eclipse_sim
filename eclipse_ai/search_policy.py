from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import math, random, copy

from .game_models import GameState, Action, Score, ActionType, PlayerState, Hex, Pieces, Planet, ShipDesign
from .rules_engine import legal_actions
from .evaluator import evaluate_action

# =============================
# Public data structures
# =============================

@dataclass
class PlanStep:
    action: Action
    score: Score

@dataclass
class Plan:
    steps: List[PlanStep] = field(default_factory=list)
    total_score: float = 0.0
    risk: float = 0.0

# =============================
# MCTS with P-UCT priors
# =============================

class MCTSPlanner:
    def __init__(
        self,
        simulations: int = 400,
        c_puct: float = 1.4,
        discount: float = 0.95,
        rollout_depth: int = 2,
        risk_aversion: float = 0.25,
        dirichlet_alpha: float = 0.3,
        dirichlet_epsilon: float = 0.25,
        seed: Optional[int] = None,
    ):
        self.simulations = simulations
        self.c = c_puct
        self.discount = discount
        self.rollout_depth = rollout_depth
        self.risk_aversion = risk_aversion
        self.dirichlet_alpha = dirichlet_alpha
        self.dirichlet_epsilon = dirichlet_epsilon
        self.rng = random.Random(seed)

    # ---- public API ----

    def plan(self, state: GameState, player_id: str, depth: int = 2, top_k: int = 5) -> List[Plan]:
        """
        Run MCTS from the given state for a single player's turn horizon.
        Opponents are not simulated; this is a myopic planner for quick advice.
        """
        root = _Node(state=copy.deepcopy(state), player_id=player_id)

        # Expand root once to create priors
        self._expand(root)

        # Add Dirichlet noise at root for exploration
        if root.children:
            noise = _dirichlet(self.rng, len(root.children), self.dirichlet_alpha)
            for i, child in enumerate(root.children):
                child.P = (1 - self.dirichlet_epsilon) * child.P + self.dirichlet_epsilon * noise[i]

        for _ in range(self.simulations):
            node = root
            path: List[_Node] = [node]

            # Selection
            while node.expanded and node.children:
                node = self._select_child(node)
                path.append(node)

            # Expansion
            if not node.expanded:
                self._expand(node)

            # Rollout / Value
            value = self._evaluate_leaf(node)

            # Backpropagate
            self._backprop(path, value)

        # Extract top-k plans from root children by visit count, then by Q
        children = sorted(root.children, key=lambda n: (n.N, n.Q), reverse=True)
        out: List[Plan] = []
        for child in children[:top_k]:
            steps, total_score, risk = self._best_line(child, max_depth=depth)
            out.append(Plan(steps=steps, total_score=total_score, risk=risk))
        if not out:
            # Fallback: single-ply ranking
            root_actions = legal_actions(state, player_id)
            scored = []
            for a in root_actions:
                sc = evaluate_action(state, a)
                scored.append(Plan(steps=[PlanStep(a, sc)], total_score=sc.expected_vp, risk=sc.risk))
            scored.sort(key=lambda p: p.total_score, reverse=True)
            return scored[:top_k]
        return out

    # ---- core steps ----

    def _expand(self, node: '_Node'):
        if node.expanded:
            return
        node.expanded = True
        state = node.state
        acts = legal_actions(state, node.player_id)
        if not acts:
            return

        # Evaluate actions for priors
        scores: List[Score] = [evaluate_action(state, a) for a in acts]
        # Convert to positive priors via softmax on risk-adjusted value estimates
        vals = [self._value_from_score(sc) for sc in scores]
        priors = _softmax(vals)

        for a, sc, p in zip(acts, scores, priors):
            next_state = _forward_model(state, node.player_id, a)
            child = _Node(
                state=next_state,
                player_id=node.player_id,  # same player; single-turn planner
                parent=node,
                action=a,
                prior_score=sc,
                P=p
            )
            node.children.append(child)

    def _select_child(self, node: '_Node') -> '_Node':
        # P-UCT
        total_N = max(1, node.N)
        best, best_score = None, -1e30
        for child in node.children:
            u = self.c * child.P * math.sqrt(total_N) / (1 + child.n())
            q = child.Q
            score = q + u
            if score > best_score:
                best, best_score = child, score
        return best if best is not None else node.children[0]

    def _evaluate_leaf(self, node: '_Node') -> float:
        # If leaf has no actions, value 0
        if not node.children:
            # Use immediate evaluation if available
            if node.prior_score is not None:
                return self._value_from_score(node.prior_score)
            return 0.0

        # Rollout a short random-improve policy
        value = 0.0
        discount = 1.0
        curr = node
        for d in range(self.rollout_depth):
            if not curr.children:
                break
            # epsilon-greedy on Q + prior to avoid getting stuck
            if self.rng.random() < 0.2:
                curr = self.rng.choice(curr.children)
            else:
                curr = max(curr.children, key=lambda c: c.Q + 0.5*c.P)
            if curr.prior_score is None:
                sc = evaluate_action(curr.state, curr.action)
                curr.prior_score = sc
            value += discount * self._value_from_score(curr.prior_score)
            discount *= self.discount
            # ensure expanded for next step
            if not curr.expanded:
                self._expand(curr)

        return value

    def _backprop(self, path: List['_Node'], value: float):
        for node in path:
            node.W += value
            node.N += 1
            node.Q = node.W / node.N

    # ---- plan extraction ----

    def _best_line(self, node: '_Node', max_depth: int = 2) -> Tuple[List[PlanStep], float, float]:
        steps: List[PlanStep] = []
        total, disc = 0.0, 1.0
        risks: List[float] = []
        curr = node
        for _ in range(max_depth):
            if curr.prior_score is None and curr.action is not None:
                curr.prior_score = evaluate_action(curr.state, curr.action)
            if curr.prior_score is not None and curr.action is not None:
                steps.append(PlanStep(curr.action, curr.prior_score))
                total += disc * float(curr.prior_score.expected_vp)
                risks.append(float(curr.prior_score.risk))
                disc *= self.discount
            if not curr.children:
                break
            curr = max(curr.children, key=lambda c: c.Q)
        avg_risk = sum(risks)/len(risks) if risks else 0.0
        return steps, total, avg_risk

    # ---- helpers ----

    def _value_from_score(self, sc: Score) -> float:
        # Risk-adjusted value
        return float(sc.expected_vp) - self.risk_aversion * float(sc.risk)

# =============================
# Node
# =============================

@dataclass
class _Node:
    state: GameState
    player_id: str
    parent: Optional['_Node'] = None
    action: Optional[Action] = None
    prior_score: Optional[Score] = None  # evaluation of action leading to this node
    P: float = 0.0                        # prior
    W: float = 0.0                        # total value
    N: int = 0                            # visit count
    Q: float = 0.0                        # mean value
    children: List['_Node'] = field(default_factory=list)
    expanded: bool = False

    def n(self) -> int:
        return self.N

# =============================
# Forward model (lightweight)
# =============================

# Local cost table to keep forward model self-contained
_SHIP_COSTS = {"interceptor":2, "cruiser":3, "dreadnought":5}
_STARBASE_COST = 4
_SCIENCE_COST_BASE = 3  # rough

def _forward_model(state: GameState, pid: str, action: Action) -> GameState:
    """Very small deterministic forward model sufficient for short planning.
    Applies optimistic but resource-aware state changes. Non-destructive via deepcopy.
    """
    s = copy.deepcopy(state)

    # Safety checks
    if pid not in s.players:
        return s
    you = s.players[pid]

    t = action.type
    p = action.payload or {}

    if t == ActionType.PASS:
        # Terminal in our single-player horizon; no change
        return s

    if t == ActionType.RESEARCH:
        tech = str(p.get("tech", ""))
        if tech and tech not in you.known_techs:
            you.known_techs.append(tech)
            # subtract rough science cost
            cost = max(2, _SCIENCE_COST_BASE + min(2, len(you.known_techs)//4))
            you.resources.science = max(0, you.resources.science - cost)
        return s

    if t == ActionType.BUILD:
        hex_id = p.get("hex")
        ships: Dict[str,int] = dict(p.get("ships", {}))
        starbase = int(p.get("starbase", 0))
        hx = s.map.hexes.get(hex_id)
        if hx is None:
            # create a placeholder hex if needed
            hx = Hex(id=str(hex_id), ring=2, wormholes=[], planets=[], pieces={})
            s.map.hexes[hx.id] = hx
        if pid not in hx.pieces:
            hx.pieces[pid] = Pieces(ships={}, starbase=0, discs=hx.pieces.get(pid, Pieces()).discs if pid in hx.pieces else 0, cubes={})

        # Apply ship builds constrained by materials
        mats = you.resources.materials
        for cls, n in ships.items():
            for _ in range(int(n)):
                c = _SHIP_COSTS.get(cls, 3)
                if mats >= c:
                    mats -= c
                    hx.pieces[pid].ships[cls] = hx.pieces[pid].ships.get(cls, 0) + 1
        if starbase > 0 and mats >= _STARBASE_COST:
            mats -= _STARBASE_COST
            hx.pieces[pid].starbase += 1
        you.resources.materials = mats
        return s

    if t == ActionType.MOVE:
        try:
            _apply_move_action(s, pid, p)
        except ValueError:
            return state  # illegal move payloads are ignored in the forward model
        return s

    if t == ActionType.EXPLORE:
        # Optimistic: reduce bag mass slightly to reflect drawing; do not place new hex
        ring = int(p.get("ring", 2))
        bag_key = f"R{ring}"
        if bag_key in s.bags:
            # Reduce the heaviest category by 1 as a placeholder draw
            bag = s.bags[bag_key]
            if bag:
                key = max(bag, key=lambda k: bag[k])
                if bag[key] > 0:
                    bag[key] -= 1
        return s

    if t == ActionType.INFLUENCE:
        # Adjust income proxy via cubes; not modeling discs inventory
        hex_id = p.get("hex")
        inc = p.get("income_delta", {})
        # store a marker by adding cubes to the hex
        hx = s.map.hexes.get(hex_id)
        if hx:
            if pid not in hx.pieces:
                hx.pieces[pid] = Pieces(ships={}, starbase=0, discs=1, cubes={})
            for color, dv in inc.items():
                key = {"yellow":"y","blue":"b","brown":"p"}.get(color, "y")
                hx.pieces[pid].cubes[key] = hx.pieces[pid].cubes.get(key, 0) + max(0, int(dv))
        return s

    if t == ActionType.DIPLOMACY:
        # Store alliance in player state
        target = p.get("with")
        if target:
            you.diplomacy[target] = "ally"
        return s

    if t == ActionType.UPGRADE:
        # Apply incremental design changes
        apply = p.get("apply", {})
        for cls, mods in apply.items():
            sd = you.ship_designs.get(cls, ShipDesign())
            for k, dv in mods.items():
                if hasattr(sd, k):
                    setattr(sd, k, max(0, getattr(sd, k) + int(dv)))
            you.ship_designs[cls] = sd
        return s

    # Unknown action -> no-op
    return s

# =============================
# Utilities
# =============================

def _softmax(xs: List[float], temp: float = 1.0) -> List[float]:
    if not xs:
        return []
    m = max(xs)
    exps = [math.exp((x - m)/max(1e-6, temp)) for x in xs]
    s = sum(exps)
    if s <= 0:
        return [1.0/len(xs)] * len(xs)
    return [e/s for e in exps]

def _dirichlet(rng: random.Random, k: int, alpha: float) -> List[float]:
    # Sample Dirichlet(k, alpha)
    # Use gamma sampling
    samples = []
    for _ in range(k):
        # Gamma(alpha, 1) via sum of exponentials for small alpha fallback
        # Use Python's gammavariate
        samples.append(rng.gammavariate(alpha, 1.0))
    s = sum(samples) or 1.0
    return [x/s for x in samples]


# =============================
# Movement helpers and executor
# =============================

def _apply_move_action(state: GameState, pid: str, payload: Dict[str, Any]) -> None:
    """Validate and apply a MOVE action with full Eclipse legality checks."""
    working = copy.deepcopy(state)

    activations = list(payload.get("activations", []))
    if not activations:
        raise ValueError("MOVE requires activations payload")

    is_reaction = bool(payload.get("is_reaction") or payload.get("reaction"))
    max_activations = 1 if is_reaction else 3
    if len(activations) > max_activations:
        raise ValueError("Too many ship activations for this action")

    player = working.players.get(pid)
    if player is None:
        raise ValueError("Unknown player for MOVE")

    for activation in activations:
        _execute_activation(working, player, activation)

    # Commit the simulated changes back to the real state only after validation succeeds.
    state.players = working.players
    state.map = working.map


def _execute_activation(state: GameState, player: PlayerState, activation: Dict[str, Any]) -> None:
    ship_class = str(activation.get("ship_class", ""))
    if not ship_class:
        raise ValueError("Activation missing ship class")
    start_hex_id = str(activation.get("from", ""))
    if not start_hex_id:
        raise ValueError("Activation missing starting hex")

    path = list(activation.get("path", []))
    if not path:
        raise ValueError("Activation requires explicit path including start")
    if path[0] != start_hex_id:
        raise ValueError("Path must begin at starting hex")

    count = int(activation.get("count", 1))
    if count <= 0:
        raise ValueError("Activation must move at least one ship")

    for _ in range(count):
        _activate_single_ship(state, player, ship_class, path, activation)


def _activate_single_ship(state: GameState, player: PlayerState, ship_class: str, path: List[str], activation: Dict[str, Any]) -> None:
    you = player.player_id
    current_hex = _require_hex(state, path[0])
    pieces = current_hex.pieces.get(you)
    if pieces is None or pieces.ships.get(ship_class, 0) <= 0:
        raise ValueError("No ship of requested class in starting hex")

    design = player.ship_designs.get(ship_class, ShipDesign())
    if ship_class == "starbase":
        if len(path) > 1:
            raise ValueError("Starbases cannot move")
        return

    movement_points = design.movement_value()
    has_jump = bool(design.has_jump_drive)
    if len(path) > 1 and movement_points <= 0 and not has_jump:
        if ship_class in {"interceptor", "cruiser", "dreadnought"}:
            raise ValueError("Ship lacks drives and cannot move")

    bay_payload = activation.get("bay") if design.interceptor_bays > 0 else None
    carried_interceptors = 0
    if bay_payload:
        carried_interceptors = int(bay_payload.get("interceptors", 0))
        if carried_interceptors < 0:
            raise ValueError("Cannot load negative interceptors")
        capacity = min(2, design.interceptor_bays)
        if carried_interceptors > capacity:
            raise ValueError("Interceptor Bay capacity exceeded")
        available = pieces.ships.get("interceptor", 0)
        if carried_interceptors > available:
            raise ValueError("Not enough interceptors to load into bay")

    # Enforce pinning when leaving the starting hex, including any interceptors we plan to carry.
    _enforce_exit_pinning(current_hex, you, 1 + carried_interceptors)

    if carried_interceptors:
        _remove_ships_from_hex(current_hex, you, "interceptor", carried_interceptors)

    jump_used = False
    steps_remaining = movement_points
    current_hex_id = path[0]

    for idx, next_hex_id in enumerate(path[1:], start=1):
        next_hex = _require_hex(state, next_hex_id)
        if not next_hex.explored:
            raise ValueError("Cannot move into unexplored hex")

        src_hex = _require_hex(state, current_hex_id)
        if src_hex.has_gcds:
            raise ValueError("GCDS blocks movement through the Galactic Center")

        connection_type = _classify_connection(state, player, current_hex_id, next_hex_id)

        if connection_type == "jump":
            if not has_jump or jump_used:
                raise ValueError("Jump Drive already used this activation")
            jump_used = True
        else:
            # Wormhole / portal movement consumes a step.
            if steps_remaining <= 0:
                raise ValueError("Movement exceeds drive allowance")
            steps_remaining -= 1
            if connection_type is None:
                raise ValueError("No legal connection between hexes")

        # Leaving current hex after validating movement points.
        _enforce_exit_pinning(src_hex, you, 1)
        _move_ship_between_hexes(state, you, ship_class, current_hex_id, next_hex_id)

        dst_hex = _require_hex(state, next_hex_id)
        enemy_in_dst = _count_enemy_ships(dst_hex, you)
        if idx < len(path) - 1:
            if dst_hex.has_gcds:
                raise ValueError("Cannot move through the Galactic Center while GCDS is active")
            if enemy_in_dst > 0:
                friendly_total = _count_friendly_ships(dst_hex, you)
                if friendly_total <= enemy_in_dst:
                    raise ValueError("Pinned upon entering contested hex")

        current_hex_id = next_hex_id

    # Re-add any interceptors transported in the bay to the final destination.
    if carried_interceptors:
        dest_hex = _require_hex(state, current_hex_id)
        dest_pieces = dest_hex.pieces.setdefault(you, Pieces())
        dest_pieces.ships["interceptor"] = dest_pieces.ships.get("interceptor", 0) + carried_interceptors


def _classify_connection(state: GameState, player: PlayerState, src_id: str, dst_id: str) -> Optional[str]:
    """Return connection type: 'wormhole', 'warp', 'wg', 'jump', or None."""
    if src_id == dst_id:
        return "wormhole"

    src_hex = state.map.hexes.get(src_id)
    dst_hex = state.map.hexes.get(dst_id)
    if src_hex is None or dst_hex is None:
        return None

    if _is_warp_connection(src_hex, dst_hex):
        return "warp"

    if _has_full_wormhole(state, src_id, dst_id):
        return "wormhole"

    if player.has_wormhole_generator and _has_half_wormhole_for_wg(state, src_id, dst_id):
        return "wg"

    if _is_neighbor(state, src_id, dst_id):
        return "jump"

    return None


def _require_hex(state: GameState, hex_id: str) -> Hex:
    hx = state.map.hexes.get(hex_id)
    if hx is None:
        raise ValueError(f"Hex {hex_id} is not on the map")
    return hx


def _is_neighbor(state: GameState, a: str, b: str) -> bool:
    hx_a = state.map.hexes.get(a)
    hx_b = state.map.hexes.get(b)
    if hx_a is None or hx_b is None:
        return False
    if b in hx_a.neighbors.values():
        return True
    if a in hx_b.neighbors.values():
        return True
    return False


def _is_warp_connection(a: Hex, b: Hex) -> bool:
    return bool(a.has_warp_portal and b.has_warp_portal)


def _has_full_wormhole(state: GameState, src_id: str, dst_id: str) -> bool:
    src = state.map.hexes.get(src_id)
    dst = state.map.hexes.get(dst_id)
    if src is None or dst is None:
        return False
    if not _is_neighbor(state, src_id, dst_id):
        return False
    edges = [edge for edge, neighbor in src.neighbors.items() if neighbor == dst_id]
    if not edges:
        return False
    back_edges = [edge for edge, neighbor in dst.neighbors.items() if neighbor == src_id]
    if not back_edges:
        return False
    if any(edge in src.wormholes for edge in edges) and any(edge in dst.wormholes for edge in back_edges):
        return True
    return False


def _has_half_wormhole_for_wg(state: GameState, src_id: str, dst_id: str) -> bool:
    src = state.map.hexes.get(src_id)
    dst = state.map.hexes.get(dst_id)
    if src is None or dst is None:
        return False
    if not _is_neighbor(state, src_id, dst_id):
        return False
    edges = [edge for edge, neighbor in src.neighbors.items() if neighbor == dst_id]
    back_edges = [edge for edge, neighbor in dst.neighbors.items() if neighbor == src_id]
    has_src_edge = any(edge in src.wormholes for edge in edges)
    has_dst_edge = any(edge in dst.wormholes for edge in back_edges)
    return has_src_edge or has_dst_edge


def _move_ship_between_hexes(state: GameState, pid: str, ship_class: str, src_id: str, dst_id: str) -> None:
    src_hex = _require_hex(state, src_id)
    dst_hex = _require_hex(state, dst_id)
    _remove_ships_from_hex(src_hex, pid, ship_class, 1)
    dst_pieces = dst_hex.pieces.setdefault(pid, Pieces())
    dst_pieces.ships[ship_class] = dst_pieces.ships.get(ship_class, 0) + 1


def _remove_ships_from_hex(hex_obj: Hex, pid: str, ship_class: str, count: int) -> None:
    if count <= 0:
        return
    pieces = hex_obj.pieces.get(pid)
    if pieces is None:
        raise ValueError("Player has no ships to remove")
    have = pieces.ships.get(ship_class, 0)
    if have < count:
        raise ValueError("Attempting to move more ships than present")
    pieces.ships[ship_class] = have - count
    if pieces.ships[ship_class] <= 0:
        del pieces.ships[ship_class]


def _count_enemy_ships(hex_obj: Hex, pid: str) -> int:
    total = int(hex_obj.ancients)
    for owner, pieces in hex_obj.pieces.items():
        if owner == pid:
            continue
        total += int(pieces.starbase)
        total += sum(int(n) for n in pieces.ships.values())
    return total


def _count_friendly_ships(hex_obj: Hex, pid: str) -> int:
    pieces = hex_obj.pieces.get(pid)
    if pieces is None:
        return 0
    return int(pieces.starbase) + sum(int(n) for n in pieces.ships.values())


def _enforce_exit_pinning(hex_obj: Hex, pid: str, leaving: int) -> None:
    enemy = _count_enemy_ships(hex_obj, pid)
    if enemy <= 0:
        return
    friendly = _count_friendly_ships(hex_obj, pid)
    if friendly - leaving < enemy:
        raise ValueError("Cannot leave contested hex without leaving pinned ships")
