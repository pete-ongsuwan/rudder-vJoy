# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`rudder.py` is a single-file Python feeder that turns two buttons on a hardware joystick into an emulated analog axis on a vJoy virtual device. Holding a button ramps the axis out to one side; releasing it makes the axis return to center (self-centering rudder). By default it targets vJoy device 1, axis Rz, using buttons 4 (left) and 5 (right) of a Logitech Attack 3.

Tested setup: vJoy v2.2.2.0, Windows 11, Logitech Attack 3. The code is Windows-only (it loads `vJoyInterface.dll` through `ctypes.WinDLL`).

## Commands

```
py -m pip install pygame                          # only dependency (Python 3.9+)
copy configuration.ini.sample configuration.ini   # first time only
py rudder.py                                      # normal run; Ctrl+C to stop
py rudder.py --sweep                              # binding helper: after [sweep] delay, moves the axis by itself for [sweep] duration, then runs normally
```

There is no build step, linter config, or test suite. To verify a change you need real hardware: a vJoy device with the configured axis (Rz by default) enabled (set in "Configure vJoy") and the physical joystick plugged in. Check the axis movement in "Monitor vJoy" or in the Windows game controller panel.

## Architecture

The program has four parts, all in [rudder.py](rudder.py):

- **Settings (`load_config`)** — reads `configuration.ini` next to the script into a frozen `Config` dataclass, which `main` passes to the other functions. See "Configuration" below.
- **vJoy output (`open_vjoy`)** — loads the vJoy DLL with `ctypes`, declares `argtypes`/`restype` for each function used, checks that the driver is enabled, the device is free or already owned, and the configured axis exists, then acquires the device. If you call a new vJoy function, declare its signature here in the same way.
- **Joystick input (`open_stick`)** — uses pygame to find the first joystick whose name contains `[joystick] name`. `SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1` is set *before* `import pygame`, so the stick is still read while the game window has focus. Keep this order.
- **Control loop (`main`)** — polls buttons at `loop_hz`, picks a target (−`max_deflection`, 0, or +`max_deflection`; both buttons pressed = center), and moves the value toward the target at a rate based on real elapsed time. It uses the slow `ramp_time` rate when moving away from center, and the fast `return_time` rate when returning to center or reversing through center. The `finally` block always centers the axis and releases the vJoy device — keep this cleanup when you change the loop.

Values inside the program are in −1..+1. `to_raw` maps them to the vJoy axis range `0x0001..0x8000`. So when a button is fully held, the axis position (as shown in Monitor vJoy) is 50% ± `max_deflection` × 50%:

| `max_deflection` | Left / Center / Right | Note |
|---|---|---|
| 0.50 | 25% / 50% / 75% | |
| 0.55 | 22.5% / 50% / 77.5% | |
| 0.60 | 20% / 50% / 80% | |
| 0.70 | 15% / 50% / 85% | value in `configuration.ini.sample` |
| 1.00 | 0% / 50% / 100% | full rudder |

## Configuration

- **Files:** all user settings live in `configuration.ini` (sections `[vjoy]`, `[joystick]`, `[rudder]`, `[sweep]`). `configuration.ini.sample` is the commented template and the only place the default values are written. The code has no fallback values.
- **Format:** INI read with the standard library `configparser`, so there is no extra dependency. It uses `interpolation=None`, so `%` is literal, and `inline_comment_prefixes=(";",)`, so `key = value ; comment` works.
- **Validation:** every key is required. `load_config` stops through `die()` with the section and key named when:
  - the file is missing or can't be parsed;
  - a section or key is missing, or a value is empty;
  - a value has the wrong type or is out of range.
- **Unknown keys are ignored.** A misspelled key still causes an error, because the correctly spelled key is then missing.
- **Values in the file are written for users:**
  - The axis is a name (`Rz`), converted with `AXIS_NAMES`.
  - Buttons are physical numbers (4, 5). `load_config` converts them to 0-based pygame indices, so `Config.btn_left`/`btn_right` are 0-based.
  - `open_stick` also checks that the buttons exist on the matched joystick.
- **Adding a setting:**
  - add it to both `.ini` files, the `Config` dataclass, and `load_config` (with a range check);
  - if users care about it, add it to the startup printout in `main`.
- **Not supported yet:** a `--config <path>` option.

## Constraints

- Only one program can own a vJoy device. Do not run Joystick Gremlin (activated) or the vJoy Feeder on the same device at the same time; `open_vjoy` exits with a "busy" error in that case.
- Why `--sweep` exists: in IL-2 Sturmovik: Cliffs of Dover Blitz, binding the rudder by pressing button 4/5 made the game bind *both* vJoy Rz and the physical Attack 3 button to the rudder. With `--sweep`, the user clicks the rudder binding field and the script moves Rz by itself, so the game only sees the vJoy axis. It is usually run once, when the binding is set up. Do not remove it. The wait before the sweep starts (`[sweep] delay`) is the time the user has to click the field.
