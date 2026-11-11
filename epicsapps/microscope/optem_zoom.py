"""
optem_zoom.py - control the Optem FUSION zoom axis (Motor2) over the network. .. with Claude


HANDOFF NOTES FOR THE PROGRAMMER
================================
Architecture
    viewer app (this module)  --HTTP/JSON-RPC 2.0-->  LSCM SDK Service on the Beelink  --USB/serial-->  controller

    * Server:    Windows service "LSCM SDK Service" (LSCMSDKService.exe) on the Beelink.
    * Endpoint:  POST http://<beelink-ip>:991/jsonrpc   (JSON-RPC 2.0, Content-Type: application/json)
                 The port is the <SocketServer Port="991"> line in
                 C:\\ProgramData\\WdiDevice\\JSON Server\\ServerConfig.  991 is the default for server
                 versions >= 2.0.0.4753 (older versions used 8081).
    * COM port:  the service opens the controller's USB-serial port named by MCX_COMPORT in that same
                 file.  It must match Device Manager (currently COM3).  If the service cannot open
                 it, every call returns -8 (Error_DeviceNotInitialized).
    * The service initialises the device by itself when it starts.  This module does NOT call
      System.ISystem.Init (not needed, and calling it repeatedly is discouraged by the manual).

Things that will bite you (all observed on our system)
    1. The Optem Fusion *Console* and the SDK service must NOT use the controller at the same time.
       Close the Console before running the viewer.  If the Console was opened while the service was
       running, restart "LSCM SDK Service" afterwards.
    2. Property reads accept AT MOST THREE properties per request (the manual's limit).  This module
       chunks automatically.
    3. Each HTTP round trip takes a noticeable fraction of a second.  The motor "busy" status bit
       (bit 6) can be missed entirely on short moves, so arrival is verified by POSITION, not just
       by the busy bit.
    4. Status bits: bit 6 busy; bits 8/9 HARD limits (treated as an error); bits 10/11 SOFT limits.
       A soft-limit bit was seen set ~665 steps before the position reached the +8500 limit, so soft
       bits are informational only here.
    5. MoveStop is not instantaneous (the stage coasts / the request takes a round trip).
    6. UNITS: the SDK names positions "...Um" (micrometres) but the Console shows the same numbers as
       "steps".  The physical size of one unit is NOT verified.  This module just calls them "steps".
       Speed/acceleration parameters have contradictory units in the manual; we leave the controller's
       defaults (5.0 / 50.0) untouched.
    7. Direction: positive steps = zoom IN, negative = zoom OUT.  Step 0 = the default 1.5X position.

Safety design
    * Moves are refused (OptemSafetyError) if the target is outside [min_steps, max_steps]
      (default -7500 .. +8500, the soft limits configured in the controller), if the controller's own
      soft limits are disabled or narrower than ours, if the motor is disabled, if a hard-limit bit is
      set, or if the stage is already moving.
    * While waiting for a move the module aborts and sends MoveStop on a hard-limit bit, an overrun
      beyond the soft-limit window, or a timeout.
    * Only calls that were exercised on our hardware are wrapped: GetProperty, MoveDistanceUm,
      MoveStop.  MotorEnable and Home exist in the SDK but are deliberately NOT wrapped yet (Home
      drives the stage through its full range; use the Console for homing).

Zoom <-> steps
    DEFAULT_CALIBRATION holds six measured points read from the module's scale (about +-0.05X
    reading error): -7000 -> 1.00X, -3000 -> 1.25X, 0 -> 1.50X, +4500 -> 2.00X, +6500 -> 2.25X,
    +8000 -> 2.50X.  Between points the zoom is interpolated geometrically (linear in log-zoom).
    The table covers -7000 .. +8000 steps; set_zoom() accepts 1.00X .. 2.50X, and get_zoom() clamps
    positions beyond the table (the stage can travel to -7500 / +8500).  Refine by passing your own
    table:  OptemZoomController(..., calibration=ZoomCalibration(((s0, z0), (s1, z1), ...)))
    with strictly increasing steps and zoom.

Threading
    All requests are serialised by an internal lock held only for one request at a time, so
    stop() can be called from another thread (e.g. a GUI button) while move_to(..., wait=True) is
    blocking in a worker thread.  In a GUI, either run moves in a worker thread, or call
    move_to(..., wait=False) and poll is_moving()/get_position() from a timer.

Minimal usage
    from optem_zoom import OptemZoomController
    zoom = OptemZoomController("10.54.161.7")          # port 991 by default
    print(zoom.connect())                               # raises OptemConnectionError if unreachable
    zoom.set_zoom(1.8)                                  # blocks until arrived
    zoom.move_to(1000)                                  # steps
    print(zoom.get_position(), zoom.get_zoom())
"""
from __future__ import annotations

