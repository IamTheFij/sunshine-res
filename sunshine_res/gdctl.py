import re
from subprocess import check_call
from subprocess import check_output
from typing import TypedDict
from typing import override

from sunshine_res.errors import CurrentModeNotFound
from sunshine_res.errors import OutputNotFound
from sunshine_res.resolution_manager import MonitorInfo
from sunshine_res.resolution_manager import MonitorMode
from sunshine_res.resolution_manager import ResolutionManager

HDR_COLOR_MODE = "bt2100"


class GdctlMode(TypedDict):
    mode: MonitorMode
    vrr: bool
    supported_scales: list[float]
    preferred_scale: float


class GdctlMonitor(TypedDict):
    connector: str
    modes: list[GdctlMode]
    current: GdctlMode | None
    color_mode: str
    supported_color_modes: list[str]


class GdctlLogicalMonitor(TypedDict):
    x: int
    y: int
    scale: float
    transform: str
    primary: bool
    connectors: list[str]


class GdctlState(TypedDict):
    monitors: dict[str, GdctlMonitor]
    logical_monitors: list[GdctlLogicalMonitor]
    layout_mode: str


def _tree_level(line: str) -> tuple[int, str]:
    """Split a gdctl tree line into its nesting level and text.

    gdctl draws each level 4 columns deeper, with the text starting 2
    columns after the level's branch character.
    """
    match = re.match(r"^([│ ├└─]*)(.*)$", line)
    assert match
    return (len(match.group(1)) - 2) // 4, match.group(2).strip()


def _parse_list(text: str) -> list[str]:
    return [item.strip() for item in text.strip("[]").split(",") if item.strip()]


