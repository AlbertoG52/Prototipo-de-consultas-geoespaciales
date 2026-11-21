"""Valores fijos del dominio: roles, estados y tipos de sesión.

Coinciden con lo que guarda la base de datos y con los tipos del frontend; renombrar uno
exige una migración y regenerar los tipos (npm run tipos). Son StrEnum: se guardan y viajan
como texto, pero mypy detecta un nombre mal escrito.
"""

from enum import StrEnum


class NombreRol(StrEnum):
    """Roles de la tabla 'roles' (001_crear_tabla_roles.sql)."""

    USUARIO = "usuario"
    MODERADOR = "moderador"
    SUPERMODERADOR = "supermoderador"


class PeriodoConsultas(StrEnum):
    """Cada cuánto se restablece el contador de consultas de un rol. Los periodos empiezan a
    las 00:00 de Costa Rica; la semana, el lunes; el mes, el día 1.
    """

    DIA = "dia"
    SEMANA = "semana"
    MES = "mes"


class EstadoCuenta(StrEnum):
    """Estado de una cuenta (usuarios.estado)."""

    ACTIVO = "activo"
    INACTIVO = "inactivo"


class TipoSesion(StrEnum):
    """Quién hace la petición: una cuenta registrada o un visitante."""

    USUARIO = "usuario"
    ANONIMO = "anonimo"


class EstadoConsulta(StrEnum):
    """Estado de una consulta (consultas.estado).

    - RESUELTA: trae la respuesta; es la única que cuenta para el límite.
    - AMBIGUA: trae las candidatas y queda pendiente hasta que se elige una.
    - SIN_COINCIDENCIAS: no se reconoció ninguna especie.
    - ORIENTACION: no era una consulta procesable (saludo, ayuda, otro idioma...); el
      motivo va en consultas.motivo.
    """

    RESUELTA = "resuelta"
    AMBIGUA = "ambigua"
    SIN_COINCIDENCIAS = "sin_coincidencias"
    ORIENTACION = "orientacion"


class MotivoOrientacion(StrEnum):
    """Por qué una consulta terminó en ORIENTACION (consultas.motivo).

    Los detecta services/preprocesamiento.py, salvo TIPO_NO_PERMITIDO
    (services/permisos.py).
    """

    SIN_SENTIDO = "sin_sentido"  # "asdfgh", "???", "123"
    IDIOMA = "idioma"  # escrita en otro idioma (por ahora, inglés)
    AYUDA = "ayuda"  # "¿qué puedo preguntar?"
    SALUDO = "saludo"  # "hola", "gracias"
    FUERA_DE_TEMA = "fuera_de_tema"  # sin especie ni nada sobre plantas
    TIPO_NO_PERMITIDO = "tipo_no_permitido"  # su rol no tiene ese tipo de consulta


class TipoPregunta(StrEnum):
    """Qué pregunta una consulta sobre una especie.

    Lo decide services/intencion.py y define qué texto se responde
    (services/contexto_especie.py).
    """

    DISTRIBUCION = "distribucion"
    HABITAT = "habitat"
    DESCRIPCION = "descripcion"
    GENERAL = "general"


class RolDeConsulta(StrEnum):
    """Roles a los que se les configuran los tipos de consulta. El supermoderador siempre
    puede todo.
    """

    VISITANTE = "visitante"  # sin cuenta
    USUARIO = NombreRol.USUARIO.value
    MODERADOR = NombreRol.MODERADOR.value


class GrupoDeUso(StrEnum):
    """Grupo de las estadísticas de uso: el rol actual de la cuenta, o visitante."""

    VISITANTE = "visitante"
    USUARIO = NombreRol.USUARIO.value
    MODERADOR = NombreRol.MODERADOR.value
    SUPERMODERADOR = NombreRol.SUPERMODERADOR.value


class PeriodoEstadisticas(StrEnum):
    """Periodo de las estadísticas de uso. Los días son en UTC."""

    HOY = "hoy"
    ULTIMOS_7_DIAS = "ultimos_7_dias"  # hoy y los 6 días anteriores
    ULTIMOS_30_DIAS = "ultimos_30_dias"  # hoy y los 29 días anteriores
    TODO = "todo"


class IntencionConsulta(StrEnum):
    """Qué quiso hacer el usuario (tiempos_respuesta.intencion).

    Es el TipoPregunta de una consulta sobre una especie o el MotivoOrientacion de un
    mensaje que no es una consulta. De una consulta no permitida se registra el tipo que se
    pidió.
    """

    DISTRIBUCION = TipoPregunta.DISTRIBUCION.value
    HABITAT = TipoPregunta.HABITAT.value
    DESCRIPCION = TipoPregunta.DESCRIPCION.value
    GENERAL = TipoPregunta.GENERAL.value
    SIN_SENTIDO = MotivoOrientacion.SIN_SENTIDO.value
    IDIOMA = MotivoOrientacion.IDIOMA.value
    AYUDA = MotivoOrientacion.AYUDA.value
    SALUDO = MotivoOrientacion.SALUDO.value
    FUERA_DE_TEMA = MotivoOrientacion.FUERA_DE_TEMA.value


class ResultadoConsulta(StrEnum):
    """Cómo terminó una consulta (tiempos_respuesta.resultado).

    Los cuatro primeros son los de EstadoConsulta; los demás, errores.
    """

    RESUELTA = "resuelta"
    AMBIGUA = "ambigua"
    SIN_COINCIDENCIAS = "sin_coincidencias"
    ORIENTACION = "orientacion"
    TIEMPO_AGOTADO = "tiempo_agotado"
    LIMITE_ALCANZADO = "limite_alcanzado"  # límite diario de consultas
    RECHAZADA = "rechazada"  # otro error de la solicitud (4xx)
    ERROR = "error"  # error inesperado o CR-BioLM no disponible


class DatoRespuesta(StrEnum):
    """Datos de una respuesta cuyo origen se indica (Procedencia.dato)."""

    ESPECIE = "especie"  # nombre, familia y nombre común
    TEXTO = "texto"
    ELEVACION = "elevacion"
    REGISTROS = "registros"
    MAPA = "mapa"
