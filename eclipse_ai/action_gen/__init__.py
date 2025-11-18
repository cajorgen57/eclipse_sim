from typing import Any, Iterable, List

from . import actions, prior, explore, research, build, upgrade, move_fight, pass_action
from .schema import MacroAction


def _collect(state, context: Any | None = None) -> List[MacroAction]:
    """Collect all macro actions from various generators."""
    macros: List[MacroAction] = []
    for gen in (actions, explore, research, build, upgrade, move_fight, pass_action):
        generator = getattr(gen, "generate")
        try:
            produced = generator(state, context=context)
        except TypeError:
            produced = generator(state)
        macros.extend(produced)
    return macros


def generate_all(state, context: Any | None = None) -> Iterable[MacroAction]:
    macros = _collect(state, context=context)
    scored = [
        MacroAction(m.type, dict(m.payload), prior.score_macro_action(state, m, context=context))
        for m in macros
    ]
    scored.sort(key=lambda m: m.prior, reverse=True)
    for m in scored:
        yield m
