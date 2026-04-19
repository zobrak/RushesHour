import json
import subprocess
from pathlib import Path


def get_video_info(filepath: Path) -> dict:
    """
    Retourne un dictionnaire d'informations sur le fichier via ffprobe.

    Clés retournées (si disponibles) :
      container, format_name, size_mb, duration_s,
      video_codec, resolution, fps, audio_codec.

    En cas d'erreur ffprobe ou de JSON invalide, retourne {"error": <message>}.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(filepath),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(result.stdout)
    except Exception as exc:
        return {"error": str(exc)}

    info: dict = {}
    fmt = data.get("format", {})

    info["container"]    = fmt.get("format_long_name", fmt.get("format_name", "inconnu"))
    info["format_name"]  = fmt.get("format_name", "")
    info["major_brand"]  = fmt.get("tags", {}).get("major_brand", "")

    try:
        info["size_mb"] = round(int(fmt.get("size", 0)) / 1024 / 1024, 2)
    except (ValueError, TypeError):
        info["size_mb"] = 0.0

    try:
        info["duration_s"] = float(fmt.get("duration", 0))
    except (ValueError, TypeError):
        info["duration_s"] = 0.0

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and "video_codec" not in info:
            info["video_codec"] = stream.get("codec_name", "inconnu")
            info["resolution"]  = (
                f"{stream.get('width', '?')}x{stream.get('height', '?')}"
            )
            info["fps"] = stream.get("r_frame_rate", "?")
        elif codec_type == "audio" and "audio_codec" not in info:
            info["audio_codec"] = stream.get("codec_name", "inconnu")

    return info


_MP4_MAJOR_BRANDS: frozenset[str] = frozenset({
    "isom",   # ISO Base Media (standard MP4)
    "mp41",   # MPEG-4 Part 1
    "mp42",   # MPEG-4 Part 2
    "avc1",   # H.264 in MP4
    "iso2", "iso4", "iso5", "iso6",
    "M4V ",   # iTunes video  (4 chars, espace de padding obligatoire)
    "M4A ",   # iTunes audio
    "f4v ",   # Adobe Flash MP4
    "MSNV",   # Sony PSP
})


def is_already_mp4(info: dict) -> bool:
    """
    Retourne True si le fichier est en conteneur MP4 + H.264.

    Utilise major_brand (atome ftyp du header, extrait par ffprobe) pour
    distinguer MP4 ("isom", "mp41"…) de MOV ("qt  "), MKV, AVI, etc.
    Les fichiers sans major_brand (MKV, AVI…) retournent False.
    """
    major_brand = info.get("major_brand", "")
    video_codec = info.get("video_codec", "")
    return major_brand in _MP4_MAJOR_BRANDS and video_codec in ("h264", "avc")


def check_errors(filepath: Path) -> list[str]:
    """
    Lance ffprobe en mode -v error et collecte les lignes écrites sur stderr.

    Retourne une liste de chaînes (vide si aucune erreur détectée).
    ffprobe n'écrit sur stderr que si le fichier présente des anomalies
    (timestamps invalides, flux corrompus, atoms manquants, etc.).
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_format", "-show_streams",
        str(filepath),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return [line.strip() for line in result.stderr.splitlines() if line.strip()]
    except Exception as exc:
        return [f"ffprobe exception : {exc}"]


def format_duration(seconds: float) -> str:
    """Formate une durée en secondes en chaîne lisible (ex. 1h02m35s, 4m12s)."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h > 0 else f"{m}m{s:02d}s"


def print_video_info(filepath: Path, info: dict, index: int, total: int) -> None:
    """Affiche le bloc récapitulatif du fichier courant."""
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  [{index}/{total}]  {filepath.name}")
    print(f"  Chemin    : {filepath.parent}")
    if "error" in info:
        print(f"  [!] Erreur ffprobe : {info['error']}")
    else:
        print(f"  Conteneur : {info.get('container', '?')}")
        print(
            f"  Vidéo     : {info.get('video_codec', '?')}  "
            f"{info.get('resolution', '')}  {info.get('fps', '')} fps"
        )
        print(f"  Audio     : {info.get('audio_codec', '?')}")
        print(f"  Durée     : {format_duration(info.get('duration_s', 0.0))}")
        print(f"  Taille    : {info.get('size_mb', '?')} Mo")
    print(sep)
