# ImmerseMe: Geography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A WoW: Forever addon that shows the land around you (terrain, ground, water, wildness) as minimap icons, plus the gathering resources your character has learned through their professions, with accuracy that grows with skill.

**Architecture:** Same split as ImmerseMe_Weather: `Data.lua` (tweakable tables), `Core.lua` (pure logic: no frames, no events, unit-tested outside the game), `Gather.lua` (WoW event glue: casts, loot, skills), `UI.lua` (minimap readout, tooltip, slash commands). Discoveries live in a per-character saved variable; the zone "truth" ships in `Data.lua`.

**Tech Stack:** Lua 5.1 (WoW client, interface 16001); standalone Lua for tests (`lua tests/run.lua`, no test framework, tiny asserts); Python 3 (`py`) with no deps for icon generation; BigWigs packager for releases.

**Spec:** `docs/superpowers/specs/2026-11-16-geography-design.md`. Sibling reference: `../ImmerseMe_Weather` (copy its patterns, colours and layout maths).

## Global Constraints

- Folder/repo: `C:\Users\serge\dev\world_of_warcraft\ImmerseMe_Geography`, its own git repo on `main`, sibling of ImmerseMe_Weather.
- TOC: `## Interface: 16001`, `## Title: ImmerseMe: Geography`, `## Author: holyc4t`, `## X-Category: Roleplay`, `## X-Suite: ImmerseMe`, `## X-License: MIT`, `## IconTexture: Interface\AddOns\ImmerseMe_Geography\Media\icon`, `## SavedVariables: ImmerseMeGeographyDB`, `## SavedVariablesPerCharacter: ImmerseMeGeographyCharDB`. Load order: `Data.lua`, `Core.lua`, `Gather.lua`, `UI.lua`.
- Author/copyright everywhere: **holyc4t**. MIT licence.
- Slash commands `/img` and `/geography`. Chat prefix `|cffd8b25aImmerseMe: Geography|r`.
- Lua texture paths use double backslashes (`"Interface\\AddOns\\..."`); a lone `\X` silently breaks the path.
- Minimap shows **no numbers** for resources: only short name + tier icon. Tiers: `1 = low/Scarce`, `2 = medium/Common`, `3 = high/Plentiful`.
- Profession-gated: Mining → `ore`, Herbalism → `herb`, Skinning → `hide`, Fishing → `fish`. No profession → that category shows nothing anywhere (data kept).
- Readout font `STANDARD_TEXT_FONT`, `OUTLINE`, default size 11, gap 10, shadow `(1,-1)` alpha 0.8, same curve maths as Weather's `LayoutReadout`; default arc `high`.
- Tooltip colours as Weather: header `1,0.82,0`; sub-zone `0.8,0.8,0.8`; labels `0.7,0.7,0.7`; values white; flavour `0.85,0.8,0.65` wrapped.
- New/changed `.tga` files need a full client restart; Lua-only changes need `/reload`. Installed copy: `C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns\ImmerseMe_Geography`.

## Review Focus

1. **Skills not loaded yet at login.** `GetNumSkillLines()` can be 0 at `ADDON_LOADED`. Expected: no resource rows until skills arrive, then rows appear; nothing gets wiped. *Test in Task 4: `BuildReading` with `skills = {}` returns no rows and leaves `charDB` untouched.*
2. **Non-gather loot right after a gather cast** (a mob kill or a chest inside the cast→loot window). Expected: only items in the cast's own category are recorded. *Test in Task 4: `MatchLoot({2770, 2318}, "hide")` returns `{}`; `MatchLoot({2770, 2318}, "ore")` returns `{"copper"}`.*
3. **Empty or nil zone name** during loading screens or on a taxi. Expected: no error; the land lookup falls back to the default. *Test in Task 3: `GetLand(nil, nil, false)` and `GetLand("", "", false)` return the default land.*
4. **Dropping and relearning a profession.** Expected: entries hide, then come back unchanged. *Test in Task 4: a reading with Mining removed has no ore rows; adding Mining back restores the same counts.*
5. **Old or partial saved data** (missing `sub`, `n` or `last`). Expected: `RecordGather` repairs it instead of erroring. *Test in Task 4: `RecordGather` on `{ disc = { Elwynn = { copper = {} } } }` gives `n == 1` and fills `sub`.*

