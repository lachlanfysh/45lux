#!/usr/bin/env python3
"""45lux: 4x5 large format camera light meter.

16x TSL2591 HDR lux sensors in a 4x4 grid at the film plane,
ESP32-S3 with BLE, SSD1327 128x128 grayscale OLED, LIS2DH IMU,
LiPo battery with USB-C MCP73831 charging.
"""

import os
os.environ["KICAD9_SYMBOL_DIR"] = "/usr/share/kicad/symbols"

from skidl import *
set_default_tool(KICAD9)


# ── USB-C + MCP73831 LiPo Charger ──────────────────────────────────────────

@subcircuit
def usb_charger(vbus, vbat, gnd, usb_dp, usb_dm):
    """USB-C with CC pull-downs, ESD protection, MCP73831 charger, status LED."""

    usb = Part("Connector", "USB_C_Receptacle_USB2.0_16P")
    for p in ["A1", "A12", "B1", "B12"]:
        usb[p] += gnd
    for p in ["A4", "A9", "B4", "B9"]:
        usb[p] += vbus
    usb["S1"] += gnd

    # CC pull-downs for UFP/sink role
    for cc_pin in ["A5", "B5"]:
        cc = Net()
        usb[cc_pin] += cc
        r = Part("Device", "R", value="5.1K")
        r[1] += cc
        r[2] += gnd

    # USB 2.0 data (tie A/B pairs)
    usb["A6"] += usb_dp
    usb["B6"] += usb_dp
    usb["A7"] += usb_dm
    usb["B7"] += usb_dm

    # SBU pins unused
    usb["A8"] += Net("SBU1_NC")
    usb["B8"] += Net("SBU2_NC")

    # ESD protection on USB data lines
    tvs = Part("Power_Protection", "USBLC6-2SC6")
    tvs[1] += usb_dp
    tvs[6] += usb_dp
    tvs[3] += usb_dm
    tvs[4] += usb_dm
    tvs[5] += vbus
    tvs[2] += gnd

    # Input decoupling
    c_in = Part("Device", "C", value="4.7uF")
    c_in[1] += vbus
    c_in[2] += gnd

    # MCP73831: 1=STAT, 2=VSS, 3=VBAT, 4=VDD, 5=PROG
    chrg = Part("Battery_Management", "MCP73831-2-OT")
    chrg[4] += vbus
    chrg[2] += gnd
    chrg[3] += vbat

    # Charge current: 2K → 500mA
    r_prog = Part("Device", "R", value="2K")
    r_prog[1] += chrg[5]
    r_prog[2] += gnd

    # Charge status LED (active-low STAT output)
    stat = Net("CHG_STAT")
    chrg[1] += stat
    r_led = Part("Device", "R", value="1K")
    led = Part("Device", "LED")
    r_led[1] += vbus
    r_led[2] += led[1]
    led[2] += stat


# ── 3.3V LDO + Battery Connector ───────────────────────────────────────────

@subcircuit
def power_supply(vbat, vcc, gnd):
    """AP2112K-3.3 LDO with JST-PH battery connector."""

    bat = Part("Connector", "Conn_01x02_Pin")
    bat[1] += vbat
    bat[2] += gnd

    c_bat = Part("Device", "C", value="10uF")
    c_bat[1] += vbat
    c_bat[2] += gnd

    # AP2112K: 1=VIN, 2=GND, 3=EN, 4=NC, 5=VOUT
    ldo = Part("Regulator_Linear", "AP2112K-3.3")
    ldo[1] += vbat
    ldo[2] += gnd
    ldo[3] += vbat  # EN tied high = always on
    ldo[5] += vcc

    c_in = Part("Device", "C", value="1uF")
    c_in[1] += vbat
    c_in[2] += gnd

    c_out = Part("Device", "C", value="1uF")
    c_out[1] += vcc
    c_out[2] += gnd


# ── ESP32-S3 MCU ────────────────────────────────────────────────────────────

@subcircuit
def mcu_esp32s3(vcc, gnd, usb_dp, usb_dm, sda, scl, btn_up, btn_down):
    """ESP32-S3-WROOM-1 with boot/reset circuit and decoupling."""

    esp = Part("RF_Module", "ESP32-S3-WROOM-1")
    esp[2] += vcc
    esp[1] += gnd
    esp[40] += gnd
    esp[41] += gnd

    # EN reset circuit
    r_en = Part("Device", "R", value="10K")
    r_en[1] += vcc
    r_en[2] += esp[3]
    c_en = Part("Device", "C", value="100nF")
    c_en[1] += esp[3]
    c_en[2] += gnd

    # Native USB (IO19=D-, IO20=D+)
    esp[14] += usb_dp
    esp[13] += usb_dm

    # I2C (IO4=SDA, IO5=SCL)
    esp[4] += sda
    esp[5] += scl

    # Buttons (IO6=UP, IO7=DOWN)
    esp[6] += btn_up
    esp[7] += btn_down

    # IO0 boot strapping pull-up
    r_boot = Part("Device", "R", value="10K")
    r_boot[1] += vcc
    r_boot[2] += esp[27]

    # Decoupling
    for _ in range(2):
        c = Part("Device", "C", value="100nF")
        c[1] += vcc
        c[2] += gnd
    c_bulk = Part("Device", "C", value="10uF")
    c_bulk[1] += vcc
    c_bulk[2] += gnd

    # Unused GPIO → NC nets
    unused_pins = [
        8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21, 22,
        23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    ]
    for p in unused_pins:
        esp[p] += Net(f"ESP_P{p}_NC")


