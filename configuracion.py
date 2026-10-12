import flet as ft

import estilos
from alertas import obtener_alertas
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from preferencias import cargar_preferencias, guardar_preferencias, filtrar_notificaciones

TEXTO = '#25252B'
GRIS = '#626A75'
BORDE = '#E1E3E6'


def vista_configuracion(page: ft.Page):
    uid = page.session.store.get('usuario_id')
    rol = page.session.store.get('usuario_rol')
    if not uid:
        page.go('/')
        return

    page.title = 'QualityCheck - Configuración'
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)
    menu = crear_menu_mas(page)
    prefs = cargar_preferencias(uid)
    estado = {'avisos': [], 'error': None}
    lista_avisos = ft.Column(spacing=9)
    resumen = ft.Text('', size=12, color=GRIS)
    mensaje = ft.Text('', size=11, color='#B91C1C')
    filtro = ft.Dropdown(
        label='Mostrar notificaciones', value='Todas',
        options=[ft.DropdownOption(key=x, text=x) for x in ('Todas', 'Urgentes', 'Próximas')],
        bgcolor='#FFFFFF', color=TEXTO, border_color=BORDE, expand=True,
    )

    def card(contenido):
        return ft.Container(
            content=ft.Column(contenido, spacing=10), bgcolor='#FFFFFF',
            border=ft.Border.all(1, BORDE), border_radius=12, padding=15,
        )

    def guardar_cambio(clave, valor):
        anterior = prefs[clave]
        prefs[clave] = valor
        try:
            guardar_preferencias(uid, prefs)
            mensaje.value = ''
        except OSError as exc:
            prefs[clave] = anterior
            mensaje.value = 'No se pudieron guardar las preferencias: ' + str(exc)
        consultar()

    def interruptor(titulo, descripcion, clave):
        control = ft.Switch(value=bool(prefs[clave]), active_color=estilos.COLOR_PRINCIPAL)
        control.on_change = lambda e: guardar_cambio(clave, control.value)
        return ft.Row([
            ft.Column([
                ft.Text(titulo, size=13, weight=ft.FontWeight.BOLD, color=TEXTO),
                ft.Text(descripcion, size=11, color=GRIS),
            ], spacing=3, expand=True),
            control,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    dias = ft.Dropdown(
        label='Avisar con anticipación', value=str(prefs['dias_anticipacion']),
        options=[ft.DropdownOption(key=str(n), text=f'{n} día(s)') for n in (1, 3, 7, 14)],
        bgcolor='#FFFFFF', color=TEXTO, border_color=BORDE,
    )
    if dias.value not in ('1', '3', '7', '14'):
        dias.value = '7'
    dias.on_select = lambda e: guardar_cambio('dias_anticipacion', int(dias.value))

    def consultar(e=None):
        try:
            estado['avisos'] = obtener_alertas(uid, rol, int(prefs['dias_anticipacion']))
            estado['error'] = None
        except Exception as exc:
            estado['error'] = str(exc)
            estado['avisos'] = []
        mostrar_avisos()

    def mostrar_avisos(e=None):
        lista_avisos.controls.clear()
        avisos = filtrar_notificaciones(estado['avisos'], prefs)
        if filtro.value == 'Urgentes':
            avisos = [a for a in avisos if a['prioridad'] == 0]
        elif filtro.value == 'Próximas':
            avisos = [a for a in avisos if a['prioridad'] > 0]
        resumen.value = f'{len(avisos)} notificación(es) para tu cuenta'
        if estado['error']:
            lista_avisos.controls.append(ft.Text('Error al consultar las notificaciones: ' + estado['error'], color='#B91C1C', size=12))
        elif not prefs['notificaciones']:
            lista_avisos.controls.append(ft.Text('Las notificaciones están desactivadas en este equipo.', color=GRIS, size=12))
        elif not avisos:
            lista_avisos.controls.append(ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color='#15803D'),
                ft.Text('No hay notificaciones con estos filtros.', color=GRIS, size=12),
            ], spacing=8))
        else:
            for aviso in avisos:
                urgente = aviso['prioridad'] == 0
                lista_avisos.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED if urgente else ft.Icons.NOTIFICATIONS_OUTLINED,
                                    color='#B91C1C' if urgente else '#B45309', size=21),
                            ft.Column([
                                ft.Text(aviso['tipo'], size=12, weight=ft.FontWeight.BOLD,
                                        color='#B91C1C' if urgente else '#B45309'),
                                ft.Text(aviso['titulo'], size=13, weight=ft.FontWeight.BOLD, color=TEXTO),
                            ], spacing=2, expand=True),
                        ], spacing=8),
                        ft.Text(aviso['descripcion'], size=12, color=TEXTO),
                        ft.Text(aviso['detalle'], size=11, color=GRIS),
                        ft.TextButton('Ver ' + ('revisión' if aviso['ruta'] == '/revisiones' else 'hallazgo'),
                                      on_click=lambda e, ruta=aviso['ruta']: page.go(ruta)),
                    ], spacing=6),
                    bgcolor='#F9FAFB', border_radius=10, padding=11,
                ))
        page.update()

    filtro.on_select = mostrar_avisos
    cuerpo = ft.Column([
        ft.Text('Configuración', size=21, weight=ft.FontWeight.BOLD, color=TEXTO),
        ft.Text('Personaliza los avisos y administra tu cuenta.', size=12, color=GRIS),
        card([
            ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE, color=TEXTO),
                    ft.Text('Mi cuenta', size=16, weight=ft.FontWeight.BOLD, color=TEXTO)], spacing=8),
            ft.Text('Consulta los datos de tu cuenta. Solo un administrador puede modificarlos.', size=12, color=GRIS),
            ft.Button('ABRIR PERFIL', icon=ft.Icons.ARROW_FORWARD, bgcolor=estilos.COLOR_PRINCIPAL,
                      color=TEXTO, on_click=lambda e: page.go('/perfil')),
        ]),
        card([
            ft.Row([ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=TEXTO),
                    ft.Text('Notificaciones', size=16, weight=ft.FontWeight.BOLD, color=TEXTO)], spacing=8),
            ft.Text('Los avisos se calculan con la información actual de Supabase.', size=12, color=GRIS),
            interruptor('Activar notificaciones', 'Mostrar avisos dentro de QualityCheck.', 'notificaciones'),
            ft.Divider(height=1, color=BORDE),
            interruptor('Revisiones preventivas', 'Programaciones próximas o vencidas.', 'preventivas'),
            interruptor('Acciones correctivas', 'Hallazgos y trabajos pendientes o vencidos.', 'correctivas'),
            interruptor('Verificaciones', 'Trabajos terminados que esperan aprobación.', 'verificaciones'),
            dias,
            mensaje,
        ]),
        card([
            ft.Row([
                ft.Column([
                    ft.Text('Mis notificaciones', size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
                    resumen,
                ], spacing=3, expand=True),
                ft.IconButton(icon=ft.Icons.REFRESH, icon_color=TEXTO, tooltip='Actualizar', on_click=consultar),
            ]),
            filtro,
            lista_avisos,
        ]),
        card([
            ft.Text('Seguridad y privacidad', size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text('Las contraseñas y los roles se administran en Usuarios y roles. Para recuperar el acceso, contacta al administrador.', size=12, color=GRIS),
            ft.Text('Estas preferencias se guardan únicamente en este equipo; no envían correos ni notificaciones del sistema operativo.', size=11, color=GRIS),
        ]),
    ], spacing=13, expand=True, scroll=ft.ScrollMode.AUTO)

    page.clean()
    page.navigation_bar = None
    configurar_navbar(page, menu, indice_inicial=0)
    page.add(ft.Column([
        crear_header('Configuración'),
        ft.Stack([
            ft.Container(content=cuerpo, padding=16, expand=True),
            ft.Container(content=menu, right=12, bottom=12),
        ], expand=True),
    ], spacing=0, expand=True))
    consultar()
