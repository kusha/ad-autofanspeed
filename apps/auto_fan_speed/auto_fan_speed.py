import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, time

#
# Auto Fan Speed Controller App
#
# Args:
# auto_fan_speed_master_bedroom:
#   module: auto_fan_speed
#   class: AutoFanSpeed
#   temp_sensor: sensor.thermostat_master_bedroom_temperature
#   fan: fan.master_bedroom_fan
#   sun: sun.sun
#   speeds:
#     low: 67
#     medium: 69
#     high: 73
#     sun_offset: -2
#   speed_values:
#     low: 33
#     medium: 67
#     high: 100
#   time:
#     start: "21:00:00"
#     end: "09:30:00"
#     turn_off_at_end_time: True
#  debug: false

class AutoFanSpeed(hass.Hass):

  def initialize(self):
    
    # REQUIRED
    self.temp_sensor  = self.args["temp_sensor"]
    self.sun          = self.args["sun"]
    self.fan          = self.args["fan"]
    
    # DEFAULTS
    self.debug        = True;
    self.low          = 67
    self.medium       = 70
    self.high         = 72
    self.low_sensor   = None
    self.medium_sensor= None
    self.high_sensor  = None
    self.offset       = 0
    self.start        = datetime.strptime("21:00:00", '%H:%M:%S').time()
    self.end          = datetime.strptime("09:30:00", '%H:%M:%S').time()
    self.turn_off     = False
    self.low_speed    = 25
    self.medium_speed = 50
    self.high_speed   = 100
    
    # USER PREFERENCES
    if "speeds" in self.args:
      if "low" in self.args["speeds"]:
        if self.is_numeric(self.args["speeds"]["low"]):
          self.low = int(self.args["speeds"]["low"])
        else:
          self.low_sensor = self.args["speeds"]["low"]
          self.listen_state(self.range_sensor_change, self.low_sensor)

      self.medium = int(self.args["speeds"]["medium"]) if "medium" in self.args["speeds"] else self.medium
      self.high = int(self.args["speeds"]["high"]) if "high" in self.args["speeds"] else self.high
      self.offset = int(self.args["speeds"]["sun_offset"]) if "sun_offset" in self.args["speeds"] else self.offset

    if "speed_values" in self.args:
      self.low_speed = int(self.args["speed_values"]["low"]) if "low" in self.args["speed_values"] else self.low_speed
      self.medium_speed = int(self.args["speed_values"]["medium"]) if "medium" in self.args["speed_values"] else self.medium_speed
      self.high_speed = int(self.args["speed_values"]["high"]) if "high" in self.args["speed_values"] else self.high_speed
    
    if "time" in self.args:
      self.start = datetime.strptime(self.args["time"]["start"], '%H:%M:%S').time() if "start" in self.args["time"] else self.start
      self.end = datetime.strptime(self.args["time"]["end"], '%H:%M:%S').time() if "end" in self.args["time"] else self.end
      self.turn_off = bool(self.args["time"]["turn_off_at_end_time"]) if "turn_off_at_end_time" in self.args["time"] else self.turn_off

    self.run_in(self.configure, 0)


  def configure(self, kwargs):

    init_log = ["\n**** INIT - AUTO FAN SPEED ****\n"]
    
    init_log += [f"FAN           {self.fan}\n"]
    init_log += [f"TEMP SENSOR   {self.temp_sensor}\n"]
    init_log += [f"SPEEDS        OFF < {self.low} > LOW < {self.medium} > MEDIUM < {self.high} > HIGH\n"]
    init_log += [f"SUN OFFSET    {self.offset}\n"]
    init_log += [f"TIME          {self.start} to {self.end}\n"]

    self.listen_state(self.temperature_change, self.temp_sensor)
    
    if self.turn_off:
        self.run_daily(self.hvac_daily_shut_off, self.end)
        init_log += [f"AUTO OFF      {self.end}\n"]
    
    self.debug_log("  ".join(init_log))
    
    self.debug = bool(self.args["debug"]) if "debug" in self.args else self.debug


  def temperature_change(self, entity, attribute, old, new, kwargs):
    
    if self.is_time_okay(self.start, self.end):
      room_temperature = float(new)
      fan_speed_percentage = self.get_target_fan_speed(room_temperature)
      if self.is_speed_update_required(fan_speed_percentage):
        self.call_service("fan/set_percentage", entity_id = self.fan, percentage = fan_speed_percentage)

  def range_sensor_change(self, entity, attribute, old, new, kwargs):
    self.debug_log(f"UPDATE OF SENSOR CHANGE: {entity} {new}")

  def get_target_fan_speed(self, room_temperature):
    
    # if sun is above horizon, then add offset
    sun_above_horizon = self.get_state(self.sun) == "above_horizon"
    offset = self.offset if sun_above_horizon else 0
    fan_speed_percentage = 0
    
    if room_temperature >= self.low + offset: fan_speed_percentage = self.low_speed
    if room_temperature >= self.medium + offset: fan_speed_percentage = self.medium_speed
    if room_temperature >= self.high + offset: fan_speed_percentage = self.high_speed
    
    self.debug_log(f"AUTO FAN SPEED: {str(room_temperature)}/{fan_speed_percentage}%" + (" (SUN OFFSET)" if sun_above_horizon else ""))
      
    return fan_speed_percentage


  def hvac_daily_shut_off(self, kwargs):
    self.call_service("fan/turn_off", entity_id = self.fan)
    self.debug_log("FAN AUTO OFF")


  def is_time_okay(self, start, end):
    current_time = datetime.now().time()
    if (start < end):
      return start <= current_time and current_time <= end
    else:
      return start <= current_time or current_time <= end

  def is_speed_update_required(self, target_fan_speed_percentage):
    current_fan_speed_percentage = float(self.get_state(self.fan, attribute="percentage"))
    if current_fan_speed_percentage != target_fan_speed_percentage:
      self.debug_log(f"SPEED UPDATE: {current_fan_speed_percentage}% -> {target_fan_speed_percentage}%")
      return True
    self.debug_log(f"SPEED UPDATE IS NOT REQUIRED: {current_fan_speed_percentage}%")
    return False

  def debug_log(self, message):
    if self.debug:
      self.log(message)

  @staticmethod
  def is_numeric(value):
    try:
        float(value)
    except ValueError:
        return False
    return True
