from services.higienizacao import higienizar_texto_nome, higienizar_valor_numerico

def test_higienizacao_nome_espacos_e_quebras():
    nome_raw = "  JOÃO   DA   SILVA  \n"
    nome_clean = higienizar_texto_nome(nome_raw)
    assert nome_clean == "JOÃO DA SILVA"

def test_higienizacao_nome_acentos():
    nome_raw = "  José  Álvaro   da  Conceição  "
    nome_clean = higienizar_texto_nome(nome_raw)
    assert nome_clean == "JOSÉ ÁLVARO DA CONCEIÇÃO"

def test_higienizacao_valor_numerico():
    v1 = higienizar_valor_numerico("R$ 4.106,09")
    assert v1 == "4106.09"
    v2 = higienizar_valor_numerico(3654.42)
    assert v2 == "3654.42"
    v3 = higienizar_valor_numerico(None)
    assert v3 == "0.00"