# ── Sensor Bank: TCA9548A mux + 8x TSL25911FN ──────────────────────────────

@subcircuit
def sensor_bank(vcc, gnd, sda, scl, bank_id):
    """One I2C mux driving 8 HDR lux sensors. bank_id: 0→0x70, 1→0x71."""

    mux = Part("Interface_Expansion", "TCA9548APWR")
    mux[24] += vcc
    mux[12] += gnd
    mux[22] += scl
    mux[23] += sda

    # Address pins: bank 0 = all low (0x70), bank 1 = A0 high (0x71)
    if bank_id == 0:
        mux[1] += gnd   # A0
    else:
        mux[1] += vcc   # A0
    mux[2] += gnd       # A1
    mux[21] += gnd      # A2

    # ~RESET pull-up (active low, hold high for normal operation)
    r_rst = Part("Device", "R", value="10K")
    r_rst[1] += vcc
    r_rst[2] += mux[3]

    c_mux = Part("Device", "C", value="100nF")
    c_mux[1] += vcc
    c_mux[2] += gnd

    # Channel data/clock pin pairs on the TCA9548A
    sd_pins = [4, 6, 8, 10, 13, 15, 17, 19]
    sc_pins = [5, 7, 9, 11, 14, 16, 18, 20]

    for ch in range(8):
        ch_sda = Net(f"MUX{bank_id}_CH{ch}_SDA")
        ch_scl = Net(f"MUX{bank_id}_CH{ch}_SCL")
        mux[sd_pins[ch]] += ch_sda
        mux[sc_pins[ch]] += ch_scl

        # TSL25911FN: 1=SCL, 2=INT, 3=GND, 4=NC, 5=VDD, 6=SDA
        sensor = Part("Sensor_Optical", "TSL25911FN")
        sensor[1] += ch_scl
        sensor[6] += ch_sda
        sensor[5] += vcc
        sensor[3] += gnd
        sensor[2] += Net(f"MUX{bank_id}_INT{ch}_NC")
        sensor[4] += Net(f"MUX{bank_id}_SNC{ch}")

        c_s = Part("Device", "C", value="100nF")
        c_s[1] += vcc
        c_s[2] += gnd


# ── IMU: LIS2DH ────────────────────────────────────────────────────────────

@subcircuit
def imu_accel(vcc, gnd, sda, scl):
    """LIS2DH accelerometer for screen rotation and digital level."""

    imu = Part("Sensor_Motion", "LIS2DH")
    imu[8] += vcc       # Vdd
    imu[7] += vcc       # Vdd_IO
    for p in [9, 10, 11, 12, 13, 14]:
        imu[p] += gnd

    imu[1] += scl       # SCL
    imu[2] += sda       # SDA
    imu[4] += vcc       # ~CS high → I2C mode
    imu[3] += gnd       # SDO/SA0 low → address 0x18

    imu[5] += Net("IMU_INT2_NC")
    imu[6] += Net("IMU_INT1_NC")

    c_imu = Part("Device", "C", value="100nF")
    c_imu[1] += vcc
    c_imu[2] += gnd


# ── OLED Display Connector ─────────────────────────────────────────────────

@subcircuit
def oled_connector(vcc, gnd, sda, scl):
    """4-pin FPC connector for SSD1327 128x128 I2C OLED."""

    conn = Part("Connector", "Conn_01x04_Pin")
    conn[1] += gnd
    conn[2] += vcc
    conn[3] += scl
    conn[4] += sda


# ── User Interface: Buttons ─────────────────────────────────────────────────

@subcircuit
def user_interface(vcc, gnd, btn_up, btn_down):
    """Two THT tactile switches with pull-ups for aperture control."""

    for btn_net in [btn_up, btn_down]:
        sw = Part("Switch", "SW_Push")
        sw[1] += btn_net
        sw[2] += gnd

        r = Part("Device", "R", value="10K")
        r[1] += vcc
        r[2] += btn_net


# ═══════════════════════════════════════════════════════════════════════════
# Top level: define nets, wire subcircuits
# ═══════════════════════════════════════════════════════════════════════════

vbus = Net("VBUS")
vbat = Net("VBAT")
vcc = Net("VCC"); vcc.drive = POWER
gnd = Net("GND"); gnd.drive = POWER

usb_dp = Net("USB_DP")
usb_dm = Net("USB_DM")
sda = Net("I2C_SDA")
scl = Net("I2C_SCL")
btn_up = Net("BTN_UP")
btn_down = Net("BTN_DOWN")

# I2C bus pull-ups (one set on the main bus)
for net in [sda, scl]:
    r = Part("Device", "R", value="4.7K")
    r[1] += vcc
    r[2] += net

usb_charger(vbus, vbat, gnd, usb_dp, usb_dm)
power_supply(vbat, vcc, gnd)
mcu_esp32s3(vcc, gnd, usb_dp, usb_dm, sda, scl, btn_up, btn_down)
sensor_bank(vcc, gnd, sda, scl, 0)   # TCA9548A @ 0x70
sensor_bank(vcc, gnd, sda, scl, 1)   # TCA9548A @ 0x71
imu_accel(vcc, gnd, sda, scl)
oled_connector(vcc, gnd, sda, scl)
user_interface(vcc, gnd, btn_up, btn_down)

generate_schematic(
    auto_stub=True,
    auto_stub_fanout=3,
    erc_max_iterations=8,
)
