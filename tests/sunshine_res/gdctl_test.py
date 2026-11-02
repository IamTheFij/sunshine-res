from collections.abc import Generator
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from sunshine_res.errors import CurrentModeNotFound
from sunshine_res.errors import OutputNotFound
from sunshine_res.gdctl import Gdctl
from sunshine_res.resolution_manager import MonitorMode

GDCTL_TWO_MONITORS = """Monitors:
├──Monitor DP-1 (AOC 27")
│  ├──Vendor: AOC
│  ├──Product: Q27G2WG4
│  ├──Serial: 0x00000000
│  ├──Modes (6)
│  │   ├──2560x1440@143.912
│  │   │   ├──Dimension: 2560x1440
│  │   │   ├──Refresh rate: 143.912
│  │   │   ├──Preferred scale: 1.0
│  │   │   ├──Supported scales: [1.0, 1.25, 2.0]
│  │   │   └──Properties: (0)
│  │   ├──2560x1440@143.912+vrr
│  │   │   ├──Dimension: 2560x1440
│  │   │   ├──Refresh rate: 143.912
│  │   │   ├──Preferred scale: 1.0
│  │   │   ├──Supported scales: [1.0, 1.25, 2.0]
│  │   │   └──Properties: (2)
│  │   │       ├──is-current ⇒  yes
│  │   │       └──refresh-rate-mode ⇒  variable
│  │   ├──1920x1080@60.000
│  │   │   ├──Dimension: 1920x1080
│  │   │   ├──Refresh rate: 60.000
│  │   │   ├──Preferred scale: 1.0
│  │   │   ├──Supported scales: [1.0, 1.25, 2.0]
│  │   │   └──Properties: (0)
│  │   ├──1920x1080@60.000+vrr
│  │   │   ├──Dimension: 1920x1080
│  │   │   ├──Refresh rate: 60.000
│  │   │   ├──Preferred scale: 1.0
│  │   │   ├──Supported scales: [1.0, 1.25, 2.0]
│  │   │   └──Properties: (1)
│  │   │       └──refresh-rate-mode ⇒  variable
│  │   ├──1440x900@59.901
│  │   │   ├──Dimension: 1440x900
│  │   │   ├──Refresh rate: 59.901
│  │   │   ├──Preferred scale: 1.0
│  │   │   ├──Supported scales: [1.0, 2.0]
│  │   │   └──Properties: (0)
│  │   └──1440x900@59.901+vrr
│  │       ├──Dimension: 1440x900
│  │       ├──Refresh rate: 59.901
│  │       ├──Preferred scale: 1.0
│  │       ├──Supported scales: [1.0, 2.0]
│  │       └──Properties: (1)
│  │           └──refresh-rate-mode ⇒  variable
│  ├──Preferences
│  │   └──Backlight: None
│  └──Properties: (3)
│      ├──is-builtin ⇒  no
│      ├──color-mode ⇒  default
│      └──supported-color-modes ⇒  [default, bt2100]
└──Monitor HDMI-1 (Dell 24")
   ├──Vendor: DEL
   ├──Product: U2415
   ├──Serial: 0x00000001
   ├──Modes (1)
   │   └──1920x1200@59.950
   │       ├──Dimension: 1920x1200
   │       ├──Refresh rate: 59.950
   │       ├──Preferred scale: 1.0
   │       ├──Supported scales: [1.0]
   │       └──Properties: (1)
   │           └──is-current ⇒  yes
   ├──Preferences
   │   └──Backlight: None
   └──Properties: (2)
       ├──is-builtin ⇒  no
       └──color-mode ⇒  default

Logical monitors:
├──Logical monitor #1
│  ├──Position: (0, 0)
│  ├──Scale: 1.25
│  ├──Transform: normal
│  ├──Primary: yes
│  ├──Monitors: (1)
│  │   └──DP-1 (AOC 27")
│  └──Properties: (0)
└──Logical monitor #2
   ├──Position: (2048, 0)
   ├──Scale: 1.0
   ├──Transform: normal
   ├──Primary: no
   ├──Monitors: (1)
   │   └──HDMI-1 (Dell 24")
   └──Properties: (0)

Properties: (2)
├──layout-mode ⇒  logical
└──supports-changing-layout-mode ⇒  yes
"""


@pytest.fixture
def mock_check_output() -> Generator[MagicMock, None, None]:
    with patch("sunshine_res.gdctl.check_output") as mock:
        mock.return_value = GDCTL_TWO_MONITORS.encode()
        yield mock


@pytest.fixture
def mock_check_call() -> Generator[MagicMock, None, None]:
    with patch("sunshine_res.gdctl.check_call") as mock:
        yield mock


@pytest.fixture
def manager() -> Gdctl:
    return Gdctl(client_width=1280, client_height=800, client_fps=60)


def test_query_monitor_info(manager: Gdctl, mock_check_output: MagicMock) -> None:
    monitor_info = manager.query_monitor_info()

    mock_check_output.assert_called_once_with(
        ["gdctl", "show", "--modes", "--properties"]
    )
    assert monitor_info["output_name"] == "DP-1"
    assert monitor_info["hdr"] is False
    assert monitor_info["current_mode"] == MonitorMode(
        id="2560x1440@143.912+vrr", width=2560, height=1440, fps=143.912
    )
    # Only the VRR variants are offered, matching the current mode
    assert [m["id"] for m in monitor_info["modes"]] == [
        "2560x1440@143.912+vrr",
        "1920x1080@60.000+vrr",
        "1440x900@59.901+vrr",
    ]


