# Define cómo se guardan los datos en PostgreSQL
import enum

from sqlalchemy import Column, Integer, String, Enum
from database import Base


class TipoUsuario(str, enum.Enum):
    CLIENTE = "CLIENTE"
    PROPIETARIO = "PROPIETARIO"
    SUPERADMIN = "SUPERADMIN"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    puntos = Column(Integer, default=0)

    tipo_usuario = Column(
        Enum(TipoUsuario),
        nullable=False,
        default=TipoUsuario.CLIENTE
    )