import argparse
import logging
import math
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import requests

__all__ = [
    "OptemZoomController", "ZoomCalibration", "DEFAULT_CALIBRATION", "Status",
    "OptemError", "OptemConnectionError", "OptemSDKError", "OptemSafetyError",
    "OptemBusyError", "OptemTimeout", "OptemMoveIncomplete",
]

log = logging.getLogger("optem_zoom")

# --------------------------------------------------------------------------- configuration
DEFAULT_HOST = "10.54.161.7"
DEFAULT_PORT = 991
DEFAULT_PATH = "/jsonrpc"
DEFAULT_CONTROLLER_INDEX = 0
DEFAULT_COMPONENT = "PFABUSMotor2"       # Motor2 = zoom module ("Zoom Module")

SAFE_MIN_STEPS = -7500.0                 # zoom out limit (soft limit configured in the controller)
SAFE_MAX_STEPS = 8500.0                  # zoom in limit

ARRIVE_TOL = 2.0                         # steps: "arrived" if within this of the target
OVERRUN_MARGIN = 150.0                   # steps beyond the window that triggers an abort
POLL_INTERVAL_S = 0.1
DEFAULT_MOVE_TIMEOUT_S = 120.0

BUSY_BIT = 1 << 6
HARD_CCW_BIT, HARD_CW_BIT = 1 << 8, 1 << 9
SOFT_CCW_BIT, SOFT_CW_BIT = 1 << 10, 1 << 11
HARD_MASK = HARD_CCW_BIT | HARD_CW_BIT

SDK_ERRORS: Dict[int, str] = {
    0: "Error_Success", 1: "Operation started, not completed",
    -1: "Error_IncorrectParamValue", -2: "Error_OperationFailed",
    -3: "Error_IncorrectDeviceStatus", -4: "Error_OperationTimeout",
    -5: "Error_LimitSwitchTriggered", -6: "Error_UnknownParameter",
    -7: "Error_IncorrectDevice", -8: "Error_DeviceNotInitialized",
    -9: "Error_UnknownOperation", -10: "Error_InvalidOperation",
    -11: "Error_IncorrectDataType", -12: "Error_DeviceBusy",
    -13: "Error_DeviceNotHomed", -14: "Error_InitDeviceFailed",
    -15: "Error_CloseDeviceFailed", -16: "Error_OtherDeviceParam",
    -17: "Error_OperationNotAllowedWhenAf", -18: "Error_WriteNotAllowed",
    -19: "Error_EEPROMReadFailed", -20: "Error_DeviceNotConnected",
    -21: "Error_IncorrectEEPROMRevision",
}


# --------------------------------------------------------------------------- exceptions
class OptemError(Exception):
    """Base class for everything this module raises."""


class OptemConnectionError(OptemError):
    """Server unreachable, HTTP error, or a reply that is not valid JSON-RPC."""


class OptemSDKError(OptemError):
    """The SDK returned a negative result code (see SDK_ERRORS). Attribute: .code"""

    def __init__(self, code: int, context: str = ""):
        self.code = code
        name = SDK_ERRORS.get(code, "unknown code")
        hint = ""
        if code in (-8, -14):
            hint = (" - the service cannot talk to the controller: check the Optem Console is closed, "
                    "MCX_COMPORT in ServerConfig matches Device Manager, then restart LSCM SDK Service")
        super().__init__(f"SDK error {code} ({name}){' during ' + context if context else ''}{hint}")


class OptemSafetyError(OptemError):
    """A safety check refused or aborted a move."""


class OptemBusyError(OptemError):
    """A move was requested while the stage is still moving."""


class OptemTimeout(OptemError):
    """A move did not finish in time (the motor was sent MoveStop)."""


