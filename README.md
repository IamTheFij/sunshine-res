# sunshine-res

**sunshine-res** is a small command‑line utility that automatically adjusts your display resolution and HDR settings to match a target resolution that your game or application expects. It works on modern Linux desktop environments that expose a standard way to query and set display modes.

## Installation

You can install sunshine-res system‑wide (or inside a virtualenv) with:

```bash
pipx install sunshine-res
```

The tool installs a console script called `sunshine-res` that can be invoked from anywhere.

## Usage

The utility accepts three commands:

| Command | Description |
|---------|-------------|
| `do` | Set the monitor to the target resolution (as specified by the environment variables below). |
| `undo` | Revert the monitor to the original mode that was active before the last `do`. |
| `auto` | Toggle between the two states. If a previous `do` was performed, `undo` will be run; otherwise `do` will be executed. This is the default if no command is given. |

### Configuring Sunshine

After installing sunshine-res, you must configure Sunshine to use the utility.

1. Open Sunshine and go to the Configuration tab (probably https://localhost:47990/config)
2. In the Command Preparations section, click "+ Add" to add a new command
3. Set the do and undo commands to `sunshine-res do` and `sunshine-res undo` respectively
4. Save

### Multiple outputs

Sunshine-res will only manage the resolution of a single display output. By default, it will use the first one present reported by the relevant control tool. This is probably fine for many users, but if you have multiple displays and require specifying a particular display, you can append `--target-output/-o` followed by the display name reported by the appropriate command line tool for your desktop environment.

Eg.
```bash
sunshine-res --target-output HDMI-2 auto
```

If you are unsure of what output name to use, look at the outputs listed by the appropriate tool for your desktop environement, in the [Supported Desktop Environments](#supported-desktop-environments) table.

### Supersampling

Rather than having the server match the client resolution exactly, a supersampling factor can be added to instruct the server to render higher resolution images than your client and allow the client to downscale them.

This can be done by adding the `--supersample` option to the `sunshine-res` command.

Eg.

```bash
sunshine-res --supersample 1.5 auto
```

This would attempt to render at 1.5× the target resolution, so if the target is 1920×1080, the server would render at the nearest resolution at or greater than 2880×1620 and the client would downscale to 1920×1080. Since the client may not support arbitrary resolutions, the server will choose the closest available mode that is at least as large as the supersampled resolution.

### Example

```bash
# Set resolution to 1920×1080 @ 60 Hz, HDR disabled
SUNSHINE_CLIENT_WIDTH=1920 SUNSHINE_CLIENT_HEIGHT=1080 SUNSHINE_CLIENT_FPS=60 SUNSHINE_CLIENT_HDR=false sunshine-res do

# Revert to original resolution
sunshine-res undo

# Toggle
sunshine-res
```

Environment variables are optional and typically set by Sunshine; defaults are:

- `SUNSHINE_CLIENT_WIDTH`  – 1920
- `SUNSHINE_CLIENT_HEIGHT` – 1080
- `SUNSHINE_CLIENT_FPS`    – 60
- `SUNSHINE_CLIENT_HDR`   – false

## Supported Desktop Environments

| Desktop | Implementation |
|---------|-----------------|
| KDE | Uses `kscreen-doctor` to query and set monitor modes. |
| COSMIC | Uses `cosmic-randr` to query and set monitor modes. |
| Gnome | Uses `gnome-randr` from [gnome-randr-rust](https://github.com/maxwellainatchi/gnome-randr-rust) if installed, otherwise `gdctl`, which ships with GNOME 48 and newer. |

The tool automatically detects the current desktop by inspecting the `XDG_CURRENT_DESKTOP`, `XDG_SESSION_DESKTOP`, or `SESSION_DESKTOP` environment variables. If no supported desktop is detected, the command will exit with an error.

## How It Works

1. **Detect Desktop** – The first step is to determine whether you are running KDE or Cosmic.
2. **Query Current Mode** – The relevant command (eg. `kscreen-doctor` or `cosmic-randr`) returns a description of the current monitor configuration.
3. **Find Matching Mode** – The tool searches the available modes for one that matches the target resolution and has the closest refresh rate that is not below the requested `SUNSHINE_CLIENT_FPS`.
4. **Apply Mode** – The chosen mode is applied with the same HDR setting you requested.
5. **Persist State** – The original monitor state is written to `~/.config/sunshine/last_mode.json` so that `undo` can restore it later.

## Common Errors & Troubleshooting

| Error | What it means | How to fix |
|-------|----------------|------------|
| `ERROR: Could not determine current desktop` | No desktop environment variable was found. | Make sure you are running the command from an active session. On some shells you may need to export `XDG_CURRENT_DESKTOP=KDE` or `COSMIC` manually. |
| `Could not find resolution manager for desktop <name>` | The desktop variable contains an unsupported value. | Check the spelling of the desktop name. Supported values are `KDE` and `COSMIC` and `GNOME`. |
| `Did not find mode matching <width>x<height> at <output>` | The monitor does not advertise the requested resolution. | Verify that the resolution is supported by your monitor or try a different resolution. |
| `Could not identify current mode` | The underlying command returned an unexpected format. | Ensure `cosmic-randr`, `gnome-randr`, `gdctl`, or `kscreen-doctor` is installed and working. Run the command manually (`cosmic-randr list --kdl`, `gnome-randr`, `gdctl show --modes --properties`, or `kscreen-doctor --json`) to confirm. |
| `Permission denied` | The command was unable to write to `~/.config/sunshine/last_mode.json`. | Verify that you have write permissions to `~/.config/sunshine`. |

If you encounter an unhandled exception, try running the command with the `-v` flag (if implemented) or inspect the stack trace. The project is open source, so feel free to file an issue.
