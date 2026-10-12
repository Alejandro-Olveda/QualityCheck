from pathlib import Path

import flet as ft

import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from revision_backend import obtener_revisiones, obtener_detalle

TEXTO = '#25252B'
GRIS = '#626A75'
BORDE = '#E1E3E6'


def _fecha(fecha):
    return fecha.strftime('%d/%m/%Y') if fecha and hasattr(fecha, 'strftime') else 'Sin fecha'


def vista_historial(page: ft.Page):
    if not page.session.store.get('usuario_id'):
        page.go('/')
        return
    page.title = 'QualityCheck - Historial de revisiones'
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)
    menu = crear_menu_mas(page)
    selector_pdf = ft.FilePicker()
    page.services.append(selector_pdf)
    cuerpo = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)
    busqueda = ft.TextField(label='Buscar por código, máquina o inspector', prefix_icon=ft.Icons.SEARCH,
                            bgcolor='#FFFFFF', color=TEXTO, border_color=BORDE)
    resultado = ft.Dropdown(label='Resultado', value='Todos',
                            options=[ft.DropdownOption(key='Todos', text='Todos')],
                            bgcolor='#FFFFFF', color=TEXTO, expand=True)
    datos = {'revisiones': [], 'error': None}

    def card(controles):
        return ft.Container(content=ft.Column(controles, spacing=7), bgcolor='#FFFFFF',
                            border=ft.Border.all(1, BORDE), border_radius=12, padding=14)

    def cargar(e=None):
        try:
            datos['revisiones'] = obtener_revisiones()
            estados = sorted({str(r.get('resultado') or 'Pendiente') for r in datos['revisiones']})
            resultado.options = [ft.DropdownOption(key='Todos', text='Todos')] + [
                ft.DropdownOption(key=estado, text=estado) for estado in estados
            ]
            if resultado.value not in ['Todos'] + estados:
                resultado.value = 'Todos'
            datos['error'] = None
        except Exception as exc:
            datos['revisiones'] = []
            datos['error'] = str(exc)
        listado()

    def listado(e=None):
        cuerpo.controls.clear()
        cuerpo.controls.extend([
            ft.Text('Historial de revisiones', size=22, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text('Consulta las inspecciones anteriores, sus criterios y los hallazgos. La Bitácora conserva la cronología general de mantenimiento.', size=12, color=GRIS),
            busqueda,
            ft.Row([resultado, ft.Button('Actualizar', icon=ft.Icons.REFRESH, on_click=cargar)], spacing=8),
        ])
        if datos['error']:
            cuerpo.controls.append(ft.Text('Error consultando el historial: ' + datos['error'], color='#B91C1C'))
            page.update()
            return
        texto = (busqueda.value or '').strip().casefold()
        filas = []
        for r in datos['revisiones']:
            cadena = ' '.join(str(r.get(k) or '') for k in ('codigo', 'maquina', 'codigo_maquina', 'inspector')).casefold()
            if texto and texto not in cadena:
                continue
            if resultado.value != 'Todos' and (r.get('resultado') or 'Pendiente') != resultado.value:
                continue
            filas.append(r)
        cuerpo.controls.append(ft.Text(f'{len(filas)} revisión(es)', size=12, weight=ft.FontWeight.BOLD, color=GRIS))
        if not filas:
            cuerpo.controls.append(card([ft.Text('No se encontraron revisiones con estos filtros.', color=GRIS)]))
        for r in filas:
            cuerpo.controls.append(card([
                ft.Row([
                    ft.Column([
                        ft.Text(r['codigo'], size=14, weight=ft.FontWeight.BOLD, color=TEXTO),
                        ft.Text(r['codigo_maquina'] + ' · ' + r['maquina'], size=12, color=TEXTO),
                    ], spacing=3, expand=True),
                    ft.Text(_fecha(r['fecha']), size=11, color=GRIS),
                ]),
                ft.Text('Inspector: ' + r['inspector'], size=11, color=GRIS),
                ft.Text('Tipo: ' + r['tipo'] + ' · Resultado: ' + (r['resultado'] or 'Pendiente'), size=12, color=TEXTO),
                ft.Button(content=ft.Text('VER REVISIÓN COMPLETA', color=TEXTO, weight=ft.FontWeight.BOLD, size=12), bgcolor=estilos.COLOR_PRINCIPAL, height=43, on_click=lambda e, rev=r: detalle(rev)),
            ]))
        page.update()

    def detalle(r):
        cuerpo.controls.clear()
        cuerpo.controls.extend([
            ft.TextButton(content=ft.Row([
                ft.Icon(ft.Icons.ARROW_BACK, size=17, color=TEXTO),
                ft.Text('Volver al historial', size=12, weight=ft.FontWeight.BOLD, color=TEXTO),
            ], spacing=5, tight=True), on_click=listado),
            ft.Text('Resultado de inspección', size=21, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text('Consulta el resultado guardado y los criterios evaluados.', size=12, color=GRIS),
        ])
        try:
            info = obtener_detalle(r['id'])
        except Exception as exc:
            cuerpo.controls.append(ft.Text('Error consultando el detalle: ' + str(exc), color='#B91C1C'))
            page.update()
            return

        def etiqueta(estado):
            estado = estado or 'Pendiente'
            if estado in ('Aprobada', 'Completada'):
                fondo, frente = '#DCFCE7', '#15803D'
            elif estado in ('No aprobada', 'Vencida', 'Cancelada'):
                fondo, frente = '#FEE2E2', '#B91C1C'
            elif estado in ('Requiere atención', 'Programada'):
                fondo, frente = '#FEF3C7', '#B45309'
            else:
                fondo, frente = '#E5E7EB', GRIS
            return ft.Container(content=ft.Text(estado, size=10, weight=ft.FontWeight.BOLD, color=frente),
                                bgcolor=fondo, padding=6, border_radius=14)

        criterios = info['criterios']
        cumplen = sum(1 for c in criterios if c['cumple'])
        no_cumplen = len(criterios) - cumplen
        cuerpo.controls.append(card([
            ft.Row([
                ft.Column([
                    ft.Text(r['codigo'], size=15, weight=ft.FontWeight.BOLD, color=TEXTO),
                    ft.Text(r['codigo_maquina'] + ' · ' + r['maquina'], size=13, weight=ft.FontWeight.BOLD, color=TEXTO),
                ], spacing=3, expand=True),
                etiqueta(r['resultado']),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1, color=BORDE),
            ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE, size=17, color=GRIS),
                    ft.Text('Inspector: ' + r['inspector'], size=12, color=TEXTO)], spacing=6),
            ft.Row([ft.Icon(ft.Icons.BUILD_OUTLINED, size=17, color=GRIS),
                    ft.Text('Tipo: ' + r['tipo'], size=12, color=TEXTO)], spacing=6),
            ft.Text('Fecha: ' + _fecha(r['fecha']), size=12, color=GRIS),
            ft.Text('Observaciones: ' + (r['observaciones'] or 'Sin observaciones'), size=12, color=GRIS),
        ]))

        def indicador(titulo, numero, color, fondo, borde):
            return ft.Container(content=ft.Column([
                ft.Text(titulo, size=11, color=color),
                ft.Text(str(numero), size=22, weight=ft.FontWeight.BOLD, color=color),
            ], spacing=2), bgcolor=fondo, padding=12, border_radius=10,
                border=ft.Border.all(1, borde), expand=True)

        cuerpo.controls.append(ft.Row([
            indicador('Evaluados', len(criterios), GRIS, '#FFFFFF', BORDE),
            indicador('Cumplen', cumplen, '#15803D', '#F0FDF4', '#BBF7D0'),
            indicador('No cumplen', no_cumplen, '#B91C1C', '#FEF2F2', '#FECACA'),
        ], spacing=8))
        cuerpo.controls.append(ft.Text('Criterios evaluados', size=16, weight=ft.FontWeight.BOLD, color=TEXTO))
        if not criterios:
            cuerpo.controls.append(card([ft.Text('No hay resultados de criterios guardados.', color=GRIS)]))
        for c in criterios:
            ok = c['cumple']
            estado = 'Cumple' if ok else 'No cumple'
            color = '#15803D' if ok else '#B91C1C'
            fondo = '#DCFCE7' if ok else '#FEE2E2'
            contenido = [
                ft.Row([
                    ft.Column([
                        ft.Text(c.get('categoria') or 'General', size=10, weight=ft.FontWeight.BOLD, color=estilos.COLOR_PRINCIPAL),
                        ft.Text(c['nombre'], size=14, weight=ft.FontWeight.BOLD, color=TEXTO),
                    ], spacing=2, expand=True),
                    ft.Container(content=ft.Text(estado, size=10, weight=ft.FontWeight.BOLD, color=color),
                                 bgcolor=fondo, padding=6, border_radius=14),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]
            if c['medido'] or c['esperado']:
                contenido.append(ft.Row([
                    ft.Column([ft.Text('Medido', size=10, color=GRIS),
                               ft.Text(c['medido'] or '—', size=12, weight=ft.FontWeight.BOLD, color=TEXTO)], expand=True, spacing=1),
                    ft.Column([ft.Text('Esperado', size=10, color=GRIS),
                               ft.Text(c['esperado'] or '—', size=12, weight=ft.FontWeight.BOLD, color=TEXTO)], expand=True, spacing=1),
                ], spacing=10))
            if c['observacion']:
                contenido.append(ft.Container(content=ft.Text('Observación: ' + c['observacion'], size=12, color=TEXTO),
                                             bgcolor='#F9FAFB', padding=9, border_radius=7))
            cuerpo.controls.append(card(contenido))

        if info['hallazgos']:
            cuerpo.controls.append(ft.Text('Hallazgos', size=16, weight=ft.FontWeight.BOLD, color=TEXTO))
            for h in info['hallazgos']:
                cuerpo.controls.append(card([
                    ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color='#B45309', size=20),
                            ft.Text(h['descripcion'], size=12, weight=ft.FontWeight.BOLD, color=TEXTO, expand=True)], spacing=8),
                    ft.Text(h['severidad'] + ' · ' + h['estado'], size=11, color=GRIS),
                ]))
        if info.get('correctivas'):
            cuerpo.controls.append(ft.Text('Revisiones correctivas relacionadas', size=16, weight=ft.FontWeight.BOLD, color=TEXTO))
            for corr in info['correctivas']:
                cuerpo.controls.append(card([
                    ft.Text(corr['codigo_inspeccion'], size=13, weight=ft.FontWeight.BOLD, color=TEXTO),
                    ft.Text('Resultado: ' + (corr['resultado_final'] or 'Pendiente'), size=12, color=GRIS),
                ]))



    busqueda.on_change = listado
    resultado.on_change = listado
    page.clean()
    page.navigation_bar = None
    configurar_navbar(page, menu, indice_inicial=2)
    page.add(ft.Column([
        crear_header('Historial de revisiones'),
        ft.Stack([
            ft.Container(content=cuerpo, padding=16, expand=True),
            ft.Container(content=menu, right=12, bottom=12),
        ], expand=True),
    ], spacing=0, expand=True))
    cargar()
