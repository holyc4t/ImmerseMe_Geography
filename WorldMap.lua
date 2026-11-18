-- ImmerseMe: Geography - the land orb on the world map, for whichever zone the map shows.
-- It appears only on zone maps where this character has gathered something: an unexplored zone
-- shows nothing. Hover for the same reading as the minimap orb, headed by what the zone is best for.
local ADDON, ns = ...

-- The terrain window and the gold ring around it, in the proportions of Blizzard's minimap
-- buttons: MiniMap-TrackingBorder's opening is about 20 px of its 50.
local WINDOW, RING, RING_OFFSET = 20, 50, 5.5
local X, Y = 8, -36            -- from the map canvas' top-left: under Blizzard's own corner button
local LEVEL = 20                -- frame levels above the canvas, clear of its pins
local CROP = 0.09

local orb, reading, lastError

local function MapReading()
	if not (WorldMapFrame and WorldMapFrame.GetMapID and C_Map and C_Map.GetMapInfo) then return nil end
	if ImmerseMeGeographyDB and ImmerseMeGeographyDB.map == false then return nil end
	local id = WorldMapFrame:GetMapID()
	local zone = id and ns.ZoneForMap(C_Map.GetMapInfo(id))
	if not zone then return nil end
	local r = ns.BuildReading(ImmerseMeGeographyCharDB, ns.skills, zone, "", false, ns.PlayerSeed())
	if #r.rows == 0 then return nil end     -- nothing gathered here yet: not explored
	return r
end

local function ShowTooltip(self)
	if not reading then return end
	GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
	ns.AddLandLines(reading, true, ns.BestFor(reading))
	GameTooltip:Show()
end

local function Refresh()
	if not orb then return end
	reading = MapReading()
	local hovered = GameTooltip:IsShown() and GameTooltip:GetOwner() == orb
	if not reading then
		orb:Hide()
		if hovered then GameTooltip:Hide() end
		return
	end
	orb.art:SetTexture(ns.FacetIcon(reading.land, "terrain"))
	orb:Show()
	if hovered then ShowTooltip(orb) end    -- a fresh gather while the map is open
end

-- Safe to call any time, also before the map exists. An error here must never break the map.
function ns.RefreshWorldMap()
	local ok, err = pcall(Refresh)
	if not ok and err ~= lastError then
		lastError = err
		ns.Print("|cffff6060world map error:|r " .. tostring(err))
	end
end

-- Builds the orb once the map exists: through the map's own corner-button system where the client
-- has it (the map then places it and refreshes it on every map change), else pinned by hand.
local function Create()
	if orb or not WorldMapFrame then return end
	-- A plain frame on the map canvas, refreshed from hooks. Not WorldMapFrame:AddOverlayFrame: that
	-- would put insecure code into Blizzard's own map-change loop and risk tainting the map.
	local canvas = WorldMapFrame.ScrollContainer
		or (WorldMapFrame.GetCanvasContainer and WorldMapFrame:GetCanvasContainer()) or WorldMapFrame
	orb = CreateFrame("Button", nil, canvas)
	orb:SetPoint("TOPLEFT", canvas, "TOPLEFT", X, Y)
	orb:SetFrameLevel((canvas:GetFrameLevel() or 0) + LEVEL)     -- above the map's pins and art
	if hooksecurefunc and WorldMapFrame.OnMapChanged then
		hooksecurefunc(WorldMapFrame, "OnMapChanged", ns.RefreshWorldMap)
	end
	orb:SetSize(WINDOW, WINDOW)

	orb.disc = orb:CreateTexture(nil, "BACKGROUND")
	orb.disc:SetTexture("Interface\\Buttons\\WHITE8X8")
	orb.disc:SetVertexColor(0.16, 0.13, 0.09)
	orb.disc:SetAllPoints(orb)
	orb.art = orb:CreateTexture(nil, "ARTWORK")
	orb.art:SetAllPoints(orb)
	orb.art:SetTexCoord(CROP, 1 - CROP, CROP, 1 - CROP)
	local mask = orb.CreateMaskTexture and orb:CreateMaskTexture()
	if mask then
		mask:SetTexture("Interface\\CharacterFrame\\TempPortraitAlphaMask", "CLAMPTOBLACKADDITIVE", "CLAMPTOBLACKADDITIVE")
		mask:SetAllPoints(orb)
		orb.disc:AddMaskTexture(mask)
		orb.art:AddMaskTexture(mask)
	end
	orb.ring = orb:CreateTexture(nil, "OVERLAY")
	orb.ring:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
	orb.ring:SetSize(RING, RING)
	orb.ring:SetPoint("TOPLEFT", orb, "TOPLEFT", -RING_OFFSET, RING_OFFSET)

	orb:SetScript("OnEnter", ShowTooltip)
	orb:SetScript("OnLeave", function() GameTooltip:Hide() end)
	if WorldMapFrame.HookScript then WorldMapFrame:HookScript("OnShow", ns.RefreshWorldMap) end
	orb:Hide()
	ns.RefreshWorldMap()
end

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:SetScript("OnEvent", function(_, _, name)
	if name == ADDON or name == "Blizzard_WorldMap" then
		local ok, err = pcall(Create)
		if not ok then ns.Print("|cffff6060world map error:|r " .. tostring(err)) end
	end
end)
