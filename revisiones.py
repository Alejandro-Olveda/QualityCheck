from io import BytesIO
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import text
from database import SessionLocal
from xml.sax.saxutils import escape

import flet as ft
import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from revision_backend import (
    obtener_maquinas, obtener_criterios, obtener_revisiones, obtener_detalle,
    guardar_revision, listar_programadas, programar_preventiva,
    cancelar_programada, reprogramar_preventiva, listar_inspectores,
)

BORDE = '#E1E3E6'
BLANCO = '#FFFFFF'
GRIS = '#6B7280'
VERDE = '#15803D'
ROJO = '#B91C1C'
AMARILLO = '#B45309'


def construir_pdf(revision, detalle):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    fuente_dir = Path(reportlab.__file__).parent / 'fonts'
    if 'QC-Vera' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('QC-Vera', str(fuente_dir / 'Vera.ttf')))
    estilo = getSampleStyleSheet()
    estilo.add(ParagraphStyle(name='QC', fontName='QC-Vera', fontSize=9, leading=13))
    def p(s):
        return Paragraph(escape(str(s or '—')).replace('\n', '<br/>'), estilo['QC'])
    salida = BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    fecha = revision['fecha'].strftime('%d/%m/%Y %H:%M') if revision['fecha'] else '—'
    story = [p('QUALITYCHECK / REPORTE DE HALLAZGOS, ACCIONES CORRECTIVAS Y RESULTADOS'), Spacer(1, 12)]
    for etiqueta, valor in [
        ('Revisión', revision['codigo']), ('Máquina', revision['codigo_maquina'] + ' · ' + revision['maquina']),
        ('Inspector', revision['inspector']), ('Tipo', revision['tipo']),
        ('Fecha', fecha), ('Resultado', revision['resultado']),
        ('Técnico', ', '.join(
            detalle.get('responsables_mantenimiento') or ['Sin asignar']
        )),
        ('Observaciones', revision['observaciones'] or 'Sin observaciones')
    ]:
        story.append(p(f'{etiqueta}: {valor}'))
    story.append(Spacer(1, 18))
    filas = [[p('Criterio'), p('Medido'), p('Esperado'), p('Cumple'), p('Observación')]]
    for c in detalle['criterios']:
        filas.append([p(c['nombre']), p(c['medido']), p(c['esperado']), p('Sí' if c['cumple'] else 'No'), p(c['observacion'])])
    if len(filas) == 1:
        filas.append([p('Sin criterios guardados'), p(''), p(''), p(''), p('')])
    tabla = Table(filas, colWidths=[125, 75, 75, 50, 150], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5A000')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#D1D5DB')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 12))
    story.append(p('Hallazgos registrados: ' + str(len(detalle['hallazgos']))))
    for h in detalle['hallazgos']:
        story.append(p(f"• {h['descripcion']} ({h['severidad']}; {h['estado']})"))
        story.append(p(
            'Técnico: '
            + ', '.join(h.get('tecnicos_mantenimiento') or ['Sin asignar'])
        ))

    # Seguimiento real del hallazgo: se muestra aun cuando la corrección está pendiente.
    with SessionLocal() as db:
        acciones = db.execute(text("""
            SELECT h.descripcion AS hallazgo, h.nivel_severidad AS severidad,
                   ac.descripcion_accion, ac.estado, ac.fecha_compromiso,
                   ac.fecha_realizada, ac.fecha_verificacion,
                   ac.observaciones_tecnico, ac.observaciones_verificacion,
                   COALESCE(tec.nombre, ac.responsable) AS tecnico,
                   ver.nombre AS verificador
            FROM hallazgos h
            LEFT JOIN acciones_correctivas ac ON ac.id_hallazgo = h.id_hallazgo
            LEFT JOIN usuarios tec ON tec.id_usuario = ac.id_responsable
            LEFT JOIN usuarios ver ON ver.id_usuario = ac.id_verificador
            WHERE h.id_inspeccion = :id
            ORDER BY h.id_hallazgo, ac.id_accion
        """), {'id': revision['id']}).mappings().all()

    if acciones:
        story.append(Spacer(1, 16))
        story.append(p('SEGUIMIENTO DE ACCIONES CORRECTIVAS Y RESULTADOS'))
        story.append(Spacer(1, 8))
        def fecha_pdf(valor):
            return valor.strftime('%d/%m/%Y') if valor else '—'
        for a in acciones:
            story.append(p('Hallazgo: ' + a['hallazgo']))
            if not a['descripcion_accion']:
                story.append(p('Acción correctiva: pendiente de asignación'))
            else:
                for etiqueta, valor in [
                    ('Acción correctiva', a['descripcion_accion']),
                    ('Técnico', a['tecnico']),
                    ('Estado', a['estado']),
                    ('Fecha compromiso', fecha_pdf(a['fecha_compromiso'])),
                    ('Fecha realizada', fecha_pdf(a['fecha_realizada'])),
                    ('Trabajo realizado / resultados', a['observaciones_tecnico'] or 'Pendiente'),
                    ('Verificador', a['verificador'] or 'Pendiente'),
                    ('Fecha de verificación', fecha_pdf(a['fecha_verificacion'])),
                    ('Resultado de verificación', a['observaciones_verificacion'] or 'Pendiente'),
                ]:
                    story.append(p(f'{etiqueta}: {valor}'))
            story.append(Spacer(1, 10))
    doc.build(story)
    return salida.getvalue()


