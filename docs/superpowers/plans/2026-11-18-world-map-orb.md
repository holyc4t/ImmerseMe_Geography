# World Map Orb Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A land orb in the world map's top-left corner that shows, for whichever zone the map shows, what this character has learned there, with a "Best for" verdict.

**Architecture:** Two pure helpers in `Core.lua` (which map is a known zone, and what a reading is best for) with unit tests. A new `WorldMap.lua` builds the orb on the map, registered with `WorldMapFrame:AddOverlayFrame` when the client has it, otherwise a plain frame on the canvas. It reuses the minimap tooltip code, which `UI.lua` exports through `ns`.

**Tech Stack:** Lua 5.1, WoW: Forever client (`## Interface: 16001`), standalone `lua tests/run.lua`.

**Spec:** `docs/superpowers/specs/2026-11-18-world-map-orb-design.md`

## Global Constraints

- Only zones with at least one reading row show the orb. No "visited zones" tracking.
- Zone maps only (`mapType == Enum.UIMapType.Zone`, fallback value `3`). No orb on continent, world or dungeon maps.
- Never show resources the character has not gathered. The reading already guarantees this, so don't add a second source.
- No new textures. Ring is `Interface\Minimap\MiniMap-TrackingBorder`; the art is `ns.FacetIcon(land, "terrain")`.
- The minimap orb and its tooltip stay exactly as they are (no "Best for" line there).
- Setting `db.map` in `ImmerseMeGeographyDB`, default `true`, toggled by `/img map`.
- Work on a branch; the PR title is `feat: land orb on the world map` (minor release). The PR description is written for players.

## Review Focus

- `WorldMapFrame` may not exist when Geography loads (load-on-demand `Blizzard_WorldMap`): create the orb then, or on `ADDON_LOADED` of `Blizzard_WorldMap`. Never error at login.
- Zone with only uncertain/unconfirmed finds: the orb shows, the "Best for" line is left out (test in Task 1).
- Map name not in `ns.Zones`, `GetMapID()` nil, or `GetMapInfo` nil: the orb hides with no error (tests in Task 1 for `ZoneForMap`).
- Gathering while the map is open: the orb appears or updates live through `OnDiscoveryChanged` (manual check in Task 2).
- An error in map code must never break the stock map: every map-side refresh runs under `pcall`, reported once through `Print`, like `SafeRefresh`.

---

### Task 1: Pure helpers `ns.ZoneForMap` and `ns.BestFor`

**Files:**
- Modify: `Core.lua` (add after `ns.BuildReading`)
- Create: `tests/worldmap_spec.lua`
- Modify: `tests/run.lua:47` (add `"tests/worldmap_spec.lua"` to the spec list)

**Interfaces:**
- Produces: `ns.ZoneForMap(info) -> string|nil`, where `info` is a `C_Map.GetMapInfo` result or nil. Returns `info.name` when `info.mapType == ns.MAP_TYPE_ZONE` and `ns.Zones[info.name]` exists, otherwise nil. `ns.MAP_TYPE_ZONE = (Enum and Enum.UIMapType and Enum.UIMapType.Zone) or 3`.
- Produces: `ns.BestFor(reading, limit) -> { string, ... }`: `row.name` of the first `limit` (default 3) rows of `reading.rows` with `not row.uncertain and not row.unconfirmed`, in row order. Returns `{}` when there are none.

- [ ] **Step 1: Write the failing tests** in `tests/worldmap_spec.lua`:

```lua
test("ZoneForMap: known zone map", function()
	eq(ns.ZoneForMap({ name = "Teldrassil", mapType = 3 }), "Teldrassil")
end)
test("ZoneForMap: continent, dungeon, unknown, nil", function()
	eq(ns.ZoneForMap({ name = "Kalimdor", mapType = 2 }), nil, "continent")
	eq(ns.ZoneForMap({ name = "Teldrassil", mapType = 4 }), nil, "not a zone map")
	eq(ns.ZoneForMap({ name = "Nowhere", mapType = 3 }), nil, "unknown name")
	eq(ns.ZoneForMap(nil), nil, "no info")
end)
local function row(name, u, c) return { name = name, uncertain = u, unconfirmed = c } end
test("BestFor: first three sure rows in order", function()
	local r = { rows = { row("Copper Ore"), row("Peacebloom"), row("Tin Ore", true), row("Silverleaf"), row("Light Leather") } }
	eq(ns.BestFor(r), { "Copper Ore", "Peacebloom", "Silverleaf" })
	eq(ns.BestFor(r, 1), { "Copper Ore" }, "limit")
end)
test("BestFor: only unsure rows gives nothing", function()
	eq(ns.BestFor({ rows = { row("Tin Ore", true), row("Odd Thing", true, true) } }), {})
	eq(ns.BestFor({ rows = {} }), {})
end)
```

