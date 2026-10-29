# rudder-vJoy

Turns two buttons on a hardware joystick into a rudder axis on a vJoy virtual joystick.

- Hold the **left** button: the rudder moves smoothly to the left.
- Hold the **right** button: the rudder moves smoothly to the right.
- Release the button: the rudder returns to center.

By default, buttons 4 and 5 of a Logitech Attack 3 drive the **Rz** axis of vJoy device 1. Games then see vJoy Rz as a normal analog rudder axis. This is useful for a stick with no twist axis and no rudder pedals.

Tested on Windows 11 with vJoy v2.2.2.0 and a Logitech Attack 3, in IL-2 Sturmovik: Cliffs of Dover Blitz.

## Requirements

- Windows (the script uses the vJoy Windows DLL)
- vJoy 2.2.x driver
- Python 3.9 or later, with the `py` launcher
- [pygame](https://www.pygame.org/)
- A hardware joystick with at least two buttons

## Setup

1. **Install vJoy** and restart Windows if the installer asks.
2. **Configure vJoy.** Open **Configure vJoy**, select device **1**, enable the **Rz** axis, and click **Apply**.
3. **Install pygame:**
   ```
   py -m pip install pygame
   ```
4. **Create your settings file.** In the project folder, run:
   ```
   copy configuration.ini.sample configuration.ini
   ```
5. **Edit `configuration.ini`** if your setup is different from the default. Each setting has a comment in the file. The main ones are:

   | Setting | Default | Meaning |
   |---|---|---|
   | `[vjoy] dll` | `C:\Program Files\vJoy\x64\vJoyInterface.dll` | Path to the vJoy DLL |
   | `[vjoy] device_id` | `1` | vJoy device number |
   | `[vjoy] axis` | `Rz` | vJoy axis to drive. Enable the same axis in Configure vJoy. |
   | `[joystick] name` | `Attack 3` | Part of your joystick's name |
   | `[joystick] button_left` / `button_right` | `4` / `5` | Button numbers as printed on the stick |
   | `[rudder] max_deflection` | `0.70` | How far the rudder moves (0 to 1 of full travel) |
   | `[rudder] ramp_time` | `0.50` | Seconds to move from center to full deflection |
   | `[rudder] return_time` | `0.20` | Seconds to return to center after release |

## Running

```
py rudder.py
```

Start it before or after the game; it keeps working while the game window has focus. At startup it prints the joystick it found and the active settings. Press **Ctrl+C** to stop. The rudder is centered and vJoy is released when it stops.

Check that it works in **Monitor vJoy**: the Rz bar should move when you hold button 4 or 5. With `max_deflection = 0.70`, it moves between 15% and 85%, and rests at 50%.

## Binding the rudder in a game (`--sweep`)

If you press button 4 or 5 while binding the rudder axis, some games bind the physical button as well as the vJoy axis. IL-2 Cliffs of Dover Blitz does this. To avoid this:

1. Run:
   ```
   py rudder.py --sweep
   ```
2. Within 5 seconds, click the rudder axis field in the game's control settings.
3. The script moves the axis left and right by itself for 10 seconds, so the game binds only the vJoy axis.
4. After the sweep, the script continues with normal button control.

You usually need this only once. The wait and the sweep time are set in the `[sweep]` section of `configuration.ini`.

## Notes

- **Only one program can use a vJoy device at a time.** Do not run Joystick Gremlin (activated) or the vJoy Feeder on the same device. Otherwise the script stops with a "device is busy" error.
- **Settings errors:** if `configuration.ini` is missing, or a setting is missing or invalid, the script stops before it opens vJoy. The error names the setting to fix.
