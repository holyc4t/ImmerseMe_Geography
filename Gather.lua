-- ImmerseMe: Geography - spotting gathering (casts + loot) and reading profession skills.
local ADDON, ns = ...

local PREFIX = "|cffd8b25aImmerseMe: Geography|r "
function ns.Print(msg) print(PREFIX .. msg) end

ns.skills = {}                           -- { Mining = 87, ... }, refreshed from the skill list
ns.debug = false                         -- /img debug: print casts and loot item IDs
ns.OnDiscoveryChanged = function() end   -- set by UI.lua

-- How long after a gathering cast the loot window still counts as its loot.
-- Fishing waits for a bite, so it gets longer.
local WINDOW = { ore = 5, herb = 5, hide = 5, fish = 30 }

---------------------------------------------------------------------------
-- Skills
---------------------------------------------------------------------------

-- Opening and closing skill headers fires SKILL_LINES_CHANGED itself; those echoes are ignored.
local ignoreSkillEventsUntil = 0

-- Newer clients list professions through GetProfessions() / GetProfessionInfo(index).
local function ReadProfessionAPI(out)
	if not (GetProfessions and GetProfessionInfo) then return end
	for _, index in pairs({ GetProfessions() }) do
		local name, _, rank = GetProfessionInfo(index)
		if name and ns.Professions[name] then out[name] = rank or 0 end
	end
end

