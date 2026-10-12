from sqlalchemy import text

from database import engine
from usuarios_login import generar_usuario_base, limpiar_nombre_usuario


def migrar():
    with engine.begin() as conexion:
        conexion.execute(text(
            "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre_usuario VARCHAR(100)"
        ))
        filas = conexion.execute(text(
            "SELECT id_usuario, nombre, nombre_usuario FROM usuarios ORDER BY id_usuario"
        )).mappings().all()
        usados = set()
        cambios = 0
        for fila in filas:
            actual = limpiar_nombre_usuario(fila["nombre_usuario"])
            base = actual or generar_usuario_base(fila["nombre"])
            candidato = base
            numero = 2
            while candidato.casefold() in usados:
                sufijo = str(numero)
                candidato = f"{base[:100 - len(sufijo)]}{sufijo}"
                numero += 1
            usados.add(candidato.casefold())
            if candidato != fila["nombre_usuario"]:
                conexion.execute(text(
                    "UPDATE usuarios SET nombre_usuario=:usuario WHERE id_usuario=:id"
                ), {"usuario": candidato, "id": fila["id_usuario"]})
                cambios += 1
        conexion.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_nombre_usuario_lower "
            "ON usuarios (LOWER(nombre_usuario))"
        ))
        conexion.execute(text(
            "ALTER TABLE usuarios ALTER COLUMN nombre_usuario SET NOT NULL"
        ))
    print(f"Migración completada. Usuarios procesados: {len(filas)}. Actualizados: {cambios}.")
    print("Puedes consultar los nombres de acceso en Usuarios y roles.")


if __name__ == "__main__":
    migrar()
