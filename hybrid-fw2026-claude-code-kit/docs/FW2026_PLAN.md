# FW2026 Plan — Firing Station Firmware Improvement Pass

Owner: Joss Clegg. Executor: Claude Code (VS Code). Rules: `CLAUDE.md`. Pins: `docs/board-map.md`.
Status legend: ✅ decided · ❓ open (Section 6). Do not resolve ❓ items yourself.

---

## 1. Goals and non-goals

**Goals**
1. Move every inter-device link from ESP-NOW to UART: Pi↔FsPower and FsPower↔FsAnalog at 2 Mbaud on-board; FsAnalog↔CapFill and FsAnalog↔AUX over RS-422 at 921600. No Wi-Fi.
2. Port to the new board: two ESPs (down from three); 2× ADS131M08 for PTs, ADS124S08 for TCs, INA237 for the main bus.
3. **Sample all 16 PTs at 1953 SPS** and stream every sample to the Pi, which logs it for combustion-instability analysis. Keep a 50 Hz psi packet for the live dashboard.
4. Stream all 16 PT and 6 TC channels whether or not a sensor is connected, so a new PT can be used without reflashing.
5. Add a 1 Hz systems-health packet per ESP: INA237, rail and eReg PGOODs, continuity, eReg IMON, link statistics, resets.
6. Make links robust: CRC on every frame, sequence numbers, command validation and command acks.
7. Strip unused devices, libraries, packets, nodes and OTA.
8. Make it quick to add another UART board (the new cap-fill board, or anything on AUX): a node-table entry and nothing else.

**Non-goals (this pass):**
- **The state machine is parked for a separate chat with Joss.** Do not change the relay logic, sequence timing, valve function mapping, or ABORT/CUSTOM behavior. The only relays-file edits allowed are those in CLAUDE.md.
- No change to the eReg control law or the cap-fill measurement.
- No new autonomous safety behavior.
- No changes to the Pi `uploader` code. Its baud setting is changed by Joss on the Pi.
- No IDF or arduino-esp32 upgrade.
- The new cap-fill board's hardware port is deferred until Joss has its pins. The link to it is built now.

---

## 2. What last year's code does (read before changing it)

| Area | Baseline (`main` @ `d71c5cb`, tagged `fs-2025-stable`) |
|---|---|
| Framework | Arduino-on-IDF (ESP-IDF 5.1.5, arduino-esp32 3.0.7). `app_main` → `initArduino()` → `WiFi.mode(WIFI_STA)` → node lookup by MAC → `EspNowSetup` → `Node::Run()` creates one task per device (4 KB stack, core 0, `tskIDLE_PRIORITY`). |
| Routing | `Device::Send(DeviceType, T)` prepends the 4-byte `DeviceType`, then loops back to a local device or calls `EspNowSend` to the owning node's MAC. `Node::OnReceive` strips the header and calls `QueueReceive`. Each device queue is 256 × 251 B ≈ 64 KB. |
| Pi link | FsScientific1 `Serial2` (RX 18 / TX 8) at 230400. Frame = raw packed struct + `AA 55`. No type byte and no CRC; the Pi tells packet types apart by length. |
| UART forwarding | FsScientific2 → `Serial1` → FsScientific1 `utils::SerialForwarder` → Pi. This is the precedent for this year's forwarding. |
| Commands | `DevFsPiPacketBroadcaster`: 10-byte `FsCommandPacket` from the Pi → `Send` to eReg, transducers, relays, then `delay(500)`, then injector. |
| Pi aggregation | `DevFsLoxGn2Transducers` receives state, eReg, imon, thermo and cap-fill packets, calls `SendToPi` for each, and also sends its own 50 Hz transducer packet. |
| Transport defects fixed by this pass | (1) `SerialPacketReader::Tick()` drains every available byte before checking for `AA 55`, so two frames that arrive together merge and get dropped. (2) `AA 55` can occur inside float payloads, which splits frames falsely. (3) `DevFsRelays::SendState()` runs on every loop pass with no rate limit; ESP-NOW's drop-if-busy behavior was the only throttle. (4) `ota.cpp` includes `ota_version.h`, which is gitignored and generated only by `deploy_ota.sh`, so a fresh clone doesn't build. Removing OTA fixes this. |
| Docs drift | README says ESP-IDF 5.5; the lockfile and sdkconfig say 5.1.5, which is what is actually used. `test_send_command.py` has stale command numbers. |

---

## 3. Design

### 3.1 Node table (`nodeconfig.h`) ✅ structure, ❓ MACs

