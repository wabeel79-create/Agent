"""Kapsi-Q — SmartCell Technologies.

Au démarrage, lit le fichier de configuration `kapsi.env` (à la racine) s'il existe :
lignes CLE=valeur ; les variables déjà définies dans l'environnement restent prioritaires.
"""
import os
from pathlib import Path

_ENV = Path(__file__).resolve().parent.parent / "kapsi.env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
