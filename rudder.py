"""
rudder.py - Logitech Attack 3 buttons 4/5 -> ramped, self-centering vJoy Rz rudder axis.

Hold button 4 = left rudder, button 5 = right rudder. Release = return to center.
Requires: vJoy 2.2.x driver (device 1 with Rz axis enabled), Python 3.9+, pygame.
    py -m pip install pygame
Settings: configuration.ini next to this script (copy configuration.ini.sample to start).
Run:  py rudder.py      (Ctrl+C to stop; axis is centered and vJoy released on exit)
      py rudder.py --sweep   (binding helper: after [sweep] delay, moves the axis by itself
                              for [sweep] duration, so the game binds the vJoy axis
                              without seeing button 4/5)

Do NOT run Joystick Gremlin (activated) at the same time - both would claim vJoy device 1.
"""
import configparser
import ctypes
import os
import sys
import time
from dataclasses import dataclass

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"  # read stick while game has focus
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configuration.ini")

AXIS_MIN, AXIS_MAX = 0x0001, 0x8000
VJD_STAT_OWN, VJD_STAT_FREE = 0, 1
AXIS_NAMES = {0x30: "X", 0x31: "Y", 0x32: "Z", 0x33: "Rx", 0x34: "Ry", 0x35: "Rz",
              0x36: "Slider", 0x37: "Dial"}
VJOY_MAX_DEVICES = 16


@dataclass(frozen=True)
class Config:
    dll: str
    device_id: int
    axis: int               # HID usage, e.g. 0x35 for Rz
    axis_name: str
    joy_name: str
    btn_left: int           # pygame index (0-based)
    btn_right: int
    max_deflection: float
    ramp_time: float
    return_time: float
    loop_hz: int
    sweep_delay: float
    sweep_duration: float


def to_raw(v: float) -> int:
    """Map -1..+1 to the vJoy axis range 1..32768."""
    v = max(-1.0, min(1.0, v))
    return int(round(AXIS_MIN + (v + 1.0) / 2.0 * (AXIS_MAX - AXIS_MIN)))


def die(msg: str) -> None:
    print("ERROR: " + msg)
    sys.exit(1)


def load_config() -> Config:
    """Read configuration.ini. Every key is required; stop with a clear error otherwise."""
    if not os.path.isfile(CONFIG_FILE):
        die("%s not found - copy configuration.ini.sample to configuration.ini." % CONFIG_FILE)
    cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=(";",))
    try:
        cp.read(CONFIG_FILE, encoding="utf-8")
    except configparser.Error as exc:
        die("Cannot read configuration.ini: %s" % exc)

    def get(section, key, convert, valid=lambda v: True, rule=""):
        if not cp.has_section(section):
            die("configuration.ini: section [%s] is missing." % section)
        if not cp.has_option(section, key):
            die("configuration.ini: [%s] %s is missing." % (section, key))
        text = cp.get(section, key).strip()
        if not text:
            die("configuration.ini: [%s] %s is empty." % (section, key))
        try:
            value = convert(text)
        except ValueError:
            die("configuration.ini: [%s] %s = %s is not a valid %s."
                % (section, key, text, convert.__name__))
        if not valid(value):
            die("configuration.ini: [%s] %s = %s, must be %s." % (section, key, text, rule))
        return value

    usages = {name.lower(): usage for usage, name in AXIS_NAMES.items()}
    axis_text = get("vjoy", "axis", str, lambda v: v.lower() in usages,
                    "one of " + ", ".join(AXIS_NAMES.values()))
    axis = usages[axis_text.lower()]

    btn_left = get("joystick", "button_left", int, lambda v: v >= 1, "1 or more")
    btn_right = get("joystick", "button_right", int,
                    lambda v: v >= 1 and v != btn_left, "1 or more and not the same as button_left")

    return Config(
        dll=get("vjoy", "dll", str),
        device_id=get("vjoy", "device_id", int, lambda v: 1 <= v <= VJOY_MAX_DEVICES,
                      "1..%d" % VJOY_MAX_DEVICES),
        axis=axis,
        axis_name=AXIS_NAMES[axis],
        joy_name=get("joystick", "name", str),
        btn_left=btn_left - 1,
        btn_right=btn_right - 1,
        max_deflection=get("rudder", "max_deflection", float, lambda v: 0 < v <= 1,
                           "more than 0 and at most 1"),
        ramp_time=get("rudder", "ramp_time", float, lambda v: v > 0, "more than 0"),
        return_time=get("rudder", "return_time", float, lambda v: v > 0, "more than 0"),
        loop_hz=get("rudder", "loop_hz", int, lambda v: v > 0, "more than 0"),
        sweep_delay=get("sweep", "delay", float, lambda v: v >= 0, "0 or more"),
        sweep_duration=get("sweep", "duration", float, lambda v: v > 0, "more than 0"),
    )


