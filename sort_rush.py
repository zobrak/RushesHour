#!/usr/bin/env python3
"""
sort_rush.py — Outil de tri de rush vidéo

Parcourt récursivement un dossier, lit chaque vidéo dans mpv, détecte et
propose de réparer les fichiers corrompus via ffmpeg, puis offre un menu
d'actions : passer au suivant, laisser sur place, renommer, déplacer,
supprimer, convertir en MP4. Un dossier de destination global peut être
défini au lancement pour un usage incrémental.

Usage :
  python3 sort_rush.py [options] /chemin/vers/dossier
  python3 sort_rush.py --help

Dépendances système :
  mpv      — lecture vidéo         (apt install mpv)
  ffmpeg   — conversion/réparation (apt install ffmpeg)
  ffprobe  — analyse des fichiers  (inclus dans le paquet ffmpeg)

Aucune dépendance Python externe.

-----------------------------------------------------------------------------
VERSION  : 0.7.1
-----------------------------------------------------------------------------

CHANGELOG
---------
v0.1.0  Parcours récursif, lecture mpv, infos ffprobe, menu basique,
        conversion MP4 (H.264/AAC), suppression avec confirmation.

v0.2.0  Dossier de destination global au lancement (création si absent,
        exclusion du scan si dans l'arborescence source). Confirmations
        o/n avec Entrée = oui par défaut.

v0.3.0  Réparation ffmpeg en 4 stratégies séquentielles : remuxage
        simple, regen timestamps, tolérance aux erreurs, réencodage de
        sauvetage. Vérification ffprobe du résultat. Détection moov atom
        manquant (non récupérable par ffmpeg).

v0.4.0  Réparation intégrée au flux principal : check_errors() avant
        chaque lecture, proposition de réparer si erreurs détectées.
        Refonte menu : [0] Suivant (défaut), [1] Ne rien faire.

v0.4.1  Option [6] Convertir en MP4 masquée si le fichier est déjà en
        MP4/H.264. Proposition de conversion au passage au suivant.

v0.5.0  Bandeau de lancement. Changelog complet en en-tête du script.

v0.5.1  Audit et refactoring complet : versioning SemVer corrigé,
        constantes en tête de module, 7 bug fixes, docstrings complètes,
        process_video() extrait, FFMPEG_ENCODE_FLAGS factorisé.

v0.6.0  Menu principal : Commencer / Destination / Options / Aide /
        Changelog. Menu options : toggle réparation/conversion (session
        uniquement). Menu fichier : [m] retour menu principal.
        Session dataclass. run_session() extrait de main().

v0.7.0  CLI complet via argparse : --destination, --no-repair,
        --no-convert, --no-menu, --version, --help-repair,
        --help-convert, --help-workflow.

v0.7.1  Audit v0.7.0 :
        - Bug fix : import field inutilisé supprimé
        - Bug fix : filepath.unlink() conditionné à filepath.exists()
          dans action_convert_mp4 (défense contre FileNotFoundError)
        - Bug fix : anti-pattern expression conditionnelle comme statement
          dans action_repair remplacé par if/else explicite
        - Bug fix : HELP_TEXT (aide interne [4]) corrigé — décrivait encore
          l'ancienne disposition [0]/[1] inversée depuis v0.7.0
        - Bug fix : textes HELP_CONVERT et HELP_WORKFLOW mis à jour pour
          refléter [0] Suivant / [1] Ne rien faire
        - Bug fix : textwrap.dedent corrigé dans build_parser (indentation
          de la première ligne alignée avec le reste)
        - Bug fix : confirm() dans setup_output_dir aligné sur la
          convention d'espacement du reste du script
        - Amélioration : process_video() propage le filepath modifié
          (renommé/déplacé) depuis show_menu vers run_session
-----------------------------------------------------------------------------
"""

import sys
import json
import shutil
import subprocess
import argparse
import textwrap
from dataclasses import dataclass
from pathlib import Path


# =============================================================================
# Constantes
# =============================================================================

VERSION = "0.7.1"

# Extensions vidéo reconnues lors du parcours récursif
VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv",
    ".wmv", ".m4v", ".mpg", ".mpeg", ".ts",  ".mts",
    ".m2ts", ".3gp", ".ogv", ".vob", ".divx", ".xvid",
})

# Paramètres d'encodage partagés par action_convert_mp4 et la stratégie 4
# de réparation (réencodage de sauvetage).
FFMPEG_ENCODE_FLAGS: list[str] = [
    "-c:v", "libx264",
    "-crf", "23",
    "-preset", "medium",
    "-c:a", "aac",
    "-b:a", "192k",
    "-movflags", "+faststart",
]

