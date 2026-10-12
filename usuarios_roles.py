import flet as ft
import estilos

from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from revision_backend import (
    actualizar_usuario_admin,
    crear_usuario_con_rol,
    listar_roles,
    listar_usuarios_roles,
)


TEXTO = "#25252B"
SECUNDARIO = "#5F6670"
BORDE = "#DFE3EB"
BLANCO = "#FFFFFF"
NARANJA = estilos.COLOR_PRINCIPAL


def vista_usuarios_roles(page: ft.Page):
    rol_actual = page.session.store.get("usuario_rol") or ""
    id_admin = page.session.store.get("usuario_id")

    if rol_actual != "Administrador" or not id_admin:
        page.go("/dashboard")
        return

    page.title = "QualityCheck - Usuarios y roles"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)

    menu_mas = crear_menu_mas(page)
    cuerpo = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)

    def aviso(mensaje):
        sb = ft.SnackBar(
            content=ft.Text(str(mensaje), color="#FFFFFF"),
            bgcolor=TEXTO,
        )
        page.overlay.append(sb)
        sb.open = True
        page.update()

    def campo(control):
        control.bgcolor = BLANCO
        control.border_color = "#A3A8B1"
        control.focused_border_color = NARANJA
        control.color = TEXTO
        if hasattr(control, "label_style"):
            control.label_style = ft.TextStyle(color=SECUNDARIO, size=12)
        if hasattr(control, "hint_style"):
            control.hint_style = ft.TextStyle(color=SECUNDARIO, size=12)
        return control

    def cerrar_dialogo(dialogo):
        dialogo.open = False
        page.update()

    def abrir_editar(usuario, roles):
        if int(usuario["id"]) == int(id_admin):
            aviso("Tu propia cuenta no se puede editar desde esta sección.")
            return

        nombre = campo(ft.TextField(label="Nombre *", value=usuario["nombre"]))
        correo = campo(ft.TextField(label="Correo *", value=usuario["correo"]))
        nombre_usuario = campo(ft.TextField(label="Usuario de acceso *", value=usuario.get("nombre_usuario") or ""))
        rol = campo(ft.Dropdown(
            label="Rol *",
            value=usuario.get("rol") or None,
            options=[ft.DropdownOption(key=r, text=r) for r in roles],
        ))
        activo = ft.Switch(
            label="Usuario activo",
            value=bool(usuario["activo"]),
            active_color=NARANJA,
        )
        nueva_password = campo(ft.TextField(
            label="Nueva contraseña (opcional)",
            password=True,
            can_reveal_password=True,
            hint_text="Déjala vacía para conservar la actual",
        ))

        dialogo = ft.AlertDialog(
            title=ft.Text(
                "Editar usuario",
                weight=ft.FontWeight.BOLD,
                color=TEXTO,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Puedes cambiar sus datos, estado y rol.",
                            size=12,
                            color=SECUNDARIO,
                        ),
                        nombre,
                        correo,
                        nombre_usuario,
                        rol,
                        activo,
                        nueva_password,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=390,
            ),
            bgcolor=BLANCO,
        )

        def guardar(_):
            try:
                actualizar_usuario_admin(
                    id_admin=id_admin,
                    id_usuario=usuario["id"],
                    nombre=nombre.value,
                    correo=correo.value,
                    nombre_usuario=nombre_usuario.value,
                    nombre_rol=rol.value,
                    activo=activo.value,
                    nueva_contrasena=nueva_password.value,
                )
                cerrar_dialogo(dialogo)
                aviso("Usuario actualizado.")
                cargar()
            except Exception as exc:
                aviso("No se pudo actualizar: " + str(exc))

        dialogo.actions = [
            ft.TextButton(
                content=ft.Text("Cancelar", color=TEXTO),
                on_click=lambda e: cerrar_dialogo(dialogo),
            ),
            ft.Button(
                content=ft.Text(
                    "Guardar cambios",
                    color=TEXTO,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=NARANJA,
                on_click=guardar,
            ),
        ]

        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    def abrir_nuevo(e):
        nombre = campo(ft.TextField(label="Nombre *"))
        correo = campo(ft.TextField(label="Correo *"))
        password = campo(ft.TextField(
            label="Contraseña *",
            password=True,
            can_reveal_password=True,
        ))

        try:
            roles = listar_roles()
        except Exception as exc:
            aviso("No se pudieron cargar los roles: " + str(exc))
            return

        rol = campo(ft.Dropdown(
            label="Rol *",
            value="Técnico" if "Técnico" in roles else (roles[0] if roles else None),
            options=[ft.DropdownOption(key=r, text=r) for r in roles],
        ))

        dialogo = ft.AlertDialog(
            title=ft.Text(
                "Nuevo usuario",
                weight=ft.FontWeight.BOLD,
                color=TEXTO,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "El usuario de acceso se genera automáticamente con el primer nombre y apellido paterno.",
                            size=12,
                            color=SECUNDARIO,
                        ),
                        nombre,
                        correo,
                        password,
                        rol,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=390,
            ),
            bgcolor=BLANCO,
        )

        def guardar(_):
            try:
                crear_usuario_con_rol(
                    nombre.value,
                    correo.value,
                    password.value,
                    rol.value,
                )
                cerrar_dialogo(dialogo)
                aviso("Usuario creado.")
                cargar()
            except Exception as exc:
                aviso("No se pudo crear: " + str(exc))

        dialogo.actions = [
            ft.TextButton(
                content=ft.Text("Cancelar", color=TEXTO),
                on_click=lambda e: cerrar_dialogo(dialogo),
            ),
            ft.Button(
                content=ft.Text(
                    "Guardar",
                    color=TEXTO,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=NARANJA,
                on_click=guardar,
            ),
        ]

        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    def tarjeta_usuario(usuario, roles):
        es_mismo = int(usuario["id"]) == int(id_admin)

        estado = "Activo" if usuario["activo"] else "Inactivo"
        estado_bg = "#DCFCE7" if usuario["activo"] else "#FEE2E2"
        estado_fg = "#166534" if usuario["activo"] else "#991B1B"

        encabezado = ft.Row(
            [
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    usuario["nombre"],
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXTO,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "TU CUENTA",
                                        size=9,
                                        weight=ft.FontWeight.BOLD,
                                        color="#92400E",
                                    ),
                                    bgcolor="#FEF3C7",
                                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                    border_radius=12,
                                    visible=es_mismo,
                                ),
                            ],
                            spacing=7,
                        ),
                        ft.Text(
                            usuario["correo"],
                            size=11,
                            color=SECUNDARIO,
                        ),
                        ft.Text(
                            "Usuario: " + (usuario.get("nombre_usuario") or "Sin asignar"),
                            size=11,
                            color=SECUNDARIO,
                        ),
                    ],
                    spacing=3,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text(
                        estado,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=estado_fg,
                    ),
                    bgcolor=estado_bg,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                    border_radius=14,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        rol_actual_usuario = usuario.get("rol") or "Sin rol"

        if es_mismo:
            accion = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCK_OUTLINE, size=16, color=SECUNDARIO),
                        ft.Text(
                            f"Rol: {rol_actual_usuario} · No editable desde aquí",
                            size=11,
                            color=SECUNDARIO,
                        ),
                    ],
                    spacing=6,
                ),
                bgcolor="#F3F4F6",
                padding=10,
                border_radius=8,
            )
        else:
            accion = ft.Row(
                [
                    ft.Container(
                        content=ft.Text(
                            rol_actual_usuario,
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color="#374151",
                        ),
                        bgcolor="#F3F4F6",
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        border_radius=14,
                    ),
                    ft.Button(
                        content=ft.Text(
                            "EDITAR",
                            color=TEXTO,
                            weight=ft.FontWeight.BOLD,
                            size=11,
                        ),
                        bgcolor="#E5E7EB",
                        height=38,
                        on_click=lambda e, u=usuario: abrir_editar(u, roles),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )

        return ft.Container(
            content=ft.Column(
                [encabezado, accion],
                spacing=10,
            ),
            bgcolor=BLANCO,
            border=ft.Border.all(1, BORDE),
            border_radius=12,
            padding=12,
        )

    def cargar():
        cuerpo.controls.clear()
        cuerpo.controls.extend(
            [
                ft.Text(
                    "Usuarios y roles",
                    size=21,
                    weight=ft.FontWeight.BOLD,
                    color=TEXTO,
                ),
                ft.Text(
                    "Administra cuentas, permisos y estado de acceso.",
                    size=12,
                    color=SECUNDARIO,
                ),
                ft.Button(
                    content=ft.Text(
                        "＋ NUEVO USUARIO",
                        color=TEXTO,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=NARANJA,
                    height=44,
                    on_click=abrir_nuevo,
                ),
            ]
        )

        try:
            roles = listar_roles()
            usuarios = listar_usuarios_roles()

            for usuario in usuarios:
                cuerpo.controls.append(tarjeta_usuario(usuario, roles))

            if not usuarios:
                cuerpo.controls.append(
                    ft.Text(
                        "No hay usuarios registrados.",
                        size=12,
                        color=SECUNDARIO,
                    )
                )
        except Exception as exc:
            cuerpo.controls.append(
                ft.Text("Error: " + str(exc), color="#B91C1C")
            )

        page.update()

    configurar_navbar(page, menu_mas, indice_inicial=0)

    page.add(
        ft.Column(
            [
                crear_header(titulo="Usuarios y roles"),
                ft.Stack(
                    [
                        ft.Container(cuerpo, padding=16, expand=True),
                        ft.Container(menu_mas, right=12, bottom=12),
                    ],
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
    )

    cargar()
