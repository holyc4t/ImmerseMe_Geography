-- Runs under standalone Lua (tests/run.lua), not the WoW client.
---@diagnostic disable: undefined-field
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