# Stratégies de réparation ffmpeg, par ordre croissant de destructivité.
# "reencodes" : True = produit un nouveau flux encodé (-> .mp4 forcé) ;
#               False = remuxage seul, extension originale conservée.
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

BANNER = f"""
+--------------------------------------------------------------+
|  triage_video  v{VERSION:<44}|
|  Tri interactif de rush vidéo                                |
+--------------------------------------------------------------+
|  Usage : sort_rush.py [options] /chemin/vers/dossier      |
|          sort_rush.py --help                              |
+--------------------------------------------------------------+
|  Nouveautés v0.7.1                                           |
|  - Audit complet v0.7.0 : 7 bug fixes, docs mises à jour    |
|  - Propagation du filepath modifié depuis show_menu          |
+--------------------------------------------------------------+
|  Dépendances : mpv  ffmpeg  ffprobe                          |
+--------------------------------------------------------------+
"""

# Aide interne affichée depuis le menu principal [4]
HELP_TEXT = """
+==============================================================+
|  AIDE — triage_video                                         |
+==============================================================+

DESCRIPTION
  Outil de tri interactif de rush vidéo. Parcourt récursivement
  un dossier, lit chaque fichier dans mpv, propose des actions
  de gestion et de conversion.

USAGE
  python3 sort_rush.py [options] /chemin/vers/dossier
  python3 sort_rush.py --help

DÉPENDANCES SYSTÈME
  mpv      — lecture vidéo         (apt install mpv)
  ffmpeg   — conversion/réparation (apt install ffmpeg)
  ffprobe  — analyse des fichiers  (inclus dans ffmpeg)

--------------------------------------------------------------
MENU PRINCIPAL
--------------------------------------------------------------
  [1] Commencer le tri
      Lance le traitement des vidéos du dossier source.
      Par défaut les fichiers restent à leur emplacement
      d'origine. Définir un dossier de destination [2] pour
      un tri incrémental : les fichiers traités (via [0]
      Suivant) y sont déplacés et exclus du scan suivant.
      Si on revient au menu principal en cours de session,
      le traitement reprend DEPUIS LE DÉBUT au prochain [1].

  [2] Destination
      Chemin vers le dossier où les fichiers traités seront
      déplacés. Créé s'il n'existe pas. S'il se trouve dans
      l'arborescence source, il est exclu du scan.

  [3] Options (session uniquement, non persistantes)
      - Réparation automatique : active/désactive la
        détection d'erreurs ffprobe et la proposition de
        réparation avant chaque lecture.
      - Conversion MP4 : active/désactive la proposition
        de conversion et l'option [6] dans le menu fichier.

  [4] Aide — affiche ce texte.

  [5] Version / Changelog — historique complet.

  [q] Quitter

--------------------------------------------------------------
MENU FICHIER (pendant le traitement)
--------------------------------------------------------------
  [0] Suivant  (défaut — Entrée)
      Déplace le fichier vers la destination globale si
      elle est définie, puis passe au fichier suivant.

  [1] Ne rien faire
      Laisse le fichier à son emplacement actuel. Ignore
      la destination globale pour ce fichier. Passe au
      fichier suivant.

  [2] Renommer
      Renomme dans le dossier courant. L'extension doit
      être incluse dans le nouveau nom.

  [3] Déplacer manuellement
      Saisir un chemin de destination. Le dossier est
      créé s'il n'existe pas.

  [4] Renommer + Déplacer manuellement
      Enchaîne [2] puis [3].

  [5] Supprimer
      Suppression définitive après confirmation. Non
      réversible.

  [6] Convertir en MP4
      Réencode en H.264 / AAC (CRF 23, preset medium).
      Le fichier converti remplace l'original ou est
      placé dans le dossier de destination si défini.
      Option masquée si le fichier est déjà en MP4/H.264
      ou si la conversion est désactivée dans [3] Options.

  [7] Rejouer
      Relance mpv sur le fichier courant.

  [m] Menu principal
      Interrompt le traitement et retourne au menu
      principal. Le traitement reprendra DEPUIS LE DÉBUT
      au prochain [1] Commencer.

  [q] Quitter le script

--------------------------------------------------------------
RÉPARATION AUTOMATIQUE
--------------------------------------------------------------
  Avant chaque lecture, ffprobe analyse le fichier.
  Si des erreurs sont détectées, 4 stratégies sont tentées
  dans l'ordre (de la moins à la plus destructive) :

  1. Remuxage simple (-c copy)
     Reconstruit le conteneur. Corrige index manquant
     et atoms mal placés. Rapide, non-destructif.

  2. Remuxage + regen timestamps (-fflags +genpts)
     Recalcule les PTS/DTS invalides. Corrige la
     désynchronisation audio/vidéo.

  3. Remuxage tolérant (-err_detect ignore_err)
     Ignore les erreurs de flux et copie ce qui est
     lisible.

  4. Réencodage de sauvetage (H.264/AAC)
     Réencode entièrement le fichier. Récupère le
     maximum du contenu lisible. Lent.

  L'original n'est jamais modifié tant que la réparation
  n'a pas été vérifiée par ffprobe (durée > 0).

  CAS NON RÉCUPÉRABLE :
  Moov atom manquant (enregistrement interrompu avant
  finalisation) : ffmpeg ne peut rien faire.
  Outil recommandé : untrunc
  https://github.com/ponchio/untrunc
  (nécessite un fichier intact du même appareil/firmware)

--------------------------------------------------------------
UTILISATION INCRÉMENTALE
--------------------------------------------------------------
  Pour éviter de retraiter les fichiers déjà triés lors
  d'une session ultérieure, définir un dossier de
  destination [2] ou --destination.

  [0] Suivant  -> déplace vers la destination, exclu du scan
                  au prochain lancement.
  [1] Ne rien faire -> reste dans la source, revu la fois
                       suivante.
  [5] Supprimer -> éliminé définitivement.

  Au prochain lancement sur le même dossier source avec la
  même destination, seuls les fichiers non encore traités
  seront présentés.

+==============================================================+
"""

