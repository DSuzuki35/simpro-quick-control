# Resource measurements

Short local samples on Windows 11, 16 logical processors, with SimPro connected, controls paused, five USB controllers detected, no assignments, and local browser pages open. Each sample ran for approximately 15 seconds. Figures include the controller's process tree; they exclude SimPro, the game and external browser/VR host.

| Implementation | Processes | Working set | Private memory | CPU, one-core equivalent |
| --- | ---: | ---: | ---: | ---: |
| Early embedded-browser popup | 7 | 470.3 MiB | 258.2 MiB | 13.31% |
| Released native popup | 1 | 62.5 MiB | 34.4 MiB | 7.18% |

The released sample corresponds to approximately **0.45% of the 16-logical-processor machine's total CPU capacity**. This is an illustrative short sample, not a guaranteed bound: startup, connected hardware, active input, other local clients and the overlay host can change usage. Physical fast-encoder/game-load performance has not been benchmarked.

The main memory reduction comes from removing the embedded browser/.NET process tree. Further changes include an event-driven adjustment worker, unchanged-configuration write suppression, persistent local HTTP connections, slower hidden-page polling, opening only assigned controllers outside Learn mode, and 250 ms idle waits when no input device needs polling. Active assigned devices retain an 8 ms polling interval.

`Start VR only.cmd` omits the native popup and tray entirely. This mode is available for users who only need an external VR browser source; it was not separately benchmarked here.

The portable release ZIP is approximately **25.7 MiB** and includes the Python/Tk/SDL runtime, so recipients do not need to install Python or an embedded browser runtime.
