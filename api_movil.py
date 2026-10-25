"""API inicial para QualityCheck Mobile. Ejecutar SOLO en una red de pruebas.

Las credenciales de PostgreSQL permanecen en el servidor, nunca en el APK.
La autenticación existente utiliza contraseñas heredadas en texto plano:
se debe migrar a hashes y HTTPS antes de un despliegue real.
"""
import os
import hmac
import secrets
import threading
import time
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, inspect, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta DATABASE_URL en el .env del servidor.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
app = FastAPI(title="QualityCheck Mobile API", docs_url=None, redoc_url=None)
_sessions = {}
_lock = threading.Lock()
SESSION_SECONDS = 4 * 60 * 60


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=150)
    contrasena: str = Field(min_length=1, max_length=200)


@lru_cache(maxsize=1)
def tiene_nombre_usuario():
    return "nombre_usuario" in {c["name"] for c in inspect(engine).get_columns("usuarios")}


def sesion_actual(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Inicia sesión.")
    token = authorization[7:]
    with _lock:
        session = _sessions.get(token)
        if not session or session["expira"] < time.time():
            _sessions.pop(token, None)
            raise HTTPException(401, "Sesión vencida. Inicia sesión otra vez.")
        return dict(session)


@app.get("/health")
def health():
    with engine.connect() as db:
        db.execute(text("SELECT 1"))
    return {"ok": True, "servicio": "QualityCheck Mobile"}


@app.post("/login")
def login(datos: Credenciales):
    identificador = datos.usuario.strip()
    if not identificador:
        raise HTTPException(401, "Credenciales incorrectas.")
    filtro = "lower(correo) = lower(:identificador)"
    if tiene_nombre_usuario():
        filtro += " OR lower(nombre_usuario) = lower(:identificador)"
    with engine.connect() as db:
        filas = db.execute(text(f"""
            SELECT id_usuario, nombre, correo, contrasena_hash
            FROM usuarios WHERE activo = TRUE AND ({filtro}) LIMIT 2
        """), {"identificador": identificador}).mappings().all()
        if len(filas) != 1 or not hmac.compare_digest(str(filas[0]["contrasena_hash"]), datos.contrasena):
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        u = filas[0]
        rol = db.execute(text("""
            SELECT r.nombre_rol FROM usuario_roles ur
            JOIN roles r ON r.id_rol = ur.id_rol
            WHERE ur.id_usuario = :id LIMIT 1
        """), {"id": u["id_usuario"]}).scalar_one_or_none() or "Sin rol"
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {"id": u["id_usuario"], "nombre": u["nombre"], "rol": rol,
                            "expira": time.time() + SESSION_SECONDS}
    return {"token": token, "nombre": u["nombre"], "rol": rol}


@app.get("/me")
def me(sesion=Depends(sesion_actual)):
    return {"id": sesion["id"], "nombre": sesion["nombre"], "rol": sesion["rol"]}


@app.get("/maquinas")
def maquinas(sesion=Depends(sesion_actual)):
    with engine.connect() as db:
        filas = db.execute(text("""
            SELECT codigo_maquina, nombre, tipo, estado, COALESCE(ubicacion, '') AS ubicacion
            FROM maquinas WHERE activa = TRUE ORDER BY nombre LIMIT 250
        """)).mappings().all()
    return [dict(f) for f in filas]


@app.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        with _lock:
            _sessions.pop(authorization[7:], None)
    return {"ok": True}

# Rutas Android adicionales
from api_movil_extensiones import instalar_rutas
instalar_rutas(app, sesion_actual)

# QualityCheck Android Fase 3
from api_movil_fase3 import instalar_rutas_fase3
instalar_rutas_fase3(app, sesion_actual)