def open_vjoy(cfg: Config):
    if not os.path.isfile(cfg.dll):
        die("vJoyInterface.dll not found at " + cfg.dll
            + " - edit [vjoy] dll in configuration.ini.")
    vj = ctypes.WinDLL(cfg.dll)
    vj.vJoyEnabled.restype = ctypes.c_bool
    vj.GetVJDStatus.argtypes = [ctypes.c_uint]
    vj.GetVJDAxisExist.argtypes = [ctypes.c_uint, ctypes.c_uint]
    vj.AcquireVJD.argtypes = [ctypes.c_uint]
    vj.AcquireVJD.restype = ctypes.c_bool
    vj.RelinquishVJD.argtypes = [ctypes.c_uint]
    vj.SetAxis.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_uint]
    vj.SetAxis.restype = ctypes.c_bool

    if not vj.vJoyEnabled():
        die("vJoy driver is not enabled.")
    status = vj.GetVJDStatus(cfg.device_id)
    if status not in (VJD_STAT_OWN, VJD_STAT_FREE):
        die("vJoy device %d is busy (Gremlin/Feeder running?) or missing. status=%d"
            % (cfg.device_id, status))
    if not vj.GetVJDAxisExist(cfg.device_id, cfg.axis):
        die("vJoy device %d has no %s axis - enable it in Configure vJoy."
            % (cfg.device_id, cfg.axis_name))
    if not vj.AcquireVJD(cfg.device_id):
        die("Could not acquire vJoy device %d." % cfg.device_id)
    return vj


def open_stick(cfg: Config):
    pygame.init()
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        if cfg.joy_name.lower() in js.get_name().lower():
            print("Using: %s (%d buttons)" % (js.get_name(), js.get_numbuttons()))
            highest = max(cfg.btn_left, cfg.btn_right) + 1
            if highest > js.get_numbuttons():
                die("Button %d does not exist on this joystick - edit [joystick] in "
                    "configuration.ini." % highest)
            return js
    die("Joystick containing '%s' not found." % cfg.joy_name)


def sweep(vj, cfg: Config) -> None:
    """Move the axis left/right automatically so the game can bind it without button presses."""
    print("[SWEEP] click the Rudder axis field in the game now. Sweep starts in %.0f s..."
          % cfg.sweep_delay)
    time.sleep(cfg.sweep_delay)
    print("[SWEEP] moving %s for %.0f s..." % (cfg.axis_name, cfg.sweep_duration))
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < cfg.sweep_duration:
        phase = (time.perf_counter() - t0) % 2.0          # 2 s cycle
        v = (phase - 0.5) if phase < 1.0 else (1.5 - phase)  # triangle wave -0.5..+0.5
        vj.SetAxis(to_raw(v * 2.0 * cfg.max_deflection), cfg.device_id, cfg.axis)
        time.sleep(0.01)
    vj.SetAxis(to_raw(0.0), cfg.device_id, cfg.axis)
    print("[SWEEP] done, %s centered. Continuing with normal button control." % cfg.axis_name)


def main() -> None:
    cfg = load_config()
    vj = open_vjoy(cfg)
    js = open_stick(cfg)
    print("Left: button %d, Right: button %d" % (cfg.btn_left + 1, cfg.btn_right + 1))
    print("Max. Deflection: %.2f, Ramp: %.2fs, Return: %.2fs"
          % (cfg.max_deflection, cfg.ramp_time, cfg.return_time))
    print("vJoy Axis: %s (device %d)" % (cfg.axis_name, cfg.device_id))
    center = to_raw(0.0)
    vj.SetAxis(center, cfg.device_id, cfg.axis)
    if "--sweep" in sys.argv:
        sweep(vj, cfg)

    ramp_rate = cfg.max_deflection / cfg.ramp_time      # units per second
    return_rate = cfg.max_deflection / cfg.return_time
    period = 1.0 / cfg.loop_hz
    value = 0.0
    last = time.perf_counter()
    print("Rudder feeder running.")
    print("Ctrl+C to stop.")

    try:
        while True:
            pygame.event.pump()
            left = js.get_button(cfg.btn_left)
            right = js.get_button(cfg.btn_right)

            now = time.perf_counter()
            elapsed = now - last
            last = now

            if left and not right:
                target = -cfg.max_deflection
            elif right and not left:
                target = cfg.max_deflection
            else:
                target = 0.0

            # Ramp out slowly; return to center (or reverse through center) quickly.
            rate = return_rate if (target == 0.0 or value * target < 0) else ramp_rate
            step = rate * elapsed
            if value < target:
                value = min(value + step, target)
            elif value > target:
                value = max(value - step, target)

            vj.SetAxis(to_raw(value), cfg.device_id, cfg.axis)
            time.sleep(period)
    except KeyboardInterrupt:
        pass
    except pygame.error as exc:
        print("Joystick error (disconnected?): %s" % exc)
    finally:
        vj.SetAxis(center, cfg.device_id, cfg.axis)
        vj.RelinquishVJD(cfg.device_id)
        pygame.quit()
        print("Stopped. Rudder centered, vJoy released.")


if __name__ == "__main__":
    main()
