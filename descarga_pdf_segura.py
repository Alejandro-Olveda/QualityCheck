"""Tickets temporales para entregar PDFs sin guardarlos en carpetas públicas."""
from threading import Lock
from time import monotonic
from secrets import token_urlsafe
import re

_LOCK = Lock()
_PENDIENTES = {}
_VIGENCIA = 120  # segundos
_LIMITE = 50

def crear_descarga(contenido: bytes, nombre: str) -> str:
    if not contenido.startswith(b"%PDF"):
        raise ValueError("Contenido de reporte no válido")
    if len(contenido) > 15 * 1024 * 1024:
        raise ValueError("Reporte PDF demasiado grande")
    archivo = re.sub(r"[^A-Za-z0-9._-]", "_", nombre)[:100].strip("._") or "reporte.pdf"
    if not archivo.lower().endswith('.pdf'):
        archivo += '.pdf'
    token = token_urlsafe(32)
    ahora = monotonic()
    with _LOCK:
        for clave, (expira, _, _) in tuple(_PENDIENTES.items()):
            if expira <= ahora:
                _PENDIENTES.pop(clave, None)
        if len(_PENDIENTES) >= _LIMITE:
            raise RuntimeError("Demasiadas descargas pendientes; intenta de nuevo")
        _PENDIENTES[token] = (ahora + _VIGENCIA, contenido, archivo)
    return token

def retirar_descarga(token: str):
    with _LOCK:
        item = _PENDIENTES.pop(token, None)
    if item is None or item[0] < monotonic():
        return None
    return item[1], item[2]
