import json
import re
import sys
import unicodedata
from pathlib import Path


def norm(value: str) -> str:
    slug = unicodedata.normalize("NFKD", value).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    src_path = root / "eclipse_ai" / "data" / "tech_costs_second_dawn.json"
    db_path = root / "eclipse_ai" / "data" / "tech.json"

    src = json.loads(src_path.read_text(encoding="utf-8"))
    db = json.loads(db_path.read_text(encoding="utf-8"))

    rows = []
    for category, entries in src.get("regular_tech", {}).items():
        for row in entries:
            rows.append((row["name"], category, int(row["min_cost"]), int(row["max_cost"]), False))
    for row in src.get("rare_technologies", []):
        rows.append((row["name"], "Rare", int(row["min_cost"]), int(row["max_cost"]), True))

    index = {name: (category, mn, mx, rare) for name, category, mn, mx, rare in rows}

    techs = db.get("techs") if isinstance(db, dict) else db
    if techs is None:
        techs = []
        if isinstance(db, dict):
            db["techs"] = techs
        else:
            db = {"techs": techs}

    name_map = {entry.get("name"): entry for entry in techs if isinstance(entry, dict)}
    for name, (category, mn, mx, rare) in index.items():
        entry = name_map.get(name)
        if entry is None:
            entry = {
                "id": norm(name),
                "name": name,
                "category": category,
                "is_rare": rare,
                "base_cost": mn,
                "cost_range": [mn, mx],
                "grants_parts": [],
                "grants_structures": [],
                "immediate_effect": None,
                "prerequisites": [],
                "notes": "",
                "sources": ["Second Dawn cost import"],
            }
            techs.append(entry)
            name_map[name] = entry
            continue

        entry["category"] = category
        entry["is_rare"] = rare
        entry["base_cost"] = mn
        entry["cost_range"] = [mn, mx]
        sources = entry.setdefault("sources", [])
        if "Second Dawn cost import" not in sources:
            sources.append("Second Dawn cost import")

    db_path.write_text(json.dumps(db, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"OK: merged costs for {len(index)} techs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
