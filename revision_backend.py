from sqlalchemy import func
from usuarios_login import generar_usuario_disponible, limpiar_nombre_usuario
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import joinedload

from database import SessionLocal
from models import (
    CriterioInspeccion,
    Hallazgo,
    Inspeccion,
    Maquina,
    ResultadoInspeccion,
    RevisionProgramada,
    Usuario,
)


def _estado_extra_revisiones(db):

    filas = db.execute(text(
        "SELECT id_inspeccion, estado_revision, id_revision_origen FROM revisiones"
    )).mappings().all()
    return {
        int(f["id_inspeccion"]): {
            "estado_revision": f["estado_revision"] or "Abierta",
            "id_revision_origen": f["id_revision_origen"],
        }
        for f in filas
    }


def obtener_maquinas():
    with SessionLocal() as db:
        return [
            {"id": m.id_maquina, "codigo": m.codigo_maquina, "nombre": m.nombre}
            for m in db.query(Maquina)
            .filter(Maquina.activa.is_(True))
            .order_by(Maquina.nombre)
            .all()
        ]


def obtener_criterios(id_maquina):
    with SessionLocal() as db:
        return [
            {
                "id": c.id_criterio,
                "nombre": c.nombre_criterio,
                "categoria": c.categoria,
                "descripcion": c.description or "",
            }
            for c in db.query(CriterioInspeccion)
            .filter(
                CriterioInspeccion.id_maquina == id_maquina,
                CriterioInspeccion.activo.is_(True),
            )
            .order_by(CriterioInspeccion.id_criterio)
            .all()
        ]


def obtener_revisiones():
    with SessionLocal() as db:
        extras = _estado_extra_revisiones(db)

        filas = (
            db.query(Inspeccion)
            .options(
                joinedload(Inspeccion.maquina),
                joinedload(Inspeccion.inspector),
            )
            .order_by(Inspeccion.fecha_inspeccion.desc())
            .all()
        )

        # Obtener el técnico y el estado de la acción correctiva
        # más reciente de cada hallazgo.
        seguimientos = db.execute(text("""
            SELECT
                h.id_inspeccion,
                h.id_hallazgo,
                COALESCE(
                    tec.nombre,
                    NULLIF(ac.responsable, '')
                ) AS tecnico,
                COALESCE(ac.estado, 'Sin asignar') AS estado_trabajo
            FROM hallazgos h
            LEFT JOIN LATERAL (
                SELECT a.*
                FROM acciones_correctivas a
                WHERE a.id_hallazgo = h.id_hallazgo
                ORDER BY a.id_accion DESC
                LIMIT 1
            ) ac ON TRUE
            LEFT JOIN usuarios tec
                ON tec.id_usuario = ac.id_responsable
            ORDER BY h.id_inspeccion, h.id_hallazgo
        """)).mappings().all()

        tecnicos_por_revision = {}

        for seguimiento in seguimientos:
            id_revision = int(seguimiento["id_inspeccion"])

            tecnicos_por_revision.setdefault(
                id_revision, []
            ).append({
                "id_hallazgo": seguimiento["id_hallazgo"],
                "tecnico": seguimiento["tecnico"] or "Sin asignar",
                "estado_trabajo": (
                    seguimiento["estado_trabajo"] or "Sin asignar"
                ),
            })

        salida = []

        for i in filas:
            extra = extras.get(i.id_inspeccion, {})
            estado_revision = extra.get(
                "estado_revision", "Abierta"
            )
            resultado = i.resultado_final or "Pendiente"

            estado_actual = (
                "Corregida"
                if estado_revision == "Corregida"
                else resultado
            )

            salida.append({
                "id": i.id_inspeccion,
                "codigo": i.codigo_inspeccion,
                "maquina": (
                    i.maquina.nombre
                    if i.maquina else "Desconocida"
                ),
                "codigo_maquina": (
                    i.maquina.codigo_maquina
                    if i.maquina else "—"
                ),
                "id_maquina": i.id_maquina,
                "inspector": (
                    i.inspector.nombre
                    if i.inspector else "Desconocido"
                ),
                "tipo": i.tipo_inspeccion,
                "fecha": i.fecha_inspeccion,
                "resultado": resultado,
                "estado_revision": estado_revision,
                "estado_actual": estado_actual,
                "id_revision_origen": extra.get(
                    "id_revision_origen"
                ),
                "observaciones": i.observaciones_generales or "",
                "tecnicos_trabajo": tecnicos_por_revision.get(
                    i.id_inspeccion, []
                ),
            })

        return salida

