import struct
from enum import Enum
from typing import Any

import uploader
from utils import MovingMedianFilter

delimiter = b"\xaa\x55"  # {0b10101010, 0b01010101}


# values must be between 0 and 255 (1 byte)
class FsCommands(Enum):
    STATE_CUSTOM = 0
    STATE_ABORT = 1
    STATE_STANDBY = 2
    STATE_GN2_STANDBY = 3
    STATE_GN2_FILL = 10
    STATE_GN2_PULSE_FILL_A = 11
    STATE_GN2_PULSE_FILL_B = 12
    STATE_GN2_PULSE_FILL_C = 13
    STATE_ENGINE_PRIME = 19
    STATE_FIRE = 20
    STATE_FIRE_MANUAL_PRESS_PILOT = 21
    STATE_FIRE_MANUAL_DOME_PILOT_CLOSE = 22
    STATE_FIRE_MANUAL_IGNITER = 23
    STATE_FIRE_MANUAL_RUN = 24
    EREG_CLOSED = 30
    EREG_STAGE_1 = 31
    EREG_STAGE_2 = 32
    RECALIBRATE_TRANSDUCERS = 100
    RESTART = 110


class FsState(Enum):
    CUSTOM = 0
    ABORT = 1
    STANDBY = 2
    GN2_STANDBY = 3
    GN2_FILL = 10
    GN2_PULSE_FILL_A = 11
    GN2_PULSE_FILL_B = 12
    GN2_PULSE_FILL_C = 13
    ENGINE_PRIME = 19
    FIRE = 20
    FIRE_MANUAL_PRESS_PILOT = 21
    FIRE_MANUAL_DOME_PILOT_CLOSE = 22
    FIRE_MANUAL_IGNITER = 23
    FIRE_MANUAL_RUN = 24


window_size = 30

oxtank_1_filter = MovingMedianFilter(window_size)
oxtank_2_filter = MovingMedianFilter(window_size)
copv_1_filter = MovingMedianFilter(window_size)
copv_2_filter = MovingMedianFilter(window_size)
pilot_pres_filter = MovingMedianFilter(window_size)
qd_pres_filter = MovingMedianFilter(window_size)
injector_1_filter = MovingMedianFilter(window_size)
injector_2_filter = MovingMedianFilter(window_size)
upper_cc_filter = MovingMedianFilter(window_size)


