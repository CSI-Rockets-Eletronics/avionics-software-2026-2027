# Raspberry Pi 5 Setup for Firing Station Telemetry

This document describes the Pi 5 configuration for the FW2026 firing station system.

## Hardware Configuration

### UART Setup

The Pi 5 uses GPIO14 (TXD) and GPIO15 (RXD) on the 40-pin header for serial communication with the FsPower ESP32.

**Pin connections:**
- GPIO14 (TXD, pin 8) → FsPower RX (IO15)
- GPIO15 (RXD, pin 10) → FsPower TX (IO7)
- GND (pin 6, 9, 14, 20, 25, 30, 34, or 39) → Board GND

### config.txt Configuration

Edit `/boot/firmware/config.txt` (or `/boot/config.txt` on older Pi OS versions) and add:

```
# Enable UART0 on GPIO14/15
dtparam=uart0=on
```

**Important:** Ensure the serial console is **disabled** on this UART. Check `/boot/firmware/cmdline.txt` and remove any `console=serial0,115200` or similar entries.

After editing, reboot:
```bash
sudo reboot
```

After reboot, verify the UART device exists:
```bash
ls -l /dev/ttyAMA0
```

You should see:
```
crw-rw---- 1 root dialout 204, 64 <date> /dev/ttyAMA0
```

Add your user to the `dialout` group to access serial ports without sudo:
```bash
sudo usermod -a -G dialout $USER
```

Log out and back in for the group change to take effect.

## A0: 2 Mbaud Loopback Test

**Purpose:** Verify that the Raspberry Pi 5 UART can reliably operate at 2,000,000 baud before connecting to the ESP32 hardware.

**When to run:** Before Phase 4, after Pi 5 UART configuration is complete.

**Pass criterion:** 10 minutes of continuous random data transmission with 0 byte errors.

### Test Procedure

#### 1. Pi-only loopback test

**Hardware setup:**
- Jumper GPIO14 to GPIO15 on the Pi 5 header (pin 8 to pin 10)
- Or use a jumper wire between TXD and RXD on a breakout board

**Software test:**

Install Python serial library if not already present:
```bash
pip3 install pyserial
```

Create test script `test_loopback.py`:
```python
#!/usr/bin/env python3
import serial
import random
import time
import sys

BAUD = 2000000
PORT = '/dev/ttyAMA0'
TEST_DURATION_SEC = 600  # 10 minutes
CHUNK_SIZE = 1024

def test_loopback(duration_sec):
    errors = 0
    bytes_sent = 0

    print(f"Opening {PORT} at {BAUD} baud...")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(0.1)  # Let port settle
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print(f"Starting {duration_sec}s loopback test...")
    start_time = time.time()

    try:
        while time.time() - start_time < duration_sec:
            # Generate random data
            tx_data = bytes([random.randint(0, 255) for _ in range(CHUNK_SIZE)])

            # Send
            ser.write(tx_data)
            bytes_sent += len(tx_data)

            # Receive (blocking with timeout)
            rx_data = ser.read(CHUNK_SIZE)

            if len(rx_data) != len(tx_data):
                errors += 1
                print(f"ERROR: Length mismatch. Sent {len(tx_data)}, received {len(rx_data)}")
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                continue

            # Compare
            if rx_data != tx_data:
                for i, (tx_byte, rx_byte) in enumerate(zip(tx_data, rx_data)):
                    if tx_byte != rx_byte:
                        errors += 1
                        print(f"ERROR at byte {bytes_sent - CHUNK_SIZE + i}: sent 0x{tx_byte:02X}, got 0x{rx_byte:02X}")

            # Progress
            if bytes_sent % (CHUNK_SIZE * 100) == 0:
                elapsed = time.time() - start_time
                print(f"  {elapsed:.1f}s: {bytes_sent} bytes, {errors} errors")

    except KeyboardInterrupt:
        print("\nTest interrupted by user")

    finally:
        ser.close()

    elapsed = time.time() - start_time
    print(f"\nTest complete:")
    print(f"  Duration: {elapsed:.1f} seconds")
    print(f"  Bytes transferred: {bytes_sent}")
    print(f"  Errors: {errors}")
    print(f"  Result: {'PASS' if errors == 0 else 'FAIL'}")

    return errors == 0

if __name__ == '__main__':
    success = test_loopback(TEST_DURATION_SEC)
    sys.exit(0 if success else 1)
```

Run the test:
```bash
chmod +x test_loopback.py
./test_loopback.py
```

