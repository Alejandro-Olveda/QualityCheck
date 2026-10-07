import flet as ft
import estilos

from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal
from models import Maquina, Area, Inspeccion, CriterioInspeccion, Hallazgo, AccionCorrectiva


def _badge(estado):
    mapa = {
        "Operativa": ("#DCFCE7", "#166534"),
        "En revisión": ("#FEF3C7", "#92400E"),
        "Fuera de servicio": ("#FEE2E2", "#991B1B"),
        "Inactiva": ("#F3F4F6", "#6B7280"),
    }
    bg, fg = mapa.get(estado or "", ("#F3F4F6", "#6B7280"))
    return ft.Container(
        content=ft.Text(estado or "Sin estado", size=10, weight=ft.FontWeight.BOLD, color=fg),
        bgcolor=bg,
        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
        border_radius=14,
    )


def vista_detalle_maquina(page: ft.Page, codigo_maquina: str):
    page.title = f"QualityCheck - {codigo_maquina}"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None

    if not page.session.store.get("usuario_id"):
        page.go("/")
        return

    aplicar_tema(page)
    menu_mas = crear_menu_mas(page)

    def aviso(msg):
        sb = ft.SnackBar(content=ft.Text(msg, color="#FFFFFF"), bgcolor=estilos.COLOR_TEXTO)
        page.overlay.append(sb)
        sb.open = True
        page.update()

    def cargar():
        with SessionLocal() as db:
            fila = (
                db.query(Maquina, Area)
                .outerjoin(Area, Maquina.id_area == Area.id_area)
                .filter(Maquina.codigo_maquina == codigo_maquina)
                .first()
            )
            if not fila:
                return None
            m, area = fila

            revisiones = (
                db.query(Inspeccion)
                .filter(Inspeccion.id_maquina == m.id_maquina)
                .order_by(Inspeccion.fecha_inspeccion.desc())
                .all()
            )
            criterios = (
                db.query(CriterioInspeccion)
                .filter(
                    CriterioInspeccion.id_maquina == m.id_maquina,
                    CriterioInspeccion.activo.is_(True),
                )
                .order_by(CriterioInspeccion.id_criterio)
                .all()
            )
            hallazgos = (
                db.query(Hallazgo)
                .join(Inspeccion, Hallazgo.id_inspeccion == Inspeccion.id_inspeccion)
                .filter(Inspeccion.id_maquina == m.id_maquina)
                .order_by(Hallazgo.id_hallazgo.desc())
                .all()
            )

            return {
                "id": m.id_maquina,
                "codigo": m.codigo_maquina,
                "nombre": m.nombre,
                "tipo": m.tipo,
                "marca": m.marca,
                "modelo": m.modelo,
                "ubicacion": m.ubicacion,
                "estado": m.estado,
                "activa": bool(m.activa),
                "area": area.nombre if area else "Sin área",
                "revisiones": [
                    {
                        "id": r.id_inspeccion,
                        "codigo": r.codigo_inspeccion,
                        "fecha": r.fecha_inspeccion,
                        "resultado": r.resultado_final,
                        "tipo": r.tipo_inspeccion,
                    }
                    for r in revisiones
                ],
                "criterios": [
                    {"id": c.id_criterio, "nombre": c.nombre_criterio, "categoria": c.categoria}
                    for c in criterios
                ],
                "hallazgos": [
                    {
                        "id": h.id_hallazgo,
                        "descripcion": h.descripcion,
                        "estado": h.estado,
                        "severidad": h.nivel_severidad,
                    }
                    for h in hallazgos
                ],
            }

    data = cargar()
    if not data:
        page.add(ft.Text("Máquina no encontrada.", color="#DC2626"))
        return

    rol = (page.session.store.get("usuario_rol") or "").casefold()
    puede_admin = rol in ("administrador", "admin", "sistemas", "administrador/sistemas")
    puede_editar = puede_admin or rol in ("inspector", "")
    estado_visible = data["estado"] if data["activa"] else "Inactiva"

    def confirmar_desactivar(e=None):
        accion = "reactivar" if not data["activa"] else "desactivar"
        dialogo = ft.AlertDialog(
            title=ft.Text(
                f"{accion.capitalize()} máquina",
                weight=ft.FontWeight.BOLD,
                color=estilos.COLOR_TEXTO,
            ),
            content=ft.Text(
                f"¿Deseas {accion} {data['codigo']} · {data['nombre']}?"
                + ("\nLa máquina dejará de aparecer en el catálogo activo." if data["activa"] else ""),
                color=estilos.COLOR_TEXTO,
            ),
            bgcolor="#FFFFFF",
        )

        def ejecutar(_):
            try:
                with SessionLocal.begin() as db:
                    m = db.query(Maquina).filter(Maquina.id_maquina == data["id"]).first()
                    if not m:
                        raise ValueError("La máquina ya no existe.")
                    m.activa = not data["activa"]
                dialogo.open = False
                page.go("/maquinas")
            except Exception as ex:
                dialogo.open = False
                aviso(f"No se pudo actualizar: {ex}")

        dialogo.actions = [
            ft.TextButton(content=ft.Text("Cancelar", color=estilos.COLOR_TEXTO), on_click=lambda _: setattr(dialogo, "open", False) or page.update()),
            ft.Button(
                content=ft.Text(accion.capitalize(), color=estilos.COLOR_TEXTO, weight=ft.FontWeight.BOLD),
                bgcolor=estilos.COLOR_PRINCIPAL,
                on_click=ejecutar,
            ),
        ]
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    def confirmar_eliminar(e=None):
        if data["revisiones"] or data["hallazgos"]:
            aviso("No se puede eliminar: la máquina tiene historial. Desactívala para conservar la trazabilidad.")
            return

        dialogo = ft.AlertDialog(
            title=ft.Text(
                "Eliminar definitivamente",
                weight=ft.FontWeight.BOLD,
                color="#991B1B",
            ),
            content=ft.Text(
                f"¿Eliminar definitivamente {data['codigo']} · {data['nombre']}?\n"
                "También se eliminarán sus criterios de inspección. Esta acción no se puede deshacer.",
                color=estilos.COLOR_TEXTO,
            ),
            bgcolor="#FFFFFF",
        )

        def ejecutar(_):
            try:
                with SessionLocal.begin() as db:
                    db.query(CriterioInspeccion).filter(CriterioInspeccion.id_maquina == data["id"]).delete(
                        synchronize_session=False
                    )
                    m = db.query(Maquina).filter(Maquina.id_maquina == data["id"]).first()
                    if m:
                        db.delete(m)
                dialogo.open = False
                page.go("/maquinas")
            except Exception as ex:
                dialogo.open = False
                aviso(f"No se pudo eliminar: {ex}")

        dialogo.actions = [
            ft.TextButton(content=ft.Text("Cancelar", color=estilos.COLOR_TEXTO), on_click=lambda _: setattr(dialogo, "open", False) or page.update()),
            ft.Button(
                content=ft.Text("Eliminar", color="#FFFFFF", weight=ft.FontWeight.BOLD),
                bgcolor="#DC2626",
                on_click=ejecutar,
            ),
        ]
        page.overlay.append(dialogo)
        dialogo.open = True
        page.update()

    tarjeta_info = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(f"{data['codigo']} · {data['nombre']}", size=19, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
                                ft.Text(data["area"], size=12, color="#5F6670"),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        _badge(estado_visible),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color="#E5E7EB"),
                ft.Text(f"Tipo: {data['tipo'] or 'N/A'}", size=12, color=estilos.COLOR_TEXTO),
                ft.Text(f"Marca - Modelo: {data['marca'] or 'N/A'} - {data['modelo'] or 'N/A'}", size=12, color=estilos.COLOR_TEXTO),
                ft.Text(f"Ubicación: {data['ubicacion'] or 'Sin ubicación'}", size=12, color=estilos.COLOR_TEXTO),
            ],
            spacing=7,
        ),
        bgcolor="#FFFFFF",
        padding=15,
        border_radius=12,
        border=ft.Border.all(1, "#DFE3EB"),
    )

    abiertos = [h for h in data["hallazgos"] if h["estado"] not in ("Cerrado",)]
    def tarjeta_resumen(titulo, valor, color_valor):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(
                            titulo,
                            size=11,
                            color="#4B5563",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        height=28,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text(
                        str(valor),
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=color_valor,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor="#FFFFFF",
            padding=10,
            border_radius=10,
            height=92,
            expand=True,
            border=ft.Border.all(1, "#E5E7EB"),
        )

    resumen = ft.Container(
        content=ft.Row(
            [
                tarjeta_resumen(
                    "Criterios",
                    len(data["criterios"]),
                    "#5F6670",
                ),
                tarjeta_resumen(
                    "Revisiones",
                    len(data["revisiones"]),
                    "#5F6670",
                ),
                tarjeta_resumen(
                    "Hallazgos abiertos",
                    len(abiertos),
                    "#B45309" if abiertos else "#15803D",
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        height=96,
    )

    criterios_ui = ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(c["nombre"], size=13, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
                                ft.Text(c["categoria"], size=11, color="#5F6670"),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=18, color="#15803D"),
                    ]
                ),
                bgcolor="#FFFFFF",
                padding=10,
                border_radius=8,
                border=ft.Border.all(1, "#E5E7EB"),
            )
            for c in data["criterios"]
        ]
        or [ft.Text("Sin criterios activos.", size=12, color="#5F6670")],
        spacing=6,
    )

    revisiones_ui = ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(r["codigo"], size=12, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
                                ft.Text(
                                    f"{r['tipo']} · {r['fecha'].strftime('%d/%m/%Y') if r['fecha'] else '—'}",
                                    size=11,
                                    color="#5F6670",
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Text(r["resultado"] or "Pendiente", size=11, weight=ft.FontWeight.BOLD, color="#B45309"),
                    ]
                ),
                bgcolor="#FFFFFF", padding=10, border_radius=8, border=ft.Border.all(1, "#E5E7EB"),
                on_click=lambda e, rid=r["id"]: page.go(f"/revisiones/{rid}"),
            )
            for r in data["revisiones"][:10]
        ]
        or [ft.Text("Sin revisiones registradas.", size=12, color="#5F6670")],
        spacing=6,
    )

    hallazgos_ui = ft.Column(
        [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(h["descripcion"], size=12, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO, expand=True),
                                ft.Text(h["estado"], size=10, color="#B45309"),
                            ]
                        ),
                        ft.Text(f"Severidad: {h['severidad']}", size=11, color="#5F6670"),
                    ],
                    spacing=3,
                ),
                bgcolor="#FFFFFF", padding=10, border_radius=8, border=ft.Border.all(1, "#E5E7EB"),
            )
            for h in data["hallazgos"][:10]
        ]
        or [ft.Text("Sin hallazgos registrados.", size=12, color="#5F6670")],
        spacing=6,
    )

    acciones = []
    if data["activa"]:
        acciones.append(
            ft.Button(
                content=ft.Container(
                    content=ft.Text(
                        "NUEVA INSPECCIÓN",
                        weight=ft.FontWeight.BOLD,
                        color=estilos.COLOR_TEXTO,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                bgcolor=estilos.COLOR_PRINCIPAL,
                height=44,
                expand=True,
                on_click=lambda e: page.go(f"/revisiones/maquina/{data['codigo']}"),
            )
        )
    if puede_editar:
        acciones.append(
            ft.Button(
                content=ft.Container(
                    content=ft.Text(
                        "EDITAR",
                        weight=ft.FontWeight.BOLD,
                        color=estilos.COLOR_TEXTO,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                bgcolor="#E5E7EB",
                height=44,
                expand=True,
                on_click=lambda e: page.go(f"/editar_maquina/{data['codigo']}"),
            )
        )

    admin_controls = []
    if puede_admin or rol == "":
        admin_controls.append(
            ft.Button(
                content=ft.Container(
                    content=ft.Text(
                        "REACTIVAR MÁQUINA" if not data["activa"] else "DESACTIVAR MÁQUINA",
                        color="#92400E",
                        weight=ft.FontWeight.BOLD,
                        size=11,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                bgcolor="#FEF3C7",
                height=42,
                expand=True,
                on_click=confirmar_desactivar,
            )
        )
        admin_controls.append(
            ft.Button(
                content=ft.Container(
                    content=ft.Text(
                        "ELIMINAR DEFINITIVAMENTE",
                        color="#991B1B",
                        weight=ft.FontWeight.BOLD,
                        size=11,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                bgcolor="#FEE2E2",
                height=42,
                expand=True,
                on_click=confirmar_eliminar,
            )
        )

    cuerpo = ft.Column(
        [
            ft.TextButton(
                content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK, size=17, color=estilos.COLOR_TEXTO), ft.Text("Volver a máquinas", color=estilos.COLOR_TEXTO)], tight=True, spacing=5),
                on_click=lambda e: page.go("/maquinas"),
            ),
            tarjeta_info,
            resumen,
            ft.Container(
                content=ft.Row(
                    acciones,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=48,
            ) if acciones else ft.Container(),
            ft.Text("Criterios de inspección", size=15, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
            criterios_ui,
            ft.Text("Revisiones recientes", size=15, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
            revisiones_ui,
            ft.Text("Hallazgos", size=15, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
            hallazgos_ui,
            ft.Divider(height=1, color="#E5E7EB"),
            ft.Container(
                content=ft.Row(
                    admin_controls,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=46,
            ) if admin_controls else ft.Container(),
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    configurar_navbar(page, menu_mas, indice_inicial=1)

    page.add(
        ft.Column(
            [
                crear_header(titulo="Detalle de máquina"),
                ft.Stack(
                    [
                        ft.Container(content=cuerpo, padding=16, expand=True),
                        ft.Container(content=menu_mas, right=15, bottom=15),
                    ],
                    expand=True,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
    )
