from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Sequence
import math, random, copy

from .game_models import GameState, Action, Score, ActionType, PlayerState, Hex, Pieces, Planet, ShipDesign
from .alliances import ship_presence
from .rules_engine import legal_actions
from .evaluator import evaluate_action
from .movement import LEGAL_CONNECTION_TYPES, classify_connection, max_ship_activations_per_action
from .technology import do_research, ResearchError, load_tech_definitions
from .pathing import compute_connectivity

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
    state_summary: Dict[str, Any] = field(default_factory=dict)
    result_state: Optional[GameState] = None

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
        # Refresh metadata on the live state so downstream consumers can inspect
        # the new game-state hints (possible actions, mobility flags, reachability).
        base_actions = legal_actions(state, player_id)
        self._gather_metadata(state, player_id, allowed_actions=base_actions)
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
        validated: List[Plan] = []
        for child in children:
            actions = self._collect_action_sequence(child, max_depth=depth)
            if not actions:
                continue
            plan = self._simulate_plan(state, player_id, actions, enforce_legality=True)
            if plan is None:
                continue
            validated.append(plan)
            if len(validated) >= top_k:
                break

        if not validated:
            # Fallback: single-ply ranking using the already-computed legal actions.
            validated = self._fallback_plans(state, player_id, base_actions, top_k)

        return validated[:top_k]

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

    def _collect_action_sequence(self, node: '_Node', max_depth: int = 2) -> List[Action]:
        actions: List[Action] = []
        curr = node
        for _ in range(max_depth):
            if curr.action is None:
                break
            actions.append(curr.action)
            if not curr.children:
                break
            curr = max(curr.children, key=lambda c: c.Q)
        return actions

    def _simulate_plan(
        self,
        base_state: GameState,
        player_id: str,
        actions: Sequence[Action],
        *,
        enforce_legality: bool = False,
    ) -> Optional[Plan]:
        working = copy.deepcopy(base_state)
        steps: List[PlanStep] = []
        total = 0.0
        disc = 1.0
        risks: List[float] = []

        allowed = legal_actions(working, player_id)
        meta_before = self._gather_metadata(working, player_id, allowed_actions=allowed)

        if not actions:
            summary = self._extract_state_summary(working, player_id)
            return Plan(steps=[], total_score=0.0, risk=0.0, state_summary=summary, result_state=working)

        for action in actions:
            if enforce_legality and action not in allowed:
                return None

            score = evaluate_action(working, action)
            steps.append(PlanStep(action, score))
            total += disc * float(score.expected_vp)
            risks.append(float(score.risk))

            working = _forward_model(working, player_id, action)
            allowed = legal_actions(working, player_id)
            meta_after = self._gather_metadata(working, player_id, allowed_actions=allowed)

            total += disc * self._mobility_bonus(meta_after)
            total += disc * self._connectivity_bonus(meta_before, meta_after)

            meta_before = meta_after
            disc *= self.discount

        summary = self._extract_state_summary(working, player_id)
        avg_risk = sum(risks) / len(risks) if risks else 0.0
        return Plan(steps=steps, total_score=total, risk=avg_risk, state_summary=summary, result_state=working)

    def _fallback_plans(
        self,
        state: GameState,
        player_id: str,
        base_actions: Sequence[Action],
        top_k: int,
    ) -> List[Plan]:
        out: List[Plan] = []
        for action in base_actions:
            plan = self._simulate_plan(state, player_id, [action], enforce_legality=True)
            if plan is None:
                continue
            out.append(plan)
            if len(out) >= top_k:
                break
        if not out:
            # ensure at least a pass plan exists
            plan = self._simulate_plan(state, player_id, [], enforce_legality=True)
            if plan is not None:
                out.append(plan)
        return out

    def _gather_metadata(
        self,
        state: GameState,
        player_id: str,
        *,
        allowed_actions: Optional[Sequence[Action]] = None,
    ) -> Dict[str, Any]:
        if allowed_actions is None:
            allowed_actions = legal_actions(state, player_id)
        try:
            reach = compute_connectivity(state, player_id)
            state.connectivity_metrics[player_id] = {
                "reachable": sorted(reach),
                "count": len(reach),
            }
            reach_count = len(reach)
        except Exception:
            reach_count = 0

        possible_actions = set(getattr(state, "possible_actions", set()) or set())
        return {
            "possible_actions": possible_actions,
            "can_move_ships": bool(getattr(state, "can_move_ships", False)),
            "can_explore": bool(getattr(state, "can_explore", False)),
            "connectivity_count": reach_count,
        }

    def _mobility_bonus(self, meta: Dict[str, Any]) -> float:
        bonus = 0.0
        if meta.get("can_move_ships"):
            bonus += 0.05
        if meta.get("can_explore"):
            bonus += 0.04
        possible_actions = meta.get("possible_actions") or set()
        bonus += 0.01 * min(6, len(possible_actions))
        reach = int(meta.get("connectivity_count", 0) or 0)
        bonus += 0.02 * min(5, reach) / 5.0
        return bonus

    def _connectivity_bonus(self, before: Dict[str, Any], after: Dict[str, Any]) -> float:
        b = int(before.get("connectivity_count", 0) or 0)
        a = int(after.get("connectivity_count", 0) or 0)
        delta = a - b
        if delta == 0:
            return 0.0
        return max(-0.5, min(0.5, 0.05 * delta))

    def _extract_state_summary(self, state: GameState, player_id: str) -> Dict[str, Any]:
        possible_actions = getattr(state, "possible_actions", set()) or set()
        actions_list = []
        for act in possible_actions:
            try:
                actions_list.append(act.value)  # type: ignore[attr-defined]
            except Exception:
                actions_list.append(str(act))
        metrics = getattr(state, "connectivity_metrics", {}).get(player_id, {}) if getattr(state, "connectivity_metrics", None) else {}
        summary: Dict[str, Any] = {
            "possible_actions": sorted(actions_list),
            "can_explore": bool(getattr(state, "can_explore", False)),
            "can_move_ships": bool(getattr(state, "can_move_ships", False)),
        }
        if metrics:
            summary["connectivity"] = {
                "count": int(metrics.get("count", 0) or 0),
                "reachable": list(metrics.get("reachable", [])),
            }
        return summary

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


