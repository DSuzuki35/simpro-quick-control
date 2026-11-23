# Compatibility verification

The version check is advisory. Unlisted versions can connect and adjust settings when the required local API and configuration fields remain available.

| SimPro build | Base | Verification | Advisory |
| --- | --- | --- | --- |
| 3.2.4.13771 | Alpha EVO Ultra, V2.3.6 | Original hardware read/write test | Tested |
| 3.2.5.13819 (`V3.2.5.13819-5dd62489`) | Alpha EVO Ultra, V2.3.8 | Read/write verification on 2026-11-23 | Tested from Quick Control 0.2.1 |
| 3.2.6.13816 (`C3.2.6.13816-6bcf7d5d`) | Alpha EVO Ultra, V2.3.8 | All 22 settings read on 2026-11-23; no completed write test before downgrade | Experimental |

## 3.2.5 live checks

The existing adapter connected without any API changes. It read all 22 controls and the 28 Nm base limit, then performed these reversible changes through its normal read-modify-write-confirm path:

| Setting | Before | Test value | Restored | Configuration part |
| --- | --- | --- | --- | --- |
| FFB strength | 100% | 99% | 100% | `servos`, ID 1 |
| Ring brightness | 35% | 34% | 35% | `global`, ID 0 |
| Ring light | On | Off | On | `light_groups`, ID 1 |

Each change was confirmed by a fresh read. Unrelated configuration values were preserved. SimPro's derived `can_reset` flag became true while live values differed from the saved preset; this is status metadata, not an extra tuning change. After restoration, all three configuration parts matched the initial snapshot, including that flag. No preset-save operation was issued.

This verifies the local configuration path, not every setting at every possible value. Physical encoder/keyboard behavior inside a game and VR headset rendering were not retested during this compatibility check. The Alpha EVO Ultra hardware restriction remains in place; other wheelbase models have not been verified.
