import pytest
from rusheshour.core.probe import format_duration, is_already_mp4, get_video_info


# =============================================================================
# format_duration
# =============================================================================

def test_format_duration_seconds():
    assert format_duration(45) == "0m45s"


def test_format_duration_minutes():
    assert format_duration(252) == "4m12s"


def test_format_duration_hours():
    assert format_duration(3755) == "1h02m35s"


# =============================================================================
# is_already_mp4 — tests unitaires (dicts mockés, pas de ffprobe)
# =============================================================================

def test_is_already_mp4_true_isom():
    info = {"major_brand": "isom", "video_codec": "h264"}
    assert is_already_mp4(info) is True


def test_is_already_mp4_true_mp41():
    info = {"major_brand": "mp41", "video_codec": "h264"}
    assert is_already_mp4(info) is True


def test_is_already_mp4_true_avc_brand():
    info = {"major_brand": "avc1", "video_codec": "avc"}
    assert is_already_mp4(info) is True


def test_is_already_mp4_false_mov():
    # MOV (QuickTime) — même format_name que MP4 mais major_brand différent
    info = {"major_brand": "qt  ", "video_codec": "h264"}
    assert is_already_mp4(info) is False


def test_is_already_mp4_false_wrong_codec():
    info = {"major_brand": "isom", "video_codec": "hevc"}
    assert is_already_mp4(info) is False


def test_is_already_mp4_false_no_brand_mkv():
    # MKV — pas d'atome ftyp, major_brand absent
    info = {"format_name": "matroska,webm", "video_codec": "h264"}
    assert is_already_mp4(info) is False


def test_is_already_mp4_false_no_brand_avi():
    info = {"format_name": "avi", "video_codec": "h264"}
    assert is_already_mp4(info) is False


def test_is_already_mp4_false_empty_info():
    assert is_already_mp4({}) is False


# =============================================================================
# is_already_mp4 — tests d'intégration (ffprobe réel)
# =============================================================================

@pytest.mark.integration
def test_is_already_mp4_true_real_mp4(valid_mp4):
    info = get_video_info(valid_mp4)
    assert "error" not in info
    assert is_already_mp4(info) is True


@pytest.mark.integration
def test_is_already_mp4_false_real_mkv(valid_mkv):
    info = get_video_info(valid_mkv)
    assert "error" not in info
    assert is_already_mp4(info) is False
