from typing import List

from .schema import MacroAction

def generate(state) -> List[MacroAction]:
    return [MacroAction("PASS", {"reason": "fallback"})]
