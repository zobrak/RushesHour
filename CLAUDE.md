# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_probe.py::test_format_duration_seconds -v

# Run integration tests (require ffmpeg)
pytest tests/ -v -m integration

# Run CLI
python sort_rush.py [options] /path/to/folder
python sort_rush.py --help

# Run GUI
python rusheshour_gui.py [dossier]

# Bootstrap venv — CLI (first launch)
bash run.sh /path/to/folder

# Bootstrap venv — GUI (also checks libmpv2/ffmpeg/ffprobe)
bash run_gui.sh [dossier]

# Bootstrap venv — GUI via run.sh
bash run.sh --gui [dossier]

# Build .deb package (Debian 13+)
bash packaging/build_deb.sh   # → dist/rusheshour_1.0.0_amd64.deb

# Install in dev mode
pip install -e ".[gui]"
```

## System dependencies

`mpv`, `libmpv2`, `ffmpeg` (includes `ffprobe`) must be installed at the OS level.  
`sudo apt install mpv libmpv2 ffmpeg`

## CLI options

| Option | Description |
|--------|-------------|
| `-d`, `--destination PATH` | Destination folder for processed files |
| `--no-repair` | Disable error detection and auto-repair |
| `--no-convert` | Disable MP4 conversion |
| `--no-menu` | Skip main menu, start processing directly |

Extended help: `--help-repair`, `--help-convert`, `--help-workflow`.

## GUI keyboard shortcuts

| Key | Action |
|-----|--------|
| `0` | Next — moves to destination if set |
| `1` | Skip (leave in place) |
| `2` | Rename |
| `3` | Move manually |
| `5` | Delete |
| `6` | Convert to MP4 |
| `7` | Replay |
| `E` | Export IN/OUT clip |
| `Space` | Pause / play |
| `F` | Toggle fullscreen |
| `Escape` | Exit fullscreen |
| `I` | Set IN marker (requires timeline focus) |
| `O` | Set OUT marker (requires timeline focus) |
| `Ctrl+O` | Open folder |
| `Ctrl+Q` | Quit |

## Architecture

The project is a video rushes sorting tool — two UIs sharing a common core.

```
rusheshour/
├── core/          # Pure logic — no Qt, no CLI
│   ├── session.py    # Session dataclass (root, output_dir, opt_repair, opt_convert)
│   ├── scanner.py    # collect_videos(), find_orphan_temps() — recursive walk, VIDEO_EXTENSIONS
│   ├── probe.py      # get_video_info(), check_errors(), is_already_mp4(), format_duration()
│   ├── repair.py     # action_repair(), REPAIR_STRATEGIES (4 ffmpeg strategies)
│   ├── convert.py    # action_convert_mp4(), FFMPEG_ENCODE_FLAGS
│   └── actions.py    # action_rename/move/delete, finalize()
├── cli/           # Interactive terminal loop
│   ├── parser.py     # build_parser(), help text constants
│   ├── menus.py      # ask(), confirm(), show_menu(), main_menu()
│   └── main.py       # check_dependencies(), process_video(), run_session(), main()
└── gui/           # PyQt6 + python-mpv
    ├── __init__.py   # launch_gui() — sets OpenGL 3.3 format before QApplication
    ├── main_window.py  # MainWindow, _FileInfoWorker (QThread for probe/error detection)
    ├── player_widget.py  # PlayerWidget(QOpenGLWidget) — mpv via MpvRenderContext
    ├── timeline_widget.py  # TimelineWidget — QPainter progress bar, seek on click, IN/OUT markers
    ├── file_panel.py   # FilePanel(QListWidget) — colour-coded file list
    └── dialogs.py      # RepairDialog, ConvertDialog, ExportDialog, OrphanCleanupDialog, DeleteConfirmDialog
```

**Entry points:** `sort_rush.py` (CLI shim) and `rusheshour_gui.py` (GUI shim) both delegate to the package.

**Session** is the shared mutable state passed from `launch_gui()` into `MainWindow` and down to all actions. The core functions operate on `Path` objects directly; `Session` carries options and destination.

## Wayland / X11

`QT_QPA_PLATFORM=xcb` is forced in `rusheshour_gui.py` before any Qt import. The GUI uses `MpvRenderContext` (OpenGL render API), not `wid=` — this renders into the Qt framebuffer and works under XWayland. Target environment: Debian 13 + KDE Plasma.

`os._exit()` is used instead of `sys.exit()` in `launch_gui()` because python-mpv creates a non-daemon event thread that would hang `sys.exit()`.

## Thread safety (mpv ↔ Qt)

mpv property observers run in the mpv internal thread. **Never update Qt widgets directly from an observer.** Always emit a `pyqtSignal` from the observer and connect it to the slot in the main thread. `PlayerWidget` uses a custom `QEvent` type to trigger `update()` from the mpv render callback.

`_FileInfoWorker` (in `main_window.py`) runs `get_video_info()` + `check_errors()` in a `QThread` to avoid blocking the GUI on file load; it emits `ready(index, info, errors)` back to the main thread.

## ffmpeg progress parsing

ffmpeg writes progress to stderr. Parse `time=HH:MM:SS.mmm` lines and compare against total duration (from ffprobe) to derive a percentage for progress bars:

```python
import re
pattern = re.compile(r"time=(\d+):(\d+):([\d.]+)")
```

## Temporary files

Failed/interrupted ffmpeg operations leave `*.repair_tmp.*` and `*.tmp_converting.mp4` orphans. These are cleaned up on success or clean failure, but survive SIGKILL.

## Tests

Unit tests cover pure functions only (no ffmpeg/mpv needed): `test_probe.py` (`format_duration`, `is_already_mp4`), `test_scanner.py` (`collect_videos`, `find_orphan_temps`), and `test_export.py` (`clip_output_path`). Integration tests requiring ffmpeg are marked `@pytest.mark.integration`.

## Roadmap (TODO.md)

All planned features complete as of v1.0.0. P1–P4 ✅.
