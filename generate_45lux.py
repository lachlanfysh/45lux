#!/usr/bin/env python3
"""45lux: 4x5 large format camera light meter.

16x OPT3004 ambient light sensors in a 4x4 grid at the film plane,
ESP32-C6 with BLE, SSD1327 128x128 grayscale OLED, LIS2DH IMU,
3xAAA battery with AP2112K-3.3 LDO. Tag-Connect for flashing.
"""

import os
os.environ["KICAD9_SYMBOL_DIR"] = "/usr/share/kicad/symbols"

from skidl import *
set_default_tool(KICAD9)

# Footprint constants
FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C_BULK = "Capacitor_SMD:C_0805_2012Metric"
FP_ESP32 = "RF_Module:ESP32-C6-MINI-1"
# OPT3004 USON 2x2mm — swap to SnapEDA footprint for production
FP_OPT = "Package_DFN_QFN:DFN-6-1EP_2x2mm_P0.65mm_EP1x1.6mm"
FP_MUX = "Package_SO:TSSOP-16_4.4x5mm_P0.65mm"
FP_IMU = "Package_LGA:Bosch_LGA-14_3x2.5mm_P0.5mm"
FP_LDO = "Package_TO_SOT_SMD:SOT-23-5"
FP_SW = "Button_Switch_THT:SW_TH_Tactile_Omron_B3F-106x"
FP_BAT = "Battery:BatteryHolder_Keystone_2479_3xAAA"
FP_OLED = "Connector_FFC-FPC:Molex_200528-0040_1x04-1MP_P1.00mm_Horizontal"
FP_TAG = "Connector:Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical"
FP_SPECTRAL = "Package_LGA:AMS_OLGA-8_2x3.1mm_P0.8mm"


# ── 3.3V LDO + Battery Connector ───────────────────────────────────────────

@subcircuit
def power_supply(vbat, vcc, gnd):
    bat = Part("Device", "Battery_Cell", value="3xAAA", footprint=FP_BAT)
    bat[1] += vbat   # +
    bat[2] += gnd    # -

    c_bat = Part("Device", "C", value="10uF", footprint=FP_C_BULK)
    c_bat[1] += vbat
    c_bat[2] += gnd

    ldo = Part("Regulator_Linear", "AP2112K-3.3", footprint=FP_LDO)
    ldo[1] += vbat   # VIN
    ldo[2] += gnd    # GND
    ldo[3] += vbat   # EN (tied to VIN = always on)
    ldo[5] += vcc    # VOUT

    c_in = Part("Device", "C", value="100nF", footprint=FP_C)
    c_in[1] += vbat
    c_in[2] += gnd
    c_out = Part("Device", "C", value="100nF", footprint=FP_C)
    c_out[1] += vcc
    c_out[2] += gnd

    return bat


# ── ESP32-C6 MCU ────────────────────────────────────────────────────────────

@subcircuit
def mcu_esp32c6(vcc, gnd, sda, scl, btn_up, btn_down, uart_tx, uart_rx,
                en_net, boot_net):
    esp = Part("RF_Module", "ESP32-C6-MINI-1", footprint=FP_ESP32)
    esp[3] += vcc      # 3V3
    esp[1] += gnd      # GND
    esp[2] += gnd
    esp[11] += gnd
    esp[14] += gnd
    for p in range(36, 54):
        esp[p] += gnd

    # EN with pull-up and filter cap
    esp[8] += en_net
    r_en = Part("Device", "R", value="10K", footprint=FP_R)
    r_en[1] += vcc
    r_en[2] += en_net
    c_en = Part("Device", "C", value="100nF", footprint=FP_C)
    c_en[1] += en_net
    c_en[2] += gnd

    # I2C on IO6/IO7
    esp[15] += sda     # IO6
    esp[16] += scl     # IO7

    # Buttons on IO4/IO5
    esp[9] += btn_up   # IO4
    esp[10] += btn_down # IO5

    # UART for Tag-Connect flashing
    esp[31] += uart_tx  # TXD0
    esp[30] += uart_rx  # RXD0

    # Boot pin with pull-up (high = normal boot, low = download)
    esp[23] += boot_net # IO9
    r_boot = Part("Device", "R", value="10K", footprint=FP_R)
    r_boot[1] += vcc
    r_boot[2] += boot_net

    # Decoupling
    for _ in range(2):
        c = Part("Device", "C", value="100nF", footprint=FP_C)
        c[1] += vcc
        c[2] += gnd
    c_bulk = Part("Device", "C", value="10uF", footprint=FP_C_BULK)
    c_bulk[1] += vcc
    c_bulk[2] += gnd

    # NC pins
    unused = [4, 5, 6, 7, 12, 13, 17, 18, 19, 20, 21, 22, 24, 25, 26,
              27, 28, 29, 32, 33, 34, 35]
    for p in unused:
        esp[p] += Net(f"ESP_P{p}_NC")