# Aides CLI contextuelles (--help-repair, --help-convert, --help-workflow)
HELP_REPAIR = """
RÉPARATION AUTOMATIQUE (--help-repair)
=======================================
Avant chaque lecture, ffprobe analyse le fichier. Si des erreurs sont
détectées sur stderr (timestamps invalides, flux corrompus, atoms
manquants), 4 stratégies de réparation sont tentées dans l'ordre
croissant de destructivité. L'original n'est jamais modifié tant que le
résultat n'a pas été vérifié par ffprobe (durée > 0).

Stratégies :
  1. Remuxage simple (-c copy)
     Reconstruit le conteneur sans réencodage. Non-destructif, rapide.
     Corrige : index manquant, atoms mal placés (ftyp/moov/mdat).

  2. Remuxage + regen timestamps (-fflags +genpts -c copy)
     Recalcule les PTS/DTS invalides ou absents sans réencoder.
     Corrige : désynchronisation audio/vidéo, timestamps corrompus.

  3. Remuxage tolérant (-err_detect ignore_err -c copy)
     Ignore les erreurs de flux et copie tout ce qui est lisible.
     Corrige : flux partiellement corrompus, paquets isolés invalides.

  4. Réencodage de sauvetage (-c:v libx264 -c:a aac)
     Réencode entièrement. Récupère le maximum du contenu lisible.
     Lent. Produit toujours un .mp4.

CAS NON RÉCUPÉRABLE :
  Si le "moov atom" est manquant (enregistrement interrompu avant
  finalisation), ffmpeg ne peut pas reconstruire l'index. Le script le
  détecte et le signale.
  Outil recommandé : untrunc — https://github.com/ponchio/untrunc
  (nécessite un fichier intact du même appareil/firmware)

Désactiver : --no-repair  (ou option [3] du menu principal)
"""

HELP_CONVERT = """
CONVERSION MP4 (--help-convert)
================================
Convertit le fichier source en MP4 conteneur, H.264 vidéo, AAC audio.
Paramètres appliqués :
  -crf 23          Qualité constante. 18 = quasi-lossless, 28 = réduit.
  -preset medium   Vitesse d'encodage. Alternatives : ultrafast,
                   superfast, veryfast, faster, fast, slow, slower,
                   veryslow.
  -b:a 192k        Débit audio AAC.
  -movflags +faststart  Index en début de fichier (streaming HTTP).

Placement du fichier converti :
  - Avec destination globale : converti placé dans la destination,
    original supprimé.
  - Sans destination : remplace l'original dans son dossier.
    Si l'original est déjà en .mp4, un fichier temporaire est utilisé
    pour éviter l'écrasement en cours de conversion.

La conversion est proposée :
  - Manuellement via [6] dans le menu fichier.
  - Automatiquement lors de [0] Suivant ou [1] Ne rien faire,
    si le fichier n'est pas déjà en MP4/H.264.
  - L'option [6] est masquée si le fichier est déjà en MP4/H.264.

Désactiver : --no-convert  (ou option [3] du menu principal)
"""

