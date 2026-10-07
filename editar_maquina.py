import flet as ft
import estilos
from sqlalchemy.exc import IntegrityError

from componentes import aplicar_tema, crear_header, crear_menu_mas, configurar_navbar
from database import SessionLocal
from models import Area, Maquina, CriterioInspeccion


TEXTO = estilos.COLOR_TEXTO
GRIS = "#5F6670"
NARANJA = estilos.COLOR_PRINCIPAL


def campo(etiqueta, valor="", pista="", disabled=False):
    return ft.TextField(
        label=etiqueta,
        value=valor or "",
        hint_text=pista,
        read_only=disabled,
        border_color="#A3A8B1",
        focused_border_color=NARANJA,
        label_style=ft.TextStyle(size=12, color="#505966"),
        hint_style=ft.TextStyle(color="#7B8493", size=12),
        bgcolor="#F3F4F6" if disabled else "#FFFFFF",
        color=TEXTO,
        expand=True,
    )


def desplegable(etiqueta, opciones, valor=None, expand=True, width=None):
    return ft.Dropdown(
        label=etiqueta,
        value=valor,
        options=[ft.DropdownOption(key=str(k), text=str(v)) for k, v in opciones],
        border_color="#A3A8B1",
        focused_border_color=NARANJA,
        label_style=ft.TextStyle(size=12, color="#505966"),
        bgcolor="#FFFFFF",
        color=TEXTO,
        expand=expand,
        width=width,
    )


def aviso(page, mensaje):
    barra = ft.SnackBar(content=ft.Text(mensaje, color="#FFFFFF"), bgcolor=TEXTO)
    page.overlay.append(barra)
    barra.open = True
    page.update()