**Expected output:**
```
Opening /dev/ttyAMA0 at 2000000 baud...
Starting 600s loopback test...
  10.0s: 1024000 bytes, 0 errors
  20.1s: 2048000 bytes, 0 errors
  ...
  600.0s: 61440000 bytes, 0 errors

Test complete:
  Duration: 600.0 seconds
  Bytes transferred: 61440000
  Errors: 0
  Result: PASS
```

#### 2. ESP32-to-Pi loopback test

**When:** After Pi-only test passes and FsPower board is available (Phase 4+).

**Hardware setup:**
- Connect Pi GPIO14 → FsPower IO15 (RX)
- Connect Pi GPIO15 ← FsPower IO7 (TX)
- Connect GND between Pi and board
- Power the FsPower board

**Firmware setup:**
- Flash FsPower with Phase 4+ firmware
- The ESP32 should echo data received on its PI UART port

**Test:**
Run the same `test_loopback.py` script. The data path is now:
```
Pi TX → ESP RX → ESP TX → Pi RX
```

**Pass criterion:** 0 errors over 10 minutes.

**If the test fails:**
1. Verify wiring and GND connection
2. Check for electrical noise or signal integrity issues
3. Try reducing baud rate to 1,500,000 and retest
4. If 1.5 Mbaud passes but 2 Mbaud fails, apply the fallback in FW2026_PLAN.md Section 3.6:
   - Change PT sample rate from 1953 SPS to 1221 SPS (adjust `kPtClkDiv` in `fs_board_config.h`)
   - Update parser and all documentation to reflect the reduced rate

## Uploader Configuration

The uploader script (`main_fs_pi.py`) uses the following settings:

**Serial port:** `/dev/ttyAMA0`
**Baud rate:** `2000000` (or `1500000` if fallback is needed)
**Frame delimiter:** `AA 55` (unchanged from FW2025)

### Uploader Baud Setting

The baud rate is a parameter that Joss can change without editing the uploader code. It is passed when calling `uploader.run()`:

```python
# In main_fs_pi.py
BAUD_RATE = 2000000  # <-- Change this line to adjust baud

uploader.run(
    delimiter=b'\xAA\x55',
    parse_packet=parse_packet,
    format_message={'FiringStation': format_message},
    port='/dev/ttyAMA0',
    baud=BAUD_RATE  # <-- Passed to uploader
)
```

No other code changes are needed to adjust the baud rate.

## Verifying uploader.py Behaviors (Phase 0 Step 5)

Before proceeding with Phase 4, verify that `uploader.py` exhibits these behaviors:

**(a) Splits only on the passed delimiter**
- The uploader must split the incoming byte stream only on the delimiter (`AA 55`), not on any other byte pattern.

**(b) Passes chunks without the delimiter**
- When calling `parse_packet(chunk)`, the delimiter bytes must already be stripped from `chunk`.

**(c) Tolerates `parse_packet` returning None**
- If `parse_packet()` returns `None` (e.g., for high-rate PT data written directly to disk), the uploader must continue processing without error.

**(d) Writes `format_message` bytes verbatim**
- When sending commands, the bytes returned by `format_message()` must be written to the serial port exactly as-is, with no added framing or modification.

**(e) Takes baud rate from a changeable setting**
- The baud rate must be configurable via a parameter or setting that Joss can change, as shown above.

**Action:** Read `docs/reference/uploader.py` when provided by Joss and confirm all five behaviors. If any are false, **STOP** and report the issue.

## Directory Structure

```
pi/
├── README.md                 # This file
├── main_fs_pi.py             # Main parser/formatter (to be written in Phase 4+)
├── decode_pt_raw.py          # Raw PT log decoder (to be written in Phase 5)
├── test_main_fs_pi.py        # Parser unit tests (to be written in Phase 4+)
├── test_loopback.py          # A0 loopback test script (above)
└── logs/
    ├── pt_raw_*.bin          # High-rate PT binary logs (auto-generated)
    └── telemetry_*.csv       # Parsed telemetry records (auto-generated)
```

## Notes

- The Pi 5's UART0 is capable of non-standard baud rates like 2,000,000
- If using a Pi 4 or older, verify UART capabilities; some may require different configuration
- The VPU (video core) clock must be stable for accurate baud rates; this is default on Pi 5
- For troubleshooting serial issues, use `sudo minicom -D /dev/ttyAMA0 -b 2000000` for manual testing