---

### Task 1: Repo scaffold and test harness

**Files:**
- Create: `ImmerseMe_Geography.toc`, `Data.lua`, `Core.lua`, `Gather.lua`, `UI.lua` (stubs: `local ADDON, ns = ...` plus a header comment)
- Create: `.gitignore`, `.gitattributes`, `.pkgmeta`, `LICENSE`, `.github/workflows/release.yml`: copy from `../ImmerseMe_Weather` and change `ImmerseMe_Weather` → `ImmerseMe_Geography`; `.pkgmeta` also ignores `tests`
- Create: `tests/run.lua`, `tests/core_spec.lua`

**Interfaces:**
- Produces: `tests/run.lua` loads `Data.lua` then `Core.lua` as chunks called with `("ImmerseMe_Geography", ns)`, stubs `date`/`time`/`print` if missing, runs every spec file listed in it, prints `N passed, M failed` and exits non-zero on failure. Spec files register tests through `test(name, fn)` and use `eq(actual, expected, msg)` (deep-compares tables) and `ok(cond, msg)`, all globals defined by `run.lua`. `run.lua` exposes the loaded namespace as global `ns`.

- [ ] **Step 1: Install standalone Lua** (needs the user's OK first: it's a download). `winget install --id DEVCOM.Lua -e`. Check with `lua -v`. Avoid Lua 5.2+ only features in the addon code (`goto`, integer division `//`, `table.unpack` without a fallback).
- [ ] **Step 2: Write the scaffold files and `tests/core_spec.lua`** with one test, `harness loads namespace`: `ok(type(ns) == "table")` and `eq(ns.ADDON, "ImmerseMe_Geography")`.
- [ ] **Step 3: Run `lua tests/run.lua`.** Expected: FAIL (`ns.ADDON` is nil).
- [ ] **Step 4: Set `ns.ADDON = ADDON` and `ns.MEDIA = "Interface\\AddOns\\" .. ADDON .. "\\Media\\"`** in `Data.lua`.
- [ ] **Step 5: Run `lua tests/run.lua`.** Expected: `1 passed, 0 failed`.
- [ ] **Step 6: `git init -b main`; add a backslash lint test** `no single backslashes in paths`: for each of `Data.lua`, `Core.lua`, `Gather.lua`, `UI.lua`, read the file and `ok(not src:find("[^\\]\\[A-Z]"), file)`. This fails on a single backslash followed by a capital letter, the broken-path case; correct `\\A` and escapes like `\n` don't match. Run it and expect PASS. Commit: `chore: scaffold ImmerseMe_Geography with test harness`. Move the spec and plan docs into the first commit too.

### Task 2: Catalogs in Data.lua

**Files:**
- Modify: `Data.lua`
- Create: `tests/data_spec.lua` (register it in `run.lua`)

