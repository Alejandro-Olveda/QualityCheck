import flet as ft
from sqlalchemy import text

import estilos
from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal

TEXTO = "#25252B"
SECUNDARIO = "#5F6670"
BORDE = "#DFE3EB"
BLANCO = "#FFFFFF"
VERDE = "#15803D"
NARANJA = "#B45309"
AZUL = "#2563EB"


def _fecha_texto(valor):
    if not valor:
        return "Sin fecha"
    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def obtener_bitacora():
    with SessionLocal() as db:
        revisiones = db.execute(text("""
            SELECT
                CASE
                    WHEN rev.tipo_inspeccion = 'Preventiva' THEN 'Preventivo'
                    WHEN rev.tipo_inspeccion = 'Correctiva' THEN 'Correctivo'
                    ELSE 'Inspección'
                END AS tipo,
                rev.id_inspeccion AS id_evento,
                m.id_maquina,
                m.codigo_maquina,
                m.nombre AS maquina,
                rev.fecha_inspeccion AS fecha,
                COALESCE(rev.observaciones_generales, '') AS trabajo,
                COALESCE(rev.observaciones_generales, '') AS observaciones,
                u.nombre AS responsable,
                NULL::varchar AS verificador,
                COALESCE(rev.resultado_final, 'Pendiente') AS estado,
                rev.codigo_inspeccion AS codigo_revision,
                NULL::varchar AS hallazgo,
                NULL::varchar AS severidad,
                NULL::text AS observacion_verificacion
            FROM revisiones rev
            JOIN maquinas m
              ON m.id_maquina = rev.id_maquina
            JOIN usuarios u
              ON u.id_usuario = rev.id_inspector
        """)).mappings().all()

        correctivos = db.execute(text("""
            SELECT
                'Correctivo verificado' AS tipo,
                ac.id_accion AS id_evento,
                m.id_maquina,
                m.codigo_maquina,
                m.nombre AS maquina,
                COALESCE(ac.fecha_verificacion, ac.fecha_realizada, ac.fecha_compromiso) AS fecha,
                ac.descripcion_accion AS trabajo,
                COALESCE(ac.observaciones_tecnico, '') AS observaciones,
                COALESCE(tec.nombre, ac.responsable) AS responsable,
                ver.nombre AS verificador,
                ac.estado AS estado,
                rev.codigo_inspeccion AS codigo_revision,
                h.descripcion AS hallazgo,
                h.nivel_severidad AS severidad,
                COALESCE(ac.observaciones_verificacion, '') AS observacion_verificacion
            FROM acciones_correctivas ac
            JOIN hallazgos h
              ON h.id_hallazgo = ac.id_hallazgo
            JOIN revisiones rev
              ON rev.id_inspeccion = h.id_inspeccion
            JOIN maquinas m
              ON m.id_maquina = rev.id_maquina
            LEFT JOIN usuarios tec
              ON tec.id_usuario = ac.id_responsable
            LEFT JOIN usuarios ver
              ON ver.id_usuario = ac.id_verificador
            WHERE ac.estado = 'Verificada'
        """)).mappings().all()

        eventos = [dict(x) for x in revisiones] + [dict(x) for x in correctivos]

        def clave_fecha(evento):
            valor = evento.get("fecha")
            if valor is None:
                return 0.0
            if hasattr(valor, "timestamp"):
                try:
                    return valor.timestamp()
                except Exception:
                    pass
            try:
                from datetime import datetime, time

                return datetime.combine(valor, time.min).timestamp()
            except Exception:
                return 0.0

        eventos.sort(key=clave_fecha, reverse=True)
        return eventos


