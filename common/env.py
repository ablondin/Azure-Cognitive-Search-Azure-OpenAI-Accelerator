import datetime
import numpy as np



house_properties = {
    "init_air_temp": 20,
    "init_mass_temp": 20,
    "target_temp": 20,
    "tolerance_temp": 2,
    "Ua": 2.18e02,  # House walls conductance (W/K). Multiplied by 3 to account for drafts (according to https://dothemath.ucsd.edu/2012/11/this-thermal-house/)
    "Cm": 3.45e06,  # House thermal mass (J/K) (area heat capacity:: 40700 J/K/m2 * area 100 m2)
    "Ca": 9.08e05,  # Air thermal mass in the house (J/K): 3 * (volumetric heat capacity: 1200 J/m3/K, default area 100 m2, default height 2.5 m)
    "Hm": 2.84e03,  # House mass surface conductance (W/K) (interioor surface heat tansfer coefficient: 8.14 W/K/m2; wall areas = Afloor + Aceiling + Aoutwalls + Ainwalls = A + A + (1+IWR)*h*R*sqrt(A/R) = 455m2 where R = width/depth of the house (default R: 1.5) and IWR is I/O wall surface ratio (default IWR: 1.5))
    "hvac_properties": {
        "id": "hvac_1",
        "COP": 2.5,
        "cooling_capacity": 5000, # W
        "latent_cooling_fraction": 0.35,
    },
    "heater_properties": {
        "id": "heater_1",
        "heating_capacity": 10000,  # W
    },
    "EV_properties": {
        "id": "EV_1",
        "battery_capacity": 40000, # Wh
        "max_autonomy": 200, # km
        "battery_level": 40000, # Wh
        "init_autonomy_objective": 200, # km
        "charging_power": 9000, # W
        "charging_efficiency": 0.9, # Ratio
    }
}


sim_properties = {
    "start_time": "2020-01-01 00:00:00",
    "house_properties": house_properties,
    "max_mean_temp": 25,    # Max mean temperature in Celsius
    "min_mean_temp": -15,   # Min mean temperature in Celsius
    "temp_daily_var": 10,   # Daily temperature variation in Celsius
}


class Simulator():
    def __init__(self, sim_properties):
        self.sim_properties = sim_properties
        self.time = self.init_time()
        self.house = self.init_house()
        self.update_ODtemperature()

    def init_time(self):
        time = datetime.datetime.strptime(self.sim_properties['start_time'], '%Y-%m-%d %H:%M:%S')
        return time

    def init_house(self):
        house = House(self.sim_properties["house_properties"])
        return house

    def step(self, action, time_step):
        """
        Take a time step for the house

        Input: action (dict), time_step (seconds)
        Return: Env current state (dict)
    
        """
        self.time += datetime.timedelta(seconds=time_step)
        
        self.update_ODtemperature()

        self.house.step(self.OD_temp, datetime.timedelta(seconds=time_step), self.time, action)

        env_state = self.get_env_state()
        return env_state
    
    def get_env_state(self):
        house_state = self.house.get_house_state()
        env_state = {
            'house_state': house_state,
            'time': self.time,
            'OD_temp': self.OD_temp
        }

        return env_state

    def update_ODtemperature(self):
        self.OD_temp = self.compute_ODtemperature(self.time)

    def compute_ODtemperature(self, time):    
        """
        Computes the outdoors temperature based on the time (sinusoidal function on the day of the year (coldest Jan 1st, hottest in July 1st), + sinusoidal function on the hour of the day (coldest at 12am, hottest at 12pm)  --> extremes = coldest on Jan 1st at night, hottest on July 1st at noon
        """
        day_of_year = time.timetuple().tm_yday  # returns 1 for January 1st, 365 or 366 for December 31st
        hour_of_day = time.hour

        max_mean = self.sim_properties['max_mean_temp']
        min_mean = self.sim_properties['min_mean_temp']
        temp_daily_var = self.sim_properties['temp_daily_var']
        
        mean_temp = -np.cos(day_of_year/365 * 2*np.pi) * (max_mean - min_mean)/2 + (max_mean + min_mean)/2

        OD_temp = mean_temp + np.cos((hour_of_day)/24 * 2*np.pi + np.pi) * temp_daily_var/2

        return OD_temp
        


