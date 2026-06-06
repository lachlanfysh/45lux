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

# Footprint constants
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C_BULK = "Capacitor_SMD:C_0805_2012Metric"
FP_LED = "LED_SMD:LED_0805_2012Metric"
FP_ESP32 = "RF_Module:ESP32-S3-WROOM-1"
FP_TSL = "OptoDevice:AMS_TSL25911FN"
FP_MUX = "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm"
FP_IMU = "Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm"
FP_CHRG = "Package_TO_SOT_SMD:SOT-23-5"
FP_LDO = "Package_TO_SOT_SMD:SOT-23-5"
FP_TVS = "Package_TO_SOT_SMD:SOT-23-6"
FP_USB = "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal"
FP_SW = "Button_Switch_THT:SW_TH_Tactile_Omron_B3F-106x"
FP_JST = "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical"
FP_OLED = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"


# ── USB-C + MCP73831 LiPo Charger ──────────────────────────────────────────

@subcircuit
def usb_charger(vbus, vbat, gnd, usb_dp, usb_dm):
    usb = Part("Connector", "USB_C_Receptacle_USB2.0_16P", footprint=FP_USB)
    for p in ["A1", "A12", "B1", "B12"]:
        usb[p] += gnd
    for p in ["A4", "A9", "B4", "B9"]:
        usb[p] += vbus
    usb["S1"] += gnd

    for cc_pin in ["A5", "B5"]:
        cc = Net()
        usb[cc_pin] += cc
        r = Part("Device", "R", value="5.1K", footprint=FP_R)
        r[1] += cc
        r[2] += gnd

    usb["A6"] += usb_dp
    usb["B6"] += usb_dp
    usb["A7"] += usb_dm
    usb["B7"] += usb_dm
    usb["A8"] += Net("SBU1_NC")
    usb["B8"] += Net("SBU2_NC")

    tvs = Part("Power_Protection", "USBLC6-2SC6", footprint=FP_TVS)
    tvs[1] += usb_dp
    tvs[6] += usb_dp
    tvs[3] += usb_dm
    tvs[4] += usb_dm
    tvs[5] += vbus
    tvs[2] += gnd

    c_in = Part("Device", "C", value="4.7uF", footprint=FP_C_BULK)
    c_in[1] += vbus
    c_in[2] += gnd

    chrg = Part("Battery_Management", "MCP73831-2-OT", footprint=FP_CHRG)
    chrg[4] += vbus
    chrg[2] += gnd
    chrg[3] += vbat

    r_prog = Part("Device", "R", value="2K", footprint=FP_R)
    r_prog[1] += chrg[5]
    r_prog[2] += gnd

    stat = Net("CHG_STAT")
    chrg[1] += stat
    r_led = Part("Device", "R", value="1K", footprint=FP_R)
    led = Part("Device", "LED", footprint=FP_LED)
    r_led[1] += vbus
    r_led[2] += led[1]
    led[2] += stat


# ── 3.3V LDO + Battery Connector ───────────────────────────────────────────

@subcircuit
def power_supply(vbat, vcc, gnd):
    bat = Part("Connector", "Conn_01x02_Pin", footprint=FP_JST)
    bat[1] += vbat
    bat[2] += gnd

    c_bat = Part("Device", "C", value="10uF", footprint=FP_C_BULK)
    c_bat[1] += vbat
    c_bat[2] += gnd

    ldo = Part("Regulator_Linear", "AP2112K-3.3", footprint=FP_LDO)
    ldo[1] += vbat
    ldo[2] += gnd
    ldo[3] += vbat
    ldo[5] += vcc

    c_in = Part("Device", "C", value="100nF", footprint=FP_C)
    c_in[1] += vbat
    c_in[2] += gnd
    c_out = Part("Device", "C", value="100nF", footprint=FP_C)
    c_out[1] += vcc
    c_out[2] += gnd


# ── ESP32-S3 MCU ────────────────────────────────────────────────────────────