def vista_editar_maquina(page: ft.Page, codigo_maquina: str):
    aplicar_tema(page)
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.title = f"QualityCheck - Editar {codigo_maquina}"
    page.floating_action_button = None

    menu_mas = crear_menu_mas(page)

    with SessionLocal() as db:
        maq = db.query(Maquina).filter(
            Maquina.codigo_maquina == codigo_maquina,
            Maquina.activa.is_(True),
        ).first()
        if not maq:
            page.add(ft.Text("La máquina no existe o está inactiva.", color="#DC2626"))
            return

        areas = [
            (str(a.id_area), a.nombre)
            for a in db.query(Area).filter(Area.activa.is_(True)).order_by(Area.nombre).all()
        ]
        criterios_db = (
            db.query(CriterioInspeccion)
            .filter(
                CriterioInspeccion.id_maquina == maq.id_maquina,
                CriterioInspeccion.activo.is_(True),
            )
            .order_by(CriterioInspeccion.id_criterio)
            .all()
        )

        datos = {
            "id": maq.id_maquina,
            "codigo": maq.codigo_maquina,
            "nombre": maq.nombre,
            "marca": maq.marca,
            "modelo": maq.modelo,
            "ubicacion": maq.ubicacion,
            "id_area": maq.id_area,
            "estado": maq.estado,
        }
        criterios = [
            {"id": c.id_criterio, "nombre": c.nombre_criterio, "categoria": c.categoria}
            for c in criterios_db
        ]

    codigo = campo("Código", datos["codigo"], disabled=True)
    nombre = campo("Nombre *", datos["nombre"])
    marca = campo("Marca", datos["marca"])
    modelo = campo("Modelo", datos["modelo"])
    ubicacion = campo("Ubicación", datos["ubicacion"])
    area = desplegable("Área *", areas, str(datos["id_area"]))
    estado = desplegable(
        "Estado",
        [(x, x) for x in ("Operativa", "En revisión", "Fuera de servicio")],
        datos["estado"] or "Operativa",
    )

    nuevo_nombre = campo("Nombre del criterio / punto a revisar", pista="Ej. Nivel de aceite hidráulico")
    categoria = desplegable(
        "Categoría",
        [(c, c) for c in ("General", "Seguridad", "Mantenimiento", "Mecánico", "Eléctrico", "Neumático", "Calidad")],
        "General",
        expand=False,
        width=145,
    )
    lista = ft.Column(spacing=8)

    def quitar(indice):
        criterios.pop(indice)
        render()

    def render():
        lista.controls = [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(c["nombre"], size=13, weight=ft.FontWeight.BOLD, color=TEXTO),
                                ft.Text(f"Categoría: {c['categoria']}", size=11, color=GRIS),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color="#DC2626",
                            tooltip="Desactivar criterio",
                            on_click=lambda e, idx=i: quitar(idx),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor="#FFFFFF",
                padding=9,
                border_radius=8,
                border=ft.Border.all(1, "#DFE3EB"),
            )
            for i, c in enumerate(criterios)
        ]
        page.update()

    def agregar(e):
        texto = (nuevo_nombre.value or "").strip()
        if not texto:
            aviso(page, "Escribe el nombre del criterio.")
            return
        if any(c["nombre"].casefold() == texto.casefold() for c in criterios):
            aviso(page, "Ese criterio ya está agregado.")
            return
        criterios.append(
            {
                "id": None,
                "nombre": texto,
                "categoria": categoria.value or "General",
            }
        )
        nuevo_nombre.value = ""
        render()

    def guardar(e):
        nom = (nombre.value or "").strip()
        if not nom or not area.value:
            aviso(page, "Completa nombre y área.")
            return
        if not criterios:
            aviso(page, "Agrega al menos un criterio de inspección.")
            return

        try:
            with SessionLocal.begin() as db:
                m = db.query(Maquina).filter(Maquina.id_maquina == datos["id"]).first()
                if not m:
                    raise ValueError("La máquina ya no existe.")

                m.nombre = nom
                m.marca = (marca.value or "").strip() or None
                m.modelo = (modelo.value or "").strip() or None
                m.ubicacion = (ubicacion.value or "").strip() or None
                m.id_area = int(area.value)
                m.estado = estado.value or "Operativa"

                activos = {c["id"] for c in criterios if c["id"] is not None}

                for original in db.query(CriterioInspeccion).filter(
                    CriterioInspeccion.id_maquina == datos["id"],
                    CriterioInspeccion.activo.is_(True),
                ).all():
                    if original.id_criterio not in activos:
                        original.activo = False

                for c in criterios:
                    if c["id"] is None:
                        db.add(
                            CriterioInspeccion(
                                id_maquina=datos["id"],
                                nombre_criterio=c["nombre"],
                                categoria=c["categoria"],
                                activo=True,
                            )
                        )

            page.go(f"/maquinas/{datos['codigo']}")
        except Exception as ex:
            aviso(page, f"No se pudo guardar: {ex}")

    seccion_criterios = ft.Column(
        [
            ft.Divider(height=1, color="#DFE3EB"),
            ft.Text("Criterios de inspección", size=16, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text(
                "Los criterios retirados se desactivan para conservar el historial de revisiones.",
                size=12,
                color=GRIS,
            ),
            ft.Row(
                [
                    nuevo_nombre,
                    categoria,
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE,
                        icon_color=NARANJA,
                        tooltip="Agregar criterio",
                        on_click=agregar,
                    ),
                ],
                spacing=8,
            ),
            lista,
        ],
        spacing=9,
    )

    formulario = ft.Column(
        [
            ft.Text("Editar máquina", size=20, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text(
                "El código es permanente y no puede modificarse.",
                size=12,
                color=GRIS,
            ),
            ft.Container(height=8),
            ft.Row([codigo, nombre], spacing=12),
            ft.Row([marca, modelo], spacing=12),
            ft.Row([area, ubicacion], spacing=12),
            ft.Row([estado]),
            ft.Container(height=10),
            seccion_criterios,
            ft.Container(height=10),
            ft.Row(
                [
                    ft.TextButton(
                        content=ft.Text("Cancelar", color=TEXTO),
                        on_click=lambda e: page.go(f"/maquinas/{datos['codigo']}"),
                    ),
                    ft.Button(
                        content=ft.Text("Guardar cambios", weight=ft.FontWeight.BOLD, color=TEXTO),
                        bgcolor=NARANJA,
                        on_click=guardar,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=10,
            ),
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    configurar_navbar(page, menu_mas, indice_inicial=1)

    page.add(
        ft.Column(
            [
                crear_header(titulo=f"Editar: {datos['codigo']}"),
                ft.Stack(
                    [
                        ft.Container(content=formulario, padding=20, expand=True),
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
    render()
