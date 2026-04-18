import argparse
import textwrap

from rusheshour import __version__ as VERSION


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
