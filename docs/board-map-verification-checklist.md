# Board Map Verification Checklist

This checklist is for verifying `hybrid-fw2026-claude-code-kit/docs/board-map.md` against the released schematic PDF in `docs/hardware/`.

**Instructions:**
- Cross-check each item below against the schematic
- Mark with ✅ when verified, ❌ if discrepancy found
- Resolve all ❓ items that the schematic can answer
- Document any discrepancies in the Notes section

---

## Module Specification

- [ ] Both ESPs are ESP32-S3-WROOM-1U-N8 (8 MB flash, no PSRAM)
- [ ] GPIO35-37 are available (not used by PSRAM)
- [ ] USB-Serial-JTAG is configured for console on both ESPs

## Node Identification

### FsPower (U13)
- [ ] Designator U13 is correct
- [ ] MAC address: _(to be read from boot log and filled in)_
- [ ] Devices: DevFsRelays, DevFsPiPacketBroadcaster, DevFsPowerHealth

### FsAnalog (U12)
- [ ] Designator U12 is correct
- [ ] MAC address: _(to be read from boot log and filled in)_
- [ ] Devices: DevFsLoxGn2Transducers, DevEregControl, DevFsThermocouples, DevFsAnalogHealth

## UART Topology

### FsPower UART Connections
- [ ] PI port: UART2, RX=IO15, TX=IO7, 2 Mbaud
- [ ] ANALOG port: UART1, RX=IO16, TX=IO17, 2 Mbaud
- [ ] 33 Ω series resistors on both links
- [ ] Pi connection to GPIO14 (TXD) and GPIO15 (RXD) on Pi header

### FsAnalog UART Connections
- [ ] POWER port: UART0, RX=IO44 (RXD0), TX=IO43 (TXD0), 2 Mbaud
- [ ] CAPFILL port: UART1, RX=IO16, TX=IO17, 921600 baud
- [ ] AUX port: UART2, RX=IO18, TX=IO8, 921600 baud
- [ ] ❓ **OPEN:** Is AUX port also through a MAX3490 RS-422 transceiver?
- [ ] CAPFILL uses MAX3490EESA+ RS-422 transceiver
- [ ] 33 Ω series resistors on RS-422 links

## FsPower GPIO Assignments (U13)

### Critical Safety Pins
- [ ] IO0: strapping pin, marked as do-not-use
- [ ] IO3: strapping pin with 10k pull-up, marked as do-not-use
- [ ] IO45, IO46: strapping pins, NC

### UART Pins
- [ ] IO7: uart-t-rpi (TX to Pi)
- [ ] IO15: uart-f-rpi (RX from Pi)
- [ ] IO16: uart-f-anlg-esp (RX from FsAnalog)
- [ ] IO17: uart-t-anlg-esp (TX to FsAnalog)

### I²C (INA237)
- [ ] IO1: ina237-scl (SCL)
- [ ] IO2: ina237-sda (SDA)
- [ ] INA237 address is 0x40 (A0=A1=GND per datasheet table)

### Valve Enable Outputs
Verify each valve-en GPIO drives its gate driver EN pin:

- [ ] VALVE_1: IO37 (valve-en1)
- [ ] VALVE_2: IO36 (valve-en2)
- [ ] VALVE_3: IO14 (valve-en3)
- [ ] VALVE_4: IO21 (valve-en4)
- [ ] VALVE_5: IO47 (valve-en5)
- [ ] VALVE_6: IO48 (valve-en6)
- [ ] VALVE_7: IO35 (valve-en7)
- [ ] VALVE_8: IO13 (valve-en8)
- [ ] VALVE_9: IO12 (valve-en9)
- [ ] VALVE_10: IO11 (valve-en10)
- [ ] VALVE_11: IO10 (valve-en11)
- [ ] VALVE_12: IO9 (valve-en12)
- [ ] ❓ **OPEN:** Verify all valve EN pins have pull-downs

### eReg Power Control
- [ ] IO38: ereg-pwr-en2 (eReg 2 TPS259827 EN)
- [ ] IO39: ereg-pwr-en1 (eReg 1 TPS259827 EN)
- [ ] ❓ **OPEN:** Is there a pull-down on each EN pin?
- [ ] ❓ **OPEN:** Verify EN polarity in TPS259827 datasheet

