import flet as ft

from componentes import crear_header
from agregar_maquina import vista_agregar_maquina
from dashboard import vista_dashboard
from detalle_maquina import vista_detalle_maquina
from listado import vista_listado
from editar_maquina import vista_editar_maquina
from revisiones import vista_revisiones
from hallazgos import vista_hallazgos
from usuarios_roles import vista_usuarios_roles
from bitacora import vista_bitacora
from alertas import vista_alertas
from historial import vista_historial
from configuracion import vista_configuracion
from perfil import vista_perfil
from database import SessionLocal
from models import Usuario
from revision_backend import obtener_rol_usuario
from recordar_usuario import leer_usuario_recordado, guardar_usuario_recordado, borrar_usuario_recordado
from sqlalchemy import func


def main(page: ft.Page):
    page.title = "QualityCheck - Login"
    page.padding = 0
    page.bgcolor = "#F5F6F8"
    page.window.width = 380
    page.window.height = 700
    page.window.resizable = False

    def mostrar_error_pantalla(seccion, error):
        page.clean()
        page.add(ft.Column([
            crear_header(seccion),
            ft.Container(content=ft.Column([
                ft.Text("No se pudo abrir " + seccion, size=18, weight=ft.FontWeight.BOLD, color="#25252B"),
                ft.Text(str(error), size=12, color="#B91C1C", selectable=True),
                ft.Button("Volver al inicio", on_click=lambda e: page.go("/dashboard")),
            ], spacing=15), padding=20),
        ], expand=True))
        page.update()

    def cambiar_ruta(e):
        page.clean()
        page.navigation_bar = None

        if page.route in ("", "/"):
            page.title = "QualityCheck - Login"
            page.add(vista_login)
        elif not page.session.store.get("usuario_id"):
            page.go("/")
        elif page.route == "/dashboard":
            vista_dashboard(page)
        elif page.route == "/maquinas":
            vista_listado(page)
        elif page.route in ("/maquinas/agregar", "/agregar_maquina"):
            if page.session.store.get("usuario_rol") == "Técnico":
                page.go("/maquinas")
            else:
                vista_agregar_maquina(page)
        elif page.route.startswith("/maquinas/") and page.route.endswith("/editar"):
            if page.session.store.get("usuario_rol") == "Técnico":
                page.go("/maquinas")
            else:
                codigo_maquina = page.route.split("/")[-2]
                vista_editar_maquina(page, codigo_maquina)
        elif page.route.startswith("/maquinas/editar/"):
            if page.session.store.get("usuario_rol") == "Técnico":
                page.go("/maquinas")
            else:
                codigo_maquina = page.route.rsplit("/", 1)[-1]
                vista_editar_maquina(page, codigo_maquina)
        elif page.route.startswith("/editar_maquina"):
            if page.session.store.get("usuario_rol") == "Técnico":
                page.go("/maquinas")
            else:
                codigo_maquina = page.route.rsplit("/", 1)[-1]
                vista_editar_maquina(page, codigo_maquina)
        elif page.route == "/revisiones" or page.route.startswith("/revisiones/"):
            vista_revisiones(page)
        elif page.route == "/hallazgos":
            vista_hallazgos(page)
        elif page.route == "/usuarios":
            vista_usuarios_roles(page)
        elif page.route == "/bitacora":
            vista_bitacora(page)
        elif page.route in ("/alertas", "/configuracion"):
            try:
                vista_configuracion(page)
            except Exception as exc:
                mostrar_error_pantalla("Configuración", exc)
        elif page.route == "/perfil":
            try:
                vista_perfil(page)
            except Exception as exc:
                mostrar_error_pantalla("Mi perfil", exc)
        elif page.route == "/historial":
            vista_historial(page)
        elif page.route.startswith("/maquinas/"):
            codigo_maquina = page.route.rsplit("/", 1)[-1]
            vista_detalle_maquina(page, codigo_maquina)
        elif page.route.startswith("/detalle_maquina/"):
            codigo_maquina = page.route.rsplit("/", 1)[-1]
            vista_detalle_maquina(page, codigo_maquina)
        else:
            page.go("/dashboard")

    lbl_error = ft.Text("", color="#DC2626", size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    usuario_guardado = leer_usuario_recordado()

    def iniciar_sesion(e):
        identificador = (txt_usuario.value or "").strip()
        contrasena = txt_password.value or ""
        lbl_error.value = ""

        if not identificador or not contrasena:
            lbl_error.value = "Ingresa tu usuario y contraseña."
            page.update()
            return

        btn_entrar.disabled = True
        page.update()
        try:
            with SessionLocal() as db:
                usuario_valido = db.query(Usuario).filter(
                    Usuario.activo.is_(True),
                    (func.lower(Usuario.nombre_usuario) == identificador.lower())
                    | (func.lower(Usuario.correo) == identificador.lower()),
                    Usuario.contrasena_hash == contrasena,
                ).first()

                if not usuario_valido:
                    lbl_error.value = "Usuario o contraseña incorrectos."
                    page.update()
                    return

                usuario_id = usuario_valido.id_usuario
                nombre = usuario_valido.nombre
                rol = obtener_rol_usuario(usuario_id)

            if rol not in ("Administrador", "Inspector", "Técnico"):
                lbl_error.value = "Tu cuenta no tiene un rol asignado. Contacta al administrador."
                page.update()
                return

            page.session.store.set("usuario_id", usuario_id)
            page.session.store.set("usuario_nombre", nombre)
            page.session.store.set("usuario_rol", rol)

            try:
                if checkbox_recordar.value:
                    guardar_usuario_recordado(identificador)
                else:
                    borrar_usuario_recordado()
            except OSError:
                pass

            txt_password.value = ""
            page.go("/dashboard")
        except Exception:
            lbl_error.value = "No se pudo iniciar sesión. Revisa la conexión e inténtalo de nuevo."
            page.update()
        finally:
            btn_entrar.disabled = False
            page.update()

    def cerrar_recuperacion(e):
        dialogo_recuperacion.open = False
        page.update()

    def abrir_recuperacion(e):
        if dialogo_recuperacion not in page.overlay:
            page.overlay.append(dialogo_recuperacion)
        dialogo_recuperacion.open = True
        page.update()

    page.on_route_change = cambiar_ruta
    header = crear_header()

    txt_titulo = ft.Text("Inicia sesión", size=20, weight=ft.FontWeight.BOLD, color="#25252B", width=320)
    txt_usuario = ft.TextField(
        label="USUARIO O CORREO",
        hint_text="Ingresa usuario o correo electrónico",
        hint_style=ft.TextStyle(size=12, color="#6B7280"),
        border_color="#BDBDBD",
        focused_border_color="#F5A000",
        label_style=ft.TextStyle(size=11, color="#616161"),
        width=320,
        bgcolor="#FFFFFF",
        color="#25252B",
        value=usuario_guardado,
    )
    txt_password = ft.TextField(
        label="CONTRASEÑA",
        hint_text="Ingrese su contraseña",
        hint_style=ft.TextStyle(size=12, color="#6B7280"),
        password=True,
        can_reveal_password=True,
        border_color="#BDBDBD",
        focused_border_color="#F5A000",
        label_style=ft.TextStyle(size=11, color="#616161"),
        width=320,
        bgcolor="#FFFFFF",
        color="#25252B",
        on_submit=iniciar_sesion,
    )

    def cambiar_recordar(valor):
        if not valor:
            borrar_usuario_recordado()

    checkbox_recordar = ft.Checkbox(
        value=bool(usuario_guardado),
        active_color="#F5A000",
        on_change=lambda e: cambiar_recordar(e.control.value),
    )
    recordar_usuario = ft.Container(
        content=ft.Row([checkbox_recordar, ft.Text("Recordar usuario", size=12, color="#616161")], spacing=5),
        width=320,
    )
    dialogo_recuperacion = ft.AlertDialog(
        title=ft.Text("Recuperación de contraseña", color="#25252B", weight=ft.FontWeight.BOLD),
        content=ft.Text(
            "Si olvidaste tu contraseña, comunícate con un administrador de QualityCheck para que te asigne una nueva.",
            color="#616161",
            size=13,
        ),
        bgcolor="#FFFFFF",
        actions=[
            ft.TextButton(content=ft.Text("Entendido", color="#25252B", weight=ft.FontWeight.BOLD), on_click=cerrar_recuperacion),
        ],
    )
    recuperar_pass = ft.TextButton(
        content=ft.Text("¿Olvidaste tu contraseña?", color="#616161", size=12),
        on_click=abrir_recuperacion,
    )
    btn_entrar = ft.Button(
        content=ft.Text("INICIAR SESIÓN", color="#25252B", weight=ft.FontWeight.BOLD, size=13),
        bgcolor="#F5A000",
        width=320,
        height=48,
        on_click=iniciar_sesion,
    )
    pie_pagina = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.LOCK_OUTLINE, size=12, color="#919090"),
            ft.Text("Acceso según rol", size=11, color="#919090", italic=True),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=5, tight=True),
        bgcolor="#EBEEF2",
        padding=10,
        border_radius=20,
    )

    formulario = ft.Column([
        txt_titulo,
        ft.Container(height=14),
        txt_usuario,
        ft.Container(height=10),
        txt_password,
        ft.Container(height=4),
        lbl_error,
        recordar_usuario,
        ft.Container(height=2),
        recuperar_pass,
        ft.Container(height=10),
        btn_entrar,
        ft.Container(height=30),
        pie_pagina,
    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    cuerpo = ft.Container(content=formulario, padding=20, alignment=ft.Alignment.TOP_CENTER, expand=True)
    vista_login = ft.Column([header, cuerpo], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, expand=True)

    if page.route in ("", "/"):
        page.add(vista_login)
    else:
        cambiar_ruta(None)


# Mantenemos ejecución local original; Render utiliza servidor_pdf.py
if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
