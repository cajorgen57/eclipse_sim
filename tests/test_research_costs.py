import json
import shutil
import types
from pathlib import Path

import pytest

from eclipse_ai.game_models import GameState, MapState, PlayerState, Resources
from eclipse_ai.technology import (
    ResearchError,
    discounted_cost,
    load_tech_definitions,
    validate_research,
)


def _make_state(defs):
    player = PlayerState(
        player_id="P1",
        color="orange",
        resources=Resources(money=5, science=0, materials=5),
        science=0,
        influence_discs=2,
    )
    state = GameState(
        round=1,
        active_player="P1",
        phase="action",
        players={"P1": player},
        map=MapState(),
        tech_bags={},
        market=[],
        tech_definitions=defs,
    )
    return state, player


def test_merge_applies_min_cost_as_base():
    defs = load_tech_definitions()
    seen = set()
    for tech in defs.values():
        if tech.id in seen:
            continue
        seen.add(tech.id)
        assert tech.base_cost == tech.cost_range[0]
        assert tech.cost_range[0] <= tech.cost_range[1]


def test_category_discount_only_regular():
    defs = load_tech_definitions()
    state, player = _make_state(defs)
    player.tech_count_by_category = {"military": 2, "rare": 3}

    plasma_cost = discounted_cost(player, defs["plasma_cannon"])
    rare_cost = discounted_cost(player, defs["rift_cannon"])

    assert plasma_cost == max(1, defs["plasma_cannon"].base_cost - 2)
    assert rare_cost == defs["rift_cannon"].base_cost


def test_affordability_uses_discounted_cost():
    defs = load_tech_definitions()
    state, player = _make_state(defs)
    state.market = ["plasma_cannon"]

    player.science = 2
    player.resources.science = 2
    player.tech_count_by_category = {"military": 2}

    validate_research(state, player, "plasma_cannon")

    player.tech_count_by_category = {}
    with pytest.raises(ResearchError, match="insufficient Science"):
        validate_research(state, player, "plasma_cannon")


def test_missing_name_creates_skeleton_entry(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    src_costs = repo_root / "eclipse_ai" / "data" / "tech_costs_second_dawn.json"
    src_data = repo_root / "eclipse_ai" / "data" / "tech.json"

    target_root = tmp_path
    (target_root / "eclipse_ai" / "data").mkdir(parents=True)
    shutil.copyfile(src_costs, target_root / "eclipse_ai" / "data" / "tech_costs_second_dawn.json")
    with open(src_data, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data["techs"] = [entry for entry in data["techs"] if entry["name"] != "Antimatter Cannon"]
    with open(target_root / "eclipse_ai" / "data" / "tech.json", "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)

    script_path = repo_root / "scripts" / "merge_tech_costs_second_dawn.py"
    module = types.ModuleType("merge_script")
    module.__file__ = str(target_root / "scripts" / "merge_tech_costs_second_dawn.py")
    target_script_dir = target_root / "scripts"
    target_script_dir.mkdir(parents=True, exist_ok=True)
    target_script_path = target_script_dir / "merge_tech_costs_second_dawn.py"
    target_script_path.write_text(script_path.read_text(encoding="utf-8"), encoding="utf-8")
    code = compile(target_script_path.read_text(encoding="utf-8"), module.__file__, "exec")
    exec(code, module.__dict__)

    module.main()

    updated = json.loads((target_root / "eclipse_ai" / "data" / "tech.json").read_text(encoding="utf-8"))
    names = {entry["name"] for entry in updated["techs"]}
    assert "Antimatter Cannon" in names