class OptemMoveIncomplete(OptemError):
    """The stage stopped before the target (e.g. stop() was called). Attributes: .position, .target"""

    def __init__(self, position: float, target: Optional[float], why: str = ""):
        self.position, self.target = position, target
        super().__init__(f"Move ended at {position:.1f} steps, target was {target}. {why}".strip())


# --------------------------------------------------------------------------- zoom calibration
@dataclass(frozen=True)
class ZoomCalibration:
    """Maps step position <-> optical zoom using measured (steps, zoom) points.

    Interpolation is linear in log(zoom) between neighbouring points, which fits a lens whose
    zoom grows geometrically with travel and passes exactly through every supplied point.
    Values outside the table are clamped (steps_to_zoom) or rejected (zoom_to_steps).
    """
    points: Tuple[Tuple[float, float], ...]

    def __post_init__(self):
        pts = self.points
        if len(pts) < 2:
            raise ValueError("calibration needs at least two points")
        for (s0, z0), (s1, z1) in zip(pts, pts[1:]):
            if not (s1 > s0 and z1 > z0 > 0):
                raise ValueError("points must have strictly increasing steps and zoom, zoom > 0")

    @property
    def min_steps(self) -> float: return self.points[0][0]
    @property
    def max_steps(self) -> float: return self.points[-1][0]
    @property
    def min_zoom(self) -> float: return self.points[0][1]
    @property
    def max_zoom(self) -> float: return self.points[-1][1]

    def steps_to_zoom(self, steps: float) -> float:
        pts = self.points
        steps = min(max(steps, self.min_steps), self.max_steps)
        for (s0, z0), (s1, z1) in zip(pts, pts[1:]):
            if steps <= s1:
                f = (steps - s0) / (s1 - s0)
                return z0 * (z1 / z0) ** f
        return self.max_zoom  # not reached

    def zoom_to_steps(self, zoom: float) -> float:
        if not (self.min_zoom - 1e-9 <= zoom <= self.max_zoom + 1e-9):
            raise ValueError(f"zoom {zoom} outside calibrated range "
                             f"{self.min_zoom:.2f}..{self.max_zoom:.2f}")
        for (s0, z0), (s1, z1) in zip(self.points, self.points[1:]):
            if zoom <= z1 + 1e-9:
                f = math.log(zoom / z0) / math.log(z1 / z0)
                return s0 + (s1 - s0) * f
        return self.max_steps  # not reached


# Measured (steps, zoom) points supplied by the user (read from the module's zoom scale, so expect
# roughly +-0.05X reading error).  Calibrated range is -7000 .. +8000 steps = 1.00X .. 2.50X; the
# stage can physically travel 500 steps further at each end (window -7500 .. +8500), where
# get_zoom() simply reports the end values (clamped).  Add points to refine, e.g. at -7500 / +8500.
DEFAULT_CALIBRATION = ZoomCalibration((
    (-7000.0, 1.00),
    (-3000.0, 1.25),
    (0.0, 1.50),
    (4500.0, 2.00),
    (6500.0, 2.25),
    (8000.0, 2.50),
))


# --------------------------------------------------------------------------- status snapshot
@dataclass(frozen=True)
class Status:
    position: float
    motion_status: int
    motor_enabled: bool
    soft_limits_enabled: bool
    soft_min: float
    soft_max: float

    @property
    def busy(self) -> bool: return bool(self.motion_status & BUSY_BIT)
    @property
    def hard_limit(self) -> bool: return bool(self.motion_status & HARD_MASK)
    @property
    def soft_cw(self) -> bool: return bool(self.motion_status & SOFT_CW_BIT)
    @property
    def soft_ccw(self) -> bool: return bool(self.motion_status & SOFT_CCW_BIT)