def obtener_detalle(id_inspeccion):
    with SessionLocal() as db:
        resultados = (
            db.query(ResultadoInspeccion)
            .filter(ResultadoInspeccion.id_inspeccion == id_inspeccion)
            .order_by(ResultadoInspeccion.id_resultado)
            .all()
        )

        criterios = []
        for r in resultados:
            c = db.get(CriterioInspeccion, r.id_criterio)
            criterios.append({
                "id_criterio": r.id_criterio,
                "nombre": c.nombre_criterio if c else f"Criterio #{r.id_criterio}",
                "categoria": c.categoria if c else "Sin categoría",
                "medido": r.valor_medido or "",
                "esperado": r.valor_esperado or "",
                "cumple": bool(r.cumple),
                "observacion": r.observacion or "",
            })

        hallazgos = (
            db.query(Hallazgo)
            .filter(Hallazgo.id_inspeccion == id_inspeccion)
            .order_by(Hallazgo.id_hallazgo)
            .all()
        )

        correctivas = db.execute(text("""
            SELECT r.id_inspeccion, r.codigo_inspeccion, r.resultado_final,
                   r.estado_revision, r.fecha_inspeccion
            FROM revisiones r
            WHERE r.id_revision_origen = :origen
            ORDER BY r.fecha_inspeccion DESC
        """), {"origen": id_inspeccion}).mappings().all()

        responsables_por_hallazgo = {}
        responsables_mantenimiento = set()
        filas_responsables = db.execute(text("""
            SELECT h.id_hallazgo,
                   COALESCE(
                       NULLIF(BTRIM(u.nombre), ''),
                       NULLIF(BTRIM(ac.responsable), '')
                   ) AS nombre
            FROM hallazgos h
            LEFT JOIN acciones_correctivas ac
                ON ac.id_hallazgo = h.id_hallazgo
            LEFT JOIN usuarios u
                ON u.id_usuario = ac.id_responsable
            WHERE h.id_inspeccion = :id
            ORDER BY h.id_hallazgo, nombre NULLS LAST
        """), {"id": id_inspeccion}).mappings().all()

        for fila in filas_responsables:
            nombre = (fila["nombre"] or "").strip() or "Sin asignar"
            responsables_por_hallazgo.setdefault(
                int(fila["id_hallazgo"]), []
            ).append(nombre)
            responsables_mantenimiento.add(nombre)

        responsables_mantenimiento = sorted(responsables_mantenimiento)
        if not responsables_mantenimiento:
            responsables_mantenimiento = ["Sin asignar"]

        return {
            "criterios": criterios,
            "hallazgos": [
                {
                    "id": h.id_hallazgo,
                    "descripcion": h.descripcion,
                    "severidad": h.nivel_severidad,
                    "estado": h.estado,
                    "tecnicos_mantenimiento": responsables_por_hallazgo.get(
                        h.id_hallazgo, ["Sin asignar"]
                    ),
                }
                for h in hallazgos
            ],
            "responsables_mantenimiento": responsables_mantenimiento,
            "correctivas": [dict(c) for c in correctivas],
        }


def _actualizar_estado_maquina(db, id_maquina):

    abiertos = (
        db.query(Hallazgo)
        .join(Inspeccion, Hallazgo.id_inspeccion == Inspeccion.id_inspeccion)
        .filter(
            Inspeccion.id_maquina == id_maquina,
            Hallazgo.estado.in_(["Abierto", "En proceso", "Pendiente de verificación"]),
        )
        .count()
    )
    maquina = db.get(Maquina, id_maquina)
    if maquina:
        maquina.estado = "En revisión" if abiertos else "Operativa"