def _refresh_connectivity(state: GameState, pid: str) -> None:
    try:
        reach = compute_connectivity(state, pid)
        state.connectivity_metrics[pid] = {
            "reachable": sorted(reach),
            "count": len(reach),
        }
    except Exception:
        pass

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
        _refresh_connectivity(s, pid)
        return s

    if t == ActionType.RESEARCH:
        tech = str(p.get("tech", ""))
        if tech:
            if not s.tech_definitions:
                s.tech_definitions = load_tech_definitions()
            try:
                do_research(s, you, tech)
            except ResearchError:
                pass
        _refresh_connectivity(s, pid)
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
        _refresh_connectivity(s, pid)
        return s

    if t == ActionType.MOVE:
        try:
            _apply_move_action(s, pid, p)
        except ValueError:
            _refresh_connectivity(state, pid)
            return state  # illegal move payloads are ignored in the forward model
        _refresh_connectivity(s, pid)
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
        _refresh_connectivity(s, pid)
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
        _refresh_connectivity(s, pid)
        return s

    if t == ActionType.DIPLOMACY:
        # Store alliance in player state
        target = p.get("with")
        if target:
            you.diplomacy[target] = "ally"
        _refresh_connectivity(s, pid)
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
        _refresh_connectivity(s, pid)
        return s

    # Unknown action -> no-op
    _refresh_connectivity(s, pid)
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

    player = working.players.get(pid)
    if player is None:
        raise ValueError("Unknown player for MOVE")

    is_reaction = bool(payload.get("is_reaction") or payload.get("reaction"))
    max_activations = max_ship_activations_per_action(player, is_reaction=is_reaction)
    if len(activations) > max_activations:
        raise ValueError("Too many ship activations for this action")

    for activation in activations:
        _execute_activation(working, player, activation, is_reaction=is_reaction)

    # Commit the simulated changes back to the real state only after validation succeeds.
    state.players = working.players
    state.map = working.map


