--!strict
-- Plays the R6 Thompson idle while this Tool is equipped.
-- Set the IdleAnimationId StringValue to your published animation id
-- (e.g. "rbxassetid://1234567890" or just "1234567890").
-- In Studio play-tests the bundled KeyframeSequence is used when no id is set.

local RunService = game:GetService("RunService")
local KeyframeSequenceProvider = game:GetService("KeyframeSequenceProvider")

local tool = script.Parent :: Tool
local idleIdValue = tool:WaitForChild("IdleAnimationId") :: StringValue

local FADE_TIME = 0.25

local track: AnimationTrack? = nil
local studioTempId: string? = nil

local function resolveAnimationId(): string?
	local id = idleIdValue.Value
	if id ~= "" then
		return if string.match(id, "^%d+$") then "rbxassetid://" .. id else id
	end
	local sequence = tool:FindFirstChild("ThompsonIdle_R6")
	if sequence and sequence:IsA("KeyframeSequence") and RunService:IsStudio() then
		if not studioTempId then
			studioTempId = KeyframeSequenceProvider:RegisterKeyframeSequence(sequence)
		end
		return studioTempId
	end
	warn("[Thompson] IdleAnimationId is empty; publish ThompsonIdle_R6 and paste its id")
	return nil
end

local function stopTrack()
	if track then
		track:Stop(FADE_TIME)
		track:Destroy()
		track = nil
	end
end

tool.Equipped:Connect(function()
	local character = tool.Parent
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if not humanoid then
		return
	end
	if humanoid.RigType ~= Enum.HumanoidRigType.R6 then
		warn("[Thompson] ThompsonIdle_R6 targets R6 characters only")
		return
	end
	local animator = humanoid:FindFirstChildOfClass("Animator") or humanoid:WaitForChild("Animator", 5)
	local id = resolveAnimationId()
	if not (animator and id) then
		return
	end

	stopTrack()
	local animation = Instance.new("Animation")
	animation.AnimationId = id
	local newTrack = (animator :: Animator):LoadAnimation(animation)
	newTrack.Priority = Enum.AnimationPriority.Action
	newTrack.Looped = true
	newTrack:Play(FADE_TIME)
	track = newTrack
end)

tool.Unequipped:Connect(stopTrack)
