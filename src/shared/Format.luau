--!strict
-- Number formatting for simulator-sized values: 1234 -> "1.23K", 5e9 -> "5B".
local Format = {}

local SUFFIXES = { "", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc" }

function Format.Short(n: number): string
	if n ~= n then
		return "0"
	end
	local neg = n < 0
	n = math.abs(n)
	if n < 1000 then
		return (if neg then "-" else "") .. tostring(math.floor(n))
	end
	local i = math.min(math.floor(math.log10(n) / 3), #SUFFIXES - 1)
	local v = n / 1000 ^ i
	local s = if v >= 100 then string.format("%d", math.floor(v)) elseif v >= 10 then string.format("%.1f", math.floor(v * 10) / 10) else string.format("%.2f", math.floor(v * 100) / 100)
	if s:find("%.") then
		s = (s:gsub("0+$", ""))
		s = (s:gsub("%.$", ""))
	end
	return (if neg then "-" else "") .. s .. SUFFIXES[i + 1]
end

return Format