# --------------------------------------------------------------------------- the controller
class OptemZoomController:
    """Network client for the Optem FUSION zoom axis. See the module docstring."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, *,
                 controller_index: int = DEFAULT_CONTROLLER_INDEX,
                 component: str = DEFAULT_COMPONENT,
                 min_steps: float = SAFE_MIN_STEPS, max_steps: float = SAFE_MAX_STEPS,
                 edge_margin_steps: float = 0.0,
                 calibration: ZoomCalibration = DEFAULT_CALIBRATION,
                 request_timeout: float = 10.0, path: str = DEFAULT_PATH):
        """edge_margin_steps: stay this far inside [min_steps, max_steps] (0 = use the full window)."""
        if not min_steps < max_steps:
            raise ValueError("min_steps must be < max_steps")
        self.url = f"http://{host}:{port}{path}"
        self.controller_index = controller_index
        self.component = component
        self.min_steps = float(min_steps) + edge_margin_steps
        self.max_steps = float(max_steps) - edge_margin_steps
        self.calibration = calibration
        self.request_timeout = request_timeout
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._next_id = 0
        self._target: Optional[float] = None

    # ---- low level -------------------------------------------------------------------
    def close(self) -> None:
        self._session.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()

    def _rpc(self, method: str, params: Optional[dict] = None):
        """One JSON-RPC call. Returns the 'result' value (dict or int). Serialised by a lock."""
        with self._lock:
            self._next_id += 1
            payload = {"jsonrpc": "2.0", "method": method, "id": self._next_id}
            if params is not None:
                payload["params"] = params
            log.debug("-> %s", payload)
            try:
                r = self._session.post(self.url, json=payload, timeout=self.request_timeout)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.RequestException as e:
                raise OptemConnectionError(f"{self.url}: {e}") from e
            except ValueError as e:
                raise OptemConnectionError(f"{self.url}: reply was not JSON") from e
        log.debug("<- %s", data)
        if "error" in data:
            raise OptemError(f"JSON-RPC error from {method}: {data['error']}")
        return data.get("result")

    @staticmethod
    def _check_code(result, context: str) -> None:
        """Move/stop operations return an int: 1 started, 0 done, negative = error."""
        if isinstance(result, int) and result < 0:
            raise OptemSDKError(result, context)

    def _get_props(self, component: str, interface: str, names: Sequence[str]) -> dict:
        """GetProperty with the manual's limit of 3 properties per request (auto-chunked)."""
        out: dict = {}
        names = list(names)
        for i in range(0, len(names), 3):
            params = {n: None for n in names[i:i + 3]}
            params["i32ControllerIndex"] = self.controller_index
            res = self._rpc(f"{component}.{interface}.GetProperty", params)
            if isinstance(res, int):
                raise OptemSDKError(res, f"GetProperty{names[i:i + 3]}")
            if not isinstance(res, dict):
                raise OptemError(f"unexpected GetProperty reply: {res!r}")
            out.update(res)
        return out

    def _motor_props(self, names: Sequence[str]) -> dict:
        return self._get_props(self.component, "IMotion", names)

    def _poll(self) -> Tuple[float, int]:
        r = self._motor_props(["floatCurrentRelPositionUm", "u32MotionStatus"])
        return float(r["floatCurrentRelPositionUm"]), int(r["u32MotionStatus"])

    # ---- reading ---------------------------------------------------------------------
    def connect(self) -> dict:
        """Verify the whole chain (network -> service -> controller). Returns controller info.
        Raises OptemConnectionError / OptemSDKError (-8 / -14 means the service has no controller)."""
        info = self._get_props("PFABUSCommon", "IController",
                               ["strFriendlyName", "u32SerialNumber", "u8MapRevision"])
        info["zoom_module_name"] = self._motor_props(["strFriendlyName"]).get("strFriendlyName")
        return info

    def read_status(self) -> Status:
        r = {}
        r.update(self._motor_props(["boolMotorEnable", "u32MotionStatus", "floatCurrentRelPositionUm"]))
        r.update(self._motor_props(["floatSoftLimitMinPositionUm", "floatSoftLimitMaxPositionUm",
                                    "boolEnableSoftLimits"]))
        return Status(position=float(r["floatCurrentRelPositionUm"]),
                      motion_status=int(r["u32MotionStatus"]),
                      motor_enabled=bool(r["boolMotorEnable"]),
                      soft_limits_enabled=bool(r["boolEnableSoftLimits"]),
                      soft_min=float(r["floatSoftLimitMinPositionUm"]),
                      soft_max=float(r["floatSoftLimitMaxPositionUm"]))

    def get_position(self) -> float:
        """Current position in steps (0 = default 1.5X, + = zoom in)."""
        return self._poll()[0]

    def get_zoom(self) -> float:
        """Estimated zoom factor from the current position (uses the rough calibration table)."""
        return self.calibration.steps_to_zoom(self.get_position())

    def is_moving(self) -> bool:
        return bool(self._poll()[1] & BUSY_BIT)

    # ---- motion ----------------------------------------------------------------------
    def move_to(self, steps: float, *, wait: bool = True, clamp: bool = False,
                timeout: float = DEFAULT_MOVE_TIMEOUT_S) -> Optional[float]:
        """Move to an absolute position in steps.

        wait=True  : blocks until arrived; returns the final position.
        wait=False : returns None right after the move starts; poll is_moving() or call
                     wait_until_done().
        clamp=True : silently limit the target to [min_steps, max_steps] instead of raising.
        """
        target = float(steps)
        if not (self.min_steps <= target <= self.max_steps):
            if clamp:
                target = min(max(target, self.min_steps), self.max_steps)
            else:
                raise OptemSafetyError(f"target {target} steps is outside the allowed window "
                                       f"[{self.min_steps}, {self.max_steps}]")
        st = self.read_status()
        self._preflight(st)
        delta = target - st.position
        if abs(delta) <= ARRIVE_TOL:
            return st.position
        self._target = target
        try:
            res = self._rpc(f"{self.component}.IMotion.MoveDistanceUm",
                            {"floatDistanceUm": float(delta),
                             "i32ControllerIndex": self.controller_index})
            self._check_code(res, "MoveDistanceUm")
        except Exception:
            self._target = None
            raise
        log.info("move %.1f -> %.1f (delta %+.1f)", st.position, target, delta)
        if not wait:
            return None
        return self.wait_until_done(target, timeout=timeout)

    def move_relative(self, delta_steps: float, **kw) -> Optional[float]:
        """Move by a signed number of steps from the current position (same options as move_to)."""
        return self.move_to(self.get_position() + float(delta_steps), **kw)

    def set_zoom(self, zoom: float, **kw) -> Optional[float]:
        """Move to the estimated position for a zoom factor (rough calibration; see module docs)."""
        try:
            steps = self.calibration.zoom_to_steps(zoom)
        except ValueError as e:
            raise OptemSafetyError(str(e)) from e
        return self.move_to(round(steps), **kw)

    def stop(self) -> None:
        """Ask the controller to stop moving (safe to call from another thread)."""
        res = self._rpc(f"{self.component}.IMotion.MoveStop",
                        {"i32ControllerIndex": self.controller_index})
        self._check_code(res, "MoveStop")

    def wait_until_done(self, target: Optional[float] = None, *,
                        timeout: float = DEFAULT_MOVE_TIMEOUT_S,
                        poll_s: float = POLL_INTERVAL_S) -> float:
        """Block until the current move finishes; returns the final position.

        Raises OptemSafetyError (hard-limit bit / overrun; motor is stopped), OptemTimeout (motor
        stopped), or OptemMoveIncomplete (stage stopped short, e.g. after stop())."""
        if target is None:
            target = self._target
        t0 = time.monotonic()
        first_pos: Optional[float] = None
        last_pos: Optional[float] = None
        stable = idle = 0
        try:
            while True:
                pos, status = self._poll()
                if first_pos is None:
                    first_pos = pos
                if status & HARD_MASK:
                    self._safe_stop()
                    raise OptemSafetyError(f"hard limit bit set (status {status}) at {pos:.1f} steps")
                if pos > self.max_steps + OVERRUN_MARGIN or pos < self.min_steps - OVERRUN_MARGIN:
                    self._safe_stop()
                    raise OptemSafetyError(f"overrun: position {pos:.1f} is outside "
                                           f"[{self.min_steps}, {self.max_steps}]")
                elapsed = time.monotonic() - t0
                if not (status & BUSY_BIT):
                    if target is None:
                        idle += 1
                        if idle >= 2:
                            return pos
                    else:
                        if abs(pos - target) <= ARRIVE_TOL:
                            return pos
                        stable = stable + 1 if (last_pos is not None and abs(pos - last_pos) < 0.01) else 0
                        moved = abs(pos - first_pos) >= 1.0
                        if stable >= 3 and moved:
                            raise OptemMoveIncomplete(pos, target, "The stage stopped before the target.")
                        if not moved and elapsed > 3.0:
                            raise OptemMoveIncomplete(pos, target, "The stage did not move.")
                else:
                    stable = idle = 0
                if elapsed > timeout:
                    self._safe_stop()
                    raise OptemTimeout(f"move not finished after {timeout:.0f}s (at {pos:.1f} steps)")
                last_pos = pos
                time.sleep(poll_s)
        finally:
            self._target = None

    # ---- internals -------------------------------------------------------------------
    def _safe_stop(self) -> None:
        try:
            self.stop()
        except Exception as e:  # never mask the original problem
            log.error("MoveStop failed: %s - use the power switch if the stage is moving", e)

    def _preflight(self, st: Status) -> None:
        if not st.motor_enabled:
            raise OptemSafetyError("motor is not enabled (enable it from the Optem Console)")
        if st.hard_limit:
            raise OptemSafetyError(f"hard limit bit set (status {st.motion_status}); move the stage "
                                   f"off the limit with the Console first")
        if st.busy:
            raise OptemBusyError("stage is still moving")
        if not st.soft_limits_enabled:
            raise OptemSafetyError("controller soft limits are disabled - refusing to move")
        if self.min_steps < st.soft_min or self.max_steps > st.soft_max:
            raise OptemSafetyError(
                f"allowed window [{self.min_steps}, {self.max_steps}] is wider than the controller's "
                f"soft limits [{st.soft_min}, {st.soft_max}]")


