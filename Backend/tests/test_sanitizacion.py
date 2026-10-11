"""Pruebas de RR_00_08 — sanitización de entradas.

No necesitan base de datos. Se ejecutan con:
    docker compose exec backend python -m pytest tests -q
"""

import pytest
from pydantic import ValidationError

from app.sanitizacion import sanitizar_texto
from app.schemas.consulta import ConsultaRequest
from app.schemas.usuario import RegistroRequest

PASSWORD_VALIDA = "Prueba123!"


# --- criterio 1 y 2: se limpian y neutralizan los caracteres peligrosos ------


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("<script>alert(1)</script>guaria", "alert(1)guaria"),
        ('<img src=x onerror="alert(1)">cedro', "cedro"),
        ("roble<!-- comentario -->negro", "roblenegro"),
        ("<scr<b>ipt>alert(1)</script>", "alert(1)"),
        ("pejibaye\x00", "pejibaye"),
        ("gua​ria", "guaria"),
        ("cedro‮odaroc", "cedroodaroc"),
        ("\x1b[31mroble", "[31mroble"),
    ],
)
def test_neutraliza_marcado_y_caracteres_de_control(entrada, esperado):
    assert sanitizar_texto(entrada) == esperado


# --- criterio 3: el contenido legítimo no cambia ---------------------------


@pytest.mark.parametrize(
    "entrada",
    [
        "¿Dónde se encuentra la guaria morada?",
        "Distribución de Cedrela odorata en Guanacaste",
        "Especies con elevación > 1000 y < 2500 msnm",
        "¿Qué es el \"cedro amargo\"; y el 'cedro dulce'?",
        "Pingüino, año, ñandú",
        "Primera línea\nSegunda línea\tcon tabulador",
    ],
)
def test_no_altera_contenido_legitimo(entrada):
    assert sanitizar_texto(entrada) == entrada


def test_normaliza_tildes_a_nfc_sin_cambiar_lo_que_se_lee():
    # "e" + acento combinante (NFD) pasa a "é" precompuesta (NFC).
    assert sanitizar_texto("Distribución") == "Distribución"


def test_quita_espacios_de_los_extremos():
    assert sanitizar_texto("   guaria   ") == "guaria"


# --- aplicación en los esquemas --------------------------------------------


def test_consulta_se_sanitiza_al_validar():
    consulta = ConsultaRequest(texto="<b>guaria</b> morada")
    assert consulta.texto == "guaria morada"


def test_consulta_solo_con_marcado_se_rechaza_como_vacia():
    with pytest.raises(ValidationError):
        ConsultaRequest(texto="<script></script>​")


@pytest.mark.parametrize("especie_id", ["cedrela-odorata", "guarianthe-skinneri"])
def test_especie_id_valido(especie_id):
    assert ConsultaRequest(texto="cedro", especie_id=especie_id).especie_id == especie_id


@pytest.mark.parametrize(
    "especie_id", ["'; DROP TABLE consultas;--", "../../etc", "<b>x</b>", "Cedrela"]
)
def test_especie_id_con_caracteres_invalidos_se_rechaza(especie_id):
    with pytest.raises(ValidationError):
        ConsultaRequest(texto="cedro", especie_id=especie_id)


def test_nombre_de_registro_se_sanitiza():
    datos = RegistroRequest(
        nombre="<i>Ana</i> Rodríguez", correo="ana@example.com", password=PASSWORD_VALIDA
    )
    assert datos.nombre == "Ana Rodríguez"


def test_nombre_de_registro_sigue_la_misma_regla_que_el_perfil():
    datos = RegistroRequest(
        nombre="  Ana    María  ", correo="ana@example.com", password=PASSWORD_VALIDA
    )
    assert datos.nombre == "Ana María"
    with pytest.raises(ValidationError):
        RegistroRequest(nombre="  a  ", correo="ana@example.com", password=PASSWORD_VALIDA)


def test_password_no_se_sanitiza():
    password = "<Abc>123!xyz"
    datos = RegistroRequest(nombre="Ana", correo="ana@example.com", password=password)
    assert datos.password == password
