"""Pantalla real de revisiones para QualityCheck (Flet). Renombrar a revisiones.py."""
from io import BytesIO
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import flet as ft
import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from revision_backend import (
    obtener_maquinas, obtener_criterios, obtener_revisiones, obtener_detalle,
    guardar_revision, listar_programadas, programar_preventiva,
    cancelar_programada, reprogramar_preventiva,
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
    story = [p('QUALITYCHECK / REPORTE DE INSPECCIÓN'), Spacer(1, 12)]
    for etiqueta, valor in [
        ('Revisión', revision['codigo']), ('Máquina', revision['codigo_maquina'] + ' · ' + revision['maquina']),
        ('Inspector', revision['inspector']), ('Tipo', revision['tipo']),
        ('Fecha', fecha), ('Resultado', revision['resultado']),
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
    doc.build(story)
    return salida.getvalue()


def vista_revisiones(page: ft.Page):
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

    def listado():
        body.controls.clear()
        body.controls.extend([
            ft.Row([
                ft.Column([
                    texto('Revisiones técnicas', 20, True),
                    texto('Consulta inspecciones realizadas y registra nuevas revisiones.', 12, color=GRIS),
                ], spacing=2, expand=True),
                ft.IconButton(icon=ft.Icons.REFRESH, icon_color=estilos.COLOR_TEXTO, tooltip='Actualizar', on_click=lambda e: listado()),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            boton_primario('＋  NUEVA REVISIÓN', lambda e: nueva_revision()),
            boton_secundario('PROGRAMAR / VER PREVENTIVAS', lambda e: preventivas()),
            ft.Divider(height=8, color=BORDE),
        ])
        try:
            registros = obtener_revisiones()
            body.controls.append(texto(f'{len(registros)} revisión(es) registrada(s)', 12, color=GRIS))
            for r in registros:
                fecha = r['fecha'].strftime('%d/%m/%Y') if r['fecha'] else 'Sin fecha'
                body.controls.append(card([
                    ft.Row([
                        ft.Column([
                            texto(r['codigo_maquina'] + ' · ' + r['maquina'], 14, True),
                            texto(r['codigo'], 11, color=GRIS),
                        ], spacing=2, expand=True),
                        etiqueta_estado(r['resultado']),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=1, color=BORDE),
                    ft.Row([
                        ft.Icon(ft.Icons.BUILD_OUTLINED, size=16, color=GRIS),
                        texto(r['tipo'], 11, color=GRIS),
                        ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=16, color=GRIS),
                        texto(fecha, 11, color=GRIS),
                    ], spacing=6),
                    ft.Row([
                        ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=GRIS),
                        texto(r['inspector'], 11, color=GRIS, expand=True),
                        texto('Ver detalle  ›', 11, True, estilos.COLOR_PRINCIPAL),
                    ], spacing=6),
                ], on_click=lambda e, rev=r: ver_detalle(rev)))
            if not registros:
                body.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.ASSIGNMENT_OUTLINED, size=44, color='#9CA3AF'),
                            texto('Aún no hay revisiones', 15, True),
                            texto('Registra la primera revisión para comenzar el historial.', 12, color=GRIS, text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        bgcolor=BLANCO,
                        border=ft.Border.all(1, BORDE),
                        border_radius=12,
                        padding=28,
                        alignment=ft.Alignment.CENTER,
                    )
                )
        except Exception as exc:
            body.controls.append(texto('Error al consultar revisiones: ' + str(exc), color=ROJO))
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
                    programar_preventiva(int(maquina.value), int(page.session.store.get('usuario_id')),
                                       dia, descripcion.value)
                    mensaje = 'Preventiva programada.'
                preventivas()
                aviso(mensaje)
            except ValueError as exc:
                aviso('Revisa los datos: ' + str(exc))
            except Exception as exc:
                aviso('No se pudo guardar: ' + str(exc))

        body.controls.extend([maquina, selector_fecha, descripcion,
                              boton_primario('GUARDAR PREVENTIVA', guardar)])
        page.update()

    def ver_detalle(r):
        body.controls.clear()
        body.controls.extend(encabezado_seccion(
            'Resultado de inspección',
            'Consulta el resultado guardado y los criterios evaluados.',
            volver=lambda e: listado(),
        ))
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
                ]))

        async def guardar_pdf(e):
            try:
                contenido = construir_pdf(r, detalle)
                destino = await selector_pdf.save_file(
                    dialog_title='Guardar reporte PDF', file_name=r['codigo'] + '.pdf',
                    file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=['pdf'],
                    src_bytes=contenido if page.web else None,
                )
                if page.web:
                    aviso('Se envió el archivo PDF al navegador.')
                elif destino:
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
    listado()