# ── Sensor Array: 1x TCA9546A + 16x OPT3004 ──────────────────────────────

@subcircuit
def sensor_array(vcc, gnd, sda, scl):
    """4-channel mux, 4 OPT3004 per channel (4 I2C addresses each)."""

    sensor_refs = []
    cap_refs = []

    mux = Part("Interface_Expansion", "TCA9546APW", footprint=FP_MUX)
    mux[16] += vcc     # VCC
    mux[8] += gnd      # GND
    mux[14] += scl     # SCL upstream
    mux[15] += sda     # SDA upstream
    mux[1] += gnd      # A0 low
    mux[2] += gnd      # A1 low  → address 0x70
    mux[13] += gnd     # A2 low

    r_rst = Part("Device", "R", value="10K", footprint=FP_R)
    r_rst[1] += vcc
    r_rst[2] += mux[3] # ~RESET pull-up

    c_mux = Part("Device", "C", value="100nF", footprint=FP_C)
    c_mux[1] += vcc
    c_mux[2] += gnd

    # TCA9546A channel pins
    sd_pins = [4, 6, 9, 11]   # SD0-SD3
    sc_pins = [5, 7, 10, 12]  # SC0-SC3

    for ch in range(4):
        ch_sda = Net(f"MUX_CH{ch}_SDA")
        ch_scl = Net(f"MUX_CH{ch}_SCL")
        mux[sd_pins[ch]] += ch_sda
        mux[sc_pins[ch]] += ch_scl

        # 4 OPT3004 per channel: ADDR pin sets address
        # GND=0x44, VDD=0x45, SDA=0x46, SCL=0x47
        addr_nets = [gnd, vcc, ch_sda, ch_scl]

        for addr_idx in range(4):
            # TSL25911FN as placeholder symbol (6-pin, same count)
            # Pin mapping follows OPT3004 datasheet, NOT TSL labels
            sensor = Part("Sensor_Optical", "TSL25911FN", footprint=FP_OPT,
                          value=f"OPT3004")
            sensor[1] += vcc                    # OPT pin 1: VDD
            sensor[2] += addr_nets[addr_idx]    # OPT pin 2: ADDR
            sensor[3] += gnd                    # OPT pin 3: GND
            sensor[4] += ch_scl                 # OPT pin 4: SCL
            sensor[5] += Net(f"OPT_CH{ch}_{addr_idx}_INT")  # OPT pin 5: INT
            sensor[6] += ch_sda                 # OPT pin 6: SDA

            sensor_refs.append(sensor)

            c_s = Part("Device", "C", value="100nF", footprint=FP_C)
            c_s[1] += vcc
            c_s[2] += gnd
            cap_refs.append(c_s)

    return sensor_refs, cap_refs


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


# ── Color Temperature: AS7341 11-channel spectral sensor ───────────────────

@subcircuit
def color_temp_sensor(vcc, gnd, sda, scl):
    """AS7341 at fixed address 0x39, center of film plane."""
    spec = Part("Sensor_Optical", "AS7341DLG", footprint=FP_SPECTRAL)
    spec[1] += vcc    # VDD
    spec[2] += scl    # SCL
    spec[3] += gnd    # GND
    spec[4] += Net("AS7341_LDR_NC")  # LDR (unused LED driver)
    spec[5] += gnd    # PGND
    spec[6] += Net("AS7341_GPIO_NC")  # GPIO
    spec[7] += Net("AS7341_INT_NC")   # INT
    spec[8] += sda    # SDA

    c_spec = Part("Device", "C", value="100nF", footprint=FP_C)
    c_spec[1] += vcc
    c_spec[2] += gnd

    return spec


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
    switches = []
    for btn_net in [btn_up, btn_down]:
        sw = Part("Switch", "SW_Push", footprint=FP_SW)
        sw[1] += btn_net
        sw[2] += gnd
        switches.append(sw)

        r = Part("Device", "R", value="10K", footprint=FP_R)
        r[1] += vcc
        r[2] += btn_net

    return switches


# ── Debug: Tag-Connect TC2030-FP ────────────────────────────────────────────

