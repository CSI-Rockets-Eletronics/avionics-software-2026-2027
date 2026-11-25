# Golden Behavior — DevFsRelays + DevEregControl (baseline)

Derived by reading `main/devices/dev_fs_relays.h` and `main/devices/dev_ereg_control.h` at the
baseline tag `fs-2025-stable` = `main` @ `d71c5cb`. Both files are identical to the May flight commit
`35b38b6`. This table was **read from the code, not measured on hardware**. Phase 1's host simulation
test must reproduce it from the baseline source, and this year's code must then produce identical results.

**Scope:** this file is a regression reference for the comms rework only. The state machine is parked for
a separate session with Joss. Nothing described here is to be "fixed" in this pass, even where it looks
wrong.

Output vector order: `gn2_drain, gn2_fill, depress, press_pilot, run, lox_fill, lox_disconnect, igniter, igniter_backup`.
`t` = ms since the state was entered by a command (`enter_state_ms`). Automatic transitions do **not**
reset `enter_state_ms`.

## Relays

**Manual overrides.** `manual_gn2_drain`, `manual_gn2_fill`, `manual_lox_fill` and
`manual_lox_disconnect` are latched from the most recent `STATE_CUSTOM` packet. They are OR-ed into
the outputs in **every** non-CUSTOM state, including ABORT, on the baseline. (Unmerged branch
`fix/abort-clears-manual-overrides` would change this. It's parked for the state-machine session; do not merge it.)

**Depress pulse.** In the pulse states (`GN2_STANDBY`, `GN2_FILL`, `GN2_PULSE_FILL_A/B/C`):
`depress = ((now − enter_depress_pulse_ms) mod 10000) < 1000`, i.e. open 1 s, closed 9 s. The timer
is reset only when a *command* moves the state from a non-pulse state into a pulse state.

| State (cmd value) | Outputs | Auto-transition |
|---|---|---|
| CUSTOM (0) | exactly as commanded (all 9); manual-4 latched | → STANDBY at t ≥ 30 000 (manual-4 stay latched) |
| ABORT (1) | depress = 1, all others 0 (+ manual-4 on baseline) | none |
| STANDBY (2) | all 0 (+ manual-4) | none |
| GN2_STANDBY (3) | depress pulse (+ manual-4) | none |
| GN2_FILL (10) | gn2_fill = (t mod 10 000) < 5 000; depress pulse (+ manual-4) | none |
| GN2_PULSE_FILL_A (11) | gn2_fill = 1; depress pulse | → GN2_STANDBY at t ≥ 500 |
| GN2_PULSE_FILL_B (12) | gn2_fill = 1; depress pulse | → GN2_STANDBY at t ≥ 1 000 |
| GN2_PULSE_FILL_C (13) | gn2_fill = 1; depress pulse | → GN2_STANDBY at t ≥ 5 000 |
| ENGINE_PRIME (19) | press_pilot = 1; gn2_fill = 1 for t ≥ 1 000 (+ manual-4) | none |
| FIRE (20) | press_pilot = 1, gn2_fill = 1; igniter for 3 000 ≤ t < 3 500; igniter_backup for 4 000 ≤ t < 4 500; run for t ≥ 10 000 (+ manual-4) | → STANDBY at t ≥ 30 000 |
| FIRE_MANUAL_PRESS_PILOT (21) | press_pilot = 1 (+ manual-4) | none |
| FIRE_MANUAL_DOME_PILOT_CLOSE (22) | all 0 (+ manual-4) | none |
| FIRE_MANUAL_IGNITER (23) | igniter = 1 (+ manual-4) | → STANDBY at t ≥ 500 |
| FIRE_MANUAL_RUN (24) | run = 1, lox_fill = 1 (+ manual-4) | none |

Non-state commands (30–32, 100) leave the relay state unchanged. 110 (RESTART) reboots the node.
Unknown command values are ignored.

**Igniter safety.** In every state, the primary `igniter` is forced off once it has been on
continuously for ≥ 500 ms. **`igniter_backup` has no such cutoff.** In CUSTOM it can stay on until the
30 s CUSTOM timeout. Each new CUSTOM packet with `igniter = 1` starts a new 500 ms pulse.

## eReg (DevEregControl)

| Command | eReg state |
|---|---|
| STATE_ABORT (1) | CLOSED (clears divergence latch) |
| STATE_ENGINE_PRIME (19) | STAGE_1 (bumpless PID reset) |
| STATE_FIRE (20) | STAGE_2 |
| EREG_CLOSED (30) | CLOSED |
| EREG_STAGE_1 (31) | STAGE_1 (bumpless PID reset) |
| EREG_STAGE_2 (32) | STAGE_2 |
| RESTART (110) | reboot |

CLOSED servo command: 0° for the first 500 ms after entering, then 2°. Pulse width
`pw = 500 + (angle + 90) × 2000 / 180` µs, so 0° → 1500 µs and 2° → 1522 µs.
Stage limits are 19° and 80°. If the lower PT reads above 500 psi, the servo is commanded to 1500 µs
while the PID keeps integrating. PID period is 6 ms.
Feedback PTs: upper = `copv_1`, lower = `oxtank_2`.

The command broadcaster delivers EREG_* commands to DevEregControl twice: once directly, and once
forwarded by DevFsLoxGn2Transducers. That's harmless, because the handlers don't change anything when
the same command is applied twice. Keep it.
