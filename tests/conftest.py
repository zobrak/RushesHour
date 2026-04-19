import subprocess
import pytest
from pathlib import Path


def _make_video(path: Path) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=128x72:r=10:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
            "-c:a", "aac",
            "-shortest",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def valid_mp4(tmp_path) -> Path:
    return _make_video(tmp_path / "video.mp4")


@pytest.fixture
def valid_mkv(tmp_path) -> Path:
    return _make_video(tmp_path / "video.mkv")
