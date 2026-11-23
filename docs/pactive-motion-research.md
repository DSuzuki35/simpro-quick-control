# P-Active motion investigation

Investigated locally on 2026-11-23 against installed SimPro 3.2.5.13819 and a P-Active reporting V1.0.18. These are observations of an unofficial implementation, not a supported SDK contract.

## What is established

- The cached SimPro frontend contains a factory dialog for position demonstration. The installed backend's read-only factory-menu response exposes the corresponding position-demonstration entry for P-Active.
- `active_pedal_position_move_mode` receives `active_pedal_position_move_mode_data` as an integer: 1 starts recording, 2 stops recording, 3 starts playback, 4 ends playback. Its native HTTP handler reads that integer. It does not parse a position target from the request.
- Despite its name, `set_active_pedal_mode` is a **candidate position/setpoint endpoint**, not the actual internal mode switch. Its integer `active_pedal_mode_data` reaches the same two-byte, little-endian encoder (subcommand `0x30`) as the playback samples. The separate internal mode encoder uses subcommand `0x31` with one byte. This is static host-side evidence; firmware acceptance and physical behavior have not been tested.
- The playback callback runs on a nominal 20 ms timer. The constructor initializes its playback buffer with a triangle ramp spanning approximately 0 to 4095. The recording buffer is separate; a transfer from recording to playback has not been established. **Starting playback must not be treated as a harmless way to enable position control:** it may start a large-travel demonstration.
- The recorded brake sample and the source of `device_pedal_get_val.brake_raw_float` share the same native integer. The JSON formatter divides it by 40.95. This suggests the sample scale can be recovered as `round(brake_raw_float * 40.95)`, but does not establish millimeters, physical end stops, or a safe command range.
- Embedded protobuf metadata describes `factory.ActivePedalPositionModeData` with a session ID, mode enum (`normal`, `vibrator`, `demonstrate`), repeated `Pos2D` positions and haptic data. This establishes that an internal position-sequence format exists, not how an external client should transmit it or what its coordinates mean.

REA 6.8.0 was used to statically inspect the cached JavaScript bundle. That analysis is bounded and has incomplete semantic coverage. Targeted PE string/reference inspection and x64 disassembly independently traced the installed native HTTP readers, packet builders, playback callback and readback formatter. Cached frontend code can differ from the running build; only the installed native observations and live read-only responses are treated as current backend evidence.

## Firmware inspection

Local V1.0.16 and V1.0.18 update files use a 64-byte `SIMPROSFU100` container header identifying `p1000e`; their bodies have high entropy. High entropy alone cannot distinguish encryption from compression. The installed updater skips its host-side transform for the P-Active device type and passes the body onward. The firmware body has **not** been decrypted or decompiled, and its motor-control implementation has not been recovered.

REA's firmware inspection backend was unavailable in this Windows environment because it requires Linux/Binwalk. The investigation continued with local container comparison and static analysis of the installed Windows executable. No firmware was flashed and no bootloader was entered.

## What remains unknown

The host packet path and nominal playback timing are identified. Firmware mode requirements, physical coordinate interpretation, force limits, command acknowledgement, cancellation behavior and watchdog remain unknown. Neither arbitrary external setpoints nor a continuous closed-loop rudder interface have been demonstrated.

On the connected CAN-FD pedal, the read-only HTTP value endpoint returned zero for every axis and `voltage: false`, while the user reported a working pedal indicator in SimPro. A brief event-64 subscription did not resolve the discrepancy and was removed afterward. A 30-second probe collected 190 all-zero samples; the user confirmed pressing and releasing the pedal for the requested test. Native tracing found that both HTTP and event delivery use the same value reader, so a separate event-only sensor path was not established. The discrepancy remains unresolved. These zeros must not be used as a confirmed physical position or proof that pedal power is off. A trustworthy current-position feed is needed before a bounded movement test.

No record/playback, mode-switch, calibration or firmware-flash command was issued during this investigation. No saved movement was played. Quick Control exposes only ordinary preset tuning; it does not expose the factory motion endpoints.

Vendor firmware, cached source, private device identifiers and user presets are excluded from this repository and release.