-- Reads the character's gathering skills: the profession API where the client has it, and the
-- classic skill list. Collapsed headers hide the lines under them, so they are opened for the
-- read and closed again after.
function ns.ReadSkills()
	local out = {}
	ReadProfessionAPI(out)
	if not (GetNumSkillLines and GetSkillLineInfo) then return out end
	local reopened = {}
	local i = 1
	while i <= GetNumSkillLines() do
		local name, isHeader, isExpanded, rank = GetSkillLineInfo(i)
		if isHeader and not isExpanded and ExpandSkillHeader then
			reopened[#reopened + 1] = name
			ExpandSkillHeader(i)
		elseif not isHeader and name and ns.Professions[name] then
			out[name] = rank or 0
		end
		i = i + 1
	end
	if #reopened > 0 then
		ignoreSkillEventsUntil = GetTime() + 1
		if CollapseSkillHeader then
			for j = GetNumSkillLines(), 1, -1 do
				local name, isHeader = GetSkillLineInfo(j)
				if isHeader then
					for _, r in ipairs(reopened) do
						if r == name then CollapseSkillHeader(j) break end
					end
				end
			end
		end
	end
	return out
end

local function RefreshSkills()
	ns.skills = ns.ReadSkills()
	ns.OnDiscoveryChanged()
end
ns.RefreshSkills = RefreshSkills

-- Skill-ups come in bursts (weapon skills in a fight): read the list once, a moment later.
local skillsQueued = false
local function QueueSkills()
	if skillsQueued then return end
	if not (C_Timer and C_Timer.After) then RefreshSkills() return end
	skillsQueued = true
	C_Timer.After(1, function()
		skillsQueued = false
		RefreshSkills()
	end)
end

-- One line for /img debug: which skill APIs this client has and what was found.
function ns.SkillReport()
	local found = {}
	for name, rank in pairs(ns.skills) do found[#found + 1] = name .. " " .. rank end
	table.sort(found)
	return ("skills: skill list %s (%s lines), profession API %s; found: %s"):format(
		GetSkillLineInfo and "yes" or "no", GetNumSkillLines and tostring(GetNumSkillLines()) or "-",
		GetProfessions and "yes" or "no", #found > 0 and table.concat(found, ", ") or "none")
end

---------------------------------------------------------------------------
-- Where the player is
---------------------------------------------------------------------------

-- Under a roof the client can name the building instead of the zone (an inn, a town hall), and
-- the land data would not know it. So the zone is looked for in turn among: the zone texts, the
-- map the player is on and the maps above it, and last (indoors only) the zone they walked in
-- from. A tavern in Duskwood is still Duskwood.
local lastZone      -- the last zone the data knows that the player stood in

local function ZoneNames()
	local names = {}
	local function add(name)
		if type(name) == "string" and name ~= "" then names[#names + 1] = name end
	end
	add(GetRealZoneText and GetRealZoneText())
	add(GetZoneText and GetZoneText())
	if C_Map and C_Map.GetBestMapForUnit and C_Map.GetMapInfo then
		local id, depth = C_Map.GetBestMapForUnit("player"), 0
		while id and id ~= 0 and depth < 6 do
			local info = C_Map.GetMapInfo(id)
			if type(info) ~= "table" then break end
			add(info.name)
			id, depth = info.parentMapID, depth + 1
		end
	end
	return names
end

-- Returns the zone and sub-zone names to look the land up by ("" when the client gives none).
function ns.CurrentZone()
	local subzone = GetSubZoneText and GetSubZoneText() or ""
	local names = ZoneNames()
	for _, name in ipairs(names) do
		if ns.Zones[name] then
			lastZone = name
			return name, subzone
		end
	end
	local inInstance = IsInInstance and IsInInstance() or false
	local roofed = (IsIndoors and IsIndoors()) or (IsResting and IsResting()) or false
	if roofed and not inInstance then
		if lastZone then return lastZone, subzone end
	else
		lastZone = nil      -- out in the open in a land the data doesn't know: nothing to carry indoors
	end
	return names[1] or "", subzone
end

-- One line for /img debug: every name the client offers, and the one that was chosen.
function ns.ZoneReport()
	local names = ZoneNames()
	local zone, subzone = ns.CurrentZone()
	return ("zone: client says %s; sub-zone '%s'; using '%s'%s"):format(
		#names > 0 and ("'" .. table.concat(names, "', '") .. "'") or "nothing", subzone, zone,
		ns.Zones[zone] and "" or " (not in the land data)")
end

---------------------------------------------------------------------------
-- Gathering
---------------------------------------------------------------------------

local pending      -- { cat = "ore", at = GetTime() }: the last gathering cast

local function SpellName(spellID)
	if GetSpellInfo then return (GetSpellInfo(spellID)) end
	if C_Spell and C_Spell.GetSpellInfo then
		local info = C_Spell.GetSpellInfo(spellID)
		return info and info.name
	end
end

local function OnCast(unit, spellID)
	if unit ~= "player" or not spellID then return end
	local name = SpellName(spellID)
	local cat = ns.CategoryForCast(name, spellID)
	if ns.debug then
		ns.Print(("cast %s (%s) -> %s"):format(tostring(name), tostring(spellID), tostring(cat or "-")))
	end
	if cat then pending = { cat = cat, at = GetTime() } end
end

local function OnLoot()
	local ids = {}
	for slot = 1, (GetNumLootItems and GetNumLootItems() or 0) do
		local id = ns.ItemIDFromLink(GetLootSlotLink(slot))
		if id then ids[#ids + 1] = id end
	end
	if ns.debug then
		ns.Print("loot: " .. (#ids > 0 and table.concat(ids, ", ") or "(no items)")
			.. (pending and (" after " .. pending.cat) or " (no gathering cast)"))
	end
	if not pending or GetTime() - pending.at > WINDOW[pending.cat] then return end
	if #ids == 0 then return end      -- nothing to read yet (LOOT_READY may come before the items)
	-- a corpse looted while the line was still out is not a catch (where the client can tell)
	if pending.cat == "fish" and IsFishingLoot and not IsFishingLoot() then return end
	local cat = pending.cat
	pending = nil

	local zone, subzone = ns.CurrentZone()
	if zone == "" then return end
	local t = (GetServerTime and GetServerTime()) or time()
	local changed = false
	for _, key in ipairs(ns.MatchLoot(ids, cat)) do
		if ns.RecordGather(ImmerseMeGeographyCharDB, zone, subzone, key, t) then
			ns.Print(("You learn that this land holds %s."):format(ns.Resources[key].name))
		end
		changed = true
	end
	if changed then ns.OnDiscoveryChanged() end
end

---------------------------------------------------------------------------
-- Events
---------------------------------------------------------------------------
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("SKILL_LINES_CHANGED")
-- only the player's own casts matter: never be woken by anyone else's
for _, e in ipairs({ "UNIT_SPELLCAST_SUCCEEDED", "UNIT_SPELLCAST_CHANNEL_START" }) do   -- fishing is a channel
	if events.RegisterUnitEvent then events:RegisterUnitEvent(e, "player") else events:RegisterEvent(e) end
end
events:RegisterEvent("LOOT_OPENED")
events:RegisterEvent("LOOT_READY")                     -- fast-loot addons empty the window before LOOT_OPENED
events:RegisterEvent("ZONE_CHANGED_NEW_AREA")          -- a second chance for skills missed at login
events:SetScript("OnEvent", function(_, event, a1, a2, a3)
	if event == "ADDON_LOADED" then
		if a1 ~= ADDON then return end
		ImmerseMeGeographyCharDB = ImmerseMeGeographyCharDB or {}
		ImmerseMeGeographyCharDB.disc = ImmerseMeGeographyCharDB.disc or {}
	elseif event == "PLAYER_ENTERING_WORLD" then
		RefreshSkills()
		-- right after login the skill list can still be empty: look again shortly
		if not next(ns.skills) and C_Timer and C_Timer.After then C_Timer.After(3, RefreshSkills) end
	elseif event == "ZONE_CHANGED_NEW_AREA" then
		RefreshSkills()
	elseif event == "SKILL_LINES_CHANGED" then
		if GetTime() >= ignoreSkillEventsUntil then QueueSkills() end
	elseif event == "UNIT_SPELLCAST_SUCCEEDED" or event == "UNIT_SPELLCAST_CHANNEL_START" then
		OnCast(a1, a3)
	elseif event == "LOOT_OPENED" or event == "LOOT_READY" then
		OnLoot()
	end
end)
