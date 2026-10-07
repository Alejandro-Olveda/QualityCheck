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
from database import SessionLocal
from services import validar_login
from models import Usuario
from revision_backend import obtener_rol_usuario


def main(page: ft.Page):
    page.title = "QualityCheck - Login"
    page.padding = 0
    page.bgcolor = "#F5F6F8"
    page.window.width = 380
    page.window.height = 700
    page.window.resizable = False

    def mostrar_snackbar(mensaje):
        snackbar = ft.SnackBar(content=ft.Text(mensaje, color="#FFFFFF"), bgcolor="#25252B")
        page.overlay.append(snackbar)
        snackbar.open = True
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
        elif page.route.startswith("/maquinas/"):
            codigo_maquina = page.route.rsplit("/", 1)[-1]
            vista_detalle_maquina(page, codigo_maquina)
        elif page.route.startswith("/detalle_maquina/"):
            codigo_maquina = page.route.rsplit("/", 1)[-1]
            vista_detalle_maquina(page, codigo_maquina)
        else:
            page.go("/dashboard")

    lbl_error = ft.Text("", color="#DC2626", size=12, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)

    def iniciar_sesion(e):
        identificador = (txt_usuario.value or "").strip()
        contrasena = txt_password.value or ""
        usuario_valido = None

        with SessionLocal() as db:
            usuario_valido = validar_login(db, identificador, contrasena)

            if not usuario_valido and "@" not in identificador and identificador:
                candidatos = db.query(Usuario).filter(
                    Usuario.correo.ilike(f"{identificador}@%"),
                    Usuario.activo.is_(True),
                ).all()
                if len(candidatos) == 1 and candidatos[0].contrasena_hash == contrasena:
                    usuario_valido = candidatos[0]

            if usuario_valido:
                page.session.store.set("usuario_id", usuario_valido.id_usuario)
                page.session.store.set("usuario_nombre", usuario_valido.nombre)
                page.session.store.set("usuario_rol", obtener_rol_usuario(usuario_valido.id_usuario))

        if usuario_valido:
            lbl_error.value = ""
            page.go("/dashboard")
        else:
            lbl_error.value = "Usuario o contraseña incorrectos"
            page.update()

    def cerrar_recuperacion(e):
        dialogo_recuperacion.open = False
        page.update()

    def enviar_recuperacion(e):
        if correo_recuperacion.value:
            dialogo_recuperacion.open = False
            page.update()
            mostrar_snackbar("Se enviaron instrucciones de recuperación.")
        else:
            mostrar_snackbar("Ingrese un correo electrónico.")

    def abrir_recuperacion(e):
        if dialogo_recuperacion not in page.overlay:
            page.overlay.append(dialogo_recuperacion)
        dialogo_recuperacion.open = True
        page.update()

    page.on_route_change = cambiar_ruta
    header = crear_header()

    txt_titulo = ft.Text("Inicia sesión", size=20, weight=ft.FontWeight.BOLD, color="#25252B", width=320)
    txt_usuario = ft.TextField(
        label="USUARIO/CORREO",
        hint_text="Ingrese su usuario o correo electrónico",
        hint_style=ft.TextStyle(size=12, color="#6B7280"),
        border_color="#BDBDBD",
        focused_border_color="#F5A000",
        label_style=ft.TextStyle(size=11, color="#616161"),
        width=320,
        bgcolor="#FFFFFF",
        color="#25252B",
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
    )

    checkbox_recordar = ft.Checkbox(value=False, active_color="#F5A000")
    recordar_usuario = ft.Container(
        content=ft.Row([checkbox_recordar, ft.Text("Recordar usuario", size=12, color="#616161")], spacing=5),
        width=320,
    )
    correo_recuperacion = ft.TextField(
        label="Correo electrónico",
        hint_text="Ingrese su correo electrónico",
        border_color="#BDBDBD",
        focused_border_color="#F5A000",
        bgcolor="#FFFFFF",
        color="#25252B",
    )
    dialogo_recuperacion = ft.AlertDialog(
        title=ft.Text("Recuperación de contraseña", color="#25252B", weight=ft.FontWeight.BOLD),
        content=ft.Column([
            ft.Text("Ingrese su correo electrónico para recibir instrucciones de recuperación.", color="#616161", size=12),
            ft.Container(height=10),
            correo_recuperacion,
        ], tight=True),
        bgcolor="#F5F6F8",
        actions=[
            ft.TextButton(content=ft.Text("Cancelar", color="#25252B"), on_click=cerrar_recuperacion),
            ft.TextButton(content=ft.Text("Enviar", color="#25252B", weight=ft.FontWeight.BOLD), on_click=enviar_recuperacion),
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
            ft.Text("Acceso seguro según rol", size=11, color="#919090", italic=True),
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


ft.run(main, assets_dir="assets")
