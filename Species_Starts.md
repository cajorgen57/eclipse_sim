# Species_Starts.md

## Purpose

Reference all species starting positions from the base game, *Rise of the Ancients*, and *Shadows of the Rift*. Each block is declarative JSON, usable as a fixture overlay for `state_assembler`.

Fields:

* `name`
* `starting_sector` (hex ID from rulebook)
* `starting_resources` (money/science/materials)
* `starting_colonies`
* `starting_ships`
* `starting_techs`
* `traits`

---

## Base Game

```json
{
  "name": "Terrans",
  "starting_sector": 101,
  "starting_resources": {"money": 2, "science": 2, "materials": 2},
  "starting_colonies": {"home": {"money": 1, "science": 1, "materials": 1}},
  "starting_ships": {"interceptor": 2, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": [],
  "traits": []
}
```

```json
{
  "name": "Eridani",
  "starting_sector": 224,
  "starting_resources": {"money": 0, "science": 0, "materials": 0},
  "starting_colonies": {"home": {"money": 1, "science": 1, "materials": 1}},
  "starting_ships": {"interceptor": 0, "cruiser": 2, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Plasma Cannon"],
  "traits": ["Starts with fewer discs", "Weaker economy, stronger fleet"]
}
```

```json
{
  "name": "Hydrans",
  "starting_sector": 226,
  "starting_resources": {"money": 0, "science": 3, "materials": 0},
  "starting_colonies": {"home": {"science": 2, "materials": 1}},
  "starting_ships": {"interceptor": 2, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Advanced Mining"],
  "traits": ["Research-focused economy"]
}
```

```json
{
  "name": "Planta",
  "starting_sector": 228,
  "starting_resources": {"money": 0, "science": 0, "materials": 3},
  "starting_colonies": {"home": {"materials": 2}},
  "starting_ships": {"interceptor": 1, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": [],
  "traits": ["Root Network: may place influence in adjacent hexes", "Own hexes count as adjacent for movement"]
}
```
```json
{
  "name": "Orion Hegemony",
  "starting_sector": 230,
  "starting_resources": {"money": 3, "science": 3, "materials": 5},
  "starting_colonies": {"home": {"money": 1, "science": 1, "materials": 1}},
  "starting_ships": {"interceptor": 2, "cruiser": 1, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Gauss Shield"],
  "traits": ["Cheaper builds", "Combat bonuses"]
}
```
```json
{
  "name": "Mechanema",
  "starting_sector": 232,
  "starting_resources": {"money": 0, "science": 3, "materials": 0},
  "starting_colonies": {"home": {"science": 2, "materials": 1}},
  "starting_ships": {"interceptor": 2, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Positron Computer"],
  "traits": ["Upgrade up to 3 parts per action", "Research-focused"]
}
```
---

## Rise of the Ancients


```json
{
  "name": "Magellan",
  "starting_sector": 234,
  "starting_resources": {"money": 0, "science": 0, "materials": 3},
  "starting_colonies": {"home": {"materials": 2}},
  "starting_ships": {"interceptor": 2, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Fusion Drive"],
  "traits": ["Exploration advantage"]
}
```

```json
{
  "name": "Rho Indi Syndicate",
  "starting_sector": 237,
  "starting_resources": {"money": 3, "science": 3, "materials": 3,
  "starting_colonies": {"home": {"money": 2}},
  "starting_ships": {"interceptor": 0, "cruiser": 1, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Gluon Computer"],
  "traits": ["Pillage: gain money when destroying ships", "Trade 3:2 for money"]
}
```

```json
{
  "name": "Wardens",
  "starting_sector": 241,
  "starting_resources": {"money": 2, "science": 2, "materials": 1},
  "starting_colonies": {"home": {"money": 1, "science": 1, "materials": 1}},
  "starting_ships": {"interceptor": 2, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Rift Cannon"],
  "traits": ["Immune to anomalies"]
}
```

```json
{
  "name": "Exiles",
  "starting_sector": 243,
  "starting_resources": {"money": 2, "science": 3, "materials": 0},
  "starting_colonies": {"home": {"science": 2}},
  "starting_ships": {"interceptor": 0, "cruiser": 1, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Wormhole Generator"],
  "traits": ["Free discovery on tech threshold", "Orbital focus"]
}
```
```json
{
  "name": "Enlightened of Lyra",
  "starting_sector": 244,
  "starting_resources": {"money": 2, "science": 2, "materials": 2},
  "starting_colonies": {"home": {"money": 1, "science": 1, "materials": 1}},
  "starting_ships": {"interceptor": 2, "cruiser": 0, "dreadnought": 0, "starbase": 0},
  "starting_techs": ["Plasma Missile"],
  "traits": ["Diplomacy bonus", "Flexible research"]
}
```

---

## Shadows of the Rift




---

### Notes

* Sector IDs come from the PDFs (224, 226, 228, 230, etc.).
* Starting cubes and techs are faithfully transcribed from setup rules.
* Place JSONs in `tests/fixtures/species/` with file names matching species.

---

Do you want me to **fill in every home hex planet composition (exact cube colors per planet)** too, so the AI can directly assemble the starting map without lookup?
