from pathlib import Path

from rusheshour.core.scanner import collect_videos, VIDEO_EXTENSIONS, find_orphan_temps


def test_collect_videos_empty_dir(tmp_path):
    result = collect_videos(tmp_path, exclude_dir=None)
    assert result == []


def test_collect_videos_finds_mp4(tmp_path):
    video = tmp_path / "clip.mp4"
    video.touch()
    result = collect_videos(tmp_path, exclude_dir=None)
    assert result == [video]


def test_collect_videos_excludes_non_video(tmp_path):
    (tmp_path / "notes.txt").touch()
    (tmp_path / "image.jpg").touch()
    result = collect_videos(tmp_path, exclude_dir=None)
    assert result == []


def test_collect_videos_excludes_dir(tmp_path):
    dest = tmp_path / "done"
    dest.mkdir()
    (dest / "already_sorted.mp4").touch()
    (tmp_path / "new.mkv").touch()
    result = collect_videos(tmp_path, exclude_dir=dest)
    assert len(result) == 1
    assert result[0].name == "new.mkv"


def test_collect_videos_recursive(tmp_path):
    sub = tmp_path / "subdir"
    sub.mkdir()
    (tmp_path / "a.mp4").touch()
    (sub / "b.mkv").touch()
    result = collect_videos(tmp_path, exclude_dir=None)
    names = {p.name for p in result}
    assert names == {"a.mp4", "b.mkv"}


def test_collect_videos_sorted(tmp_path):
    (tmp_path / "z.mp4").touch()
    (tmp_path / "a.mp4").touch()
    result = collect_videos(tmp_path, exclude_dir=None)
    assert [p.name for p in result] == ["a.mp4", "z.mp4"]


def test_collect_videos_case_insensitive_extension(tmp_path):
    (tmp_path / "clip.MP4").touch()
    result = collect_videos(tmp_path, exclude_dir=None)
    assert len(result) == 1


def test_collect_videos_all_known_extensions(tmp_path):
    for ext in VIDEO_EXTENSIONS:
        (tmp_path / f"file{ext}").touch()
    result = collect_videos(tmp_path, exclude_dir=None)
    assert len(result) == len(VIDEO_EXTENSIONS)


# ---------------------------------------------------------------------------
# find_orphan_temps
# ---------------------------------------------------------------------------

def test_find_orphan_temps_empty(tmp_path):
    assert find_orphan_temps(tmp_path) == []


def test_find_orphan_temps_finds_repair_tmp(tmp_path):
    f = tmp_path / "video.repair_tmp.mkv"
    f.touch()
    assert find_orphan_temps(tmp_path) == [f]


def test_find_orphan_temps_finds_converting(tmp_path):
    f = tmp_path / "video.tmp_converting.mp4"
    f.touch()
    assert find_orphan_temps(tmp_path) == [f]


def test_find_orphan_temps_ignores_normal_videos(tmp_path):
    (tmp_path / "video.mp4").touch()
    (tmp_path / "video.mkv").touch()
    assert find_orphan_temps(tmp_path) == []


def test_find_orphan_temps_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    f = sub / "video.repair_tmp.mkv"
    f.touch()
    assert find_orphan_temps(tmp_path) == [f]


def test_find_orphan_temps_extra_dirs(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    f1 = tmp_path / "a.repair_tmp.mkv"
    f2 = dest / "b.tmp_converting.mp4"
    f1.touch()
    f2.touch()
    result = find_orphan_temps(tmp_path, extra_dirs=[dest])
    assert set(result) == {f1, f2}


def test_find_orphan_temps_deduplicates(tmp_path):
    f = tmp_path / "video.repair_tmp.mkv"
    f.touch()
    result = find_orphan_temps(tmp_path, extra_dirs=[tmp_path])
    assert result == [f]


def test_find_orphan_temps_both_patterns(tmp_path):
    f1 = tmp_path / "a.repair_tmp.avi"
    f2 = tmp_path / "b.tmp_converting.mp4"
    f1.touch()
    f2.touch()
    result = find_orphan_temps(tmp_path)
    assert set(result) == {f1, f2}
