#!/usr/bin/env python3
"""
Test script to send FsCommandPacket to FsScientific1 via serial.
This simulates the Raspberry Pi sending commands.

Usage:
    python test_send_command.py <COM_PORT> <COMMAND_NUMBER>

Example:
    python test_send_command.py COM8 STATE_STANDBY   # by name (preferred)
    python test_send_command.py COM8 2               # by number (STATE_STANDBY)
    python test_send_command.py COM8 RESTART --baud 115200

The serial link to the Pi (Serial2, pins RX=18 / TX=8) runs at 230400 baud,
which is the default here. Numbers must match FsCommand in main/include/packets.h.
"""

import serial
import struct
import sys
import time

# FsCommand enum values (must match enum class FsCommand in main/include/packets.h)
FS_COMMANDS = {
    "STATE_CUSTOM": 0,
    "STATE_ABORT": 1,
    "STATE_STANDBY": 2,
    "STATE_GN2_STANDBY": 3,
    "STATE_GN2_FILL": 10,
    "STATE_GN2_PULSE_FILL_A": 11,
    "STATE_GN2_PULSE_FILL_B": 12,
    "STATE_GN2_PULSE_FILL_C": 13,
    "STATE_ENGINE_PRIME": 19,
    "STATE_FIRE": 20,
    "STATE_FIRE_MANUAL_PRESS_PILOT": 21,
    "STATE_FIRE_MANUAL_DOME_PILOT_CLOSE": 22,
    "STATE_FIRE_MANUAL_IGNITER": 23,
    "STATE_FIRE_MANUAL_RUN": 24,
    "EREG_CLOSED": 30,
    "EREG_STAGE_1": 31,
    "EREG_STAGE_2": 32,
    "RECALIBRATE_TRANSDUCERS": 100,
    "RESTART": 110,
}

# Packet delimiters (must match utils.h)
PACKET_DELIMITER_1 = 0b10101010
PACKET_DELIMITER_2 = 0b01010101

def create_fs_command_packet(command_value):
    """
    Create an FsCommandPacket.

    Structure (from packets.h with #pragma pack(push, 1)):
        FsCommand command;  // uint8_t (1 byte, enum class FsCommand : uint8_t)
        bool gn2_drain, gn2_fill, depress, press_pilot, run;  // 5 bytes
        bool lox_fill, lox_disconnect, igniter, igniter_backup;   // 4 bytes

    Total: 1 byte (command) + 9 bytes (bools) = 10 bytes
    """
    # Pack as: 10 uint8_t values (B = unsigned char = 1 byte each)
    # Format: '<10B' means little-endian, 10 unsigned bytes
    packet = struct.pack('<10B',
        command_value,  # command (uint8_t, not uint32_t!)
        0, 0, 0, 0, 0,  # gn2_drain, gn2_fill, depress, press_pilot, run (all false)
        0, 0, 0, 0      # lox_fill, lox_disconnect, igniter, igniter_backup (all false)
    )
    return packet

def send_command(port, command_value, baud=230400):
    """Send FsCommandPacket to ESP32 via serial."""
    try:
        # Open serial port
        ser = serial.Serial(port, baud, timeout=1)
        print(f"Opened serial port {port} at {baud} baud")
        time.sleep(0.1)  # Wait for connection to stabilize

        # Create packet
        packet = create_fs_command_packet(command_value)

        # Add delimiters
        full_packet = packet + bytes([PACKET_DELIMITER_1, PACKET_DELIMITER_2])

        # Send packet
        print(f"Sending FsCommandPacket:")
        print(f"  Command value: {command_value}")
        print(f"  Packet size: {len(packet)} bytes")
        print(f"  Full size (with delimiters): {len(full_packet)} bytes")
        print(f"  Hex: {full_packet.hex()}")

        ser.write(full_packet)
        ser.flush()

        print("Command sent successfully!")

        # Wait a moment and show any response
        time.sleep(0.5)
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"Response: {response}")

        ser.close()

    except serial.SerialException as e:
        print(f"Serial error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_send_command.py <COM_PORT> <COMMAND>")
        print("\nAvailable commands:")
        for name, value in sorted(FS_COMMANDS.items(), key=lambda x: x[1]):
            print(f"  {value:2d} - {name}")
        sys.exit(1)

    port = sys.argv[1]

    baud = 230400
    if "--baud" in sys.argv:
        baud = int(sys.argv[sys.argv.index("--baud") + 1])

    # Parse command (accept number or name)
    command_arg = sys.argv[2]
    if command_arg.isdigit():
        command_value = int(command_arg)
        # Find command name for display
        command_name = next((name for name, val in FS_COMMANDS.items() if val == command_value), None)
        if command_name is None:
            print(f"Error: {command_value} is not a valid FsCommand number")
            sys.exit(1)
    else:
        command_name = command_arg.upper()
        if command_name not in FS_COMMANDS:
            print(f"Error: Unknown command '{command_arg}'")
            print("\nAvailable commands:")
            for name, value in sorted(FS_COMMANDS.items(), key=lambda x: x[1]):
                print(f"  {value:2d} - {name}")
            sys.exit(1)
        command_value = FS_COMMANDS[command_name]

    print(f"Sending command: {command_name} (value={command_value})")
    send_command(port, command_value, baud)

if __name__ == "__main__":
    main()