HELP_WORKFLOW = """
UTILISATION INCRÉMENTALE (--help-workflow)
==========================================
Par défaut, les fichiers restent à leur emplacement d'origine. Si on
relance le script, tous les fichiers sont présentés à nouveau.

Pour un usage incrémental (éviter de revoir les fichiers déjà triés) :

  1. Définir un dossier de destination :
       --destination /chemin/dest
       ou option [2] du menu principal.

  2. Utiliser [0] Suivant pour les fichiers à conserver ou convertir.
     Ils sont déplacés vers la destination et exclus du scan suivant.

  3. Utiliser [1] Ne rien faire pour les fichiers à revoir plus tard.
     Ils restent dans la source et seront présentés au prochain lancement.

  4. Utiliser [5] Supprimer pour éliminer définitivement les mauvaises
     prises.

Au prochain lancement sur le même dossier source avec la même destination,
seuls les fichiers non encore traités seront présentés.

Note : si la destination est dans l'arborescence source, elle est
automatiquement exclue du scan.
"""


# =============================================================================
# État de session
# =============================================================================

@dataclass
class Session:
    """
    Encapsule l'état mutable d'une session de triage.

    Attributes
    ----------
    root : Path
        Dossier source à parcourir récursivement.
    output_dir : Path | None
        Dossier de destination global. None = fichiers laissés sur place.
    opt_repair : bool
        Si True, check_errors() est appelé avant chaque lecture et une
        réparation est proposée si des anomalies sont détectées.
    opt_convert : bool
        Si True, l'option de conversion MP4 est disponible dans le menu
        fichier et une proposition est faite au passage au suivant.
    """
    root:        Path
    output_dir:  Path | None = None
    opt_repair:  bool        = True
    opt_convert: bool        = True


# =============================================================================
# Vérification des dépendances
# =============================================================================

