from datetime import date, timedelta

import flet as ft
from sqlalchemy import text

import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal

TEXTO = '#25252B'
GRIS = '#626A75'
BORDE = '#E1E3E6'


def _fecha(valor):
    if not valor:
        return None
    return valor.date() if hasattr(valor, 'date') else valor


def obtener_alertas(id_usuario, rol, dias_anticipacion=7):
    """Alertas calculadas en tiempo real; no modifica datos ni necesita tablas nuevas."""
    if rol not in ('Administrador', 'Inspector', 'Técnico'):
        return []
    hoy = date.today()
    avisos = []
    with SessionLocal() as db:
        filtro = 'AND rp.id_responsable = :usuario' if rol == 'Técnico' else ''
        programadas = db.execute(text(f"""
            SELECT rp.id_programacion, rp.fecha_programada, rp.descripcion,
                   m.codigo_maquina, m.nombre AS maquina
            FROM revisiones_programadas rp
            JOIN maquinas m ON m.id_maquina = rp.id_maquina
            WHERE rp.estado = 'Programada' AND rp.fecha_programada <= :limite
            {filtro}
            ORDER BY rp.fecha_programada ASC
        """), {'usuario': id_usuario, 'limite': hoy + timedelta(days=dias_anticipacion)}).mappings().all()
        for fila in programadas:
            f = _fecha(fila['fecha_programada'])
            dias = (f - hoy).days
            avisos.append({
                'tipo': 'Preventiva vencida' if dias < 0 else 'Preventiva próxima',
                'titulo': f"{fila['codigo_maquina']} · {fila['maquina']}",
                'descripcion': fila['descripcion'] or 'Mantenimiento preventivo programado',
                'fecha': f,
                'prioridad': 0 if dias < 0 else (1 if dias <= 2 else 2),
                'ruta': '/revisiones',
                'detalle': f'Vencida hace {-dias} día(s)' if dias < 0 else ('Programada para hoy' if dias == 0 else f'Faltan {dias} día(s)'),
            })

        filtro = 'AND ac.id_responsable = :usuario' if rol == 'Técnico' else ''
        hallazgos = db.execute(text(f"""
            SELECT h.id_hallazgo, h.descripcion, h.estado AS estado_hallazgo,
                   m.codigo_maquina, m.nombre AS maquina,
                   ac.id_accion, ac.estado AS estado_accion, ac.fecha_compromiso
            FROM hallazgos h
            JOIN revisiones r ON r.id_inspeccion = h.id_inspeccion
            JOIN maquinas m ON m.id_maquina = r.id_maquina
            LEFT JOIN LATERAL (
                SELECT a.* FROM acciones_correctivas a
                WHERE a.id_hallazgo = h.id_hallazgo
                ORDER BY a.id_accion DESC LIMIT 1
            ) ac ON TRUE
            WHERE h.estado <> 'Cerrado' {filtro}
            ORDER BY h.id_hallazgo DESC
        """), {'usuario': id_usuario}).mappings().all()

        for h in hallazgos:
            estado = h['estado_accion'] or ''
            f = _fecha(h['fecha_compromiso'])
            dias = (f - hoy).days if f else None
            tipo = None
            prioridad = 2
            detalle = ''

            if rol in ('Administrador', 'Inspector') and estado == 'Pendiente de verificación':
                tipo, prioridad, detalle = 'Pendiente de verificación', 0, 'El inspector debe validar el trabajo'
            elif rol in ('Administrador', 'Inspector') and not h['id_accion']:
                tipo, prioridad, detalle = 'Hallazgo sin asignar', 0, 'Asignar un técnico'
            elif rol == 'Técnico' and estado == 'Requiere ajuste':
                tipo, prioridad, detalle = 'Corrección requiere ajuste', 0, 'Revisar las observaciones del inspector'
            elif estado not in ('Verificada', 'Pendiente de verificación') and dias is not None and dias < 0:
                tipo, prioridad, detalle = 'Correctiva vencida', 0, f'Vencida hace {-dias} día(s)'
            elif estado not in ('Verificada', 'Pendiente de verificación') and dias is not None and dias <= dias_anticipacion:
                tipo, prioridad, detalle = 'Correctiva próxima', 1, 'Vence hoy' if dias == 0 else f'Faltan {dias} día(s)'
            if tipo:
                avisos.append({
                    'tipo': tipo,
                    'titulo': f"{h['codigo_maquina']} · {h['maquina']}",
                    'descripcion': h['descripcion'],
                    'fecha': f,
                    'prioridad': prioridad,
                    'ruta': '/hallazgos',
                    'detalle': detalle,
                })

    avisos.sort(key=lambda a: (a['prioridad'], a['fecha'] or date.max, a['titulo']))
    return avisos


def vista_alertas(page: ft.Page):
    page.go('/configuracion')
