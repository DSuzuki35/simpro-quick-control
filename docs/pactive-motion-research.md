# P-Active motion investigation

Investigated locally on 2026-11-23 against installed SimPro 3.2.5.13819 and a P-Active reporting V1.0.18. These are observations of an unofficial implementation, not a supported SDK contract.

## Live test invalidated the assumed command scale

**Do not connect an input axis to the factory endpoint on the basis of this research.** An explicitly authorized bench test sent the integer 20 once to `set_active_pedal_mode`, followed roughly 250 ms later by the standalone stop operation (state 4). The intended small displacement was not achieved: readback subsequently rose to 100%, and the user confirmed travel to the end stop. Later readback returned to zero. The stop request did not prevent the observed excursion and is not a verified emergency stop.

The assumption that 20 represents about 0.5% of physical travel was wrong or incomplete. Static reuse of an encoder and a 0–4095 demonstration buffer did **not** establish the live command's scale, operating mode or response. The test script was disabled immediately; no axis-to-motor loop was run or released. Quick Control 0.3.1 contains ordinary tuning only, including maximum force.

## What is established

- The cached SimPro frontend contains a factory dialog for position demonstration. The installed backend's read-only factory-menu response exposes the corresponding position-demonstration entry for P-Active.
- `active_pedal_position_move_mode` receives `active_pedal_position_move_mode_data` as an integer: 1 starts recording, 2 stops recording, 3 starts playback, 4 ends playback. Its native HTTP handler reads that integer. It does not parse a position target from the request.
- `set_active_pedal_mode` was investigated as a candidate position/setpoint endpoint. Its integer `active_pedal_mode_data` reaches the same two-byte, little-endian encoder (subcommand `0x30`) as the playback samples. A separate internal mode helper uses subcommand `0x31` with one byte. These are static host-side observations; they did not predict the bounded physical response required for external position control, as the live test above demonstrated.
- The playback callback runs on a nominal 20 ms timer. The constructor initializes its playback buffer with a triangle ramp spanning approximately 0 to 4095. The recording buffer is separate; a transfer from recording to playback has not been established. **Starting playback must not be treated as a harmless way to enable position control:** it may start a large-travel demonstration.
- The recorded brake sample and the source of `device_pedal_get_val.brake_raw_float` share the same native integer. The JSON formatter divides it by 40.95. This suggests the sample scale can be recovered as `round(brake_raw_float * 40.95)`, but does not establish millimeters, physical end stops, or a safe command range.
- Embedded protobuf metadata describes `factory.ActivePedalPositionModeData` with a session ID, mode enum (`normal`, `vibrator`, `demonstrate`), repeated `Pos2D` positions and haptic data. This establishes that an internal position-sequence format exists, not how an external client should transmit it or what its coordinates mean.

REA 6.8.0 was used to statically inspect the cached JavaScript bundle. That analysis is bounded and has incomplete semantic coverage. Targeted PE string/reference inspection and x64 disassembly independently traced the installed native HTTP readers, packet builders, playback callback and readback formatter. Cached frontend code can differ from the running build; only the installed native observations and live read-only responses are treated as current backend evidence.

## Firmware inspection

Local V1.0.16 and V1.0.18 update files use a 64-byte `SIMPROSFU100` container header identifying `p1000e`; their bodies have high entropy. High entropy alone cannot distinguish encryption from compression. The installed updater skips its host-side transform for the P-Active device type and passes the body onward. The firmware body has **not** been decrypted or decompiled, and its motor-control implementation has not been recovered.

REA's firmware inspection backend was unavailable in this Windows environment because it requires Linux/Binwalk. The investigation continued with local container comparison and static analysis of the installed Windows executable. No firmware was flashed and no bootloader was entered.

## What remains unknown

The host packet path and nominal playback timing are identified. Firmware mode requirements, physical coordinate interpretation, force limits, command acknowledgement, cancellation behavior and watchdog remain unknown. Neither arbitrary external setpoints nor a continuous closed-loop rudder interface have been demonstrated.

Initial short read windows returned only zeros. A later five-minute direct-USB capture, overlapping confirmed user input, recorded pedal raw values from 0 to 19.21856% and wheel angles from -43 to 21 degrees. Windows joystick input also changed. Thus the HTTP reader does work on this setup; the earlier null readings do not establish a CAN-FD defect. The `voltage: false` field was not a reliable indication of power. Native tracing found that HTTP and event delivery use the same value reader. Fresh telemetry alone does not establish a safe motor-command scale or stop behavior.

The single target request and subsequent standalone stop described above were issued. No playback-start, calibration or firmware-flash command was issued, and no saved movement was played. Quick Control does not expose these factory motion endpoints.

Vendor firmware, cached source, private device identifiers and user presets are excluded from this repository and release.
