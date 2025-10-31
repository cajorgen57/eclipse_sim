"""Progressive Widening Monte Carlo Tree Search planner."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional

from .. import evaluator, round_flow
from ..action_gen import generate as generate_legacy  # renamed old entrypoint
from ..action_gen.schema import MacroAction
from ..context import Context
from ..hashing import hash_state
from ..hidden_info import determinize
from ..opponents import analyze_state

# new imports
from eclipse_ai.rules import api as rules_api
from eclipse_ai import validators


@dataclass
class Node:
    """Tree node for progressive-widening MCTS."""

    state: Any
    parent: Optional["Node"]
    action_from_parent: Optional[MacroAction]
    prior: float = 0.0
    visits: int = 0
    value: float = 0.0
    zkey: int = 0
    children: List["Node"] | None = None
    _action_iter: Iterator[MacroAction] | None = None
    _k_open: int = 0
    fully_expanded: bool = False
    context: Context | None = None
    player_id: int | str | None = None

    def __post_init__(self) -> None:
        if self.children is None:
            self.children = []
        # infer player
        if self.player_id is None:
            self.player_id = getattr(self.state, "active_player", None) or getattr(
                self.state, "active_player_id", None
            )
            if self.player_id is None and isinstance(self.state, dict):
                self.player_id = self.state.get("active_player") or self.state.get("active_player_id")

        # we keep the legacy generator but it is now centralized
        if self._action_iter is None:
            self._action_iter = iter(generate_legacy(self.state))

        self.zkey = hash_state(self.state)

    def can_expand(self, c: float, alpha: float) -> bool:
        if self.fully_expanded:
            return False
        allowed = int(c * (self.visits ** alpha))
        if allowed > self._k_open:
            self._k_open = allowed
        return len(self.children) < self._k_open


class PW_MCTSPlanner:
    """Progressive-widening MCTS planner operating on macro actions."""

    def __init__(
        self,
        pw_c: float = 1.5,
        pw_alpha: float = 0.6,
        prior_scale: float = 0.5,
        sims: int = 200,
        depth: int = 2,
        seed: int = 0,
        opponent_awareness: bool = True,
    ) -> None:
        self.pw_c = pw_c
        self.pw_alpha = pw_alpha
        self.prior_scale = prior_scale
        self.sims = sims
        self.depth = depth
        random.seed(seed)
        self.tt: dict[int, tuple[int, float]] = {}
        self.opponent_awareness = opponent_awareness
        self._seed = seed

    def ucb(self, child: Node, parent_visits: int, c: float = 1.414) -> float:
        q = (child.value / child.visits) if child.visits else 0.0
        u = c * math.sqrt(math.log(parent_visits + 1) / (child.visits + 1))
        pb = self.prior_scale * child.prior / (1 + child.visits)
        return q + u + pb

    def apply(self, state: Any, mac: MacroAction, player_id: int | str | None = None) -> Any:
        """
        Apply a macro action to the state.

        New behavior:
        - use centralized rules to apply the action if we can
        - fall back to legacy round_flow for raw actions
        """
        raw = mac.payload.get("__raw__")

        # try centralized path first
        act_type = mac.type
        payload = dict(mac.payload)
        payload.pop("__raw__", None)
        action_dict = {"type": act_type, "payload": payload}

        pid = player_id
        if pid is None:
            pid = getattr(state, "active_player", None) or getattr(state, "active_player_id", None)
            if pid is None and isinstance(state, dict):
                pid = state.get("active_player") or state.get("active_player_id")

        if pid is not None and validators._is_action_legal(state, pid, action_dict):
            # pure transition
            return rules_api.apply_action(state, pid, action_dict)

        # fallback: legacy bridge
        if raw is None:
            raise NotImplementedError(f"No applier for macro type {mac.type}")
        next_state = copy.deepcopy(state)
        round_flow.take_action(next_state, raw)
        return next_state

    def rollout(self, leaf: Node) -> float:
        """Perform a depth-limited rollout from the leaf node."""

        state_copy = copy.deepcopy(leaf.state)
        remaining_depth = self.depth
        ctx = getattr(leaf, "context", None)
        pid = leaf.player_id
        while remaining_depth > 0:
            try:
                mac = next(iter(generate_legacy(state_copy)))
            except StopIteration:
                break
            if mac.type == "PASS":
                break
            state_copy = self.apply(state_copy, mac, player_id=pid)
            # refresh player if state changed turn
            pid = getattr(state_copy, "active_player", None) or getattr(
                state_copy, "active_player_id", None
            ) or (state_copy.get("active_player") if isinstance(state_copy, dict) else pid)
            remaining_depth -= 1
        try:
            return float(evaluator.evaluate_state(state_copy, context=ctx))
        except Exception:  # evaluator may not be wired in tests
            return 0.0

    def plan(self, root_state: Any) -> List[Optional[MacroAction]]:
        """Run PW-MCTS simulations and return actions sorted by value."""

        det = determinize(root_state)
        rd = getattr(root_state, "round_index", getattr(det, "round_index", 0))
        me_id = getattr(root_state, "active_player_id", getattr(det, "active_player_id", 0))
        if self.opponent_awareness:
            models, tmap = analyze_state(det, my_id=me_id, round_idx=rd)
            context = Context(opponent_models=models, threat_map=tmap, round_index=rd)
        else:
            context = Context(round_index=rd)
        root = Node(det, None, None, prior=0.0, context=context, player_id=me_id)
        for _ in range(self.sims):
            node = root
            # selection
            while node.children and not node.can_expand(self.pw_c, self.pw_alpha):
                node = max(node.children, key=lambda child: self.ucb(child, node.visits))
            # expansion
            if node.can_expand(self.pw_c, self.pw_alpha):
                try:
                    mac = next(node._action_iter)
                    child_state = self.apply(node.state, mac, player_id=node.player_id) if mac.type != "PASS" else node.state
                    # determine next player
                    next_pid = getattr(child_state, "active_player", None) or getattr(
                        child_state, "active_player_id", None
                    )
                    if next_pid is None and isinstance(child_state, dict):
                        next_pid = child_state.get("active_player") or child_state.get("active_player_id", node.player_id)
                    child_context = getattr(node, "context", None)
                    child = Node(
                        child_state,
                        node,
                        mac,
                        prior=mac.prior,
                        context=child_context,
                        player_id=next_pid,
                    )
                    node.children.append(child)
                    node = child
                except StopIteration:
                    node.fully_expanded = True
                    node._action_iter = None
            # rollout
            value = self.rollout(node)
            # backup
            while node is not None:
                node.visits += 1
                node.value += value
                v_vis, v_val = self.tt.get(node.zkey, (0, 0.0))
                self.tt[node.zkey] = (v_vis + 1, v_val + value)
                node = node.parent
        if not root.children:
            return []
        root.children.sort(key=lambda child: (child.value / max(1, child.visits)), reverse=True)
        return [child.action_from_parent for child in root.children]

    def _root_child_stats(self, root):
        stats = []
        for ch in root.children:
            mac = ch.action_from_parent
            stats.append({
                "type": getattr(mac, "type", "?"),
                "prior": float(getattr(ch, "prior", 0.0)),
                "visits": int(getattr(ch, "visits", 0)),
                "mean_value": float(ch.value / max(1, ch.visits)),
                "payload": dict(getattr(mac, "payload", {})),
            })
        stats.sort(key=lambda x: x["mean_value"], reverse=True)
        return stats

    def plan_with_diagnostics(self, root_state):
        # you can make the same apply() change here too if you want full symmetry
        root = Node(root_state, None, None, prior=0.0)
        for _ in range(self.sims):
            node = root
            while node.children and not node.can_expand(self.pw_c, self.pw_alpha):
                node = max(node.children, key=lambda ch: self.ucb(ch, node.visits))
            if node.can_expand(self.pw_c, self.pw_alpha):
                try:
                    mac = next(node._action_iter)
                    child_state = self.apply(node.state, mac) if mac.type != "PASS" else node.state
                    child = Node(child_state, node, mac, prior=mac.prior)
                    if hasattr(node, "context"):
                        child.context = node.context
                    node.children.append(child)
                    node = child
                except StopIteration:
                    pass
            v = self.rollout(node)
            while node is not None:
                node.visits += 1
                node.value += v
                node = node.parent

        if not root.children:
            return [], {
                "children": [],
                "sims": self.sims,
                "depth": self.depth,
                "seed": getattr(self, "_seed", 0),
                "params": {
                    "pw_alpha": self.pw_alpha,
                    "pw_c": self.pw_c,
                    "prior_scale": self.prior_scale,
                },
            }
        root.children.sort(key=lambda ch: (ch.value / max(1, ch.visits)), reverse=True)
        di = {
            "children": self._root_child_stats(root),
            "sims": self.sims,
            "depth": self.depth,
            "seed": getattr(self, "_seed", 0),
            "params": {
                "pw_alpha": self.pw_alpha,
                "pw_c": self.pw_c,
                "prior_scale": self.prior_scale,
            },
        }
        return [ch.action_from_parent for ch in root.children], di


