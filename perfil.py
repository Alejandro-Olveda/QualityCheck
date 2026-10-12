import flet as ft

import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal
from models import Usuario

TEXTO = '#25252B'
GRIS = '#626A75'
BORDE = '#E1E3E6'


def vista_perfil(page: ft.Page):
    uid = page.session.store.get('usuario_id')
    if not uid:
        page.go('/')
        return

    page.title = 'QualityCheck - Mi perfil'
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)
    menu = crear_menu_mas(page)

    cuerpo = ft.Column(
        spacing=13,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    def tarjeta(controles):
        return ft.Container(
            content=ft.Column(
                controles,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            bgcolor='#FFFFFF',
            border=ft.Border.all(1, BORDE),
            border_radius=12,
            padding=16,
        )

    def dato(icono, etiqueta, valor):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icono, size=19, color='#6B7280'),
                ft.Column([
                    ft.Text(etiqueta, size=11, color=GRIS),
                    ft.Text(
                        str(valor) if valor is not None and str(valor).strip() else 'No registrado',
                        size=14,
                        color=TEXTO,
                        selectable=True,
                    ),
                ], spacing=4, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor='#F8FAFC',
            border=ft.Border.all(1, '#E5E7EB'),
            border_radius=10,
            padding=12,
        )

    def mostrar():
        cuerpo.controls.clear()
        try:
            with SessionLocal() as db:
                usuario = db.get(Usuario, uid)
                if not usuario or not usuario.activo:
                    page.session.store.remove('usuario_id')
                    page.go('/')
                    return
                datos = {
                    'nombre': usuario.nombre,
                    'correo': usuario.correo,
                    'nombre_usuario': getattr(usuario, 'nombre_usuario', None),
                    'fecha_creacion': usuario.fecha_creacion,
                }
        except Exception as exc:
            cuerpo.controls.append(
                ft.Text('No se pudo consultar el perfil: ' + str(exc), color='#B91C1C')
            )
            page.update()
            return

        fecha = datos['fecha_creacion']
        fecha_texto = fecha.strftime('%d/%m/%Y') if fecha else 'Sin fecha'
        rol = page.session.store.get('usuario_rol') or 'Sin rol'

        cuerpo.controls.extend([
            ft.Text('Mi perfil', size=21, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text('Información de tu cuenta (solo lectura).', size=12, color=GRIS),
            tarjeta([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.PERSON_OUTLINE, color=TEXTO, size=29),
                        bgcolor='#FEF3C7',
                        border_radius=40,
                        width=60,
                        height=60,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column([
                        ft.Text(datos['nombre'], size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
                        ft.Text(rol, size=12, color=GRIS),
                        ft.Text('Cuenta creada: ' + fecha_texto, size=11, color=GRIS),
                    ], spacing=4, expand=True),
                ], spacing=12),
            ]),
            tarjeta([
                ft.Text('Datos personales', size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
                dato(ft.Icons.PERSON_OUTLINE, 'Nombre completo', datos['nombre']),
                dato(ft.Icons.EMAIL_OUTLINED, 'Correo electrónico', datos['correo']),
            ]),
            tarjeta([
                ft.Text('Acceso y permisos', size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
                dato(ft.Icons.BADGE_OUTLINED, 'Usuario de acceso', datos['nombre_usuario']),
                dato(ft.Icons.LOCK_OUTLINE, 'Rol', rol),
                ft.Text(
                    'Para modificar los datos de la cuenta, el usuario de acceso, '
                    'el rol o la contraseña, contacta a un administrador.',
                    size=12,
                    color=GRIS,
                ),
            ]),
        ])
        page.update()

    page.clean()
    page.navigation_bar = None
    configurar_navbar(page, menu, indice_inicial=0)
    page.add(ft.Column([
        crear_header('Mi perfil'),
        ft.Stack([
            ft.Container(content=cuerpo, padding=16, expand=True),
            ft.Container(content=menu, right=12, bottom=12),
        ], expand=True),
    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, expand=True))
    mostrar()
