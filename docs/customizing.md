# Customizing

Everything about the land lives in [`Data.lua`](../Data.lua), which is safe to edit.
After editing, `/reload` in game. Run `lua tests/run.lua` from the repo root to check the data.

## Add or fix a zone

```lua
ns.Zones = {
	["Westfall"] = { terrain = "grassland", tone = "gold", ground = "soil", water = "sea", wild = "frontier",
		fishSkill = 55, skinSkill = 75,
		flavor = "Fallow fields run to the sea; scarecrows stand guard over empty farms.",
		res = { copper = 3, tin = 2, silver = 1, peacebloom = 2, lightleather = 3, mackerel = 3 } },
}
```

- The name must match `GetRealZoneText()` (the zone name above the minimap). Dungeons use their own name.
- Facet values must be one of those listed in `ns.Facets`.
- `tone` is optional: it draws the terrain icon in the zone's own colours (Westfall's grassland is
  gold, not green). It must be one of the tones `ns.TerrainTones` lists for that terrain.
- `res` keys are resource keys from `ns.Resources`; the values are 1 (Scarce), 2 (Common) or 3 (Plentiful).
- `fishSkill` is the fishing skill the zone's waters ask for; `skinSkill` is the skinning skill its
  typical game asks for (mob level × 5).

## Add a mine or cave

```lua
ns.SubZones = {
	["Jangolode Mine"] = { terrain = "underground", ground = "stone", water = "none",
		flavor = "A worked-out mine, still rich enough to be worth the risk.",
		res = { copper = 3, tin = 2, silver = 1 } },
}
```

The name must match `GetSubZoneText()`. Facets you name replace the zone's. A `res` table is laid over
the zone's list while you're inside: its entries win, the rest of the zone's list still holds.

## Add a resource

```lua
ns.Resources = {
	copper = { cat = "ore", items = { 2770 }, short = "Copper", name = "Copper Ore", req = 1 },
}
```

- `cat` is `ore`, `herb`, `hide` or `fish`.
- `items` lists every item ID that counts as gathering it (`/img debug` prints the IDs you loot).
- `short` is the minimap name and `name` the tooltip name.
- `req` is the gathering skill required (ore and herb only).

## Restyle the art

The icons are drawn by [`tools/make_icons.py`](../tools/make_icons.py). Edit a drawing function, then:

```
py tools/make_icons.py
py tools/preview_icons.py
```

Then fully restart the client: new textures aren't picked up by `/reload`.

### Add a zone colouring

Each terrain is drawn from a palette, so one drawing serves every tone. To give a terrain a new tone:

1. Add the palette to `TERRAIN_TONES` in `tools/make_icons.py` (only the colours that differ from the
   terrain's own look), and run the two commands above. That writes
   `Media/land_terrain_<terrain>_<tone>.tga`.
2. List the tone under its terrain in `ns.TerrainTones` in `Data.lua`.
3. Give it to a zone with `tone = "<tone>"`.

`lua tests/run.lua` fails if a tone has no texture, if no zone uses it, or if `Media/` holds a texture
the addon never asks for.
