# Board Map — Firing Station Rev A (2026)

Sources: Altium schematic screenshots of U12, U13 and U14, plus Joss's answers in chat (2026-11-25).
Items marked ❓ are still open; stop and ask before writing code that depends on them.
Before any pin constant is used on hardware, Joss re-verifies this file against the released
schematic PDF in `docs/hardware/`.

**Module (both ESPs): ESP32-S3-WROOM-1U-N8.** 8 MB quad flash, **no PSRAM**, so GPIO35–37 are free.
(On -N8R8 and other octal-PSRAM variants they would not be.) `sdkconfig` still says 4 MB flash; that's
fine on an 8 MB part, so leave it.

Console on both ESPs is USB-Serial-JTAG (`CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` and
`ARDUINO_USB_CDC_ON_BOOT=1`), so Arduino `Serial` is USB. All three hardware UARTs are free for links.

## Node roles

| Node | Ref | Devices hosted | MAC |
|---|---|---|---|
| `FsPower` | U13 | DevFsRelays, DevFsPiPacketBroadcaster, DevFsPowerHealth (new) | ❓ boards not built; read from boot log later |
| `FsAnalog` | U12 | DevFsLoxGn2Transducers (all 16 PTs), DevEregControl, DevFsThermocouples, DevFsAnalogHealth (new) | ❓ later |
| `CapFill` | new cap-fill board (deferred) | DevCapFill | ❓ later. New hardware, so last year's `10:51:db:46:02:b8` no longer applies |

## UART topology

```
 Raspberry Pi 5 ──2 Mbaud── [FsPower] ──2 Mbaud── [FsAnalog] ──RS-422 921600── [CapFill]   (uart1)
 (uart0, GPIO14/15)                    on-board              ──RS-422 921600── [aux board] (uart2, reserved)
```

| Node | Port | ESP UART | RX GPIO | TX GPIO | Peer | Baud | Physical |
|---|---|---|---|---|---|---|---|
| FsPower | `PI` | 2 | IO15 (`uart-f-rpi`) | IO7 (`uart-t-rpi`) | Pi 5 uart0 (GPIO14/15, `/dev/ttyAMA0`) | 2 000 000 | on-board, 33 Ω series |
| FsPower | `ANALOG` | 1 | IO16 (`uart-f-anlg-esp`) | IO17 (`uart-t-anlg-esp`) | FsAnalog | 2 000 000 | on-board, 33 Ω series |
| FsAnalog | `POWER` | 0 | IO44/RXD0 (`uart-to-anlg-esp`) | IO43/TXD0 (`uart-from-anlg-esp`) | FsPower | 2 000 000 | on-board |
| FsAnalog | `CAPFILL` | 1 | IO16 (`uart1-f-esp`) | IO17 (`uart1-t-esp`) | CapFill | 921 600 | MAX3490EESA+ RS-422, 33 Ω series |
| FsAnalog | `AUX` | 2 | IO18 (`uart2-f-esp`) | IO8 (`uart2-t-esp`) | reserved, no node yet | 921 600 | ❓ also through a MAX3490? |

- Baud rates are per-port constants in the node table, so changing one is a one-line edit.
- The MAX3490 is a 10 Mbps full-duplex RS-422 part (from memory; check its datasheet). 921 600 baud over ~20 ft of cable leaves a large margin, and the cap-fill traffic is tiny. The off-board baud can go up later if needed.
- The analog ESP's UART0 TX (IO43) carries the **ROM bootloader log** at every reset, before any of our code runs. The power ESP's `ANALOG` port will see a burst of garbage each time FsAnalog resets. The link framing drops it and counts it as framing errors; that's expected and not a fault.
- Pi 5: the GPIO14/15 UART is `uart0` → `/dev/ttyAMA0`, enabled with `dtparam=uart0` in `config.txt`. The Pi 5 has no mini UART. The Pi 5's UART clock isn't confirmed, so the 2 Mbaud link must pass the loopback test in Phase 0 (test A0).

## FsPower — U13

