import subprocess
from pathlib import Path


FFMPEG_ENCODE_FLAGS: list[str] = [
    "-c:v", "libx264",
    "-crf", "23",
    "-preset", "medium",
    "-c:a", "aac",
    "-b:a", "192k",
    "-movflags", "+faststart",
]


def action_convert_mp4(filepath: Path, output_dir: Path | None) -> Path:
    """
    Convertit filepath en MP4 H.264/AAC (CRF 23, preset medium).

    Placement du fichier converti :
      - output_dir défini : converti placé dans output_dir, original supprimé.
      - output_dir None   : converti remplace l'original dans son dossier.
                            Si l'original est déjà en .mp4, passage par un
                            fichier temporaire pour éviter l'écrasement en
                            cours de conversion.

    Retourne le chemin du fichier résultant, ou filepath si échec/annulation.
    """
    from rusheshour.cli.menus import confirm

    if output_dir is not None:
        output_path = output_dir / filepath.with_suffix(".mp4").name
    else:
        output_path = filepath.with_suffix(".mp4")

    use_temp  = (output_path.resolve() == filepath.resolve())
    work_path = filepath.with_suffix(".tmp_converting.mp4") if use_temp else output_path

    if work_path.exists() and not use_temp:
        if not confirm(f"'{work_path.name}' existe déjà. Écraser ?"):
            print("  Annulé.")
            return filepath

    print(f"\n  Conversion en cours -> {output_path.name}")
    print("  (H.264 / AAC, CRF 23 — peut prendre du temps)")

    cmd = ["ffmpeg", "-i", str(filepath)] + FFMPEG_ENCODE_FLAGS + ["-y", str(work_path)]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print("  [!] Échec de la conversion.")
        print(result.stderr[-800:])
        if work_path.exists():
            work_path.unlink()
        return filepath

    size = round(work_path.stat().st_size / 1024 / 1024, 2)

    if filepath.exists():
        filepath.unlink()

    if use_temp:
        work_path.rename(output_path)
        print(f"  ✓ Converti et remplacé : {output_path.name} ({size} Mo)")
    else:
        print(f"  ✓ Converti -> {output_path.name} ({size} Mo) — original supprimé.")

    return output_path
