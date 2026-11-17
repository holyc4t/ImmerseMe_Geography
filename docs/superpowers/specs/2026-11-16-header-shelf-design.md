# ImmerseMe: Geography — header shelf (readout redesign)

Date: 2026-11-16 · Author: holyc4t · Status: draft for approval · Size: small change (UI.lua, docs)

## Intent

The readout on the minimap's curve stacks outward into the default buff / debuff area and reads
as a bolt-on. Geography should look like part of the stock minimap: the zone header says where
you are, and Geography says what that place is like, right there with it.

## Goals

- The four land icons (terrain, ground, water, wildness) sit in one row attached to the stock
  minimap header, on the minimap side of it, left-aligned with the header's left end. That band
  between the header and the circle is empty today and lies inside the minimap cluster, so it
  cannot reach buffs or debuffs.
- The row follows the header: under it when the header is on top, above it when Edit Mode's
  "header underneath" is on. Detected from where the header actually is, so no client API guess.
- Profession / resource information is hover-only. Nothing about ores, herbs, game or fish is
  drawn on screen.
- Hovering the icons shows the full Geography tooltip. Hovering the stock zone name shows the
  stock tooltip with Geography's lines added, so the header itself answers "what is this land".
- Icons drawn larger (18 px, from 15) from the existing 64 px art. No custom outlined font on
  screen; any text uses the stock Blizzard fonts.

## Non-goals

- Replacing the stock header frame, zone name, clock or their styling.
- Redrawing the icon art in a painted style (separate piece of work if wanted).
- Changing ImmerseMe: Weather. Its lower-left text stays where it is.

## Anti-goals

- Anything that sticks out left of the minimap cluster.
- Covering the tracking button, clock, calendar or Weather's sky orb.

## Approaches

| | Approach | Trade-off |
|---|---|---|
| A | Icons inside the header bar, next to the zone name | Most integrated, but the bar has ~100 px for the name; four icons leave ~45 px, so most zone names would be cut off |
| **B** | **Icon row attached to the header, in the empty band between header and circle** | **Picked (my call).** Reads as part of the header, never truncates the name, follows header up / down |
| C | Icons riding the minimap rim | Compact, but still "on the curve", which the user wants to move away from |

## Details (my calls)

- Anchor: `MinimapCluster.BorderTop` if present, else `MinimapZoneTextButton`, else the
  minimap's top-left corner.
- Settings: `/img size <12-24>`, `/img x <n>`, `/img y <n>` nudges, `/img show | hide`,
  `/img reset`. Removed: `rows`, `arc`, `gap`, `font`, `words` (saved-settings version 4 clears them).
- The resource cells, tier pips on the minimap and the Weather arc tip are removed. The tooltip
  keeps the per-profession list unchanged.
- With the header underneath, the row sits in the bottom-left corner and may touch Weather's
  last line; `/imw arc high` or `/img x` resolves it.

## Left to the builder

Exact pixel offsets, to be tuned in game.
