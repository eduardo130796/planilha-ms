from utils.datas import normalizar_data, validar_data
from datetime import datetime

def test_data_valida():
    dt_str = normalizar_data("1986-12-27")
    assert dt_str == "27/12/1986"
    is_valid, msg = validar_data(dt_str)
    assert is_valid is True

def test_data_invalida():
    dt_str = normalizar_data("31/02/2024")
    is_valid, msg = validar_data(dt_str)
    assert is_valid is False
    assert "formato inválido" in msg or "impossível" in msg

def test_data_vazia():
    dt_str = normalizar_data(None)
    assert dt_str == ""
    is_valid, msg = validar_data(dt_str)
    assert is_valid is False
    assert msg == "Data de nascimento vazia"

def test_data_futura():
    dt_str = normalizar_data("2099-01-01")
    is_valid, msg = validar_data(dt_str)
    assert is_valid is False
    assert "futuro" in msg
