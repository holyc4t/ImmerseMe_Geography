-- ImmerseMe: Geography - the land orb on the minimap, tooltip, slash commands.
local ADDON, ns = ...

local floor, max, min = math.floor, math.max, math.min
local Print = ns.Print
local db

local DEFAULTS = {
	show    = true,
	layout  = 4,     -- saved-settings version (4: orb / header row)
	style   = "orb", -- orb: one terrain orb mirroring the sky orb | row: four icons under the header
	size    = 18,    -- icon size of the row style
	xOffset = 0,     -- nudge right (+) or left (-) in pixels
	yOffset = 0,     -- nudge up (+) or down (-) in pixels
}

local GOLD = { 1, 0.82, 0 }
local LABEL = { 0.7, 0.7, 0.7 }
local FLAVOR = { 0.85, 0.8, 0.65 }
local TIER_COLOR = { { 0.80, 0.62, 0.42 }, { 1, 1, 1 }, { 1, 0.82, 0 } }

---------------------------------------------------------------------------
-- The reading for where the player stands
---------------------------------------------------------------------------
local function PlayerSeed()
	return (UnitName and UnitName("player") or "?") .. "-" .. (GetRealmName and GetRealmName() or "?")
end

local function GetReading()
	local zone, subzone = ns.CurrentZone()
	local inInstance = IsInInstance and IsInInstance() or false
	return ns.BuildReading(ImmerseMeGeographyCharDB, ns.skills, zone, subzone, inInstance, PlayerSeed())
end

