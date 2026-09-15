from utils.cpf import limpar_cpf, validar_cpf

def test_cpf_valido():
    # CPF válido real ou gerado com DV correto
    cpf_valido = "11144477735"
    is_valid, msg = validar_cpf(cpf_valido)
    assert is_valid is True
    assert msg == ""

def test_cpf_invalido_dv():
    cpf_invalido = "11144477700"
    is_valid, msg = validar_cpf(cpf_invalido)
    assert is_valid is False
    assert "Dígito verificador" in msg

def test_cpf_com_mascara():
    raw = "111.444.777-35"
    clean = limpar_cpf(raw)
    assert clean == "11144477735"

def test_cpf_zero_inicial():
    raw = "12345678"
    clean = limpar_cpf(raw)
    assert len(clean) == 11
    assert clean.startswith("000")

def test_cpf_vazio():
    clean = limpar_cpf("")
    assert clean == ""
    is_valid, msg = validar_cpf(clean)
    assert is_valid is False
    assert msg == "CPF vazio"

def test_cpf_digitos_repetidos():
    clean = limpar_cpf("111.111.111-11")
    is_valid, msg = validar_cpf(clean)
    assert is_valid is False
    assert "repetidos" in msg
