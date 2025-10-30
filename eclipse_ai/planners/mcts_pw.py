"""Progressive Widening Monte Carlo Tree Search planner."""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from typing import Any, Iterator, List, Optional

from .. import evaluator, round_flow
from ..action_gen import generate_all
from ..action_gen.schema import MacroAction
from ..hashing import hash_state


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

    def __post_init__(self) -> None:
        if self.children is None:
            self.children = []
        if self._action_iter is None:
            self._action_iter = iter(generate_all(self.state))
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
    ) -> None:
        self.pw_c = pw_c
        self.pw_alpha = pw_alpha
        self.prior_scale = prior_scale
        self.sims = sims
        self.depth = depth
        random.seed(seed)
        self.tt: dict[int, tuple[int, float]] = {}

    def ucb(self, child: Node, parent_visits: int, c: float = 1.414) -> float:
        q = (child.value / child.visits) if child.visits else 0.0
        u = c * math.sqrt(math.log(parent_visits + 1) / (child.visits + 1))
        pb = self.prior_scale * child.prior / (1 + child.visits)
        return q + u + pb

    def apply(self, state: Any, mac: MacroAction) -> Any:
        """Apply a macro action to the state using the legacy round_flow bridge."""

        raw = mac.payload.get("__raw__")
        if raw is None:
            raise NotImplementedError(f"No applier for macro type {mac.type}")
        next_state = copy.deepcopy(state)
        round_flow.take_action(next_state, raw)
        return next_state

    def rollout(self, leaf: Node) -> float:
        """Perform a depth-limited rollout from the leaf node."""

        state_copy = copy.deepcopy(leaf.state)
        remaining_depth = self.depth
        while remaining_depth > 0:
            try:
                mac = next(iter(generate_all(state_copy)))
            except StopIteration:
                break
            if mac.type == "PASS":
                break
            state_copy = self.apply(state_copy, mac)
            remaining_depth -= 1
        try:
            return float(evaluator.evaluate_state(state_copy))
        except Exception:  # pragma: no cover - evaluator may not be wired in tests
            return 0.0

    def plan(self, root_state: Any) -> List[Optional[MacroAction]]:
        """Run PW-MCTS simulations and return actions sorted by value."""

        root = Node(root_state, None, None, prior=0.0)
        for _ in range(self.sims):
            node = root
            while node.children and not node.can_expand(self.pw_c, self.pw_alpha):
                node = max(node.children, key=lambda child: self.ucb(child, node.visits))
            if node.can_expand(self.pw_c, self.pw_alpha):
                try:
                    mac = next(node._action_iter)
                    child_state = self.apply(node.state, mac) if mac.type != "PASS" else node.state
                    child = Node(child_state, node, mac, prior=mac.prior)
                    node.children.append(child)
                    node = child
                except StopIteration:
                    node.fully_expanded = True
                    node._action_iter = None
            value = self.rollout(node)
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
