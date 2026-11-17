# How it works

## The land

Each zone in [`Data.lua`](../Data.lua) `ns.Zones` has four facets, each drawn as one icon:

| Facet | Values |
|---|---|
| Terrain | forest, grassland, hills, mountains, desert, badlands, swamp, jungle, tundra, coast, volcanic, blighted, underground, city |
| Ground underfoot | soil, mud, sand, rock, snow, ash, stone |
| Water | river, lake, sea, marsh, none |
| Wildness | settled, frontier, wild |

The terrain icon is drawn in the zone's own colours where the zone has a `tone`: the grassland of
Westfall and the Barrens is gold, Mulgore's is green. Tones exist for forest (dusk, pine, dead, violet),
grassland (gold), hills (red, dry), mountains (snow, brown, dark), badlands (tan, grey), coast (grey),
blighted (plague) and city (one per capital).

A sub-zone in `ns.SubZones` (a mine, a cave) replaces the facets it names while you stand in it.
In a dungeon or raid only the *underground* icon shows. Zones the data doesn't know get
grassland / soil / no water / wild.

## What the land holds

Each zone also lists its resources and their true level, from 1 (Scarce) to 3 (Plentiful). A sub-zone
with its own list is laid over the zone's while you're inside: the mine's ores win, the zone's herbs, game and fish still hold.

The addon shows a resource only when **both** of these are true:

1. Your character has the profession: Mining for ore, Herbalism for herbs, Skinning for leather, Fishing for fish.
2. Your character has gathered that resource **in this zone**.

How gathering is spotted: when you cast Mining, Herb Gathering, Skinning or Fishing, the addon remembers it.
If a loot window opens soon after (5 seconds, or 30 for fishing), the items in it that belong to that
profession are recorded against the zone and the sub-zone you're in. Loot from a mob or a chest
you open in that window is ignored unless it's that profession's own resource.

Discoveries are saved per character (`ImmerseMeGeographyCharDB`). Dropping a profession hides its
entries; learning it again brings them back.

## How sure you are

Each discovered resource gets a confidence between 0 and 1:

```
confidence = min(1, max(0, (skill - required) / 75) + gathers / 25)
```

`required` is the resource's own gathering requirement for ores and herbs. For fish and leather, it
is the zone's fishing level (`fishSkill`) or the level of its local game × 5 (`skinSkill`).

- At confidence 1 the reading is exact.
- Below 1 the reading is **uncertain**: the tooltip greys the level and adds a `?`. With
  chance `0.5 × (1 - confidence)` the shown level is one step off, up or down.

Whether a reading is off, and which way, comes from a hash of your character, the zone and the
resource. It doesn't change on `/reload`. It only changes when your skill or gather count moves.

## Hints

At skill 225 or more, if a zone holds a resource of your profession that you could gather but haven't
yet, the tooltip says *"There may be richer veins here you have not found."* It never names the resource.

## Unconfirmed

If you gather something the data doesn't list for that zone, it is still recorded. It shows as
*Common?* with **(unconfirmed)**, and stays uncertain whatever your skill, because there is no true
level to measure against. `/img known` lists these. Please report them so the data can be fixed.