| GPIO | Mod. pin | Net | Use |
|---|---|---|---|
| IO0 | 27 | ESP2_GPIO0 | boot strap; do not use |
| IO1 | 39 | ina237-scl | I²C SCL → INA237 |
| IO2 | 38 | ina237-sda | I²C SDA → INA237 (A0 = A1 = GND → address 0x40; confirm against the INA237 address table) |
| IO3 | 15 | io3-2-pu | strap, 10k pull-up; do not use |
| IO4 | 4 | valve-cont | ADC1_CH3 ← mux U14 COMMON (100 nF C97 to GND) |
| IO5, IO6 | 5, 6 | — | NC |
| IO7 | 7 | uart-t-rpi | UART TX → Pi |
| IO8 | 12 | ereg-pgood2 | input (TPS259827 PG) |
| IO9 | 17 | valve-en12 | output → VALVE_12 gate-driver EN |
| IO10 | 18 | valve-en11 | output → VALVE_11 |
| IO11 | 19 | valve-en10 | output → VALVE_10 |
| IO12 | 20 | valve-en9 | output → VALVE_9 |
| IO13 | 21 | valve-en8 | output → VALVE_8 |
| IO14 | 22 | valve-en3 | output → VALVE_3 |
| IO15 | 8 | uart-f-rpi | UART RX ← Pi |
| IO16 | 9 | uart-f-anlg-esp | UART RX ← FsAnalog |
| IO17 | 10 | uart-t-anlg-esp | UART TX → FsAnalog |
| IO18 | 11 | ereg-pgood1 | input (TPS259827 PG) |
| IO19, IO20 | 13, 14 | USB2_N/P | USB |
| IO21 | 23 | valve-en4 | output → VALVE_4 |
| IO35 | 28 | valve-en7 | output → VALVE_7 |
| IO36 | 29 | valve-en2 | output → VALVE_2 |
| IO37 | 30 | valve-en1 | output → VALVE_1 |
| IO38 | 31 | ereg-pwr-en2 | output → TPS259827 EN, eReg 2 high-side switch |
| IO39 | 32 | ereg-pwr-en1 | output → TPS259827 EN, eReg 1 high-side switch |
| IO40 | 33 | cont-mux-S3 | output |
| IO41 | 34 | cont-mux-S2 | output |
| IO42 | 35 | cont-mux-S1 | output |
| IO44 (RXD0) | 36 | cont-mux-S0 | output (UART0 RX pin reused as GPIO) |
| IO43 (TXD0) | 37 | — | NC |
| IO45, IO46 | 26, 16 | — | NC (straps) |
| IO47 | 24 | valve-en5 | output → VALVE_5 |
| IO48 | 25 | valve-en6 | output → VALVE_6 |

- **Valve enables:** every `valve-enN` drives its gate driver's EN pin, which has a pull-down. HIGH = driver enabled.
- **eReg power enables:** `ereg-pwr-enN` drives the TPS259827 EN pin; that eFuse is used as the high-side switch. ❓ Is there a pull-down on EN? Confirm from the schematic and check the EN polarity in the TPS259827 datasheet.
- ❓ Do `ereg-pgood1/2` have pull-ups, given the TPS259827 PG output is open-drain? IO18 is ADC2_CH7 and IO8 is ADC1_CH7. Both are usable as digital inputs; ADC2 is also usable because Wi-Fi is never started.

### Valve channels

All 12 channels are named `VALVE_1` … `VALVE_12` in `fs_board_config.h`. Joss will add comments saying
what each one drives; the function mapping is parked for the state-machine work.

| Channel | GPIO | Function (Joss to comment later) |
|---|---|---|
| VALVE_1 | IO37 | |
| VALVE_2 | IO36 | |
| VALVE_3 | IO14 | |
| VALVE_4 | IO21 | |
| VALVE_5 | IO47 | |
| VALVE_6 | IO48 | |
| VALVE_7 | IO35 | |
| VALVE_8 | IO13 | |
| VALVE_9 | IO12 | |
| VALVE_10 | IO11 | |
| VALVE_11 | IO10 | |
| VALVE_12 | IO9 | |

**Provisional function map** (used until Joss assigns it in the state-machine chat): DevFsRelays'
`RelayPin` values are set in order to VALVE_1…VALVE_9 = GN2_DRAIN, GN2_FILL, DEPRESS, PRESS_PILOT, RUN,
LOX_FILL, LOX_DISCONNECT, IGNITER, IGNITER_BACKUP. VALVE_10–12 are held LOW. This map exists **only**
so the firmware builds and can be bench-tested with dummy loads. It is guarded by `FS_PROVISIONAL_MAP`;
see plan Section 3.10.

## Continuity mux — U14 (CD74HC4067SM96), on FsPower

VCC = 3V3; E_N tied to GND. COMMON → `valve-cont` (IO4) with 100 nF to GND.
Select lines: S0 = IO44, S1 = IO42, S2 = IO41, S3 = IO40.

| Mux ch | Net | Source circuit |
|---|---|---|
| I0 | valve-cont3 | VALVE_3 continuity |
| I1 | valve-cont4 | VALVE_4 |
| I2 | valve-cont5 | VALVE_5 |
| I3 | valve-cont8 | VALVE_8 |
| I4 | valve-cont9 | VALVE_9 |
| I5 | valve-cont10 | VALVE_10 |
| I6 | valve-cont11 | VALVE_11 |
| I7 | valve-cont12 | VALVE_12 |
| I8 | valve-cont6 | VALVE_6 |
| I9 | valve-cont7 | VALVE_7 |
| I10 | valve-cont1 | VALVE_1 |
| I11 | valve-cont2 | VALVE_2 |
| I12 | ereg-imon-mux1 | eReg 1 IMON |
| I13 | ereg-imon-mux2 | eReg 2 IMON |
| I14, I15 | — | NC |

