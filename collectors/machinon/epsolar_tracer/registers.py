import datetime
from enum import Enum, IntEnum
import logging

from pymodbus.register_read_message import ReadRegistersResponseBase


class RegisterType(Enum):
    COIL = "coil"
    DISCRETE = "discrete"
    INPUT = "input"
    HOLDING = "holding"
    UNKNOWN = "unknown"


class RegisterUnit(Enum):
    """UNIT = (abbreviation, single, plural)"""

    VOLT = ("V", "volt", "volts")
    AMP = ("A", "amp", "amps")
    AH = ("A⋅h", "amp hour", "amp hours")
    WATT = ("W", "watt", "watts")
    KWH = ("kW⋅h", "kilowatt hour", "kilowatt hours")
    CELSIUS = ("°C", "celsius", "celsius")
    PERCENT = ("%", "percent", "percent")
    TON = ("T", "ton", "tons")
    HOUR = ("h", "hour", "hours")
    MINUTE = ("m", "minute", "minutes")
    SECOND = ("s", "second", "seconds")
    NONE = ("", "", "")


class RegisterValue:
    def __init__(self, register, raw_value):
        self.register = register
        self.raw_value = raw_value

        if self.register.multiplier != 1 and raw_value is not None:
            self.value = float(raw_value) / self.register.multiplier
        else:
            self.value = raw_value

    def __repr__(self):
        if self.value is None:
            return f"{self.register.description} = {self.value}"

        if self.value == 1:
            unit = self.register.unit.value[1]
        else:
            unit = self.register.unit.value[2]

        return f"{self.register.description} = {self.value} {unit}"

    def __str__(self):
        if self.value is None:
            return str(self.value)
        return f"{self.value} {self.register.unit.value[0]}"

    def __float__(self):
        return float(self.value)

    def __int__(self):
        return int(self.value)


class Register:
    def __init__(
        self,
        address,
        description="",
        unit: RegisterUnit = RegisterUnit.NONE,
        multiplier=1,
        size=1,
    ):
        self.logger = logging.getLogger(__name__)

        self.address = address
        self.size = size
        self.description = description
        self.unit = unit
        self.multiplier = multiplier

        if 0x0 <= self.address < 0x1000:
            self.type = RegisterType.COIL
        elif 0x1000 <= self.address < 0x3000:
            self.type = RegisterType.DISCRETE
        elif 0x3000 <= self.address < 0x9000:
            self.type = RegisterType.INPUT
        elif 0x9000 <= self.address < 0x10000:
            self.type = RegisterType.HOLDING
        else:
            self.type = RegisterType.UNKNOWN

    def encode(self, value):
        raw_value = int(value * self.multiplier)
        values = []
        for i in range(self.size):
            values.append((raw_value >> (i * 16)) & 0xFFFF)
        self.logger.debug(f"Encoded {value} to {values}")
        return values

    def decode(self, response: ReadRegistersResponseBase) -> RegisterValue:
        if not hasattr(response, "registers"):
            self.logger.info(f"No value for register {self.description}")
            return RegisterValue(self, None)

        raw_value = 0
        for i in range(len(response.registers)):
            raw_value |= response.registers[i] << (i * 16)

        # If this is a negative number, it needs to be sign-extended for python to interpret it properly
        if (response.registers[-1] & 0x8000) == 0x8000:
            raw_value -= 1 << len(response.registers) * 16

        self.logger.debug(f"Decoded {response.registers} to {raw_value}")

        return RegisterValue(self, raw_value)


