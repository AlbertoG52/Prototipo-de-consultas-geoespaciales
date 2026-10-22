"""Valores fijos del dominio: roles, estados y tipos de sesión.

Es el único lugar donde se escriben estos textos. Coinciden con lo que guarda
la base de datos (las migraciones siembran los roles) y con lo que espera el
frontend (Frontend/src/types), así que renombrar uno implica una migración y
regenerar los tipos del frontend (npm run tipos).

Son StrEnum: cada miembro ES un str (Rol.USUARIO == "usuario"), así que se
guardan en la BD, viajan en JSON y se comparan como texto normal, pero el
editor y mypy detectan un nombre mal escrito.
"""

from enum import StrEnum


class NombreRol(StrEnum):
    """Roles de la tabla 'roles' (001_crear_tabla_roles.sql)."""

    USUARIO = "usuario"
    MODERADOR = "moderador"
    SUPERMODERADOR = "supermoderador"


class EstadoCuenta(StrEnum):
    """Columna usuarios.estado (RR_74, RR_75)."""

    ACTIVO = "activo"
    INACTIVO = "inactivo"


class TipoSesion(StrEnum):
    """Quién hace la petición: una cuenta registrada o un visitante (RR_00_11)."""

    USUARIO = "usuario"
    ANONIMO = "anonimo"


class EstadoConsulta(StrEnum):
    """Columna consultas.estado.

    - RESUELTA: trae la respuesta; es la única que cuesta del límite diario.
    - AMBIGUA: trae las candidatas (RR_17); queda pendiente hasta que se elige.
    - SIN_COINCIDENCIAS: no se reconoció ninguna especie.
    - ORIENTACION: no era una consulta que se pudiera procesar (saludo, ayuda,
      otro idioma...); se responde orientando al usuario. El porqué va en
      consultas.motivo (MotivoOrientacion). No cuesta del límite diario.
    """

    RESUELTA = "resuelta"
    AMBIGUA = "ambigua"
    SIN_COINCIDENCIAS = "sin_coincidencias"
    ORIENTACION = "orientacion"


class MotivoOrientacion(StrEnum):
    """Columna consultas.motivo: por qué una consulta terminó en ORIENTACION.

    Los detecta services/preprocesamiento.py, salvo TIPO_NO_PERMITIDO
    (services/permisos.py). Todos menos FUERA_DE_TEMA se detectan antes de
    buscar especies.
    """

    SIN_SENTIDO = "sin_sentido"  # RR_32: "asdfgh", "???", "123"
    IDIOMA = "idioma"  # RR_22: escrita en otro idioma (por ahora, inglés)
    AYUDA = "ayuda"  # RR_40: "¿qué puedo preguntar?"
    SALUDO = "saludo"  # RR_37: "hola", "gracias"
    FUERA_DE_TEMA = "fuera_de_tema"  # RR_37: sin especie ni nada sobre plantas
    TIPO_NO_PERMITIDO = "tipo_no_permitido"  # RR_77: su rol no tiene ese tipo de consulta


class TipoPregunta(StrEnum):
    """Qué pregunta una consulta sobre una especie — RR_41 y RR_29.

    Lo decide services/intencion.py (ver la prioridad allí) y elige el texto de
    la respuesta (services/contexto_especie.py). Se creó en intencion.py y vive
    aquí desde RR_33, porque se guarda en la BD (IntencionConsulta).
    """

    DISTRIBUCION = "distribucion"
    HABITAT = "habitat"  # RR_29
    DESCRIPCION = "descripcion"
    GENERAL = "general"


class RolDeConsulta(StrEnum):
    """Columna permisos_tipo_consulta.rol (019, RR_77): a quién se le configuran
    los tipos de consulta. El supermoderador no está: siempre puede todo."""

    VISITANTE = "visitante"  # sin cuenta (RR_00_11)
    USUARIO = NombreRol.USUARIO.value
    MODERADOR = NombreRol.MODERADOR.value


class IntencionConsulta(StrEnum):
    """Columna tiempos_respuesta.intencion (RR_33): qué quiso hacer el usuario.

    Une los dos casos: una consulta sobre una especie (su TipoPregunta) o un
    mensaje que no es una consulta (su MotivoOrientacion). Los valores son los
    mismos de esos dos enums, salvo TIPO_NO_PERMITIDO (RR_77): de esa consulta
    se registra el tipo que se pidió.
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
    """Columna tiempos_respuesta.resultado (RR_57): cómo terminó una consulta.

    Los cuatro primeros son los de EstadoConsulta; los demás, las consultas que
    terminaron en error.
    """

    RESUELTA = "resuelta"
    AMBIGUA = "ambigua"
    SIN_COINCIDENCIAS = "sin_coincidencias"
    ORIENTACION = "orientacion"
    TIEMPO_AGOTADO = "tiempo_agotado"  # RR_38
    LIMITE_ALCANZADO = "limite_alcanzado"  # límite diario de consultas
    RECHAZADA = "rechazada"  # otro error de la solicitud (4xx)
    ERROR = "error"  # error inesperado o CR-BioLM no disponible


class DatoRespuesta(StrEnum):
    """Los datos de una respuesta cuyo origen se indica (RR_45, Procedencia.dato)."""

    ESPECIE = "especie"  # nombre, familia y nombre común
    TEXTO = "texto"
    ELEVACION = "elevacion"
    REGISTROS = "registros"
    MAPA = "mapa"