def _execute_activation(
    state: GameState,
    player: PlayerState,
    activation: Dict[str, Any],
    *,
    is_reaction: bool = False,
) -> None:
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
    if is_reaction and count != 1:
        raise ValueError("Reaction MOVE may activate exactly one ship")

    for _ in range(count):
        _activate_single_ship(state, player, ship_class, path, activation)


def _activate_single_ship(state: GameState, player: PlayerState, ship_class: str, path: List[str], activation: Dict[str, Any]) -> None:
    you = player.player_id
    current_hex = _require_hex(state, path[0])
    pieces = current_hex.pieces.get(you)
    if pieces is None or pieces.ships.get(ship_class, 0) <= 0:
        raise ValueError("No ship of requested class in starting hex")

    friendly_start, enemy_start = ship_presence(state, current_hex, you)
    pinned_at_start = enemy_start > 0

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
    if pinned_at_start:
        activation.setdefault("pinned", True)
    _enforce_exit_pinning(state, current_hex, you, 1 + carried_interceptors)

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

        connection_type = classify_connection(
            state,
            player,
            current_hex_id,
            next_hex_id,
            ship_design=design,
            ship_class=ship_class,
        )
        if connection_type not in LEGAL_CONNECTION_TYPES:
            raise ValueError("No legal connection between hexes")

        if connection_type == "jump":
            if not has_jump or jump_used:
                raise ValueError("Jump Drive already used this activation")
            jump_used = True
        else:
            if steps_remaining <= 0:
                raise ValueError("Movement exceeds drive allowance")
            steps_remaining -= 1

        # Leaving current hex after validating movement points.
        _enforce_exit_pinning(state, src_hex, you, 1)
        _move_ship_between_hexes(state, you, ship_class, current_hex_id, next_hex_id)

        dst_hex = _require_hex(state, next_hex_id)
        enemy_in_dst = _count_enemy_ships(state, dst_hex, you)
        if idx < len(path) - 1:
            if dst_hex.has_gcds:
                raise ValueError("Cannot move through the Galactic Center while GCDS is active")
            if enemy_in_dst > 0:
                friendly_total = _count_friendly_ships(state, dst_hex, you)
                if friendly_total <= enemy_in_dst:
                    raise ValueError("Pinned upon entering contested hex")

        current_hex_id = next_hex_id

    # Re-add any interceptors transported in the bay to the final destination.
    if carried_interceptors:
        dest_hex = _require_hex(state, current_hex_id)
        dest_pieces = dest_hex.pieces.setdefault(you, Pieces())
        dest_pieces.ships["interceptor"] = dest_pieces.ships.get("interceptor", 0) + carried_interceptors


def _require_hex(state: GameState, hex_id: str) -> Hex:
    hx = state.map.hexes.get(hex_id)
    if hx is None:
        raise ValueError(f"Hex {hex_id} is not on the map")
    return hx


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


def _count_enemy_ships(state: GameState, hex_obj: Hex, pid: str) -> int:
    if not hex_obj:
        return 0
    _, enemy = ship_presence(state, hex_obj, pid)
    return enemy


def _count_friendly_ships(state: GameState, hex_obj: Hex, pid: str) -> int:
    if not hex_obj:
        return 0
    friendly, _ = ship_presence(state, hex_obj, pid)
    return friendly


def _enforce_exit_pinning(state: GameState, hex_obj: Hex, pid: str, leaving: int) -> None:
    enemy = _count_enemy_ships(state, hex_obj, pid)
    if enemy <= 0:
        return
    friendly = _count_friendly_ships(state, hex_obj, pid)
    if friendly - leaving < enemy:
        raise ValueError("Cannot leave contested hex without leaving pinned ships")
