from typing import NamedTuple

from sunshine_res.gen_edid import COMMON_REFRESH_RATES
from sunshine_res.gen_edid import COMMON_RESOLUTIONS
from sunshine_res.gen_edid import create_edid
from sunshine_res.gen_edid import interactive_mode

DISPLAY_NAME = "Sunshine Virtual Display"


class Edid(NamedTuple):
    output_file: str
    name: str
    edid: bytes


def generate_all_edids() -> list[Edid]:
    edids: list[Edid] = []

    for resolution in COMMON_RESOLUTIONS.values():
        for refresh_rate in COMMON_REFRESH_RATES.values():
            for enable_hdr in [False, True]:
                edid = create_edid(
                    width=resolution[1],
                    height=resolution[2],
                    refresh_rate=refresh_rate,
                    enable_hdr=enable_hdr,
                    display_name=DISPLAY_NAME,
                )
                output_file = f"{resolution[0]}_{resolution[1]}_{refresh_rate}Hz{'_HDR' if enable_hdr else ''}.bin"
                name = f"{resolution[0]}x{resolution[1]}@{refresh_rate}Hz{' HDR' if enable_hdr else ''}"
                edids.append(Edid(output_file, name, edid))

    return edids


def interractive_edid() -> Edid:
    print(
        f"When using auto mode, display name will be {DISPLAY_NAME}. The default here is to use 'Custom Display' as the display name, but you can change it to whatever you want."
    )
    width, height, refresh_rate, enable_hdr, display_name, output_file = (
        interactive_mode()
    )

    edid = create_edid(
        width=width,
        height=height,
        refresh_rate=refresh_rate,
        enable_hdr=enable_hdr,
        display_name=display_name,
    )

    return Edid(output_file, display_name, edid)


def write_edid(edid: Edid) -> None:
    with open(edid.output_file, "wb") as f:
        _ = f.write(edid.edid)
    print(f"EDID written to {edid.output_file} with name '{edid.name}'")


def create_virtual_display(interractive: bool = False) -> None:
    if interractive:
        edid = interractive_edid()
        write_edid(edid)
    else:
        edids = generate_all_edids()
        for edid in edids:
            write_edid(edid)
