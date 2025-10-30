from typing import Iterable, List

from . import prior, explore, research, build, upgrade, move_fight, diplomacy, pass_action
from .schema import MacroAction


def _collect(state) -> List[MacroAction]:
    macros: List[MacroAction] = []
    for gen in (explore, research, build, upgrade, move_fight, diplomacy, pass_action):
        macros.extend(gen.generate(state))
    return macros


def generate_all(state) -> Iterable[MacroAction]:
    macros = _collect(state)
    scored = [MacroAction(m.type, dict(m.payload), prior.score_macro_action(state, m)) for m in macros]
    scored.sort(key=lambda m: m.prior, reverse=True)
    for m in scored:
        yield m
