#!/usr/bin/env python3
"""Point d'entrée CLI du package rusheshour."""

import sys
import shutil
from pathlib import Path

from rusheshour.core.session import Session
from rusheshour.core.scanner import collect_videos
from rusheshour.core.probe import get_video_info, print_video_info, check_errors
from rusheshour.core.repair import action_repair
from rusheshour.cli.parser import BANNER, HELP_REPAIR, HELP_CONVERT, HELP_WORKFLOW, build_parser


CHANGELOG = """CHANGELOG
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
          (renommé/déplacé) depuis show_menu vers run_session"""


def check_dependencies() -> None:
    """Vérifie la présence des outils système requis. Quitte si l'un manque."""
    missing = [t for t in ("mpv", "ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        print(f"\n  [ERREUR] Outil(s) manquant(s) : {', '.join(missing)}")
        print("  Installe avec : sudo apt install mpv ffmpeg")
        sys.exit(1)


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
    from rusheshour.cli.menus import confirm, play_video, show_menu

    info = get_video_info(filepath)
    print_video_info(filepath, info, index, total)

    if session.opt_repair:
        errors = check_errors(filepath)
        if errors:
            print("\n  /!\\ Erreurs détectées par ffprobe :")
            for line in errors[:10]:
                print(f"    {line}")
            if len(errors) > 10:
                print(f"    ... ({len(errors) - 10} ligne(s) supplémentaire(s))")
            if confirm("Tenter une réparation avant lecture ?", default_yes=True):
                filepath = action_repair(filepath, prior_errors=errors)
                info = get_video_info(filepath)
        else:
            print("  ✓ Aucune erreur détectée.")

    play_video(filepath)

    return show_menu(filepath, info, session)


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
            continue
        action, _ = process_video(video, index, total, session)
        if action == "menu":
            return "menu"

    print("\n  ✓ Toutes les vidéos ont été traitées.")
    return "done"


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
    from rusheshour.cli.menus import main_menu

    parser = build_parser()
    args   = parser.parse_args()

    if args.help_repair:
        print(HELP_REPAIR)
        sys.exit(0)
    if args.help_convert:
        print(HELP_CONVERT)
        sys.exit(0)
    if args.help_workflow:
        print(HELP_WORKFLOW)
        sys.exit(0)

    if not args.dossier:
        parser.print_help()
        sys.exit(1)

    root = Path(args.dossier).expanduser().resolve()
    if not root.is_dir():
        print(f"  [ERREUR] Dossier introuvable : {root}")
        sys.exit(1)

    check_dependencies()
    print(BANNER)

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

    if args.no_menu:
        run_session(session)
    else:
        main_menu(session)


if __name__ == "__main__":
    main()
