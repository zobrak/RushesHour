from dataclasses import dataclass
from pathlib import Path


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
