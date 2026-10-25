import flet as ft
import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar

TEXTO = '#25252B'
GRIS = '#626A75'
BORDE = '#E1E3E6'


def vista_configuracion(page: ft.Page):
    uid = page.session.store.get('usuario_id')
    if not uid:
        page.go('/')
        return

    page.title = 'QualityCheck - Configuración'
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)
    menu = crear_menu_mas(page)
    def card(contenido):
        return ft.Container(
            content=ft.Column(contenido, spacing=10), bgcolor='#FFFFFF',
            border=ft.Border.all(1, BORDE), border_radius=12, padding=15,
        )

    cuerpo = ft.Column([
        ft.Text('Configuración', size=21, weight=ft.FontWeight.BOLD, color=TEXTO),
        ft.Text('Administra tu cuenta y seguridad.', size=12, color=GRIS),
        card([
            ft.Row([ft.Icon(ft.Icons.PERSON_OUTLINE, color=TEXTO),
                    ft.Text('Mi cuenta', size=16, weight=ft.FontWeight.BOLD, color=TEXTO)], spacing=8),
            ft.Text('Consulta los datos de tu cuenta. Solo un administrador puede modificarlos.', size=12, color=GRIS),
            ft.Button('ABRIR PERFIL', icon=ft.Icons.ARROW_FORWARD, bgcolor=estilos.COLOR_PRINCIPAL,
                      color=TEXTO, on_click=lambda e: page.go('/perfil')),
        ]),
        card([
            ft.Text('Seguridad y privacidad', size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text('Las contraseñas y los roles se administran en Usuarios y roles. Para recuperar el acceso, contacta al administrador.', size=12, color=GRIS),
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
