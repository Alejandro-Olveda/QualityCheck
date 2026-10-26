import flet as ft
import estilos

from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal
from models import Maquina, Area, Inspeccion, Hallazgo


TEXTO = estilos.COLOR_TEXTO
SECUNDARIO = "#5F6670"
NARANJA = estilos.COLOR_PRINCIPAL


def _normalizar(texto):
    return (texto or "").strip().casefold()


def _badge_estado(estado):
    mapa = {
        "operativa": ("#DCFCE7", "#166534"),
        "en revisión": ("#FEF3C7", "#92400E"),
        "fuera de servicio": ("#FEE2E2", "#991B1B"),
        "inactiva": ("#F3F4F6", "#4B5563"),
    }
    fondo, color = mapa.get(_normalizar(estado), ("#F3F4F6", "#4B5563"))
    return ft.Container(
        content=ft.Text(
            estado or "Sin estado",
            size=10,
            weight=ft.FontWeight.BOLD,
            color=color,
        ),
        bgcolor=fondo,
        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
        border_radius=14,
    )


def vista_listado(page: ft.Page):
    page.title = "QualityCheck - Máquinas"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None

    if not page.session.store.get("usuario_id"):
        page.go("/")
        return

    rol = page.session.store.get("usuario_rol") or "Sin rol"
    aplicar_tema(page)

    header = crear_header(titulo="Máquinas")
    menu_mas = crear_menu_mas(page)

    def cargar_datos():
        with SessionLocal() as db:
            filas = (
                db.query(Maquina, Area)
                .outerjoin(Area, Maquina.id_area == Area.id_area)
                .order_by(Maquina.id_maquina.desc())
                .all()
            )

            revisiones = (
                db.query(Inspeccion)
                .order_by(
                    Inspeccion.id_maquina,
                    Inspeccion.fecha_inspeccion.desc(),
                    Inspeccion.id_inspeccion.desc(),
                )
                .all()
            )

            ultima_revision = {}
            for rev in revisiones:
                if rev.id_maquina not in ultima_revision:
                    ultima_revision[rev.id_maquina] = rev

            hallazgos_abiertos = {}
            rows_hallazgos = (
                db.query(Hallazgo, Inspeccion)
                .join(
                    Inspeccion,
                    Hallazgo.id_inspeccion == Inspeccion.id_inspeccion,
                )
                .all()
            )

            estados_cerrados = {"cerrado", "cerrada", "corregido", "corregida"}

            for hallazgo, revision in rows_hallazgos:
                if _normalizar(hallazgo.estado) not in estados_cerrados:
                    hallazgos_abiertos[revision.id_maquina] = (
                        hallazgos_abiertos.get(revision.id_maquina, 0) + 1
                    )

            return [
                {
                    "id": maquina.id_maquina,
                    "codigo": maquina.codigo_maquina or "",
                    "nombre": maquina.nombre or "",
                    "tipo": maquina.tipo or "",
                    "ubicacion": maquina.ubicacion or "",
                    "estado": maquina.estado or "",
                    "activa": bool(maquina.activa),
                    "area": area.nombre if area else "Sin área",
                    "ultima_revision": ultima_revision.get(maquina.id_maquina),
                    "hallazgos_abiertos": hallazgos_abiertos.get(
                        maquina.id_maquina, 0
                    ),
                }
                for maquina, area in filas
            ]

    datos = cargar_datos()

    txt_buscar = ft.TextField(
        hint_text="Buscar por código, nombre, área o ubicación...",
        prefix_icon=ft.Icons.SEARCH,
        border_color="#D1D5DB",
        focused_border_color=NARANJA,
        bgcolor="#FFFFFF",
        color=TEXTO,
        hint_style=ft.TextStyle(color=SECUNDARIO),
        height=46,
        text_size=13,
        expand=True,
    )

    lista = ft.Column(spacing=10)
    resumen = ft.Text("", size=12, color=SECUNDARIO)

    filtro_actual = {"valor": "activas"}

    filtros = [
        ("activas", "Activas"),
        ("todas", "Todas"),
        ("operativa", "Operativas"),
        ("en revisión", "En revisión"),
        ("fuera de servicio", "Fuera de servicio"),
        ("inactivas", "Inactivas"),
    ]

    contenedor_filtros = ft.Row(
        spacing=6,
        wrap=True,
    )

    def construir_boton_filtro(valor, etiqueta):
        seleccionado = filtro_actual["valor"] == valor

        return ft.Container(
            content=ft.Text(
                etiqueta,
                size=11,
                weight=ft.FontWeight.BOLD,
                color="#25252B",
            ),
            bgcolor=NARANJA if seleccionado else "#FFFFFF",
            border=ft.Border.all(
                1,
                NARANJA if seleccionado else "#D1D5DB",
            ),
            border_radius=18,
            padding=ft.Padding.symmetric(horizontal=11, vertical=7),
            on_click=lambda e, v=valor: seleccionar_filtro(v),
        )

    def renderizar_filtros():
        contenedor_filtros.controls = [
            construir_boton_filtro(valor, etiqueta)
            for valor, etiqueta in filtros
        ]

    def coincide_filtro(maquina):
        f = filtro_actual["valor"]

        if f == "todas":
            return True

        if f == "activas":
            return maquina["activa"]

        if f == "inactivas":
            return not maquina["activa"]

        if not maquina["activa"]:
            return False

        return _normalizar(maquina["estado"]) == f

    def tarjeta(maquina):
        estado_visible = (
            maquina["estado"]
            if maquina["activa"]
            else "Inactiva"
        )

        rev = maquina["ultima_revision"]

        if rev:
            fecha = (
                rev.fecha_inspeccion.strftime("%d/%m/%Y")
                if rev.fecha_inspeccion
                else "—"
            )
            info_revision = (
                f"Última revisión: {fecha} · "
                f"{rev.resultado_final or 'Pendiente'}"
            )
        else:
            info_revision = "Sin revisiones registradas"

        cantidad = maquina["hallazgos_abiertos"]

        if cantidad:
            info_hallazgo = (
                f"{cantidad} hallazgo abierto"
                if cantidad == 1
                else f"{cantidad} hallazgos abiertos"
            )
            color_hallazgo = "#92400E"
        else:
            info_hallazgo = "Sin hallazgos abiertos"
            color_hallazgo = "#166534"

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{maquina['codigo']} · "
                                        f"{maquina['nombre']}",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=TEXTO,
                                    ),
                                    ft.Text(
                                        f"{maquina['area']} · "
                                        f"{maquina['ubicacion'] or 'Sin ubicación'}",
                                        size=11,
                                        color=SECUNDARIO,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            _badge_estado(estado_visible),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=1, color="#EEF0F3"),
                    ft.Text(
                        info_revision,
                        size=11,
                        color=SECUNDARIO,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                info_hallazgo,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=color_hallazgo,
                            ),
                            ft.Row(
                                [
                                    ft.Text(
                                        "Ver detalle",
                                        size=11,
                                        color=SECUNDARIO,
                                    ),
                                    ft.Icon(
                                        ft.Icons.CHEVRON_RIGHT,
                                        size=17,
                                        color=SECUNDARIO,
                                    ),
                                ],
                                spacing=2,
                                tight=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=7,
            ),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, "#DFE3EB"),
            border_radius=12,
            padding=13,
            on_click=lambda e, codigo=maquina["codigo"]: page.go(
                f"/maquinas/{codigo}"
            ),
        )

    def actualizar(e=None):
        busqueda = _normalizar(txt_buscar.value)

        visibles = []

        for maquina in datos:
            if not coincide_filtro(maquina):
                continue

            texto_busqueda = _normalizar(
                " ".join(
                    [
                        maquina["codigo"],
                        maquina["nombre"],
                        maquina["tipo"],
                        maquina["ubicacion"],
                        maquina["area"],
                        maquina["estado"],
                    ]
                )
            )

            if busqueda and busqueda not in texto_busqueda:
                continue

            visibles.append(maquina)

        lista.controls.clear()

        if visibles:
            lista.controls.extend(
                tarjeta(maquina)
                for maquina in visibles
            )
        else:
            lista.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(
                                ft.Icons.PRECISION_MANUFACTURING_OUTLINED,
                                size=42,
                                color="#6B7280",
                            ),
                            ft.Text(
                                "No se encontraron máquinas",
                                weight=ft.FontWeight.BOLD,
                                color=TEXTO,
                            ),
                            ft.Text(
                                "Prueba con otro filtro o búsqueda.",
                                size=12,
                                color=SECUNDARIO,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=7,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=35,
                )
            )

        resumen.value = f"{len(visibles)} máquina(s)"
        renderizar_filtros()
        page.update()

    def seleccionar_filtro(valor):
        filtro_actual["valor"] = valor
        actualizar()

    txt_buscar.on_change = actualizar

    renderizar_filtros()

    btn_agregar = ft.Button(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.ADD,
                    size=18,
                    color="#25252B",
                ),
                ft.Text(
                    "REGISTRAR MÁQUINA",
                    weight=ft.FontWeight.BOLD,
                    color="#25252B",
                    size=12,
                ),
            ],
            tight=True,
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=NARANJA,
        height=45,
        on_click=lambda e: page.go("/agregar_maquina"),
    )

    encabezado_maquinas = [resumen]
    if rol != "Técnico":
        encabezado_maquinas.append(btn_agregar)

    cuerpo = ft.Column(
        [
            txt_buscar,
            contenedor_filtros,
            ft.Row(
                encabezado_maquinas,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            lista,
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    configurar_navbar(
        page,
        menu_mas,
        indice_inicial=1,
    )

    page.add(
        ft.Column(
            [
                header,
                ft.Stack(
                    [
                        ft.Container(
                            content=cuerpo,
                            padding=16,
                            expand=True,
                        ),
                        ft.Container(
                            content=menu_mas,
                            right=15,
                            bottom=15,
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

    actualizar()