######### House #########


class House():
    """
    Single house simulator.

    Attributes:
    house_properties: dictionary, containing the configuration properties of the House object
    init_air_temp: float, initial indoors air temperature of the house, in Celsius
    init_mass_temp: float, initial indoors mass temperature of the house, in Celsius
    current_temp: float, current indoors air temperature of the house, in Celsius
    current_mass_temp: float, current house mass temperature, in Celsius
    target_temp: float, target indoors air temperature of the house, in Celsius
    tolerance_temp: float, tolerance for the indoors air temperature of the house, in Celsius
    Ua: float, House conductance in Watts/Kelvin
    Ca: float, Air thermal mass, in Joules/Kelvin (or Watts/Kelvin.second)
    Hm: float, House mass surface conductance, in Watts/Kelvin
    Cm: float, House thermal mass, in Joules/Kelvin (or Watts/Kelvin.second)
    device_properties: dictionary, containing the properties of the houses' devices
    ac: ac object for the house
    heater: heater object for the house
    ac: ac object for the house
    disp_count: int, iterator for printing count

    Functions:
    step(self, od_temp, time_step): Take a time step for the house
    update_temperature(self, od_temp, time_step): Compute the new temperatures depending on the state of the house's HVACs
    """

    def __init__(self, house_properties):
        """
        Initialize the house

        Parameters:
        house_properties: dictionary, containing the configuration properties of the SingleHouse
        """

        self.house_properties = house_properties
        self.init_air_temp = house_properties["init_air_temp"]
        self.current_temp = self.init_air_temp
        self.init_mass_temp = house_properties["init_mass_temp"]
        self.current_mass_temp = self.init_mass_temp


        # Thermal constraints
        self.target_temp = house_properties["target_temp"]
        self.tolerance_temp = house_properties["tolerance_temp"]

        # Thermodynamic properties
        self.Ua = house_properties["Ua"]
        self.Ca = house_properties["Ca"]
        self.Hm = house_properties["Hm"]
        self.Cm = house_properties["Cm"]


        # Heating and cooling devices
        self.hvac_properties = house_properties["hvac_properties"]
        self.heater_properties = house_properties["heater_properties"]

        self.hvac = HVAC(self.hvac_properties)
        self.heater = Heater(self.heater_properties)


        # Electric vehicle
        self.EV = ElectricVehicle(house_properties["EV_properties"])

    def step(self, od_temp, time_step, date_time, action):
        """
        Take a time step for the house

        Return: -

        Parameters:
        self
        od_temp: float, current outdoors temperature in Celsius
        time_step: timedelta, time step duration
        date_time: datetime, current date and time
        target_temp_command: float to the new target temperature, None if not necessary to command
        """

        target_temp_command = action["target_temp_command"]

        self.update_temperature(od_temp, time_step, date_time)

        if target_temp_command:
            self.target_temp = target_temp_command

        self.hvac.step(self.target_temp, self.tolerance_temp, self.current_temp)
        self.heater.step(self.target_temp, self.tolerance_temp, self.current_temp)

        self.EV.step(time_step, action["EV_action"])

    def get_house_state(self):
        """
        Return the state of the house

        Return: dict
        """

        house_state = {
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "hvac": self.hvac.get_hvac_state(),
            "heater": self.heater.get_heater_state(),
            "EV": self.EV.get_EV_state(),
            "house_consumption": self.hvac.power_consumption() + self.heater.power_consumption() + self.EV.power_consumption(),
        }

        return house_state


    def update_temperature(self, od_temp, time_step, date_time):
        """
        Update the temperature of the house

        Return: -

        Parameters:
        self
        od_temp: float, current outdoors temperature in Celsius
        time_step: timedelta, time step duration
        date_time: datetime, current date and time


        ---
        Model taken from http://gridlab-d.shoutwiki.com/wiki/Residential_module_user's_guide
        """

        time_step_sec = time_step.seconds
        Hm, Ca, Ua, Cm = self.Hm, self.Ca, self.Ua, self.Cm

        # Convert Celsius temperatures in Kelvin
        od_temp_K = od_temp + 273
        current_temp_K = self.current_temp + 273
        current_mass_temp_K = self.current_mass_temp + 273

        # Heat from hvacs (negative if it is AC)
        Qa = self.hvac.get_Q() + self.heater.get_Q()

        # Heat from inside devices (oven, windows, etc)
        Qm = 0

        # Variables and time constants
        a = Cm * Ca / Hm
        b = Cm * (Ua + Hm) / Hm + Ca
        c = Ua
        d = Qm + Qa + Ua * od_temp_K
        g = Qm / Hm

        r1 = (-b + np.sqrt(b**2 - 4 * a * c)) / (2 * a)
        r2 = (-b - np.sqrt(b**2 - 4 * a * c)) / (2 * a)

        dTA0dt = (
            Hm * current_mass_temp_K / Ca
            - (Ua + Hm) * current_temp_K / Ca
            + Ua * od_temp_K / Ca
            + Qa / Ca
        )

        A1 = (r2 * current_temp_K - dTA0dt - r2 * d / c) / (r2 - r1)
        A2 = current_temp_K - d / c - A1
        A3 = r1 * Ca / Hm + (Ua + Hm) / Hm
        A4 = r2 * Ca / Hm + (Ua + Hm) / Hm

        # Updating the temperature
        old_temp_K = current_temp_K
        new_current_temp_K = (
            A1 * np.exp(r1 * time_step_sec) + A2 * np.exp(r2 * time_step_sec) + d / c
        )
        new_current_mass_temp_K = (
            A1 * A3 * np.exp(r1 * time_step_sec)
            + A2 * A4 * np.exp(r2 * time_step_sec)
            + g
            + d / c
        )

        self.current_temp = new_current_temp_K - 273
        self.current_mass_temp = new_current_mass_temp_K - 273


