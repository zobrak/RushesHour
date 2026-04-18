import shutil
from pathlib import Path


def action_rename(filepath: Path) -> Path:
    """
    Renomme le fichier dans son dossier courant.

    Retourne le nouveau Path, ou filepath inchangé si annulé ou si le nom
    cible existe déjà.
    """
    from rusheshour.cli.menus import ask
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
    from rusheshour.cli.menus import confirm
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
    from rusheshour.cli.menus import ask, confirm
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
    from rusheshour.cli.menus import confirm
    print(f"\n  /!\\ SUPPRESSION DÉFINITIVE : {filepath.name}")
    if confirm("Confirmer la suppression ?"):
        filepath.unlink()
        print("  ✓ Fichier supprimé.")
        return True
    print("  Annulé.")
    return False


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
