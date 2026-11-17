-- ImmerseMe: Geography - pure logic: land lookup, discovery, skill accuracy.
-- No frames and no events here, so it can be tested outside the game (lua tests/run.lua).
local ADDON, ns = ...

local function blank(s) return s == nil or s == "" end

-- The land where the player stands. zone / subzone as the client gives them;
-- inInstance: the player is in a dungeon or raid (only "underground" is shown there).
function ns.GetLand(zone, subzone, inInstance)
	if blank(zone) then zone = "Unknown" end
	if blank(subzone) then subzone = "" end
	local entry = ns.Zones[zone]
	local sub = subzone ~= "" and ns.SubZones[subzone] or nil
	local base = entry or ns.DEFAULT_LAND
	local land = {
		zone = zone, subzone = subzone, instance = inInstance and true or false, listed = entry ~= nil,
		flavor = (sub and sub.flavor) or (entry and entry.flavor)
			or (inInstance and ns.INSTANCE_FLAVOR) or ns.DEFAULT_FLAVOR,
	}
	for _, facet in ipairs(ns.FACET_ORDER) do
		land[facet] = (sub and sub[facet]) or base[facet]
	end
	-- the zone's colouring belongs to its own terrain: a mine inside it doesn't inherit it
	local tone
	if sub and sub.terrain then tone = sub.tone else tone = (sub and sub.tone) or base.tone end
	if inInstance then
		land.terrain, land.ground, land.water, land.wild = "underground", nil, nil, nil
		tone = nil
	end
	local tones = ns.TerrainTones[land.terrain]
	land.tone = (tone and tones and tones[tone]) and tone or nil
	return land
end

-- The texture for one facet of a land: the terrain in the zone's own colours when it has a tone.
function ns.FacetIcon(land, facet)
	local value = land[facet]
	local def = value and ns.Facets[facet][value]
	if not def then return nil end
	if facet == "terrain" and land.tone then return def.icon .. "_" .. land.tone end
	return def.icon
end

-- What the land truly holds here: the zone's list, with the sub-zone's entries laid over it
-- (inside a mine the mine's ores win; the zone's herbs, game and fish still hold).
-- Returns a fresh res table ({} when unknown) and the zone entry (for fishSkill / skinSkill).
function ns.TruthFor(zone, subzone)
	local entry = not blank(zone) and ns.Zones[zone] or nil
	local sub = not blank(subzone) and ns.SubZones[subzone] or nil
	local res = {}
	for key, tier in pairs((entry and entry.res) or {}) do res[key] = tier end
	for key, tier in pairs((sub and sub.res) or {}) do res[key] = tier end
	return res, entry
end

local floor, sin, max, min = math.floor, math.sin, math.max, math.min

-- Deterministic pseudo-random number in [0,1) from a string key and an integer
-- (the same hash as ImmerseMe: Weather).
local M = 2147483647
function ns.Hash01(key, n)
	local h = 5381
	for i = 1, #key do h = (h * 33 + key:byte(i)) % M end
	h = (h + n * 2654435) % M
	h = (h * 48271) % M
	local x = sin((h % 1000003) * 0.6180339 + 0.1) * 43758.5453
	return x - floor(x)
end

---------------------------------------------------------------------------
-- Discovery
---------------------------------------------------------------------------

