"""Pruebas de RR_78 — estadísticas de uso del sistema (services/estadisticas.py).

La BD del contenedor ya tiene consultas, así que las del servicio comparan
antes y después de agregar las suyas. Corren en la sesión `sesion` de
conftest.py, que se deshace al final: no dejan datos. Las de la API solo leen,
con una cuenta que `correos_de_prueba` borra al terminar. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy.orm import Session

from app.dominio import (
    EstadoConsulta,
    GrupoDeUso,
    IntencionConsulta,
    MotivoOrientacion,
    NombreRol,
    PeriodoEstadisticas,
    ResultadoConsulta,
    TipoPregunta,
    TipoSesion,
)
from app.models import Consulta, Conversacion, Rol, TiempoRespuesta, Usuario
from app.services import admin, estadisticas
from app.services.estadisticas import Conteo
from app.tiempo import ahora

from apoyo import api, crear_cuenta_verificada, crear_usuario, iniciar_sesion

PASSWORD = "Clave#2024"


def _consulta(db: Session, usuario: Usuario, estado: EstadoConsulta, hace_dias: int = 0) -> None:
    """Guarda una consulta de `usuario` hecha hace `hace_dias` días."""
    conversacion = Conversacion(usuario_id=usuario.id, titulo="Estadísticas")
    db.add(conversacion)
    db.flush()
    momento = ahora() - timedelta(days=hace_dias)
    db.add(
        Consulta(
            usuario_id=usuario.id,
            conversacion_id=conversacion.id,
            texto="consulta de prueba",
            estado=estado,
            motivo=MotivoOrientacion.SALUDO if estado == EstadoConsulta.ORIENTACION else None,
            realizada_en=momento,
            resuelta_en=momento if estado == EstadoConsulta.RESUELTA else None,
        )
    )
    db.flush()


def _tiempo(
    db: Session,
    resultado: ResultadoConsulta,
    tipo_sesion: TipoSesion = TipoSesion.ANONIMO,
    intencion: IntencionConsulta | None = None,
    hace_dias: int = 0,
) -> None:
    """Registra una consulta en tiempos_respuesta, como hace services/tiempos.py."""
    db.add(
        TiempoRespuesta(
            duracion_ms=1,
            resultado=resultado,
            tipo_sesion=tipo_sesion,
            intencion=intencion,
            registrada_en=ahora() - timedelta(days=hace_dias),
        )
    )
    db.flush()


def _diferencia(antes: dict[GrupoDeUso, Conteo], despues: dict[GrupoDeUso, Conteo]) -> dict:
    return {
        g: (despues[g].consultas - antes[g].consultas, despues[g].resueltas - antes[g].resueltas)
        for g in GrupoDeUso
    }


def _total(db: Session, periodo: PeriodoEstadisticas) -> int:
    return estadisticas.estadisticas(db, periodo).total


# --- sin BD ----------------------------------------------------------------------------


def test_la_tasa_de_exito_es_resueltas_entre_consultas():
    assert Conteo(4, 1).tasa_exito == 0.25
    assert Conteo().tasa_exito is None  # sin consultas no hay tasa
    assert Conteo(1, 1) + Conteo(2, 0) == Conteo(3, 1)


def test_cada_periodo_empieza_a_medianoche_utc():
    hoy = datetime.combine(ahora().date(), time.min, tzinfo=UTC)
    assert estadisticas.desde_de(PeriodoEstadisticas.HOY) == hoy
    assert estadisticas.desde_de(PeriodoEstadisticas.ULTIMOS_7_DIAS) == hoy - timedelta(days=6)
    assert estadisticas.desde_de(PeriodoEstadisticas.ULTIMOS_30_DIAS) == hoy - timedelta(days=29)
    assert estadisticas.desde_de(PeriodoEstadisticas.TODO) is None


# --- criterios 1 y 2: qué se cuenta y cómo se agrupa -----------------------------------


def test_las_cuentas_cuentan_todo_menos_las_orientaciones(sesion):
    antes = estadisticas.por_grupo(sesion, None)
    usuario = crear_usuario(sesion, "usuario.estadisticas@example.com")
    for estado in EstadoConsulta:
        _consulta(sesion, usuario, estado)

    cambio = _diferencia(antes, estadisticas.por_grupo(sesion, None))

    # resuelta, ambigua y sin coincidencias; de ellas, una resuelta.
    assert cambio[GrupoDeUso.USUARIO] == (3, 1)


def test_cada_cuenta_cuenta_con_su_rol_de_hoy(sesion):
    usuario = crear_usuario(sesion, "ascendido.estadisticas@example.com")
    _consulta(sesion, usuario, EstadoConsulta.RESUELTA)
    _consulta(sesion, usuario, EstadoConsulta.SIN_COINCIDENCIAS)
    antes = estadisticas.por_grupo(sesion, None)

    usuario.rol_id = sesion.query(Rol.id).filter(Rol.nombre == NombreRol.MODERADOR).scalar()
    sesion.flush()

    cambio = _diferencia(antes, estadisticas.por_grupo(sesion, None))
    assert cambio[GrupoDeUso.USUARIO] == (-2, -1)
    assert cambio[GrupoDeUso.MODERADOR] == (2, 1)


def test_los_visitantes_se_cuentan_desde_los_tiempos_de_respuesta(sesion):
    antes = estadisticas.por_grupo(sesion, None)
    for resultado in ResultadoConsulta:
        _tiempo(sesion, resultado)
    _tiempo(sesion, ResultadoConsulta.RESUELTA, tipo_sesion=TipoSesion.USUARIO)  # no es visitante

    cambio = _diferencia(antes, estadisticas.por_grupo(sesion, None))

    # Solo resuelta y sin coincidencias: una ambigua cuenta cuando se resuelve.
    assert cambio[GrupoDeUso.VISITANTE] == (2, 1)
    assert cambio[GrupoDeUso.USUARIO] == (0, 0)


def test_el_total_suma_todos_los_grupos(sesion):
    datos = estadisticas.estadisticas(sesion, PeriodoEstadisticas.TODO)
    assert [g.grupo for g in datos.por_grupo] == list(GrupoDeUso)
    assert datos.total == sum(g.consultas for g in datos.por_grupo)
    assert datos.resueltas == sum(g.resueltas for g in datos.por_grupo)
    if datos.total:
        assert datos.tasa_exito == datos.resueltas / datos.total


def test_las_cuentas_coinciden_con_el_uso_por_rol(sesion):
    # Misma regla que RR_76, así los números del panel no se contradicen.
    usuario = crear_usuario(sesion, "coincide.estadisticas@example.com")
    _consulta(sesion, usuario, EstadoConsulta.AMBIGUA)
    grupos = estadisticas.por_grupo(sesion, None)
    for uso in admin.uso_por_rol(sesion):
        assert grupos[GrupoDeUso(uso.rol)].consultas == uso.consultas


# --- criterio 3 y periodos --------------------------------------------------------------


def test_una_consulta_nueva_aparece_en_la_siguiente_peticion(sesion):
    antes = _total(sesion, PeriodoEstadisticas.HOY)
    _tiempo(sesion, ResultadoConsulta.RESUELTA)
    assert _total(sesion, PeriodoEstadisticas.HOY) == antes + 1


def test_cada_periodo_cuenta_solo_lo_suyo(sesion):
    antes = {p: _total(sesion, p) for p in PeriodoEstadisticas}
    usuario = crear_usuario(sesion, "periodo.estadisticas@example.com")
    _consulta(sesion, usuario, EstadoConsulta.RESUELTA, hace_dias=10)
    _tiempo(sesion, ResultadoConsulta.RESUELTA, hace_dias=10)

    cambio = {p: _total(sesion, p) - antes[p] for p in PeriodoEstadisticas}
    assert cambio == {
        PeriodoEstadisticas.HOY: 0,
        PeriodoEstadisticas.ULTIMOS_7_DIAS: 0,
        PeriodoEstadisticas.ULTIMOS_30_DIAS: 2,
        PeriodoEstadisticas.TODO: 2,
    }


def test_las_consultas_por_dia_son_los_ultimos_siete(sesion):
    antes = estadisticas.estadisticas(sesion, PeriodoEstadisticas.TODO).por_dia
    usuario = crear_usuario(sesion, "dias.estadisticas@example.com")
    _consulta(sesion, usuario, EstadoConsulta.RESUELTA)
    _tiempo(sesion, ResultadoConsulta.SIN_COINCIDENCIAS, hace_dias=3)

    despues = estadisticas.estadisticas(sesion, PeriodoEstadisticas.TODO).por_dia
    hoy = ahora().date()
    assert [d.fecha for d in despues] == [hoy - timedelta(days=d) for d in range(6, -1, -1)]
    cambio = [d.consultas - a.consultas for a, d in zip(antes, despues, strict=True)]
    assert cambio == [0, 0, 0, 1, 0, 0, 1]


def test_los_tipos_de_consulta_salen_de_la_intencion_registrada(sesion):
    def por_tipo() -> dict[TipoPregunta, int]:
        datos = estadisticas.estadisticas(sesion, PeriodoEstadisticas.TODO)
        return {t.tipo: t.consultas for t in datos.por_tipo}

    antes = por_tipo()
    _tiempo(sesion, ResultadoConsulta.RESUELTA, intencion=IntencionConsulta.DESCRIPCION)
    _tiempo(sesion, ResultadoConsulta.AMBIGUA, intencion=IntencionConsulta.HABITAT)
    _tiempo(sesion, ResultadoConsulta.ORIENTACION, intencion=IntencionConsulta.SALUDO)

    despues = por_tipo()
    assert list(despues) == list(TipoPregunta)
    assert {t: despues[t] - antes[t] for t in TipoPregunta} == {
        TipoPregunta.DISTRIBUCION: 0,
        TipoPregunta.HABITAT: 0,  # la ambigua cuenta cuando se resuelve
        TipoPregunta.DESCRIPCION: 1,
        TipoPregunta.GENERAL: 0,
    }


# --- tarjetas del panel --------------------------------------------------------------------


def test_el_resumen_cuenta_cuentas_hoy_ayer_y_30_dias(sesion):
    antes = estadisticas.resumen(sesion)
    usuario = crear_usuario(sesion, "resumen.estadisticas@example.com")
    _consulta(sesion, usuario, EstadoConsulta.RESUELTA)
    _consulta(sesion, usuario, EstadoConsulta.SIN_COINCIDENCIAS, hace_dias=1)

    despues = estadisticas.resumen(sesion)
    assert despues.usuarios - antes.usuarios == 1
    assert despues.usuarios_nuevos_30_dias - antes.usuarios_nuevos_30_dias == 1
    assert despues.consultas_hoy - antes.consultas_hoy == 1
    assert despues.consultas_ayer - antes.consultas_ayer == 1
    assert despues.consultas_30_dias - antes.consultas_30_dias == 2


# --- por la API ------------------------------------------------------------------------------


@pytest.fixture
def supermoderador(correos_de_prueba):
    correo = correos_de_prueba("super")
    crear_cuenta_verificada(correo, PASSWORD, NombreRol.SUPERMODERADOR)
    return iniciar_sesion(correo, PASSWORD)


def test_el_supermoderador_ve_las_estadisticas(supermoderador):
    datos = api.get("/admin/estadisticas", headers=supermoderador).json()
    assert datos["periodo"] == PeriodoEstadisticas.TODO  # por defecto
    assert datos["desde"] is None
    assert [g["grupo"] for g in datos["por_grupo"]] == list(GrupoDeUso)

    hoy = api.get("/admin/estadisticas?periodo=hoy", headers=supermoderador).json()
    assert hoy["periodo"] == PeriodoEstadisticas.HOY
    assert hoy["total"] <= datos["total"]


def test_el_resumen_por_la_api(supermoderador):
    datos = api.get("/admin/estadisticas/resumen", headers=supermoderador).json()
    assert datos["usuarios"] >= 1  # al menos el supermoderador de la prueba


def test_un_periodo_desconocido_se_rechaza(supermoderador):
    salida = api.get("/admin/estadisticas?periodo=semana", headers=supermoderador)
    assert salida.status_code == 422


def test_solo_el_supermoderador_ve_las_estadisticas(correos_de_prueba):
    correo = correos_de_prueba("usuario")
    crear_cuenta_verificada(correo, PASSWORD)
    cabeceras = iniciar_sesion(correo, PASSWORD)
    assert api.get("/admin/estadisticas", headers=cabeceras).status_code == 403
    assert api.get("/admin/estadisticas/resumen", headers=cabeceras).status_code == 403