def test_query_monitor_info_target_output(mock_check_output: MagicMock) -> None:
    manager = Gdctl(
        client_width=1280, client_height=800, client_fps=60, target_output="HDMI-1"
    )
    monitor_info = manager.query_monitor_info()

    assert monitor_info["output_name"] == "HDMI-1"
    assert monitor_info["current_mode"]["id"] == "1920x1200@59.950"
    assert len(monitor_info["modes"]) == 1


def test_query_monitor_info_display_not_found(mock_check_output: MagicMock) -> None:
    manager = Gdctl(
        client_width=1280, client_height=800, client_fps=60, target_output="HDMI-2"
    )
    with pytest.raises(
        OutputNotFound, match="Could not find output named HDMI-2. Check gdctl"
    ):
        _ = manager.query_monitor_info()


def test_query_monitor_info_current_mode_not_found(
    manager: Gdctl, mock_check_output: MagicMock
) -> None:
    mock_check_output.return_value = GDCTL_TWO_MONITORS.replace(
        "is-current ⇒  yes", "is-current ⇒  no"
    ).encode()
    with pytest.raises(CurrentModeNotFound, match="DP-1. Check gdctl"):
        _ = manager.query_monitor_info()


def test_query_monitor_info_hdr(manager: Gdctl, mock_check_output: MagicMock) -> None:
    mock_check_output.return_value = GDCTL_TWO_MONITORS.replace(
        "color-mode ⇒  default\n│", "color-mode ⇒  bt2100\n│"
    ).encode()
    assert manager.query_monitor_info()["hdr"] is True


def test_parse_logical_monitors(manager: Gdctl) -> None:
    state = manager.parse_gdctl(GDCTL_TWO_MONITORS)

    assert state["layout_mode"] == "logical"
    assert state["logical_monitors"] == [
        {
            "x": 0,
            "y": 0,
            "scale": 1.25,
            "transform": "normal",
            "primary": True,
            "connectors": ["DP-1"],
        },
        {
            "x": 2048,
            "y": 0,
            "scale": 1.0,
            "transform": "normal",
            "primary": False,
            "connectors": ["HDMI-1"],
        },
    ]
    assert state["monitors"]["DP-1"]["supported_color_modes"] == ["default", "bt2100"]


def test_apply_mode(
    manager: Gdctl, mock_check_output: MagicMock, mock_check_call: MagicMock
) -> None:
    manager.apply_mode(
        "DP-1",
        MonitorMode(id="1440x900@59.901+vrr", width=1440, height=900, fps=59.901),
    )

    # Scale 1.25 is not supported at 1440x900, so the preferred scale is used.
    # DP-1 shrinks from 2048 to 1440 logical pixels wide, so HDMI-1 moves left.
    mock_check_call.assert_called_once_with(
        [
            "gdctl",
            "set",
            "--logical-monitor",
            "--x",
            "0",
            "--y",
            "0",
            "--scale",
            "1.0",
            "--transform",
            "normal",
            "--primary",
            "--monitor",
            "DP-1",
            "--mode",
            "1440x900@59.901+vrr",
            "--color-mode",
            "default",
            "--logical-monitor",
            "--x",
            "1440",
            "--y",
            "0",
            "--scale",
            "1.0",
            "--transform",
            "normal",
            "--monitor",
            "HDMI-1",
            "--mode",
            "1920x1200@59.950",
        ]
    )


def test_apply_mode_keeps_supported_scale_and_sets_hdr(manager: Gdctl) -> None:
    state = manager.parse_gdctl(GDCTL_TWO_MONITORS)
    cmd = manager.build_set_command(
        state,
        "DP-1",
        MonitorMode(id="1920x1080@60.000+vrr", width=1920, height=1080, fps=60.0),
        hdr=True,
    )

    assert cmd[:16] == [
        "gdctl",
        "set",
        "--logical-monitor",
        "--x",
        "0",
        "--y",
        "0",
        "--scale",
        "1.25",
        "--transform",
        "normal",
        "--primary",
        "--monitor",
        "DP-1",
        "--mode",
        "1920x1080@60.000+vrr",
    ]
    assert cmd[16:18] == ["--color-mode", "bt2100"]
    # 1920 / 1.25 = 1536 logical pixels wide
    assert cmd[cmd.index("--logical-monitor", 3) + 2] == "1536"


def test_apply_mode_unknown_mode(manager: Gdctl) -> None:
    state = manager.parse_gdctl(GDCTL_TWO_MONITORS)
    with pytest.raises(ValueError, match="Mode 800x600@60.000 not available"):
        _ = manager.build_set_command(
            state,
            "DP-1",
            MonitorMode(id="800x600@60.000", width=800, height=600, fps=60.0),
            hdr=False,
        )


def test_do_selects_matching_aspect(
    manager: Gdctl,
    mock_check_output: MagicMock,
    mock_check_call: MagicMock,
    tmp_path,
) -> None:
    manager.last_mode = tmp_path / "last_mode.json"
    manager.do()

    cmd = mock_check_call.call_args.args[0]
    assert cmd[cmd.index("DP-1") + 2] == "1440x900@59.901+vrr"
    assert manager.last_mode.exists()