-- The catalog resources of one category among looted item IDs (no duplicates, in loot order).
function ns.MatchLoot(itemIDs, cat)
	local out, seen = {}, {}
	for _, id in ipairs(itemIDs or {}) do
		local key = ns.ItemToResource[id]
		if key and not seen[key] and ns.Resources[key].cat == cat then
			seen[key] = true
			out[#out + 1] = key
		end
	end
	return out
end

-- Notes one gather in charDB.disc[zone][resKey] = { n, last, sub = { [subzone] = count } }.
-- Repairs entries saved by older versions. Returns true when it was the first in this zone.
function ns.RecordGather(charDB, zone, subzone, resKey, t)
	charDB.disc = charDB.disc or {}
	local z = charDB.disc[zone]
	if type(z) ~= "table" then z = {}; charDB.disc[zone] = z end
	local d = z[resKey]
	local first = d == nil
	if type(d) ~= "table" then d = {}; z[resKey] = d end
	d.n = (tonumber(d.n) or 0) + 1
	d.last = t
	if type(d.sub) ~= "table" then d.sub = {} end
	if subzone and subzone ~= "" then d.sub[subzone] = (d.sub[subzone] or 0) + 1 end
	return first
end

---------------------------------------------------------------------------
-- Accuracy: how sure the player can be of what they have learned.
---------------------------------------------------------------------------

-- 0..1. Exact (1) at 75 skill points above the requirement, or after 25 gathers there.
function ns.Confidence(skill, req, count)
	return min(1, max(0, (skill - req) / 75) + (count or 0) / 25)
end

-- The tier the player believes in. Below full confidence the reading may be one step
-- off; whether and which way is fixed by the seed, so it never flickers.
function ns.ShownTier(trueTier, conf, seed)
	if conf >= 1 then return trueTier, false end
	local tier = trueTier
	if ns.Hash01(seed, 1) < 0.5 * (1 - conf) then
		local dir = ns.Hash01(seed, 2) < 0.5 and -1 or 1
		if tier + dir < 1 or tier + dir > 3 then dir = -dir end
		tier = tier + dir
	end
	return tier, true
end

function ns.Ago(seconds)
	seconds = max(0, seconds or 0)
	if seconds < 60 then return "just now" end
	if seconds < 3600 then return ("%d min ago"):format(floor(seconds / 60)) end
	if seconds < 86400 then
		local h = floor(seconds / 3600)
		return h == 1 and "an hour ago" or ("%d hours ago"):format(h)
	end
	local d = floor(seconds / 86400)
	return d == 1 and "yesterday" or ("%d days ago"):format(d)
end

---------------------------------------------------------------------------
-- The reading: everything the readout and tooltip show for where the player stands.
---------------------------------------------------------------------------

local HINT_SKILL = 225

local function requirement(res, entry)
	if res.req then return res.req end
	if res.cat == "fish" then return (entry and entry.fishSkill) or 1 end
	if res.cat == "hide" then return (entry and entry.skinSkill) or 1 end
	return 1
end

-- charDB: the per-character saved table (read only here); skills: { Mining = 87, ... };
-- playerSeed: a stable per-character string ("Name-Realm").
function ns.BuildReading(charDB, skills, zone, subzone, inInstance, playerSeed)
	local land = ns.GetLand(zone, subzone, inInstance)
	zone = land.zone
	local truth, entry = ns.TruthFor(zone, land.subzone)
	local reading = { land = land, rows = {}, hints = {}, profs = {} }

	local skillFor = {}
	for name, skill in pairs(skills or {}) do
		local cat = ns.Professions[name]
		if cat then
			skillFor[cat] = skill
			reading.profs[#reading.profs + 1] = { name = name, cat = cat, skill = skill }
		end
	end
	table.sort(reading.profs, function(a, b) return a.name < b.name end)

	local known = (charDB and charDB.disc and charDB.disc[zone]) or {}
	for key, d in pairs(known) do
		local res = ns.Resources[key]
		local skill = res and skillFor[res.cat]
		if skill and type(d) == "table" then
			local n = tonumber(d.n) or 0
			local row = { key = key, cat = res.cat, short = res.short, name = res.name, n = n, last = d.last }
			local trueTier = truth[key]
			if trueTier then
				row.tier, row.uncertain = ns.ShownTier(trueTier, ns.Confidence(skill, requirement(res, entry), n),
					(playerSeed or "") .. ":" .. zone .. ":" .. key)
				row.unconfirmed = false
			else
				row.tier, row.uncertain, row.unconfirmed = 2, true, true
			end
			reading.rows[#reading.rows + 1] = row
		end
	end
	table.sort(reading.rows, function(a, b)
		if a.tier ~= b.tier then return a.tier > b.tier end
		if a.n ~= b.n then return a.n > b.n end
		return a.short < b.short
	end)

	for key in pairs(truth) do
		local res = ns.Resources[key]
		local skill = res and skillFor[res.cat]
		if skill and skill >= HINT_SKILL and not known[key] and requirement(res, entry) <= skill then
			reading.hints[res.cat] = true
		end
	end
	return reading
end

---------------------------------------------------------------------------
-- Small parsing helpers for Gather.lua
---------------------------------------------------------------------------

function ns.ItemIDFromLink(link)
	local id = type(link) == "string" and link:match("item:(%d+)")
	return id and tonumber(id) or nil
end

-- Which resource category a cast gathers: by spell name first, then by known spell ID.
function ns.CategoryForCast(spellName, spellID)
	return (spellName and ns.GatherSpells[spellName]) or (spellID and ns.GatherSpellIDs[spellID]) or nil
end
