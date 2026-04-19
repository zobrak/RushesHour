import sys
import subprocess
from pathlib import Path

from rusheshour.core.session import Session
from rusheshour.core.probe import is_already_mp4
from rusheshour.core.actions import (
    action_rename, action_move_to, action_move_manual,
    action_delete, finalize,
)
from rusheshour.core.convert import action_convert_mp4


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


def play_video(filepath: Path) -> None:
    """Lance mpv sur filepath et bloque jusqu'à la fin de la lecture."""
    print(f"\n  >> {filepath.name}")
    print("  (Ferme la fenêtre mpv ou appuie sur Q pour accéder au menu)")
    subprocess.run(["mpv", str(filepath)], check=False)


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


def main_menu(session: Session) -> None:
    """
    Affiche le menu principal et dispatche vers les sous-menus ou le
    traitement. Boucle jusqu'à ce que l'utilisateur quitte.

    L'objet session est modifié en place (output_dir, options).
    """
    from rusheshour.cli.main import run_session
    from rusheshour.cli.parser import HELP_TEXT

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
            from rusheshour.cli.main import CHANGELOG
            print("\n" + CHANGELOG if CHANGELOG else "  Changelog introuvable.")

        elif choice.lower() == "q":
            print("\n  Au revoir.\n")
            sys.exit(0)

        else:
            print("  Choix invalide.")