# --------------------------------------------------------------------------- command line demo
def _print_table(cal: ZoomCalibration) -> None:
    print("steps    zoom (rough estimate)")
    s = int(cal.min_steps)
    while s < cal.max_steps:
        print(f"{s:6d}   {cal.steps_to_zoom(s):.2f}X")
        s += 1000
    print(f"{int(cal.max_steps):6d}   {cal.max_zoom:.2f}X")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Optem zoom demo/diagnostic tool")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation before moving")
    ap.add_argument("-v", "--verbose", action="store_true", help="log every request")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="read-only: show connection and state")
    sub.add_parser("table", help="print the rough zoom vs steps table")
    sub.add_parser("stop", help="send MoveStop")
    p = sub.add_parser("steps", help="move to an absolute step position"); p.add_argument("value", type=float)
    p = sub.add_parser("rel", help="move by a number of steps"); p.add_argument("value", type=float)
    p = sub.add_parser("zoom", help="move to an estimated zoom factor"); p.add_argument("value", type=float)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(message)s")

    if a.cmd == "table":
        _print_table(DEFAULT_CALIBRATION)
        return 0
    try:
        with OptemZoomController(a.host, a.port) as z:
            if a.cmd == "status":
                print("controller:", z.connect())
                st = z.read_status()
                print(f"position {st.position:.1f} steps  (~{z.calibration.steps_to_zoom(st.position):.2f}X estimated)")
                print(f"status {st.motion_status}  busy={st.busy} soft_cw={st.soft_cw} soft_ccw={st.soft_ccw} "
                      f"hard={st.hard_limit}  motor_enabled={st.motor_enabled}")
                print(f"controller soft limits [{st.soft_min}, {st.soft_max}] enabled={st.soft_limits_enabled}")
                return 0
            if a.cmd == "stop":
                z.stop()
                print("MoveStop sent")
                return 0
            # motion commands
            pos = z.get_position()
            if a.cmd == "steps":
                target = a.value
            elif a.cmd == "rel":
                target = pos + a.value
            else:
                target = round(z.calibration.zoom_to_steps(a.value))
            print(f"Current {pos:.1f} steps -> target {target:.1f} steps "
                  f"(~{z.calibration.steps_to_zoom(target):.2f}X estimated)")
            if not a.yes and input("Type MOVE to proceed: ").strip() != "MOVE":
                print("Aborted - nothing moved.")
                return 1
            try:
                final = z.move_to(target)
            except KeyboardInterrupt:
                z.stop()
                print("\nCtrl+C - MoveStop sent")
                return 2
            print(f"Arrived at {final:.1f} steps (~{z.calibration.steps_to_zoom(final):.2f}X estimated)")
            return 0
    except OptemError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
