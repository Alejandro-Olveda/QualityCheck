import flet as ft
import base64
from pathlib import Path
import estilos


def aplicar_tema(page):
    # Fuerza tema claro para que menús desplegables, diálogos y campos
    # no hereden texto claro del tema del sistema operativo.
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=estilos.COLOR_PRINCIPAL,
            on_primary="#25252B",
            surface="#FFFFFF",
            on_surface="#25252B",
            on_surface_variant="#5F6670",
        ),
        navigation_bar_theme=ft.NavigationBarTheme(
            label_text_style={
                ft.ControlState.DEFAULT: ft.TextStyle(color="#5F6670", size=11),
                ft.ControlState.SELECTED: ft.TextStyle(
                    color="#F5A000", size=11, weight=ft.FontWeight.BOLD
                ),
            },
            indicator_color="#FFD67A",
            bgcolor="#FFFFFF",
            height=72,
        ),
    )


def _logo_base64():
    """Carga la imagen de assets dentro de Flet sin depender de la ruta web."""
    ruta = Path(__file__).resolve().parent / "assets" / "logo.png"
    try:
        return base64.b64encode(ruta.read_bytes()).decode("ascii")
    except OSError:
        return None


def crear_header(titulo=None):
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Image(src=_logo_base64(), width=44, height=44, fit=ft.BoxFit.CONTAIN),
                    width=44,
                    height=44,
                    bgcolor="#FFFFFF",
                    border_radius=22,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text(titulo or "QualityCheck", color="#25252B", weight=ft.FontWeight.BOLD, size=20),
                        ft.Text("SISTEMA DE INSPECCIÓN INDUSTRIAL", color="#25252B", size=9),
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=10,
        ),
        bgcolor=estilos.COLOR_PRINCIPAL,
        padding=15,
    )


def crear_menu_mas(page=None):
    rol = page.session.store.get("usuario_rol") if page else None

    def cerrar_sesion(e):
        for clave in ("usuario_id", "usuario_nombre", "usuario_rol"):
            page.session.store.remove(clave)
        page.go("/")

    def abrir_seccion(ruta):
        def navegar(e):
            menu.visible = False
            page.go(ruta)
        return navegar

    controles = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.HISTORY_OUTLINED, color="#4B5563"),
            title=ft.Text("Bitácora de mantenimiento", color="#374151"),
            on_click=abrir_seccion("/bitacora") if page else None,
        )
    ]

    controles.append(
        ft.ListTile(
            leading=ft.Icon(ft.Icons.HISTORY, color="#4B5563"),
            title=ft.Text("Historial de revisiones", color="#374151"),
            on_click=abrir_seccion("/historial") if page else None,
        )
    )

    if rol == "Administrador":
        controles.append(
            ft.ListTile(
                leading=ft.Icon(ft.Icons.MANAGE_ACCOUNTS_OUTLINED, color="#4B5563"),
                title=ft.Text("Usuarios y roles", color="#374151"),
                on_click=abrir_seccion("/usuarios") if page else None,
            )
        )

    controles.extend([
        ft.ListTile(
            leading=ft.Icon(ft.Icons.PERSON_OUTLINE, color="#4B5563"),
            title=ft.Text("Perfil", color="#374151"),
            on_click=abrir_seccion("/perfil") if page else None,
        ),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.SETTINGS_OUTLINED, color="#4B5563"),
            title=ft.Text("Configuración", color="#374151"),
            on_click=abrir_seccion("/configuracion") if page else None,
        ),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.LOGOUT, color="#B91C1C"),
            title=ft.Text("Cerrar sesión", color="#B91C1C"),
            on_click=cerrar_sesion if page else None,
        ),
    ])

    menu = ft.Container(
        content=ft.Column(controles, tight=True),
        width=230,
        bgcolor="#FFFFFF",
        padding=10,
        border_radius=15,
        visible=False,
    )
    return menu


def crear_destinos_navbar(pequeno=False):
    destinos = [
        ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icon(ft.Icons.HOME, color=estilos.COLOR_TEXTO), label="Inicio"),
        ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icon(ft.Icons.SETTINGS, color=estilos.COLOR_TEXTO), label="Máquinas"),
        ft.NavigationBarDestination(icon=ft.Icons.ASSIGNMENT_OUTLINED, selected_icon=ft.Icon(ft.Icons.ASSIGNMENT, color=estilos.COLOR_TEXTO), label="Revisiones"),
    ]
    if not pequeno:
        destinos.append(
            ft.NavigationBarDestination(
                icon=ft.Icons.WARNING_AMBER_OUTLINED,
                selected_icon=ft.Icon(ft.Icons.WARNING_AMBER, color=estilos.COLOR_TEXTO),
                label="Hallazgos",
            )
        )
    destinos.append(
        ft.NavigationBarDestination(
            icon=ft.Icons.MENU,
            selected_icon=ft.Icon(ft.Icons.MENU, color=estilos.COLOR_TEXTO),
            label="Más",
        )
    )
    return destinos


def configurar_navbar(page, menu_mas, indice_inicial=0):
    navbar_pequeno = crear_destinos_navbar(pequeno=True)
    navbar_completo = crear_destinos_navbar(pequeno=False)
    indice_actual = indice_inicial
    rutas = {0: "/dashboard", 1: "/maquinas", 2: "/revisiones", 3: "/hallazgos"}

    def cambiar_seccion(e):
        nonlocal indice_actual
        indice = e.control.selected_index
        indice_mas = 3 if page.width < 350 else 4
        if indice == indice_mas:
            menu_mas.visible = not menu_mas.visible
            barra.selected_index = indice_actual
            if page.floating_action_button:
                page.floating_action_button.visible = not menu_mas.visible
            page.update()
            return
        menu_mas.visible = False
        indice_actual = indice
        if page.floating_action_button:
            page.floating_action_button.visible = True
        ruta = rutas.get(indice)
        if ruta and ruta != page.route:
            page.go(ruta)
        else:
            page.update()

    def ajustar_tamano(e=None):
        nonlocal indice_actual
        if page.width < 350:
            barra.destinations = navbar_pequeno
            if indice_actual == 3:
                indice_actual = 2
            barra.selected_index = indice_actual
        else:
            barra.destinations = navbar_completo
            barra.selected_index = indice_actual
        menu_mas.visible = False
        if page.floating_action_button:
            page.floating_action_button.visible = True
        page.update()

    barra = ft.NavigationBar(
        destinations=navbar_completo,
        on_change=cambiar_seccion,
        selected_index=indice_inicial,
        bgcolor="#FFFFFF",
        indicator_color=estilos.COLOR_PRINCIPAL,
    )
    page.navigation_bar = barra
    page.on_resize = ajustar_tamano
    ajustar_tamano()
    return barra
