"""Pruebas de RR_67, RR_68, RR_79 y RR_80 — mapa y fuentes en las respuestas.

Las primeras no necesitan base de datos: prueban `preferencias.aplicar` y
`preferencias.de` con respuestas y usuarios en memoria. Las de la API usan la
BD del contenedor; cada una crea sus cuentas y las borra al terminar, y las
que cambian el comportamiento por defecto lo devuelven a como estaba.
Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from pydantic import ValidationError

from app.dominio import DatoRespuesta, NombreRol
from app.schemas.consulta import EspecieCandidata, MapaEspecie, Procedencia, RespuestaConsulta
from app.schemas.preferencias import CambioPreferencias
from app.services import preferencias
from app.services.preferencias import Preferencias

from apoyo import api, crear_cuenta_verificada, sql, usuario_falso

PASSWORD = "Clave#2024"
RESUELTA = "pejibaye"  # el catálogo de demostración la resuelve con fuentes


# --- aplicar: qué se quita de la respuesta ------------------------------------


def _respuesta() -> RespuestaConsulta:
    return RespuestaConsulta(
        especie=EspecieCandidata(
            id="quercus-costaricensis",
            nombre_cientifico="Quercus costaricensis",
            familia="Fagaceae",
        ),
        texto="Crece en Talamanca【Quercus costaricensis (Tomo V, p.779)】 sobre los 2000 m.",
        fuentes=["Manual de Plantas de Costa Rica, Tomo V, p. 779", "GBIF"],
        mapa=MapaEspecie(url="/especies/quercus-costaricensis/mapa", capas=["Regiones"], puntos=12),
        procedencia=[
            Procedencia(
                dato=DatoRespuesta.TEXTO, fuente="Manual de Plantas de Costa Rica", detalle="p. 779"
            ),
            Procedencia(dato=DatoRespuesta.MAPA, fuente="CR-BioLM", detalle="mapa generado"),
        ],
    )


def test_con_todo_la_respuesta_no_cambia():
    respuesta = _respuesta()
    assert preferencias.aplicar(respuesta, Preferencias()) == respuesta


def test_sin_mapa_se_quita_el_mapa_y_su_procedencia():
    # RR_67 criterio 1.
    salida = preferencias.aplicar(_respuesta(), Preferencias(incluir_mapa=False))
    assert salida.mapa is None
    assert [p.dato for p in salida.procedencia] == [DatoRespuesta.TEXTO]
    assert salida.fuentes and "【" in salida.texto  # las fuentes siguen


def test_sin_fuentes_se_quitan_la_lista_la_procedencia_y_las_citas():
    # RR_68 criterio 1.
    salida = preferencias.aplicar(_respuesta(), Preferencias(incluir_fuentes=False))
    assert salida.fuentes == [] and salida.procedencia == []
    assert salida.texto == "Crece en Talamanca sobre los 2000 m."
    assert salida.mapa is not None  # el mapa sigue


def test_sin_nada_queda_el_texto():
    salida = preferencias.aplicar(_respuesta(), Preferencias(False, False))
    assert salida.mapa is None and salida.fuentes == [] and salida.procedencia == []
    assert salida.texto.startswith("Crece en Talamanca")


def test_aplicar_no_modifica_la_respuesta_original():
    original = _respuesta()
    preferencias.aplicar(original, Preferencias(False, False))
    assert original.mapa is not None and original.fuentes


# --- de: qué preferencias le tocan a cada quien --------------------------------


class _BD:
    """Solo lo que usa preferencias.de: db.get de la fila del sistema."""

    def __init__(self, mapa=True, fuentes=True):
        self.fila = type("Fila", (), {"incluir_mapa": mapa, "incluir_fuentes": fuentes})()

    def get(self, _modelo, _id):
        return self.fila


def _moderador(mapa=None, fuentes=None, rol=NombreRol.MODERADOR):
    return usuario_falso(rol=rol, incluir_mapa=mapa, incluir_fuentes=fuentes)


def test_moderador_sin_cambios_usa_la_del_sistema():
    # RR_80 criterio 2.
    assert preferencias.de(_BD(mapa=False), _moderador()) == Preferencias(False, True)


def test_moderador_con_preferencia_propia_la_usa():
    # RR_67 y RR_68: la propia gana sobre la del sistema, campo por campo.
    bd = _BD(mapa=True, fuentes=False)
    assert preferencias.de(bd, _moderador(mapa=False)) == Preferencias(False, False)
    assert preferencias.de(bd, _moderador(fuentes=True)) == Preferencias(True, True)


def test_el_supermoderador_tambien_puede_personalizar():
    assert preferencias.de(
        _BD(), _moderador(mapa=False, rol=NombreRol.SUPERMODERADOR)
    ) == Preferencias(False, True)


@pytest.mark.parametrize(
    "usuario", [None, usuario_falso(rol=NombreRol.USUARIO, incluir_mapa=False)]
)
def test_usuario_y_visitante_siempre_usan_la_del_sistema(usuario):
    # Un valor guardado de cuando era moderador no aplica si ya no lo es.
    assert preferencias.de(_BD(fuentes=False), usuario) == Preferencias(True, False)


def test_sin_la_fila_del_sistema_se_incluye_todo():
    class _Vacia:
        def get(self, *_):
            return None

    assert preferencias.de(_Vacia(), None) == Preferencias()


def test_el_cambio_solo_acepta_los_dos_campos():
    with pytest.raises(ValidationError):
        CambioPreferencias(incluir_mapa=True, otro=1)


# --- por la API, con la BD ---------------------------------------------------


@pytest.fixture
def cuenta(correos_de_prueba):
    """Crea una cuenta con el rol pedido y devuelve sus cabeceras."""

    def crear(rol: str = NombreRol.MODERADOR) -> dict:
        correo = correos_de_prueba(rol)
        crear_cuenta_verificada(correo, PASSWORD, rol)
        return _entrar(correo)

    return crear


def _entrar(correo: str) -> dict:
    token = api.post("/auth/login", json={"correo": correo, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {token['access_token']}", "_correo": correo}


def _h(cabeceras: dict) -> dict:
    return {k: v for k, v in cabeceras.items() if not k.startswith("_")}


def _fuentes_de_una_consulta(cabeceras: dict) -> list[str]:
    salida = api.post("/consultas", headers=_h(cabeceras), json={"texto": RESUELTA})
    assert salida.status_code == 200, salida.text
    return salida.json()["respuesta"]["fuentes"]


@pytest.fixture
def sistema():
    """Deja el comportamiento por defecto como estaba al terminar la prueba."""
    antes = sql(
        "SELECT incluir_mapa, incluir_fuentes FROM configuracion_respuestas WHERE id = 1"
    ).one()
    yield
    sql(
        "UPDATE configuracion_respuestas SET incluir_mapa = :m, incluir_fuentes = :f, "
        "actualizado_por = NULL WHERE id = 1",
        m=antes.incluir_mapa,
        f=antes.incluir_fuentes,
    )


def test_el_usuario_normal_no_configura_sus_respuestas(cuenta):
    # RR_67: solo el moderador.
    yo = cuenta(NombreRol.USUARIO)
    assert api.get("/perfil/preferencias", headers=_h(yo)).status_code == 403
    assert (
        api.patch(
            "/perfil/preferencias", headers=_h(yo), json={"incluir_fuentes": False}
        ).status_code
        == 403
    )


def test_el_visitante_no_tiene_preferencias():
    token = api.post("/auth/anonimo").json()["access_token"]
    assert (
        api.get("/perfil/preferencias", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_el_moderador_desactiva_las_fuentes_y_aplica_a_la_siguiente(cuenta, sistema):
    # RR_68 criterios 1 y 2.
    yo = cuenta()
    assert _fuentes_de_una_consulta(yo)  # por defecto vienen

    cambio = api.patch("/perfil/preferencias", headers=_h(yo), json={"incluir_fuentes": False})
    assert cambio.status_code == 200
    assert cambio.json()["incluir_fuentes"] is False and cambio.json()["fuentes_propio"] is True
    assert cambio.json()["mapa_propio"] is False  # el mapa no se tocó

    assert _fuentes_de_una_consulta(yo) == []


def test_las_preferencias_se_conservan_entre_sesiones(cuenta, sistema):
    # RR_67 y RR_68 criterio 3, RR_79 criterios 1 y 2.
    yo = cuenta()
    api.patch(
        "/perfil/preferencias",
        headers=_h(yo),
        json={"incluir_mapa": False, "incluir_fuentes": False},
    )
    api.post("/auth/logout", headers=_h(yo))

    de_nuevo = _entrar(yo["_correo"])
    guardadas = api.get("/perfil/preferencias", headers=_h(de_nuevo)).json()
    assert guardadas["incluir_mapa"] is False and guardadas["incluir_fuentes"] is False
    assert _fuentes_de_una_consulta(de_nuevo) == []


def test_cada_moderador_tiene_las_suyas(cuenta, sistema):
    # RR_79 criterio 3.
    uno, otro = cuenta(), cuenta()
    api.patch("/perfil/preferencias", headers=_h(uno), json={"incluir_fuentes": False})
    assert _fuentes_de_una_consulta(uno) == []
    assert _fuentes_de_una_consulta(otro)
    assert api.get("/perfil/preferencias", headers=_h(otro)).json()["fuentes_propio"] is False


def test_el_supermoderador_cambia_el_comportamiento_por_defecto(cuenta, sistema):
    # RR_80 criterios 1, 2 y 3: aplica a quien no lo ha cambiado, también al
    # usuario normal y al visitante; el moderador con preferencia propia la conserva.
    jefe, usuario, sin_cambios, con_cambios = (
        cuenta(NombreRol.SUPERMODERADOR),
        cuenta(NombreRol.USUARIO),
        cuenta(),
        cuenta(),
    )
    api.patch("/perfil/preferencias", headers=_h(con_cambios), json={"incluir_fuentes": True})

    cambio = api.put(
        "/admin/preferencias-respuesta",
        headers=_h(jefe),
        json={"incluir_mapa": True, "incluir_fuentes": False},
    )
    assert cambio.status_code == 200
    assert cambio.json()["incluir_fuentes"] is False
    assert cambio.json()["actualizado_por"] == jefe["_correo"]

    visitante = {"Authorization": f"Bearer {api.post('/auth/anonimo').json()['access_token']}"}
    assert _fuentes_de_una_consulta(usuario) == []
    assert _fuentes_de_una_consulta(visitante) == []
    assert _fuentes_de_una_consulta(sin_cambios) == []
    assert _fuentes_de_una_consulta(con_cambios)

    # Volver a la del sistema: null.
    api.patch("/perfil/preferencias", headers=_h(con_cambios), json={"incluir_fuentes": None})
    assert _fuentes_de_una_consulta(con_cambios) == []


def test_solo_el_supermoderador_cambia_el_comportamiento_por_defecto(cuenta):
    moderador = cuenta()
    datos = {"incluir_mapa": False, "incluir_fuentes": False}
    assert (
        api.put("/admin/preferencias-respuesta", headers=_h(moderador), json=datos).status_code
        == 403
    )
    assert api.get("/admin/preferencias-respuesta", headers=_h(moderador)).status_code == 403