def check_dependencies() -> None:
    """Vérifie la présence des outils système requis. Quitte si l'un manque."""
    missing = [t for t in ("mpv", "ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        print(f"\n  [ERREUR] Outil(s) manquant(s) : {', '.join(missing)}")
        print("  Installe avec : sudo apt install mpv ffmpeg")
        sys.exit(1)


# =============================================================================
# Collecte des fichiers vidéo
# =============================================================================

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


# =============================================================================
# Analyse ffprobe
# =============================================================================

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

    info["container"]   = fmt.get("format_long_name", fmt.get("format_name", "inconnu"))
    info["format_name"] = fmt.get("format_name", "")

    # size et duration sont des chaînes dans la sortie ffprobe — cast sécurisé
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


def is_already_mp4(info: dict) -> bool:
    """
    Retourne True si le fichier est déjà encodé en conteneur MP4 + H.264.

    format_name peut contenir plusieurs valeurs séparées par des virgules
    (ex. "mov,mp4,m4a,3gp,3g2,mj2") ; on ne teste que le premier token.
    """
    first_fmt   = info.get("format_name", "").split(",")[0].strip()
    video_codec = info.get("video_codec", "")
    return first_fmt == "mp4" and video_codec in ("h264", "avc")


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


# =============================================================================
# Lecture mpv
# =============================================================================

def play_video(filepath: Path) -> None:
    """Lance mpv sur filepath et bloque jusqu'à la fin de la lecture."""
    print(f"\n  >> {filepath.name}")
    print("  (Ferme la fenêtre mpv ou appuie sur Q pour accéder au menu)")
    subprocess.run(["mpv", str(filepath)], check=False)


# =============================================================================
# Utilitaires de saisie
# =============================================================================

def ask(prompt: str) -> str:
    """Lit une ligne sur stdin. Quitte proprement sur Ctrl+C."""
    try:
        return input(prompt).strip()
    except KeyboardInterrupt:
        print("\n\n  Interruption. Fin du script.")
        sys.exit(0)


def confirm(prompt: str, default_yes: bool = True) -> bool:
    """
    Affiche une question o/n et retourne True si l'utilisateur confirme.

    default_yes=True  -> Entrée seul = oui  [O/n]
    default_yes=False -> Entrée seul = non  [o/N]
    """
    hint = "[O/n]" if default_yes else "[o/N]"
    rep = ask(f"  {prompt} {hint} : ").lower()
    return default_yes if rep == "" else rep == "o"


# =============================================================================
# Actions sur les fichiers
# =============================================================================

def action_rename(filepath: Path) -> Path:
    """
    Renomme le fichier dans son dossier courant.

    Retourne le nouveau Path, ou filepath inchangé si annulé ou si le nom
    cible existe déjà.
    """
    print(f"\n  Nom actuel : {filepath.name}")
    new_name = ask("  Nouveau nom (avec extension, vide = annuler) : ")
    if not new_name:
        print("  Annulé.")
        return filepath
    new_path = filepath.parent / new_name
    if new_path.exists():
        print(f"  [!] '{new_name}' existe déjà. Annulé.")
        return filepath
    filepath.rename(new_path)
    print(f"  ✓ Renommé -> {new_name}")
    return new_path


def action_move_to(filepath: Path, dest_dir: Path) -> Path:
    """
    Déplace filepath vers dest_dir (chemin déjà résolu).

    En cas de conflit de nom dans la destination, propose d'écraser.
    Retourne le nouveau Path, ou filepath inchangé si annulé.
    """
    new_path = dest_dir / filepath.name
    if new_path.exists():
        if not confirm(f"'{filepath.name}' existe déjà dans la destination. Écraser ?"):
            print("  Annulé.")
            return filepath
    shutil.move(str(filepath), str(new_path))
    print(f"  ✓ Déplacé -> {new_path}")
    return new_path


def action_move_manual(filepath: Path) -> Path:
    """
    Déplace le fichier vers un dossier saisi par l'utilisateur.

    Propose de créer le dossier s'il n'existe pas.
    Retourne le nouveau Path, ou filepath inchangé si annulé.
    """
    print(f"\n  Emplacement actuel : {filepath.parent}")
    dest_str = ask("  Dossier de destination (vide = annuler) : ")
    if not dest_str:
        print("  Annulé.")
        return filepath
    dest_dir = Path(dest_str).expanduser().resolve()
    if not dest_dir.is_dir():
        if not confirm(f"Dossier inexistant. Créer '{dest_dir}' ?"):
            print("  Annulé.")
            return filepath
        dest_dir.mkdir(parents=True, exist_ok=True)
    return action_move_to(filepath, dest_dir)


def action_delete(filepath: Path) -> bool:
    """
    Supprime le fichier après confirmation explicite.

    Retourne True si la suppression a eu lieu, False si annulée.
    """
    print(f"\n  /!\\ SUPPRESSION DÉFINITIVE : {filepath.name}")
    if confirm("Confirmer la suppression ?"):
        filepath.unlink()
        print("  ✓ Fichier supprimé.")
        return True
    print("  Annulé.")
    return False


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
    if output_dir is not None:
        output_path = output_dir / filepath.with_suffix(".mp4").name
    else:
        output_path = filepath.with_suffix(".mp4")

    # L'original est déjà en .mp4 et on reste dans le même dossier :
    # output_path == filepath -> temporaire requis pour éviter l'auto-écrasement.
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

    # Suppression de l'original (conditionné à son existence)
    if filepath.exists():
        filepath.unlink()

    if use_temp:
        work_path.rename(output_path)
        print(f"  ✓ Converti et remplacé : {output_path.name} ({size} Mo)")
    else:
        print(f"  ✓ Converti -> {output_path.name} ({size} Mo) — original supprimé.")

    return output_path


def finalize(filepath: Path, output_dir: Path | None) -> Path:
    """
    Déplace filepath vers output_dir si celui-ci est défini et que le fichier
    ne s'y trouve pas encore.

    Retourne le chemin final du fichier (déplacé ou inchangé).
    """
    if output_dir is None or not filepath.exists():
        return filepath
    try:
        filepath.relative_to(output_dir)
        return filepath  # déjà dans la destination
    except ValueError:
        pass
    return action_move_to(filepath, output_dir)


# =============================================================================
# Réparation vidéo
# =============================================================================

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
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
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
    # Suppression de l'éventuel conflit de nom, puis de l'original
    if final_path.exists() and final_path.resolve() != repaired_path.resolve():
        final_path.unlink()
    if filepath.exists():
        filepath.unlink()
    repaired_path.rename(final_path)

    print(f"  ✓ Réparé -> {final_path.name} (original remplacé)")
    return final_path


# =============================================================================
# Menu fichier (pendant le traitement)
# =============================================================================

def show_menu(
    filepath: Path,
    info: dict,
    session: Session,
) -> tuple[str, Path]:
    """
    Affiche le menu d'actions pour le fichier courant et traite le choix.

    Retourne un tuple (action, filepath) :
      'next'    -> passer au suivant, avec déplacement vers output_dir ([0]).
      'skip'    -> passer au suivant sans déplacer ([1]).
      'deleted' -> fichier supprimé (filepath est un chemin fantôme).
      'menu'    -> retour au menu principal demandé par l'utilisateur.

    Le filepath retourné reflète tout renommage ou déplacement effectué
    avant la sortie du menu, y compris en cas de retour menu ou de
    suppression.
    """
    # Calculé une seule fois : ne change pas sauf après [6], qui sort du menu.
    mp4     = is_already_mp4(info)
    convert = session.opt_convert and not mp4

    while True:
        dest_label = str(session.output_dir) if session.output_dir else "non définie"
        print("\n  .- Actions " + "-" * 50)
        print("  |  [0] Suivant        - déplace vers destination si définie  (défaut)")
        print("  |  [1] Ne rien faire  - laisse le fichier où il est")
        print("  |  [2] Renommer")
        print("  |  [3] Déplacer manuellement")
        print("  |  [4] Renommer + Déplacer manuellement")
        print("  |  [5] Supprimer")
        if convert:
            print("  |  [6] Convertir en MP4")
        print("  |  [7] Rejouer")
        print("  |  [m] Menu principal")
        print("  |  [q] Quitter le script")
        print(f"  '- Destination : {dest_label}")

        choice = ask("\n  Choix [0] : ") or "0"

        if choice == "0":
            if convert and confirm(
                "Convertir en MP4 avant de passer au suivant ?", default_yes=False
            ):
                filepath = action_convert_mp4(filepath, session.output_dir)
            else:
                filepath = finalize(filepath, session.output_dir)
            return ("next", filepath)

        elif choice == "1":
            if convert and confirm(
                "Convertir en MP4 avant de passer au suivant ?", default_yes=False
            ):
                filepath = action_convert_mp4(filepath, session.output_dir)
            return ("skip", filepath)

        elif choice == "2":
            filepath = action_rename(filepath)

        elif choice == "3":
            filepath = action_move_manual(filepath)

        elif choice == "4":
            filepath = action_rename(filepath)
            if filepath.exists():
                filepath = action_move_manual(filepath)

        elif choice == "5":
            if action_delete(filepath):
                return ("deleted", filepath)

        elif choice == "6":
            if not convert:
                print("  Option non disponible.")
            else:
                filepath = action_convert_mp4(filepath, session.output_dir)
                return ("next", filepath)

        elif choice == "7":
            play_video(filepath)

        elif choice.lower() == "m":
            print("  Retour au menu principal.")
            return ("menu", filepath)

        elif choice.lower() == "q":
            print("\n  Fin du script.")
            sys.exit(0)

        else:
            print("  Choix invalide.")


# =============================================================================
# Traitement d'un fichier
# =============================================================================

def process_video(
    filepath: Path,
    index: int,
    total: int,
    session: Session,
) -> tuple[str, Path]:
    """
    Traite un fichier vidéo de bout en bout :
      1. Affiche les informations ffprobe.
      2. Si opt_repair actif : détecte les erreurs et propose une réparation.
      3. Lance la lecture mpv.
      4. Présente le menu d'actions.

    Retourne le tuple (action, filepath) de show_menu, où filepath reflète
    tout renommage ou déplacement effectué pendant la session du fichier.
    Les valeurs d'action possibles : 'next', 'skip', 'deleted', 'menu'.
    """
    info = get_video_info(filepath)
    print_video_info(filepath, info, index, total)

    # --- Détection d'erreurs et réparation optionnelle --------------------
    if session.opt_repair:
        errors = check_errors(filepath)
        if errors:
            print("\n  /!\\ Erreurs détectées par ffprobe :")
            for line in errors[:10]:
                print(f"    {line}")
            if len(errors) > 10:
                print(f"    ... ({len(errors) - 10} ligne(s) supplémentaire(s))")
            if confirm("Tenter une réparation avant lecture ?", default_yes=True):
                # prior_errors transmis pour éviter un second appel ffprobe
                filepath = action_repair(filepath, prior_errors=errors)
                info = get_video_info(filepath)
        else:
            print("  ✓ Aucune erreur détectée.")

    # --- Lecture ----------------------------------------------------------
    play_video(filepath)

    # --- Menu -------------------------------------------------------------
    return show_menu(filepath, info, session)


# =============================================================================
# Boucle de traitement
# =============================================================================

def run_session(session: Session) -> str:
    """
    Parcourt les vidéos du dossier source et traite chacune via process_video.

    Retourne :
      'done' -> toutes les vidéos ont été traitées.
      'menu' -> l'utilisateur a demandé le retour au menu principal.
    """
    videos = collect_videos(session.root, exclude_dir=session.output_dir)
    if not videos:
        print(f"\n  Aucune vidéo trouvée dans : {session.root}")
        return "done"

    total = len(videos)
    print(f"\n  {total} vidéo(s) trouvée(s) dans {session.root}")
    if session.output_dir:
        print(f"  Destination : {session.output_dir}")
    repair_label  = "active"     if session.opt_repair  else "désactivée"
    convert_label = "active"     if session.opt_convert else "désactivée"
    print(f"  Réparation : {repair_label}  |  Conversion : {convert_label}")

    for index, video in enumerate(videos, start=1):
        if not video.exists():
            # Fichier déplacé ou supprimé lors d'une action précédente
            continue
        action, _ = process_video(video, index, total, session)
        if action == "menu":
            return "menu"

    print("\n  ✓ Toutes les vidéos ont été traitées.")
    return "done"


# =============================================================================
# Configuration du dossier de destination
# =============================================================================

def setup_output_dir(current: Path | None = None) -> Path | None:
    """
    Invite l'utilisateur à définir (ou redéfinir) le dossier de destination.

    current : valeur actuellement définie, affichée à titre indicatif.
              Si l'utilisateur annule la saisie, current est conservé.
    Si le dossier saisi n'existe pas, propose de le créer.
    Retourne le Path résolu, ou current si l'utilisateur annule.
    """
    if current:
        print(f"\n  Destination actuelle : {current}")
    print("  Entrez le chemin du dossier de destination (vide = annuler) :")
    dest_str = ask("  Chemin : ")
    if not dest_str:
        print("  Annulé.")
        return current

    dest_dir = Path(dest_str).expanduser().resolve()

    if not dest_dir.exists():
        if confirm(f"Dossier inexistant. Créer '{dest_dir}' ?"):
            dest_dir.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Dossier créé : {dest_dir}")
        else:
            print("  Annulé.")
            return current
    elif not dest_dir.is_dir():
        print(f"  [!] '{dest_dir}' existe mais n'est pas un dossier. Annulé.")
        return current

    print(f"  ✓ Destination : {dest_dir}")
    return dest_dir


# =============================================================================
# Menu options
# =============================================================================

def menu_options(session: Session) -> None:
    """
    Affiche le menu des options de session et permet de basculer
    la réparation automatique et la conversion MP4.

    Les modifications sont appliquées directement sur l'objet session.
    Elles sont actives uniquement pour la session en cours (non persistantes).
    """
    while True:
        r_label = "active     [O/n]" if session.opt_repair  else "désactivée [o/N]"
        c_label = "active     [O/n]" if session.opt_convert else "désactivée [o/N]"
        print("\n  .- Options de session " + "-" * 38)
        print(f"  |  [1] Réparation automatique : {r_label}")
        print(f"  |  [2] Conversion MP4          : {c_label}")
        print("  |  [r] Retour")
        print("  '- (Options non persistantes — session uniquement)")

        choice = ask("\n  Choix : ")

        if choice == "1":
            session.opt_repair = not session.opt_repair
            state = "activée" if session.opt_repair else "désactivée"
            print(f"  Réparation automatique : {state}")

        elif choice == "2":
            session.opt_convert = not session.opt_convert
            state = "activée" if session.opt_convert else "désactivée"
            print(f"  Conversion MP4 : {state}")

        elif choice.lower() == "r":
            return

        else:
            print("  Choix invalide.")


# =============================================================================
# Menu principal
# =============================================================================

def main_menu(session: Session) -> None:
    """
    Affiche le menu principal et dispatche vers les sous-menus ou le
    traitement. Boucle jusqu'à ce que l'utilisateur quitte.

    L'objet session est modifié en place (output_dir, options).
    """
    while True:
        dest_label = str(session.output_dir) if session.output_dir else "non définie"
        r_label    = "on"  if session.opt_repair  else "off"
        c_label    = "on"  if session.opt_convert else "off"

        print("\n  .- Menu principal " + "-" * 42)
        print("  |  [1] Commencer le tri")
        print(f"  |  [2] Destination : {dest_label}")
        print(f"  |  [3] Options     : réparation={r_label}  conversion={c_label}")
        print("  |  [4] Aide")
        print("  |  [5] Version / Changelog")
        print("  |  [q] Quitter")
        print("  '- " + "-" * 57)

        choice = ask("\n  Choix : ")

        if choice == "1":
            result = run_session(session)
            if result == "done":
                print("\n  Session terminée.")

        elif choice == "2":
            session.output_dir = setup_output_dir(current=session.output_dir)

        elif choice == "3":
            menu_options(session)

        elif choice == "4":
            print(HELP_TEXT)

        elif choice == "5":
            # Extrait dynamiquement le bloc CHANGELOG du docstring du module
            doc = __doc__ or ""
            in_changelog = False
            lines: list[str] = []
            for line in doc.splitlines():
                if line.strip().startswith("CHANGELOG"):
                    in_changelog = True
                if in_changelog:
                    lines.append(line)
            print("\n" + "\n".join(lines) if lines else "  Changelog introuvable.")

        elif choice.lower() == "q":
            print("\n  Au revoir.\n")
            sys.exit(0)

        else:
            print("  Choix invalide.")


# =============================================================================
# CLI — parser argparse
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    """
    Construit et retourne le parser argparse du script.

    Arguments positionnels :
      dossier               Dossier source à parcourir (obligatoire sauf
                            pour --help-* et --version).

    Options principales :
      -d / --destination    Dossier de destination pour les fichiers traités.
      --no-repair           Désactive la réparation automatique.
      --no-convert          Désactive la conversion MP4.
      --no-menu             Démarre directement sans menu principal.

    Aides contextuelles (quittent après affichage, sans dossier requis) :
      --help-repair         Détail des stratégies de réparation ffmpeg.
      --help-convert        Paramètres d'encodage de la conversion MP4.
      --help-workflow       Utilisation incrémentale avec dossier de destination.

    Exemples :
      # Lancement interactif
      sort_rush.py /media/rushes

      # Démarrage direct, destination prédéfinie
      sort_rush.py /media/rushes --destination /media/trie --no-menu

      # Session sans réparation ni conversion
      sort_rush.py /media/rushes --no-repair --no-convert --no-menu

      # Aide contextuelle (sans dossier)
      sort_rush.py --help-repair
    """
    parser = argparse.ArgumentParser(
        prog="sort_rush.py",
        description=textwrap.dedent("""\
            Outil de tri interactif de rush vidéo.

            Parcourt récursivement un dossier, lit chaque vidéo dans mpv,
            détecte et propose de réparer les fichiers corrompus via ffmpeg,
            puis offre un menu d'actions : passer au suivant, laisser sur
            place, renommer, déplacer, supprimer, convertir en MP4.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            aides contextuelles :
              --help-repair    réparation automatique (stratégies ffmpeg)
              --help-convert   conversion MP4 (paramètres d'encodage)
              --help-workflow  utilisation incrémentale (dossier de destination)

            dépendances système :
              mpv      lecture vidéo         (apt install mpv)
              ffmpeg   conversion/réparation (apt install ffmpeg)
              ffprobe  analyse des fichiers  (inclus dans ffmpeg)
        """),
    )

    parser.add_argument(
        "dossier",
        nargs="?",
        help="Dossier source à parcourir récursivement.",
    )
    parser.add_argument(
        "--destination", "-d",
        metavar="CHEMIN",
        help=(
            "Dossier de destination pour les fichiers traités. "
            "Créé s'il n'existe pas. Voir --help-workflow."
        ),
    )
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help=(
            "Désactive la détection d'erreurs et la réparation automatique. "
            "Voir --help-repair."
        ),
    )
    parser.add_argument(
        "--no-convert",
        action="store_true",
        help=(
            "Désactive la conversion MP4 (proposition et option [6]). "
            "Voir --help-convert."
        ),
    )
    parser.add_argument(
        "--no-menu",
        action="store_true",
        help=(
            "Démarre le traitement directement sans menu principal. "
            "Les options CLI sont appliquées telles quelles."
        ),
    )
    parser.add_argument(
        "--help-repair",
        action="store_true",
        help="Affiche la doc détaillée sur la réparation automatique et quitte.",
    )
    parser.add_argument(
        "--help-convert",
        action="store_true",
        help="Affiche la doc détaillée sur la conversion MP4 et quitte.",
    )
    parser.add_argument(
        "--help-workflow",
        action="store_true",
        help="Affiche la doc sur l'utilisation incrémentale et quitte.",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"triage_video {VERSION}",
    )

    return parser


# =============================================================================
# Point d'entrée
# =============================================================================

def main() -> None:
    """
    Point d'entrée principal du script.

    Séquence :
      1. Parse les arguments CLI via argparse.
      2. Traite les flags d'aide contextuelle et quitte si présents.
      3. Valide le dossier source et les dépendances système.
      4. Initialise la Session avec les valeurs CLI.
      5. Lance run_session() directement (--no-menu) ou main_menu().
    """
    parser = build_parser()
    args   = parser.parse_args()

    # --- Aides contextuelles : prioritaires, ne nécessitent pas de dossier
    if args.help_repair:
        print(HELP_REPAIR)
        sys.exit(0)
    if args.help_convert:
        print(HELP_CONVERT)
        sys.exit(0)
    if args.help_workflow:
        print(HELP_WORKFLOW)
        sys.exit(0)

    # --- Validation du dossier source
    if not args.dossier:
        parser.print_help()
        sys.exit(1)

    root = Path(args.dossier).expanduser().resolve()
    if not root.is_dir():
        print(f"  [ERREUR] Dossier introuvable : {root}")
        sys.exit(1)

    check_dependencies()
    print(BANNER)

    # --- Construction de la session depuis les arguments CLI
    output_dir: Path | None = None
    if args.destination:
        dest = Path(args.destination).expanduser().resolve()
        if not dest.exists():
            dest.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Dossier de destination créé : {dest}")
        elif not dest.is_dir():
            print(f"  [ERREUR] --destination : '{dest}' n'est pas un dossier.")
            sys.exit(1)
        output_dir = dest

    session = Session(
        root        = root,
        output_dir  = output_dir,
        opt_repair  = not args.no_repair,
        opt_convert = not args.no_convert,
    )

    # --- Lancement
    if args.no_menu:
        run_session(session)
    else:
        main_menu(session)


if __name__ == "__main__":
    main()