**Interfaces:**
- Produces:
  - `ns.TIERS = { "low", "medium", "high" }` and `ns.TIER_WORDS = { "Scarce", "Common", "Plentiful" }`
  - `ns.Facets = { terrain = {...}, ground = {...}, water = {...}, wild = {...} }`. Each maps a value key to `{ label = "Hills", icon = ns.MEDIA .. "land_terrain_hills" }`. The value keys are exactly the spec's lists: terrain `forest grassland hills mountains desert badlands swamp jungle tundra coast volcanic blighted underground city`; ground `soil mud sand rock snow ash stone`; water `river lake sea marsh none`; wild `settled frontier wild`.
  - `ns.Professions = { Mining = "ore", Herbalism = "herb", Skinning = "hide", Fishing = "fish" }` (skill-line name → category)
  - `ns.GatherSpells = { ["Mining"] = "ore", ["Herb Gathering"] = "herb", ["Skinning"] = "hide", ["Fishing"] = "fish" }` and `ns.GatherSpellIDs = { [2575]="ore", [2576]="ore", [3564]="ore", [10248]="ore", [2366]="herb", [2368]="herb", [3570]="herb", [11993]="herb", [8613]="hide", [8617]="hide", [8618]="hide", [10768]="hide", [7620]="fish", [7731]="fish", [7732]="fish", [18248]="fish" }`
  - `ns.Resources[key] = { cat = "ore", items = { 2770 }, short = "Copper", name = "Copper Ore", req = 1 }`. `req` is set for ore/herb only; fish and hide take their requirement from the zone. Built from it: `ns.ItemToResource[itemID] = key`.
  - Coverage: classic ores (copper 2770 req 1, tin 2771/65, silver 2775/75, iron 2772/125, gold 2776/155, mithril 3858/175, truesilver 7911/230, thorium 10620/245, darkiron 11370/230, incendicite 3340/65, bloodstone 4278/75) and classic herbs Peacebloom → Black Lotus with their standard gathering requirements. Leather: light 2318, medium 2319, heavy 4234, thick 4304, rugged 8170. Fish: the common classic catches per zone band (e.g. Raw Brilliant Smallfish 6291, Raw Longjaw Mud Snapper 6289, Raw Bristle Whisker Catfish 6308, Raw Mithril Head Trout 8365, Raw Redgill 13758, Raw Spotted Yellowtail 4603, Stonescale Eel 13422 …). The builder fills the full lists from Classic data.
- [ ] **Step 1: Write `tests/data_spec.lua`:**
  - `facet values match spec`: `eq` the sorted key lists of each `ns.Facets[f]` to the spec lists above
  - `every resource valid`: for each resource, `cat` is one of `ore herb hide fish`, `#items >= 1`, `short` and `name` are non-empty, and `req` is a number exactly when `cat` is `ore` or `herb`
  - `item index unique`: no item ID appears under two resources, and `ns.ItemToResource[2770] == "copper"`
  - `gather spells`: `ns.GatherSpells["Herb Gathering"] == "herb"` and `ns.GatherSpellIDs[2575] == "ore"`
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Fill in the catalogs in `Data.lua`.**
- [ ] **Step 4: Run.** Expected: all pass. Commit: `feat: land facet and resource catalogs`.

### Task 3: Land and truth lookup (Core.lua)

**Files:**
- Modify: `Core.lua`, `Data.lua` (seed `ns.Zones` / `ns.SubZones` with three test zones: Elwynn Forest, Westfall, Dun Morogh, plus the sub-zones `Fargodeep Mine` and `Jangolode Mine`; full coverage comes in Task 5)
- Create: `tests/land_spec.lua`

**Interfaces:**
- Consumes: `ns.Facets`, `ns.Resources`
- Produces:
  - Zone entry shape: `ns.Zones[name] = { terrain=, ground=, water=, wild=, flavor="...", fishSkill=n?, skinSkill=n?, res = { copper = 3, tin = 1, ... } }` (tier numbers). `ns.SubZones[name] = { ...any facet or flavor..., res = {...}? }`.
  - `ns.DEFAULT_LAND = { terrain="grassland", ground="soil", water="none", wild="wild" }`
  - `ns.GetLand(zone, subzone, inInstance) -> land` where `land = { zone=, subzone=, terrain=, ground=, water=, wild=, flavor=, instance=bool, listed=bool }`. A sub-zone entry overrides the facets it names. With `inInstance`, terrain is `"underground"` and `ground`/`water`/`wild` are nil. A nil or empty zone becomes `"Unknown"`, `listed=false` and the default facets.
  - `ns.TruthFor(zone, subzone) -> res, entry`. `res` is the sub-zone's `res` table when it has one (it **replaces** the zone list), otherwise the zone's; `{}` when neither exists. `entry` is the zone entry or nil (it carries `fishSkill`/`skinSkill`).