def guardar_revision(
    id_maquina,
    id_inspector,
    tipo,
    observaciones,
    evaluaciones,
    id_programacion=None,
    id_revision_origen=None,
):

    if not evaluaciones:
        raise ValueError("La máquina no tiene criterios activos para evaluar.")
    if tipo not in ("Preventiva", "Correctiva", "Rutina"):
        raise ValueError("Tipo de revisión no válido.")
    if id_revision_origen is not None and tipo != "Correctiva":
        raise ValueError("Una revisión vinculada como corrección debe ser de tipo Correctiva.")

    with SessionLocal() as db:
        try:
            maquina = (
                db.query(Maquina)
                .filter(Maquina.id_maquina == id_maquina, Maquina.activa.is_(True))
                .first()
            )
            ids = [e["id_criterio"] for e in evaluaciones]
            if len(ids) != len(set(ids)):
                raise ValueError("Hay criterios repetidos.")
            validos = {
                x[0]
                for x in db.query(CriterioInspeccion.id_criterio)
                .filter(
                    CriterioInspeccion.id_maquina == id_maquina,
                    CriterioInspeccion.activo.is_(True),
                )
                .all()
            }
            if set(ids) != validos:
                raise ValueError("Se deben evaluar todos los criterios activos de esta máquina.")
            if not all(isinstance(e.get("cumple"), bool) for e in evaluaciones):
                raise ValueError("Marca Cumple o No cumple en cada criterio.")

            if id_programacion is not None:
                programada = db.get(RevisionProgramada, id_programacion)
                if (
                    not programada
                    or programada.estado != "Programada"
                    or programada.id_maquina != id_maquina
                ):
                    raise ValueError("La programación no existe, ya se realizó o es de otra máquina.")
                id_inspector = programada.id_responsable
            else:
                programada = None

            inspector = (
                db.query(Usuario)
                .filter(Usuario.id_usuario == id_inspector, Usuario.activo.is_(True))
                .first()
            )
            if not maquina or not inspector:
                raise ValueError("Máquina o inspector inexistente/inactivo.")

            origen = None
            if id_revision_origen is not None:
                origen = db.get(Inspeccion, id_revision_origen)
                if not origen or origen.id_maquina != id_maquina:
                    raise ValueError("La revisión origen no existe o pertenece a otra máquina.")
                extra = db.execute(text(
                    "SELECT estado_revision FROM revisiones WHERE id_inspeccion=:id"
                ), {"id": id_revision_origen}).scalar_one_or_none()
                if origen.resultado_final != "Requiere atención" or extra == "Corregida":
                    raise ValueError("La revisión origen ya no requiere una correctiva.")

            fallas = any(not e["cumple"] for e in evaluaciones)
            nuevo = Inspeccion(
                codigo_inspeccion="INS-" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid4().hex[:5].upper(),
                id_maquina=id_maquina,
                id_inspector=id_inspector,
                tipo_inspeccion=tipo,
                resultado_final="Requiere atención" if fallas else "Aprobada",
                observaciones_generales=observaciones[:500] if observaciones else None,
            )
            db.add(nuevo)
            db.flush()

            estado_nuevo = "Abierta" if fallas else "Cerrada"
            db.execute(text("""
                UPDATE revisiones
                SET estado_revision=:estado, id_revision_origen=:origen
                WHERE id_inspeccion=:id
            """), {
                "estado": estado_nuevo,
                "origen": id_revision_origen,
                "id": nuevo.id_inspeccion,
            })

            for e in evaluaciones:
                db.add(ResultadoInspeccion(
                    id_inspeccion=nuevo.id_inspeccion,
                    id_criterio=e["id_criterio"],
                    cumple=e["cumple"],
                    valor_medido=(e.get("medido") or "")[:150],
                    valor_esperado=(e.get("esperado") or "")[:150],
                    observacion=e.get("observacion") or None,
                ))
                if not e["cumple"]:
                    db.add(Hallazgo(
                        id_inspeccion=nuevo.id_inspeccion,
                        id_criterio=e["id_criterio"],
                        nivel_severidad="Media",
                        descripcion=(e.get("observacion") or "Criterio no cumple")[:500],
                        estado="Abierto",
                    ))

            if programada is not None:
                programada.estado = "Completada"
                programada.id_inspeccion = nuevo.id_inspeccion


            if origen is not None and not fallas:
                (
                    db.query(Hallazgo)
                    .filter(
                        Hallazgo.id_inspeccion == origen.id_inspeccion,
                        Hallazgo.estado.in_(["Abierto", "En proceso", "Pendiente de verificación"]),
                    )
                    .update({Hallazgo.estado: "Cerrado"}, synchronize_session=False)
                )
                db.execute(text("""
                    UPDATE revisiones
                    SET estado_revision='Corregida'
                    WHERE id_inspeccion=:id
                """), {"id": origen.id_inspeccion})

            db.flush()
            _actualizar_estado_maquina(db, id_maquina)
            db.commit()
            return nuevo.codigo_inspeccion
        except Exception:
            db.rollback()
            raise