class RTC(Register):
    def __init__(self, address):
        super().__init__(address, "Real-time Clock", size=3)

    def decode(self, response: ReadRegistersResponseBase) -> RegisterValue:
        register_value = super().decode(response)

        if register_value.value is not None:
            value = int(register_value.value)
            year = ((value & 0xFF0000000000) >> 40) + 2000
            month = (value & 0x00FF00000000) >> 32
            day = (value & 0x0000FF000000) >> 24
            hour = (value & 0x000000FF0000) >> 16
            minute = (value & 0x00000000FF00) >> 8
            second = value & 0x0000000000FF
            register_value.value = datetime.datetime(
                year, month, day, hour, minute, second
            )

        return register_value

    def encode(self, value: datetime.datetime):
        if hasattr(value, "year"):
            register_value = 0x0
            register_value |= (value.year - 2000) << 40
            register_value |= value.month << 32
            register_value |= value.day << 24
            register_value |= value.hour << 16
            register_value |= value.minute << 8
            register_value |= value.second
        else:
            register_value = value

        return super().encode(register_value)


class Coil(Register):
    def decode(self, response):
        if not hasattr(response, "bits"):
            self.logger.info("No value for coil " + repr(self.description))
            return RegisterValue(self, None)

        return RegisterValue(self, response.bits[0])


class StatusRegister(Register):
    def __init__(self, address, describe_fn, **kwargs):
        super().__init__(address, **kwargs)
        self.describe = describe_fn


class RatedData:
    ArrayRatedVoltage = Register(
        0x3000,
        description="PV array rated voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    ArrayRatedCurrent = Register(
        0x3001,
        description="PV array rated current",
        unit=RegisterUnit.AMP,
        multiplier=100,
    )
    ArrayRatedPower = Register(
        0x3002,
        description="PV array rated power",
        unit=RegisterUnit.WATT,
        multiplier=100,
        size=2,
    )
    ChargingRatedVoltage = Register(
        0x3004,
        description="Rated charging voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    ChargingRatedCurrent = Register(
        0x3005,
        description="Rated charging current",
        unit=RegisterUnit.AMP,
        multiplier=100,
    )
    ChargingRatedPower = Register(
        0x3006,
        description="Rated charging power",
        unit=RegisterUnit.WATT,
        multiplier=100,
        size=2,
    )
    ChargingMode = Register(
        0x3008, description="Charging mode: 0=connect/disconnect, 1=PWM, 2=MPPT"
    )
    LoadRatedCurrent = Register(
        0x300E, description="Rated load current", unit=RegisterUnit.AMP, multiplier=100
    )


