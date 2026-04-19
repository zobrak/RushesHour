from rusheshour.core.probe import format_duration, is_already_mp4


def test_format_duration_seconds():
    assert format_duration(45) == "0m45s"


def test_format_duration_minutes():
    assert format_duration(252) == "4m12s"


def test_format_duration_hours():
    assert format_duration(3755) == "1h02m35s"


def test_is_already_mp4_true():
    info = {"format_name": "mp4", "video_codec": "h264"}
    assert is_already_mp4(info) is True


def test_is_already_mp4_true_avc():
    info = {"format_name": "mp4", "video_codec": "avc"}
    assert is_already_mp4(info) is True


def test_is_already_mp4_false_wrong_codec():
    info = {"format_name": "mp4", "video_codec": "hevc"}
    assert is_already_mp4(info) is False


def test_is_already_mp4_false_wrong_container():
    info = {"format_name": "matroska", "video_codec": "h264"}
    assert is_already_mp4(info) is False


def test_is_already_mp4_true_multi_format():
    # ffprobe returns "mov,mp4,m4a,3gp,3g2,mj2" for real .mp4 files
    info = {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "video_codec": "h264"}
    assert is_already_mp4(info) is True
