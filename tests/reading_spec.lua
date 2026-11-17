-- Runs under standalone Lua (tests/run.lua), not the WoW client.
---@diagnostic disable: undefined-field
local function copy(t)
	if type(t) ~= "table" then return t end
	local out = {}
	for k, v in pairs(t) do out[k] = copy(v) end
	return out
end

local function keys(rows)
	local out = {}
	for i, r in ipairs(rows) do out[i] = r.key end
	return out
end

test("hash01 stable and varied", function()
	local v = ns.Hash01("Duskwood:w", 3)
	ok(v >= 0 and v < 1, "range")
	eq(ns.Hash01("Duskwood:w", 3), v, "stable")
	ok(ns.Hash01("Duskwood:w", 4) ~= v, "varies with n")
end)

test("match loot by category", function()
	eq(ns.MatchLoot({ 2770, 2318 }, "ore"), { "copper" })
	eq(ns.MatchLoot({ 2770, 2318 }, "hide"), { "lightleather" })
	eq(ns.MatchLoot({ 2770, 2770, 999999 }, "ore"), { "copper" })
	eq(ns.MatchLoot({ 2318 }, "ore"), {})
	eq(ns.MatchLoot({}, "fish"), {})
end)

test("record creates", function()
	local c = {}
	ns.RecordGather(c, "Westfall", "Jangolode Mine", "copper", 100)
	ns.RecordGather(c, "Westfall", "Jangolode Mine", "copper", 200)
	ns.RecordGather(c, "Westfall", "", "copper", 300)
	local d = c.disc["Westfall"].copper
	eq(d.n, 3)
	eq(d.sub["Jangolode Mine"], 2)
	eq(d.sub[""], nil)
	eq(d.last, 300)
end)

test("record repairs", function()
	local c = { disc = { ["Elwynn Forest"] = { copper = {} } } }
	ns.RecordGather(c, "Elwynn Forest", "Goldshire", "copper", 50)
	local d = c.disc["Elwynn Forest"].copper
	eq(d.n, 1)
	ok(type(d.sub) == "table", "sub table")
	eq(d.sub.Goldshire, 1)
	eq(d.last, 50)
end)

test("confidence bounds", function()
	ok(ns.Confidence(1, 1, 1) < 1, "fresh discovery is uncertain")
	eq(ns.Confidence(76, 1, 0), 1)
	eq(ns.Confidence(1, 1, 25), 1)
	eq(ns.Confidence(0, 50, 0), 0)
	eq(ns.Confidence(300, 1, 400), 1)
end)

test("shown tier exact", function()
	local tier, unsure = ns.ShownTier(3, 1, "x")
	eq(tier, 3)
	eq(unsure, false)
end)

test("shown tier deterministic and in range", function()
	local off = 0
	for t = 1, 3 do
		for i = 1, 200 do
			local seed = "seed" .. i
			local a, ua = ns.ShownTier(t, 0, seed)
			local b, ub = ns.ShownTier(t, 0, seed)
			eq(a, b, "same seed same tier")
			eq(ua, true)
			ok(a >= 1 and a <= 3, "in range")
			ok(math.abs(a - t) <= 1, "at most one step off")
			if a ~= t then off = off + 1 end
		end
	end
	ok(off > 0, "some readings are off")
	ok(off < 600, "not all readings are off")
end)

test("no profession, no rows", function()
	local c = { disc = { ["Westfall"] = { copper = { n = 4, last = 10, sub = {} } } } }
	local before = copy(c)
	local r = ns.BuildReading(c, {}, "Westfall", "", false, "Me-Realm")
	eq(r.rows, {})
	eq(r.profs, {})
	eq(c, before, "charDB untouched")
	eq(r.land.terrain, "grassland")
end)

test("profession gating", function()
	local c = { disc = { ["Westfall"] = {
		copper = { n = 4, last = 10, sub = {} }, peacebloom = { n = 2, last = 10, sub = {} } } } }
	local r = ns.BuildReading(c, { Mining = 100 }, "Westfall", "", false, "Me-Realm")
	eq(keys(r.rows), { "copper" })
	eq(r.profs, { { name = "Mining", cat = "ore", skill = 100 } })
end)

test("relearn restores", function()
	local c = { disc = { ["Westfall"] = { copper = { n = 4, last = 10, sub = {} } } } }
	local a = ns.BuildReading(c, { Mining = 100 }, "Westfall", "", false, "Me-Realm")
	local b = ns.BuildReading(c, {}, "Westfall", "", false, "Me-Realm")
	local again = ns.BuildReading(c, { Mining = 100 }, "Westfall", "", false, "Me-Realm")
	eq(b.rows, {})
	eq(again.rows, a.rows)
end)

test("row fields", function()
	local c = { disc = { ["Westfall"] = { copper = { n = 30, last = 77, sub = {} } } } }
	local r = ns.BuildReading(c, { Mining = 300 }, "Westfall", "", false, "Me-Realm")
	local row = r.rows[1]
	eq(row.key, "copper"); eq(row.cat, "ore"); eq(row.short, "Copper"); eq(row.name, "Copper Ore")
	eq(row.tier, 3); eq(row.uncertain, false); eq(row.unconfirmed, false); eq(row.n, 30); eq(row.last, 77)
end)