######### Devices #########

class AbstractDevice(object):
    """
    Abstract class for devices
    """

    def __init__(self, device_properties):
        self.id = device_properties["id"]
        self.device_properties = device_properties

    def step(self, command):
        raise NotImplementedError("Abstract method not implemented")

    def power_consumption(self):
        raise NotImplementedError("Abstract method not implemented")




class HVAC(AbstractDevice):
    """
    Simulator of HVAC object (air conditioner)

    Attributes:

    id: string, unique identifier of the device.
    hvac_properties: dictionary, containing the configuration properties of the HVAC.
    COP: float, coefficient of performance (ratio between cooling capacity and electric power consumption)
    cooling_capacity: float, rate of "negative" heat transfer produced by the HVAC, in Watts
    latent_cooling_fraction: float between 0 and 1, fraction of sensible cooling (temperature) which is latent cooling (humidity)
    turned_on: bool, if the HVAC is currently ON (True) or OFF (False)
    time_step: a timedelta object, representing the time step for the simulation.


    Main functions:

    step(self, command): take a step in time for this TCL, given action of TCL agent
    get_Q(self): compute the rate of heat transfer produced by the HVAC
    power_consumption(self): compute the electric power consumption of the HVAC
    """

    def __init__(self, hvac_properties):
        """
        Initialize the HVAC

        Parameters:
        """

        super().__init__(hvac_properties)
        self.hvac_properties = hvac_properties
        self.COP = hvac_properties["COP"]
        self.cooling_capacity = hvac_properties["cooling_capacity"]
        self.latent_cooling_fraction = hvac_properties["latent_cooling_fraction"]
       
        self.turned_on = False
        self.max_consumption = self.cooling_capacity / self.COP

        if self.latent_cooling_fraction > 1 or self.latent_cooling_fraction < 0:
            raise ValueError(
                "HVAC id: {} - Latent cooling fraction must be between 0 and 1. Current value: {}.".format(
                    self.id, self.latent_cooling_fraction
                )
            )

        if self.cooling_capacity < 0:
            raise ValueError(
                "HVAC id: {} - Cooling capacity must be positive. Current value: {}.".format(
                    self.id, self.cooling_capacity
                )
            )
        if self.COP < 0:
            raise ValueError(
                "HVAC id: {} - Coefficient of performance (COP) must be positive. Current value: {}.".format(
                    self.id, self.COP
                )
            )

    def step(self, target_temp, tolerance_temp, current_temp):
        """
        Turn HVAC on if current temperature is above target temperature + tolerance temperature, turn off if current temperature is below target temperature

        Return: Nothing
        -

        Parameters:
        self
        command: bool, action of the TCL agent (True: ON, False: OFF)
        """
        if current_temp > target_temp + tolerance_temp:
            self.turned_on = True
        elif current_temp < target_temp:
            self.turned_on = False
        else:
            pass

    def get_Q(self):
        """
        Compute the rate of heat transfer produced by the HVAC

        Return:
        q_hvac: float, heat of transfer produced by the HVAC, in Watts

        Parameters:
        self
        """
        if self.turned_on:
            q_hvac = -1 * self.cooling_capacity / (1 + self.latent_cooling_fraction)
        else:
            q_hvac = 0

        return q_hvac

    def power_consumption(self):
        """
        Compute the electric power consumption of the HVAC

        Return:
        power_cons: float, electric power consumption of the HVAC, in Watts
        """
        if self.turned_on:
            power_cons = self.max_consumption
        else:
            power_cons = 0

        return power_cons

    def get_hvac_state(self):
        hvac_state = {
            "turned_on": self.turned_on,
            "power_consumption": self.power_consumption(),
        }
        return hvac_state