def listar_programadas(solo_activas=True):

    with SessionLocal() as db:
        consulta = (
            db.query(RevisionProgramada, Maquina, Usuario)
            .join(Maquina, RevisionProgramada.id_maquina == Maquina.id_maquina)
            .join(Usuario, RevisionProgramada.id_responsable == Usuario.id_usuario)
        )
        if solo_activas:
            consulta = consulta.filter(RevisionProgramada.estado == "Programada")
        filas = consulta.order_by(RevisionProgramada.fecha_programada.asc()).all()

        salida = []
        for p, m, u in filas:
            estado = p.estado
            if estado == "Programada" and p.fecha_programada < date.today():
                estado = "Vencida"
            salida.append({
                "id": p.id_programacion,
                "id_maquina": p.id_maquina,
                "maquina": m.nombre,
                "codigo_maquina": m.codigo_maquina,
                "responsable": u.nombre,
                "fecha": p.fecha_programada,
                "descripcion": p.descripcion,
                "observaciones": p.observaciones or "",
                "estado": estado,
                "id_inspeccion": p.id_inspeccion,
            })
        return salida


def listar_historial_programadas():
    with SessionLocal() as db:
        filas = (
            db.query(RevisionProgramada, Maquina, Usuario)
            .join(Maquina, RevisionProgramada.id_maquina == Maquina.id_maquina)
            .join(Usuario, RevisionProgramada.id_responsable == Usuario.id_usuario)
            .filter(RevisionProgramada.estado.in_(["Completada", "Cancelada"]))
            .order_by(RevisionProgramada.creado_en.desc())
            .all()
        )
        return [{
            "id": p.id_programacion,
            "id_maquina": p.id_maquina,
            "maquina": m.nombre,
            "codigo_maquina": m.codigo_maquina,
            "responsable": u.nombre,
            "fecha": p.fecha_programada,
            "descripcion": p.descripcion,
            "observaciones": p.observaciones or "",
            "estado": p.estado,
            "id_inspeccion": p.id_inspeccion,
        } for p, m, u in filas]


def programar_preventiva(id_maquina, id_responsable, fecha, descripcion):
    if not (descripcion or "").strip():
        raise ValueError("Agrega una descripción.")
    if fecha < date.today():
        raise ValueError("La fecha programada no puede ser anterior a hoy.")
    with SessionLocal() as db:
        if not db.get(Maquina, id_maquina):
            raise ValueError("No existe esa máquina.")
        inspector = db.execute(text("""
            SELECT 1
            FROM usuarios u
            JOIN usuario_roles ur ON ur.id_usuario = u.id_usuario
            JOIN roles r ON r.id_rol = ur.id_rol
            WHERE u.id_usuario=:id AND u.activo=TRUE
              AND r.nombre_rol='Inspector'
        """), {"id": id_responsable}).scalar_one_or_none()
        if not inspector:
            raise ValueError("El responsable seleccionado no es un Inspector activo.")
        p = RevisionProgramada(
            id_maquina=id_maquina,
            id_responsable=id_responsable,
            fecha_programada=fecha,
            descripcion=descripcion.strip(),
            estado="Programada",
        )
        db.add(p)
        db.commit()
        return p.id_programacion


def cancelar_programada(id_programacion, id_usuario):
    with SessionLocal() as db:
        p = db.get(RevisionProgramada, id_programacion)
        if p is None:
            raise ValueError("No existe esa preventiva.")
        if p.estado != "Programada":
            raise ValueError("Solo se pueden cancelar preventivas programadas.")
        p.estado = "Cancelada"
        p.observaciones = f"Cancelada por usuario {id_usuario}."
        db.commit()


def reprogramar_preventiva(id_programacion, fecha, descripcion):
    if fecha < date.today():
        raise ValueError("La nueva fecha debe ser hoy o posterior.")
    if not (descripcion or "").strip():
        raise ValueError("Agrega una descripción.")
    with SessionLocal() as db:
        p = db.get(RevisionProgramada, id_programacion)
        if p is None or p.estado != "Programada":
            raise ValueError("Solo puedes editar preventivas programadas.")
        p.fecha_programada = fecha
        p.descripcion = descripcion.strip()
        db.commit()