- [ ] **Step 2: Run, expect failure.** `lua tests/run.lua` gives `FAIL ZoneForMap: known zone map: ... attempt to call field 'ZoneForMap' (a nil value)`.
- [ ] **Step 3: Implement** both functions and `ns.MAP_TYPE_ZONE` in `Core.lua` as in the Interfaces block. They stay pure: no frames, and `C_Map` is never called.
- [ ] **Step 4: Run, expect pass.** `lua tests/run.lua` gives `63 passed, 0 failed`.
- [ ] **Step 5: Commit** on branch `feat/world-map-orb`: `git commit -m "feat: zone-map lookup and best-for verdict"`.

### Task 2: The orb on the world map

**Files:**
- Create: `WorldMap.lua`
- Modify: `ImmerseMe_Geography.toc` (add `WorldMap.lua` after `UI.lua`)
- Modify: `UI.lua`. Export `ns.AddLandLines = AddLandLines` and `ns.PlayerSeed = PlayerSeed`. Give `AddLandLines(r, withZone, bestFor)` an optional third argument: when it's a non-empty list, add `"Best for: " .. table.concat(bestFor, ", ")` in GOLD right after the zone/subzone header lines. The minimap callers pass nothing. In `SafeRefresh`, also call `ns.RefreshWorldMap()` when it's set. Add `DEFAULTS.map = true`, `/img map` (toggle `db.map`, print `"World map orb on."` / `"World map orb off."`, then `SafeRefresh()`), and a HELP line `"/img map - show or hide the land orb on the world map"`.
- Modify: `README.md` (one player-facing paragraph on the map orb and `/img map`).

**Interfaces:**
- Consumes: `ns.ZoneForMap`, `ns.BestFor` (Task 1), `ns.BuildReading`, `ns.FacetIcon`, `ns.AddLandLines(r, withZone, bestFor)`, `ns.PlayerSeed()`, `ns.Print`.
- Produces: `ns.RefreshWorldMap()` (safe to call any time, including before the map exists).

- [ ] **Step 1: Build the orb** in `WorldMap.lua`:
  - `Create()` runs once, when `WorldMapFrame` exists (at load, or on `ADDON_LOADED` arg `"Blizzard_WorldMap"`).
  - If `WorldMapFrame.AddOverlayFrame` exists, use `WorldMapFrame:AddOverlayFrame(nil, "Button", "TOPLEFT", WorldMapFrame:GetCanvasContainer(), "TOPLEFT", 4, -40)`. Define `frame.Refresh = ns.RefreshWorldMap` before the next map change.
  - Otherwise use `CreateFrame("Button", nil, WorldMapFrame.ScrollContainer or WorldMapFrame)` at the same anchor, plus `hooksecurefunc(WorldMapFrame, "OnMapChanged", ns.RefreshWorldMap)` and `WorldMapFrame:HookScript("OnShow", ns.RefreshWorldMap)`.
  - Size it 30×30 to start (tune in Step 3). Frame level above the canvas pins.
  - Art: the terrain texture with `SetTexCoord(0.1, 0.9, 0.1, 0.9)` and a circle mask (`Interface\CharacterFrame\TempPortraitAlphaMask`).
  - Ring: `MiniMap-TrackingBorder` at 54×54, `TOPLEFT` offset −5, 5 (same proportions as `UI.lua`'s fallback ring).
- [ ] **Step 2: Implement `ns.RefreshWorldMap()`** under `pcall`, reporting each distinct error once via `ns.Print`:
  - `zone = ns.ZoneForMap(C_Map.GetMapInfo(WorldMapFrame:GetMapID() or 0))`.
  - Then `r = ns.BuildReading(ImmerseMeGeographyCharDB, ns.skills, zone, "", false, ns.PlayerSeed())`.
  - Show the orb only if `ImmerseMeGeographyDB.map ~= false`, `zone` is set, and `#r.rows > 0`. Set the art to `ns.FacetIcon(r.land, "terrain")`.
  - OnEnter: `GameTooltip:SetOwner(self, "ANCHOR_RIGHT")`, `ns.AddLandLines(r, true, ns.BestFor(r))`, `Show()`. OnLeave hides it. If the tooltip is open on the orb during a refresh, rebuild it.
- [ ] **Step 3: Check in game.**
  - Run `lua tests/run.lua` and expect `63 passed, 0 failed`.
  - Copy `Core.lua`, `UI.lua`, `WorldMap.lua` and the `.toc` to `C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns\ImmerseMe_Geography\`.
  - The `.toc` changed, so restart the client. Then check each of these:
    - A zone where you've gathered shows the orb under Blizzard's top-left button with no overlap, and the tooltip has the "Best for" line.
    - An ungathered zone, Kalimdor and the world view show no orb.
    - Gathering with the map open makes the orb appear.
    - `/img map` toggles it.
    - The minimap tooltip is unchanged.
  - Adjust size and offset until it matches Blizzard's button.
- [ ] **Step 4: Commit** `git commit -m "feat: land orb on the world map"` and open the PR titled `feat: land orb on the world map` with a player-facing description.