class Heater(AbstractDevice):
    """
    Simulator of Heater object (electric heater)

    Attributes:

    id: string, unique identifier of the device.
    heater_properties: dictionary, containing the configuration properties of the heater.
    heating_capacity: float, rate of heat transfer produced by the heater, in Watts
    turned_on: bool, if the heater is currently ON (True) or OFF (False)

    Main functions:

    step(self, command): take a step in time for this heater, given action of heater agent
    get_Q(self): compute the rate of heat transfer produced by the heater
    power_consumption(self): compute the electric power consumption of the heater
    """

    def __init__(self, heater_properties):
        """
        Initialize the heater

        Parameters:
            hvac_properties: dictionary, containing the configuration properties of the HVAC.
        """

        super().__init__(heater_properties)
        self.heater_properties = heater_properties
        self.heating_capacity = heater_properties["heating_capacity"]
       
        self.turned_on = False
        self.max_consumption = self.heating_capacity


        if self.heating_capacity < 0:
            raise ValueError(
                "HVAC id: {} - Cooling capacity must be positive. Current value: {}.".format(
                    self.id, self.heating_capacity
                )
            )

    def step(self, target_temp, tolerance_temp, current_temp):
        """
        Turn heater OFF if current temperature is higher than target temperature, turn ON if current temperature is below target temperature - tolerance temperature

        Return: Nothing
        -

        Parameters:
        self
        command: bool, action of the TCL agent (True: ON, False: OFF)
        """
        if current_temp > target_temp:
            self.turned_on = False
        elif current_temp < target_temp - tolerance_temp:
            self.turned_on = True
        else:
            pass

    def get_Q(self):
        """
        Compute the rate of heat transfer produced by the HVAC

        Return:
        q_hvac: float, heat of transfer produced by the HVAC, in Watts

        Parameters:
        self
        """
        if self.turned_on:
            q_hvac = self.heating_capacity 
        else:
            q_hvac = 0

        return q_hvac

    def power_consumption(self):
        """
        Compute the electric power consumption of the HVAC

        Return:
        power_cons: float, electric power consumption of the HVAC, in Watts
        """
        if self.turned_on:
            power_cons = self.max_consumption
        else:
            power_cons = 0

        return power_cons
    
    def get_heater_state(self):
        heater_state = {
            "turned_on": self.turned_on,
            "power_consumption": self.power_consumption(),
        }
        return heater_state


