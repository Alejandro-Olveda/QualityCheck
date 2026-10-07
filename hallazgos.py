from datetime import datetime, timedelta

import flet as ft
import estilos

from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from revision_backend import (
    asignar_hallazgo,
    listar_hallazgos_y_acciones,
    listar_tecnicos,
    registrar_trabajo_tecnico,
    verificar_trabajo,
)


def vista_hallazgos(page: ft.Page):
    usuario_id = page.session.store.get("usuario_id")
    rol = page.session.store.get("usuario_rol") or "Sin rol"
    if not usuario_id:
        page.go("/")
        return

    page.title = "QualityCheck - Hallazgos"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None
    aplicar_tema(page)
    menu_mas = crear_menu_mas(page)
    cuerpo = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=10)

    def aviso(mensaje):
        sb = ft.SnackBar(content=ft.Text(str(mensaje), color="#FFFFFF"), bgcolor="#25252B")
        page.overlay.append(sb)
        sb.open = True
        page.update()

    def etiqueta(estado):
        mapa = {
            "Abierto": ("#FEF3C7", "#B45309"),
            "En proceso": ("#DBEAFE", "#1D4ED8"),
            "Asignada": ("#DBEAFE", "#1D4ED8"),
            "Pendiente de verificación": ("#FEF3C7", "#B45309"),
            "Cerrado": ("#DCFCE7", "#15803D"),
            "Verificada": ("#DCFCE7", "#15803D"),
        }
        bg, fg = mapa.get(estado, ("#F3F4F6", "#6B7280"))
        return ft.Container(
            ft.Text(estado or "Sin estado", size=10, weight=ft.FontWeight.BOLD, color=fg),
            bgcolor=bg,
            padding=6,
            border_radius=14,
        )

    def boton(titulo, fn, primario=False):
        return ft.Button(
            content=ft.Text(titulo, color=estilos.COLOR_TEXTO, weight=ft.FontWeight.BOLD, size=12),
            bgcolor=estilos.COLOR_PRINCIPAL if primario else "#FFFFFF",
            style=None if primario else ft.ButtonStyle(side=ft.BorderSide(1, "#E1E3E6")),
            on_click=fn,
        )

    def actualizar(e=None):
        cuerpo.controls.clear()
        subtitulo = {
            "Técnico": "Trabajos correctivos que te fueron asignados.",
            "Inspector": "Asigna técnicos y verifica los trabajos terminados.",
            "Administrador": "Supervisa y administra los hallazgos del sistema.",
        }.get(rol, "Consulta de hallazgos.")
        cuerpo.controls.extend([
            ft.Text("Hallazgos y correctivas", size=21, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
            ft.Text(subtitulo, size=12, color=estilos.COLOR_TEXTO_SECUNDARIO),
        ])
        try:
            filas = listar_hallazgos_y_acciones(usuario_id, rol)
            if not filas:
                cuerpo.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.TASK_ALT, size=42, color="#9CA3AF"),
                        ft.Text("No hay trabajos pendientes", weight=ft.FontWeight.BOLD),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor="#FFFFFF",
                    border=ft.Border.all(1, "#E1E3E6"),
                    border_radius=12,
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                ))
            for x in filas:
                acciones = []
                if rol in ("Inspector", "Administrador"):
                    if not x.get("id_accion") or x.get("estado_accion") in (None, "Requiere ajuste"):
                        acciones.append(boton("Asignar técnico", lambda e, h=x: dialogo_asignar(h), True))
                    elif x.get("estado_accion") == "Pendiente de verificación":
                        acciones.append(boton("Verificar", lambda e, a=x: dialogo_verificar(a), True))
                elif rol == "Técnico" and x.get("estado_accion") in ("Asignada", "En proceso", "Requiere ajuste"):
                    acciones.append(boton("Registrar trabajo", lambda e, a=x: dialogo_trabajo(a), True))

                cuerpo.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Column([
                                ft.Text(f"{x['codigo_maquina']} · {x['maquina']}", size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(x["codigo_revision"], size=11, color=estilos.COLOR_TEXTO_SECUNDARIO),
                            ], spacing=2, expand=True),
                            etiqueta(x.get("estado_accion") or x.get("estado_hallazgo")),
                        ]),
                        ft.Text(x["descripcion_hallazgo"], size=12),
                        ft.Text("Severidad: " + x["severidad"], size=11, color=estilos.COLOR_TEXTO_SECUNDARIO),
                        *([ft.Text("Técnico: " + x["tecnico"], size=11, color=estilos.COLOR_TEXTO_SECUNDARIO)] if x.get("tecnico") else []),
                        *([ft.Text("Trabajo: " + x["descripcion_accion"], size=11, color=estilos.COLOR_TEXTO_SECUNDARIO)] if x.get("descripcion_accion") else []),
                        *([ft.Row(acciones, spacing=8, wrap=True)] if acciones else []),
                    ], spacing=7),
                    bgcolor="#FFFFFF",
                    border=ft.Border.all(1, "#E1E3E6"),
                    border_radius=12,
                    padding=12,
                ))
        except Exception as exc:
            cuerpo.controls.append(ft.Text("Error: " + str(exc), color="#B91C1C"))
        page.update()

    def dialogo_asignar(h):
        tecnicos = listar_tecnicos()
        if not tecnicos:
            aviso("No hay usuarios con rol Técnico.")
            return
        tecnico = ft.Dropdown(
            label="Técnico *",
            options=[ft.DropdownOption(key=str(t["id"]), text=t["nombre"]) for t in tecnicos],
            value=str(tecnicos[0]["id"]),
            bgcolor="#FFFFFF",
            color=estilos.COLOR_TEXTO,
            border_color="#A3A8B1",
            focused_border_color=estilos.COLOR_PRINCIPAL,
        )
        descripcion = ft.TextField(
            label="Trabajo a realizar *",
            multiline=True,
            min_lines=2,
            bgcolor="#FFFFFF",
            color=estilos.COLOR_TEXTO,
            border_color="#A3A8B1",
            focused_border_color=estilos.COLOR_PRINCIPAL,
        )
        fecha_inicial = datetime.now().date() + timedelta(days=2)

        fecha = ft.TextField(
            label="Fecha compromiso *",
            value=fecha_inicial.strftime("%d/%m/%Y"),
            read_only=True,
            bgcolor="#FFFFFF",
            color=estilos.COLOR_TEXTO,
            border_color="#A3A8B1",
            focused_border_color=estilos.COLOR_PRINCIPAL,
            expand=True,
        )

        calendario = ft.DatePicker(
            value=datetime.combine(fecha_inicial, datetime.min.time()),
            first_date=datetime.now(),
            last_date=datetime.now() + timedelta(days=365 * 5),
        )

        fecha_seleccionada = {"valor": fecha_inicial}

        def seleccionar_fecha(e):
            if calendario.value:
                valor = calendario.value
                if hasattr(valor, "date"):
                    valor = valor.date()
                fecha_seleccionada["valor"] = valor
                fecha.value = valor.strftime("%d/%m/%Y")
                page.update()

        calendario.on_change = seleccionar_fecha

        def abrir_calendario(e):
            page.show_dialog(calendario)

        selector_fecha = ft.Row(
            [
                fecha,
                ft.IconButton(
                    icon=ft.Icons.CALENDAR_MONTH_OUTLINED,
                    icon_color=estilos.COLOR_PRINCIPAL,
                    tooltip="Seleccionar fecha",
                    on_click=abrir_calendario,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        d = ft.AlertDialog(
            title=ft.Text(
                "Asignar correctiva",
                color=estilos.COLOR_TEXTO,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                [tecnico, descripcion, selector_fecha],
                tight=True,
                spacing=10,
            ),
            bgcolor="#FFFFFF",
        )

        def cerrar(_):
            d.open = False
            page.update()

        def guardar(_):
            try:
                fecha_compromiso = datetime.combine(
                    fecha_seleccionada["valor"],
                    datetime.min.time(),
                )
                asignar_hallazgo(
                    h["id_hallazgo"],
                    int(tecnico.value),
                    int(usuario_id),
                    descripcion.value,
                    fecha_compromiso,
                )
                cerrar(None)
                aviso("Trabajo asignado.")
                actualizar()
            except Exception as exc:
                aviso("No se pudo asignar: " + str(exc))

        d.actions = [
            ft.TextButton(
                content=ft.Text("Cancelar", color=estilos.COLOR_TEXTO),
                on_click=cerrar,
            ),
            boton("Asignar", guardar, True),
        ]
        page.overlay.append(d)
        d.open = True
        page.update()

    def dialogo_trabajo(a):
        observaciones = ft.TextField(
            label="¿Qué trabajo realizaste? *",
            multiline=True,
            min_lines=3,
            max_lines=5,
            bgcolor="#FFFFFF",
            color=estilos.COLOR_TEXTO,
            border_color="#A3A8B1",
            focused_border_color=estilos.COLOR_PRINCIPAL,
            label_style=ft.TextStyle(size=12, color="#5F6670"),
            hint_style=ft.TextStyle(size=12, color="#5F6670"),
        )

        d = ft.AlertDialog(
            title=ft.Text(
                "Registrar trabajo",
                color=estilos.COLOR_TEXTO,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Describe claramente la corrección realizada.",
                            size=12,
                            color="#5F6670",
                        ),
                        observaciones,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=330,
            ),
            bgcolor="#FFFFFF",
        )

        def cerrar(_):
            d.open = False
            page.update()

        def guardar(_):
            try:
                registrar_trabajo_tecnico(
                    a["id_accion"],
                    int(usuario_id),
                    observaciones.value,
                )
                cerrar(None)
                aviso("Trabajo enviado al inspector para verificación.")
                actualizar()
            except Exception as exc:
                aviso("No se pudo registrar: " + str(exc))

        d.actions = [
            ft.TextButton(
                content=ft.Text(
                    "Cancelar",
                    color=estilos.COLOR_TEXTO,
                ),
                on_click=cerrar,
            ),
            ft.Button(
                content=ft.Text(
                    "Enviar a verificación",
                    color=estilos.COLOR_TEXTO,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=estilos.COLOR_PRINCIPAL,
                on_click=guardar,
            ),
        ]

        page.overlay.append(d)
        d.open = True
        page.update()

    def dialogo_verificar(a):
        observaciones = ft.TextField(
            label="Observaciones de verificación",
            hint_text="Ej. Corrección realizada correctamente",
            multiline=True,
            min_lines=3,
            max_lines=5,
            bgcolor="#FFFFFF",
            color=estilos.COLOR_TEXTO,
            border_color="#A3A8B1",
            focused_border_color=estilos.COLOR_PRINCIPAL,
            label_style=ft.TextStyle(size=12, color="#5F6670"),
            hint_style=ft.TextStyle(size=12, color="#5F6670"),
        )

        d = ft.AlertDialog(
            title=ft.Text(
                "Verificar trabajo",
                color=estilos.COLOR_TEXTO,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Revisa el trabajo del técnico antes de aprobarlo o devolverlo.",
                            size=12,
                            color="#5F6670",
                        ),
                        observaciones,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=330,
            ),
            bgcolor="#FFFFFF",
        )

        def cerrar(_):
            d.open = False
            page.update()

        def resolver(aprobado):
            try:
                verificar_trabajo(
                    a["id_accion"],
                    int(usuario_id),
                    aprobado,
                    observaciones.value,
                )
                cerrar(None)
                aviso(
                    "Trabajo aprobado y hallazgo cerrado."
                    if aprobado
                    else "Trabajo devuelto al técnico."
                )
                actualizar()
            except Exception as exc:
                aviso("No se pudo verificar: " + str(exc))

        d.actions = [
            ft.TextButton(
                content=ft.Text(
                    "Cancelar",
                    color=estilos.COLOR_TEXTO,
                ),
                on_click=cerrar,
            ),
            ft.Button(
                content=ft.Text(
                    "Devolver",
                    color="#991B1B",
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor="#FEE2E2",
                on_click=lambda e: resolver(False),
            ),
            ft.Button(
                content=ft.Text(
                    "Aprobar",
                    color=estilos.COLOR_TEXTO,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=estilos.COLOR_PRINCIPAL,
                on_click=lambda e: resolver(True),
            ),
        ]

        page.overlay.append(d)
        d.open = True
        page.update()

    configurar_navbar(page, menu_mas, indice_inicial=3)
    page.add(ft.Column([
        crear_header(titulo="Hallazgos"),
        ft.Stack([
            ft.Container(cuerpo, padding=16, expand=True),
            ft.Container(menu_mas, right=12, bottom=12),
        ], expand=True),
    ], spacing=0, expand=True))
    actualizar()
