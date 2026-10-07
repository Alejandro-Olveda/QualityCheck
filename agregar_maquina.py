import flet as ft
import estilos

from componentes import (
    aplicar_tema,
    crear_header,
    crear_menu_mas,
    configurar_navbar,
)

from database import SessionLocal
from models import Area, Maquina, CriterioInspeccion


def vista_agregar_maquina(page: ft.Page):
    page.title = "QualityCheck - Agregar máquina"
    page.padding = 0
    page.bgcolor = estilos.COLOR_FONDO
    page.floating_action_button = None

    aplicar_tema(page)
    menu_mas = crear_menu_mas(page)

    def mostrar_mensaje(mensaje):
        snackbar = ft.SnackBar(
            content=ft.Text(mensaje, color="#FFFFFF"),
            bgcolor=estilos.COLOR_TEXTO,
        )
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

    def cancelar(e):
        page.go("/maquinas")

    with SessionLocal() as db:
        lista_areas = db.query(Area).filter(Area.activa == True).all()

    opciones_areas = [
        ft.DropdownOption(key=str(area.id_area), text=area.nombre)
        for area in lista_areas
    ]

    def crear_campo(label, hint):
        return ft.TextField(
            label=label,
            hint_text=hint,
            border_color="#BDBDBD",
            focused_border_color=estilos.COLOR_PRINCIPAL,
            label_style=ft.TextStyle(size=11, color="#5F6670"),
            bgcolor="#FFFFFF",
            color=estilos.COLOR_TEXTO,
            expand=True,
        )

    nombre = crear_campo("Nombre *", "Ej. Torno 04")
    marca = crear_campo("Marca", "Ej. Mazak")
    modelo = crear_campo("Modelo", "Ej. QUICK TURN 250")
    ubicacion = crear_campo("Ubicación", "Ej. Nave 1 - Pasillo B")

    dd_area = ft.Dropdown(
        label="Área *",
        hint_text="Seleccione un área",
        options=opciones_areas,
        border_color="#BDBDBD",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        bgcolor="#FFFFFF",
        color=estilos.COLOR_TEXTO,
        expand=True,
    )

    estado = ft.Dropdown(
        label="Estado",
        value="Operativa",
        options=[
            ft.DropdownOption(key="Operativa", text="Operativa"),
            ft.DropdownOption(key="En revisión", text="En revisión"),
            ft.DropdownOption(key="Fuera de servicio", text="Fuera de servicio"),
        ],
        border_color="#BDBDBD",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        bgcolor="#FFFFFF",
        color=estilos.COLOR_TEXTO,
        expand=True,
    )

    lista_criterios_ui = ft.Column(spacing=6)
    criterios_temporales = []

    txt_nuevo_criterio = ft.TextField(
        label="Nombre del criterio",
        hint_text="Ej. Nivel de aceite hidráulico",
        border_color="#BDBDBD",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        bgcolor="#FFFFFF",
        color=estilos.COLOR_TEXTO,
        expand=True,
    )

    dd_categoria_criterio = ft.Dropdown(
        label="Categoría",
        value="General",
        options=[
            ft.DropdownOption(key="General", text="General"),
            ft.DropdownOption(key="Seguridad", text="Seguridad"),
            ft.DropdownOption(key="Mantenimiento", text="Mantenimiento"),
            ft.DropdownOption(key="Mecánico", text="Mecánico"),
            ft.DropdownOption(key="Eléctrico", text="Eléctrico"),
            ft.DropdownOption(key="Neumático", text="Neumático"),
        ],
        border_color="#BDBDBD",
        focused_border_color=estilos.COLOR_PRINCIPAL,
        bgcolor="#FFFFFF",
        color=estilos.COLOR_TEXTO,
        width=150,
    )

    def renderizar_criterios():
        lista_criterios_ui.controls = [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    criterio["nombre_criterio"],
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=estilos.COLOR_TEXTO,
                                ),
                                ft.Text(
                                    f"Categoría: {criterio['categoria']}",
                                    size=11,
                                    color="#5F6670",
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color="#DC2626",
                            tooltip="Quitar criterio",
                            on_click=lambda _, idx=i: quitar_criterio(idx),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor="#FFFFFF",
                padding=8,
                border_radius=8,
                border=ft.Border(
                    top=ft.BorderSide(1, "#E1E3E6"),
                    bottom=ft.BorderSide(1, "#E1E3E6"),
                    left=ft.BorderSide(1, "#E1E3E6"),
                    right=ft.BorderSide(1, "#E1E3E6"),
                ),
            )
            for i, criterio in enumerate(criterios_temporales)
        ]
        page.update()

    def agregar_criterio(e):
        nombre_criterio = (txt_nuevo_criterio.value or "").strip()
        if not nombre_criterio:
            mostrar_mensaje("Escriba el nombre del criterio.")
            return

        criterios_temporales.append(
            {
                "nombre_criterio": nombre_criterio,
                "categoria": dd_categoria_criterio.value or "General",
            }
        )
        txt_nuevo_criterio.value = ""
        renderizar_criterios()

    def quitar_criterio(index):
        if 0 <= index < len(criterios_temporales):
            criterios_temporales.pop(index)
            renderizar_criterios()

    btn_agregar_criterio = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE,
        icon_color=estilos.COLOR_PRINCIPAL,
        tooltip="Añadir criterio",
        on_click=agregar_criterio,
    )

    seccion_criterios = ft.Column(
        [
            ft.Divider(height=1, color="#E1E3E6"),
            ft.Text(
                "Criterios de Inspección Específicos",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=estilos.COLOR_TEXTO,
            ),
            ft.Text(
                "Define los puntos técnicos que se evaluarán en las revisiones de esta máquina.",
                size=12,
                color="#5F6670",
            ),
            ft.Row(
                [txt_nuevo_criterio, dd_categoria_criterio, btn_agregar_criterio],
                spacing=8,
            ),
            lista_criterios_ui,
        ],
        spacing=8,
    )

    def guardar(e):
        if not nombre.value or not nombre.value.strip() or not dd_area.value:
            mostrar_mensaje("Complete los campos obligatorios (*), incluyendo el área.")
            return

        if not criterios_temporales:
            mostrar_mensaje("Agrega al menos un criterio de inspección.")
            return

        try:
            with SessionLocal() as db:
                ultima_maquina = (
                    db.query(Maquina)
                    .order_by(Maquina.id_maquina.desc())
                    .first()
                )

                siguiente_numero = ultima_maquina.id_maquina + 1 if ultima_maquina else 1
                codigo_generado = f"MAQ-{siguiente_numero:03d}"

                while (
                    db.query(Maquina)
                    .filter(Maquina.codigo_maquina == codigo_generado)
                    .first()
                    is not None
                ):
                    siguiente_numero += 1
                    codigo_generado = f"MAQ-{siguiente_numero:03d}"

                nueva_maquina = Maquina(
                    codigo_maquina=codigo_generado,
                    nombre=nombre.value.strip(),
                    tipo="Industrial",
                    marca=marca.value.strip() if marca.value else None,
                    modelo=modelo.value.strip() if modelo.value else None,
                    ubicacion=ubicacion.value.strip() if ubicacion.value else None,
                    id_area=int(dd_area.value),
                    estado=estado.value or "Operativa",
                    activa=True,
                )

                db.add(nueva_maquina)
                db.flush()

                for criterio in criterios_temporales:
                    db.add(
                        CriterioInspeccion(
                            id_maquina=nueva_maquina.id_maquina,
                            categoria=criterio["categoria"],
                            nombre_criterio=criterio["nombre_criterio"],
                            activo=True,
                        )
                    )

                db.commit()

            mostrar_mensaje(f"Máquina {codigo_generado} registrada correctamente.")
            page.go("/maquinas")

        except Exception as ex:
            mostrar_mensaje(f"Error al guardar: {ex}")

    header = crear_header()

    formulario = ft.Column(
        controls=[
            ft.Text("Nueva máquina", size=20, weight=ft.FontWeight.BOLD, color=estilos.COLOR_TEXTO),
            ft.Text(
                "El código de máquina se generará automáticamente.",
                size=13,
                color="#5F6670",
            ),
            ft.Container(height=12),
            ft.Row([nombre], spacing=12),
            ft.Row([marca, modelo], spacing=12),
            ft.Row([dd_area, ubicacion], spacing=12),
            ft.Row([estado], spacing=12),
            ft.Container(height=16),
            seccion_criterios,
            ft.Container(height=16),
            ft.Row(
                [
                    ft.TextButton(
                        content=ft.Text("Cancelar", color=estilos.COLOR_TEXTO),
                        on_click=cancelar,
                    ),
                    ft.Button(
                        content=ft.Text(
                            "Guardar máquina",
                            color=estilos.COLOR_TEXTO,
                            weight=ft.FontWeight.BOLD,
                        ),
                        bgcolor=estilos.COLOR_PRINCIPAL,
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

    cuerpo = ft.Container(content=formulario, padding=20, expand=True)
    configurar_navbar(page, menu_mas, indice_inicial=1)

    contenido = ft.Stack(
        [
            cuerpo,
            ft.Container(content=menu_mas, right=15, bottom=15),
        ],
        expand=True,
    )

    page.add(
        ft.Column(
            [header, contenido],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )
    )