def parse_packet(packet: bytes):
    # struct FsStatePacket {
    #     uint32_t ms_since_boot;  // 4 bytes
    #     FsState state;           // 1 byte
    #     bool gn2_drain;          // 1 byte
    #     bool gn2_fill;           // 1 byte
    #     bool depress;            // 1 byte
    #     bool press_pilot;        // 1 byte
    #     bool run;                // 1 byte
    #     bool lox_fill;           // 1 byte
    #     bool lox_disconnect;     // 1 byte
    #     bool igniter;            // 1 byte
    #     bool igniter_backup;     // 1 byte
    # };  // size: 14 bytes
    if len(packet) == 14:
        # Breakdown of "<IBBBBBBBBBB":
        #   "<": little-endian
        #   "I": uint32_t (4 bytes)
        #   "B": uint8_t / bool (1 byte each, 10 total)
        (
            ms_since_boot,
            state,
            gn2_drain,
            gn2_fill,
            depress,
            press_pilot,
            run,
            lox_fill,
            lox_disconnect,
            igniter,
            igniter_backup,
        ) = struct.unpack("<IBBBBBBBBBB", packet)
        data = {
            "ms_since_boot": ms_since_boot,
            "state": FsState(state).name,
            "gn2_drain": bool(gn2_drain),
            "gn2_fill": bool(gn2_fill),
            "depress": bool(depress),
            "press_pilot": bool(press_pilot),
            "run": bool(run),
            "lox_fill": bool(lox_fill),
            "lox_disconnect": bool(lox_disconnect),
            "igniter": bool(igniter),
            "igniter_backup": bool(igniter_backup),
        }
        return uploader.Record("FsState", data)

    # struct FsLoxGn2TransducersPacket {
    #     uint64_t ts;           // 8 bytes
    #     float oxtank_1;        // 4 bytes
    #     float oxtank_2;        // 4 bytes
    #     float copv_1;          // 4 bytes
    #     float copv_2;          // 4 bytes
    #     float pilot_pres;      // 4 bytes
    #     float qd_pres;         // 4 bytes
    #     bool ereg_closed;      // 1 byte
    #     bool ereg_stage_1;     // 1 byte
    #     bool ereg_stage_2;     // 1 byte
    #     float current_angle;   // 4 bytes
    #     float p_cont;          // 4 bytes
    #     float i_cont;          // 4 bytes
    #     float d_cont;          // 4 bytes
    # };  // size: 51 bytes
    if len(packet) == 51:
        # Breakdown of "<QffffffBBBffff":
        #   "<": little-endian
        #   "Q": uint64_t (8 bytes)
        #   "f": float (4 bytes each, 6 total)
        #   "B": uint8_t / bool (1 byte each, 3 total)
        #   "f": float (4 bytes each, 4 total)
        (
            ts,
            oxtank_1,
            oxtank_2,
            copv_1,
            copv_2,
            pilot_pres,
            qd_pres,
            ereg_closed,
            ereg_stage_1,
            ereg_stage_2,
            current_angle,
            p_cont,
            i_cont,
            d_cont,
        ) = struct.unpack("<QffffffBBBffff", packet)
        data = {
            "ts": ts,
            "oxtank_1": oxtank_1,
            "oxtank_2": oxtank_2,
            "copv_1": copv_1,
            "copv_2": copv_2,
            "pilot_pres": pilot_pres,
            "qd_pres": qd_pres,
            "ereg_closed": bool(ereg_closed),
            "ereg_stage_1": bool(ereg_stage_1),
            "ereg_stage_2": bool(ereg_stage_2),
            "current_angle": current_angle,
            "p_cont": p_cont,
            "i_cont": i_cont,
            "d_cont": d_cont,
            "oxtank_1_median": oxtank_1_filter.add(oxtank_1).median(),
            "oxtank_2_median": oxtank_2_filter.add(oxtank_2).median(),
            "copv_1_median": copv_1_filter.add(copv_1).median(),
            "copv_2_median": copv_2_filter.add(copv_2).median(),
            "pilot_pres_median": pilot_pres_filter.add(pilot_pres).median(),
            "qd_pres_median": qd_pres_filter.add(qd_pres).median(),
        }
        return uploader.Record("FsLoxGn2Transducers", data)

    # struct FsInjectorTransducersPacket {
    #     uint64_t ts;                // 8 bytes
    #     float injector_1;           // 4 bytes
    #     float injector_2;           // 4 bytes
    #     float upper_cc;             // 4 bytes
    # };  // size: 20 bytes
    if len(packet) == 20:
        # Breakdown of "<Qfff":
        #   "<": little-endian
        #   "Q": uint64_t (8 bytes)
        #   "f": float (4 bytes each, 3 total)
        ts, injector_1, injector_2, upper_cc = struct.unpack("<Qfff", packet)
        data = {
            "ts": ts,
            "injector_1": injector_1,
            "injector_2": injector_2,
            "upper_cc": upper_cc,
            "injector_1_median": injector_1_filter.add(injector_1).median(),
            "injector_2_median": injector_2_filter.add(injector_2).median(),
            "upper_cc_median": upper_cc_filter.add(upper_cc).median(),
        }
        return uploader.Record("FsInjectorTransducers", data)

    # struct FsThermocouplesPacket {
    #     uint64_t ts;                   // 8 bytes
    #     float gn2_internal_celsius;    // 4 bytes
    #     float gn2_external_celsius;    // 4 bytes
    #     float lox_upper_celsius;       // 4 bytes
    #     float lox_lower_celsius;       // 4 bytes
    #     uint8_t dummy;                 // 1 byte (for unique packet size)
    # };  // size: 25 bytes
    if len(packet) == 25:
        # Breakdown of "<QffffB":
        #   "<": little-endian
        #   "Q": uint64_t (8 bytes)
        #   "f": float (4 bytes each, 4 total)
        #   "B": uint8_t (1 byte, dummy)
        (
            ts,
            gn2_internal_celsius,
            gn2_external_celsius,
            lox_upper_celsius,
            lox_lower_celsius,
            _dummy,
        ) = struct.unpack("<QffffB", packet)
        data = {
            "ts": ts,
            "gn2_internal_celsius": gn2_internal_celsius,
            "gn2_external_celsius": gn2_external_celsius,
            "lox_upper_celsius": lox_upper_celsius,
            "lox_lower_celsius": lox_lower_celsius,
        }
        return uploader.Record("FsThermocouples", data)

    # struct CapFillPacket {
    #     uint64_t ts;            // 8 bytes
    #     float cap_fill_base;    // 4 bytes
    #     float cap_fill_actual;  // 4 bytes
    #     int8_t board_temp;      // 1 byte
    # };  // size: 17 bytes
    if len(packet) == 17:
        # Breakdown of "<Qffb":
        #   "<": little-endian
        #   "Q": uint64_t (8 bytes)
        #   "f": float (4 bytes each, 2 total)
        #   "b": int8_t (1 byte)
        ts, cap_fill_base, cap_fill_actual, board_temp = struct.unpack("<Qffb", packet)
        data = {
            "ts": ts,
            "cap_fill_base": cap_fill_base,
            "cap_fill_actual": cap_fill_actual,
            "board_temp": board_temp,
        }
        return uploader.Record("CapFill", data)

    # struct RelayCurrentMonitorPacket {
    #     uint64_t ts;                // 8 bytes
    #     int16_t gn2_drain_ma;       // 2 bytes
    #     int16_t gn2_fill_ma;        // 2 bytes
    #     int16_t depress_ma;         // 2 bytes
    #     int16_t press_pilot_ma;     // 2 bytes
    #     int16_t run_ma;             // 2 bytes
    #     int16_t lox_fill_ma;        // 2 bytes
    #     int16_t lox_disconnect_ma;  // 2 bytes
    #     int16_t igniter_ma;         // 2 bytes
    #     int16_t igniter_backup_ma;  // 2 bytes
    # };  // size: 26 bytes
    if len(packet) == 26:
        # Breakdown of "<Qhhhhhhhhh":
        #   "<": little-endian
        #   "Q": uint64_t (8 bytes)
        #   "h": int16_t (2 bytes each, 9 total)
        (
            ts,
            gn2_drain_ma,
            gn2_fill_ma,
            depress_ma,
            press_pilot_ma,
            run_ma,
            lox_fill_ma,
            lox_disconnect_ma,
            igniter_ma,
            igniter_backup_ma,
        ) = struct.unpack("<Qhhhhhhhhh", packet)
        data = {
            "ts": ts,
            "gn2_drain_ma": gn2_drain_ma,
            "gn2_fill_ma": gn2_fill_ma,
            "depress_ma": depress_ma,
            "press_pilot_ma": press_pilot_ma,
            "run_ma": run_ma,
            "lox_fill_ma": lox_fill_ma,
            "lox_disconnect_ma": lox_disconnect_ma,
            "igniter_ma": igniter_ma,
            "igniter_backup_ma": igniter_backup_ma,
        }
        return uploader.Record("RelayCurrentMonitor", data)


def format_message(message: Any):
    command = message["command"]
    assert isinstance(command, str)

    try:
        command_value = FsCommands[command].value
    except KeyError:
        raise ValueError(f"Invalid command: {command}")

    # solenoid states (only used if command is STATE_CUSTOM)
    gn2_drain = False
    gn2_fill = False
    depress = False
    press_pilot = False
    run = False
    lox_fill = False
    lox_disconnect = False
    igniter = False
    igniter_backup = False

    if command_value == FsCommands.STATE_CUSTOM.value:
        gn2_drain = message["gn2_drain"]
        gn2_fill = message["gn2_fill"]
        depress = message["depress"]
        press_pilot = message["press_pilot"]
        run = message["run"]
        lox_fill = message["lox_fill"]
        lox_disconnect = message["lox_disconnect"]
        igniter = message["igniter"]
        igniter_backup = message["igniter_backup"]

    command_bytes = struct.pack(
        "<BBBBBBBBBB",  # 10 bytes
        command_value,
        gn2_drain,
        gn2_fill,
        depress,
        press_pilot,
        run,
        lox_fill,
        lox_disconnect,
        igniter,
        igniter_backup,
    )

    return command_bytes + delimiter

uploader.run(delimiter, parse_packet, {"FiringStation": format_message})
