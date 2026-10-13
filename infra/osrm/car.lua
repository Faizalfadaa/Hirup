-- Reuse the pinned OSRM profile; do not duplicate its speed assumptions.
local car = dofile('/opt/car.lua')
local upstream_setup = car.setup

function car.setup()
  local profile = upstream_setup()
  profile.properties.left_hand_driving = true
  return profile
end

return car