def obtener_rol_usuario(id_usuario):

    if not id_usuario:
        return "Sin rol"
    with SessionLocal() as db:
        filas = db.execute(text("""
            SELECT r.nombre_rol
            FROM usuario_roles ur
            JOIN roles r ON r.id_rol = ur.id_rol
            WHERE ur.id_usuario = :id
        """), {"id": id_usuario}).scalars().all()
    prioridad = ["Administrador", "Inspector", "Técnico"]
    for nombre in prioridad:
        if nombre in filas:
            return nombre
    return filas[0] if filas else "Sin rol"


def listar_roles():
    with SessionLocal() as db:
        return list(db.execute(text("SELECT nombre_rol FROM roles ORDER BY id_rol")).scalars().all())


def listar_usuarios_roles():
    with SessionLocal() as db:
        filas = db.execute(text("""
            SELECT u.id_usuario, u.nombre, u.correo, u.nombre_usuario, u.activo,
                   string_agg(r.nombre_rol, ', ' ORDER BY r.nombre_rol) AS roles
            FROM usuarios u
            LEFT JOIN usuario_roles ur ON ur.id_usuario = u.id_usuario
            LEFT JOIN roles r ON r.id_rol = ur.id_rol
            GROUP BY u.id_usuario, u.nombre, u.correo, u.nombre_usuario, u.activo
            ORDER BY u.nombre
        """)).mappings().all()
        salida = []
        for f in filas:
            roles = [x.strip() for x in (f["roles"] or "").split(",") if x.strip()]
            principal = next((r for r in ["Administrador", "Inspector", "Técnico"] if r in roles), roles[0] if roles else None)
            salida.append({
                "id": f["id_usuario"],
                "nombre": f["nombre"],
                "correo": f["correo"],
                "nombre_usuario": f["nombre_usuario"],
                "activo": f["activo"],
                "rol": principal,
            })
        return salida


def cambiar_rol_usuario(id_usuario, nombre_rol):
    if nombre_rol not in ("Administrador", "Inspector", "Técnico"):
        raise ValueError("Rol no válido.")
    with SessionLocal() as db:
        try:
            rol_id = db.execute(text("SELECT id_rol FROM roles WHERE nombre_rol=:r"), {"r": nombre_rol}).scalar_one_or_none()
            if rol_id is None:
                raise ValueError("El rol no existe. Ejecuta la migración de roles.")
            existe = db.execute(text("SELECT 1 FROM usuarios WHERE id_usuario=:u"), {"u": id_usuario}).scalar_one_or_none()
            if not existe:
                raise ValueError("El usuario no existe.")
            db.execute(text("DELETE FROM usuario_roles WHERE id_usuario=:u"), {"u": id_usuario})
            db.execute(text("INSERT INTO usuario_roles(id_usuario,id_rol) VALUES(:u,:r)"), {"u": id_usuario, "r": rol_id})
            db.commit()
        except Exception:
            db.rollback()
            raise


def crear_usuario_con_rol(nombre, correo, contrasena, nombre_rol):
    nombre = (nombre or "").strip()
    correo = (correo or "").strip().lower()
    contrasena = (contrasena or "").strip()
    if not nombre or not correo or not contrasena or not nombre_rol:
        raise ValueError("Completa todos los campos.")
    if "@" not in correo:
        raise ValueError("Captura un correo válido.")
    with SessionLocal() as db:
        try:
            if db.query(Usuario).filter(Usuario.correo == correo).first():
                raise ValueError("Ese correo ya está registrado.")
            rol_id = db.execute(text("SELECT id_rol FROM roles WHERE nombre_rol=:r"), {"r": nombre_rol}).scalar_one_or_none()
            if rol_id is None:
                raise ValueError("Rol no válido.")

            usuario = Usuario(
                nombre=nombre, correo=correo,
                nombre_usuario=generar_usuario_disponible(db, nombre),
                contrasena_hash=contrasena, activo=True,
            )
            db.add(usuario)
            db.flush()
            db.execute(text("INSERT INTO usuario_roles(id_usuario,id_rol) VALUES(:u,:r)"), {"u": usuario.id_usuario, "r": rol_id})
            db.commit()
            return usuario.id_usuario
        except Exception:
            db.rollback()
            raise


