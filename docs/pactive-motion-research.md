# P-Active motion investigation

Investigated locally on 2026-11-23 against installed SimPro 3.2.5.13819 and a P-Active reporting V1.0.18. These are observations of an unofficial implementation, not a supported SDK contract.

## What is established

- The cached SimPro frontend contains a factory dialog for position demonstration. The installed backend's read-only factory-menu response exposes the corresponding position-demonstration entry for P-Active.
- `active_pedal_position_move_mode` receives `active_pedal_position_move_mode_data` as an integer: 1 starts recording, 2 stops recording, 3 starts playback, 4 ends playback. Its native HTTP handler reads that integer. It does not parse a position target from the request.
- `set_active_pedal_mode` similarly reads an integer `active_pedal_mode_data`. A mode switch alone does not establish an arbitrary position command.
- Embedded protobuf metadata describes `factory.ActivePedalPositionModeData` with a session ID, mode enum (`normal`, `vibrator`, `demonstrate`), repeated `Pos2D` positions and haptic data. This establishes that an internal position-sequence format exists, not how an external client should transmit it or what its coordinates mean.

REA 6.8.0 was used to statically inspect the cached JavaScript bundle. That analysis is bounded and has incomplete semantic coverage. Targeted PE string/reference inspection and x64 disassembly independently confirmed the two native HTTP argument readers. Cached frontend code can differ from the running build; only the installed native observations and live read-only responses are treated as current backend evidence.

## What remains unknown

The position sequence's transport, coordinate units, sample timing, force limits, cancellation behavior, watchdog and firmware support for arbitrary external setpoints have not been established. A recorded demonstration is not evidence of a continuous closed-loop rudder interface.

No record/playback, mode-switch, calibration or firmware-flash command was issued during this investigation. No saved movement was played. Quick Control exposes only ordinary preset tuning; it does not expose the factory motion endpoints.

Vendor firmware, cached source, private device identifiers and user presets are excluded from this repository and release.
