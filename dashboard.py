from datetime import date

import flet as ft
import estilos

from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal
from services import obtener_resumen_dashboard
from revision_backend import (
    listar_programadas,
    listar_hallazgos_y_acciones,
    listar_usuarios_roles,
    obtener_revisiones,
)

TEXTO = "#25252B"
SECUNDARIO = "#5F6670"
BORDE = "#E1E3E6"
BLANCO = "#FFFFFF"
VERDE = "#15803D"
NARANJA_OSCURO = "#B45309"
ROJO = "#B91C1C"


def vista_dashboard(page: ft.Page):
    page.title = "QualityCheck - Dashboard"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None

    usuario_id = page.session.store.get("usuario_id")
    usuario_nombre = (page.session.store.get("usuario_nombre") or "Usuario").strip()
    rol = page.session.store.get("usuario_rol") or "Sin rol"

    if not usuario_id:
        page.go("/")
        return

    primer_nombre = usuario_nombre.split()[0] if usuario_nombre else "Usuario"

    aplicar_tema(page)
    menu_mas = crear_menu_mas(page)

    def bloque_resumen(titulo, cantidad, color, icono):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icono, color=color, size=22),
                    ft.Text(
                        str(cantidad),
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=TEXTO,
                    ),
                    ft.Text(
                        titulo,
                        size=10,
                        color=SECUNDARIO,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=5,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=BLANCO,
            border=ft.Border.all(1, BORDE),
            border_radius=12,
            padding=9,
            height=98,
            expand=True,
        )

    def boton_accion(titulo, icono, ruta, primario=False):
        return ft.Button(
            content=ft.Row(
                [
                    ft.Icon(icono, size=18, color=TEXTO),
                    ft.Text(
                        titulo,
                        color=TEXTO,
                        weight=ft.FontWeight.BOLD,
                        size=11,
                    ),
                ],
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=estilos.COLOR_PRINCIPAL if primario else BLANCO,
            style=None if primario else ft.ButtonStyle(
                side=ft.BorderSide(1, BORDE)
            ),
            height=42,
            expand=True,
            on_click=lambda e: page.go(ruta),
        )

    def tarjeta_programada(p):
        color_estado = ROJO if p["estado"] == "Vencida" else NARANJA_OSCURO
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                f"{p['codigo_maquina']} · {p['maquina']}",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                            ),
                            ft.Text(
                                p["descripcion"],
                                size=11,
                                color=SECUNDARIO,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                "Inspector: " + str(p.get("responsable") or "Sin asignar"),
                                size=10,
                                color=SECUNDARIO,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                p["fecha"].strftime("%d/%m/%Y"),
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=color_estado,
                            ),
                            ft.Text(
                                p["estado"],
                                size=10,
                                color=SECUNDARIO,
                            ),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=BLANCO,
            border=ft.Border.all(1, BORDE),
            border_radius=12,
            padding=11,
            on_click=lambda e: page.go("/revisiones/programadas"),
        )

    def tarjeta_trabajo(x):
        estado = x.get("estado_accion") or x.get("estado_hallazgo") or "Sin asignar"
        fecha_compromiso = x.get("fecha_compromiso")
        if hasattr(fecha_compromiso, "date"):
            fecha_compromiso = fecha_compromiso.date()
        if (
            fecha_compromiso
            and fecha_compromiso < date.today()
            and estado not in ("Cerrado", "Verificada")
        ):
            estado = "Vencida"
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                f"{x['codigo_maquina']} · {x['maquina']}",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                                expand=True,
                            ),
                            ft.Text(
                                estado,
                                size=10,
                                weight=ft.FontWeight.BOLD,
                                color=NARANJA_OSCURO,
                            ),
                        ]
                    ),
                    ft.Text(
                        x["descripcion_hallazgo"],
                        size=11,
                        color=SECUNDARIO,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        "Revisión: "
                        + (
                            x["fecha_revision"].strftime("%d/%m/%Y")
                            if x.get("fecha_revision")
                            else "Sin fecha"
                        ),
                        size=10,
                        color=SECUNDARIO,
                    ),
                    ft.Text(
                        "Técnico: " + str(x.get("tecnico") or "Sin asignar"),
                        size=10,
                        color=SECUNDARIO,
                    ),
                    *([
                        ft.Text(
                            "Compromiso: "
                            + x["fecha_compromiso"].strftime("%d/%m/%Y"),
                            size=10,
                            color=SECUNDARIO,
                        )
                    ] if x.get("fecha_compromiso") else []),
                ],
                spacing=5,
            ),
            bgcolor=BLANCO,
            border=ft.Border.all(1, BORDE),
            border_radius=12,
            padding=11,
            on_click=lambda e: page.go(
                f"/revisiones/resultado/{x['id_inspeccion']}"
            ),
        )

    cuerpo = ft.Column(
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # Encabezado personalizado
    cuerpo.controls.extend(
        [
            ft.Text(
                f"Hola, {primer_nombre}",
                size=22,
                weight=ft.FontWeight.BOLD,
                color=TEXTO,
            ),
            ft.Text(
                {
                    "Administrador": "Panel de administración del sistema.",
                    "Inspector": "Revisa el estado de las máquinas y tus inspecciones pendientes.",
                    "Técnico": "Consulta tus trabajos correctivos asignados.",
                }.get(rol, "Resumen de actividad."),
                size=12,
                color=SECUNDARIO,
            ),
        ]
    )

    try:
        if rol == "Técnico":
            trabajos = listar_hallazgos_y_acciones(int(usuario_id), rol)
            asignados = sum(
                1
                for x in trabajos
                if (x.get("estado_accion") or "") in ("Asignada", "En proceso", "Requiere ajuste")
            )
            verificacion = sum(
                1
                for x in trabajos
                if (x.get("estado_accion") or "") == "Pendiente de verificación"
            )

            cuerpo.controls.extend(
                [
                    ft.Text(
                        "Mi trabajo",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=TEXTO,
                    ),
                    ft.Row(
                        [
                            bloque_resumen(
                                "Por realizar",
                                asignados,
                                NARANJA_OSCURO,
                                ft.Icons.BUILD_OUTLINED,
                            ),
                            bloque_resumen(
                                "En verificación",
                                verificacion,
                                "#2563EB",
                                ft.Icons.FACT_CHECK_OUTLINED,
                            ),
                            bloque_resumen(
                                "Pendientes",
                                len(trabajos),
                                "#6B7280",
                                ft.Icons.ASSIGNMENT_OUTLINED,
                            ),
                        ],
                        spacing=8,
                    ),
                    boton_accion(
                        "VER MIS TRABAJOS",
                        ft.Icons.HANDYMAN_OUTLINED,
                        "/hallazgos",
                        True,
                    ),
                    ft.Text(
                        "Trabajos asignados",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=TEXTO,
                    ),
                ]
            )

            if trabajos:
                cuerpo.controls.extend(tarjeta_trabajo(x) for x in trabajos[:5])
            else:
                cuerpo.controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.TASK_ALT,
                                    size=38,
                                    color=VERDE,
                                ),
                                ft.Text(
                                    "No tienes trabajos pendientes",
                                    weight=ft.FontWeight.BOLD,
                                    color=TEXTO,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=7,
                        ),
                        bgcolor=BLANCO,
                        border=ft.Border.all(1, BORDE),
                        border_radius=12,
                        padding=24,
                        alignment=ft.Alignment.CENTER,
                    )
                )

        else:
            with SessionLocal() as db:
                resumen = obtener_resumen_dashboard(db)

            if rol == "Inspector":
                programadas = listar_programadas(
                    id_responsable=int(usuario_id)
                )
            else:
                programadas = listar_programadas()
            vencidas = sum(1 for p in programadas if p["estado"] == "Vencida")
            pendientes_h = listar_hallazgos_y_acciones(int(usuario_id), rol)

            cuerpo.controls.extend(
                [
                    ft.Text(
                        "Resumen general",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=TEXTO,
                    ),
                    ft.Row(
                        [
                            bloque_resumen(
                                "Operativas",
                                resumen["operativas"],
                                "#16A34A",
                                ft.Icons.CHECK_CIRCLE_OUTLINE,
                            ),
                            bloque_resumen(
                                "En revisión",
                                resumen["en_revision"],
                                "#D97706",
                                ft.Icons.BUILD_OUTLINED,
                            ),
                            bloque_resumen(
                                "Fuera de servicio",
                                resumen["fuera_de_servicio"],
                                "#DC2626",
                                ft.Icons.ERROR_OUTLINE,
                            ),
                            bloque_resumen(
                                "Total",
                                resumen["total"],
                                "#6B7280",
                                ft.Icons.DASHBOARD_OUTLINED,
                            ),
                        ],
                        spacing=8,
                    ),
                ]
            )

            if rol == "Administrador":
                usuarios = listar_usuarios_roles()
                cuerpo.controls.extend(
                    [
                        ft.Text(
                            "Administración",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Row(
                            [
                                boton_accion(
                                    f"USUARIOS ({len(usuarios)})",
                                    ft.Icons.MANAGE_ACCOUNTS_OUTLINED,
                                    "/usuarios",
                                    True,
                                ),
                                boton_accion(
                                    f"HALLAZGOS ({len(pendientes_h)})",
                                    ft.Icons.WARNING_AMBER_OUTLINED,
                                    "/hallazgos",
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Row(
                            [
                                boton_accion(
                                    "MÁQUINAS",
                                    ft.Icons.PRECISION_MANUFACTURING_OUTLINED,
                                    "/maquinas",
                                ),
                                boton_accion(
                                    "REVISIONES",
                                    ft.Icons.ASSIGNMENT_OUTLINED,
                                    "/revisiones",
                                ),
                            ],
                            spacing=8,
                        ),
                    ]
                )
                if pendientes_h:
                    cuerpo.controls.append(
                        ft.Text(
                            "Revisiones con hallazgos",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        )
                    )
                    cuerpo.controls.extend(
                        tarjeta_trabajo(x) for x in pendientes_h[:5]
                    )
            else:
                cuerpo.controls.extend(
                    [
                        ft.Text(
                            "Acciones del inspector",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=TEXTO,
                        ),
                        ft.Row(
                            [
                                boton_accion(
                                    "NUEVA REVISIÓN",
                                    ft.Icons.ADD_TASK,
                                    "/revisiones",
                                    True,
                                ),
                                boton_accion(
                                    f"HALLAZGOS ({len(pendientes_h)})",
                                    ft.Icons.WARNING_AMBER_OUTLINED,
                                    "/hallazgos",
                                ),
                            ],
                            spacing=8,
                        ),
                    ]
                )

            cuerpo.controls.extend(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Próximas revisiones",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                                expand=True,
                            ),
                            ft.TextButton(
                                content=ft.Text(
                                    "Gestionar",
                                    color=TEXTO,
                                    weight=ft.FontWeight.BOLD,
                                    size=11,
                                ),
                                on_click=lambda e: page.go("/revisiones"),
                            ),
                        ]
                    ),
                ]
            )

            if vencidas:
                cuerpo.controls.append(
                    ft.Container(
                        content=ft.Text(
                            f"{vencidas} revisión(es) vencida(s)",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ROJO,
                        ),
                        bgcolor="#FEE2E2",
                        border_radius=8,
                        padding=8,
                    )
                )

            if programadas:
                cuerpo.controls.extend(tarjeta_programada(p) for p in programadas[:5])
            else:
                cuerpo.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "No hay revisiones preventivas programadas.",
                            size=12,
                            color=SECUNDARIO,
                        ),
                        bgcolor=BLANCO,
                        border=ft.Border.all(1, BORDE),
                        border_radius=12,
                        padding=18,
                    )
                )

    except Exception as exc:
        cuerpo.controls.append(
            ft.Text(
                "No se pudo cargar el resumen: " + str(exc),
                color=ROJO,
                size=12,
            )
        )

    configurar_navbar(page, menu_mas, indice_inicial=0)

    page.add(
        ft.Column(
            [
                crear_header(),
                ft.Stack(
                    [
                        ft.Container(
                            content=cuerpo,
                            padding=16,
                            expand=True,
                        ),
                        ft.Container(
                            content=menu_mas,
                            right=12,
                            bottom=12,
                        ),
                    ],
                    expand=True,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
    )