local function FacetLabels(land)
	local out = {}
	for _, facet in ipairs(ns.FACET_ORDER) do
		local v = land[facet]
		if v then out[#out + 1] = ns.Facets[facet][v].label end
	end
	return out
end

local function ItemIcon(res)
	local id = res and res.items[1]
	if not id then return nil end
	if GetItemIcon then return GetItemIcon(id) end
	if C_Item and C_Item.GetItemIconByID then return C_Item.GetItemIconByID(id) end
end

---------------------------------------------------------------------------
-- Tooltip: the land, then what each of the player's gathering trades has learned here.
-- Resources are shown nowhere else.
---------------------------------------------------------------------------
local function AddLandLines(r, withZone)
	local land = r.land
	if withZone then
		GameTooltip:AddLine(land.zone, GOLD[1], GOLD[2], GOLD[3])
		if land.subzone ~= "" and land.subzone ~= land.zone then
			GameTooltip:AddLine(land.subzone, 0.8, 0.8, 0.8)
		end
	end
	local icons = {}
	for _, facet in ipairs(ns.FACET_ORDER) do
		local v = land[facet]
		if v then icons[#icons + 1] = "|T" .. ns.FacetIcon(land, facet) .. ":16|t " .. ns.Facets[facet][v].label end
	end
	GameTooltip:AddLine(table.concat(icons, "  "), 1, 1, 1)
	if land.wild then GameTooltip:AddLine(ns.Facets.wild[land.wild].desc, LABEL[1], LABEL[2], LABEL[3], true) end
	GameTooltip:AddLine(land.flavor, FLAVOR[1], FLAVOR[2], FLAVOR[3], true)

	for _, prof in ipairs(r.profs) do
		GameTooltip:AddLine(" ")
		GameTooltip:AddLine(("%s (skill %d)"):format(prof.name, prof.skill), GOLD[1], GOLD[2], GOLD[3])
		local any = false
		for _, row in ipairs(r.rows) do
			if row.cat == prof.cat then
				any = true
				local icon = ItemIcon(ns.Resources[row.key])
				local left = (icon and ("|T" .. icon .. ":14|t ") or "") .. row.name
				local right = ns.TIER_WORDS[row.tier] .. (row.uncertain and "?" or "")
					.. (row.unconfirmed and " (unconfirmed)" or "")
				right = right .. (" · %d %s"):format(row.n, ns.CATEGORY_VERB[row.cat])
				if row.last then
					local now = (GetServerTime and GetServerTime()) or time()
					right = right .. ", " .. ns.Ago(now - row.last)
				end
				local c = row.uncertain and LABEL or TIER_COLOR[row.tier]
				GameTooltip:AddDoubleLine(left, right, 0.9, 0.9, 0.9, c[1], c[2], c[3])
			end
		end
		if not any then GameTooltip:AddLine("Nothing gathered here yet.", 0.5, 0.5, 0.5) end
		if r.hints[prof.cat] then
			GameTooltip:AddLine(("There may be richer %s here you have not found."):format(ns.CATEGORY_HINT[prof.cat]),
				FLAVOR[1], FLAVOR[2], FLAVOR[3], true)
		end
	end
end

local function ShowTooltip(owner)
	GameTooltip:SetOwner(owner, "ANCHOR_BOTTOMLEFT")
	AddLandLines(GetReading(), true)
	GameTooltip:Show()
end

---------------------------------------------------------------------------
-- The land on the minimap. Two styles (/img style):
--   orb (default)  one round, gold-ringed window showing the terrain, on the upper-left of the
--                  minimap's rim: the mirror image of the stock day / night icon (which
--                  ImmerseMe: Weather turns into its sky orb). Sky on the right, land on the left.
--   row            the four facet icons in a row hung on the stock minimap header.
-- Either way it stays inside the minimap cluster, clear of the buffs, and everything else
-- (ground, water, wildness, resources) is in the tooltip.
---------------------------------------------------------------------------
local cluster = MinimapCluster
local readout = CreateFrame("Frame", "ImmerseMeGeographyReadout", cluster or Minimap)
readout:SetFrameStrata("MEDIUM")
readout:SetFrameLevel(Minimap:GetFrameLevel() + 9)
readout:EnableMouse(true)
readout:SetScript("OnEnter", function(self) ShowTooltip(self) end)
readout:SetScript("OnLeave", function() GameTooltip:Hide() end)
readout.icons = {}
for i = 1, #ns.FACET_ORDER do readout.icons[i] = readout:CreateTexture(nil, "ARTWORK") end

-- orb parts: a dark earth-toned disc behind the terrain icon, and the gold ring around it
readout.disc = readout:CreateTexture(nil, "BACKGROUND")
readout.disc:SetTexture("Interface\\Buttons\\WHITE8X8")
readout.disc:SetVertexColor(0.16, 0.13, 0.09)
readout.disc:SetAllPoints(readout)
readout.ring = readout:CreateTexture(nil, "OVERLAY")
do
	local mask = readout.CreateMaskTexture and readout:CreateMaskTexture()
	if mask then
		mask:SetTexture("Interface\\CharacterFrame\\TempPortraitAlphaMask", "CLAMPTOBLACKADDITIVE", "CLAMPTOBLACKADDITIVE")
		mask:SetAllPoints(readout)
		readout.disc:AddMaskTexture(mask)
		readout.mask = mask
	end
end

local ICON_GAP, EDGE_PAD, HEADER_GAP = 1, 4, 2
local ORB_WINDOW, ORB_ICON = 20, 1        -- stand-alone window size; icon as a fraction of the window
-- The icons are square paintings with their own border. In the orb the round gold ring is the
-- border instead: the painting fills the window, cut round, with its square frame cropped away.
local ORB_CROP = 0.09

-- The stock header bar (zone name and clock), if this client has one.
local function Header()
	return (cluster and (cluster.BorderTop or cluster.ZoneTextButton)) or MinimapZoneTextButton
end

-- Centre of a frame or texture in screen pixels, and its scale.
local function ScreenCenter(obj)
	local x, y = obj:GetCenter()
	if not (x and y) then return nil end
	local s = obj.GetEffectiveScale and obj:GetEffectiveScale()
	if not s then
		local parent = obj.GetParent and obj:GetParent()
		s = parent and parent.GetEffectiveScale and parent:GetEffectiveScale() or 1
	end
	return x * s, y * s, s
end

-- true when the header sits below the minimap (Edit Mode: "header underneath").
-- Read from where the header is on screen, so it holds whatever the client calls the setting.
local function HeaderUnderneath(header)
	local _, hy = ScreenCenter(header)
	local _, my = ScreenCenter(Minimap)
	return hy ~= nil and my ~= nil and hy < my
end

-- The stock day / night icon: its sun / moon art and its gold ring, found by their atlas names
-- (UI-HUD-Minimap-DayCycle / NightCycle, ...-Frame-Cycle), the same way ImmerseMe: Weather does.
local stockArt, stockRing
local stockMisses = 0     -- searches in a row that found nothing
local STOCK_TRIES = 5     -- after this many, stop looking (entering the world looks again)
local function FindStock()
	if stockArt or stockMisses >= STOCK_TRIES then return stockArt, stockRing end
	local function search(frame, depth)
		if depth > 5 or frame == readout then return nil end
		local art, ring
		for _, region in ipairs({ frame:GetRegions() }) do
			local atlas = region.GetAtlas and region:GetAtlas()
			if type(atlas) == "string" and atlas:find("Cycle") then
				if atlas:find("Frame") then ring = region else art = region end
			end
		end
		if art then return art, ring end
		for _, child in ipairs({ frame:GetChildren() }) do
			local a, r = search(child, depth + 1)
			if a then return a, r end
		end
	end
	if cluster then stockArt, stockRing = search(cluster, 0) end
	if not stockArt then stockArt, stockRing = search(Minimap, 0) end
	if not stockArt then stockMisses = stockMisses + 1 end
	return stockArt, stockRing
end

local function RenderLand(land)
	local orb = db.style ~= "row"
	readout.disc:SetShown(orb)
	readout.ring:SetShown(orb)
	local size, x = db.size, 0
	for i, facet in ipairs(ns.FACET_ORDER) do
		local tex, value = readout.icons[i], land[facet]
		tex:ClearAllPoints()
		if value and (i == 1 or not orb) then
			tex:SetTexture(ns.FacetIcon(land, facet))
			if orb then
				tex:SetPoint("CENTER")       -- sized with the window in LayoutOrb
				tex:SetTexCoord(ORB_CROP, 1 - ORB_CROP, ORB_CROP, 1 - ORB_CROP)
				if readout.mask and not tex.masked then
					tex:AddMaskTexture(readout.mask)
					tex.masked = true
				end
			else
				tex:SetTexCoord(0, 1, 0, 1)
				if tex.masked then
					tex:RemoveMaskTexture(readout.mask)
					tex.masked = nil
				end
				tex:SetSize(size, size)
				tex:SetPoint("LEFT", readout, "LEFT", x, 0)
				x = x + size + ICON_GAP
			end
			tex:Show()
		else
			tex:Hide()
		end
	end
	if not orb then readout:SetSize(max(1, x - ICON_GAP), size) end
end

local function LayoutOrb()
	local ring, icon = readout.ring, readout.icons[1]
	local art, stockRingTex = FindStock()
	local scale = readout:GetEffectiveScale()
	local mx, my = ScreenCenter(Minimap)
	local ax, ay, as
	if art then ax, ay, as = ScreenCenter(art) end
	ring:ClearAllPoints()
	if art and ax and as and mx and scale and scale > 0 then
		-- mirror the stock icon across the minimap's vertical axis, at the same size
		local k = as / scale
		local window = (art:GetWidth() or 21) * 0.92 * k
		readout:SetSize(window, window)
		readout:SetPoint("CENTER", Minimap, "CENTER", (mx - ax) / scale + db.xOffset, (ay - my) / scale + db.yOffset)
		local atlas = stockRingTex and stockRingTex.GetAtlas and stockRingTex:GetAtlas()
		local rx, ry
		if atlas then rx, ry = ScreenCenter(stockRingTex) end
		if atlas and rx and stockRingTex then
			ring:SetAtlas(atlas)
			ring:SetTexCoord(0, 1, 0, 1)
			ring:SetSize(stockRingTex:GetWidth() * k, stockRingTex:GetHeight() * k)
			ring:SetPoint("CENTER", readout, "CENTER", (ax - rx) / scale, (ry - ay) / scale)
		else
			ring:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
			ring:SetTexCoord(0, 0.6, 0, 0.6)
			ring:SetSize(window * 1.55, window * 1.55)
			ring:SetPoint("CENTER")
		end
		icon:SetSize(window * ORB_ICON, window * ORB_ICON)
	else
		-- no stock icon on this client: stand on the rim's upper left by ourselves
		local r, a = Minimap:GetWidth() / 2 + 6, math.rad(125)
		readout:SetSize(ORB_WINDOW, ORB_WINDOW)
		readout:SetPoint("CENTER", Minimap, "CENTER", r * math.cos(a) + db.xOffset, r * math.sin(a) + db.yOffset)
		ring:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
		ring:SetTexCoord(0, 1, 0, 1)
		ring:SetSize(50, 50)
		ring:SetPoint("TOPLEFT", readout, "TOPLEFT", -5.5, 5.5)
		icon:SetSize(ORB_WINDOW * ORB_ICON, ORB_WINDOW * ORB_ICON)
	end
end

local function LayoutRow()
	local header = Header()
	if header and HeaderUnderneath(header) then
		readout:SetPoint("BOTTOMLEFT", header, "TOPLEFT", EDGE_PAD + db.xOffset, HEADER_GAP + db.yOffset)
	elseif header then
		readout:SetPoint("TOPLEFT", header, "BOTTOMLEFT", EDGE_PAD + db.xOffset, -HEADER_GAP + db.yOffset)
	else
		readout:SetPoint("BOTTOMLEFT", Minimap, "TOPLEFT", db.xOffset, HEADER_GAP + db.yOffset)
	end
end

---------------------------------------------------------------------------
-- Dragging: the land can be moved anywhere inside the minimap circle, out to its rim.
-- The spot is saved as a fraction of the minimap's radius, so it survives a resized minimap.
---------------------------------------------------------------------------
local RIM_PAD = 6     -- how far past the minimap's edge the centre may go (onto the rim, like the stock icon)

-- Where the cursor is, relative to the minimap's centre, held inside the circle.
local function CursorSpot()
	local cx, cy = GetCursorPosition()
	local ms = Minimap:GetEffectiveScale()
	local mx, my = Minimap:GetCenter()
	local R = Minimap:GetWidth() / 2
	local dx, dy = cx - mx * ms, cy - my * ms
	local limit = (R + RIM_PAD) * ms
	local d = math.sqrt(dx * dx + dy * dy)
	if d > limit then dx, dy = dx * limit / d, dy * limit / d end
	return dx / (R * ms), dy / (R * ms)
end

local function PlaceAt(fx, fy)
	local k = Minimap:GetWidth() / 2 * Minimap:GetEffectiveScale() / readout:GetEffectiveScale()
	readout:ClearAllPoints()
	readout:SetPoint("CENTER", Minimap, "CENTER", fx * k, fy * k)
end

local function FollowCursor(self)
	local fx, fy = CursorSpot()
	self.dragSpot = { fx, fy }
	PlaceAt(fx, fy)
end

readout:RegisterForDrag("LeftButton")
readout:SetScript("OnDragStart", function(self)
	if not db then return end
	GameTooltip:Hide()
	self.dragSpot = nil
	self:SetScript("OnUpdate", FollowCursor)
end)
readout:SetScript("OnDragStop", function(self)
	self:SetScript("OnUpdate", nil)
	if db and self.dragSpot then db.pos = self.dragSpot end
	self.dragSpot = nil
end)

local function LayoutReadout()
	readout:ClearAllPoints()
	if db.style == "row" then LayoutRow() else LayoutOrb() end
	if db.pos then PlaceAt(db.pos[1], db.pos[2]) end     -- a dragged spot wins over the automatic one
end

local function Refresh()
	if not db then return end
	RenderLand(GetReading().land)
	LayoutReadout()
	readout:SetShown(db.show)
	-- keep an open tooltip current (a new discovery, a skill-up)
	if GameTooltip:IsShown() and GameTooltip:GetOwner() == readout then ShowTooltip(readout) end
end

local lastError
local function SafeRefresh()
	local ok, err = pcall(Refresh)
	if not ok and err ~= lastError then
		lastError = err
		Print("|cffff6060error:|r " .. tostring(err))
	end
end
ns.OnDiscoveryChanged = SafeRefresh

-- Hovering the stock zone name tells the land too: Geography's lines join the stock tooltip.
local function HookZoneName()
	local button = (cluster and cluster.ZoneTextButton) or MinimapZoneTextButton
	if not (button and button.HookScript) then return end
	button:HookScript("OnEnter", function(self)
		if not (db and db.show) then return end
		local ok = pcall(function()
			if GameTooltip:IsShown() and GameTooltip:GetOwner() == self then
				GameTooltip:AddLine(" ")
				AddLandLines(GetReading(), false)
				GameTooltip:Show()
			else
				ShowTooltip(self)
			end
		end)
		if not ok then GameTooltip:Hide() end
	end)
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("ZONE_CHANGED")
events:RegisterEvent("ZONE_CHANGED_INDOORS")
events:RegisterEvent("ZONE_CHANGED_NEW_AREA")
pcall(events.RegisterEvent, events, "EDIT_MODE_LAYOUTS_UPDATED")   -- the header may have moved
events:SetScript("OnEvent", function(_, event, arg1)
	if event == "ADDON_LOADED" then
		if arg1 ~= ADDON then return end
		ImmerseMeGeographyDB = ImmerseMeGeographyDB or {}
		db = ImmerseMeGeographyDB
		if db.layout ~= DEFAULTS.layout then
			-- earlier builds drew on the minimap's curve; their layout settings mean nothing now
			for _, k in ipairs({ "rows", "words", "arc", "gap", "fontSize", "yOffset", "weatherHint" }) do db[k] = nil end
		end
		for k, v in pairs(DEFAULTS) do
			if db[k] == nil then db[k] = v end
		end
		db.layout = DEFAULTS.layout
		HookZoneName()
		if hooksecurefunc and cluster and cluster.SetHeaderUnderneath then
			hooksecurefunc(cluster, "SetHeaderUnderneath", function() if db then LayoutReadout() end end)
		end
		-- no ticker: the land only changes with the zone, a discovery or a skill-up, and each
		-- of those refreshes it
		SafeRefresh()
	elseif db then
		if event == "PLAYER_ENTERING_WORLD" then
			stockMisses = 0
			-- the minimap may not have settled into place yet: lay out once more shortly
			if C_Timer and C_Timer.After then C_Timer.After(2, SafeRefresh) end
		end
		SafeRefresh()
	end
end)

---------------------------------------------------------------------------
-- Slash commands
---------------------------------------------------------------------------
local HELP = {
	"/img - describe the land here",
	"/img show | hide - show or hide the land on the minimap",
	"/img style orb | row - one terrain orb mirroring the sky orb, or four icons under the header",
	"/img size <12-24> - icon size of the row style",
	"/img x <-60-60> - nudge it right (+) or left (-)",
	"/img y <-60-60> - nudge it up (+) or down (-)",
	"/img known - what this character has learned about this zone",
	"/img forget zone | all - forget this zone (or everything; 'forget all confirm')",
	"/img debug - print gathering casts and loot, and which zone the addon thinks you are in",
	"Drag the land with the left mouse button to move it anywhere on the minimap.",
	"/img reset - restore default layout (and the default spot)",
}

local function Summary(r)
	local text = table.concat(FacetLabels(r.land), " · ") .. "."
	for _, prof in ipairs(r.profs) do
		for _, row in ipairs(r.rows) do
			if row.cat == prof.cat then
				text = text .. (" %s: %s (%s%s)."):format(prof.name, row.short, ns.TIER_WORDS[row.tier]:lower(),
					row.uncertain and "?" or "")
				break
			end
		end
	end
	return r.land.zone .. ": " .. text
end

local function Known(r)
	if #r.profs == 0 then Print("You know no gathering trade, so the land keeps its riches to itself.") return end
	if #r.rows == 0 then Print("You have gathered nothing in " .. r.land.zone .. " yet.") return end
	Print("What you have learned of " .. r.land.zone .. ":")
	local disc = ImmerseMeGeographyCharDB.disc[r.land.zone] or {}
	for _, row in ipairs(r.rows) do
		local subs = {}
		for sub, count in pairs((disc[row.key] or {}).sub or {}) do subs[#subs + 1] = sub .. " " .. count end
		table.sort(subs)
		print(("  %s: %s%s, %d %s%s%s"):format(row.name, ns.TIER_WORDS[row.tier], row.uncertain and "?" or "",
			row.n, ns.CATEGORY_VERB[row.cat], #subs > 0 and (" (" .. table.concat(subs, ", ") .. ")") or "",
			row.unconfirmed and "  |cffff9933unconfirmed|r" or ""))
	end
end

SLASH_IMMERSEMEGEOGRAPHY1 = "/img"
SLASH_IMMERSEMEGEOGRAPHY2 = "/geography"
SlashCmdList.IMMERSEMEGEOGRAPHY = function(input)
	local cmd, arg = (input or ""):match("^%s*(%S*)%s*(.-)%s*$")
	cmd, arg = cmd:lower(), arg:lower()

	if cmd == "" then
		Print(Summary(GetReading()))
		return
	elseif cmd == "help" or cmd == "?" then
		for _, line in ipairs(HELP) do Print(line) end
		return
	elseif cmd == "known" then
		Known(GetReading())
		return
	elseif cmd == "debug" then
		ns.debug = not ns.debug
		Print("Debug " .. (ns.debug and "on: gathering casts and loot are printed." or "off."))
		if ns.debug then
			ns.RefreshSkills()
			Print(ns.SkillReport())
			Print(ns.ZoneReport())
		end
		return
	elseif cmd == "show" then db.show = true
	elseif cmd == "hide" then db.show = false
	elseif cmd == "style" then
		if arg ~= "orb" and arg ~= "row" then Print("Usage: /img style orb | row") return end
		db.style = arg
	elseif cmd == "size" or cmd == "x" or cmd == "y" then
		local v = tonumber(arg)
		if not v then Print("Usage: /img " .. cmd .. " <number>") return end
		if cmd == "size" then db.size = max(12, min(24, floor(v)))
		elseif cmd == "x" then db.xOffset = max(-60, min(60, floor(v)))
		else db.yOffset = max(-60, min(60, floor(v))) end
	elseif cmd == "forget" then
		local disc = ImmerseMeGeographyCharDB.disc
		if arg == "zone" then
			local zone = GetReading().land.zone
			disc[zone] = nil
			Print("You put " .. zone .. " out of your mind.")
		elseif arg == "all confirm" then
			ImmerseMeGeographyCharDB.disc = {}
			Print("Everything this character learned of the land is forgotten.")
		elseif arg == "all" then
			Print("This forgets every zone for this character. Type /img forget all confirm to go ahead.")
			return
		else
			Print("Usage: /img forget zone | all")
			return
		end
	elseif cmd == "reset" then
		db.style, db.size, db.xOffset, db.yOffset = DEFAULTS.style, DEFAULTS.size, DEFAULTS.xOffset, DEFAULTS.yOffset
		db.pos = nil
		Print("Layout reset.")
	else
		Print("Unknown command. Try /img help")
		return
	end
	SafeRefresh()
end