@subcircuit
def mcu_esp32s3(vcc, gnd, usb_dp, usb_dm, sda, scl, btn_up, btn_down):
    esp = Part("RF_Module", "ESP32-S3-WROOM-1", footprint=FP_ESP32)
    esp[2] += vcc
    esp[1] += gnd
    esp[40] += gnd
    esp[41] += gnd

    r_en = Part("Device", "R", value="10K", footprint=FP_R)
    r_en[1] += vcc
    r_en[2] += esp[3]
    c_en = Part("Device", "C", value="100nF", footprint=FP_C)
    c_en[1] += esp[3]
    c_en[2] += gnd

    esp[14] += usb_dp
    esp[13] += usb_dm
    esp[4] += sda
    esp[5] += scl
    esp[6] += btn_up
    esp[7] += btn_down

    r_boot = Part("Device", "R", value="10K", footprint=FP_R)
    r_boot[1] += vcc
    r_boot[2] += esp[27]

    for _ in range(2):
        c = Part("Device", "C", value="100nF", footprint=FP_C)
        c[1] += vcc
        c[2] += gnd
    c_bulk = Part("Device", "C", value="10uF", footprint=FP_C_BULK)
    c_bulk[1] += vcc
    c_bulk[2] += gnd

    unused_pins = [
        8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21, 22,
        23, 24, 25, 26, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    ]
    for p in unused_pins:
        esp[p] += Net(f"ESP_P{p}_NC")


# ── Sensor Array: 2x TCA9548A + 16x TSL25911FN ─────────────────────────────

@subcircuit
def sensor_array(vcc, gnd, sda, scl):
    """Both I2C muxes and all 16 HDR lux sensors in one group."""

    sensor_refs = []

    for bank in range(2):
        mux = Part("Interface_Expansion", "TCA9548APWR", footprint=FP_MUX)
        mux[24] += vcc
        mux[12] += gnd
        mux[22] += scl
        mux[23] += sda

        if bank == 0:
            mux[1] += gnd   # A0 low → 0x70
        else:
            mux[1] += vcc   # A0 high → 0x71
        mux[2] += gnd       # A1
        mux[21] += gnd      # A2

        r_rst = Part("Device", "R", value="10K", footprint=FP_R)
        r_rst[1] += vcc
        r_rst[2] += mux[3]

        c_mux = Part("Device", "C", value="100nF", footprint=FP_C)
        c_mux[1] += vcc
        c_mux[2] += gnd

        sd_pins = [4, 6, 8, 10, 13, 15, 17, 19]
        sc_pins = [5, 7, 9, 11, 14, 16, 18, 20]

        for ch in range(8):
            ch_sda = Net(f"MUX{bank}_CH{ch}_SDA")
            ch_scl = Net(f"MUX{bank}_CH{ch}_SCL")
            mux[sd_pins[ch]] += ch_sda
            mux[sc_pins[ch]] += ch_scl

            sensor = Part("Sensor_Optical", "TSL25911FN", footprint=FP_TSL)
            sensor[1] += ch_scl
            sensor[6] += ch_sda
            sensor[5] += vcc
            sensor[3] += gnd
            sensor[2] += Net(f"MUX{bank}_INT{ch}_NC")
            sensor[4] += Net(f"MUX{bank}_SNC{ch}")

            sensor_refs.append(sensor)

            c_s = Part("Device", "C", value="100nF", footprint=FP_C)
            c_s[1] += vcc
            c_s[2] += gnd

    return sensor_refs


# ── IMU: LIS2DH ────────────────────────────────────────────────────────────

@subcircuit
def imu_accel(vcc, gnd, sda, scl):
    imu = Part("Sensor_Motion", "LIS2DH", footprint=FP_IMU)
    imu[8] += vcc
    imu[7] += vcc
    for p in [9, 10, 11, 12, 13, 14]:
        imu[p] += gnd

    imu[1] += scl
    imu[2] += sda
    imu[4] += vcc   # ~CS high → I2C mode
    imu[3] += gnd   # SDO/SA0 low → address 0x18

    imu[5] += Net("IMU_INT2_NC")
    imu[6] += Net("IMU_INT1_NC")

    c_imu = Part("Device", "C", value="100nF", footprint=FP_C)
    c_imu[1] += vcc
    c_imu[2] += gnd