class ElectricVehicle(AbstractDevice):
    """
    Simulator of Electric Vehicle object (EV)
    
    Attributes:
        -- Car --   
        battery_capacity: float, battery capacity of the EV, in Wh
        max_autonomy: float, maximum autonomy of the EV, in km
        battery_level: float, current battery level of the EV, in Wh
        current_autonomy: float, current autonomy of the EV, in km
        autonomy_objective: float, autonomy objective of the EV, in km
        plug_status: string, status of the EV plug, "plugged" or "unplugged"
        -- Charging station --
        charging_power: float, power of the charging station, in W
        charging_efficiency: float, efficiency of the charging station, ratio
        charging_consumption: float,  consumption of the charging station, in W
        charging_status: string, status of the EV charging station, "idle" or "charging"

    Main functions:
        step(self, time_step, EV_action): take a step in time for this EV, given action of EV agent
        power_consumption(self): compute the electric power consumption of the EV
        get_EV_state(self): return the state of the EV

    """


    def __init__(self, device_properties):
        super().__init__(device_properties)
        self.device_properties = device_properties

        # Car
        self.battery_capacity = device_properties["battery_capacity"]   # Wh
        self.max_autonomy = device_properties["max_autonomy"]           # km
        self.battery_level = device_properties["battery_level"]         # Wh    
        self.current_autonomy = self.max_autonomy * self.battery_level / self.battery_capacity # km     # strong assumption: the autonomy is linear with the battery level
        self.autonomy_objective = device_properties["init_autonomy_objective"] # km

        # Charging station
        self.charging_power = device_properties["charging_power"]                   # W
        self.charging_efficiency = device_properties["charging_efficiency"]         # Ratio
        self.charging_consumption = self.charging_power/self.charging_efficiency    # W

        self.plug_status = "plugged" # "plugged", "unplugged"
        self.charging_status = "idle"   # "idle", "charging"


    def step(self, time_step, EV_action):
        """
        Take a time step for the EV. The EV can be plugged or unplugged, and can charge if it is plugged. 
        The autonomy objective can be set when plugged. This is how an agent can control the consumption of the EV charging process.
        """

        # Accepts a command to plug/unplug the EV, and/or to set the autonomy objective
        if EV_action is None:
            EV_action_plug = None
            EV_action_endtrip_autonomy = None
            EV_action_autonomy_obj = None
        else:
            EV_action_plug = EV_action["plug_action"]
            EV_action_endtrip_autonomy = EV_action["endtrip_autonomy"]
            EV_action_autonomy_obj = EV_action["autonomy_objective"]

        if EV_action_plug == "plug":
            if self.plug_status == "unplugged":
                assert EV_action_endtrip_autonomy is not None   # When the EV is plugged after being unplugged (return from a trip), the remaining autonomy must be told.
                self.battery_level = EV_action_endtrip_autonomy * self.battery_capacity / self.max_autonomy
                self.current_autonomy = EV_action_endtrip_autonomy
            self.plug_status = "plugged" 
            
        elif EV_action_plug == "unplug":
            self.plug_status = "unplugged"

        elif EV_action_plug is None:        # If no command is given, the EV keeps its current plug status and battery level
            pass

        if EV_action_autonomy_obj is not None:      # If such a command is given, the EV sets its autonomy objective
            self.autonomy_objective = EV_action_autonomy_obj


        # If the EV is plugged, it can charge
        ## Charging station decision
        if self.plug_status == "plugged":
            if self.current_autonomy < self.autonomy_objective:
                self.charging_status = "charging"
            elif self.current_autonomy >= self.autonomy_objective:
                self.charging_status = "idle"

        ## Battery level update
            if self.charging_status == "charging":
                self.battery_level += self.charging_power * time_step.seconds / 3600
                if self.battery_level > self.battery_capacity:
                    self.battery_level = self.battery_capacity
                self.current_autonomy = self.max_autonomy * self.battery_level / self.battery_capacity

            elif self.charging_status == "idle":
                pass

   
        # If the EV is unplugged, it cannot charge
        elif self.plug_status == "unplugged":
            self.battery_level = None       # When the EV is unplugged, the battery level is not known
            self.charging_status = "idle"   # The EV cannot charge if it is unplugged
            self.current_autonomy = None    # The autonomy is not known if the EV is unplugged
        
        return self.get_EV_state()  
    
    def power_consumption(self):
        """
        Return the power consumption of the EV
        """
        if self.charging_status == "charging":
            power_cons = self.charging_consumption
        else:
            power_cons = 0
        return power_cons
  
    def get_EV_state(self):
        EV_state = {
            "battery_level": self.battery_level,        
            "current_autonomy": self.current_autonomy,
            "plug_status": self.plug_status,
            "charging_status": self.charging_status,
            "autonomy_objective": self.autonomy_objective,
            "power_consumption": self.power_consumption(),
        }

        return EV_state



    



        

        




    