def actualizar_usuario_admin(
    id_admin,
    id_usuario,
    nombre,
    correo,
    nombre_rol,
    activo=True,
    nueva_contrasena=None,
    nombre_usuario=None,
):

    try:
        id_admin = int(id_admin)
        id_usuario = int(id_usuario)
    except (TypeError, ValueError):
        raise ValueError("Usuario no válido.")

    if id_admin == id_usuario:
        raise PermissionError("No puedes editar tu propia cuenta desde Usuarios y roles.")

    nombre = (nombre or "").strip()
    correo = (correo or "").strip().lower()
    nombre_rol = (nombre_rol or "").strip()

    if not nombre:
        raise ValueError("El nombre es obligatorio.")
    if not correo or "@" not in correo:
        raise ValueError("Captura un correo válido.")
    if nombre_rol not in ("Administrador", "Inspector", "Técnico"):
        raise ValueError("Rol no válido.")

    with SessionLocal() as db:
        try:

            admin_es_valido = db.execute(text("""
                SELECT 1
                FROM usuario_roles ur
                JOIN roles r ON r.id_rol = ur.id_rol
                JOIN usuarios u ON u.id_usuario = ur.id_usuario
                WHERE ur.id_usuario = :id
                  AND u.activo = TRUE
                  AND r.nombre_rol = 'Administrador'
                LIMIT 1
            """), {"id": id_admin}).scalar_one_or_none()

            if not admin_es_valido:
                raise PermissionError("Solo un administrador puede editar usuarios.")

            usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
            if usuario is None:
                raise ValueError("El usuario no existe.")

            duplicado = (
                db.query(Usuario)
                .filter(
                    Usuario.correo == correo,
                    Usuario.id_usuario != id_usuario,
                )
                .first()
            )
            if duplicado:
                raise ValueError("Ese correo ya está registrado por otro usuario.")

            rol_id = db.execute(
                text("SELECT id_rol FROM roles WHERE nombre_rol=:rol"),
                {"rol": nombre_rol},
            ).scalar_one_or_none()
            if rol_id is None:
                raise ValueError("El rol seleccionado no existe.")

            nombre_acceso = limpiar_nombre_usuario(nombre_usuario) if nombre_usuario is not None else usuario.nombre_usuario
            if not nombre_acceso:
                raise ValueError("El usuario de acceso no puede estar vacío.")
            repetido = db.query(Usuario.id_usuario).filter(
                func.lower(Usuario.nombre_usuario) == nombre_acceso.lower(),
                Usuario.id_usuario != id_usuario,
            ).first()
            if repetido:
                raise ValueError("Ese nombre de usuario ya está ocupado.")

            usuario.nombre = nombre
            usuario.correo = correo
            usuario.nombre_usuario = nombre_acceso
            usuario.activo = bool(activo)

            nueva_contrasena = (nueva_contrasena or "").strip()
            if nueva_contrasena:

                usuario.contrasena_hash = nueva_contrasena

            db.execute(
                text("DELETE FROM usuario_roles WHERE id_usuario=:id"),
                {"id": id_usuario},
            )
            db.execute(
                text("INSERT INTO usuario_roles(id_usuario,id_rol) VALUES(:u,:r)"),
                {"u": id_usuario, "r": rol_id},
            )

            db.commit()
        except Exception:
            db.rollback()
            raise

def listar_tecnicos():
    with SessionLocal() as db:
        filas = db.execute(text("""
            SELECT DISTINCT u.id_usuario, u.nombre, u.correo
            FROM usuarios u
            JOIN usuario_roles ur ON ur.id_usuario = u.id_usuario
            JOIN roles r ON r.id_rol = ur.id_rol
            WHERE u.activo = TRUE AND r.nombre_rol = 'Técnico'
            ORDER BY u.nombre
        """)).mappings().all()
        return [{"id": f["id_usuario"], "nombre": f["nombre"], "correo": f["correo"]} for f in filas]


