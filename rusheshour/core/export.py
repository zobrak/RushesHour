import subprocess
from pathlib import Path


def _fmt_clip_time(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"


def clip_output_path(
    filepath: Path,
    start: float,
    end: float,
    output_dir: Path | None,
) -> Path:
    """
    Retourne le chemin de sortie qu'utiliserait action_export_clip.

    Utile pour tester une collision avant de lancer l'export.
    """
    suffix   = f"_clip_{_fmt_clip_time(start)}-{_fmt_clip_time(end)}"
    out_name = filepath.stem + suffix + filepath.suffix
    out_dir  = output_dir if output_dir is not None else filepath.parent
    return out_dir / out_name


def action_export_clip(
    filepath: Path,
    start: float,
    end: float,
    output_dir: Path | None,
) -> Path:
    """
    Exporte le segment [start, end] de filepath vers un nouveau fichier.

    Utilise ffmpeg avec seek avant entrée (-ss avant -i) et stream copy
    (-c copy) : extraction rapide sans réencodage. Le point de départ est
    arrondi au keyframe précédent ; un écart de quelques frames est possible
    selon le GOP source.

    Le fichier produit conserve l'extension originale et porte le suffixe
    _clip_MMmSSs-MMmSSs (ex. video_clip_01m30s-02m45s.mkv).

    output_dir défini → clip placé dans output_dir ;
    output_dir None   → même dossier que l'original.

    Retourne le chemin du clip produit.
    Lève ValueError si end ≤ start.
    Lève subprocess.CalledProcessError si ffmpeg échoue.
    """
    duration = end - start
    if duration <= 0:
        raise ValueError(f"Durée invalide : end ({end:.3f}) ≤ start ({start:.3f})")

    out_path = clip_output_path(filepath, start, end, output_dir)

    cmd = [
        "ffmpeg",
        "-ss", str(start),
        "-i",  str(filepath),
        "-t",  str(duration),
        "-c",  "copy",
        "-avoid_negative_ts", "make_zero",
        "-y",
        str(out_path),
    ]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=3600)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, stderr=result.stderr
        )
    return out_path