- [ ] **Step 1: Write `tests/land_spec.lua`:**
  - `listed zone`: `GetLand("Elwynn Forest", "", false).terrain == "forest"` and `listed == true`
  - `subzone overrides`: `GetLand("Elwynn Forest", "Fargodeep Mine", false).terrain == "underground"` while its `wild` still equals Elwynn's
  - `instance`: `GetLand("The Deadmines", "", true)` gives terrain `"underground"`, `ground == nil` and `instance == true`
  - `unknown zone`: `GetLand(nil, nil, false)` and `GetLand("", "", false)` give terrain `"grassland"`, zone `"Unknown"` and `listed == false` (Review Focus 3)
  - `truth replace`: `TruthFor("Westfall", "Jangolode Mine")` equals the mine's `res`; `TruthFor("Westfall", "Sentinel Hill")` equals Westfall's `res`; `TruthFor("Nowhere", "")` equals `{}`
  - `seed data valid`: every `res` key in `ns.Zones`/`ns.SubZones` exists in `ns.Resources`, every tier is in `1..3`, and every facet value exists in `ns.Facets`. Put this one in `data_spec.lua` so it keeps guarding the data from Task 5 on.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement both functions in `Core.lua`.** **Step 4: Run.** Expected: PASS. Commit: `feat: land and resource truth lookup`.

### Task 4: Discovery, accuracy and reading (Core.lua)

**Files:**
- Modify: `Core.lua`
- Create: `tests/reading_spec.lua`

**Interfaces:**
- Consumes: `ns.GetLand`, `ns.TruthFor`, `ns.Resources`, `ns.ItemToResource`, `ns.Professions`
- Produces:
  - `ns.Hash01(key, n) -> [0,1)`: copy Weather's `hash01` exactly
  - `ns.MatchLoot(itemIDs, cat) -> { resKey, ... }`: only resources whose `cat` matches, no duplicates, in input order
  - `ns.RecordGather(charDB, zone, subzone, resKey, t)`: creates or repairs `charDB.disc[zone][resKey] = { n, last, sub = { [subzone]=count } }`, increments `n` and `sub[subzone]` (skips `sub` when subzone is empty), sets `last = t`
  - `ns.Confidence(skill, req, count) -> 0..1` = `min(1, max(0, (skill - req) / 75) + count / 25)`
  - `ns.ShownTier(trueTier, conf, seed) -> tier, uncertain`. When `conf >= 1`: `trueTier, false`. Otherwise `p = 0.5 * (1 - conf)`; if `Hash01(seed, 1) < p`, shift by `Hash01(seed, 2) < 0.5 and -1 or 1`, flipping the direction when it would leave `1..3`. Return `tier, true`.
  - `ns.Ago(seconds) -> string`: `"just now"` (<60 s), `"N min ago"`, `"N hours ago"`, `"yesterday"`, `"N days ago"`
  - `ns.BuildReading(charDB, skills, zone, subzone, inInstance, playerSeed) -> reading`.
    - `skills` is `{ Mining = 87, ... }`.
    - `reading = { land = <GetLand>, rows = { row... }, hints = { [cat] = true }, profs = { { name="Mining", cat="ore", skill=87 }, ... } }`, with `profs` sorted by name.
    - `row = { key, cat, short, name, tier, uncertain, unconfirmed, n, last }`.
    - Rows come only from categories the player has and only from discovered entries in `charDB.disc[zone]`. The truth tier comes from `TruthFor`. A resource gathered but missing from the truth gets `tier 2, uncertain = true, unconfirmed = true` at any skill.
    - The requirement for confidence is `res.req`, or for fish/hide `entry.fishSkill` / `entry.skinSkill` (fall back to 1 when missing). The seed is `playerSeed .. ":" .. zone .. ":" .. key`.
    - Rows are sorted by tier desc, then `n` desc, then `short` asc.
    - `hints[cat] = true` when skill >= 225 and the truth holds an undiscovered resource in that category whose `req` (or the zone requirement) is <= skill.