class RealtimeData:
    PvArrayInputVoltage = Register(
        0x3100, description="PV array voltage", unit=RegisterUnit.VOLT, multiplier=100
    )
    PvArrayInputCurrent = Register(
        0x3101, description="PV array current", unit=RegisterUnit.AMP, multiplier=100
    )
    PvArrayInputPower = Register(
        0x3102,
        description="PV array power",
        unit=RegisterUnit.WATT,
        multiplier=100,
        size=2,
    )
    BatteryVoltage = Register(
        0x3104, description="Battery voltage", unit=RegisterUnit.VOLT, multiplier=100
    )
    BatteryCurrent = Register(
        0x3105,
        description="Battery charging current",
        unit=RegisterUnit.AMP,
        multiplier=100,
    )
    BatteryPower = Register(
        0x3106,
        description="Battery charging power",
        unit=RegisterUnit.WATT,
        multiplier=100,
        size=2,
    )
    LoadVoltage = Register(
        0x310C, description="Load voltage", unit=RegisterUnit.VOLT, multiplier=100
    )
    LoadCurrent = Register(
        0x310D, description="Load current", unit=RegisterUnit.AMP, multiplier=100
    )
    LoadPower = Register(
        0x310E, description="Load power", unit=RegisterUnit.WATT, multiplier=100, size=2
    )
    BatteryTemperature = Register(
        0x3110,
        description="Battery temperature",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    EquipmentTemperature = Register(
        0x3111,
        description="Case temperature",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    PowerComponentsTemperature = Register(
        0x3112,
        description="Power components temperature",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    BatterySOC = Register(
        0x311A, description="Battery state of charge", unit=RegisterUnit.PERCENT
    )
    RemoteBatteryTemperature = Register(
        0x311B,
        description="Remote sensor battery temperature",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    BatteryRealRatedPower = Register(
        0x311D,
        description="Battery rated voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )


class RealtimeStatus:
    def describe_battery_status(val: int):
        """BatteryStatus bits:
        D15: 1-Wrong identification for rated voltage
        D8: Battery inner resistance abnormal 1, normal 0
        D7-D4: 00H Normal, 01H Over Temp.(Higher than the warning settings), 02H Low Temp.(Lower than the warning settings)
        D3-D0: 00H Normal, 01H Overvolt, 02H Under Volt, 03H Low Volt Disconnect, 04H Fault
        """
        status = []
        faults = []

        if val & (1 << 15):
            faults.append("Wrong identification for rated voltage")
        if val & (1 << 8):
            faults.append("Battery internal resistance abnormal")
        else:
            status.append("Battery internal resistance normal")
        if (val & 0x00F0) >> 4 == 2:
            faults.append("Battery temperature too low")
        if (val & 0x00F0) >> 4 == 1:
            faults.append("Battery temperature too high")
        if (val & 0x00F0) >> 4 == 0:
            faults.append("Battery temperature normal")
        if val & 0x000F == 4:
            faults.append("Voltage fault")
        if val & 0x000F == 3:
            faults.append("Low voltage disconnect")
        if val & 0x000F == 2:
            faults.append("Voltage too low")
        if val & 0x000F == 1:
            faults.append("Voltage too high")
        if val & 0x000F == 0:
            faults.append("Voltage normal")

        return (status, faults)

    BatteryStatus = StatusRegister(
        0x3200,
        description="Battery voltage/temperature status",
        describe_fn=describe_battery_status,
    )

    def describe_charging_equipment_status(val: int):
        """ChargingEquipmentStatus bits:
        D15-D14: Input voltage status: 00 normal, 01 no power connected, 02H Higher volt input, 03H Input volt error
        D13: Charging MOSFET is short
        D12: Charging or Anti-reverse MOSFET is short
        D11: Anti-reverse MOSFET is short
        D10: Input is over current
        D9: Load is over current
        D8: Load is short
        D7: Load MOSFET is short
        D4: PV Input is short
        D3-2: Charging status: 00 Not charging, 01 Float, 02 Boost, 03 Equalization
        D1: Charging status: 0 Normal, 1 Fault
        D0: Charging status: 1 Running, 0 Standby
        """
        status = []
        faults = []

        if (val & 0xC000) >> 14 == 3:
            faults.append("Input voltage error")
        if (val & 0xC000) >> 14 == 2:
            faults.append("Input voltage too high")
        if (val & 0xC000) >> 14 == 1:
            faults.append("Input voltage disconnected")
        if (val & 0xC000) >> 14 == 0:
            status.append("Input voltage normal")
        if val & (1 << 13):
            faults.append("Charging MOSFET is shorted")
        if val & (1 << 12):
            faults.append("Charging or anti-reverse MOSFET is shorted")
        if val & (1 << 11):
            faults.append("Anti-reverse MOSFET is shorted")
        if val & (1 << 10):
            faults.append("Input current too high")
        if val & (1 << 9):
            faults.append("Load current too high")
        if val & (1 << 8):
            faults.append("Load is shorted")
        if val & (1 << 7):
            faults.append("Load MOSFET is shorted")
        if val & (1 << 4):
            faults.append("PV input is shorted")
        if (val & 0xC) >> 2 == 3:
            status.append("Mode is equalization")
        if (val & 0xC) >> 2 == 2:
            status.append("Mode is boost")
        if (val & 0xC) >> 2 == 1:
            status.append("Mode is float")
        if (val & 0xC) >> 2 == 0:
            status.append("Not charging")
        if val & (1 << 1):
            faults.append("Charging fault")
        else:
            status.append("Charging system normal")
        if val & 1:
            status.append("Charging system active")
        else:
            status.append("Charging system standby")

        return (status, faults)

    ChargingEquipmentStatus = StatusRegister(
        0x3201,
        description="Charging equipment voltage/current status",
        describe_fn=describe_charging_equipment_status,
    )

    def describe_discharging_equipment_status(val: int):
        """DischargingEquipmentStatus bits:
        D15-D14: 00H normal, 01H low, 02H High, 03H no access Input volt error.
        D13-D12: output power: 00H light load, 01H moderate, 02H rated, 03H overload
        D11: short circuit
        D10: unable to discharge
        D9: unable to stop discharging
        D8: output voltage abnormal
        D7: input overpressure
        D6: high voltage side short circuit
        D5: boost overpressure
        D4: output overpressure
        D1: 0 Normal, 1 Fault
        D0: 1 Running, 0 Standby
        """
        status = []
        faults = []

        if (val & 0xC000) >> 14 == 3:
            faults.append("Input voltage error")
        if (val & 0xC000) >> 14 == 2:
            faults.append("Input voltage too high")
        if (val & 0xC000) >> 14 == 1:
            faults.append("Input voltage too low")
        if (val & 0xC000) >> 14 == 0:
            status.append("Input voltage normal")
        if (val & 0x3000) >> 12 == 3:
            faults.append("Output power overload")
        if (val & 0x3000) >> 12 == 2:
            status.append("Output power near rated limit")
        if (val & 0x3000) >> 12 == 1:
            status.append("Output power moderate")
        if (val & 0x3000) >> 12 == 0:
            status.append("Output power light load")
        if val & (1 << 11):
            faults.append("Short circuit")
        if val & (1 << 10):
            faults.append("Unable to discharge")
        if val & (1 << 9):
            faults.append("Unable to stop discharging")
        if val & (1 << 8):
            faults.append("Output voltage abnormal")
        if val & (1 << 7):
            faults.append("Input current too high")
        if val & (1 << 6):
            faults.append("PV input is shorted")
        if val & (1 << 5):
            faults.append("Boost current too high")
        if val & (1 << 4):
            faults.append("Output current too high")
        if val & (1 << 1):
            faults.append("Discharging fault")
        else:
            status.append("Discharging system normal")
        if val & 1:
            status.append("Discharging system active")
        else:
            status.append("Discharging system standby")

        return (status, faults)

    DischargingEquipmentStatus = StatusRegister(
        0x3202,
        description="Load equipment status",
        describe_fn=describe_discharging_equipment_status,
    )


class StatisticalParameter:
    MaximumPVVoltageToday = Register(
        0x3300,
        description="Maximum PV voltage since midnight",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    MinimunPVVoltageToday = Register(
        0x3301,
        description="Minimum PV voltage since midnight",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    MaximumBatteryVoltageToday = Register(
        0x3302,
        description="Maximum battery voltage since midnight",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    MinimumBatteryVoltageToday = Register(
        0x3303,
        description="Minimum battery voltage since midnight",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    ConsumedEnergyToday = Register(
        0x3304,
        description="Energy consumed since midnight",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    ConsumedEnergyMonth = Register(
        0x3306,
        description="Energy consumed since the first of the month",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    ConsumedEnergyYear = Register(
        0x3308,
        description="Energy consumed since the first of the year",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    TotalConsumedEnergy = Register(
        0x330A,
        description="Total energy consumed",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    GeneratedEnergyToday = Register(
        0x330C,
        description="Energy generated since midnight",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    GeneratedEnergyMonth = Register(
        0x330E,
        description="Energy generated since the first of the month",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    GeneratedEnergyYear = Register(
        0x3310,
        description="Energy generated since the first of the year",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    TotalGeneratedEnergy = Register(
        0x3312,
        description="Total energy generated",
        unit=RegisterUnit.KWH,
        multiplier=100,
        size=2,
    )
    CarbonDioxideReduction = Register(
        0x3314,
        description="Carbon dioxide reduction",
        unit=RegisterUnit.TON,
        multiplier=100,
        size=2,
    )
    BatteryVoltage = Register(
        0x331A, description="Battery voltage", unit=RegisterUnit.VOLT, multiplier=100
    )
    BatteryCurrent = Register(
        0x331B,
        description="Net battery current",
        unit=RegisterUnit.AMP,
        multiplier=100,
        size=2,
    )
    BatteryTemperature = Register(
        0x331D,
        description="Battery temperature",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    AmbientTemperature = Register(
        0x331E,
        description="Ambient temperature",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )


class SettingParameter:
    class BatteryTypeEnum(Enum):
        USER = 0
        SEALED = 1
        GEL = 2
        FLOODED = 3

    BatteryType = Register(0x9000, description="Battery type")
    BatteryCapacity = Register(
        0x9001, description="Rated battery capacity", unit=RegisterUnit.AH
    )
    TemperatureCompensation = Register(
        0x9002,
        description="Temperature compensation coefficient (mV/°C/2V)",
        multiplier=100,
    )
    HighVoltageDisconnect = Register(
        0x9003,
        description="High voltage disconnect",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    ChargingLimitVoltage = Register(
        0x9004,
        description="Charging limit voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    OverVoltageReconnect = Register(
        0x9005,
        description="Over voltage reconnect",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    EqualizationVoltage = Register(
        0x9006,
        description="Equalization voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    BoostVoltage = Register(
        0x9007, description="Boost voltage", unit=RegisterUnit.VOLT, multiplier=100
    )
    FloatVoltage = Register(
        0x9008, description="Float voltage", unit=RegisterUnit.VOLT, multiplier=100
    )
    BoostReconnectVoltage = Register(
        0x9009,
        description="Boost reconnect voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    LowVoltageReconnect = Register(
        0x900A,
        description="Low voltage reconnect",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    UnderVoltageRecover = Register(
        0x900B,
        description="Under voltage recover",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    UnderVoltageWarning = Register(
        0x900C,
        description="Under voltage warning",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    LowVoltageDisconnect = Register(
        0x900D,
        description="Low voltage disconnect",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    DischargingLimitVoltage = Register(
        0x900E,
        description="Discharging limit voltage",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    Clock = RTC(0x9013)
    EqualizationDay = Register(
        0x9016, description="Day of month (1-28) to perform equalization"
    )
    BatteryTempUpperLimit = Register(
        0x9017,
        description="Battery high temperature warning",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    BatteryTempLowerLimit = Register(
        0x9018,
        description="Battery low temperature warning",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    ControllerTempUpperLimit = Register(
        0x9019,
        description="Controller temperature upper limit",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    ControllerTempUpperLimitRecover = Register(
        0x901A,
        description="Controller temperature upper limit recover",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    PowerTempUpperLimit = Register(
        0x901B,
        description="Power component temperature upper limit",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    PowerTempUpperLimitRecover = Register(
        0x901C,
        description="Power component temperature upper limit recover",
        unit=RegisterUnit.CELSIUS,
        multiplier=100,
    )
    LineImpedance = Register(
        0x901D, description="Wire resistance (mOhm)", multiplier=100
    )
    NightThresholdVoltage = Register(
        0x901E,
        description="Voltage at which the controller switches to nighttime mode",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    NightThresholdDelay = Register(
        0x901F,
        description="Delay after voltage drops below nighttime threshold before changing to night mode",
        unit=RegisterUnit.MINUTE,
    )
    DayThresholdVoltage = Register(
        0x9020,
        description="Voltage at which the controller switches to daytime mode",
        unit=RegisterUnit.VOLT,
        multiplier=100,
    )
    DayThresholdDelay = Register(
        0x9021,
        description="Delay after voltage goes above threshold before changing to day mode",
        unit=RegisterUnit.MINUTE,
    )

    class LoadControlModeEnum(Enum):
        MANUAL = 0
        ON_OFF = 1
        ON_TIMER = 2
        TIME = 3

    LoadControlMode = Register(0x903D, description="Load control mode")

    LoadTimer1 = Register(0x903E, description="Load output timer 1 duration (0xHHMM)")
    LoadTimer2 = Register(0x903F, description="Load output timer 2 duration (0xHHMM)")
    LoadTimer1OnSecond = Register(
        0x9042, description="Timer 1 turn on time (xx:xx:SS)", unit=RegisterUnit.SECOND
    )
    LoadTimer1OnMinute = Register(
        0x9043, description="Timer 1 turn on time (xx:MM:xx)", unit=RegisterUnit.MINUTE
    )
    LoadTimer1OnHour = Register(
        0x9044, description="Timer 1 turn on time (HH:xx:xx)", unit=RegisterUnit.HOUR
    )
    LoadTimer1OffSecond = Register(
        0x9045, description="Timer 1 turn off time (xx:xx:SS)", unit=RegisterUnit.SECOND
    )
    LoadTimer1OffMinute = Register(
        0x9046, description="Timer 1 turn off time (xx:MM:xx)", unit=RegisterUnit.MINUTE
    )
    LoadTimer1OffHour = Register(
        0x9047, description="Timer 1 turn off time (HH:xx:xx)", unit=RegisterUnit.HOUR
    )
    LoadTimer2OnSecond = Register(
        0x9048, description="Timer 2 turn on time (xx:xx:SS)", unit=RegisterUnit.SECOND
    )
    LoadTimer2OnMinute = Register(
        0x9049, description="Timer 2 turn on time (xx:MM:xx)", unit=RegisterUnit.MINUTE
    )
    LoadTimer2OnHour = Register(
        0x904A, description="Timer 2 turn on time (HH:xx:xx)", unit=RegisterUnit.HOUR
    )
    LoadTimer2OffSecond = Register(
        0x904B, description="Timer 2 turn off time (xx:xx:SS)", unit=RegisterUnit.SECOND
    )
    LoadTimer2OffMinute = Register(
        0x904C, description="Timer 2 turn off time (xx:MM:xx)", unit=RegisterUnit.MINUTE
    )
    LoadTimer2OffHour = Register(
        0x904D, description="Timer 2 turn off time (HH:xx:xx)", unit=RegisterUnit.HOUR
    )

    LengthOfNight = Register(0x9065, description="Default length of nighttime (0xHHMM")

    class BatteryVoltageCodeEnum(Enum):
        AUTO = 0
        NOMINAL_12V = 1
        NOMINAL_24V = 2
        NOMINAL_36V = 3
        NOMINAL_48V = 4

    BatteryVoltageCode = Register(
        0x9067, description="Battery system voltage selection"
    )

    class LoadTimerSelectionEnum(Enum):
        SINGLE_TIMER = 0
        DUAL_TIMER = 1

    LoadTimerSelection = Register(0x9069, description="Load timer selection")
    LoadDefaultState = Register(
        0x906A, description="Default load state in manual mode 0: off, 1: on"
    )
    EqualizeDuration = Register(
        0x906B, description="Equalize duration", unit=RegisterUnit.MINUTE
    )
    BoostDuration = Register(
        0x906C, description="Boost duration", unit=RegisterUnit.MINUTE
    )
    DischargingPercentage = Register(
        0x906D,
        description="Remaining battery capacity when the load is disconnected?",
        unit=RegisterUnit.PERCENT,
    )
    ChargingPercentage = Register(
        0x906E,
        description="Battery capacity when charging is terminated",
        unit=RegisterUnit.PERCENT,
    )

    class BatteryManagementModeEnum(Enum):
        VOLTAGE_COMPENSATION = 0
        STATE_OF_CHARGE = 1

    BatteryManagementMode = Register(
        0x9070, description="Management of battery charge/discharge"
    )


class ControlCoil:
    LoadControl = Coil(
        0x2, description="Load control when in manual mode 0: off, 1: on"
    )

    LoadTestMode = Coil(0x5, description="Load test control 0: off, 1: on")

    ForceLoadControl = Coil(0x6, description="Force load control 0: off, 1: on")

    OverTemperature = Register(
        0x2000, description="Over-temperature indication 0: normal, 1: over temperature"
    )

    class DayNightEnum(Enum):
        DAY = 0
        NIGHT = 1

    DayNight = Register(0x200C, description="Day/night indicator")