def listar_inspectores():
    with SessionLocal() as db:
        filas = db.execute(text("""
            SELECT DISTINCT u.id_usuario, u.nombre, u.correo
            FROM usuarios u
            JOIN usuario_roles ur ON ur.id_usuario = u.id_usuario
            JOIN roles r ON r.id_rol = ur.id_rol
            WHERE u.activo = TRUE AND r.nombre_rol = 'Inspector'
            ORDER BY u.nombre
        """)).mappings().all()
        return [
            {"id": f["id_usuario"], "nombre": f["nombre"], "correo": f["correo"]}
            for f in filas
        ]


def _requiere_rol(id_usuario, permitidos):
    rol_actual = obtener_rol_usuario(id_usuario)
    if rol_actual not in permitidos:
        raise PermissionError("No tienes permiso para realizar esta acción.")
    return rol_actual


def listar_hallazgos_y_acciones(id_usuario, rol_usuario):

    with SessionLocal() as db:
        parametros = {"uid": id_usuario}
        filtro = ""
        if rol_usuario == "Técnico":
            filtro = "AND ac.id_responsable = :uid AND COALESCE(ac.estado, 'Asignada') <> 'Verificada'"
        elif rol_usuario in ("Inspector", "Administrador"):
            filtro = "AND (h.estado <> 'Cerrado' OR COALESCE(ac.estado, '') = 'Pendiente de verificación')"
        else:
            return []

        filas = db.execute(text(f"""
            SELECT h.id_hallazgo,
                   h.descripcion AS descripcion_hallazgo,
                   h.nivel_severidad AS severidad,
                   h.estado AS estado_hallazgo,
                   rev.id_inspeccion,
                   rev.codigo_inspeccion AS codigo_revision,
                   m.id_maquina,
                   m.codigo_maquina,
                   m.nombre AS maquina,
                   ac.id_accion,
                   ac.descripcion_accion,
                   ac.estado AS estado_accion,
                   ac.fecha_compromiso,
                   ac.fecha_realizada,
                   ac.observaciones_tecnico,
                   ac.observaciones_verificacion,
                   tec.nombre AS tecnico
            FROM hallazgos h
            JOIN revisiones rev ON rev.id_inspeccion = h.id_inspeccion
            JOIN maquinas m ON m.id_maquina = rev.id_maquina
            LEFT JOIN LATERAL (
                SELECT a.*
                FROM acciones_correctivas a
                WHERE a.id_hallazgo = h.id_hallazgo
                ORDER BY a.id_accion DESC
                LIMIT 1
            ) ac ON TRUE
            LEFT JOIN usuarios tec ON tec.id_usuario = ac.id_responsable
            WHERE TRUE {filtro}
            ORDER BY rev.fecha_inspeccion DESC, h.id_hallazgo DESC
        """), parametros).mappings().all()
        return [dict(f) for f in filas]


def asignar_hallazgo(id_hallazgo, id_tecnico, id_asignador, descripcion_accion, fecha_compromiso):
    _requiere_rol(id_asignador, ("Inspector", "Administrador"))
    descripcion_accion = (descripcion_accion or "").strip()
    if not descripcion_accion:
        raise ValueError("Describe el trabajo que debe realizar el técnico.")
    with SessionLocal() as db:
        try:
            h = db.get(Hallazgo, id_hallazgo)
            if h is None or h.estado == "Cerrado":
                raise ValueError("El hallazgo no existe o ya está cerrado.")
            tecnico_ok = db.execute(text("""
                SELECT 1
                FROM usuario_roles ur
                JOIN roles r ON r.id_rol=ur.id_rol
                JOIN usuarios u ON u.id_usuario=ur.id_usuario
                WHERE ur.id_usuario=:u AND r.nombre_rol='Técnico' AND u.activo=TRUE
            """), {"u": id_tecnico}).scalar_one_or_none()
            if not tecnico_ok:
                raise ValueError("El responsable seleccionado no es un Técnico activo.")
            nombre_tecnico = db.execute(text("SELECT nombre FROM usuarios WHERE id_usuario=:u"), {"u": id_tecnico}).scalar_one()

            db.execute(text("""
                INSERT INTO acciones_correctivas
                    (id_hallazgo, descripcion_accion, responsable, fecha_compromiso,
                     completada, id_responsable, id_asignado_por, estado)
                VALUES
                    (:h, :d, :nombre, :f, FALSE, :tec, :asig, 'Asignada')
            """), {
                "h": id_hallazgo,
                "d": descripcion_accion[:500],
                "nombre": nombre_tecnico[:150],
                "f": fecha_compromiso,
                "tec": id_tecnico,
                "asig": id_asignador,
            })
            h.estado = "En proceso"
            db.commit()
        except Exception:
            db.rollback()
            raise


