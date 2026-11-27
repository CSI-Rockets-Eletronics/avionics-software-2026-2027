# Baseline Build — fs-2025-stable

Baseline snapshot for FW2026 improvement pass. All changes will be compared against this baseline.

## Repository State

**Baseline commit:** `d71c5cb` ("Change the calibration for oxtank 1")
**Tag:** `fs-2025-stable` (note: currently points to `46c6415`, may need retag)
**Branch:** `main`

## Build Environment

**ESP-IDF Version:** _(to be filled after build)_
**arduino-esp32 Version:** _(to be filled after build)_
**Build Date:** _(to be filled)_

## Submodule Status

```
(Run: git submodule status)

-c834224b91781947453ca653c45c20d9950592ac components/Adafruit_ADS1X15/Adafruit_ADS1X15
-055013b58dab9c3f1e016c75aac6eafb58e8d789 components/Adafruit_BusIO/Adafruit_BusIO
-f7bff30a018753caf48ebd3a87e32baca88137e6 components/Adafruit_GPS/Adafruit_GPS
-0a9127a1e886ff1adb4c1b6f5958b24108d55aa6 components/Adafruit_Sensor/Adafruit_Sensor
-2295fe471c38d5e649a7b68cecccc42193c8e41c components/DHT-sensor-library/DHT-sensor-library
-e697ea76b8c45e18ff3a5f636640c9a15c593d12 components/ESP32Servo/ESP32Servo
-589178cf41264d6c0e485e9049945c9b2c73f22f components/FDC2214/FDC2214
-63cbc35437ce4680b45d0526bad19e3b3bfa6fcd components/MPU9255-Arduino-Library/MPU9255-Arduino-Library
-90993e3f25fa53e78311ed9c86baf5b1a491dfee components/RadioHead/RadioHead
-399d721629fc5f10fc8a02883ba9206c3a46a584 components/SparkFun_MCP9600_Arduino_Library/SparkFun_MCP9600_Arduino_Library
```

## Build Output

### Warning Count

_(To be filled after running: idf.py build 2>&1 | grep -c "warning:")_

**Baseline warning count:** _(number)_

### Flash and RAM Usage

_(To be filled after running: idf.py size)_

```
(Paste idf.py size output here)
```

Expected output format:
```
Total sizes:
Used stat D/IRAM:   XXXXX bytes
      .flash.text:  XXXXX bytes
    .flash.rodata:  XXXXX bytes
         .dram0.bss:  XXXXX bytes
        .dram0.data:  XXXXX bytes
```

## Build Procedure

1. Ensure ESP-IDF 5.1.5 environment is activated
2. If `main/include/ota_version.h` is missing, run:
   ```bash
   ./deploy_ota.sh  # (run only the ota_version.h generation step)
   ```
3. Build:
   ```bash
   idf.py build
   ```
4. Record warnings and size output in this file

## Phase 0 Status

### Completed
- ✅ Tag and submodule verification
- ✅ README IDF version corrected (5.5 → 5.1.5)
- ✅ PreToolUse hook configured to protect files per CLAUDE.md
- ✅ Baseline documentation template created

### Waiting on Joss
- ⏳ `docs/reference/uploader.py` - needed to verify behaviors (a)-(e) per Phase 0 step 5
- ⏳ Schematic PDF for board-map verification

## Notes

- Dependencies are pinned in `dependencies.lock`
- arduino-esp32 3.0.7 as IDF component
- No IDF or component upgrades during FW2026 pass
- Do not run `idf.py update-dependencies`
- Tag `fs-2025-stable` currently points to `46c6415` but baseline commit is `d71c5cb` - may need retag
