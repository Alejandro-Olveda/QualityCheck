"""Fase 3 de QualityCheck Android: escritura con autorización en servidor.

Importar desde api_movil.py una sola vez:
    from api_movil_fase3 import instalar_rutas_fase3
    instalar_rutas_fase3(app, sesion_actual)

Solo usar en red local de pruebas. No publicar HTTP ni credenciales heredadas.
"""
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models import Area, Maquina, CriterioInspeccion
from revision_backend import (
    obtener_rol_usuario, listar_roles, crear_usuario_con_rol,
    actualizar_usuario_admin, reprogramar_preventiva, obtener_revisiones,
)

ESTADOS = ("Operativa", "En revisión", "Fuera de servicio")
CATEGORIAS = ("General", "Seguridad", "Mantenimiento", "Mecánico", "Eléctrico", "Neumático", "Calidad")
ROLES = ("Administrador", "Inspector", "Técnico")


class CriterioEntrada(BaseModel):
    id: int | None = None
    nombre: str = Field(min_length=1, max_length=150)
    categoria: str = Field(default="General", max_length=100)


class MaquinaEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    marca: str = Field(default="", max_length=100)
    modelo: str = Field(default="", max_length=100)
    ubicacion: str = Field(default="", max_length=150)
    id_area: int
    estado: str = "Operativa"
    criterios: list[CriterioEntrada] = Field(min_length=1)


class CambioActivo(BaseModel):
    activa: bool


class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    correo: str = Field(min_length=3, max_length=150)
    contrasena: str = Field(min_length=1, max_length=200)
    rol: str


