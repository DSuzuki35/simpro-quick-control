# Changelog

## 0.2.1 — 2026-11-23

- Verified live reads and reversible writes with installed SimPro 3.2.5.13819 and Alpha EVO Ultra firmware V2.3.8; no API adapter change was needed.
- Recognize both 3.2.4.13771 and 3.2.5.13819 as tested versions. Other versions remain usable with an experimental advisory.
- Document partial 3.2.6.13816 verification: all 22 controls read successfully; writes were not tested before downgrade.

## 0.2.0 — 2026-11-01

- Added optional global keyboard shortcuts for every shared and dedicated control, alongside USB assignments.
- Added shortcut picker, duplicate validation and visible Windows registration conflicts.
- Keyboard adjustments respect pause/learning state, use one configured step, and do not auto-repeat or accelerate.
- Added version identification in the settings footer, popup title, CLI and Windows executable metadata.
- Build outputs now use versioned directories and protect existing runtime data.
- Existing 0.1.0 settings remain compatible. No controls or features were removed.

## 0.1.0 — 2026-11-01

Initial public release: USB encoder/button control, 22 wheelbase settings, acceleration, native popup, minimal VR page, inactivity hiding, Windows startup and auto-enable options.