- [ ] **Step 1: Write `tests/reading_spec.lua`:**
  - `match loot by category`: `eq(MatchLoot({2770, 2318}, "ore"), {"copper"})` and `eq(MatchLoot({2770, 2318}, "hide"), {})` (Review Focus 2)
  - `record creates`: on an empty `{}`, after two calls `disc["Westfall"].copper.n == 2`, `sub["Jangolode Mine"] == 2` and `last == t2`
  - `record repairs`: `{ disc = { ["Elwynn Forest"] = { copper = {} } } }` → `n == 1` and `type(sub) == "table"` (Review Focus 5)
  - `confidence bounds`: `Confidence(1, 1, 1) < 1`, `Confidence(76, 1, 0) == 1`, `Confidence(1, 1, 25) == 1`, `Confidence(0, 50, 0) == 0`
  - `shown tier exact`: `ShownTier(3, 1, "x")` → `3, false`
  - `shown tier deterministic and in range`: across 200 seeds `ShownTier(t, 0, seed)` stays in `1..3`, `|shown - t| <= 1`, at least one is off by one, and the same seed always returns the same result
  - `no profession, no rows`: with `skills = {}`, `reading.rows` is empty and `charDB` stays byte-identical after the call (compare a deep copy) (Review Focus 1)
  - `profession gating`: a char with ore and herb discoveries and only `{ Mining = 100 }` gets ore rows only
  - `relearn restores`: build with Mining, then without, then with again; the first and third `rows` are equal (Review Focus 4)
  - `unconfirmed`: discovering `silver` in Elwynn (not in Elwynn's truth) gives `tier 2`, `uncertain` and `unconfirmed`, even at skill 300
  - `ordering`: rows are sorted by tier desc, then n desc
  - `hint`: Mining 230 with copper discovered in a zone whose truth also holds iron (req 125) gives `hints.ore == true`; at skill 200, nil
  - `ago`: `Ago(30) == "just now"`, `Ago(3 * 3600) == "3 hours ago"`, `Ago(36 * 3600) == "yesterday"`, `Ago(3 * 86400) == "3 days ago"`
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS. Commit: `feat: discovery, skill accuracy and readings`.

### Task 5: Full zone data

**Files:**
- Modify: `Data.lua`
- Modify: `tests/data_spec.lua`

**Interfaces:**
- Consumes: the zone entry shape from Task 3
- Produces: `ns.Zones` covers every zone key in `../ImmerseMe_Weather/Data.lua` `ns.Zones` (Eastern Kingdoms and Kalimdor vanilla zones, cities included: cities get terrain `city`, wild `settled` and no `res`). It also covers the classic dungeons and raids where gathering happens: Blackrock Depths, Maraudon, Dire Maul, Scholomance, Stratholme, Zul'Farrak, Sunken Temple, Blackrock Spire, Molten Core. Sub-zones cover the well-known mines and caves of each zone. Tiers follow well-known Classic distributions. Every non-city outdoor zone has `fishSkill` and `skinSkill`. Every zone has a one-line `flavor` in the voice of Weather's flavour text.
- [ ] **Step 1: Add test `covers weather zones`**: a hard-coded list of the 46 zone names from Weather's table. `ok(ns.Zones[name], name)` for each. The Task 3 `seed data valid` test keeps checking keys and tiers.
- [ ] **Step 2: Run.** Expected: FAIL (only 3 zones). **Step 3: Write the data.** **Step 4: Run.** Expected: PASS. Commit: `feat: zone geography and resource data`.

### Task 6: Icons

**Files:**
- Create: `tools/make_icons.py`, `tools/preview_icons.py` (pure Python 3, no deps; reuse the TGA writer, supersampling and style helpers from `../ImmerseMe_Weather/tools/make_icons.py`)
- Create: `Media/land_<facet>_<value>.tga` (64×64, 32-bit, one per facet value from Task 2), `Media/tier_low.tga`, `tier_medium.tga`, `tier_high.tga` (64×64), `Media/icon.tga` (128×128 in the shared ImmerseMe frame, same frame as Weather's `icon.tga`)
- Create: `docs/images/icons.png` (contact sheet)
- Modify: `tests/data_spec.lua`

**Interfaces:**
- Produces: a file for every `ns.Facets[f][v].icon`, plus `ns.MEDIA .. "tier_" .. ns.TIERS[i]`. Tier art: 1, 2 and 3 gold pips stacked like a rising signal, the high one brightest. The UI desaturates them for uncertain readings, so they must read in grey too. Land icons are painted, stock-icon-like and readable at 14 px. The water `none` icon is a dry, cracked bowl. City is a small walled tower.
- [ ] **Step 1: Add test `every icon file exists`**: for each facet icon and each tier icon, strip `ns.MEDIA`, then `io.open("Media/" .. base .. ".tga")` must succeed (run.lua runs from the repo root).
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Write the scripts and run `py tools/make_icons.py` then `py tools/preview_icons.py`.** **Step 4: Run the tests.** Expected: PASS. Look at `docs/images/icons.png` to check the icons read at a small size. Commit: `feat: geography icons`.

### Task 7: Gather detection and skills (Gather.lua)

**Files:**
- Modify: `Gather.lua`, `Core.lua` (two pure helpers)
- Modify: `tests/reading_spec.lua`

**Interfaces:**
- Consumes: `ns.GatherSpells`, `ns.GatherSpellIDs`, `ns.Professions`, `ns.MatchLoot`, `ns.RecordGather`
- Produces:
  - Core: `ns.ItemIDFromLink(link) -> number|nil` (pattern `item:(%d+)`) and `ns.CategoryForCast(spellName, spellID) -> cat|nil` (name first, then ID)
  - Gather: `ns.ReadSkills() -> { [profName] = rank }`, built from `GetNumSkillLines`/`GetSkillLineInfo` and keeping only names in `ns.Professions`. `ns.skills` holds the latest result, refreshed on `PLAYER_ENTERING_WORLD` and `SKILL_LINES_CHANGED`.
  - Gather: on `UNIT_SPELLCAST_SUCCEEDED` (`unit == "player"`, `spellID` = 3rd arg, name from `GetSpellInfo(spellID)`) it remembers `{ cat, at = GetTime() }`. On `LOOT_OPENED`, if a cast is remembered within 30 s (fish) or 5 s (others), it collects the item IDs from `GetLootSlotLink(1..GetNumLootItems())`, then calls `ns.RecordGather(ImmerseMeGeographyCharDB, zone, subzone, key, GetServerTime())` for each `ns.MatchLoot` result and clears the cast. It then fires `ns.OnDiscoveryChanged()` (set by UI; no-op default). The first discovery of a key in a zone prints `You learn that this land holds <name>.`.
  - Gather: `ns.debug` flag. When on, it prints every cast (name, ID, category) and every loot item ID.
  - `ImmerseMeGeographyCharDB` initialised on `ADDON_LOADED` to `{ disc = {} }` if nil.
- [ ] **Step 1: Add tests**: `ItemIDFromLink("|cffffffff|Hitem:2770::::::::60:::::|h[Copper Ore]|h|r") == 2770`, `ItemIDFromLink(nil) == nil`; `CategoryForCast("Herb Gathering", 0) == "herb"`, `CategoryForCast("Unknown", 2575) == "ore"`, `CategoryForCast("Fireball", 133) == nil`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement the helpers and Gather.lua.** **Step 4: Run.** Expected: PASS. Commit: `feat: gather detection and skill reading`.

### Task 8: Minimap readout, tooltip, commands (UI.lua)

**Files:**
- Modify: `UI.lua`

**Interfaces:**
- Consumes: `ns.BuildReading`, `ns.Facets`, `ns.TIERS`, `ns.TIER_WORDS`, `ns.Ago`, `ns.skills`, `ns.debug`, `ns.OnDiscoveryChanged`
- Produces:
  - `DEFAULTS = { show = true, rows = 4, arc = "high", gap = 10, yOffset = 0, fontSize = 11, words = true, weatherHint = false }` in `ImmerseMeGeographyDB`
  - Frame `ImmerseMeGeographyReadout`: parented to Minimap, `SetAllPoints(Minimap)`, mouse disabled, frame level Minimap + 9.
    - Row 1, the land row: four textures (terrain, ground, water, wild; size `fontSize + 4`) to the right of the terrain word when `words` is on. Hidden facets (instance) leave no gap.
    - Up to `db.rows` resource rows: the `short` text with the tier texture on its right. Uncertain readings call `SetDesaturated(true)` and `SetAlpha(0.6)`.
    - Every row takes the mouse and shows the shared tooltip.
    - Layout copies Weather's `LayoutReadout`, including its `high`/`middle`/`low` formulas, `gap` and `yOffset`.
  - Tooltip, `ANCHOR_LEFT`, laid out as in the spec's sketch:
    1. The zone (gold) and the sub-zone (grey, if different).
    2. The facet labels joined by `" · "`, then the flavour.
    3. Per profession in `reading.profs`: a gold sub-header `"<Name> (skill N)"`. Each row is a double line: the left side is `name`, prefixed with the item's game icon (`"|T" .. GetItemIcon(items[1]) .. ":14|t "`; skip the icon if it's nil); the right side is the tier word, plus `"?"` and the colour `0.7,0.7,0.7` when uncertain and `" (unconfirmed)"` when unconfirmed, followed by `" · N mined/picked/skinned/caught, last <Ago>"`.
    4. The hint line in the flavour colour, `"There may be richer <veins|herbs|game|waters> here you have not found."`, when `hints[cat]` is set.
    5. A profession with no discoveries in this zone gets one grey line: `"Nothing gathered here yet."`.
  - Refresh on `PLAYER_ENTERING_WORLD`, `ZONE_CHANGED`, `ZONE_CHANGED_INDOORS`, `ZONE_CHANGED_NEW_AREA`, `SKILL_LINES_CHANGED`, `ns.OnDiscoveryChanged`, plus a 5 s ticker. Wrap it in a `pcall` and print each new error once (same as Weather's `SafeRefresh`). `playerSeed = UnitName("player") .. "-" .. GetRealmName()`.
  - Weather hint: on the first `PLAYER_ENTERING_WORLD`, if `IsAddOnLoaded("ImmerseMe_Weather")` (or `C_AddOns.IsAddOnLoaded`), `ImmerseMeWeatherDB.arc ~= "low"`, our arc is `high` and `not db.weatherHint`, print `Tip: ImmerseMe: Weather's readout shares the upper arc. /imw arc low moves it below the minimap's middle.` and set `db.weatherHint = true`.
  - Slash `/img`, `/geography`: no argument prints a one-line summary (terrain, ground, water, wild, and the top resource per profession). The subcommands are `show`, `hide`, `rows <0-6>`, `arc high|middle|low`, `gap <0-40>`, `y <-60-60>`, `font <8-18>`, `words on|off`, `known` (prints every discovery in the zone with tier, n, sub-zone counts and an `unconfirmed` flag), `forget zone` / `forget all` (the second needs `forget all confirm`), `debug` (toggles `ns.debug`), `reset` (layout defaults) and `help`. Invalid input prints usage, like Weather does.
- [ ] **Step 1: Implement UI.lua.**
- [ ] **Step 2: Run `lua tests/run.lua`** (the lint covers UI.lua). Expected: PASS.
- [ ] **Step 3: Install and check in game.**
  - Copy the addon folder to the AddOns path (minus `tests`, `tools`, `docs`). Fully restart the client, since the textures are new.
  - Check, ticking each line:
    - The land row sits on the upper-left arc and doesn't overlap Weather's readout at the defaults.
    - Hovering shows the tooltip.
    - `/img debug` then mining a vein prints `Mining`, the spell ID, `ore` and the item IDs (this confirms the client API); a Copper row then appears.
    - `/img known` lists it.
    - In an instance, only the underground icon shows.
    - A character without professions shows only the land row.
  - Record the confirmed API facts (spell IDs, loot behaviour) in the WoW: Forever client memory.
- [ ] **Step 4: Commit:** `feat: minimap readout, tooltip and commands`.

### Task 9: Docs and release files

**Files:**
- Create: `README.md` (same structure as Weather's: what it is, features, screenshot placeholders `docs/images/minimap.png` and `icons.png`, install, the command table, how discovery works in brief), `CHANGELOG.md` (`## 1.0.0`), `docs/how-it-works.md` (land facets, the discovery and confidence formula, hints, unconfirmed entries), `docs/customizing.md` (how to add zones and resources in Data.lua), `docs/curseforge.md`
- Modify: `ImmerseMe_Geography.toc` (`## Version: 1.0.0`, `## Notes:` one sentence)
- [ ] **Step 1: Write the docs.** **Step 2: Run `lua tests/run.lua`.** Expected: PASS. **Step 3: Commit:** `docs: README, how it works, customizing`. Don't tag or push a release without the user's go-ahead.
