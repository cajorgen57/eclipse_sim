from .schema import MacroAction

def score_macro_action(state, mac: MacroAction) -> float:
    base = {"RESEARCH":0.6,"UPGRADE":0.5,"BUILD":0.5,"EXPLORE":0.4,"MOVE_FIGHT":0.4,"INFLUENCE":0.3,"DIPLOMACY":0.2,"PASS":0.0}.get(mac.type,0.1)
    return float(base)
