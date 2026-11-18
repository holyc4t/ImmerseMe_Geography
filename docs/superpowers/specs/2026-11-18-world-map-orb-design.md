# World map orb (design)

Date: 2026-11-18. Size: small change.

## Intent

When farming, the player wants to plan where to go. Opening the world map on any zone should show
what this character has learned about that zone (its land and its gathering resources) and say what
it is best for, in a way that looks like part of Blizzard's own map.

## Goals

- A land orb in the top-left corner of the world map canvas, for whichever zone the map shows
  (not only the zone the player stands in).
- Hover tooltip: the same content as the minimap orb tooltip (zone header, land facets, flavour,
  per-profession resource rows), computed for the shown zone, plus a "Best for" verdict line at
  the top.
- Looks native: Blizzard's gold map-button ring (`Interface\Minimap\MiniMap-TrackingBorder`, as the
  minimap fallback already uses), same size as the map's own corner buttons, terrain art inside.

## Non-goals / anti-goals

- No orb for unexplored zones: a zone with no entries in `ImmerseMeGeographyCharDB.disc[zone]`
  shows nothing at all. No new "visited zones" tracking (user decision).
- No orb on continent or world views (zone maps only). My call: those views span many zones.
- Never reveal resources the character has not gathered (same rule as the minimap).
- No new textures, no change to the minimap orb's look or behaviour, nothing shared with sibling
  addons.

## Approaches

- **A, chosen:** register via `WorldMapFrame:AddOverlayFrame(...)`, the map's own mechanism for
  corner controls (the map anchors it and calls `Refresh()` on every map change), anchored
  top-left below Blizzard's existing button.
- **B, fallback when A's API is missing:** plain frame parented to the map's canvas container,
  anchored top-left, refreshed from `WorldMapFrame:OnMapChanged` (hooksecurefunc) and `OnShow`.
  Works everywhere but the position is hard-coded and could collide with other map addons.
- **C, rejected:** a map pin (data provider) at a map coordinate. It pans and zooms with the map,
  while the user asked for a fixed corner.

## Design

- **Which zone:** `WorldMapFrame:GetMapID()`, then `C_Map.GetMapInfo(id)`. Only `mapType ==
  Enum.UIMapType.Zone` (fallback: value 3) counts. The name is looked up in `ns.Zones`; unknown names
  hide the orb.
- **Reading:** `ns.BuildReading(charDB, ns.skills, zoneName, "", false, PlayerSeed())`. The orb shows
  only when `reading.rows` is non-empty. Rows already exist only for the character's current
  gathering professions, so a dropped profession's finds stay hidden.
- **Verdict:** a new pure `ns.BestFor(reading)` in `Core.lua`: up to 3 resource names from the top of
  `reading.rows` (already sorted tier, then count), skipping uncertain or unconfirmed rows. Tooltip
  line: `Best for: Copper Ore, Peacebloom` in gold, with no line if nothing qualifies. Unit tested in
  `tests/`.
- **Tooltip:** reuse `AddLandLines(reading, true)`, with the verdict line inserted after the zone
  header. Anchored `ANCHOR_RIGHT` of the orb so it stays inside the map.
- **Render:** the terrain facet icon (`ns.FacetIcon(land, "terrain")`), cropped and circle-masked
  like the minimap orb, inside the ring. Refresh on map change, on map show, and on
  `OnDiscoveryChanged` while the map is open (so a fresh gather updates it live).
- **Setting:** `/img map` toggles it (`db.map`, default on).

## Left to the builder

- Exact size and offset under Blizzard's top-left button, checked in game.
- Whether this client's map has `AddOverlayFrame`. Keep the B fallback either way.
- README and CHANGELOG lines for players.