# ── OLED Display Connector ─────────────────────────────────────────────────

@subcircuit
def oled_connector(vcc, gnd, sda, scl):
    conn = Part("Connector", "Conn_01x04_Pin", footprint=FP_OLED)
    conn[1] += gnd
    conn[2] += vcc
    conn[3] += scl
    conn[4] += sda


# ── User Interface: Buttons ─────────────────────────────────────────────────

@subcircuit
def user_interface(vcc, gnd, btn_up, btn_down):
    for btn_net in [btn_up, btn_down]:
        sw = Part("Switch", "SW_Push", footprint=FP_SW)
        sw[1] += btn_net
        sw[2] += gnd

        r = Part("Device", "R", value="10K", footprint=FP_R)
        r[1] += vcc
        r[2] += btn_net


# ═══════════════════════════════════════════════════════════════════════════
# Top level
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

# I2C bus pull-ups
for net in [sda, scl]:
    r = Part("Device", "R", value="4.7K", footprint=FP_R)
    r[1] += vcc
    r[2] += net

usb_charger(vbus, vbat, gnd, usb_dp, usb_dm)
power_supply(vbat, vcc, gnd)
mcu_esp32s3(vcc, gnd, usb_dp, usb_dm, sda, scl, btn_up, btn_down)
sensors = sensor_array(vcc, gnd, sda, scl)
imu_accel(vcc, gnd, sda, scl)
oled_connector(vcc, gnd, sda, scl)
user_interface(vcc, gnd, btn_up, btn_down)


# ── Generate Schematic ──────────────────────────────────────────────────────

generate_schematic(
    auto_stub=True,
    auto_stub_fanout=3,
    erc_max_iterations=8,
)


# ── Generate PCB Layout ────────────────────────────────────────────────────

from skidl.layout import (
    extract_groups, place_parts, write_kicad_pcb, validate,
    LayoutConstraints, BoardOutline, FixedPosition, derive_outline,
    load_footprint_bboxes,
)

# Board outline: 4x5 film holder interior (~120mm x 160mm)
outline = BoardOutline(120.0, 160.0)

# Fix the 16 sensors in a center-weighted 4x4 grid inside the film window
# Film area ~95x120mm on 120x160mm board, 5mm inset from film edge
# Inner gaps 60% of outer gaps for center weighting
grid_x = [18.0, 50.0, 70.0, 102.0]   # center pair 20mm apart, outer 32mm
grid_y = [25.0, 67.0, 93.0, 135.0]   # center pair 26mm apart, outer 42mm
sensor_fixed = []
for i, sensor_part in enumerate(sensors):
    row, col = divmod(i, 4)
    sensor_fixed.append(FixedPosition(sensor_part.ref, grid_x[col], grid_y[row], 0.0))

constraints = LayoutConstraints(
    fixed=sensor_fixed,
    outline=outline,
)

# Collect footprint names and load bounding boxes
ckt = default_circuit
fp_names = set()
for p in ckt.parts:
    fp = getattr(p, "footprint", None)
    if fp:
        # SKiDL stores footprint as "Lib:Name" or just the value
        fp_str = str(fp)
        if ":" in fp_str:
            fp_names.add(fp_str)

fp_lib_dirs = ["/usr/share/kicad/footprints"]
fp_bboxes = load_footprint_bboxes(fp_names, fp_lib_dirs)

placed = place_parts(extract_groups(ckt), constraints, fp_bboxes)

result = validate(placed, ckt, fp_bboxes, outline=outline)
print(result.summary())

write_kicad_pcb(
    placed, ckt, fp_lib_dirs,
    output_path="45lux.kicad_pcb",
    outline=outline,
)

print(f"PCB written to 45lux.kicad_pcb")
