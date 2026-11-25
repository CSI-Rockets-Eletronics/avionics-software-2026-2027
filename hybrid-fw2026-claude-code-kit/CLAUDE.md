# Firing Station Firmware — 2026

## What this repo is
One ESP-IDF firmware image runs on every ESP32-S3 in the firing station system. It uses ESP-IDF **5.1.5** with
arduino-esp32 **3.0.7** as an IDF component; both are pinned in `dependencies.lock`.
- At boot each chip reads its MAC, looks itself up in `main/devices/nodeconfig.h`, and runs only that node's `Device`s.
- Each `Device` has `Setup()` + `Loop()` on its own FreeRTOS task.
- Devices talk with `Send(DeviceType, packet)` and `Receive(&a, &b, ...)`. Receive matches incoming messages **by size**, so packet sizes must be unique within each `Receive` call.

This year is an **improvement pass on last year's flown code, not a rewrite**. The repo is easy to read and debug, and it must stay that way. Read before doing anything:
- `docs/FW2026_PLAN.md`: plan, wire protocol, phases, acceptance tests, open items.
- `docs/board-map.md`: pins and hardware facts.
- `docs/state-regression.md`: baseline relay and eReg behavior.

System this year: two ESPs on one board (down from three boards).
- **FsPower** (U13): DevFsRelays, DevFsPiPacketBroadcaster (Pi link and command fan-out), DevFsPowerHealth (new).
- **FsAnalog** (U12): DevFsLoxGn2Transducers (now all 16 PTs on 2× ADS131M08 at 1953 SPS; it keeps its class name), DevEregControl, DevFsThermocouples (now ADS124S08), DevFsAnalogHealth (new).
- **CapFill**: a new board, its hardware port deferred. It links to FsAnalog over RS-422. **AUX**: an RS-422 port reserved for future boards.
- **All links are UART:** Pi↔FsPower and FsPower↔FsAnalog at 2 Mbaud; RS-422 ports at 921600. No Wi-Fi, ESP-NOW, Bluetooth or OTA anywhere.

## Baseline
- Tag `fs-2025-stable` = `main` @ `d71c5cb`. Work on branch `fs-2026`, with one branch per phase off it.
- Every change must be reviewable with `git diff fs-2025-stable`.
- Do not upgrade ESP-IDF, arduino-esp32, or any managed component. Do not run `idf.py update-dependencies`.

## Prime directive: minimal, reviewable change
1. Change only what the current phase requires. No drive-by refactors, renames, reformatting, `.clang-format` runs on untouched files, or cleanup outside the phase.
2. Keep the architecture: `Device` / `Node` / `REGISTER_AVIONICS_DEVICE`, `Send()` / `Receive()`, packed structs in `packets.h`, one image selected by MAC. The transport under `Send()` changes; the API devices call does not.
3. **The state machine is parked** (Joss will handle it in a separate session). Do not change relay logic, sequence timing, valve function assignments, or ABORT/CUSTOM behavior, even where it looks wrong. Note concerns in your phase report instead.
4. **Protected files** (a PreToolUse hook blocks edits):
   - `main/devices/dev_cap_fill.h`: no edits.
   - `main/devices/dev_ereg_control.h`: **one** pre-approved edit only: `kServoPin` 9 → 42 (`ereg-pwm1`), in Phase 5.
   - `main/devices/dev_fs_relays.h`: pre-approved edits only, in Phase 4:
     - (a) `RelayPin` values → constants from `fs_board_config.h` (the provisional VALVE map);
     - (b) rate-limit `SendState()`: on change, otherwise every 50 ms.

   For anything else in these files: STOP and ask.
5. Do not change any `FsCommand` / `FsState` numeric values, `FsCommandPacket` (10 B), `FsStatePacket` (14 B), `CapFillPacket` (17 B), or `EregStateData`.
6. No new autonomous behavior: no state transitions, actuating timeouts, auto-abort or link-loss actions. Report conditions in telemetry.

## Safety rules (non-negotiable)
- On FsPower, all 12 `VALVE_*` GPIOs and both `ereg-pwr-en` GPIOs are driven LOW **immediately after node identification**, before any banner, delay, or device `Setup()`. Never drive a GPIO before the node is identified: the same GPIO number means something different on the other ESP.
- Never use strapping pins (GPIO0, 3, 45, 46).
- **Provisional builds** (`FS_PROVISIONAL_MAP`, plan Section 3.10) must never drive `ereg-pwr-en` high, must print the boot banner, and must set the health `flags` bit. Never remove the provisional guard yourself; only Joss fills in the maps.
- Any change touching the igniter path, valve enables, eReg PWM or power, or the command → actuation path: STOP, explain, wait for approval.
- A frame that fails stuffing, length or CRC validation causes **no** state change and no ack.
- Transport TX **never blocks** a device `Loop()` or the PT acquisition task. If the frame doesn't fit, drop it and count it.
- Never run `idf.py flash`, `monitor`, or anything that opens a serial port. Joss flashes hardware. Build only.

## How to work
- Plan mode at the start of every phase; present the plan and wait for approval.
- Branch per phase: `fs-2026/pN-<name>`. One logical change per commit.
- After every change, `idf.py build` must pass with no new warnings vs. `docs/baseline.md`.
- At the end of every phase, report:
  - `git diff --stat fs-2025-stable`
  - `git diff fs-2025-stable -- main/devices/dev_cap_fill.h` (must be empty) and the diffs of the other two protected files (approved edits only)
  - flash/RAM size change (`idf.py size`)
  - host test results (including the Phase 1 relay goldens)
  - the exact bench checks Joss must run
- Drivers (ADS131M08, ADS124S08, INA237): every register address, field and conversion constant gets a comment citing the datasheet section or table in `docs/datasheets/`. Never write register values from memory. If a datasheet is missing, stop and ask for it.
- Pins and hardware constants come only from `docs/board-map.md`. A ❓ there means stop and ask.
- Wire structs: inside `#pragma pack(push, 1)` with `static_assert(sizeof(T) == N)` for each one.
- Match the repo's existing style: Arduino API, `Serial.print` debug output, header-only devices in `main/devices/`. New code should look like the code next to it.

## Stop and ask when
- A protected file would need an edit outside the list above.
- The schematic, `docs/board-map.md` and the code disagree.
- Baseline behavior is ambiguous; `docs/state-regression.md` and the Phase 1 harness are the reference.
- A datasheet value, register or pin can't be verified from a file in the repo.
- A requirement in the plan conflicts with this file.