```
FsPower  : MAC ❓  devices {DevFsRelays, DevFsPiPacketBroadcaster, DevFsPowerHealth}
           ports {PI:     UART2 RX15 TX7  2000000  → reaches {Pi}
                  ANALOG: UART1 RX16 TX17 2000000  → reaches {FsAnalog, CapFill, <aux nodes>}}
FsAnalog : MAC ❓  devices {DevFsLoxGn2Transducers, DevEregControl, DevFsThermocouples, DevFsAnalogHealth}
           ports {POWER:   UART0 RX44 TX43 2000000 → reaches {FsPower, Pi}
                  CAPFILL: UART1 RX16 TX17 921600  → reaches {CapFill}
                  AUX:     UART2 RX18 TX8  921600  → reaches {}   (reserved)}
CapFill  : MAC ❓ (new board, deferred)  devices {DevCapFill}
           ports {ANALOG: ❓ pins, 921600 → reaches {FsAnalog, FsPower, Pi}}
```
- Replace `Node`'s `use_esp_now` flag with a list of `LinkPort` descriptors: name, UART number, RX/TX pins, baud, and the set of nodes (plus the Pi) reachable through that port. The topology is a tree, so routing is a static next-hop lookup with no discovery.
- **Adding a board** (cap-fill now, AUX later):
  1. Add a `Node` entry with its MAC, devices and its one port.
  2. Add the node's name to the `reaches` set of every port on the path from the Pi to it.
  3. Flash the same image.

  Document this recipe in the README (Phase 8).
- MAC: `esp_read_mac(mac, ESP_MAC_WIFI_STA)` replaces `esp_wifi_get_mac`. It returns the same eFuse-derived address without starting Wi-Fi. Remove `WiFi.mode(WIFI_STA)`. Leave `CONFIG_ESP_WIFI_ENABLED` in sdkconfig alone; just never call any Wi-Fi or ESP-NOW API.
- New-board MAC procedure: flash the board. `main.cpp` already prints `This MAC:` before calling `Die()` on an unknown node; read it from the USB console and add it to the node table.

### 3.2 Link framing (all ports, both directions) ✅

The uploader splits the stream on `AA 55` and hands each chunk to `parse_packet` (verify in Phase 0). So the
delimiter stays `AA 55`, and the frame body is byte-stuffed so that `AA 55` can't appear inside it.

Frame body, before stuffing (little-endian):

| Off | Field | Type | Meaning |
|---|---|---|---|
| 0 | `dst` | u8 | `DeviceType` value, or `0xFE` = Pi, or `0xFD` = command from Pi |
| 1 | `src` | u8 | Origin node ID: 0 FsPower, 1 FsAnalog, 2 CapFill, 3+ future, 0xFF Pi |
| 2 | `type` | u8 | `PacketType` (Section 3.3) for Pi-bound frames and commands; 0 for internal traffic |
| 3 | `seq` | u16 | Per-(origin node, type) counter; wraps |
| 5 | payload | N ≤ 256 | The packed struct, unchanged |
| 5+N | `crc` | u16 | CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, xorout 0) over bytes 0…4+N. Check value for ASCII `"123456789"` = **0x29B1**. Python: `binascii.crc_hqx(body, 0xFFFF)`. |

**Stuffing:** insert `0x00` after every `0xAA` in the body, then append `AA 55`. The receiver removes the
`0x00` that follows each `0xAA`. Any other byte after `0xAA`, a body shorter than 7 bytes, or a CRC
mismatch means the frame is dropped and counted.

**Receiver:** feed one byte at a time into a state machine, check for the delimiter after **every** byte,
and un-stuff on the fly into a 300-byte body buffer. On overflow, discard until the next delimiter and count it.

**Routing on receive:**
- `dst` is a local device → `QueueReceive(payload)`, as `Node::OnReceive` does today. Internal device messages stay ≤ 250 B.
- `dst` lives on another node, or is `0xFE` and the Pi isn't on this node → forward the **received stuffed bytes unchanged** out of the next-hop port, as last year's `SerialForwarder` did.
- `dst == 0xFE` on FsPower → write to the PI port.
- `dst == 0xFD` → deliver to DevFsPiPacketBroadcaster.

**`Device::Send` is unchanged for callers.** It resolves the owning node; if local, it loops back; otherwise it frames with `type = 0` and writes to the next-hop port.
**New `SendToPi(const T&)`**, usable by any device: `type` comes from a compile-time trait `PacketTypeOf<T>` (a `static_assert` fails without one), and it routes to `dst = 0xFE`. This replaces the three copies of `SendToPi` / `SendToOtherEsp32` and the `SerialForwarder`.

**TX:** one mutex per port. If `availableForWrite() < frame_len`, drop the frame and count it; **never block**.
**Buffers:** set with `setRxBufferSize` / `setTxBufferSize` **before** `begin()`:
- 8 KB RX and 8 KB TX on the 2 Mbaud ports (≈ 40 ms at 200 kB/s);
- 2 KB on the 921600 ports.

**RX tasks:** one per port, pinned to **core 1** at `tskIDLE_PRIORITY + 2`. Loop: read everything available, parse and route, then `vTaskDelay(1)`. Device tasks are unchanged (core 0, idle priority).

**Queue sizing (required):** `kQueueNumEntries` 256 → 64 (≈ 16 KB per device). At 256, FsAnalog's four device queues alone would take ~257 KB of a ~300 KB heap. The 256 was set for 100 Hz cap-fill, which now runs at 20 Hz. Replace `ESP_NOW_MAX_DATA_LEN` with a local `kMaxMessageLen = 250`. Report free heap after `Node::Run()` on both nodes.

### 3.3 Packets ✅

Pi-bound types (all packed, with `static_assert` on size):

