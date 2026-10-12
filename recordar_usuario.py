import json
import os
from pathlib import Path


def _archivo():
    carpeta = Path(os.environ.get("APPDATA") or Path.home() / ".qualitycheck") / "QualityCheck"
    return carpeta / "preferencias_login.json"


def leer_usuario_recordado():
    try:
        with _archivo().open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos.get("usuario", "") if isinstance(datos, dict) else ""
    except (OSError, ValueError, TypeError):
        return ""


def guardar_usuario_recordado(usuario):
    ruta = _archivo()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump({"usuario": usuario}, archivo, ensure_ascii=False)
    os.replace(temporal, ruta)


def borrar_usuario_recordado():
    try:
        _archivo().unlink(missing_ok=True)
    except OSError:
        pass