### eReg Power Good Inputs
- [ ] IO8: ereg-pgood2 (TPS259827 PG output)
- [ ] IO18: ereg-pgood1 (TPS259827 PG output)
- [ ] ❓ **OPEN:** Do ereg-pgood1/2 have pull-ups? (TPS259827 PG is open-drain)

### Continuity Mux Control
- [ ] IO4: valve-cont (ADC1_CH3, mux COMMON with 100 nF to GND)
- [ ] IO44 (RXD0 reused): cont-mux-S0
- [ ] IO42: cont-mux-S1
- [ ] IO41: cont-mux-S2
- [ ] IO40: cont-mux-S3

### Unused Pins
- [ ] IO5, IO6: NC
- [ ] IO43 (TXD0): NC

## Continuity Mux (U14) on FsPower

### Mux IC and Power
- [ ] U14 is CD74HC4067SM96
- [ ] VCC = 3V3
- [ ] E_N tied to GND (always enabled)

### Mux Channel Assignments
Verify net connections for each mux input:

- [ ] I0: valve-cont3 (VALVE_3)
- [ ] I1: valve-cont4 (VALVE_4)
- [ ] I2: valve-cont5 (VALVE_5)
- [ ] I3: valve-cont8 (VALVE_8)
- [ ] I4: valve-cont9 (VALVE_9)
- [ ] I5: valve-cont10 (VALVE_10)
- [ ] I6: valve-cont11 (VALVE_11)
- [ ] I7: valve-cont12 (VALVE_12)
- [ ] I8: valve-cont6 (VALVE_6)
- [ ] I9: valve-cont7 (VALVE_7)
- [ ] I10: valve-cont1 (VALVE_1)
- [ ] I11: valve-cont2 (VALVE_2)
- [ ] I12: ereg-imon-mux1 (eReg 1 IMON)
- [ ] I13: ereg-imon-mux2 (eReg 2 IMON)
- [ ] I14, I15: NC

### Continuity Divider Circuit
- [ ] 100 kΩ resistor (top of divider)
- [ ] 10 kΩ resistor (bottom of divider)
- [ ] Divider fed from 12V battery through the load
- [ ] ❓ **OPEN:** Does divider tap the low-side switched node or high-side?
- [ ] Expected voltage when load connected and off: V_bat × 10/110

### eReg IMON Circuit
- [ ] TPS259827 R_IMON = 665 Ω
- [ ] 10 kΩ / 22 nF RC filter to mux
- [ ] Filter cutoff ≈ 680 Hz
- [ ] Confirm TPS259827 G_IMON value from datasheet

## FsAnalog GPIO Assignments (U12)

### Critical Safety Pins
- [ ] IO0: strapping pin, marked as do-not-use
- [ ] IO3: strapping pin with 10k pull-up, marked as do-not-use
- [ ] IO45, IO46: strapping pins, NC

### UART Pins
- [ ] IO43 (TXD0): uart-from-anlg-esp (TX to FsPower)
- [ ] IO44 (RXD0): uart-to-anlg-esp (RX from FsPower)
- [ ] IO16: uart1-f-esp (UART1 RX from CapFill)
- [ ] IO17: uart1-t-esp (UART1 TX to CapFill)
- [ ] IO18: uart2-f-esp (UART2 RX from AUX)
- [ ] IO8: uart2-t-esp (UART2 TX to AUX)

### ADC1 Inputs (IO4-7)
- [ ] IO4: tc-cjc-temp (MCP9700 CJC sensor, ADC1_CH3)
- [ ] IO5: 24V-pwr-pgood (ADC1_CH4, logic and analog)
- [ ] IO6: 12V-pwr-pgood (ADC1_CH5, logic and analog)
- [ ] IO7: 12V-digital-pgood (ADC1_CH6, logic and analog)
- [ ] ❓ **OPEN:** Are IO5-7 resistor dividers (give values) or regulator PG outputs?

