from pathlib import Path


VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv",
    ".wmv", ".m4v", ".mpg", ".mpeg", ".ts",  ".mts",
    ".m2ts", ".3gp", ".ogv", ".vob", ".divx", ".xvid",
})


_ORPHAN_PATTERNS = ("*.repair_tmp.*", "*.tmp_converting.mp4")


def find_orphan_temps(
    root: Path,
    extra_dirs: list[Path] | None = None,
) -> list[Path]:
    """Retourne les fichiers temporaires orphelins laissés par un SIGKILL ffmpeg."""
    dirs = [root]
    if extra_dirs:
        dirs.extend(extra_dirs)
    seen: set[Path] = set()
    orphans: list[Path] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for pattern in _ORPHAN_PATTERNS:
            for path in d.rglob(pattern):
                resolved = path.resolve()
                if resolved not in seen and path.is_file():
                    seen.add(resolved)
                    orphans.append(path)
    return sorted(orphans)


def collect_videos(root_path: Path, exclude_dir: Path | None) -> list[Path]:
    """
    Retourne la liste triée des fichiers vidéo trouvés sous root_path.

    Les fichiers situés dans exclude_dir (et ses sous-dossiers) sont ignorés,
    ce qui permet de définir un dossier de destination dans l'arborescence
    source sans qu'il soit scanné.
    """
    videos: list[Path] = []
    for path in sorted(root_path.rglob("*")):
        if exclude_dir is not None:
            try:
                path.relative_to(exclude_dir)
                continue  # appartient au dossier exclu
            except ValueError:
                pass
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(path)
    return videos
