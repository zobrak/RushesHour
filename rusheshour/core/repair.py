import json
import subprocess
from pathlib import Path

from rusheshour.core.convert import FFMPEG_ENCODE_FLAGS


REPAIR_STRATEGIES: list[dict] = [
    {
        "label":        "1/4 — Remuxage simple (-c copy)",
        "desc":         "Reconstruit le conteneur sans réencodage. "
                        "Corrige index manquant, atoms mal placés.",
        "input_flags":  [],
        "output_flags": ["-c", "copy"],
        "reencodes":    False,
    },
    {
        "label":        "2/4 — Remuxage + régénération timestamps (-fflags +genpts)",
        "desc":         "Recalcule les PTS/DTS corrompus ou absents. "
                        "Corrige les désynchronisations audio/vidéo.",
        "input_flags":  ["-fflags", "+genpts"],
        "output_flags": ["-c", "copy"],
        "reencodes":    False,
    },
    {
        "label":        "3/4 — Remuxage tolérant aux erreurs (-err_detect ignore_err)",
        "desc":         "Ignore les erreurs de flux, copie ce qui est lisible.",
        "input_flags":  ["-err_detect", "ignore_err"],
        "output_flags": ["-c", "copy"],
        "reencodes":    False,
    },
    {
        "label":        "4/4 — Réencodage de sauvetage (H.264/AAC)",
        "desc":         "Réencode entièrement. Récupère le maximum du contenu "
                        "lisible. Opération longue.",
        "input_flags":  [],
        "output_flags": FFMPEG_ENCODE_FLAGS,
        "reencodes":    True,
    },
]


def _run_repair_strategy(filepath: Path, strategy: dict, temp_path: Path) -> bool:
    """
    Exécute une stratégie de réparation ffmpeg et écrit le résultat dans
    temp_path.

    Retourne True si ffmpeg s'est terminé avec le code de retour 0.
    En cas d'échec, affiche les 5 dernières lignes de stderr et supprime
    temp_path s'il a été partiellement créé.
    """
    cmd = (
        ["ffmpeg", "-y"]
        + strategy["input_flags"]
        + ["-i", str(filepath)]
        + strategy["output_flags"]
        + [str(temp_path)]
    )
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, timeout=3600)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        print(f"    ✗ Échec : {tail}")
        if temp_path.exists():
            temp_path.unlink()
        return False
    return True


def _verify_repaired(temp_path: Path) -> bool:
    """
    Vérifie via ffprobe que temp_path est lisible et possède une durée > 0.

    Retourne True si le fichier passe la vérification.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-print_format", "json", "-show_format",
        str(temp_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data   = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0)) > 0
    except Exception:
        return False


def action_repair(filepath: Path, prior_errors: list[str]) -> Path:
    """
    Tente de réparer filepath via les stratégies de REPAIR_STRATEGIES,
    dans l'ordre (de la moins à la plus destructive).

    prior_errors : résultats de check_errors() déjà collectés — évite un
    second appel ffprobe pour détecter le moov atom manquant.

    Comportement :
      - L'original n'est jamais modifié tant qu'une stratégie n'a pas réussi
        et que le résultat n'a pas été vérifié par ffprobe.
      - Stratégies sans réencodage (reencodes=False) : extension originale
        conservée.
      - Stratégie avec réencodage (reencodes=True) : produit un .mp4.
      - Le fichier réparé remplace l'original dans son dossier courant.
      - Retourne le chemin résultant (réparé ou filepath inchangé si échec).

    Note : output_dir n'est pas géré ici. La réparation se fait sur place,
    avant la lecture ; le menu décide du placement final.
    """
    if any("moov atom not found" in e for e in prior_errors):
        print("\n  [!] Moov atom manquant — enregistrement interrompu avant finalisation.")
        print("      ffmpeg ne peut pas reconstruire l'index à partir de rien.")
        print("      Outil recommandé : untrunc  https://github.com/ponchio/untrunc")
        print("      (nécessite un fichier intact du même appareil/firmware)")
        return filepath

    print(f"\n  Réparation : {filepath.name}")
    print("  L'original ne sera modifié qu'en cas de succès vérifié.\n")

    original_suffix = filepath.suffix or ".mp4"
    repaired_path: Path | None = None

    for strategy in REPAIR_STRATEGIES:
        print(f"  [{strategy['label']}]")
        print(f"   {strategy['desc']}")

        tmp_suffix = ".mp4" if strategy["reencodes"] else original_suffix
        temp_path  = filepath.with_name(filepath.stem + ".repair_tmp" + tmp_suffix)

        if not _run_repair_strategy(filepath, strategy, temp_path):
            continue

        if not _verify_repaired(temp_path):
            print("    ✗ Fichier produit illisible ou durée nulle.")
            if temp_path.exists():
                temp_path.unlink()
            continue

        size = round(temp_path.stat().st_size / 1024 / 1024, 2)
        print(f"    ✓ Succès ({size} Mo)")
        repaired_path = temp_path
        break

    if repaired_path is None:
        print("\n  [!] Toutes les stratégies ont échoué. Original inchangé.")
        return filepath

    final_path = filepath.with_name(
        repaired_path.name.replace(".repair_tmp", "")
    )
    if final_path.exists() and final_path.resolve() != repaired_path.resolve():
        final_path.unlink()
    if filepath.exists():
        filepath.unlink()
    repaired_path.rename(final_path)

    print(f"  ✓ Réparé -> {final_path.name} (original remplacé)")
    return final_path