def vista_revisiones(page: ft.Page, id_inspeccion_inicial=None):
    if not page.session.store.get('usuario_id'):
        page.go('/')
        return
    page.title = 'QualityCheck - Revisiones Técnicas'
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)
    menu_mas = crear_menu_mas(page)
    selector_pdf = ft.FilePicker()
    page.services.append(selector_pdf)
    body = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    id_revision_ruta = None

    partes_ruta = page.route.rstrip("/").split("/")

    if (
        len(partes_ruta) == 3
        and partes_ruta[1] == "revisiones"
        and partes_ruta[2].isdigit()
    ):
        id_revision_ruta = int(partes_ruta[2])

    def aviso(mensaje):
        page.show_dialog(ft.SnackBar(content=ft.Text(str(mensaje))))

    def montar():
        page.clean()
        page.navigation_bar = None
        configurar_navbar(page, menu_mas, indice_inicial=2)
        page.add(ft.Column([
            crear_header(titulo='Revisiones Técnicas'),
            ft.Stack([
                ft.Container(content=body, padding=16, expand=True),
                ft.Container(content=menu_mas, right=12, bottom=12),
            ], expand=True),
        ], spacing=0, expand=True))
        page.update()

    def texto(s, size=13, negrita=False, color=None, **kwargs):
        return ft.Text(
            str(s),
            size=size,
            color=color or estilos.COLOR_TEXTO,
            weight=ft.FontWeight.BOLD if negrita else ft.FontWeight.NORMAL,
            **kwargs,
        )

    def card(contenido, on_click=None, padding=14):
        return ft.Container(
            content=ft.Column(contenido, spacing=8),
            bgcolor=BLANCO,
            padding=padding,
            border_radius=12,
            border=ft.Border.all(1, BORDE),
            on_click=on_click,
            width=float('inf'),
        )

    def etiqueta_estado(estado):
        estado = estado or 'Pendiente'
        if estado in ('Aprobada', 'Completada'):
            fondo, frente = '#DCFCE7', VERDE
        elif estado in ('No aprobada', 'Vencida', 'Cancelada'):
            fondo, frente = '#FEE2E2', ROJO
        elif estado in ('Requiere atención', 'Programada'):
            fondo, frente = '#FEF3C7', AMARILLO
        else:
            fondo, frente = '#E5E7EB', GRIS
        return ft.Container(
            content=texto(estado, 10, True, frente),
            bgcolor=fondo,
            padding=6,
            border_radius=14,
        )

    def boton_primario(titulo, accion):
        return ft.Button(
            content=ft.Text(titulo, color=estilos.COLOR_TEXTO, weight=ft.FontWeight.BOLD, size=13),
            bgcolor=estilos.COLOR_PRINCIPAL,
            height=46,
            on_click=accion,
        )

    def boton_secundario(titulo, accion):
        return ft.Button(
            content=ft.Text(titulo, color=estilos.COLOR_TEXTO, weight=ft.FontWeight.BOLD, size=13),
            bgcolor=BLANCO,
            height=46,
            on_click=accion,
            style=ft.ButtonStyle(side=ft.BorderSide(1, BORDE)),
        )

    def boton_texto(titulo, accion, color=None, icono=None):
        contenido = []
        if icono is not None:
            contenido.append(ft.Icon(icono, size=17, color=color or estilos.COLOR_TEXTO))
        contenido.append(ft.Text(
            titulo,
            size=12,
            color=color or estilos.COLOR_TEXTO,
            weight=ft.FontWeight.BOLD,
        ))
        return ft.TextButton(
            content=ft.Row(contenido, spacing=5, tight=True),
            on_click=accion,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            ),
        )

    def boton_volver(accion, texto_boton='Volver'):
        return ft.Row(
            [boton_texto(texto_boton, accion, estilos.COLOR_TEXTO, ft.Icons.ARROW_BACK)],
            alignment=ft.MainAxisAlignment.START,
        )

    def encabezado_seccion(titulo, subtitulo=None, volver=None, texto_volver='Volver'):
        controles = []
        if volver is not None:
            controles.append(boton_volver(volver, texto_volver))
        controles.append(texto(titulo, 21, True))
        if subtitulo:
            controles.append(texto(subtitulo, 12, color=GRIS))
        return controles

    def estilizar_campo(control):
        control.bgcolor = BLANCO
        control.border_color = '#BDBDBD'
        control.focused_border_color = estilos.COLOR_PRINCIPAL
        control.color = estilos.COLOR_TEXTO
        return control

    mostrar_historial_completo = False

    def cambiar_historial(e=None):
        nonlocal mostrar_historial_completo
        mostrar_historial_completo = not mostrar_historial_completo
        listado()


    def listado():
        body.controls.clear()

        body.controls.extend(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                texto("Revisiones técnicas", 20, True),
                                texto(
                                    "Consulta inspecciones realizadas y registra nuevas revisiones.",
                                    12,
                                    color=GRIS,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_color=estilos.COLOR_TEXTO,
                            tooltip="Actualizar",
                            on_click=lambda e: listado(),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                boton_primario("＋  NUEVA REVISIÓN", lambda e: nueva_revision()),
                boton_secundario("PROGRAMAR / VER PREVENTIVAS", lambda e: preventivas()),
                ft.Divider(height=8, color=BORDE),
            ]
        )

        try:
            registros = obtener_revisiones()
            aprobadas_ocultas = [
                r for r in registros
                if r.get("resultado") == "Aprobada"
                and r.get("estado_revision") != "Corregida"
            ]
            ids_aprobadas_ocultas = {
                r.get("id") for r in aprobadas_ocultas
            }
            registros_visibles = (
                registros
                if mostrar_historial_completo
                else [
                    r for r in registros
                    if r.get("id") not in ids_aprobadas_ocultas
                ]
            )

            body.controls.append(
                texto(
                    f"{len(registros_visibles)} revisión(es) visible(s) "
                    f"de {len(registros)} registrada(s)",
                    12,
                    color=GRIS,
                )
            )
            if aprobadas_ocultas:
                body.controls.append(
                    boton_secundario(
                        (
                            "OCULTAR APROBADAS"
                            if mostrar_historial_completo
                            else f"VER HISTORIAL COMPLETO ({len(registros)} revisiones)"
                        ),
                        cambiar_historial,
                    )
                )

            for r in registros_visibles:
                fecha = r["fecha"].strftime("%d/%m/%Y") if r.get("fecha") else "Sin fecha"

                contenido_revision = [
                    # Máquina y resultado de la inspección
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    texto(
                                        r["codigo_maquina"] + " · " + r["maquina"], 14, True
                                    ),
                                    texto(r["codigo"], 11, color=GRIS),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            etiqueta_estado(r["resultado"]),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color=BORDE),
                    # Tipo de revisión y fecha
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.BUILD_OUTLINED, size=16, color=GRIS),
                            texto(r["tipo"], 11, color=GRIS),
                            ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=16, color=GRIS),
                            texto(fecha, 11, color=GRIS),
                        ],
                        spacing=6,
                    ),
                    # Inspector que realizó la revisión
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=GRIS),
                            texto(
                                "Inspector: " + str(r.get("inspector") or "Sin asignar"),
                                11,
                                color=GRIS,
                                expand=True,
                            ),
                            texto("Ver detalle  ›", 11, True, estilos.COLOR_PRINCIPAL),
                        ],
                        spacing=6,
                    ),
                ]

                # Información del resultado y del trabajo correctivo
                if (
                    r.get("resultado") == "Aprobada"
                    and r.get("estado_revision") != "Corregida"
                ):
                    contenido_revision.append(
                        texto(
                            "Aprobada desde el inicio · Sin hallazgos "
                            "ni corrección requerida",
                            11,
                            True,
                            VERDE,
                        )
                    )
                else:
                    if r.get("estado_revision") == "Corregida":
                        contenido_revision.append(
                            texto("Corregida mediante hallazgos", 11, True, VERDE)
                        )

                    contenido_revision.append(
                        texto(
                            "Técnico responsable y estado del trabajo", 11, True, AMARILLO
                        )
                    )

                    tecnicos = r.get("tecnicos_trabajo") or [
                        {
                            "tecnico": "Sin asignar",
                            "estado_trabajo": "Sin asignar",
                        }
                    ]

                    for t in tecnicos:
                        contenido_revision.append(
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.PERSON_OUTLINE, size=15, color=GRIS),
                                    texto(
                                        str(t.get("tecnico") or "Sin asignar"),
                                        11,
                                        True,
                                        expand=True,
                                    ),
                                    etiqueta_estado(
                                        t.get("estado_trabajo") or "Sin asignar"
                                    ),
                                ],
                                spacing=6,
                            )
                        )

                body.controls.append(
                    card(contenido_revision, on_click=lambda e, rev=r: ver_detalle(rev))
                )

            if not registros:
                body.controls.append(
                    card(
                        [
                            ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=32, color=GRIS),
                            texto("No hay revisiones registradas.", 14, True),
                        ]
                    )
                )

        except Exception as exc:
            body.controls.append(
                texto("Error al consultar revisiones: " + str(exc), color=ROJO)
            )

        page.update()

    def nueva_revision(maquina_inicial=None, id_programacion=None):
        body.controls.clear()
        body.controls.extend(encabezado_seccion(
            'Nueva revisión',
            'Registra los resultados de una inspección técnica.',
            volver=lambda e: listado(),
        ))
        try:
            maquinas = obtener_maquinas()
        except Exception as exc:
            body.controls.append(texto(f'Error al obtener máquinas: {exc}', color='#B91C1C'))
            page.update()
            return
        if not maquinas:
            body.controls.append(texto('Primero registra una máquina activa.'))
            page.update()
            return
        opciones = [ft.DropdownOption(key=str(m['id']), text=f"{m['codigo']} · {m['nombre']}") for m in maquinas]
        selector_maquina = estilizar_campo(ft.Dropdown(label='Máquina *', options=opciones, value=str(maquina_inicial or maquinas[0]['id']), disabled=id_programacion is not None))
        selector_tipo = estilizar_campo(ft.Dropdown(label='Tipo de revisión *', value='Preventiva', options=[
            ft.DropdownOption(key='Preventiva', text='Preventiva'),
            ft.DropdownOption(key='Rutina', text='Rutina'),
            ft.DropdownOption(key='Correctiva', text='Correctiva')], disabled=id_programacion is not None))
        observaciones = estilizar_campo(ft.TextField(label='Observaciones generales', multiline=True, min_lines=2, max_lines=4))
        zona_criterios = ft.Column(spacing=10)
        evaluaciones = []

        def cargar_criterios(e=None):
            zona_criterios.controls.clear()
            evaluaciones.clear()
            if not selector_maquina.value:
                page.update()
                return
            try:
                criterios = obtener_criterios(int(selector_maquina.value))
                if not criterios:
                    zona_criterios.controls.append(texto('Esta máquina no tiene criterios activos. Agrégalos desde Máquinas.', color='#B45309'))
                for c in criterios:
                    estado = estilizar_campo(ft.Dropdown(label='Resultado *', options=[ft.DropdownOption(key='Cumple', text='Cumple'), ft.DropdownOption(key='No cumple', text='No cumple')]))
                    medido = estilizar_campo(ft.TextField(label='Valor medido (opcional)'))
                    esperado = estilizar_campo(ft.TextField(label='Valor esperado (opcional)'))
                    obs = estilizar_campo(ft.TextField(label='Observación / descripción del fallo', multiline=True, min_lines=1, max_lines=3))
                    zona_criterios.controls.append(card([
                        texto(c['categoria'] + ' · ' + c['nombre'], 14, True),
                        texto(c['descripcion'], 11, color='#6B7280') if c['descripcion'] else ft.Container(),
                        estado, medido, esperado, obs,
                    ]))
                    evaluaciones.append((c['id'], estado, medido, esperado, obs))
            except Exception as exc:
                zona_criterios.controls.append(texto(f'Error al cargar criterios: {exc}', color='#B91C1C'))
            page.update()

        def guardar(e):
            if not evaluaciones:
                aviso('La máquina no tiene criterios para evaluar.')
                return
            if any(estado.value not in ('Cumple', 'No cumple') for _, estado, _, _, _ in evaluaciones):
                aviso('Selecciona Cumple o No cumple en TODOS los criterios.')
                return
            datos = [dict(id_criterio=cid, cumple=estado.value == 'Cumple', medido=medido.value,
                          esperado=esperado.value, observacion=obs.value)
                     for cid, estado, medido, esperado, obs in evaluaciones]
            if any(not d['cumple'] and not (d['observacion'] or '').strip() for d in datos):
                aviso('Describe el problema en cada criterio que No cumple.')
                return
            try:
                codigo = guardar_revision(int(selector_maquina.value),
                                         int(page.session.store.get('usuario_id')),
                                         selector_tipo.value, observaciones.value, datos,
                                         id_programacion=id_programacion)
            except Exception as exc:
                aviso('No se pudo guardar: ' + str(exc))
                return
            listado()
            aviso('Revisión guardada: ' + codigo)

        selector_maquina.on_select = cargar_criterios
        body.controls.extend([
            texto('Datos de la revisión', 16, True),
            texto('Selecciona la máquina y el tipo de inspección.', 12, color=GRIS),
            selector_maquina,
            selector_tipo,
            observaciones,
            ft.Divider(height=12, color=BORDE),
            texto('Criterios de inspección', 16, True),
            texto('Evalúa todos los puntos configurados para esta máquina.', 12, color=GRIS),
            zona_criterios,
            boton_primario('GUARDAR REVISIÓN', guardar),
        ])
        cargar_criterios()
        page.update()

    def preventivas():
        body.controls.clear()
        body.controls.extend(encabezado_seccion(
            'Revisiones preventivas',
            'Programa, reprograma o realiza el mantenimiento preventivo de tus máquinas.',
            volver=lambda e: listado(),
            texto_volver='Volver a inspecciones',
        ))
        body.controls.append(boton_primario('＋  PROGRAMAR PREVENTIVA', lambda e: formulario_preventiva()))
        try:
            programas = listar_programadas()
            body.controls.append(texto(f'{len(programas)} revisión(es) preventiva(s)', 12, color=GRIS))
            for p in programas:
                acciones = []
                if p['estado'] in ('Programada', 'Vencida'):
                    acciones.extend([
                        boton_primario('REALIZAR REVISIÓN', lambda e, p=p: nueva_revision(p['id_maquina'], p['id'])),
                        boton_texto('Reprogramar', lambda e, p=p: formulario_preventiva(p), estilos.COLOR_TEXTO, ft.Icons.EDIT_CALENDAR_OUTLINED),
                        boton_texto('Cancelar', lambda e, p=p: cancelar_preventiva(p), ROJO, ft.Icons.CANCEL_OUTLINED),
                    ])
                body.controls.append(card([
                    ft.Row([
                        texto(f"{p['codigo_maquina']} · {p['maquina']}", 14, True, '#25252B'),
                        etiqueta_estado(p['estado']),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    texto(f"Fecha: {p['fecha']:%d/%m/%Y} · Responsable: {p['responsable']}", 12),
                    texto(p['descripcion'], 12),
                    *acciones,
                ]))
            if not programas:
                body.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.EVENT_NOTE_OUTLINED, size=42, color='#9CA3AF'),
                        texto('No hay preventivas programadas', 15, True),
                        texto('Programa una revisión preventiva para comenzar.', 12, color=GRIS, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    bgcolor=BLANCO, border=ft.Border.all(1, BORDE), border_radius=12, padding=28,
                    alignment=ft.Alignment.CENTER,
                ))
        except Exception as exc:
            body.controls.append(texto('Error consultando preventivas: ' + str(exc), color='#B91C1C'))
        page.update()

    def cancelar_preventiva(p):
        try:
            cancelar_programada(p['id'], int(page.session.store.get('usuario_id')))
            preventivas()
            aviso('Revisión preventiva cancelada.')
        except Exception as exc:
            aviso('No se pudo cancelar: ' + str(exc))

    def formulario_preventiva(programa=None):
        body.controls.clear()
        body.controls.extend(encabezado_seccion(
            'Reprogramar preventiva' if programa else 'Programar preventiva',
            'Define la máquina, la fecha y el trabajo preventivo que se realizará.',
            volver=lambda e: preventivas(),
            texto_volver='Volver a preventivas',
        ))
        try:
            maquinas = obtener_maquinas()
        except Exception as exc:
            body.controls.append(texto('Error al cargar máquinas: ' + str(exc), color='#B91C1C'))
            page.update()
            return
        if not maquinas:
            body.controls.append(texto('Primero registra una máquina activa.'))
            page.update()
            return
        opciones = [ft.DropdownOption(key=str(m['id']), text=f"{m['codigo']} · {m['nombre']}") for m in maquinas]
        maquina = estilizar_campo(ft.Dropdown(label='Máquina', options=opciones,
                              value=str(programa['id_maquina'] if programa else maquinas[0]['id']), disabled=bool(programa)))
        inspector = None
        if programa is None:
            try:
                inspectores = listar_inspectores()
            except Exception as exc:
                body.controls.append(texto('Error al cargar inspectores: ' + str(exc), color='#B91C1C'))
                page.update()
                return
            if not inspectores:
                body.controls.append(texto('Primero registra un Inspector activo para asignar la preventiva.', color='#B45309'))
                page.update()
                return
            inspector = estilizar_campo(ft.Dropdown(
                label='Inspector asignado *',
                options=[
                    ft.DropdownOption(key=str(i['id']), text=i['nombre'])
                    for i in inspectores
                ],
                value=str(inspectores[0]['id']),
            ))
        fecha = estilizar_campo(
            ft.TextField(
                label='Fecha programada *',
                value=(programa['fecha'].isoformat() if programa else date.today().isoformat()),
                read_only=True,
                expand=True,
            )
        )

        def fecha_seleccionada(e):
            if calendario.value:
                fecha.value = calendario.value.date().isoformat()
                page.update()

        calendario = ft.DatePicker(
            value=(programa['fecha'] if programa else date.today()),
            first_date=date.today(),
            last_date=date(date.today().year + 5, 12, 31),
            on_change=fecha_seleccionada,
        )

        def abrir_calendario(e):
            page.show_dialog(calendario)

        selector_fecha = ft.Row(
            [
                fecha,
                ft.IconButton(
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    icon_color=estilos.COLOR_PRINCIPAL,
                    tooltip='Seleccionar fecha',
                    on_click=abrir_calendario,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        descripcion = estilizar_campo(ft.TextField(label='Descripción del mantenimiento',
                                   value=(programa['descripcion'] if programa else ''), multiline=True, min_lines=2))

        def guardar(e):
            try:
                dia = date.fromisoformat((fecha.value or '').strip())
                if programa:
                    reprogramar_preventiva(programa['id'], dia, descripcion.value)
                    mensaje = 'Preventiva reprogramada.'
                else:
                    programar_preventiva(
                        int(maquina.value),
                        int(inspector.value),
                        dia,
                        descripcion.value,
                    )
                    mensaje = 'Preventiva programada.'
                preventivas()
                aviso(mensaje)
            except ValueError as exc:
                aviso('Revisa los datos: ' + str(exc))
            except Exception as exc:
                aviso('No se pudo guardar: ' + str(exc))

        controles = [maquina]
        if inspector is not None:
            controles.append(inspector)
        controles.extend([selector_fecha, descripcion,
                              boton_primario('GUARDAR PREVENTIVA', guardar)])
        body.controls.extend(controles)
        page.update()

    def volver_a_lista(e=None):
        if page.route != "/revisiones":
            page.go("/revisiones")
        else:
            listado()

    def ver_detalle(r):
        body.controls.clear()
        body.controls.extend(
            encabezado_seccion(
                "Resultado de inspección",
                "Consulta el resultado guardado y los criterios evaluados.",
                volver=volver_a_lista,
            )
        )
        try:
            detalle = obtener_detalle(r['id'])
        except Exception as exc:
            body.controls.append(texto(f'Error al obtener detalle: {exc}', color=ROJO))
            page.update()
            return

        criterios = detalle['criterios']
        ok = sum(1 for c in criterios if c['cumple'])
        no_ok = len(criterios) - ok

        body.controls.append(card([
            ft.Row([
                ft.Column([
                    texto(r['codigo'], 15, True),
                    texto(r['codigo_maquina'] + ' · ' + r['maquina'], 13, True),
                ], spacing=3, expand=True),
                etiqueta_estado(r['resultado']),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1, color=BORDE),
            ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE, size=17, color=GRIS), texto('Inspector: ' + r['inspector'], 12)], spacing=6),
            ft.Row([
                ft.Icon(ft.Icons.HANDYMAN_OUTLINED, size=17, color=GRIS),
                texto(
                    'Técnico: '
                    + ', '.join(detalle['responsables_mantenimiento']),
                    12,
                ),
            ], spacing=6),
            ft.Row([ft.Icon(ft.Icons.BUILD_OUTLINED, size=17, color=GRIS), texto('Tipo: ' + r['tipo'], 12)], spacing=6),
            texto('Observaciones: ' + (r['observaciones'] or 'Sin observaciones'), 12, color=GRIS),
        ]))

        body.controls.append(ft.Row([
            ft.Container(
                content=ft.Column([texto('Evaluados', 11, color=GRIS), texto(str(len(criterios)), 22, True)], spacing=2),
                bgcolor=BLANCO, padding=12, border_radius=10, border=ft.Border.all(1, BORDE), expand=True,
            ),
            ft.Container(
                content=ft.Column([texto('Cumplen', 11, color=VERDE), texto(str(ok), 22, True, VERDE)], spacing=2),
                bgcolor='#F0FDF4', padding=12, border_radius=10, border=ft.Border.all(1, '#BBF7D0'), expand=True,
            ),
            ft.Container(
                content=ft.Column([texto('No cumplen', 11, color=ROJO), texto(str(no_ok), 22, True, ROJO)], spacing=2),
                bgcolor='#FEF2F2', padding=12, border_radius=10, border=ft.Border.all(1, '#FECACA'), expand=True,
            ),
        ], spacing=8))

        body.controls.append(texto('Criterios evaluados', 16, True))
        if criterios:
            for c in criterios:
                resultado = 'Cumple' if c['cumple'] else 'No cumple'
                color = VERDE if c['cumple'] else ROJO
                fondo = '#DCFCE7' if c['cumple'] else '#FEE2E2'
                datos_valores = []
                if c['medido'] or c['esperado']:
                    datos_valores.append(
                        ft.Row([
                            ft.Column([texto('Medido', 10, color=GRIS), texto(c['medido'] or '—', 12, True)], expand=True, spacing=1),
                            ft.Column([texto('Esperado', 10, color=GRIS), texto(c['esperado'] or '—', 12, True)], expand=True, spacing=1),
                        ], spacing=10)
                    )
                contenido = [
                    ft.Row([
                        ft.Column([
                            texto(c.get('categoria') or 'General', 10, True, estilos.COLOR_PRINCIPAL),
                            texto(c['nombre'], 14, True),
                        ], spacing=2, expand=True),
                        ft.Container(texto(resultado, 10, True, color), bgcolor=fondo, padding=6, border_radius=14),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    *datos_valores,
                ]
                if c['observacion']:
                    contenido.append(ft.Container(
                        content=texto('Observación: ' + c['observacion'], 12),
                        bgcolor='#F9FAFB', padding=9, border_radius=7,
                    ))
                body.controls.append(card(contenido))
        else:
            body.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=34, color='#9CA3AF'),
                    texto('No hay resultados de criterios guardados', 14, True),
                    texto('Esta revisión no tiene filas en resultados_inspeccion.', 11, color=GRIS, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                bgcolor=BLANCO, border=ft.Border.all(1, BORDE), border_radius=12, padding=22,
            ))

        if detalle['hallazgos']:
            body.controls.append(texto('Hallazgos', 16, True))
            for h in detalle['hallazgos']:
                body.controls.append(card([
                    ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=AMARILLO, size=20),
                        texto(h['descripcion'], 12, True, expand=True),
                    ], spacing=8),
                    texto(h['severidad'] + ' · ' + h['estado'], 11, color=GRIS),
                    texto(
                        'Técnico: '
                        + ', '.join(h.get('tecnicos_mantenimiento') or ['Sin asignar']),
                        11,
                        color=GRIS,
                    ),
                ]))

        async def guardar_pdf(e):
            try:
                contenido = construir_pdf(r, detalle)
                if page.web:
                    # Un enlace aleatorio de 2 min: el servidor ofrece un PDF real con Content-Disposition.
                    # Este paso lo intercepta GeckoView mediante onExternalResponse.
                    from descarga_pdf_segura import crear_descarga
                    token = crear_descarga(contenido, r['codigo'] + '.pdf')
                    import os
                    base = os.environ.get('QC_PUBLIC_BASE_URL', 'https://qualitycheck-e4nz.onrender.com').rstrip('/')
                    enlace = base + '/qc-download/' + token
                    # Abrir la descarga en ventana independiente: la vista Flet no debe navegar ni reiniciarse.
                    launcher = ft.UrlLauncher()
                    page.services.append(launcher)
                    page.update()
                    await launcher.launch_url(enlace, web_only_window_name='_blank')
                else:
                    destino = await selector_pdf.save_file(
                        dialog_title='Guardar reporte PDF', file_name=r['codigo'] + '.pdf',
                        file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['pdf'],
                        src_bytes=contenido,
                    )
                    if destino:
                        ruta = Path(destino)
                        if ruta.suffix.lower() != '.pdf':
                            ruta = Path(str(ruta) + '.pdf')
                        ruta.write_bytes(contenido)
                        aviso('PDF guardado en ' + str(ruta))
            except ImportError:
                aviso('Instala reportlab: python -m pip install reportlab')
            except Exception as exc:
                aviso('Error generando PDF: ' + str(exc))

        body.controls.append(boton_primario('GUARDAR REPORTE PDF', guardar_pdf))
        page.update()

    montar()

    if id_inspeccion_inicial is not None:
        try:
            registros = obtener_revisiones()
            revision = next(
                (r for r in registros if str(r["id"]) == str(id_inspeccion_inicial)),
                None,
            )

            if revision:
                ver_detalle(revision)
            else:
                listado()
                aviso("No se encontró el resultado de esa inspección.")
        except Exception as exc:
            listado()
            aviso("No se pudo abrir el resultado: " + str(exc))
    else:
        listado()