######### Grid #########

class Grid():
    """
    Grid simulator
    
    Provides a price signal to the house depending on the time of the day, and the current outdoor temperature
    """

    def __init__(self):
        pass




if __name__ == "__main__":


    test_type = "test_HVAC"     # "test_EV", "test_HVAC"
    
    simulator = Simulator(sim_properties)

    if test_type == "test_EV":

        env_state = simulator.get_env_state()

        print("Initial state")
        print(env_state["house_state"]["EV"])
        print("------------------")


        action = {
            'target_temp_command': None,
            'EV_action': {
                'plug_action': 'plug',
                'endtrip_autonomy': 20,
                'autonomy_objective': 200
            }
        }
        env_state = simulator.step(action, 60)

        print("After redundant action of plugging")
        print(env_state["house_state"]["EV"])
        print("------------------")


        action = {
            'target_temp_command': None,
            'EV_action': {
                'plug_action': 'unplug',
                'endtrip_autonomy': None,
                'autonomy_objective': None
            }
        }
        env_state = simulator.step(action, 60)

        print("After unplugging")
        print(env_state["house_state"]["EV"])
        print("------------------")


        action = {
            'target_temp_command': None,
            'EV_action': {
                'plug_action': None,
                'endtrip_autonomy': None,
                'autonomy_objective': None
            }
        }
        
        for i in range(60):
            simulator.step(action, 60)
            env_state = simulator.get_env_state()
        env_state = simulator.step(action, 60)

        print("After 1 hour of unplugged")
        print(env_state["house_state"]["EV"])
        print("------------------")
        
        action = {
            'target_temp_command': None,
            'EV_action': {
                'plug_action': 'plug',
                'endtrip_autonomy': 100,
                'autonomy_objective': 150
            }
        }
        env_state = simulator.step(action, 60)

        print("After plugging back and setting autonomy objective to 150 km")
        print(env_state["house_state"]["EV"])
        print("------------------")


        for i in range(60):
            simulator.step(action, 60)
        env_state = simulator.get_env_state()
        print("After 1 hour of charging")
        print(env_state["house_state"]["EV"])
        print("------------------")


        for i in range(600):
            simulator.step(action, 60)
        env_state = simulator.get_env_state()
        print("After 10 hours of charging")
        print(env_state["house_state"]["EV"])
        print("------------------")

        
        action = {
            'target_temp_command': None,
            'EV_action': {
                'plug_action': None,
                'endtrip_autonomy': None,
                'autonomy_objective': 200
            }
        }   

        env_state = simulator.step(action, 60)
        print("After setting autonomy objective to 200 km")
        print(env_state["house_state"]["EV"])
        print("------------------")

        for i in range(60):
            simulator.step(action, 60)
        env_state = simulator.get_env_state()
        print("After 1 hour of charging")
        print(env_state["house_state"]["EV"])
        print("------------------")


    elif test_type == "test_HVAC":

        sim_properties["start_time"] = "2020-01-01 6:00:00"

        action = {
            'target_temp_command': None,
            'EV_action': None
        }

        for i in range(60*28):
            simulator.step(action, 60)
            env_state = simulator.get_env_state()
            if i % 2 == 0:
                print("Time: {}, Current temp: {:.2f} C, OD temp: {:.2f} C, House consumption: {:.2f} W, HVAC: {}, Heater: {}".format(env_state['time'], env_state['house_state']['current_temp'], env_state['OD_temp'], env_state['house_state']['house_consumption'], env_state['house_state']['hvac']["turned_on"], env_state['house_state']['heater']['turned_on'])) 