@subcircuit
def debug_connector(vcc, gnd, uart_tx, uart_rx, en_net, boot_net):
    tag = Part("Connector_Generic", "Conn_02x03_Odd_Even", footprint=FP_TAG)
    # Standard ESP32 UART flash header layout
    tag[1] += vcc       # VCC
    tag[2] += uart_tx   # TXD
    tag[3] += uart_rx   # RXD
    tag[4] += gnd       # GND
    tag[5] += en_net    # EN/RESET
    tag[6] += boot_net  # BOOT (IO9)


# ═══════════════════════════════════════════════════════════════════════════
# Top level
# ═══════════════════════════════════════════════════════════════════════════

vbat = Net("VBAT")
vcc = Net("VCC"); vcc.drive = POWER
gnd = Net("GND"); gnd.drive = POWER

sda = Net("I2C_SDA")
scl = Net("I2C_SCL")
btn_up = Net("BTN_UP")
btn_down = Net("BTN_DOWN")
uart_tx = Net("UART_TX")
uart_rx = Net("UART_RX")
en_net = Net("ESP_EN")
boot_net = Net("ESP_BOOT")

# I2C bus pull-ups
for net in [sda, scl]:
    r = Part("Device", "R", value="4.7K", footprint=FP_R)
    r[1] += vcc
    r[2] += net

bat_holder = power_supply(vbat, vcc, gnd)
mcu_esp32c6(vcc, gnd, sda, scl, btn_up, btn_down, uart_tx, uart_rx,
            en_net, boot_net)
sensors, sensor_caps = sensor_array(vcc, gnd, sda, scl)
imu_accel(vcc, gnd, sda, scl)
spectral = color_temp_sensor(vcc, gnd, sda, scl)
oled_connector(vcc, gnd, sda, scl)
sw_up, sw_down = user_interface(vcc, gnd, btn_up, btn_down)
debug_connector(vcc, gnd, uart_tx, uart_rx, en_net, boot_net)


# ── Generate Schematic ──────────────────────────────────────────────────────

generate_schematic(
    auto_stub=True,
    auto_stub_fanout=3,
    erc_max_iterations=8,
)


# ── Generate PCB Layout ────────────────────────────────────────────────────

from skidl.layout import (
    extract_groups, place_parts, write_kicad_pcb, validate,
    LayoutConstraints, BoardOutline, FixedPosition, KeepOut, derive_outline,
    load_footprint_bboxes,
)

# Board: 120mm wide, 185mm tall (45mm below film area for electronics)
outline = BoardOutline(120.0, 185.0)

# Fix 16 sensors in uniform 4x4 grid inside film window
# Film area ~95x120mm on board, 10mm inset from film edge
grid_x = [22.5, 47.5, 72.5, 97.5]
grid_y = [30.0, 63.3, 96.7, 130.0]
sensor_fixed = []
for i, sensor_part in enumerate(sensors):
    row, col = divmod(i, 4)
    sensor_fixed.append(FixedPosition(sensor_part.ref, grid_x[col], grid_y[row], 0.0))
    # Bottom row caps need explicit fixing — placer pushes them to electronics
    # zone because they're close enough to the keepout boundary for the spiral
    # search to succeed (rows 0-2 caps stay near sensors via fallback)
    if row == 3:
        sensor_fixed.append(FixedPosition(sensor_caps[i].ref, grid_x[col], grid_y[row] + 3.0, 0.0))

# AS7341 spectral sensor at center of film area
sensor_fixed.append(FixedPosition(spectral.ref, 60.0, 80.0, 0.0))

# Battery holder across the bottom of the board
sensor_fixed.append(FixedPosition(bat_holder.ref, 60.0, 170.0, 0.0))

# Switches flanking the electronics cluster
sensor_fixed.append(FixedPosition(sw_up.ref, 20.0, 155.0, 0.0))
sensor_fixed.append(FixedPosition(sw_down.ref, 100.0, 155.0, 0.0))

# Keepout: everything above the electronics zone (sensors only)
# Electronics zone is below the film area: y=140 to y=185
top_keepout = KeepOut(x_min=0.0, y_min=0.0, x_max=120.0, y_max=140.0)

constraints = LayoutConstraints(
    fixed=sensor_fixed,
    keepouts=[top_keepout],
    outline=outline,
)

ckt = default_circuit
fp_names = set()
for p in ckt.parts:
    fp = getattr(p, "footprint", None)
    if fp:
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
