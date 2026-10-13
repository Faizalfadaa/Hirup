-- Free-flow approximation, not a calibrated Jakarta motorcycle speed model.
-- TODO(verify): calibrate motorcycle speeds against sourced Jakarta observations.
local car = dofile('/opt/car.lua')
local upstream_setup = car.setup
local upstream_way = car.process_way
local upstream_node = car.process_node

local function tolled(object)
  for _, key in ipairs({'toll', 'toll:motorcycle', 'toll:forward', 'toll:backward'}) do
    local value = object:get_value_by_key(key)
    if value and value ~= '' and value ~= 'no' and value ~= 'false' and value ~= '0' then
      return true
    end
  end
  return false
end

function car.setup()
  local profile = upstream_setup()
  profile.properties.left_hand_driving = true
  profile.access_tags_hierarchy = Sequence {'motorcycle', 'motor_vehicle', 'vehicle', 'access'}
  profile.restrictions = Sequence {'motorcycle', 'motor_vehicle', 'vehicle'}
  -- Use OSRM's sourced urban default as an explicit cap, not invented speeds.
  local urban_cap = profile.maxspeed_table_default.urban
  for highway, speed in pairs(profile.speeds.highway) do
    profile.speeds.highway[highway] = math.min(speed, urban_cap)
  end
  for key, speed in pairs(profile.maxspeed_table_default) do
    profile.maxspeed_table_default[key] = math.min(speed, urban_cap)
  end
  for key, speed in pairs(profile.maxspeed_table) do
    profile.maxspeed_table[key] = math.min(speed, urban_cap)
  end
  return profile
end

function car.process_way(profile, way, result, relations)
  local highway = way:get_value_by_key('highway')
  if highway == 'motorway' or highway == 'motorway_link' or tolled(way) then
    return
  end
  upstream_way(profile, way, result, relations)
  local cap = profile.maxspeed_table_default.urban
  result.forward_speed = math.min(result.forward_speed, cap)
  result.backward_speed = math.min(result.backward_speed, cap)
end

function car.process_node(profile, node, result, relations)
  if node:get_value_by_key('barrier') == 'toll_booth' or tolled(node) then
    result.barrier = true
    return
  end
  upstream_node(profile, node, result, relations)
end

return car
