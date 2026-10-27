from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(150), unique=True, nullable=False, index=True)
    nombre_usuario = Column(String(100), nullable=False)
    contrasena_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    roles = relationship(
        "usuarioRol",
        back_populates="usuario",
        cascade="all, delete-orphan",
    )


class rol(Base):
    __tablename__ = "roles"

    id_rol = Column(Integer, primary_key=True, index=True)
    nombre_rol = Column(String(50), nullable=False, unique=True)
    descripcion = Column(String(255))

    usuarios = relationship(
        "usuarioRol",
        back_populates="rol",
        cascade="all, delete-orphan",
    )


class usuarioRol(Base):
    __tablename__ = "usuario_roles"

    id_usuario_rol = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=False,
    )
    id_rol = Column(
        Integer,
        ForeignKey("roles.id_rol"),
        nullable=False,
    )

    usuario = relationship("Usuario", back_populates="roles")
    rol = relationship("rol", back_populates="usuarios")


class Area(Base):
    __tablename__ = "areas"

    id_area = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(String(255))
    activa = Column(Boolean, default=True)

    maquinas = relationship("Maquina", back_populates="area_rel")


class Maquina(Base):
    __tablename__ = "maquinas"

    id_maquina = Column(Integer, primary_key=True, index=True)
    id_area = Column(
        Integer,
        ForeignKey("areas.id_area"),
        nullable=False,
    )
    codigo_maquina = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    nombre = Column(String(150), nullable=False)
    tipo = Column(String(100), nullable=False)
    marca = Column(String(100))
    modelo = Column(String(100))
    numero_serie = Column(String(100), unique=True)
    ubicacion = Column(String(150))
    estado = Column(String(50), default="Operativa", index=True)
    activa = Column(Boolean, default=True)

    area_rel = relationship("Area", back_populates="maquinas")
    criterios = relationship(
        "CriterioInspeccion",
        back_populates="maquina",
    )


class CriterioInspeccion(Base):
    __tablename__ = "criterios_inspeccion"

    id_criterio = Column(Integer, primary_key=True, index=True)
    id_maquina = Column(
        Integer,
        ForeignKey("maquinas.id_maquina"),
        nullable=False,
    )
    categoria = Column(String(100), nullable=False)
    nombre_criterio = Column(String(150), nullable=False)

    # Se conserva "description" porque el backend actual usa c.description.
    description = Column(Text)
    activo = Column(Boolean, default=True)

    maquina = relationship(
        "Maquina",
        back_populates="criterios",
    )


class Inspeccion(Base):
    __tablename__ = "revisiones"

    id_inspeccion = Column(Integer, primary_key=True, index=True)
    codigo_inspeccion = Column(
        String(50),
        unique=True,
        nullable=False,
    )
    id_maquina = Column(
        Integer,
        ForeignKey("maquinas.id_maquina"),
        nullable=False,
    )
    id_inspector = Column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=False,
    )
    tipo_inspeccion = Column(String(50), nullable=False)
    fecha_inspeccion = Column(DateTime, default=datetime.utcnow)
    resultado_final = Column(String(50))
    observaciones_generales = Column(String(500))

    # Estado actual de la revisión sin perder el resultado histórico original.
    estado_revision = Column(
        String(30),
        nullable=False,
        default="Abierta",
    )

    # Si esta revisión es una correctiva, apunta a la revisión que originó el problema.
    id_revision_origen = Column(
        Integer,
        ForeignKey("revisiones.id_inspeccion"),
        nullable=True,
    )

    maquina = relationship("Maquina")
    inspector = relationship("Usuario")

    hallazgos = relationship(
        "Hallazgo",
        back_populates="inspeccion",
    )

    revision_origen = relationship(
        "Inspeccion",
        remote_side=[id_inspeccion],
        foreign_keys=[id_revision_origen],
    )


class Hallazgo(Base):
    __tablename__ = "hallazgos"

    id_hallazgo = Column(Integer, primary_key=True, index=True)
    id_inspeccion = Column(
        Integer,
        ForeignKey("revisiones.id_inspeccion"),
        nullable=False,
    )
    id_criterio = Column(
        Integer,
        ForeignKey("criterios_inspeccion.id_criterio"),
        nullable=False,
    )
    descripcion = Column(String(500), nullable=False)
    estado = Column(String(50), default="Abierto")

    inspeccion = relationship(
        "Inspeccion",
        back_populates="hallazgos",
    )
    criterio = relationship("CriterioInspeccion")
    acciones = relationship(
        "AccionCorrectiva",
        back_populates="hallazgo",
    )


class AccionCorrectiva(Base):
    __tablename__ = "acciones_correctivas"

    id_accion = Column(Integer, primary_key=True, index=True)
    id_hallazgo = Column(
        Integer,
        ForeignKey("hallazgos.id_hallazgo"),
        nullable=False,
    )

    descripcion_accion = Column(String(500), nullable=False)

    # Se conserva por compatibilidad/historial con registros anteriores.
    responsable = Column(String(150), nullable=False)

    fecha_compromiso = Column(DateTime, nullable=False)
    completada = Column(Boolean, default=False)

    # Técnico asignado actualmente.
    id_responsable = Column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=True,
    )

    # Inspector/Admin que hizo la asignación.
    id_asignado_por = Column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=True,
    )

    estado = Column(
        String(30),
        nullable=False,
        default="Asignada",
    )

    fecha_realizada = Column(DateTime)
    observaciones_tecnico = Column(Text)

    # Inspector/Admin que verificó el trabajo.
    id_verificador = Column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=True,
    )
    fecha_verificacion = Column(DateTime)
    observaciones_verificacion = Column(Text)

    hallazgo = relationship(
        "Hallazgo",
        back_populates="acciones",
    )
    tecnico = relationship(
        "Usuario",
        foreign_keys=[id_responsable],
    )
    asignado_por = relationship(
        "Usuario",
        foreign_keys=[id_asignado_por],
    )
    verificador = relationship(
        "Usuario",
        foreign_keys=[id_verificador],
    )


class ResultadoInspeccion(Base):
    __tablename__ = "resultados_inspeccion"

    id_resultado = Column(Integer, primary_key=True)
    id_inspeccion = Column(
        Integer,
        ForeignKey("revisiones.id_inspeccion"),
        nullable=False,
    )
    id_criterio = Column(
        Integer,
        ForeignKey("criterios_inspeccion.id_criterio"),
        nullable=False,
    )
    valor_medido = Column(String(150))
    valor_esperado = Column(String(150))
    cumple = Column(Boolean, nullable=False)
    observacion = Column(Text)

    inspeccion = relationship("Inspeccion")
    criterio = relationship("CriterioInspeccion")


class RevisionProgramada(Base):
    __tablename__ = "revisiones_programadas"

    id_programacion = Column(Integer, primary_key=True)
    id_maquina = Column(
        Integer,
        ForeignKey("maquinas.id_maquina"),
        nullable=False,
    )
    id_responsable = Column(
        Integer,
        ForeignKey("usuarios.id_usuario"),
        nullable=False,
    )
    fecha_programada = Column(Date, nullable=False)
    descripcion = Column(Text, nullable=False)
    estado = Column(
        String(30),
        nullable=False,
        default="Programada",
    )
    observaciones = Column(Text)

    # Se llena cuando la preventiva programada ya produjo una revisión real.
    id_inspeccion = Column(
        Integer,
        ForeignKey("revisiones.id_inspeccion"),
        unique=True,
        nullable=True,
    )

    creado_en = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    maquina = relationship("Maquina")
    responsable = relationship("Usuario")
    inspeccion = relationship("Inspeccion")
