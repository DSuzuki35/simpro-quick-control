# Architecture

`core.py` defines verified setting metadata and pure adjustment/binding/visibility rules. `simpro.py` owns local HTTP, device/preset discovery and serialized read-modify-confirm operations. `service.py` owns assignments, acceleration, queueing, persistence and state. `input_reader.py` translates SDL joystick button edges into service actions. `server.py` serves local static pages and a token-protected API. `desktop.py` hosts the optional non-activating Tk popup and tray. `startup.py` manages an opt-in per-user Windows login startup entry. `main.py` wires their lifetimes together.

## SimPro integration

All calls are HTTP POST JSON under `http://127.0.0.1:56791/simpro/api/v3/`.

| Method | Purpose |
| --- | --- |
| `app_get_info` | Optional software version metadata |
| `get_device_list` | Discover base and identity |
| `preset_get_selected_dev_config` | Identify active preset |
| `preset_get_dev_config` | Read current complete configuration |
| `device_base_get_status` | Confirm identity and read maximum torque |
| `preset_set_dev_config` | Update one full configuration part |

Device/product UUIDs are hexadecimal strings; the preset UUID is a decimal string. Servo writes use `part_type: servos`, `part_id: 1`; global lighting uses `global`, ID 0; the ring uses `light_groups`, ID 1. The current complete part is copied and just the selected field changed, preserving fields this app does not understand. Steering-angle changes also update the hard-lock angle, matching the inspected SimPro UI.

The selected-preset call can return saved/stale settings, so it is only used for preset identity. Live values come from `preset_get_dev_config`. A successful write response is an acknowledgment, not proof of application: the adapter polls for readback confirmation, with a two-second timeout. Preset changes reject queued work. No preset-save call is issued.

Local HTTP uses `http.client` directly, avoiding proxy discovery and unnecessary TLS context initialization. This also avoids a frozen-app SSL initialization failure observed on the development machine. Remote endpoints and HTTPS are rejected by the adapter's constructor because this integration is local-only.

No proprietary SimPro binaries, cached frontend bundles, user presets or device IDs are included. The adapter's behavior was established by inspecting the installed application's request contract and validating a reversible 100% → 99% → 100% strength change.

## Visibility

User actions update a monotonic inactivity timestamp. Polling does not. The desktop host calls `ShowWindow(SW_SHOWNOACTIVATE)` and `SetWindowPos(SWP_NOACTIVATE)`; hiding affects the entire native window. `/vr` instead fades its card, since the page cannot close or hide a third-party VR host.

## Resource choices

There is no frontend framework or JavaScript build pipeline. The backend sleeps between work, caches optional version metadata, avoids unchanged preference writes and skips copying the full state for hidden native visibility checks. Unassigned USB controllers are closed except during learning. `--headless` does not import Tk or the tray library. All data remains local.
