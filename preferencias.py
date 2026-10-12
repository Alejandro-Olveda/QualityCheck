import json
import os
from pathlib import Path


DEFAULTS = {
    'notificaciones': True,
    'preventivas': True,
    'correctivas': True,
    'verificaciones': True,
    'dias_anticipacion': 7,
}


def _ruta():
    base = Path(os.environ.get('APPDATA') or (Path.home() / '.qualitycheck'))
    return base / 'QualityCheck' / 'preferencias.json'


def cargar_preferencias(id_usuario):
    try:
        datos = json.loads(_ruta().read_text(encoding='utf-8'))
        guardado = datos.get(str(id_usuario), {})
        if isinstance(guardado, dict):
            return {**DEFAULTS, **{k: v for k, v in guardado.items() if k in DEFAULTS}}
    except (OSError, ValueError, TypeError):
        pass
    return DEFAULTS.copy()


def guardar_preferencias(id_usuario, preferencias):
    ruta = _ruta()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        datos = json.loads(ruta.read_text(encoding='utf-8'))
        if not isinstance(datos, dict):
            datos = {}
    except (OSError, ValueError, TypeError):
        datos = {}
    datos[str(id_usuario)] = {k: preferencias.get(k, v) for k, v in DEFAULTS.items()}
    temporal = ruta.with_suffix('.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporal, ruta)


def filtrar_notificaciones(avisos, preferencias):
    if not preferencias.get('notificaciones', True):
        return []
    resultado = []
    for aviso in avisos:
        tipo = aviso['tipo'].lower()
        if 'preventiva' in tipo and not preferencias.get('preventivas', True):
            continue
        if 'verificación' in tipo and not preferencias.get('verificaciones', True):
            continue
        if 'preventiva' not in tipo and 'verificación' not in tipo and not preferencias.get('correctivas', True):
            continue
        resultado.append(aviso)
    return resultado