| Type | Struct (bytes) | Path | Rate | Contents |
|---|---|---|---|---|
| 0x01 | `FsStatePacket` (14, **unchanged**) | relays → transducers → Pi | on change + 20 Hz | as last year |
| 0x02 | `FsPtsPacket` (72) | transducers → Pi | 50 Hz | `u64 ts; float psi[16];` exactly what the firmware (and the eReg) sees: zeroed by RECALIBRATE, × psi_per_volt. Feeds the live dashboard. |
| 0x03 | `FsTcsPacket` (37) | thermocouples → transducers → Pi | ≥ 10 Hz | `u64 ts; float tc_c[6]; float cjc_c; u8 open_mask;` |
| 0x04 | `FsEregPacket` (27) | transducers (from `EregStateData`) → Pi | 50 Hz | `u64 ts; bool closed, stage_1, stage_2; float current_angle, p_cont, i_cont, d_cont;` |
| 0x05 | `CapFillPacket` (17, **unchanged**) | cap-fill → transducers → Pi | 20 Hz | as last year |
| 0x06 | `FsPowerHealthPacket` | power health → Pi | 1 Hz + fault edges (≤ 10 Hz) | Section 3.5 |
| 0x07 | `FsAnalogHealthPacket` | analog health → Pi | 1 Hz + fault edges (≤ 10 Hz) | Section 3.5 |
| 0x08 | `FsCommandAckPacket` (8) | broadcaster → Pi | per command | `u16 cmd_seq; u8 command; u8 result; u32 ms_since_boot;` result: 0 accepted, 1 rejected |
| 0x09 | `FsPtsRawPacket` (252) | PT acquisition task → Pi | 390.6 frames/s | `u64 ts_us_first; u32 first_sample_index; u8 code[5][16][3];` = 5 consecutive samples × 16 channels of raw 24-bit two's-complement ADC codes, little-endian. `first_sample_index` increments by 5 per frame, so a gap is a lost frame. |
| 0x0A | `FsPtCalPacket` (200) | transducers → Pi | 1 Hz, and immediately after RECALIBRATE | `u64 ts; float zero_volts[16]; float volts_per_code[16]; float psi_per_volt[16];`. Lets the Pi convert raw codes exactly the way the firmware does: `psi = (code × volts_per_code − zero_volts) × psi_per_volt`, where `volts_per_code` includes the divider ratio and the per-channel gain calibration. |

Pi → ESP: `type 0x80` = `FsCommandPacket` (10 B, unchanged), `dst 0xFD`, `src 0xFF`.

Internal sizes received by DevFsLoxGn2Transducers: command 10, state 14, `EregStateData` 20, `FsTcsPacket` 37, `CapFillPacket` 17. All unique; the existing `static_assert` enforces it.
Removed: `FsLoxGn2TransducersPacket`, `FsInjectorTransducersPacket`, `FsThermocouplesPacket`, `RelayCurrentMonitorPacket`, `GpsPacket`, `ImuPacket`, `DhtPacket`, `RadioPacket`.

### 3.4 Command path ✅
1. FsPower PI port receives a frame with `dst 0xFD`. Validate stuffing, CRC, `type == 0x80`, a 10 B payload, `command` ∈ known `FsCommand` values, and every bool byte ≤ 1.
2. Invalid but with a good CRC → ack `result = 1`, no delivery. Bad CRC → nothing (counted).
3. Valid → `Send` to **DevFsRelays (local) first**, then DevEregControl, then DevFsLoxGn2Transducers (both on FsAnalog). **Remove the `delay(500)`** and the send to the deleted injector device. Then ack `result = 0`.
4. Everything downstream is unchanged baseline behavior.

Requirement: ABORT, from the last byte on the Pi TX line to DEPRESS valve-en going high, ≤ 20 ms; eReg PWM at CLOSED ≤ 30 ms (test A3). In provisional-map builds DEPRESS = VALVE_3 (Section 3.10).

### 3.5 Health packets ✅ fields; Claude Code finalizes the layout and size

Integers in engineering units (mV, mA, mW, 0.1 °C). Fault signals increment **saturating u8 counters**
and request an immediate send (≤ 10 Hz). Counters survive a lost packet; a latched flag wouldn't.

**FsPowerHealthPacket:**
- `u64 ts`; `u8 flags` (bit0 = provisional-map build)
- INA237: `u16 vbus_mv`, `i32 ibus_ma`, `u32 power_mw`, `i16 die_temp_c10`, `u16 diag_alrt` (raw)
- `u16 valve_cont_mv[12]` (VALVE_1…12 order, translated from the mux order), `u16 valve_cont_ok` (bit N: V_cont > 0.5 × V_bus × 10/110), `u16 valve_en_readback` (pin output levels)
- `i16 ereg_imon_ma[2]`; `u8 ereg_pwr_en` (bits 0–1); `u8 ereg_pgood` (bits 0–1); `u8 ereg_pgood_falls[2]` (from GPIO falling-edge interrupts on IO18/IO8)
- `u8 reset_reason`, `u32 uptime_ms`, `u32 min_free_heap`
- per port (PI, ANALOG): `u32 rx_frames; u16 crc_err, framing_err, tx_drop, seq_gaps, ms_since_rx`
- `u16 cmds_ok, cmds_rejected`