test("unconfirmed", function()
	local c = { disc = { ["Elwynn Forest"] = { silver = { n = 50, last = 10, sub = {} } } } }
	local r = ns.BuildReading(c, { Mining = 300 }, "Elwynn Forest", "", false, "Me-Realm")
	eq(r.rows[1].tier, 2)
	eq(r.rows[1].uncertain, true)
	eq(r.rows[1].unconfirmed, true)
end)

test("subzone truth used inside a mine", function()
	-- inside Jangolode Mine the mine's own list (silver 1) is the truth
	local c = { disc = { ["Westfall"] = { silver = { n = 40, last = 10, sub = {} } } } }
	local r = ns.BuildReading(c, { Mining = 300 }, "Westfall", "Jangolode Mine", false, "Me-Realm")
	eq(r.rows[1].tier, 1)
	eq(r.rows[1].unconfirmed, false)
end)

test("fish use the zone requirement", function()
	-- Westfall asks fishSkill 55: at 55 with one catch the reading is uncertain, at 130 exact
	local c = { disc = { ["Westfall"] = { mackerel = { n = 1, last = 10, sub = {} } } } }
	eq(ns.BuildReading(c, { Fishing = 55 }, "Westfall", "", false, "Me").rows[1].uncertain, true)
	eq(ns.BuildReading(c, { Fishing = 130 }, "Westfall", "", false, "Me").rows[1].uncertain, false)
end)

test("ordering", function()
	local c = { disc = { ["Westfall"] = {
		silver = { n = 9, last = 1, sub = {} }, tin = { n = 5, last = 1, sub = {} },
		copper = { n = 1, last = 1, sub = {} }, briarthorn = { n = 3, last = 1, sub = {} },
		mageroyal = { n = 7, last = 1, sub = {} }, earthroot = { n = 7, last = 1, sub = {} } } } }
	local r = ns.BuildReading(c, { Mining = 300, Herbalism = 300 }, "Westfall", "", false, "Me")
	-- tier desc, then n desc, then short asc
	eq(keys(r.rows), { "copper", "earthroot", "mageroyal", "tin", "silver", "briarthorn" })
end)

test("profs sorted by name", function()
	local r = ns.BuildReading({}, { Skinning = 5, Fishing = 10, Mining = 1 }, "Westfall", "", false, "Me")
	eq(r.profs, { { name = "Fishing", cat = "fish", skill = 10 }, { name = "Mining", cat = "ore", skill = 1 },
	              { name = "Skinning", cat = "hide", skill = 5 } })
end)

test("hint", function()
	local c = { disc = { ["Westfall"] = { copper = { n = 4, last = 10, sub = {} } } } }
	eq(ns.BuildReading(c, { Mining = 230 }, "Westfall", "", false, "Me").hints.ore, true)
	eq(ns.BuildReading(c, { Mining = 200 }, "Westfall", "", false, "Me").hints.ore, nil)
	-- everything discovered: no hint
	c.disc["Westfall"].tin = { n = 1, last = 1, sub = {} }
	c.disc["Westfall"].silver = { n = 1, last = 1, sub = {} }
	eq(ns.BuildReading(c, { Mining = 300 }, "Westfall", "", false, "Me").hints.ore, nil)
end)

test("ago", function()
	eq(ns.Ago(30), "just now")
	eq(ns.Ago(5 * 60), "5 min ago")
	eq(ns.Ago(3 * 3600), "3 hours ago")
	eq(ns.Ago(36 * 3600), "yesterday")
	eq(ns.Ago(3 * 86400), "3 days ago")
end)

test("item id from link", function()
	eq(ns.ItemIDFromLink("|cffffffff|Hitem:2770::::::::60:::::|h[Copper Ore]|h|r"), 2770)
	eq(ns.ItemIDFromLink(nil), nil)
	eq(ns.ItemIDFromLink("|cff9d9d9d|Hcurrency:1|h[Gold]|h|r"), nil)
end)

test("category for cast", function()
	eq(ns.CategoryForCast("Herb Gathering", 0), "herb")
	eq(ns.CategoryForCast("Unknown", 2575), "ore")
	eq(ns.CategoryForCast(nil, 7620), "fish")
	eq(ns.CategoryForCast("Fireball", 133), nil)
end)

test("record repairs non-table saves", function()
	local c = { disc = { ["Elwynn Forest"] = { copper = 7 } } }
	ns.RecordGather(c, "Elwynn Forest", "", "copper", 5)
	eq(c.disc["Elwynn Forest"].copper.n, 1)
	local c2 = { disc = { ["Elwynn Forest"] = "junk" } }
	ns.RecordGather(c2, "Elwynn Forest", "", "copper", 5)
	eq(c2.disc["Elwynn Forest"].copper.n, 1)
end)

test("herbs in a mine stay confirmed", function()
	local c = { disc = { ["Elwynn Forest"] = { peacebloom = { n = 40, last = 1, sub = {} } } } }
	local r = ns.BuildReading(c, { Herbalism = 300 }, "Elwynn Forest", "Fargodeep Mine", false, "Me")
	eq(r.rows[1].unconfirmed, false)
	eq(r.rows[1].tier, 3)
end)
