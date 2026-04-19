import pytest
from pathlib import Path
from rusheshour.core.export import clip_output_path, action_export_clip


# =============================================================================
# clip_output_path — tests unitaires (pas de ffmpeg)
# =============================================================================

def test_clip_output_path_same_dir_when_no_output_dir(tmp_path):
    src = tmp_path / "myrush.mp4"
    result = clip_output_path(src, 90.0, 165.0, None)
    assert result.parent == tmp_path


def test_clip_output_path_uses_output_dir(tmp_path):
    src = tmp_path / "myrush.mp4"
    out = tmp_path / "exports"
    result = clip_output_path(src, 90.0, 165.0, out)
    assert result.parent == out


def test_clip_output_path_preserves_stem(tmp_path):
    src = tmp_path / "interview_final.mkv"
    result = clip_output_path(src, 10.0, 20.0, None)
    assert result.stem.startswith("interview_final_clip_")


def test_clip_output_path_preserves_extension(tmp_path):
    for ext in (".mp4", ".mkv", ".mov", ".avi"):
        src = tmp_path / f"video{ext}"
        result = clip_output_path(src, 0.0, 5.0, None)
        assert result.suffix == ext


def test_clip_output_path_format_minutes(tmp_path):
    src = tmp_path / "v.mp4"
    # 1m30s → 2m45s
    result = clip_output_path(src, 90.0, 165.0, None)
    assert "_clip_01m30s-02m45s" in result.name


def test_clip_output_path_format_hours(tmp_path):
    src = tmp_path / "v.mp4"
    # 1h02m03s → 1h02m10s
    result = clip_output_path(src, 3723.0, 3730.0, None)
    assert "_clip_1h02m03s-1h02m10s" in result.name


def test_clip_output_path_start_zero(tmp_path):
    src = tmp_path / "v.mp4"
    result = clip_output_path(src, 0.0, 30.0, None)
    assert "_clip_00m00s-00m30s" in result.name


def test_clip_output_path_float_truncated_to_int(tmp_path):
    src = tmp_path / "v.mp4"
    # 90.9 should truncate to 90 = 01m30s, same as 90.0
    r_float = clip_output_path(src, 90.9, 165.7, None)
    r_int   = clip_output_path(src, 90.0, 165.0, None)
    assert r_float.name == r_int.name


# =============================================================================
# action_export_clip — validation sans ffmpeg
# =============================================================================

def test_export_invalid_range_raises(tmp_path):
    src = tmp_path / "v.mp4"
    src.touch()
    with pytest.raises(ValueError):
        action_export_clip(src, 60.0, 30.0, None)


def test_export_equal_start_end_raises(tmp_path):
    src = tmp_path / "v.mp4"
    src.touch()
    with pytest.raises(ValueError):
        action_export_clip(src, 30.0, 30.0, None)


# =============================================================================
# action_export_clip — tests d'intégration (ffmpeg requis)
# =============================================================================

pytestmark_integration = pytest.mark.integration


@pytest.mark.integration
def test_export_clip_creates_file(valid_mp4):
    result = action_export_clip(valid_mp4, 0.0, 1.0, None)
    assert result.exists()
    assert result.stat().st_size > 0


@pytest.mark.integration
def test_export_clip_same_dir_when_no_output_dir(valid_mp4):
    result = action_export_clip(valid_mp4, 0.0, 1.0, None)
    assert result.parent == valid_mp4.parent


@pytest.mark.integration
def test_export_clip_uses_output_dir(valid_mp4, tmp_path):
    out_dir = tmp_path / "clips"
    out_dir.mkdir()
    result = action_export_clip(valid_mp4, 0.0, 1.0, out_dir)
    assert result.parent == out_dir


@pytest.mark.integration
def test_export_clip_preserves_extension(valid_mkv):
    result = action_export_clip(valid_mkv, 0.0, 1.0, None)
    assert result.suffix == ".mkv"


@pytest.mark.integration
def test_export_clip_does_not_modify_original(valid_mp4):
    mtime_before = valid_mp4.stat().st_mtime
    action_export_clip(valid_mp4, 0.0, 1.0, None)
    assert valid_mp4.stat().st_mtime == mtime_before


@pytest.mark.integration
def test_export_clip_name_contains_timecodes(valid_mp4):
    result = action_export_clip(valid_mp4, 0.0, 1.0, None)
    assert "_clip_" in result.name
    assert result.suffix == ".mp4"
