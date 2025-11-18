# Eclipse: New Dawn for the Galaxy - Setup Guide

This document describes the core board setup and starting state configuration for **Eclipse: New Dawn for the Galaxy** (1st edition). This guide covers Terran players; alien species setup will be documented separately.

## Core Board Setup

### Galactic Center
- Place the **Galactic Center** hex in the middle of the play area
- Place **1 Discovery tile face-down** on the Galactic Center
- Place the **GCDS tile** on top of the Discovery tile

### Sector Stacks
- Create **three face-down sector stacks**:
  - **Inner (I)**: Full set (8 hexes, hex IDs 101-108)
  - **Middle (II)**: Full set (11 hexes, hex IDs 201-211)
  - **Outer (III)**: Limited by player count (see table below)
- The Outer (III) stack is limited by player count; Inner and Middle use the full sets
- **Start Player** is determined by: the person who has spent the least time on Earth

### Technology and Supply Setup
- Bag and shuffle **Technology tiles**, then draw onto the Research tracks using the tech-tile counts below
- Shuffle and set out:
  - **Discovery tiles**
  - **Reputation tiles**
- Place on supply board:
  - **Ship Part tiles**
  - **Orbitals/Monoliths**
  - **Ancients**
  - **Round marker**

## Player Setup (Terran)

For each player:

### Components
- Take **all ships, ambassadors, influence discs, population cubes** in one color
- Take **3 Colony Ship tiles**
- Take a **summary card**

### Player Board Setup
On your player board:

1. **Influence Track**
   - Place **1 disc** on each circle of the Influence track

2. **Resource Tracks**
   - Place **population cubes** on every square of Money/Science/Materials tracks **except** the rightmost light square
   - This means: fill all tracks except the last light square on each

3. **Storage Markers**
   - Set **Storage markers** to:
     - **Money: 2**
     - **Science: 3**
     - **Materials: 3**

### Starting Sector Setup
On your **Starting Sector** (placed two hexes from center in the middle ring, closest spot to you):

1. **Ships**
   - Place **1 Interceptor** on the sector

2. **Colonies**
   - Move **1 population cube** of each resource type (Money, Science, Materials) to the matching planet squares on the sector

3. **Influence**
   - Place **1 influence disc** on the sector

### Starting Sector Placement Rules
- Starting sectors are placed at the six middle-ring entry points
- Each sector is **two hexes from the Galactic Center**
- In 2–5 player games, only the nearest needed entry points are used
- Players should place their starting sector closest to their position at the table

## Setup Counts by Player Number

Use these counts during setup:

| Players | Outer (III) Sectors | Tech Tiles on Tracks |
|---------|-------------------:|---------------------:|
| 2       | **5**              | **12**               |
| 3       | **10**             | **14**               |
| 4       | **14**             | **16**               |
| 5       | **16**             | **18**               |
| 6       | **18**             | **20**               |

**Note**: These counts come directly from the rulebook's setup table.

## Table Layout Tips

1. **Outer (III) Stack Visibility**
   - Keep the Outer (III) stack visible; it's the only stack limited by player count
   - Inner (I) and Middle (II) stacks always use the full sets

2. **Starting Sector Placement**
   - Starting sectors are placed at the six middle-ring entry points
   - Each sector is two hexes from the Galactic Center
   - In games with fewer than 6 players, only use the nearest needed entry points

3. **First Game Recommendation**
   - For a first game, use **Terrans** for all players
   - Alien species can be added in subsequent games

## Terran Starting Configuration Summary

**Starting Resources:**
- Money: 2 (from storage marker)
- Science: 3 (from storage marker)
- Materials: 3 (from storage marker)

**Starting Ships:**
- 1 Interceptor (on starting sector)

**Starting Colonies:**
- 1 Money cube (placed on planet)
- 1 Science cube (placed on planet)
- 1 Materials cube (placed on planet)

**Starting Tech:**
- None (Terrans start with no technologies)

**Starting Influence:**
- All discs on Influence track (default starting position)
- 1 disc on starting sector

**Colony Ships:**
- 3 Colony Ship tiles (face-up, available)

## Round Mechanics

### Tech Tile Replenishment (Cleanup Phase)

At the end of each round during the **Cleanup Phase**, new technology tiles are drawn from the bag and placed on the Research tracks. The number of tiles drawn depends on player count:

| Players | Tech Tiles Drawn Per Round |
|---------|---------------------------|
| 2       | 5                         |
| 3       | 6                         |
| 4       | 7                         |
| 5       | 8                         |
| 6       | 9                         |

**Note:** This is different from the initial tech tile count during setup. Initial setup uses the values from the "Tech tiles to draw" table above, while each subsequent round draws according to this table.

### Round Structure

Each round follows this sequence:

1. **Action Phase** - Players take turns performing actions or passing until all have passed
2. **Combat Phase** - Resolve battles in hexes with multiple players' ships
3. **Upkeep Phase** - Players collect resources and pay influence upkeep
4. **Cleanup Phase** - Draw new tech tiles, reset action discs, refresh colony ships

## Notes

- This guide is for **Eclipse: New Dawn for the Galaxy (1st edition)**
- For **Second Dawn (2nd edition)**, there are small differences (documentation to be added)
- Alien species starting configurations will be documented separately
- See `Species_Starts.md` for species-specific starting data

## References

- Rulebook: [Eclipse Rulebook - 1jour-1jeu.com](https://cdn.1j1ju.com/medias/48/0e/83-eclipse-rulebook.pdf)
- Species data: `eclipse_ai/data/species.json`
- Species starts reference: `Species_Starts.md`