**FsAnalogHealthPacket:**
- `u64 ts`; `u8 flags`
- Rails, from ADC1 samples of IO5/IO6/IO7: `u16 rail_pin_mv[3]`; `u16 rail_est_mv[3]` (pin mV ÷ divider ratio, or 0 if ❓ D6 says these aren't dividers); `u8 rail_good` (bits 0–2, by threshold with hysteresis); `u8 rail_falls[3]`
- `u16 pt_present_mask` (PT-output volts within 0.30–4.70 V)
- ADS131M08 ×2: `u16 status_word[2]`, `u16 spi_crc_err[2]`, `u32 samples_total`, `u16 drdy_overrun`, `u16 raw_tx_drop`
- ADS124S08: `u8 status`, `u8 tc_open_mask`
- `i16 cjc_c10`, `i16 ads124_temp_c10` (internal sensor as a cross-check), `i16 esp_temp_c10`
- `u8 reset_reason`, `u32 uptime_ms`, `u32 min_free_heap`
- per port (POWER, CAPFILL, AUX): the same six link counters

**Rail ADC sampling (FsAnalog):** ADC1 continuous (DMA) mode on IO4–IO7 at ≥ 2 kSPS per channel, using arduino-esp32's continuous-ADC API or IDF `adc_continuous`. The PGOOD state is derived from these samples with hysteresis. Drops of ≥ 1 ms are counted; shorter glitches can be missed, and that's accepted. The IO4 samples also give the CJC reading (averaged).

**Continuity / IMON scan (FsPower):** select a channel, wait the settling time from board-map (8 ms for continuity, 11 ms for IMON), then average 16 samples with `analogReadMilliVolts()`. Full scan ≈ 120 ms. Use the latest complete scan in each health packet.

### 3.6 Link bandwidth (2 Mbaud = 200 000 B/s) ✅

| Stream | Frame on wire (payload + 7 + 2 + stuffing) | Rate | B/s |
|---|---|---|---|
| FsPtsRaw | 252 + 9 + ~1 = 262 | 390.6/s | 102 300 |
| FsPts | 72 + 9 + ~0.3 = 81 | 50 Hz | 4 070 |
| FsEreg | 36 | 50 Hz | 1 800 |
| FsState | 23 | 20 Hz | 460 |
| FsTcs | 46 | 10 Hz | 460 |
| CapFill | 26 | 20 Hz | 520 |
| FsPtCal | 209 | 1 Hz | 210 |
| Health ×2 | ~100 | 1 Hz each | 200 |
| **Total** | | | **≈ 110 000 B/s = 55 %** |

- Both 2 Mbaud links (Pi↔FsPower and FsPower↔FsAnalog) carry the same Pi-bound load; keep measured utilization ≤ 60 %.
- At 1.5 Mbaud this would be 73 %, which is too high. If the Pi 5 fails the 2 Mbaud loopback (A0), fall back to 1221 SPS (Section 3.7): ≈ 72 kB/s, 36 % of 2 Mbaud or 48 % of 1.5 Mbaud.

### 3.7 PT acquisition (FsAnalog) ✅

- **Rate:** CLKIN = 8.000 MHz from LEDC on IO35 (80 MHz APB source, 1-bit duty resolution, integer divider → 50 % duty). OSR = 2048. fDATA = fCLKIN / (2 × OSR) = **1953.125 SPS** on every channel.
  - The clock divider is one constant in `fs_board_config.h`. Divider 16 (5.000 MHz CLKIN) gives **1220.7 SPS** if that's ever wanted.
  - Both CLKINs are inside the HR-mode range for gain 1. Verify the waveform and duty cycle on a scope; the datasheet allows 40–60 %.
- **Filter:** for OSR ≥ 2048 the ADS131M08 uses sinc3 at OSR 1024 followed by a sinc1 stage. My derivation gives a −3 dB point of ≈ 700 Hz at 1953 SPS (≈ 450 Hz at 1221 SPS). The datasheet gives no number, so measure it (A6b).
  - Alias rejection just above Nyquist (977 Hz) is weak, and the 8.5 kHz front-end RC doesn't help there. Content between ~1 kHz and ~3 kHz will partially fold into band; A6b quantifies how much.
  - If that matters for the instability data, the follow-on is to run the ADC at 3906 SPS (OSR 1024) and FIR-decimate on the ESP. That's out of scope for now.
- **Two ADCs:** shared SPI (SPI2/FSPI through the GPIO matrix on IO36/37/38, SCLK 8 MHz), shared SYNC/RESET (IO21), shared CLKIN; separate CS (prim IO47, bck IO40) and DRDY (prim IO48, bck IO39).
  - Configure per the datasheet's multi-device synchronization section. Enable the SPI CRC and count errors.
  - Gain 1 (±1.2 V), internal reference. Leave the DC-block filter off (it would remove static pressure).
- **Acquisition task:** pinned to **core 1** at a priority above the link RX tasks.
  - prim DRDY falling-edge ISR → task notification → read both devices (status + 8 channels + CRC each; 60 B at 8 MHz ≈ 60 µs) → store each channel's latest code.
  - Every 5 samples, pack an `FsPtsRawPacket` and `SendToPi` it (non-blocking; count drops).
  - Count DRDY overruns: if a new DRDY arrives before the read finishes, count it.
- **Conversion:**
  - `pt_volts = code × (1.2 V / 2²³) / k × gain_cal[ch] + offset_cal[ch]`, with k = 0.19968 (board-map).
  - `psi = (pt_volts − zero_volts[ch]) × psi_per_volt[ch]`.
  - `gain_cal` and `offset_cal` come from the A6 bench calibration and live in `fs_board_config.h` (defaults 1.0 and 0.0).
- **Interface compatibility (critical):** DevEregControl reads `transducers_->copv_1.GetLatestPsi()` and `transducers_->oxtank_2.GetLatestPsi()` from its own task.
  - New class `PtChannel` keeps `MovingMedianADC`'s public methods: `Tick()`, `Recalibrate(int)`, `ResetZero()`, `GetLatestVolts()`, `GetMedianVolts()`, `GetLatestPsi()`, `GetMedianPsi()`, `PrintLatestPsi()`.
  - `DevFsLoxGn2Transducers` keeps public members **named `copv_1` and `oxtank_2`**, bound to the channels assigned to the eReg upper and lower roles in `fs_board_config.h`.
  - Latest values are single aligned 32-bit stores (atomic on Xtensa), read lock-free as today.
  - `Tick()` becomes a no-op, because the acquisition task updates the channels.
- `Recalibrate(n)` takes the median of n **fresh** samples per channel (100 samples ≈ 51 ms), then sends `FsPtCalPacket`.
- Board config `main/include/fs_board_config.h`:
  - `kPtChannels[16] = {name, adc, ain, psi_per_volt, gain_cal, offset_cal}`, with names `PT1`…`PT16` and `psi_per_volt` 0 (unassigned) until Joss fills them in;
  - `kEregUpperPt`, `kEregLowerPt` (−1 = unassigned → provisional, Section 3.10);
  - `kPtClkDiv`.
- Delete `MovingMedianAdc`, `Adafruit_ADS1X15`, `Adafruit_BusIO`.

### 3.8 TC acquisition (FsAnalog) ✅
- ADS124S08 on SPI3/HSPI (MISO IO9, SCLK IO10, MOSI IO11, CS IO12). No DRDY/START/RESET pins are wired, so use the SPI commands (RESET, START, RDATA) and status polling per the datasheet.
- TCn: AIN(2n−2)+ / AIN(2n−1)− (❓ confirm TC3–6). **VBIAS enabled on every TC− input** (ungrounded probes; VBIAS = 0 V with ±2.5 V supplies). Internal 2.5 V reference. **PGA gain 64** (±39.06 mV).
- Cycle the 6 channels with the input mux. After each mux change, wait out the filter latency the datasheet specifies so every reported conversion is settled. Choose the data rate and filter (e.g. low-latency) for **≥ 10 Hz per channel** with 50/60 Hz rejection if achievable.
- Open-TC detection: the ADS124S08 burnout current sources, applied in a separate diagnostic conversion (not during measurement) once per second → `open_mask`.
- Type E: NIST ITS-90 polynomials (NIST Monograph 175 / NIST ITS-90 thermocouple database). CJC: MCP9700 on IO4 (`T = (mV − 500) / 10`) → forward polynomial to mV, add the measured mV, apply the inverse polynomial. Host test against NIST table values at −180, −100, 0, 100 and 300 °C, within ±0.05 °C.
- `kCjcOffsetC` (one-point calibration, default 0) in `fs_board_config.h`.
- Delete `SparkFun_MCP9600_Arduino_Library`.

### 3.9 Pi parser (`pi/main_fs_pi.py`) ✅
The same shape as last year's file: `parse_packet(packet)` returns `uploader.Record` or `None`;
`format_message(message)` returns bytes; then `uploader.run(delimiter, parse_packet, {"FiringStation": format_message})`.
Standard library only, plus `uploader` and `utils.MovingMedianFilter`.
- `parse_packet`: un-stuff, check CRC, dispatch on `type`, track `seq` gaps per (src, type), drop invalid frames (count them and print the count every 10 s).
- **High-rate PTs:**
  - Each `FsPtsRaw` payload is appended to a binary log file (`PT_RAW_LOG_DIR/pt_raw_<UTC start>.bin`; record = `u8 type, u16 len, payload`), and the function returns `None`. Last year's parser already returned `None` for unknown sizes, so the uploader tolerates it; Phase 0 confirms.
  - Each `FsPtCal` is written to the same file (so offline conversion is exact) and also emitted as a record.
  - Check `first_sample_index` continuity and count lost samples.
- `pi/decode_pt_raw.py`: converts a `.bin` log into a CSV and a `.npz` (time s, psi per channel, using the most recent calibration in the file). Inputs to PSD analysis.
- Records: `FsState` (unchanged fields), `FsPts`, `FsTcs`, `FsEreg`, `CapFill` (unchanged fields), `FsPtCal`, `FsPowerHealth`, `FsAnalogHealth`, `FsCommandAck`.
- **Legacy compatibility:** `PT_NAMES = {channel: legacy_name}` and `TC_NAMES`, empty until Joss fills them in. Using these, also emit last year's `FsLoxGn2Transducers` / `FsInjectorTransducers` / `FsThermocouples` records with exactly last year's field names, including the `*_median` fields. Unmapped legacy fields are 0.0, as last year.
- `PT_SCALE_OVERRIDE = {channel: psi_per_volt}` lets someone use a new PT without reflashing.
- `format_message`: same inputs as last year. It builds the 10-byte payload, adds the header (`dst 0xFD`, `src 0xFF`, `type 0x80`, module-level `seq`), CRC, stuffing and `AA 55`.
- `pi/test_main_fs_pi.py`: byte-exact round-trip against golden frames from the firmware host tests; the CRC check value; stuffing edge cases (payload ending in 0xAA, consecutive 0xAA, embedded `AA 55`); merged-frame and false-delimiter fuzz; raw-log write and decode.
- `pi/README.md`: Pi 5 setup.
  - `config.txt`: `dtparam=uart0` (GPIO14/15 → `/dev/ttyAMA0`), with no serial console on it.
  - Uploader baud = 2000000.
  - The A0 loopback test procedure.

### 3.10 Provisional maps (safety guard while the state machine and PT assignments are parked) ✅
The valve-function map and the eReg feedback PTs aren't assigned yet. To build and bench-test anyway:
- `fs_board_config.h` defines `FS_PROVISIONAL_MAP` while `kEregUpperPt`/`kEregLowerPt` are unassigned **or** the valve-function map is the provisional identity map from board-map.
- In a provisional build:
  1. `ereg-pwr-en1/2` are **never** driven high, so the servo stays unpowered. The eReg code runs unchanged but can't move anything.
  2. A boot banner prints "PROVISIONAL MAP — NOT FOR STAND USE".
  3. `flags` bit 0 is set in both health packets, and the Pi parser prints a warning on every health packet.
- Valve outputs **do** operate in provisional builds; they're needed for the A2/A3 bench tests with dummy loads.
- Leaving provisional mode requires Joss to fill in the maps; it's a source edit, never a runtime switch.
- In a non-provisional build, eReg 1 power is enabled at the end of FsPower setup (servo always powered, as last year) ❓ D4. eReg 2 is held off.

---

## 4. Phases

Each phase: plan mode → approval → branch `fs-2026/pN-*` → build green → report (per CLAUDE.md) → Joss bench-checks → merge into `fs-2026`. **Stop at the end of every phase.**

### Phase 0 — Baseline and housekeeping (no firmware behavior change)
Joss provides:
- the schematic PDF → `docs/hardware/`;
- datasheets → `docs/datasheets/`: ADS131M08, ADS124S08, INA237, CD74HC4067, TPS259827, MCP9700, MAX3490;
- `uploader.py` and last year's `main_fs_pi.py` → `docs/reference/` (read-only).

Steps:
1. Confirm tag `fs-2025-stable` = `d71c5cb` (`main` HEAD) and branch `fs-2026` exist.
2. Build the baseline as-is with ESP-IDF 5.1.5. Run `deploy_ota.sh`'s `ota_version.h` generation step only, if needed to compile. Record in `docs/baseline.md`: IDF and arduino-esp32 versions, warning count, `idf.py size`, `git submodule status`.
3. Fix the README's IDF version (→ 5.1.5).
4. Add a PreToolUse hook in `.claude/settings.json` that blocks Edit/Write on the protected files (CLAUDE.md).
5. Read `docs/reference/uploader.py` (read-only) and confirm it:
   - (a) splits only on the passed `delimiter`;
   - (b) passes chunks without the delimiter;
   - (c) tolerates `parse_packet` returning `None`;
   - (d) writes `format_message`'s bytes verbatim;
   - (e) takes its baud rate from a setting Joss can change.

   If any of these is false, STOP.
6. Write `pi/README.md` with the A0 loopback procedure. **Joss runs A0** on the Pi 5 before Phase 4.
7. Verify `docs/board-map.md` against the schematic PDF and resolve every ❓ the PDF answers. Wait for Joss to mark it verified.

### Phase 1 — Relay/eReg host simulation harness (guard only, no logic changes)
`test/host/`: a CMake host build that compiles `dev_fs_relays.h` **unmodified** against stubs for `Arduino.h` (simulated `millis()`, recorded `pinMode`/`digitalWrite`), `avionics.h` (scripted `Receive`, captured `Send`) and `packets.h`.
- Script every row of `docs/state-regression.md`; save output-vector timelines at 1 ms resolution as goldens.
- From now on, every phase must reproduce them bit-for-bit. Its only job is to prove the comms rework didn't touch relay behavior.
- Add a lighter version for `DevEregControl::ParseCommand` (servo writes captured).

### Phase 2 — Strip unused code (deletions plus the list edits needed to compile)
Remove:
- **Devices:** `dev_dht.h`, `dev_gps.h`, `dev_imu.h`, `dev_pi_serial.h`, `dev_ground_radio.h`, `dev_rocket_radio.h`, `dev_relay_imon.h`, `dev_fs_injector_transducers.h`; their `DeviceType` enumerators and `deviceindex.h` includes.
- **Nodes:** `FsScientific2`, `RocketRadio`, `PosTracking`, `GroundRadio`.
- **References that would no longer compile:** the broadcaster's `Send` to the injector, and the `RelayCurrentMonitorPacket` case in the transducers `Receive`.
- **Packets:** `GpsPacket`, `ImuPacket`, `DhtPacket`, `RadioPacket`, `RelayCurrentMonitorPacket`.
- **Components and submodules:** `DHT-sensor-library`, `Adafruit_GPS`, `RadioHead`, `MPU9255-Arduino-Library`, `Adafruit_Sensor`, `RocketsClient`.
- The stray `#include <MPU9255.h>` in the broadcaster.
- **OTA:** `ota.cpp`, `ota.h`, `deploy_ota.sh`, the `#include "ota.h"` and the commented `CheckForUpdate` call in `main.cpp`, and the README's OTA section.
  - Nothing else references OTA; app rollback is disabled in sdkconfig, so no mark-valid call is needed.
  - Keep `partitions.csv` unchanged: the factory partition boots, and the unused OTA partitions are harmless.
- `test_send_command.py`, `questions_for_alex.txt`.

Keep ADS1X15, MCP9600 and MovingMedianAdc until Phases 5 and 6 replace them, so the build stays green. Update `.gitmodules` and `main/CMakeLists.txt`.

### Phase 3 — UART link layer (replaces ESP-NOW)
1. `main/link.cpp` + `main/include/link.h`: framing, stuffing, CRC, RX state machine, non-blocking TX, counters, next-hop routing from the port table. Plain C++ behind a thin `HardwareSerial` adapter, so it compiles in host tests.
2. `avionics.cpp`: `Device::Send` and `Node::OnReceive` call the link layer. Queue 256 → 64. Remove `esp_now.h`.
3. `comms.cpp`: delete the ESP-NOW functions; keep `MacAddress`; `GetThisMacAddress()` uses `esp_read_mac`.
4. `main.cpp`: remove `WiFi.h`/`WiFi.mode`; replace `EspNowSetup` with `LinkSetup(this_node)`.
5. `utils.h`: delete `SerialPacketReader` and `SerialForwarder`.
6. Host tests:
   - CRC check value;
   - 10⁶ random-payload stuffing round-trips;
   - embedded `AA 55`; merged and truncated frames;
   - 10⁶ single-bit flips → 0 corrupt frames accepted;
   - routing for every node, including a dummy AUX node.

   Emit golden frames for the Pi tests.

### Phase 4 — Node map, Pi path, commands, relays port
1. `fs_board_config.h`: `VALVE_1`…`VALVE_12` GPIO table (board-map), the provisional function map, `FS_PROVISIONAL_MAP` logic (Section 3.10), and the `ereg-pwr-en` pins.
2. New `nodeconfig.h` (Section 3.1; MACs as `❓` placeholders that fail the build with a clear message until filled in).
3. `main.cpp`: on FsPower only, **immediately after `FindNode`**, drive all 12 `VALVE_*` and both `ereg-pwr-en` LOW, before the existing banner and delays.
4. `DevFsPiPacketBroadcaster`: validated `0xFD` frames from the link layer; ordering, validation and acks per Section 3.4.
5. `DevFsLoxGn2Transducers`: replace Serial1/Serial2/forwarder/`SendToPi` with the shared `SendToPi`. Its receive-and-forward switch is otherwise unchanged.
6. **Approved relays edits:**
   - `RelayPin` values → the provisional VALVE map via `fs_board_config.h` constants, with VALVE_10–12 held LOW;
   - `SendState()` sends on any change of state or outputs, otherwise every 50 ms.
7. `pi/main_fs_pi.py` v1 (FsState, CapFill, FsCommandAck, commands) + tests.
8. Phase 1 goldens still pass. Bench: A2, A3, A4.

### Phase 5 — PT port (ADS131M08, 1953 SPS raw stream)
- Section 3.7 implementation: `PtChannel`, acquisition task, `FsPtsRaw` / `FsPtCal` / `FsPts` / `FsEreg` packets replacing `FsLoxGn2TransducersPacket`.
- **The one approved eReg edit:** `kServoPin` → 42 (`ereg-pwm1`).
- Remove `MovingMedianAdc` / `Adafruit_ADS1X15` / `Adafruit_BusIO`.
- Parser: FsPts, FsEreg, FsPtCal, the raw log, `decode_pt_raw.py`, the legacy records.
- Bench: A5, A6, A6b, A7, A12.

### Phase 6 — TC port (ADS124S08)
Section 3.8. `FsTcsPacket` replaces `FsThermocouplesPacket` on the existing path. Remove `SparkFun_MCP9600_Arduino_Library`. Parser: FsTcs and the legacy `FsThermocouples` record. Bench: A8.

### Phase 7 — Health
`DevFsPowerHealth`:
- INA237 at 0x40, ADCRANGE ±163.84 mV; compute `CURRENT_LSB` and `SHUNT_CAL` from the datasheet for a 40 A maximum.
- Mux scan per Section 3.5; eReg PGOOD interrupts; valve-en readback; link counters.

`DevFsAnalogHealth`: rail ADC sampling, ADC status words, link counters, temperatures.

Parser: both health records. Bench: A9, A10, A11.

### Phase 8 — Integration and acceptance
- Run all of Section 5 with dummy loads.
- Final review of `git diff fs-2025-stable`.
- README: build steps, new-board MAC procedure, add-a-board recipe, node/port table, packet table, Pi 5 setup.

---

## 5. Acceptance tests (Joss runs them; Claude Code writes the procedures in `docs/test-procedures.md`)

| ID | Test | Pass criterion |
|---|---|---|
| A0 | Pi 5 UART at 2 Mbaud (Phase 0, before Phase 4) | GPIO14↔15 jumpered, 10 min of random data at 2 000 000 baud: 0 byte errors. Then the same test ESP↔Pi on the real board. If it fails, retest at 1.5 Mbaud and apply the fallback in Section 3.6 |
| A1 | Host simulation regression | Phase 1 goldens reproduced bit-for-bit |
| A2 | Boot-safe outputs | Scope all 12 valve-en and both ereg-pwr-en through power-on, EN reset, and USB flash + reset: no line ever goes high |
| A3 | Command latency | 100 × ABORT from STANDBY: Pi TX last byte → DEPRESS valve-en high ≤ 20 ms max; eReg PWM at 1500 µs ≤ 30 ms max |
| A4 | Corrupt commands | 1 000 commands with a random single-bit flip: 0 state changes, 0 acks for bad CRCs; 1 000 good commands: 1 000 acks |
| A5 | Link soak | 30 min at full PT rate, solenoids cycling at 1 Hz on dummy loads: 0 CRC errors and 0 seq gaps on the inter-ESP link; 0 lost raw PT samples (`first_sample_index` continuous at the Pi); measured utilization ≤ 60 % on both 2 Mbaud links |
| A6 | PT DC accuracy and calibration | Calibrated 0.500 V and 4.500 V injected at each PT connector → derive `gain_cal` / `offset_cal` per channel. After calibration, error ≤ ±5 mV (±0.125 % of the 4 V span) at 0.5, 2.5 and 4.5 V |
| A6b | PT frequency response and aliasing | 1 V p-p sine into one channel per ADC, swept 10 Hz–3 kHz: measure the −3 dB point and the alias level for 1.0–3.0 kHz inputs. Record the results; no pass/fail, they define the usable band for instability analysis |
| A7 | PT timing | Measured rate 1953 SPS ± 0.1 %; 0 DRDY overruns and 0 SPI CRC errors over 30 min; the eReg loop still runs at 6 ms |
| A8 | TC | After the one-point CJC offset at room temperature: ice bath within ±1.5 °C; LN₂ (−196 °C) within ±3 °C; NIST host-test points within ±0.05 °C; an open TC flagged within 1 s |
| A9 | Health | 5 ms rail-PGOOD pull-low → fall counter increments and a packet arrives ≤ 200 ms; INA237 vs. DMM at a 5 A dummy load within ±2 %; continuity: every channel reads V_bus × 10/110 ± 5 % with the load connected and off, and < 50 mV when open; the eReg IMON pin isn't disturbed by mux switching (scope) |
| A10 | Reset recovery | Reset FsAnalog in STANDBY: FsPower relays unaffected, link recovers ≤ 5 s, framing-error burst visible in counters. Reset FsPower: FsAnalog keeps sampling, reset reason reported |
| A11 | RS-422 link | With a loopback or test node on CAPFILL and on AUX: unplug and replug the cable, data resumes without a reboot, `ms_since_rx` tracks the outage |
| A12 | eReg | Non-provisional build only: CLOSED pulse widths 1500 µs, then 1522 µs after 500 ms (±2 µs); stage behavior on the bench pressure rig matches baseline |

---

## 6. Open items for Joss (Claude Code: do not resolve)

| ID | Item | Needed by | Default |
|---|---|---|---|
| D1 | MAC addresses of FsPower and FsAnalog | Phase 4 hardware bring-up | Build fails with a clear message until filled in |
| D2 | Valve-function map (state-machine chat) | Leaving provisional mode | Provisional identity map, VALVE_1–9 |
| D3 | PT names, ranges (psi_per_volt), eReg upper/lower PTs | Leaving provisional mode | `PT1`…`PT16`, psi_per_volt 0, eReg unassigned |
| D4 | eReg 1 power policy in non-provisional builds | Leaving provisional mode | On at end of FsPower setup, like last year |
| D5 | TC3–6 pin pattern (TCn = AIN(2n−2)/AIN(2n−1)) and TC names | Phase 6 | Pattern as stated; names `TC1`…`TC6` |
| D6 | Are `24V-pwr-pgood`, `12V-pwr-pgood`, `12V-digital-pgood` resistor dividers off their rails (values?) or regulator PG outputs? | Phase 7 | Report pin mV and logic state; `rail_est_mv = 0` |
| D7 | Pull-down on `ereg-pwr-en`; pull-ups on `ereg-pgood1/2` | Phase 4 | Must be confirmed from the schematic; boot test A2 checks |
| D8 | Is the continuity divider on the low-side switched node (so it reads 0 V when the channel is on)? | Phase 7 | Pi interprets continuity only while that channel is off |
| D9 | Is AUX (uart2) also behind a MAX3490? | Phase 3 | Yes, 921600 |
| D10 | New cap-fill board: MAC, UART pins, sensor pins (protected-file pin edit) | When the board exists | Link and node entry ready; DevCapFill unchanged |
| D11 | 1953 SPS vs. 1221 SPS | Phase 5 | 1953 SPS (one constant to change) |