class Gdctl(ResolutionManager):
    """Designed to work with gdctl, shipped with GNOME 48 and newer."""

    def parse_gdctl(self, out: str) -> GdctlState:
        state: GdctlState = {"monitors": {}, "logical_monitors": [], "layout_mode": ""}
        section = ""
        # Text of the current line and each of its ancestors, by tree level
        path: list[str] = []
        monitor: GdctlMonitor | None = None
        mode: GdctlMode | None = None
        logical: GdctlLogicalMonitor | None = None

        for line in out.split("\n"):
            if not line.strip():
                continue

            if line[0] not in "│ ├└":
                section = line.strip()
                path = []
                continue

            level, text = _tree_level(line)
            path = path[:level] + [text]
            parent = path[-2] if len(path) > 1 else ""

            if section == "Monitors:":
                if level == 0 and (m := re.match(r"^Monitor (\S+)", text)):
                    monitor = {
                        "connector": m.group(1),
                        "modes": [],
                        "current": None,
                        "color_mode": "default",
                        "supported_color_modes": [],
                    }
                    state["monitors"][monitor["connector"]] = monitor
                    mode = None
                elif monitor is None:
                    continue
                elif level == 2 and parent.startswith("Modes"):
                    m = re.match(r"^([0-9]+)x([0-9]+)@([0-9.]+)(\+vrr)?$", text)
                    if m:
                        mode = {
                            "mode": MonitorMode(
                                id=text,
                                width=int(m.group(1)),
                                height=int(m.group(2)),
                                fps=float(m.group(3)),
                            ),
                            "vrr": bool(m.group(4)),
                            "supported_scales": [],
                            "preferred_scale": 1.0,
                        }
                        monitor["modes"].append(mode)
                elif level == 2 and parent.startswith("Properties"):
                    if m := re.match(r"^color-mode ⇒\s*(\S+)", text):
                        monitor["color_mode"] = m.group(1)
                    elif m := re.match(r"^supported-color-modes ⇒\s*(.*)$", text):
                        monitor["supported_color_modes"] = _parse_list(m.group(1))
                elif level > 2 and mode is not None and path[1].startswith("Modes"):
                    if m := re.match(r"^Supported scales: (.*)$", text):
                        mode["supported_scales"] = [
                            float(s) for s in _parse_list(m.group(1))
                        ]
                    elif m := re.match(r"^Preferred scale: ([0-9.]+)$", text):
                        mode["preferred_scale"] = float(m.group(1))
                    elif re.match(r"^is-current ⇒\s*yes$", text):
                        monitor["current"] = mode

            elif section == "Logical monitors:":
                if level == 0 and text.startswith("Logical monitor"):
                    logical = {
                        "x": 0,
                        "y": 0,
                        "scale": 1.0,
                        "transform": "normal",
                        "primary": False,
                        "connectors": [],
                    }
                    state["logical_monitors"].append(logical)
                elif logical is None:
                    continue
                elif level == 1:
                    if m := re.match(r"^Position: \((-?[0-9]+), (-?[0-9]+)\)$", text):
                        logical["x"], logical["y"] = int(m.group(1)), int(m.group(2))
                    elif m := re.match(r"^Scale: ([0-9.]+)$", text):
                        logical["scale"] = float(m.group(1))
                    elif m := re.match(r"^Transform: (\S+)$", text):
                        logical["transform"] = m.group(1)
                    elif m := re.match(r"^Primary: (\S+)$", text):
                        logical["primary"] = m.group(1) == "yes"
                elif level == 2 and parent.startswith("Monitors"):
                    logical["connectors"].append(text.split(" ")[0])

            elif section.startswith("Properties"):
                if m := re.match(r"^layout-mode ⇒\s*(\S+)", text):
                    state["layout_mode"] = m.group(1)

        return state

    def query_state(self) -> GdctlState:
        out = check_output(["gdctl", "show", "--modes", "--properties"])
        return self.parse_gdctl(out.decode())

    def _select_monitor(self, state: GdctlState) -> GdctlMonitor:
        # Only consider monitors that are part of the current layout
        enabled = [c for lm in state["logical_monitors"] for c in lm["connectors"]]
        for connector, monitor in state["monitors"].items():
            if connector not in enabled:
                continue
            if self.target_output is None or self.target_output == connector:
                return monitor

        raise OutputNotFound("gdctl", self.target_output)

    @override
    def query_monitor_info(self) -> MonitorInfo:
        monitor = self._select_monitor(self.query_state())
        current = monitor["current"]
        if current is None:
            raise CurrentModeNotFound("gdctl", monitor["connector"])

        # gdctl lists each mode with and without VRR. Only offer the variants
        # matching the current VRR state so a resolution change keeps it as is.
        return MonitorInfo(
            output_name=monitor["connector"],
            hdr=monitor["color_mode"] == HDR_COLOR_MODE,
            modes=[m["mode"] for m in monitor["modes"] if m["vrr"] == current["vrr"]],
            current_mode=current["mode"],
        )

    @override
    def apply_mode(
        self, output_name: str, mode: MonitorMode, hdr: bool = False
    ) -> None:
        # gdctl modes should all have an ID
        assert mode["id"], "Expected an ID for the selected mode"

        _ = check_call(
            self.build_set_command(self.query_state(), output_name, mode, hdr)
        )

    def build_set_command(
        self, state: GdctlState, output_name: str, mode: MonitorMode, hdr: bool
    ) -> list[str]:
        """
        Build a gdctl set command that changes one monitor's mode.

        gdctl set replaces the whole layout, so every enabled logical monitor
        is passed back with its current settings. Monitors to the right of or
        below the changed one are shifted so the layout stays adjacent.
        """
        monitor = state["monitors"].get(output_name)
        if monitor is None or monitor["current"] is None:
            raise OutputNotFound("gdctl", output_name)

        new_mode = next(
            (m for m in monitor["modes"] if m["mode"]["id"] == mode["id"]), None
        )
        if new_mode is None:
            raise ValueError(f"Mode {mode['id']} not available on {output_name}")

        target = next(
            lm for lm in state["logical_monitors"] if output_name in lm["connectors"]
        )

        # Keep the scale if the new mode supports it, otherwise fall back to
        # the mode's preferred scale
        scale = target["scale"]
        if new_mode["supported_scales"] and scale not in new_mode["supported_scales"]:
            scale = new_mode["preferred_scale"]

        def layout_size(m: MonitorMode, s: float, transform: str) -> tuple[int, int]:
            w, h = m["width"], m["height"]
            if state["layout_mode"] == "logical":
                w, h = round(w / s), round(h / s)
            if transform in ("90", "270", "flipped-90", "flipped-270"):
                w, h = h, w
            return w, h

        old_w, old_h = layout_size(
            monitor["current"]["mode"], target["scale"], target["transform"]
        )
        new_w, new_h = layout_size(new_mode["mode"], scale, target["transform"])

        cmd = ["gdctl", "set"]
        for lm in state["logical_monitors"]:
            x, y, lm_scale = lm["x"], lm["y"], lm["scale"]
            if lm is target:
                lm_scale = scale
            else:
                if x >= target["x"] + old_w:
                    x += new_w - old_w
                if y >= target["y"] + old_h:
                    y += new_h - old_h

            cmd += ["--logical-monitor", "--x", str(x), "--y", str(y)]
            cmd += ["--scale", str(lm_scale), "--transform", lm["transform"]]
            if lm["primary"]:
                cmd.append("--primary")

            for connector in lm["connectors"]:
                mon = state["monitors"][connector]
                if connector == output_name:
                    mode_id = new_mode["mode"]["id"]
                    color_mode = mon["color_mode"]
                    if HDR_COLOR_MODE in mon["supported_color_modes"]:
                        color_mode = HDR_COLOR_MODE if hdr else "default"
                elif mon["current"] is not None:
                    mode_id = mon["current"]["mode"]["id"]
                    color_mode = mon["color_mode"]
                else:
                    raise CurrentModeNotFound("gdctl", connector)

                cmd += ["--monitor", connector, "--mode", str(mode_id)]
                if mon["supported_color_modes"]:
                    cmd += ["--color-mode", color_mode]

        return cmd