class UsuarioEdicion(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    correo: str = Field(min_length=3, max_length=150)
    nombre_usuario: str = Field(min_length=1, max_length=100)
    rol: str
    activo: bool = True
    nueva_contrasena: str = Field(default="", max_length=200)


class PreventivaEdicion(BaseModel):
    fecha: date
    descripcion: str = Field(min_length=1, max_length=2000)


def instalar_rutas_fase3(app, sesion_actual):
    def autorizado(s, roles):
        rol = obtener_rol_usuario(s["id"])
        if rol not in roles:
            raise HTTPException(403, "No tienes permiso para realizar esta acción.")
        with SessionLocal() as db:
            activo = db.execute(text("SELECT activo FROM usuarios WHERE id_usuario=:id"), {"id": s["id"]}).scalar_one_or_none()
        if activo is not True:
            raise HTTPException(401, "Tu cuenta ya no está activa.")
        return rol

    def ejecutar(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except IntegrityError as exc:
            raise HTTPException(409, "Ya existe un registro con esos datos.") from exc

    def validar_maquina(d):
        if not d.nombre.strip():
            raise HTTPException(400, "Escribe el nombre de la máquina.")
        if d.estado not in ESTADOS:
            raise HTTPException(400, "Estado de máquina no válido.")
        nombres = [c.nombre.strip().casefold() for c in d.criterios]
        if any(not n for n in nombres) or len(set(nombres)) != len(nombres):
            raise HTTPException(400, "Los criterios no pueden estar vacíos ni repetidos.")
        if any(c.categoria not in CATEGORIAS for c in d.criterios):
            raise HTTPException(400, "Categoría de criterio no válida.")
        ids = [c.id for c in d.criterios if c.id is not None]
        if len(ids) != len(set(ids)):
            raise HTTPException(400, "Hay criterios duplicados.")

    @app.get("/areas")
    def areas(s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        with SessionLocal() as db:
            return [{"id": a.id_area, "nombre": a.nombre} for a in
                    db.query(Area).filter(Area.activa.is_(True)).order_by(Area.nombre).all()]

    @app.get("/maquinas-admin")
    def maquinas_admin(s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        with SessionLocal() as db:
            filas = db.query(Maquina).order_by(Maquina.nombre).all()
            return [{"id": m.id_maquina, "codigo_maquina": m.codigo_maquina,
                     "nombre": m.nombre, "estado": m.estado, "activa": bool(m.activa)} for m in filas]

    @app.get("/maquinas/{id_maquina}/editar")
    def detalle_edicion(id_maquina: int, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        with SessionLocal() as db:
            m = db.get(Maquina, id_maquina)
            if not m:
                raise HTTPException(404, "Máquina no encontrada.")
            criterios = db.query(CriterioInspeccion).filter(
                CriterioInspeccion.id_maquina == id_maquina,
                CriterioInspeccion.activo.is_(True),
            ).order_by(CriterioInspeccion.id_criterio).all()
            return {"id": m.id_maquina, "codigo_maquina": m.codigo_maquina,
                    "nombre": m.nombre, "marca": m.marca or "", "modelo": m.modelo or "",
                    "ubicacion": m.ubicacion or "", "id_area": m.id_area,
                    "estado": m.estado, "activa": bool(m.activa),
                    "criterios": [{"id": c.id_criterio, "nombre": c.nombre_criterio,
                                   "categoria": c.categoria} for c in criterios]}

    @app.post("/maquinas")
    def crear_maquina(d: MaquinaEntrada, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        validar_maquina(d)
        try:
            with SessionLocal.begin() as db:
                if not db.query(Area).filter(Area.id_area == d.id_area, Area.activa.is_(True)).first():
                    raise HTTPException(400, "Selecciona un área activa.")
                # Evita que dos creaciones simultáneas produzcan el mismo código MAQ-NNN.
                db.execute(text("SELECT pg_advisory_xact_lock(60234219)"))
                ultimo_id = db.query(func.max(Maquina.id_maquina)).scalar() or 0
                n = ultimo_id + 1
                while db.query(Maquina.id_maquina).filter(Maquina.codigo_maquina == f"MAQ-{n:03d}").first():
                    n += 1
                m = Maquina(codigo_maquina=f"MAQ-{n:03d}", nombre=d.nombre.strip(),
                            tipo="Industrial", marca=d.marca.strip() or None,
                            modelo=d.modelo.strip() or None, ubicacion=d.ubicacion.strip() or None,
                            id_area=d.id_area, estado=d.estado, activa=True)
                db.add(m)
                db.flush()
                for c in d.criterios:
                    db.add(CriterioInspeccion(id_maquina=m.id_maquina,
                                             nombre_criterio=c.nombre.strip(), categoria=c.categoria, activo=True))
                codigo = m.codigo_maquina
                identificador = m.id_maquina
            return {"id": identificador, "codigo": codigo}
        except IntegrityError as exc:
            raise HTTPException(409, "Conflicto al crear máquina; intenta nuevamente.") from exc

    @app.put("/maquinas/{id_maquina}")
    def editar_maquina(id_maquina: int, d: MaquinaEntrada, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        validar_maquina(d)
        try:
            with SessionLocal.begin() as db:
                m = db.get(Maquina, id_maquina)
                if not m or not m.activa:
                    raise HTTPException(404, "La máquina no existe o está inactiva.")
                if not db.query(Area).filter(Area.id_area == d.id_area, Area.activa.is_(True)).first():
                    raise HTTPException(400, "Selecciona un área activa.")
                actuales = {c.id_criterio: c for c in db.query(CriterioInspeccion).filter(
                    CriterioInspeccion.id_maquina == id_maquina,
                    CriterioInspeccion.activo.is_(True),
                ).all()}
                recibidos = {c.id for c in d.criterios if c.id is not None}
                if not recibidos.issubset(actuales):
                    raise HTTPException(400, "Uno de los criterios no pertenece a esta máquina.")
                m.nombre = d.nombre.strip()
                m.marca = d.marca.strip() or None
                m.modelo = d.modelo.strip() or None
                m.ubicacion = d.ubicacion.strip() or None
                m.id_area = d.id_area
                m.estado = d.estado
                for id_criterio, c in actuales.items():
                    if id_criterio not in recibidos:
                        c.activo = False  # Conserva referencias de inspecciones históricas.
                for c in d.criterios:
                    if c.id is None:
                        db.add(CriterioInspeccion(id_maquina=id_maquina, nombre_criterio=c.nombre.strip(),
                                                 categoria=c.categoria, activo=True))
                    else:
                        # Coincide con la edición en PC: los criterios existentes no se renombran.
                        pass
            return {"ok": True}
        except IntegrityError as exc:
            raise HTTPException(409, "Conflicto al guardar máquina.") from exc

    @app.patch("/maquinas/{id_maquina}/activo")
    def cambiar_activo(id_maquina: int, d: CambioActivo, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        with SessionLocal.begin() as db:
            m = db.get(Maquina, id_maquina)
            if not m:
                raise HTTPException(404, "Máquina no encontrada.")
            m.activa = d.activa
        return {"ok": True}

    @app.delete("/maquinas/{id_maquina}")
    def eliminar_maquina(id_maquina: int, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador",))
        with SessionLocal.begin() as db:
            m = db.get(Maquina, id_maquina)
            if not m:
                raise HTTPException(404, "Máquina no encontrada.")
            revisiones = db.execute(text("SELECT 1 FROM revisiones WHERE id_maquina=:id LIMIT 1"),
                                    {"id": id_maquina}).first()
            programadas = db.execute(text("SELECT 1 FROM revisiones_programadas WHERE id_maquina=:id LIMIT 1"),
                                     {"id": id_maquina}).first()
            if revisiones or programadas:
                raise HTTPException(409, "La máquina tiene historial o programaciones. Desactívala para conservar los registros.")
            db.query(CriterioInspeccion).filter(CriterioInspeccion.id_maquina == id_maquina).delete(
                synchronize_session=False)
            db.delete(m)
        return {"ok": True}

    @app.get("/roles")
    def roles(s=Depends(sesion_actual)):
        autorizado(s, ("Administrador",))
        return [x for x in listar_roles() if x in ROLES]

    @app.post("/usuarios")
    def crear_usuario(d: UsuarioNuevo, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador",))
        if d.rol not in ROLES:
            raise HTTPException(400, "Rol no válido.")
        nuevo = ejecutar(crear_usuario_con_rol, d.nombre, d.correo, d.contrasena, d.rol)
        return {"id": nuevo}

    @app.put("/usuarios/{id_usuario}")
    def editar_usuario(id_usuario: int, d: UsuarioEdicion, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador",))
        if d.rol not in ROLES:
            raise HTTPException(400, "Rol no válido.")
        ejecutar(actualizar_usuario_admin, s["id"], id_usuario, d.nombre, d.correo, d.rol,
                 d.activo, d.nueva_contrasena or None, d.nombre_usuario)
        return {"ok": True}

    @app.put("/programadas/{id_programacion}")
    def editar_programada(id_programacion: int, d: PreventivaEdicion, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        ejecutar(reprogramar_preventiva, id_programacion, d.fecha, d.descripcion)
        return {"ok": True}

    @app.get("/correctivas-pendientes")
    def correctivas_pendientes(id_maquina: int, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        revisiones = obtener_revisiones()
        return [{"id": r["id"], "codigo": r["codigo"], "resultado": r["resultado"]}
                for r in revisiones if r["id_maquina"] == id_maquina
                and r["resultado"] == "Requiere atención"
                and r["estado_revision"] != "Corregida"]
