import re
import unicodedata

from sqlalchemy import func

from models import Usuario


def limpiar_nombre_usuario(valor):
    valor = unicodedata.normalize("NFKD", (valor or "").strip())
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    valor = re.sub(r"[^A-Za-z0-9 ]", " ", valor)
    return " ".join(valor.split()).title()[:100]


def generar_usuario_base(nombre_completo):
    partes = (nombre_completo or "").split()
    if not partes:
        raise ValueError("El nombre es obligatorio.")
    apellido = partes[-2] if len(partes) >= 3 else (partes[-1] if len(partes) == 2 else "")
    return limpiar_nombre_usuario(f"{partes[0]} {apellido}")


def generar_usuario_disponible(db, nombre_completo, excluir_id=None):
    base = generar_usuario_base(nombre_completo)
    candidato = base
    numero = 2
    while True:
        consulta = db.query(Usuario.id_usuario).filter(
            func.lower(Usuario.nombre_usuario) == candidato.lower()
        )
        if excluir_id is not None:
            consulta = consulta.filter(Usuario.id_usuario != excluir_id)
        if consulta.first() is None:
            return candidato
        sufijo = str(numero)
        candidato = f"{base[:100 - len(sufijo)]}{sufijo}"
        numero += 1