def registrar_trabajo_tecnico(id_accion, id_tecnico, observaciones):
    _requiere_rol(id_tecnico, ("Técnico",))
    observaciones = (observaciones or "").strip()
    if not observaciones:
        raise ValueError("Describe el trabajo realizado.")
    with SessionLocal() as db:
        try:
            fila = db.execute(text("""
                SELECT id_hallazgo, id_responsable, estado
                FROM acciones_correctivas
                WHERE id_accion=:a
            """), {"a": id_accion}).mappings().first()
            if not fila:
                raise ValueError("La acción correctiva no existe.")
            if fila["id_responsable"] != id_tecnico:
                raise PermissionError("Esta tarea no está asignada a tu usuario.")
            if fila["estado"] not in ("Asignada", "En proceso", "Requiere ajuste"):
                raise ValueError("Esta tarea ya fue enviada o verificada.")
            db.execute(text("""
                UPDATE acciones_correctivas
                SET estado='Pendiente de verificación', completada=TRUE,
                    fecha_realizada=CURRENT_TIMESTAMP,
                    observaciones_tecnico=:o
                WHERE id_accion=:a
            """), {"a": id_accion, "o": observaciones})
            db.execute(text("""
                UPDATE hallazgos SET estado='Pendiente de verificación'
                WHERE id_hallazgo=:h
            """), {"h": fila["id_hallazgo"]})
            db.commit()
        except Exception:
            db.rollback()
            raise


def verificar_trabajo(id_accion, id_inspector, aprobado, observaciones=""):
    _requiere_rol(id_inspector, ("Inspector", "Administrador"))
    with SessionLocal() as db:
        try:
            fila = db.execute(text("""
                SELECT ac.id_hallazgo, ac.estado, h.id_inspeccion, r.id_maquina
                FROM acciones_correctivas ac
                JOIN hallazgos h ON h.id_hallazgo = ac.id_hallazgo
                JOIN revisiones r ON r.id_inspeccion = h.id_inspeccion
                WHERE ac.id_accion=:a
            """), {"a": id_accion}).mappings().first()
            if not fila:
                raise ValueError("La acción correctiva no existe.")
            if fila["estado"] != "Pendiente de verificación":
                raise ValueError("El técnico todavía no ha enviado este trabajo a verificación.")

            if aprobado:
                db.execute(text("""
                    UPDATE acciones_correctivas
                    SET estado='Verificada', id_verificador=:v,
                        fecha_verificacion=CURRENT_TIMESTAMP,
                        observaciones_verificacion=:o
                    WHERE id_accion=:a
                """), {"a": id_accion, "v": id_inspector, "o": (observaciones or "").strip()})
                db.execute(text("UPDATE hallazgos SET estado='Cerrado' WHERE id_hallazgo=:h"), {"h": fila["id_hallazgo"]})

                abiertos = db.execute(text("""
                    SELECT COUNT(*)
                    FROM hallazgos
                    WHERE id_inspeccion=:r AND estado <> 'Cerrado'
                """), {"r": fila["id_inspeccion"]}).scalar_one()
                if abiertos == 0:
                    db.execute(text("""
                        UPDATE revisiones SET estado_revision='Corregida'
                        WHERE id_inspeccion=:r
                    """), {"r": fila["id_inspeccion"]})
            else:
                db.execute(text("""
                    UPDATE acciones_correctivas
                    SET estado='Requiere ajuste', completada=FALSE,
                        id_verificador=:v, fecha_verificacion=CURRENT_TIMESTAMP,
                        observaciones_verificacion=:o
                    WHERE id_accion=:a
                """), {"a": id_accion, "v": id_inspector, "o": (observaciones or "").strip()})
                db.execute(text("UPDATE hallazgos SET estado='En proceso' WHERE id_hallazgo=:h"), {"h": fila["id_hallazgo"]})

            db.flush()
            _actualizar_estado_maquina(db, fila["id_maquina"])
            db.commit()
        except Exception:
            db.rollback()
            raise
