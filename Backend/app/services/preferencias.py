"""Si una respuesta incluye el mapa y las fuentes.

- El supermoderador define el comportamiento por defecto (tabla configuracion_respuestas,
  una sola fila). Aplica a todos los que no lo han cambiado.
- Un moderador o supermoderador puede cambiar el suyo; se guarda en su cuenta. NULL = usa
  el del sistema.

`aplicar` quita de la respuesta lo que se excluye. consultas.py la llama antes de guardar,
así la conversación reabierta muestra lo mismo que se respondió.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..dominio import DatoRespuesta, NombreRol
from ..models import ConfiguracionRespuestas, Usuario
from ..models.configuracion_respuestas import FILA_UNICA
from ..schemas.consulta import RespuestaConsulta
from ..schemas.preferencias import (
    CambioPreferencias,
    CambioPreferenciasPorDefecto,
    PreferenciasModerador,
    PreferenciasPorDefecto,
    PreferenciasRespuesta,
)
from ..tiempo import ahora

# Roles que pueden tener preferencias propias.
ROLES_CON_PREFERENCIAS = frozenset({NombreRol.MODERADOR, NombreRol.SUPERMODERADOR})

# Citas del Manual dentro del texto redactado por el LLM: "…en Talamanca【Quercus
# costaricensis (Tomo V, p.779)】." Son fuentes, así que se quitan con ellas.
_CITA_EN_EL_TEXTO = re.compile(r"\s*【[^】]*】")


@dataclass(frozen=True)
class Preferencias:
    incluir_mapa: bool = True
    incluir_fuentes: bool = True

    def a_esquema(self) -> PreferenciasRespuesta:
        return PreferenciasRespuesta(
            incluir_mapa=self.incluir_mapa, incluir_fuentes=self.incluir_fuentes
        )


# --- comportamiento por defecto del sistema ---------------------------------


def _configuracion(db: Session) -> ConfiguracionRespuestas | None:
    return db.get(ConfiguracionRespuestas, FILA_UNICA)


def por_defecto(db: Session) -> Preferencias:
    """Comportamiento por defecto. Sin la fila se incluye todo."""
    fila = _configuracion(db)
    if fila is None:
        return Preferencias()
    return Preferencias(incluir_mapa=fila.incluir_mapa, incluir_fuentes=fila.incluir_fuentes)


def ver_por_defecto(db: Session) -> PreferenciasPorDefecto:
    fila = _configuracion(db)
    if fila is None:
        return PreferenciasPorDefecto(incluir_mapa=True, incluir_fuentes=True)
    autor = db.get(Usuario, fila.actualizado_por) if fila.actualizado_por else None
    return PreferenciasPorDefecto(
        incluir_mapa=fila.incluir_mapa,
        incluir_fuentes=fila.incluir_fuentes,
        actualizado_en=fila.actualizado_en,
        actualizado_por=autor.correo if autor else None,
    )


def cambiar_por_defecto(
    db: Session, actor: Usuario, datos: CambioPreferenciasPorDefecto
) -> PreferenciasPorDefecto:
    """Cambia el comportamiento por defecto. Aplica desde la siguiente consulta de quienes no
    tienen preferencia propia.
    """
    fila = _configuracion(db)
    if fila is None:
        fila = ConfiguracionRespuestas(id=FILA_UNICA)
        db.add(fila)
    fila.incluir_mapa = datos.incluir_mapa
    fila.incluir_fuentes = datos.incluir_fuentes
    fila.actualizado_en = ahora()
    fila.actualizado_por = actor.id
    db.commit()
    return ver_por_defecto(db)


# --- preferencias de cada moderador -----------------------------------------


def puede_personalizar(usuario: Usuario | None) -> bool:
    return (
        usuario is not None
        and usuario.rol is not None
        and (usuario.rol.nombre in ROLES_CON_PREFERENCIAS)
    )


def de(db: Session, usuario: Usuario | None) -> Preferencias:
    """Preferencias que aplican a las respuestas de esta persona: las propias del moderador
    donde las haya cambiado y, en lo demás, las del sistema. Un usuario o un visitante
    siempre recibe las del sistema.
    """
    sistema = por_defecto(db)
    if usuario is None or not puede_personalizar(usuario):
        return sistema
    return Preferencias(
        incluir_mapa=sistema.incluir_mapa if usuario.incluir_mapa is None else usuario.incluir_mapa,
        incluir_fuentes=(
            sistema.incluir_fuentes if usuario.incluir_fuentes is None else usuario.incluir_fuentes
        ),
    )


def ver_del_moderador(db: Session, usuario: Usuario) -> PreferenciasModerador:
    efectivas = de(db, usuario)
    return PreferenciasModerador(
        incluir_mapa=efectivas.incluir_mapa,
        incluir_fuentes=efectivas.incluir_fuentes,
        mapa_propio=usuario.incluir_mapa is not None,
        fuentes_propio=usuario.incluir_fuentes is not None,
        por_defecto=por_defecto(db).a_esquema(),
    )


def cambiar_del_moderador(
    db: Session, usuario: Usuario, datos: CambioPreferencias
) -> PreferenciasModerador:
    """Solo cambia los campos que vienen; null vuelve a la del sistema."""
    enviados = datos.model_fields_set
    if "incluir_mapa" in enviados:
        usuario.incluir_mapa = datos.incluir_mapa
    if "incluir_fuentes" in enviados:
        usuario.incluir_fuentes = datos.incluir_fuentes
    db.commit()
    db.refresh(usuario)
    return ver_del_moderador(db, usuario)


# --- aplicar a una respuesta -------------------------------------------------


def quitar_citas(texto: str) -> str:
    return _CITA_EN_EL_TEXTO.sub("", texto)


def aplicar(respuesta: RespuestaConsulta, preferencias: Preferencias) -> RespuestaConsulta:
    """La respuesta sin lo que excluyen las preferencias.

    - Sin mapa: `mapa` = None y sin la procedencia del mapa.
    - Sin fuentes: sin la lista de fuentes, sin la procedencia de cada dato y sin las citas
      del Manual dentro del texto.

    El resto (texto, elevación, registros, avisos) no cambia.
    """
    cambios: dict = {}
    procedencia = respuesta.procedencia
    if not preferencias.incluir_mapa:
        cambios["mapa"] = None
        procedencia = [p for p in procedencia if p.dato != DatoRespuesta.MAPA]
    if not preferencias.incluir_fuentes:
        cambios["fuentes"] = []
        cambios["texto"] = quitar_citas(respuesta.texto)
        procedencia = []
    if not cambios:
        return respuesta
    cambios["procedencia"] = procedencia
    return respuesta.model_copy(update=cambios)