The mux order is **not** sequential, so firmware uses this table.

**Continuity divider.** 100 kΩ over 10 kΩ, fed from the 12 V battery through the load.
- Load connected, channel off: V = V_bat × 10/110. That's 1.09 V at 12.0 V, ranging 0.91–1.33 V over 10.0–14.6 V.
- Open load: ≈ 0 V (pulled to ground through the 10 kΩ).
- Report raw mV, plus a `cont_ok` bit = V_cont > 0.5 × (V_bus × 10/110), using V_bus from the INA237.
- ❓ If the divider taps the low-side switched node, continuity reads ≈ 0 V whenever the channel is **on**, so it's only meaningful while the channel is commanded off. The health packet sends `valve_en_readback` alongside it so the Pi can tell. Confirm the tap point.
- The divider passes 12 V / 110 kΩ = **109 µA** (133 µA at 14.6 V) continuously through each load, igniters included. That's about three orders of magnitude below typical igniter no-fire currents, but confirm against the igniter's datasheet no-fire spec.

**eReg IMON.** TPS259827 R_IMON = 665 Ω, then a 10 kΩ / 22 nF RC filter into the mux (f_c = 1/(2π·10.67 kΩ·22 nF) ≈ 680 Hz).
- I_load = V_IMON / (R_IMON × G_IMON), with G_IMON taken from the TPS259827 datasheet. Do not assume it.

**Settling, per channel, when the mux switches onto it** (to within 1 LSB at 12 bit, i.e. 8.3 τ):
- Continuity: R_src = 100k ∥ 10k = 9.09 kΩ, C = 100 nF → τ = 0.91 ms → **wait 8 ms**.
- IMON: R = 10.67 kΩ, C = 100 nF + 22 nF → τ = 1.30 ms → **wait 11 ms**.
- Full 14-channel scan: 12 × 8 + 2 × 11 = **118 ms**, about 8.5 Hz. Mux on-resistance is ignored here; check it on a scope.
- ❓ Bench check: when the mux switches onto an IMON channel, C97's previous charge is shared into the 22 nF IMON filter node. That injects up to ~0.9 V through the 10 kΩ into the IMON pin, which could disturb it if that pin also sets the current limit. Scope the TPS259827 IMON pin during a scan.

**Breakwire:** will reuse one of the valve channels; Joss decides later. No firmware change needed: it's just that channel's continuity reading.

## FsAnalog — U12

| GPIO | Mod. pin | Net | Use |
|---|---|---|---|
| IO0 | 27 | ESP1_GPIO0 | boot strap; do not use |
| IO1, IO2 | 39, 38 | — | NC |
| IO3 | 15 | io3-1-pu | strap, 10k pull-up; do not use |
| IO4 | 4 | tc-cjc-temp | ADC1_CH3 ← MCP9700 CJC sensor (next to the TC terminal block) |
| IO5 | 5 | 24V-pwr-pgood | ADC1_CH4: logic level **and** analog voltage |
| IO6 | 6 | 12V-pwr-pgood | ADC1_CH5: logic level and analog voltage |
| IO7 | 7 | 12V-digital-pgood | ADC1_CH6: logic level and analog voltage |
| IO8 | 12 | uart2-t-esp | UART2 TX → aux |
| IO9 | 17 | tc-miso | SPI MISO ← ADS124S08 |
| IO10 | 18 | tc-sclk | SPI SCLK |
| IO11 | 19 | tc-mosi | SPI MOSI |
| IO12 | 20 | tc-cs | SPI CS (ADS124S08). No DRDY/START/RESET pins are wired, so use SPI commands and polling |
| IO13–IO15 | 21, 22, 8 | — | NC |
| IO16 | 9 | uart1-f-esp | UART1 RX ← cap-fill (RS-422) |
| IO17 | 10 | uart1-t-esp | UART1 TX → cap-fill |
| IO18 | 11 | uart2-f-esp | UART2 RX ← aux |
| IO19, IO20 | 13, 14 | USB1_N/P | USB |
| IO21 | 23 | pt-sync | SYNC/RESET, shared by both ADS131M08 |
| IO35 | 28 | esp-clkout | CLKIN → both ADS131M08 (LEDC output) |
| IO36 | 29 | pt-mosi | SPI MOSI |
| IO37 | 30 | pt-miso | SPI MISO |
| IO38 | 31 | pt-sclk | SPI SCLK |
| IO39 | 32 | pt-drdy-bck | DRDY ← ADS131M08 "bck" (PT9–16) |
| IO40 | 33 | pt-cs-bck | CS → ADS131M08 "bck" |
| IO41 | 34 | ereg-pwm2 | eReg 2 servo PWM; not driven, eReg 2 unused |
| IO42 | 35 | ereg-pwm1 | eReg 1 servo PWM → `kServoPin` |
| IO43 (TXD0) | 37 | uart-from-anlg-esp | UART0 TX → FsPower (ROM log at reset, see above) |
| IO44 (RXD0) | 36 | uart-to-anlg-esp | UART0 RX ← FsPower |
| IO45, IO46 | 26, 16 | — | NC (straps) |
| IO47 | 24 | pt-cs-prim | CS → ADS131M08 "prim" (PT1–8) |
| IO48 | 25 | pt-drdy-prim | DRDY ← ADS131M08 "prim" |

