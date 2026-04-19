import pytest
from rusheshour.core.repair import action_repair, _verify_repaired

pytestmark = pytest.mark.integration


def test_repair_moov_atom_missing_returns_unchanged(valid_mp4):
    """Retourne filepath inchangé sans appel ffmpeg si moov atom manquant."""
    prior = ["moov atom not found (the bitrate may be too high or might not be a valid file)"]
    result = action_repair(valid_mp4, prior)
    assert result == valid_mp4
    assert valid_mp4.exists()


def test_repair_valid_mp4_succeeds(valid_mp4):
    """Stratégie 1 (remux -c copy) réussit sur un MP4 valide."""
    result = action_repair(valid_mp4, prior_errors=[])
    assert result.exists()
    assert ".repair_tmp" not in result.name


def test_repair_result_replaces_original(valid_mp4):
    """Le fichier réparé prend le chemin de l'original."""
    original_path = valid_mp4
    result = action_repair(valid_mp4, prior_errors=[])
    assert result == original_path


def test_repair_no_temp_files_left(valid_mp4):
    """Aucun fichier .repair_tmp.* ne subsiste après succès."""
    action_repair(valid_mp4, prior_errors=[])
    assert list(valid_mp4.parent.glob("*.repair_tmp.*")) == []


def test_repair_result_is_readable(valid_mp4):
    """Le fichier réparé est lisible par ffprobe (durée > 0)."""
    result = action_repair(valid_mp4, prior_errors=[])
    assert _verify_repaired(result)


def test_repair_preserves_mkv_extension(valid_mkv):
    """Les stratégies sans réencodage préservent l'extension d'origine."""
    result = action_repair(valid_mkv, prior_errors=[])
    assert result.suffix == ".mkv"
    assert result.exists()
