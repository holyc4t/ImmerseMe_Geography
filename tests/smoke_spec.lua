-- Runs under standalone Lua (tests/run.lua), not the WoW client.
---@diagnostic disable: undefined-global, undefined-field, inject-field, missing-parameter
-- Loads the whole addon against a fake WoW client and drives it: catches nil calls,
-- typos and wiring mistakes in Gather.lua / UI.lua that the pure tests can't reach.

local function fakeClient(state)
	local env = setmetatable({}, { __index = _G })
	local frames = {}
	local function object(kind)
		local o = { kind = kind, scripts = {}, events = {}, shown = true, parent = nil, points = 0, text = "" }
		return setmetatable(o, { __index = function(self, name)
			if name == "SetScript" then return function(s, n, fn) s.scripts[n] = fn end end
			if name == "HookScript" then return function(s, n, fn) s.hooks = rawget(s, "hooks") or {}; s.hooks[n] = fn end end
			if name == "RegisterEvent" or name == "RegisterUnitEvent" then return function(s, e) s.events[e] = true end end
			if name == "CreateFontString" or name == "CreateTexture" then
				return function(s)
					local c = object(name); c.parent = s
					s.children = rawget(s, "children") or {}
					table.insert(s.children, c)
					return c
				end
			end
			if name == "SetFont" then return function(s, file) s.hasFont = file ~= nil end end
			if name == "SetFontObject" then return function(s, f) s.fontObject = f end end
			if name == "SetText" then return function(s, t)
				-- the real client throws "Font not set" here when the font object has no font yet
				if rawget(s, "fontObject") and not rawget(s.fontObject, "hasFont") then error("Font not set") end
				s.text = t or ""
			end end
			if name == "SetTexture" then return function(s, t) s.tex = t end end
			if name == "GetStringWidth" then return function(s) return #(s.text or "") * 6 end end
			if name == "SetShown" then return function(s, v) s.shown = v and true or false end end
			if name == "Show" then return function(s) s.shown = true end end
			if name == "Hide" then return function(s) s.shown = false end end
			if name == "IsShown" then return function(s) return s.shown end end
			if name == "GetParent" then return function(s) return s.parent end end
			if name == "SetPoint" then return function(s, point, rel, relPoint, x, y)
				s.points = s.points + 1
				s.point, s.rel, s.relPoint, s.x, s.y = point, rel, relPoint, x, y
			end end
			if name == "GetRegions" or name == "GetChildren" then return function() end end
			if name == "SetSize" then return function(s, w, h) s.w, s.h = w, h end end
			if name:match("^Get") then return function() return 140 end end
			return function() end
		end })
	end
	env.CreateFrame = function(kind, name, parent)
		local f = object(kind); f.parent = parent
		frames[#frames + 1] = f
		if name then env[name] = f end
		return f
	end
	env.CreateFont = function() return object("Font") end
	env.Minimap = object("Minimap")
	env.Minimap.GetWidth = function() return 198 end
	env.Minimap.GetCenter = function() return 500, 500 end
	env.Minimap.GetEffectiveScale = function() return 1 end
	if state.stock then
		-- the stock day / night icon: sun art and gold ring, by atlas name, at state.stock.x / y
		local function region(atlas)
			local r = object("Texture")
			r.GetAtlas = function() return atlas end
			r.GetCenter = function() return state.stock.x, state.stock.y end
			r.GetEffectiveScale = function() return 1 end
			r.GetWidth = function() return 20 end
			r.GetHeight = function() return 20 end
			return r
		end
		local art, ring = region("UI-HUD-Minimap-DayCycle"), region("UI-HUD-Minimap-Frame-Cycle")
		ring.GetWidth = function() return 30 end
		ring.GetHeight = function() return 30 end
		env.Minimap.GetRegions = function() return art, ring end
		env.stockArt = art
	end
	if state.header then
		-- the stock header bar and zone-name button; state.header.y is where the bar sits on screen
		local bar, zoneName = object("Frame"), object("Button")
		bar.GetCenter = function() return 500, state.header.y end
		bar.GetEffectiveScale = function() return 1 end
		env.MinimapCluster = object("Frame")
		env.MinimapCluster.BorderTop, env.MinimapCluster.ZoneTextButton = bar, zoneName
	end
	env.GameTooltip = object("GameTooltip")
	env.GameTooltip.lines, env.GameTooltip.owner = {}, false
	env.GameTooltip.AddLine = function(s, t) s.lines[#s.lines + 1] = t end
	env.GameTooltip.AddDoubleLine = function(s, a, b) s.lines[#s.lines + 1] = a .. " | " .. b end
	env.GameTooltip.SetOwner = function(s, o) s.owner = o; s.lines = {} end
	env.GameTooltip.GetOwner = function(s) return s.owner or nil end
	env.GameTooltip.IsShown = function(s) return s.owner and true or false end
	env.STANDARD_TEXT_FONT = "Fonts\\FRIZQT__.TTF"
	env.C_Timer = { NewTicker = function() end }
	env.SlashCmdList = {}
	env.wipe = function(t) for k in pairs(t) do t[k] = nil end return t end
	env.printed = {}
	env.print = function(...) env.printed[#env.printed + 1] = table.concat({ ... }, " ") end
	env.GetTime = function() return state.now end
	env.GetServerTime = function() return 1000000 + state.now end
	env.GetRealZoneText = function() return state.zone end
	env.GetSubZoneText = function() return state.subzone end
	env.IsInInstance = function() return false end
	env.UnitName = function() return "Tester" end
	env.GetRealmName = function() return "Realm" end
	env.GetNumSkillLines = function() return #state.skills end
	env.GetSkillLineInfo = function(i) local s = state.skills[i]; return s[1], s[2], true, s[3] end
	if state.profs then
		-- the newer profession API: GetProfessions() returns indices, GetProfessionInfo(i) name/icon/rank
		env.GetProfessions = function()
			local idx = {}
			for i = 1, #state.profs do idx[i] = i end
			return idx[1], idx[2], idx[3], idx[4], idx[5]
		end
		env.GetProfessionInfo = function(i) local p = state.profs[i]; return p[1], 136246, p[2] end
	end
	env.GetSpellInfo = function(id) return state.spells[id] end
	env.GetNumLootItems = function() return #state.loot end
	env.GetLootSlotLink = function(i) return "|Hitem:" .. state.loot[i] .. "::|h[x]|h" end
	env.GetItemIcon = function() return 134579 end
	env.IsAddOnLoaded = function() return false end
	env.frames = frames
	return env
end

local function fire(env, event, ...)
	for _, f in ipairs(env.frames) do
		if f.events[event] and f.scripts.OnEvent then f.scripts.OnEvent(f, event, ...) end
	end
end

-- Load an addon file with env as its globals: setfenv on Lua 5.1 (the game's), loadfile's env on 5.2+.
local function loadIn(file, env)
	local chunk = assert(loadfile(file, "t", env))
	if setfenv then setfenv(chunk, env) end
	return chunk
end

local function boot(state)
	local env = fakeClient(state)
	local space = {}
	for _, file in ipairs({ "Data.lua", "Core.lua", "Gather.lua", "UI.lua" }) do
		local chunk = loadIn(file, env)
		chunk("ImmerseMe_Geography", space)
	end
	fire(env, "ADDON_LOADED", "ImmerseMe_Geography")
	fire(env, "PLAYER_ENTERING_WORLD")
	return env, space
end

local function noErrors(env)
	for _, line in ipairs(env.printed) do ok(not line:find("error"), line) end
end

test("smoke: loads, gathers, shows the tooltip", function()
	local state = { now = 100, zone = "Westfall", subzone = "Jangolode Mine",
		skills = { { "Professions", true, 0 }, { "Mining", false, 120 } },
		spells = { [2575] = "Mining" }, loot = { 2770, 2835 } }
	local env, ns = boot(state)
	noErrors(env)
	eq(ns.skills, { Mining = 120 })
	ok(env.ImmerseMeGeographyReadout, "readout frame exists")

	fire(env, "UNIT_SPELLCAST_SUCCEEDED", "player", "guid", 2575)
	state.now = 102
	fire(env, "LOOT_OPENED")
	noErrors(env)
	eq(env.ImmerseMeGeographyCharDB.disc["Westfall"].copper.n, 1)
	local learned = false
	for _, line in ipairs(env.printed) do if line:find("holds Copper Ore") then learned = true end end
	ok(learned, "discovery message printed")

	-- loot long after the cast doesn't count
	state.now = 200
	fire(env, "LOOT_OPENED")
	eq(env.ImmerseMeGeographyCharDB.disc["Westfall"].copper.n, 1)

	-- hover the icons: tooltip lists the profession and the resource
	local row = env.ImmerseMeGeographyReadout
	row.scripts.OnEnter(row)
	local all = table.concat(env.GameTooltip.lines, "\n")
	ok(all:find("Westfall"), "zone in tooltip")
	ok(all:find("Mining %(skill 120%)"), "profession header")
	ok(all:find("Copper Ore"), "resource line")
	ok(all:find("1 mined"), "gather count")
end)

test("smoke: slash commands run", function()
	local state = { now = 100, zone = "Elwynn Forest", subzone = "", skills = {}, spells = {}, loot = {} }
	local env = boot(state)
	local slash = env.SlashCmdList.IMMERSEMEGEOGRAPHY
	for _, cmd in ipairs({ "", "help", "known", "debug", "debug", "size 20", "size", "x 4", "y -5", "rows 2",
	                       "hide", "show", "forget all", "forget zone", "forget all confirm", "nonsense" }) do
		slash(cmd)
	end
	noErrors(env)
	eq(env.ImmerseMeGeographyDB.size, 20)
	eq(env.ImmerseMeGeographyDB.xOffset, 4)
	slash("reset")
	eq(env.ImmerseMeGeographyDB.size, 18, "reset restores size")
	eq(env.ImmerseMeGeographyDB.xOffset, 0, "reset restores x")
	local summary = env.printed[1] or ""
	ok(summary:find("Elwynn Forest: Forest · Soil · River · Settled"), summary)
end)

local function textures(frame)
	local out = {}
	for _, c in ipairs(frame.icons) do
		if c.shown then out[#out + 1] = rawget(c, "tex") end
	end
	return out
end

test("smoke: by default the land is one orb, the mirror image of the stock day / night icon", function()
	-- minimap centre at 500,500; the stock icon up and to the right of it
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {},
		stock = { x = 560, y = 590 }, header = { y = 600 } }
	local env, ns = boot(state)
	noErrors(env)
	local orb = env.ImmerseMeGeographyReadout
	eq(env.ImmerseMeGeographyDB.style, "orb")
	eq(textures(orb), { ns.Facets.terrain.grassland.icon .. "_gold" }, "the terrain alone, in Westfall's gold")
	ok(orb.disc.shown and orb.ring.shown, "disc and ring drawn")
	ok(orb.rel == env.Minimap and orb.point == "CENTER", "placed from the minimap's centre")
	-- the fake readout's scale is 140, the stock icon's 1
	ok(math.abs(orb.x * 140 - -60) < 0.01, "mirrored to the left: x=" .. orb.x * 140)
	ok(math.abs(orb.y * 140 - 90) < 0.01, "same height: y=" .. orb.y * 140)
	ok(math.abs(orb.w * 140 - 20 * 0.92) < 0.01, "the stock icon's size")
	-- row style and back
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("style row")
	eq(#textures(orb), 4)
	ok(not orb.disc.shown and not orb.ring.shown, "no disc or ring on the row")
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("style bogus")
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("reset")
	eq(env.ImmerseMeGeographyDB.style, "orb", "reset restores the orb")
	eq(#textures(orb), 1)
end)

test("smoke: without a stock day / night icon the orb stands on the rim's upper left", function()
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {} }
	local env = boot(state)
	noErrors(env)
	local orb = env.ImmerseMeGeographyReadout
	ok(orb.rel == env.Minimap, "on the minimap")
	ok(orb.x < 0 and orb.y > 0, "upper left")
	local r = math.sqrt(orb.x ^ 2 + orb.y ^ 2)
	ok(math.abs(r - (99 + 6)) < 0.01, "on the rim: r=" .. r)
end)

test("smoke: land is one row of four icons under the header", function()
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {},
		header = { y = 600 } }
	local env, ns = boot(state)
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("style row")
	noErrors(env)
	local row = env.ImmerseMeGeographyReadout
	local F = ns.Facets
	eq(textures(row), { F.terrain.grassland.icon .. "_gold", F.ground.soil.icon, F.water.sea.icon, F.wild.frontier.icon })
	ok(row.rel == env.MinimapCluster.BorderTop, "hung on the header")
	eq({ row.point, row.relPoint }, { "TOPLEFT", "BOTTOMLEFT" }, "below a header that is on top")
	ok(row.y < 0, "below the header")
	ok(row.shown, "shown")
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("hide")
	ok(not row.shown, "hide hides it")
end)

test("smoke: the row flips above a header that sits underneath the minimap", function()
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {},
		header = { y = 400 } }
	local env = boot(state)
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("style row")
	noErrors(env)
	local row = env.ImmerseMeGeographyReadout
	eq({ row.point, row.relPoint }, { "BOTTOMLEFT", "TOPLEFT" })
	ok(row.y > 0, "above the header")
	-- the header moves back on top (Edit Mode); the next refresh follows it
	state.header.y = 600
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("show")
	eq({ row.point, row.relPoint }, { "TOPLEFT", "BOTTOMLEFT" })
end)

test("smoke: without a stock header the row sits on the minimap's top-left corner", function()
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {} }
	local env = boot(state)
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("style row")
	noErrors(env)
	ok(env.ImmerseMeGeographyReadout.rel == env.Minimap, "anchored to the minimap")
	eq(env.ImmerseMeGeographyReadout.point, "BOTTOMLEFT")
end)

test("smoke: resources never draw on the minimap, only in the tooltip", function()
	local state = { now = 100, zone = "Westfall", subzone = "",
		skills = { { "Mining", false, 300 } }, spells = {}, loot = {}, header = { y = 600 } }
	local env = boot(state)
	env.ImmerseMeGeographyCharDB.disc["Westfall"] = { copper = { n = 3, last = 1, sub = {} } }
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("show")
	noErrors(env)
	local row = env.ImmerseMeGeographyReadout
	eq(#textures(row), 1, "only the terrain icon")
	for _, f in ipairs(env.frames) do ok(f.parent ~= row, "no child frames on the row") end
	row.scripts.OnEnter(row)
	ok(table.concat(env.GameTooltip.lines, "\n"):find("Copper Ore"), "resource in the tooltip")
end)

test("smoke: hovering the stock zone name adds the land to its tooltip", function()
	local state = { now = 100, zone = "Elwynn Forest", subzone = "", skills = {}, spells = {}, loot = {},
		header = { y = 600 } }
	local env, ns = boot(state)
	local button = env.MinimapCluster.ZoneTextButton
	ok(rawget(button, "hooks") and button.hooks.OnEnter, "zone name hooked")
	-- the stock handler has already filled the tooltip
	env.GameTooltip:SetOwner(button)
	env.GameTooltip:AddLine("Elwynn Forest")
	button.hooks.OnEnter(button)
	local all = table.concat(env.GameTooltip.lines, " / ")
	ok(all:find("^Elwynn Forest / "), "stock lines kept: " .. all)
	ok(all:find("Forest", 15, true) and all:find(ns.Facets.wild.settled.desc, 1, true), all)
end)

test("smoke: skills that arrive late are picked up on a zone change", function()
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {} }
	local env, ns = boot(state)
	eq(ns.skills, {})
	state.skills = { { "Herbalism", false, 50 } }
	fire(env, "ZONE_CHANGED_NEW_AREA")
	eq(ns.skills, { Herbalism = 50 })
end)

test("smoke: fast-loot (LOOT_READY then LOOT_OPENED) counts once", function()
	local state = { now = 100, zone = "Westfall", subzone = "", skills = { { "Mining", false, 50 } },
		spells = { [2575] = "Mining" }, loot = { 2770 } }
	local env = boot(state)
	fire(env, "UNIT_SPELLCAST_SUCCEEDED", "player", "guid", 2575)
	fire(env, "LOOT_READY")
	state.loot = {}            -- a fast-loot addon has already emptied the window
	fire(env, "LOOT_OPENED")
	eq(env.ImmerseMeGeographyCharDB.disc["Westfall"].copper.n, 1)
end)

test("smoke: professions read through GetProfessions when the skill list has none", function()
	local state = { now = 100, zone = "Teldrassil", subzone = "", skills = {}, spells = {}, loot = {},
		profs = { { "Herbalism", 45 }, { "Fishing", 12 } } }
	local env, ns = boot(state)
	noErrors(env)
	eq(ns.skills, { Herbalism = 45, Fishing = 12 })
end)

test("smoke: debug reports how skills were read", function()
	local state = { now = 100, zone = "Teldrassil", subzone = "", skills = {}, spells = {}, loot = {},
		profs = { { "Herbalism", 45 } } }
	local env = boot(state)
	env.printed = {}
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("debug")
	local all = table.concat(env.printed, " / ")
	ok(all:find("skills:"), all)
	ok(all:find("Herbalism 45"), all)
end)

test("smoke: tooltip explains the wildness", function()
	local state = { now = 100, zone = "Elwynn Forest", subzone = "", skills = {}, spells = {}, loot = {} }
	local env, ns = boot(state)
	local row = env.ImmerseMeGeographyReadout
	row.scripts.OnEnter(row)
	local all = table.concat(env.GameTooltip.lines, " / ")
	ok(all:find(ns.Facets.wild.settled.desc, 1, true), all)
end)

test("smoke: the land can be dragged anywhere inside the minimap circle, and stays there", function()
	-- minimap centre 500,500, radius 99; the orb may sit out to the rim (radius 99 + 6)
	local state = { now = 100, zone = "Westfall", subzone = "", skills = {}, spells = {}, loot = {},
		stock = { x = 560, y = 590 }, header = { y = 600 } }
	local env = boot(state)
	local orb = env.ImmerseMeGeographyReadout
	orb.GetEffectiveScale = function() return 1 end
	env.GetCursorPosition = function() return state.cx, state.cy end
	ok(orb.scripts.OnDragStart and orb.scripts.OnDragStop, "draggable")

	orb.scripts.OnDragStart(orb)
	state.cx, state.cy = 450, 520                  -- inside the circle
	orb.scripts.OnUpdate(orb, 0.016)
	ok(orb.rel == env.Minimap and orb.point == "CENTER", "follows the cursor around the minimap's centre")
	ok(math.abs(orb.x - -50) < 0.01 and math.abs(orb.y - 20) < 0.01, ("at %.1f, %.1f"):format(orb.x, orb.y))

	state.cx, state.cy = 300, 500                  -- far outside, to the left
	orb.scripts.OnUpdate(orb, 0.016)
	ok(math.abs(orb.x - -105) < 0.01 and math.abs(orb.y) < 0.01, ("held on the rim: %.1f, %.1f"):format(orb.x, orb.y))
	orb.scripts.OnDragStop(orb)
	eq(orb.scripts.OnUpdate, nil, "stops following the cursor")
	ok(env.ImmerseMeGeographyDB.pos, "position saved")

	env.SlashCmdList.IMMERSEMEGEOGRAPHY("show")    -- any refresh keeps the dragged spot
	ok(math.abs(orb.x - -105) < 0.01 and math.abs(orb.y) < 0.01, ("kept: %.1f, %.1f"):format(orb.x, orb.y))
	env.SlashCmdList.IMMERSEMEGEOGRAPHY("style row")
	ok(orb.rel == env.Minimap and math.abs(orb.x - -105) < 0.01, "the row style keeps the spot too")

	env.SlashCmdList.IMMERSEMEGEOGRAPHY("reset")
	eq(env.ImmerseMeGeographyDB.pos, nil, "reset forgets the spot")
	ok(math.abs(orb.x - -60) < 0.01 and math.abs(orb.y - 90) < 0.01, "back to the mirror of the stock icon")
	noErrors(env)
end)

test("smoke: a building the client names instead of the zone is still part of the zone", function()
	-- as in the Scarlet Raven Tavern in Darkshire: the zone text is the tavern, the map is Duskwood
	local state = { now = 100, zone = "Scarlet Raven Tavern", subzone = "Scarlet Raven Tavern", skills = {}, spells = {}, loot = {} }
	local env = fakeClient(state)
	local maps = { [1] = { name = "Scarlet Raven Tavern", parentMapID = 2 }, [2] = { name = "Duskwood", parentMapID = 3 },
	               [3] = { name = "Eastern Kingdoms", parentMapID = 0 } }
	env.C_Map = { GetBestMapForUnit = function() return state.map end, GetMapInfo = function(id) return maps[id] end }
	env.IsIndoors = function() return state.indoors end
	local ns = {}
	for _, file in ipairs({ "Data.lua", "Core.lua", "Gather.lua", "UI.lua" }) do
		loadIn(file, env)("ImmerseMe_Geography", ns)
	end
	fire(env, "ADDON_LOADED", "ImmerseMe_Geography")
	fire(env, "PLAYER_ENTERING_WORLD")

	-- the map knows: the tavern sits on Duskwood's map
	state.map, state.indoors = 1, true
	eq({ ns.CurrentZone() }, { "Duskwood", "Scarlet Raven Tavern" })
	fire(env, "ZONE_CHANGED_INDOORS")
	eq(textures(env.ImmerseMeGeographyReadout), { ns.Facets.terrain.forest.icon .. "_dusk" }, "Duskwood's dark forest, not grassland")
	ok(ns.ZoneReport():find("using 'Duskwood'"), ns.ZoneReport())

	-- no map to go by: under a roof, the zone the player walked in from still holds
	state.map, state.zone, state.indoors = nil, "Duskwood", false
	eq((ns.CurrentZone()), "Duskwood")
	state.zone, state.indoors = "Scarlet Raven Tavern", true
	eq((ns.CurrentZone()), "Duskwood", "carried in through the door")

	-- but never out in the open: an unknown land is an unknown land
	state.zone, state.indoors = "Somewhere New", false
	eq((ns.CurrentZone()), "Somewhere New")
	state.indoors = true
	eq((ns.CurrentZone()), "Somewhere New", "and its buildings don't become Duskwood")
	ok(ns.ZoneReport():find("not in the land data"), ns.ZoneReport())
	noErrors(env)
end)