### PT Acquisition (ADS131M08 × 2)
- [ ] IO21: pt-sync (SYNC/RESET, shared by both ADCs)
- [ ] IO35: esp-clkout (CLKIN to both ADCs, LEDC output)
- [ ] IO36: pt-mosi (SPI MOSI, shared)
- [ ] IO37: pt-miso (SPI MISO, shared)
- [ ] IO38: pt-sclk (SPI SCLK, shared)
- [ ] IO47: pt-cs-prim (CS for "prim" ADC, PT1-8)
- [ ] IO48: pt-drdy-prim (DRDY from "prim")
- [ ] IO40: pt-cs-bck (CS for "bck" ADC, PT9-16)
- [ ] IO39: pt-drdy-bck (DRDY from "bck")

### TC Acquisition (ADS124S08)
- [ ] IO9: tc-miso (SPI MISO)
- [ ] IO10: tc-sclk (SPI SCLK)
- [ ] IO11: tc-mosi (SPI MOSI)
- [ ] IO12: tc-cs (SPI CS)
- [ ] No DRDY/START/RESET pins wired (use SPI commands)

### eReg PWM Outputs
- [ ] IO42: ereg-pwm1 (eReg 1 servo PWM, kServoPin)
- [ ] IO41: ereg-pwm2 (eReg 2 servo PWM, not driven)

### Unused Pins
- [ ] IO1, IO2: NC
- [ ] IO13, IO14, IO15: NC

## PT Front End (ADS131M08 × 2)

### Channel Assignment
- [ ] PT1-8 → "prim" AIN0-7
- [ ] PT9-16 → "bck" AIN0-7
- [ ] PT1 = prim AIN0, PT8 = prim AIN7, PT9 = bck AIN0, PT16 = bck AIN7

### Divider Circuit (per channel)
- [ ] 20 kΩ resistor (top)
- [ ] 4.99 kΩ resistor (bottom)
- [ ] Ratio k = 0.19968
- [ ] 4.7 nF capacitor from divider node to GND
- [ ] Cutoff frequency ≈ 8.48 kHz

### ADC Configuration
- [ ] Internal 1.2V reference (REFIN is capacitor to GND)
- [ ] PGA gain 1 (±1.2V FSR)
- [ ] CLKIN frequency for 1953 SPS: 8.000 MHz (OSR 2048)
- [ ] Alternative CLKIN for 1221 SPS: 5.000 MHz

## TC Front End (ADS124S08)

### Channel Assignment Pattern
- [ ] TC1: AIN0 (+) / AIN1 (−)
- [ ] TC2: AIN2 (+) / AIN3 (−)
- [ ] ❓ **OPEN:** Confirm TC3-6 follow pattern: TCn = AIN(2n-2)/AIN(2n-1)
- [ ] TC6: AIN10 (+) / AIN11 (−)

### ADC Configuration
- [ ] Internal 2.5V reference
- [ ] PGA gain 64 (±39.06 mV FSR)
- [ ] VBIAS enabled on all TC− inputs (AIN1, 3, 5, 7, 9, 11)
- [ ] Type E thermocouple assumed for all 6 channels

### CJC Sensor (MCP9700)
- [ ] Located on IO4 (ADC1_CH3)
- [ ] Next to TC terminal block
- [ ] V_out = 500 mV + 10 mV/°C
- [ ] Verify MCP9700 accuracy spec from datasheet

## INA237 (on FsPower)

### I²C Configuration
- [ ] Address 0x40 (A0=A1=GND per datasheet table)
- [ ] SCL on IO1
- [ ] SDA on IO2

### Current Sensing
- [ ] Shunt resistor = 2 mΩ
- [ ] ADCRANGE = ±163.84 mV (verify value from datasheet)
- [ ] Full scale ≈ 81.9 A
- [ ] Resolution ≈ 2.5 mA

## Datasheets to Cross-Reference

Verify that all datasheets are present in `docs/datasheets/`:

- [ ] ADS131M08
- [ ] ADS124S08
- [ ] INA237
- [ ] CD74HC4067 (mux)
- [ ] TPS259827 (eFuse)
- [ ] MCP9700 (CJC sensor)
- [ ] MAX3490 (RS-422 transceiver)

## Notes and Discrepancies

_(Document any issues found during verification)_

---

## Verification Sign-off

**Verified by:** _________________
**Date:** _________________
**Schematic revision:** _________________

**Outstanding ❓ items after verification:**
-
-
-

**Action items:**
-
-
