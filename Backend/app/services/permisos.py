"""Tipos de consulta permitidos por rol — RR_77.

- Criterio 1: el supermoderador define, para el visitante sin cuenta, el
  usuario y el moderador, qué tipos de pregunta (dominio.TipoPregunta:
  distribución, hábitat, descripción, general) pueden hacer. Se guarda en la
  tabla permisos_tipo_consulta (019); al inicio todo está permitido. El
  supermoderador siempre puede todo, para que no pueda bloquearse a sí mismo.
- Criterio 2: services/consultas.py pide `de(db, identidad)` y no busca ni
  responde una consulta de un tipo no permitido. El tipo se revisa con el
  texto antes de buscar especies (no se llama a CR-BioLM) y otra vez con el
  tipo de la respuesta, que puede precisarse con el vocabulario de CR-BioLM
  (RR_29).
- Criterio 3: se responde como orientación, con el motivo TIPO_NO_PERMITIDO y
  `Permisos.mensaje`, que dice qué tipos sí tiene. No descuenta del límite
  diario.

Cada cambio queda en la auditoría (RR_00_09) por un trigger de la BD (019),
con quien lo hizo, como los cambios de rol.

Solo aplica al chat (POST /consultas): la ficha de una especie
(GET /especies/{id}) se sigue viendo completa.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..dominio import NombreRol, RolDeConsulta, TipoPregunta
from ..models import PermisoTipoConsulta, Usuario
from ..schemas.permisos import CambioPermisos, PermisosDeRol, PermisosTiposConsulta
from ..security import Identidad
from ..tiempo import ahora

TODOS = frozenset(TipoPregunta)

# Cómo se nombra cada tipo en los mensajes al usuario.
NOMBRES = {
    TipoPregunta.DISTRIBUCION: "distribución",
    TipoPregunta.HABITAT: "hábitat",
    TipoPregunta.DESCRIPCION: "descripción",
    TipoPregunta.GENERAL: "información general",
}


@dataclass(frozen=True)
class Permisos:
    """Lo que puede consultar una persona. `rol` None: supermoderador, puede todo."""

    rol: RolDeConsulta | None
    permitidos: frozenset[TipoPregunta] = TODOS

    def permite(self, tipo: TipoPregunta) -> bool:
        return tipo in self.permitidos

    def mensaje(self, tipo: TipoPregunta) -> str:
        """Criterio 3: qué tipo no está disponible para su rol y cuáles sí."""
        if self.rol is RolDeConsulta.VISITANTE:
            quien = "Como visitante sin cuenta no tienes habilitadas"
        else:
            quien = f"Tu rol ({self.rol}) no tiene habilitadas"
        aviso = f"{quien} las consultas de {NOMBRES[tipo]}."
        otros = [NOMBRES[t] for t in TipoPregunta if t in self.permitidos]
        if not otros:
            return f"{aviso} Por ahora no tienes habilitado ningún tipo de consulta."
        return f"{aviso} Puedes preguntar por: {_enumerar(otros)}."


def _enumerar(partes: list[str]) -> str:
    """['a', 'b', 'información'] -> 'a, b e información' ("e" antes de "i")."""
    if len(partes) == 1:
        return partes[0]
    union = "e" if partes[-1][0] in "ií" else "y"
    return f"{', '.join(partes[:-1])} {union} {partes[-1]}"


def rol_de(identidad: Identidad) -> RolDeConsulta | None:
    """El rol que se configura para esta persona; None si es supermoderador."""
    usuario = identidad.usuario
    if usuario is None:
        return RolDeConsulta.VISITANTE
    nombre = usuario.rol.nombre if usuario.rol else NombreRol.USUARIO
    if nombre == NombreRol.SUPERMODERADOR:
        return None
    return RolDeConsulta(nombre)


def de(db: Session, identidad: Identidad) -> Permisos:
    """Criterio 2: lo que puede consultar esta persona, leído en cada consulta.

    Un tipo sin fila en la tabla (no debería pasar: la siembra la migración
    019) se considera permitido, como antes de este requerimiento.
    """
    rol = rol_de(identidad)
    if rol is None:
        return Permisos(rol=None)
    bloqueados = (
        db.query(PermisoTipoConsulta.tipo)
        .filter(PermisoTipoConsulta.rol == rol, PermisoTipoConsulta.permitido.is_(False))
        .tuples()
        .all()
    )
    return Permisos(rol=rol, permitidos=TODOS - {TipoPregunta(t) for (t,) in bloqueados})


def ver(db: Session) -> PermisosTiposConsulta:
    """Criterio 1: la configuración de cada rol y quién la cambió por última vez."""
    filas = db.query(PermisoTipoConsulta).all()
    bloqueados = {(f.rol, f.tipo) for f in filas if not f.permitido}
    roles = [
        PermisosDeRol(rol=rol, permitidos=[t for t in TipoPregunta if (rol, t) not in bloqueados])
        for rol in RolDeConsulta
    ]
    cambiadas = [f for f in filas if f.actualizado_por is not None]
    if not cambiadas:
        return PermisosTiposConsulta(roles=roles)
    ultima = max(cambiadas, key=lambda f: f.actualizado_en)
    autor = db.get(Usuario, ultima.actualizado_por)
    return PermisosTiposConsulta(
        roles=roles,
        actualizado_en=ultima.actualizado_en,
        actualizado_por=autor.correo if autor else None,
    )


def cambiar(db: Session, actor: Usuario, datos: CambioPermisos) -> PermisosTiposConsulta:
    """Criterio 1: deja permitidos solo los tipos que vienen para cada rol enviado.

    Aplica desde la siguiente consulta. Solo se escriben las filas que
    cambian, así la auditoría registra un cambio real por fila.
    """
    # El trigger de auditoría (019) lee quién actúa, como en services/admin.py.
    db.execute(text("SELECT set_config('app.actor_id', :id, true)"), {"id": str(actor.id)})
    filas = {(f.rol, f.tipo): f for f in db.query(PermisoTipoConsulta).all()}
    momento = ahora()
    for cambio in datos.roles:
        for tipo in TipoPregunta:
            permitido = tipo in cambio.permitidos
            fila = filas.get((cambio.rol, tipo))
            if fila is None:
                fila = PermisoTipoConsulta(rol=cambio.rol, tipo=tipo)
                db.add(fila)
            elif fila.permitido == permitido:
                continue
            fila.permitido = permitido
            fila.actualizado_en = momento
            fila.actualizado_por = actor.id
    db.commit()
    return ver(db)
