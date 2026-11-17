-- Runs under standalone Lua (tests/run.lua), not the WoW client.
---@diagnostic disable: undefined-global
test("harness loads namespace", function()
	ok(type(ns) == "table", "ns is a table")
	eq(ns.ADDON, "ImmerseMe_Geography")
end)

test("no single backslashes in paths", function()
	for _, file in ipairs({ "Data.lua", "Core.lua", "Gather.lua", "UI.lua" }) do
		local f = assert(io.open(file, "rb"))
		local src = f:read("*a") -- "*a": Lua 5.1, the game's version
		f:close()
		ok(not src:find("[^\\]\\[A-Z]"), file .. " has a single backslash before a capital letter")
	end
end)
