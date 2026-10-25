"""Rutas adicionales para api_movil.py.

Instalación: añadir al FINAL de api_movil.py:
    from api_movil_extensiones import instalar_rutas
    instalar_rutas(app, sesion_actual)

Las rutas usan las mismas reglas de negocio del backend de QualityCheck.
No exponer este servidor directamente a Internet; entorno de prueba local.
"""
from datetime import date
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from database import SessionLocal
from revision_backend import (
    obtener_revisiones, obtener_detalle, listar_programadas,
    listar_hallazgos_y_acciones, listar_tecnicos, listar_inspectores,
    obtener_criterios,
    guardar_revision, asignar_hallazgo, registrar_trabajo_tecnico,
    verificar_trabajo, listar_usuarios_roles, programar_preventiva,
    cancelar_programada, reprogramar_preventiva,
)


class Evaluacion(BaseModel):
    id_criterio: int
    cumple: bool
    medido: str = ""
    esperado: str = ""
    observacion: str = ""


class NuevaRevision(BaseModel):
    id_maquina: int
    tipo: str
    observaciones: str = ""
    evaluaciones: list[Evaluacion]
    id_programacion: int | None = None
    id_revision_origen: int | None = None


class Asignacion(BaseModel):
    id_tecnico: int
    descripcion: str = Field(min_length=1, max_length=500)
    fecha: date


class Trabajo(BaseModel):
    observaciones: str = Field(min_length=1)


class Verificacion(BaseModel):
    aprobado: bool
    observaciones: str = ""


class Programacion(BaseModel):
    id_maquina: int
    id_inspector: int
    fecha: date
    descripcion: str = Field(min_length=1)


def instalar_rutas(app, sesion_actual):
    def autorizado(s, roles):
        # Revalidar el rol contra la BD para no confiar en un rol guardado en la sesión.
        from revision_backend import obtener_rol_usuario
        rol = obtener_rol_usuario(s["id"])
        if rol not in roles:
            raise HTTPException(status_code=403, detail="No tienes permiso para esta operación.")
        return rol

    def ejecutar(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PermissionError as e:
            raise HTTPException(403, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.get("/dashboard")
    def dashboard(s=Depends(sesion_actual)):
        with SessionLocal() as db:
            m = db.execute(text("SELECT COUNT(*) FROM maquinas WHERE activa=TRUE")).scalar_one()
            r = db.execute(text("SELECT COUNT(*) FROM revisiones")).scalar_one()
            h = db.execute(text("SELECT COUNT(*) FROM hallazgos WHERE estado <> 'Cerrado'")).scalar_one()
            p = db.execute(text("SELECT COUNT(*) FROM revisiones_programadas WHERE estado='Programada'")).scalar_one()
        return {"maquinas": m, "revisiones": r, "hallazgos": h, "programadas": p}

    @app.get("/maquinas-detalle")
    def maquinas_detalle(s=Depends(sesion_actual)):
        with SessionLocal() as db:
            filas = db.execute(text("""
                SELECT m.id_maquina AS id, m.codigo_maquina, m.nombre, m.tipo,
                       m.marca, m.modelo, m.numero_serie, m.ubicacion, m.estado,
                       a.nombre AS area
                FROM maquinas m LEFT JOIN areas a ON a.id_area=m.id_area
                WHERE m.activa=TRUE ORDER BY m.nombre
            """)).mappings().all()
        return [dict(x) for x in filas]

    @app.get("/maquinas/{id_maquina}/criterios")
    def criterios(id_maquina: int, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        return obtener_criterios(id_maquina)

    @app.get("/revisiones")
    def revisiones(historial: bool = False, s=Depends(sesion_actual)):
        registros = obtener_revisiones()
        if not historial:
            registros = [
                revision for revision in registros
                if not (
                    revision.get("resultado") == "Aprobada"
                    and revision.get("estado_revision") != "Corregida"
                )
            ]
        return registros

    @app.get("/revisiones/{id_revision}")
    def revision_detalle(id_revision: int, s=Depends(sesion_actual)):
        return obtener_detalle(id_revision)

    @app.post("/revisiones")
    def crear_revision(d: NuevaRevision, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        codigo = ejecutar(guardar_revision, d.id_maquina, s["id"], d.tipo,
                          d.observaciones, [e.model_dump() for e in d.evaluaciones],
                          d.id_programacion, d.id_revision_origen)
        return {"codigo": codigo}

    @app.get("/programadas")
    def programadas(s=Depends(sesion_actual)):
        return listar_programadas()

    @app.post("/programadas")
    def nueva_programada(d: Programacion, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        idp = ejecutar(
            programar_preventiva,
            d.id_maquina,
            d.id_inspector,
            d.fecha,
            d.descripcion,
        )
        return {"id": idp}

    @app.delete("/programadas/{id_programacion}")
    def cancelar(id_programacion: int, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        ejecutar(cancelar_programada, id_programacion, s["id"])
        return {"ok": True}

    @app.get("/bitacora")
    def bitacora(s=Depends(sesion_actual)):
        from bitacora import obtener_bitacora
        return obtener_bitacora()

    @app.get("/hallazgos")
    def hallazgos(s=Depends(sesion_actual)):
        rol = autorizado(s, ("Administrador", "Inspector", "Técnico"))
        return listar_hallazgos_y_acciones(s["id"], rol)

    @app.get("/tecnicos")
    def tecnicos(s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        return listar_tecnicos()

    @app.get("/inspectores")
    def inspectores(s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        return listar_inspectores()

    @app.post("/hallazgos/{id_hallazgo}/asignar")
    def asignar(id_hallazgo: int, d: Asignacion, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        ejecutar(asignar_hallazgo, id_hallazgo, d.id_tecnico, s["id"], d.descripcion, d.fecha)
        return {"ok": True}

    @app.post("/acciones/{id_accion}/trabajo")
    def trabajo(id_accion: int, d: Trabajo, s=Depends(sesion_actual)):
        autorizado(s, ("Técnico",))
        ejecutar(registrar_trabajo_tecnico, id_accion, s["id"], d.observaciones)
        return {"ok": True}

    @app.post("/acciones/{id_accion}/verificar")
    def verificar(id_accion: int, d: Verificacion, s=Depends(sesion_actual)):
        autorizado(s, ("Administrador", "Inspector"))
        ejecutar(verificar_trabajo, id_accion, s["id"], d.aprobado, d.observaciones)
        return {"ok": True}

    @app.get("/usuarios")
    def usuarios(s=Depends(sesion_actual)):
        autorizado(s, ("Administrador",))
        return listar_usuarios_roles()

    @app.get("/perfil")
    def perfil(s=Depends(sesion_actual)):
        with SessionLocal() as db:
            u = db.execute(text("""
                SELECT nombre, nombre_usuario, correo, activo
                FROM usuarios WHERE id_usuario=:id
            """), {"id": s["id"]}).mappings().first()
        if not u:
            raise HTTPException(404, "Usuario no encontrado")
        return {**dict(u), "rol": s["rol"]}
