"""
Resolution Management Module

This module provides a system to dynamically adjust display resolution and HDR settings
based on the user's desktop environment (KDE or Cosmic). It supports command-line
operations to 'do' (apply a resolution), 'undo' (revert to original), or 'auto' (toggle
between modes). The module uses platform-specific tools (kscreen-doctor for KDE,
cosmic-randr for Cosmic) to interface with the display server.

Key Features:
- Auto-detects desktop environment (KDE/Cosmic)
- Manages resolution and HDR settings
- Persistent state tracking for 'undo' operations

Usage:
sunshine-res [do/undo/auto]
"""

import argparse
import os
import sys
from argparse import Namespace
from typing import NamedTuple
from typing import cast

from sunshine_res.cosmic import CosmicRandr
from sunshine_res.gnome import GnomeRandr
from sunshine_res.kde import KscreenDoctor
from sunshine_res.types import ResolutionManager
from sunshine_res.virtual_display import create_virtual_display

SUNSHINE_CLIENT_WIDTH = int(os.getenv("SUNSHINE_CLIENT_WIDTH", 1920))
SUNSHINE_CLIENT_HEIGHT = int(os.getenv("SUNSHINE_CLIENT_HEIGHT", 1080))
SUNSHINE_CLIENT_FPS = int(os.getenv("SUNSHINE_CLIENT_FPS", 60))
SUNSHINE_CLIENT_HDR = bool(os.getenv("SUNSHINE_CLIENT_HDR")) == True


DESKTOP_TO_CLASS: dict[str, type[ResolutionManager]] = {
    "KDE": KscreenDoctor,
    "COSMIC": CosmicRandr,
    "GNOME": GnomeRandr,
}


class SunshineResArgs(NamedTuple):
    command: str
    supersample: float
    target_output: str | None
    virtual_interactive: bool = False


def parse_args(sys_argv: list[str]) -> SunshineResArgs:
    parser = argparse.ArgumentParser(
        "sunshine-res", description="Sunshine Resolution Manager"
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    undo_parser = subparsers.add_parser(
        "undo", help="Revert to the original resolution"
    )
    do_parser = subparsers.add_parser("do", help="Apply the resolution change")
    auto_parser = subparsers.add_parser(
        "auto", help="Automatically apply or undo the resolution change"
    )

    for cmd_parser in [do_parser, auto_parser]:
        _ = cmd_parser.add_argument(
            "-s",
            "--supersample",
            type=float,
            default=1.0,
            help="Supersampling scale factor (default: 1.0, disabled)",
        )

        _ = cmd_parser.add_argument(
            "-o",
            "--target-output",
            type=str,
            default=None,
            help="Target output for resolution updates (default: first display)",
        )

    create_virtual_parser = subparsers.add_parser(
        "create_virtual",
        help="Create a virtual display with the specified resolution",
        description="This command generates a virtual display with a range of resolutions and refresh rates. By default, it will create a display with the name 'Sunshine Virtual Display'. You can specify custom parameters in interactive mode. It will likely require root permissions to write the EDID file to the correct location, so make sure to run with sudo if you encounter permission errors.",
    )

    _ = create_virtual_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode to specify custom resolution parameters",
    )

    parsed_args = parser.parse_args()
    return SunshineResArgs(
        command=cast(str, parsed_args.command),
        supersample=(
            cast(float, parsed_args.supersample)
            if hasattr(parsed_args, "supersample")
            else 1.0
        ),
        target_output=(
            cast(str | None, parsed_args.target_output)
            if hasattr(parsed_args, "target_output")
            else None
        ),
        virtual_interactive=(
            cast(bool, parsed_args.interactive)
            if hasattr(parsed_args, "interactive")
            else False
        ),
    )


def main() -> None:
    """Entry point for sunshine-res command line tool."""
    args = parse_args(sys.argv)

    # Get the currently listed desktop
    current_desktop = os.getenv(
        "XDG_CURRENT_DESKTOP",
        os.getenv("XDG_SESSION_DESKTOP", os.getenv("SESSION_DESKTOP")),
    )
    if not current_desktop:
        print("ERROR: Could not determine current desktop")
        exit(1)

    if args.command == "create_virtual":
        create_virtual_display(interractive=args.virtual_interactive)
        return

    # Find a manager class that matches
    manager: ResolutionManager
    for desktop in current_desktop.split(":"):
        if mc := DESKTOP_TO_CLASS.get(desktop.upper()):
            manager = mc(
                client_width=SUNSHINE_CLIENT_WIDTH,
                client_height=SUNSHINE_CLIENT_HEIGHT,
                client_fps=SUNSHINE_CLIENT_FPS,
                client_hdr=SUNSHINE_CLIENT_HDR,
                supersample_scale=args.supersample,
                target_output=args.target_output,
            )
            break
    else:
        print(f"Could not find resolution manager for desktop {current_desktop}")
        exit(1)

    # Execute command in given manager
    if args.command == "auto":
        manager.toggle()
    elif args.command == "do":
        manager.do()
    elif args.command == "undo":
        manager.undo()
    else:
        print(f"Unknown command {args.command}")
        exit(1)


if __name__ == "__main__":
    main()