**Rail PGOODs (IO5–7).** Joss wants each read both as a high/low state and as an analog voltage, to
estimate the actual bus voltage.
- ❓ For each net: is it a resistor divider off its rail (give the values), or a regulator's PG output pulled up to 3V3? A bus-voltage estimate is only possible with a divider.
- Firmware samples all four ADC1 pins (IO4–IO7) and derives the logic state **from the ADC samples**, using thresholds with hysteresis. Arduino-ESP32 3.x's peripheral manager assigns a pin to one function at a time, so the same pin can't be both a digital input with an interrupt and an ADC input. (That's my understanding of 3.x; verify it.)

**PT front end.** PT1–8 → "prim" AIN0–7; PT9–16 → "bck" AIN0–7 (PT1 = prim AIN0, …, PT8 = prim AIN7, PT9 = bck AIN0, …).
- Divider: 20 kΩ top over 4.99 kΩ bottom, ratio k = 4.99 / 24.99 = **0.19968**.
  - PT 0.5 V → 99.8 mV at the ADC; PT 4.5 V → 898.6 mV.
  - At gain 1 (FSR ±1.2 V) the ADC full scale corresponds to **6.01 V** at the PT output, which leaves headroom for supply faults.
  - Use **PGA gain 1**. Gain 2 (±0.6 V) would clip above 3.0 V of PT output.
- 4.7 nF from the divider node to GND. Source resistance R_th = 20k ∥ 4.99k = 3.99 kΩ, so f_c = **8.48 kHz**.
  - At the 4 MHz modulator rate that's about −53 dB, which is ample.
  - It does nothing against content at 1–4 kHz folding back below the output Nyquist frequency. See plan Section 3.7.
- Expect percent-level gain error per channel:
  - two 1 % resistors give up to ≈ ±1.6 % ratio error;
  - the ADC's input impedance at gain 1 (check the datasheet) loads the 4 kΩ source.
  
  So a per-channel two-point calibration (offset and gain) is required (test A6).
- Reference: REFIN is a capacitor to GND, so use the **internal 1.2 V reference**.
- PT names, ranges and the two eReg feedback roles: ❓ later (Joss). Until assigned, the PT names are `PT1`…`PT16`.

**TC front end.**
- TCn+ → AIN(2n−2), TCn− → AIN(2n−1): TC1 = AIN0/AIN1, TC2 = AIN2/AIN3, … TC6 = AIN10/AIN11. ❓ Confirm the pattern holds for TC3–TC6; only TC1+ and TC2+ were stated.
- TC− goes straight to the odd AIN pin with no ground reference, and the probes are ungrounded-junction. Each TC therefore needs a common-mode bias: enable the ADS124S08 **VBIAS** on each TC− input. With ±2.5 V supplies VBIAS is (AVDD+AVSS)/2 = 0 V. Without it the inputs float and the readings are garbage.
- Internal 2.5 V reference. **PGA gain 64** → ±39.06 mV, which covers Type E from −270 °C up to ≈ +530 °C. Type E reaches ≈ 37.0 mV at 500 °C; confirm against the NIST table.
- CJC: **MCP9700** on IO4, right next to the terminal block. V_out = 500 mV + 10 mV/°C. Its accuracy (a few °C; check the datasheet) adds directly to every TC reading, so do a one-point CJC offset calibration at room temperature (test A8).
- All six TCs assumed Type E. Names: `TC1`…`TC6` until Joss assigns them.

## INA237 (on FsPower)

I²C on IO1 (SCL) / IO2 (SDA); A0 = A1 = GND → address **0x40** (confirm against the address table). Shunt = **2 mΩ**.
30 A × 2 mΩ = 60 mV, which exceeds the ±40.96 mV range (20.48 A max), so use **ADCRANGE = ±163.84 mV** → 81.9 A
full scale, about 2.5 mA resolution (5 µV LSB ÷ 2 mΩ). The range values are from memory; confirm them in the INA237 datasheet.
