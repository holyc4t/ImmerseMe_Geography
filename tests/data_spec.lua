-- Runs under standalone Lua (tests/run.lua), not the WoW client.
---@diagnostic disable: undefined-global
local function sortedKeys(t)
	local out = {}
	for k in pairs(t or {}) do out[#out + 1] = k end
	table.sort(out)
	return out
end

local SPEC_FACETS = {
	terrain = { "badlands", "blighted", "city", "coast", "desert", "forest", "grassland", "hills", "jungle",
	            "mountains", "swamp", "tundra", "underground", "volcanic" },
	ground  = { "ash", "mud", "rock", "sand", "snow", "soil", "stone" },
	water   = { "lake", "marsh", "none", "river", "sea" },
	wild    = { "frontier", "settled", "wild" },
}

test("facet values match spec", function()
	ok(ns.Facets, "ns.Facets exists")
	for facet, values in pairs(SPEC_FACETS) do
		eq(sortedKeys(ns.Facets[facet]), values, facet)
		for v, def in pairs(ns.Facets[facet]) do
			ok(type(def.label) == "string" and def.label ~= "", facet .. "." .. v .. " label")
			eq(def.icon, ns.MEDIA .. "land_" .. facet .. "_" .. v, facet .. "." .. v .. " icon")
		end
	end
end)

test("tiers", function()
	eq(ns.TIER_WORDS, { "Scarce", "Common", "Plentiful" })
end)

local CATS = { ore = true, herb = true, hide = true, fish = true }

test("every resource valid", function()
	ok(ns.Resources and next(ns.Resources), "ns.Resources not empty")
	for key, r in pairs(ns.Resources) do
		ok(CATS[r.cat], key .. " cat")
		ok(type(r.items) == "table" and #r.items >= 1, key .. " items")
		ok(type(r.short) == "string" and r.short ~= "", key .. " short")
		ok(type(r.name) == "string" and r.name ~= "", key .. " name")
		local needsReq = (r.cat == "ore" or r.cat == "herb")
		eq(type(r.req) == "number", needsReq, key .. " req")
	end
end)

test("item index unique", function()
	local seen = {}
	for key, r in pairs(ns.Resources) do
		for _, id in ipairs(r.items) do
			ok(not seen[id], ("item %d in both %s and %s"):format(id, tostring(seen[id]), key))
			seen[id] = key
			eq(ns.ItemToResource[id], key, "index " .. id)
		end
	end
	eq(ns.ItemToResource[2770], "copper")
end)

test("gather spells", function()
	eq(ns.GatherSpells["Herb Gathering"], "herb")
	eq(ns.GatherSpellIDs[2575], "ore")
	eq(ns.Professions.Mining, "ore")
	eq(ns.Professions.Fishing, "fish")
end)

test("seed data valid", function()
	local function check(where, e)
		for _, facet in ipairs({ "terrain", "ground", "water", "wild" }) do
			if e[facet] ~= nil then ok(ns.Facets[facet][e[facet]], where .. " " .. facet .. "=" .. tostring(e[facet])) end
		end
		if e.tone ~= nil then
			ok(e.terrain, where .. " has a tone but no terrain of its own")
			ok((ns.TerrainTones[e.terrain] or {})[e.tone], where .. " tone=" .. tostring(e.tone))
		end
		for key, tier in pairs(e.res or {}) do
			ok(ns.Resources[key], where .. " unknown resource " .. key)
			ok(tier == 1 or tier == 2 or tier == 3, where .. " " .. key .. " tier " .. tostring(tier))
		end
	end
	ok(next(ns.Zones), "ns.Zones not empty")
	for name, e in pairs(ns.Zones) do
		check(name, e)
		ok(e.terrain, name .. " has terrain")
	end
	for name, e in pairs(ns.SubZones) do check(name, e) end
end)

local WEATHER_ZONES = { "Elwynn Forest","Stormwind City","Redridge Mountains","Westfall","Duskwood","Deadwind Pass","Stranglethorn Vale","Swamp of Sorrows","Blasted Lands","Burning Steppes","Searing Gorge","Badlands","Dun Morogh","Ironforge","Loch Modan","Wetlands","Arathi Highlands","Hillsbrad Foothills","Alterac Mountains","The Hinterlands","Silverpine Forest","Tirisfal Glades","Undercity","Western Plaguelands","Eastern Plaguelands","Durotar","Orgrimmar","The Barrens","Mulgore","Thunder Bluff","Teldrassil","Darnassus","Darkshore","Ashenvale","Moonglade","Stonetalon Mountains","Desolace","Feralas","Dustwallow Marsh","Thousand Needles","Tanaris","Un'Goro Crater","Silithus","Felwood","Azshara","Winterspring" }
local INSTANCES = { "Blackrock Depths", "Maraudon", "Dire Maul", "Scholomance", "Stratholme", "Zul'Farrak",
                    "Sunken Temple", "Blackrock Spire", "Molten Core" }
local CITIES = { ["Stormwind City"] = true, ["Ironforge"] = true, ["Undercity"] = true, ["Orgrimmar"] = true,
                 ["Thunder Bluff"] = true, ["Darnassus"] = true }

test("covers weather zones and instances", function()
	eq(#WEATHER_ZONES, 46)
	for _, name in ipairs(WEATHER_ZONES) do ok(ns.Zones[name], name) end
	for _, name in ipairs(INSTANCES) do ok(ns.Zones[name], name) end
end)

test("zone entries complete", function()
	for _, name in ipairs(WEATHER_ZONES) do
		local e = ns.Zones[name]
		if e then
			ok(type(e.flavor) == "string" and e.flavor ~= "", name .. " flavor")
			for _, f in ipairs(ns.FACET_ORDER) do ok(e[f], name .. " " .. f) end
			if CITIES[name] then
				eq(e.terrain, "city", name); eq(e.wild, "settled", name)
			else
				ok(type(e.fishSkill) == "number", name .. " fishSkill")
				ok(type(e.skinSkill) == "number", name .. " skinSkill")
				ok(e.res and next(e.res), name .. " has resources")
			end
		end
	end
end)

test("every icon file exists", function()
	local function exists(path)
		local base = path:sub(#ns.MEDIA + 1)
		local f = io.open("Media/" .. base .. ".tga", "rb")
		if f then f:close() end
		return f ~= nil, base
	end
	for facet, values in pairs(ns.Facets) do
		for _, def in pairs(values) do
			local found, base = exists(def.icon)
			ok(found, base)
		end
	end
	for terrain, tones in pairs(ns.TerrainTones) do
		ok(ns.Facets.terrain[terrain], "tones for unknown terrain " .. terrain)
		for tone in pairs(tones) do
			local found, base = exists(ns.Facets.terrain[terrain].icon .. "_" .. tone)
			ok(found, base)
		end
	end
	ok(exists(ns.MEDIA .. "icon"), "icon")
end)

test("no icon is left unused", function()
	local used = { ["icon.tga"] = true }
	for facet, values in pairs(ns.Facets) do
		for v in pairs(values) do used["land_" .. facet .. "_" .. v .. ".tga"] = true end
	end
	for terrain, tones in pairs(ns.TerrainTones) do
		for tone in pairs(tones) do used["land_terrain_" .. terrain .. "_" .. tone .. ".tga"] = true end
	end
	-- every facet value and every tone is worn by some zone
	local worn = {}
	for _, list in ipairs({ ns.Zones, ns.SubZones, { ns.DEFAULT_LAND } }) do
		for _, e in pairs(list) do
			for _, facet in ipairs(ns.FACET_ORDER) do
				if e[facet] then worn[facet .. "_" .. e[facet]] = true end
			end
			if e.tone then worn["terrain_" .. e.terrain .. "_" .. e.tone] = true end
		end
	end
	for facet, values in pairs(ns.Facets) do
		for v in pairs(values) do ok(worn[facet .. "_" .. v], "no zone uses " .. facet .. " " .. v) end
	end
	for terrain, tones in pairs(ns.TerrainTones) do
		for tone in pairs(tones) do ok(worn["terrain_" .. terrain .. "_" .. tone], "no zone uses " .. terrain .. " " .. tone) end
	end
	-- and every file in Media/ is one the addon can ask for
	local listing = io.popen(package.config:sub(1, 1) == "\\" and "dir /b Media" or "ls Media")
	local n = 0
	if listing then
		for name in listing:lines() do
			name = name:gsub("%s+$", "")
			if name:match("%.tga$") then
				n = n + 1
				ok(used[name], "unused file Media/" .. name)
			end
		end
		listing:close()
	end
	ok(n > 0, "Media/ could be listed")
end)
