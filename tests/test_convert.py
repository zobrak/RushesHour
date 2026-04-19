import pytest
from rusheshour.core.convert import action_convert_mp4
from rusheshour.core.probe import get_video_info

pytestmark = pytest.mark.integration


def test_convert_mkv_in_place(valid_mkv):
    """Convertit un MKV sur place : résultat en .mp4, original supprimé."""
    result = action_convert_mp4(valid_mkv, output_dir=None)
    assert result.suffix == ".mp4"
    assert result.parent == valid_mkv.parent
    assert result.exists()
    assert not valid_mkv.exists()


def test_convert_to_output_dir(valid_mkv, tmp_path):
    """Convertit vers output_dir : résultat dans le bon dossier, original supprimé."""
    out_dir = tmp_path / "sortie"
    out_dir.mkdir()
    result = action_convert_mp4(valid_mkv, output_dir=out_dir)
    assert result.parent == out_dir
    assert result.suffix == ".mp4"
    assert result.exists()
    assert not valid_mkv.exists()


def test_convert_mp4_in_place_uses_temp(valid_mp4):
    """Quand l'original est déjà .mp4, passe par .tmp_converting pour éviter
    l'écrasement en cours de conversion."""
    result = action_convert_mp4(valid_mp4, output_dir=None)
    assert result.exists()
    assert result.suffix == ".mp4"
    assert list(result.parent.glob("*.tmp_converting.mp4")) == []


def test_convert_no_temp_files_left(valid_mkv):
    """Aucun fichier .tmp_converting.mp4 ne subsiste après succès."""
    action_convert_mp4(valid_mkv, output_dir=None)
    assert list(valid_mkv.parent.glob("*.tmp_converting.mp4")) == []


def test_convert_result_is_valid_mp4(valid_mkv):
    """Le fichier converti est un MP4 H.264 lisible par ffprobe."""
    result = action_convert_mp4(valid_mkv, output_dir=None)
    info = get_video_info(result)
    assert "error" not in info
    assert info.get("video_codec") == "h264"
    assert "mp4" in info.get("format_name", "")
    assert info.get("duration_s", 0) > 0