def vista_bitacora(page: ft.Page):
    if not page.session.store.get("usuario_id"):
        page.go("/")
        return

    page.title = "QualityCheck - Bitácora de mantenimiento"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None

    aplicar_tema(page)
    menu_mas = crear_menu_mas(page)

    estado_datos = {
        "eventos": [],
        "error": None,
    }

    def recargar_datos():
        try:
            estado_datos["eventos"] = obtener_bitacora()
            estado_datos["error"] = None
        except Exception as exc:
            estado_datos["eventos"] = []
            estado_datos["error"] = str(exc)

    recargar_datos()

    def maquinas_disponibles():
        maquinas = {}
        for evento in estado_datos["eventos"]:
            maquinas[evento["id_maquina"]] = (
                f'{evento["codigo_maquina"]} · {evento["maquina"]}'
            )
        return maquinas

    maquinas = maquinas_disponibles()

    buscar = ft.TextField(
        hint_text="Buscar máquina, trabajo o responsable...",
        prefix_icon=ft.Icons.SEARCH,
        bgcolor=BLANCO,
        color=TEXTO,
        hint_style=ft.TextStyle(color=SECUNDARIO, size=12),
        border_color="#A3A8B1",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        expand=True,
        height=46,
    )

    filtro_tipo = ft.Dropdown(
        label="Tipo",
        value="Todos",
        options=[
            ft.DropdownOption(key="Todos", text="Todos"),
            ft.DropdownOption(key="Inspección", text="Inspección"),
            ft.DropdownOption(key="Preventivo", text="Preventivo"),
            ft.DropdownOption(key="Correctivo", text="Correctivo"),
            ft.DropdownOption(
                key="Correctivo verificado", text="Correctivo verificado"
            ),
        ],
        bgcolor=BLANCO,
        color=TEXTO,
        border_color="#A3A8B1",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        width=140,
    )

    filtro_maquina = ft.Dropdown(
        label="Máquina",
        value="Todas",
        options=[
            ft.DropdownOption(key="Todas", text="Todas"),
            *[
                ft.DropdownOption(key=str(k), text=v)
                for k, v in sorted(maquinas.items(), key=lambda x: x[1])
            ],
        ],
        bgcolor=BLANCO,
        color=TEXTO,
        border_color="#A3A8B1",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        expand=True,
    )

    resumen = ft.Text("", size=12, color=SECUNDARIO)
    lista = ft.Column(spacing=9)

    def cerrar_dialogo(dialogo):
        dialogo.open = False
        page.update()

    def detalle_evento(e):
        es_correctivo = e["tipo"] in ("Correctivo", "Correctivo verificado")

        filas = [
            ("Máquina", f'{e["codigo_maquina"]} · {e["maquina"]}'),
            ("Tipo", e["tipo"]),
            ("Fecha", _fecha_texto(e["fecha"])),
            ("Revisión origen", e.get("codigo_revision") or "—"),
            ("Responsable", e.get("responsable") or "—"),
            ("Estado", e.get("estado") or "—"),
        ]

        if es_correctivo:
            filas.extend(
                [
                    ("Hallazgo", e.get("hallazgo") or "—"),
                    ("Severidad", e.get("severidad") or "—"),
                    ("Verificado por", e.get("verificador") or "—"),
                ]
            )

        contenido = []
        for etiqueta, valor in filas:
            contenido.append(
                ft.Column(
                    [
                        ft.Text(etiqueta, size=10, color=SECUNDARIO),
                        ft.Text(
                            str(valor), size=12, color=TEXTO, weight=ft.FontWeight.BOLD
                        ),
                    ],
                    spacing=1,
                )
            )

        contenido.extend(
            [
                ft.Divider(height=1, color=BORDE),
                ft.Text("Trabajo realizado / programado", size=11, color=SECUNDARIO),
                ft.Text(e.get("trabajo") or "—", size=12, color=TEXTO),
            ]
        )

        if e.get("observaciones"):
            contenido.extend(
                [
                    ft.Text("Observaciones del responsable", size=11, color=SECUNDARIO),
                    ft.Text(e["observaciones"], size=12, color=TEXTO),
                ]
            )

        if e.get("observacion_verificacion"):
            contenido.extend(
                [
                    ft.Text("Observaciones de verificación", size=11, color=SECUNDARIO),
                    ft.Text(e["observacion_verificacion"], size=12, color=TEXTO),
                ]
            )

        d = ft.AlertDialog(
            title=ft.Text(
                "Detalle de mantenimiento",
                color=TEXTO,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Container(
                content=ft.Column(
                    contenido,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=420,
                height=440,
            ),
            bgcolor=BLANCO,
            actions=[
                ft.Button(
                    content=ft.Text(
                        "Cerrar",
                        color=TEXTO,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=estilos.COLOR_PRINCIPAL,
                    on_click=lambda _: cerrar_dialogo(d),
                )
            ],
        )
        page.overlay.append(d)
        d.open = True
        page.update()

    def tarjeta(e):
        es_correctivo = e["tipo"] in ("Correctivo", "Correctivo verificado")

        if e["tipo"] == "Preventivo":
            color = AZUL
            fondo = "#DBEAFE"
        elif es_correctivo:
            color = NARANJA
            fondo = "#FEF3C7"
        else:
            color = "#6D28D9"
            fondo = "#EDE9FE"

        subtitulo = (
            e.get("hallazgo")
            if es_correctivo and e.get("hallazgo")
            else e.get("trabajo")
        ) or "Sin descripción"

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        f'{e["codigo_maquina"]} · {e["maquina"]}',
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXTO,
                                    ),
                                    ft.Text(
                                        subtitulo,
                                        size=11,
                                        color=SECUNDARIO,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    e["tipo"],
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=color,
                                ),
                                bgcolor=fondo,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                                border_radius=14,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color="#EEF0F3"),
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.CALENDAR_MONTH_OUTLINED,
                                        size=15,
                                        color=SECUNDARIO,
                                    ),
                                    ft.Text(
                                        _fecha_texto(e["fecha"]),
                                        size=11,
                                        color=SECUNDARIO,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.PERSON_OUTLINE,
                                        size=15,
                                        color=SECUNDARIO,
                                    ),
                                    ft.Text(
                                        e.get("responsable") or "Sin responsable",
                                        size=11,
                                        color=SECUNDARIO,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                e.get("codigo_revision") or "Sin revisión vinculada",
                                size=10,
                                color=SECUNDARIO,
                            ),
                            ft.Text(
                                "Ver detalle  ›",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=estilos.COLOR_PRINCIPAL,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=6,
            ),
            bgcolor=BLANCO,
            border=ft.Border.all(1, BORDE),
            border_radius=12,
            padding=12,
            on_click=lambda _, evento=e: detalle_evento(evento),
        )

    def actualizar(_=None):
        texto = (buscar.value or "").strip().casefold()
        tipo = filtro_tipo.value or "Todos"
        maquina = filtro_maquina.value or "Todas"

        visibles = []
        for e in estado_datos["eventos"]:
            if tipo != "Todos" and e["tipo"] != tipo:
                continue

            if maquina != "Todas" and str(e["id_maquina"]) != maquina:
                continue

            bolsa = " ".join(
                [
                    e.get("codigo_maquina") or "",
                    e.get("maquina") or "",
                    e.get("trabajo") or "",
                    e.get("responsable") or "",
                    e.get("verificador") or "",
                    e.get("hallazgo") or "",
                    e.get("codigo_revision") or "",
                ]
            ).casefold()

            if texto and texto not in bolsa:
                continue

            visibles.append(e)

        lista.controls.clear()

        if estado_datos["error"]:
            lista.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No se pudo consultar la bitácora: " + estado_datos["error"],
                        color="#B91C1C",
                        size=12,
                    ),
                    bgcolor="#FEE2E2",
                    padding=12,
                    border_radius=10,
                )
            )
        elif visibles:
            lista.controls.extend(tarjeta(e) for e in visibles)
        else:
            lista.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(
                                ft.Icons.HISTORY_OUTLINED, size=42, color="#9CA3AF"
                            ),
                            ft.Text(
                                "Sin registros de mantenimiento",
                                color=TEXTO,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Las revisiones realizadas y los correctivos verificados aparecerán aquí.",
                                size=12,
                                color=SECUNDARIO,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=7,
                    ),
                    bgcolor=BLANCO,
                    border=ft.Border.all(1, BORDE),
                    border_radius=12,
                    padding=26,
                    alignment=ft.Alignment.CENTER,
                )
            )

        resumen.value = f"{len(visibles)} registro(s)"
        page.update()

    def refrescar(_=None):
        maquina_anterior = filtro_maquina.value or "Todas"
        recargar_datos()

        nuevas_maquinas = maquinas_disponibles()
        filtro_maquina.options = [
            ft.DropdownOption(key="Todas", text="Todas"),
            *[
                ft.DropdownOption(key=str(k), text=v)
                for k, v in sorted(nuevas_maquinas.items(), key=lambda x: x[1])
            ],
        ]

        claves = {"Todas"} | {str(k) for k in nuevas_maquinas.keys()}
        filtro_maquina.value = (
            maquina_anterior if maquina_anterior in claves else "Todas"
        )
        actualizar()

    buscar.on_change = actualizar
    filtro_tipo.on_change = actualizar
    filtro_maquina.on_change = actualizar

    cuerpo = ft.Column(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                "Bitácora de mantenimiento",
                                size=21,
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                            ),
                            ft.Text(
                                "Historial consolidado de mantenimientos preventivos y correctivos.",
                                size=12,
                                color=SECUNDARIO,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_color=TEXTO,
                        tooltip="Actualizar bitácora",
                        on_click=refrescar,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            buscar,
            ft.Row([filtro_maquina, filtro_tipo], spacing=8),
            resumen,
            lista,
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    configurar_navbar(page, menu_mas, indice_inicial=0)

    page.add(
        ft.Column(
            [
                crear_header(titulo="Bitácora de mantenimiento"),
                ft.Stack(
                    [
                        ft.Container(content=cuerpo, padding=16, expand=True),
                        ft.Container(content=menu_mas, right=12, bottom=12),
                    ],
                    expand=True,
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
    )

    actualizar()
