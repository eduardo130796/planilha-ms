import pandas as pd
from services.validacao import validar_base

def test_validacao_duplicidade_e_erros():
    df = pd.DataFrame([
        {'CPF': '111.444.777-35', 'Nome': 'JOAO SILVA', 'Nascimento': '10/05/1995'},
        {'CPF': '111.444.777-35', 'Nome': 'JOAO SILVA', 'Nascimento': '10/05/1995'}, # Duplicado
        {'CPF': '00000000000', 'Nome': 'PEDRO', 'Nascimento': '10/05/1995'}, # CPF invalido
        {'CPF': '11144477735', 'Nome': '', 'Nascimento': '10/05/1995'} # Nome vazio
    ])
    
    col_map = {'cpf': 'CPF', 'nome': 'Nome', 'data_nascimento': 'Nascimento'}
    res = validar_base(df, col_map)
    
    assert len(res) == 4
    # Registro 0 e 1 devem ter alerta de duplicidade
    assert any("duplicado" in str(e) for e in res[0]['erros_criticos'])
    assert any("duplicado" in str(e) for e in res[1]['erros_criticos'])
    # Registro 2 CPF invalido
    assert any("inválido" in str(e) for e in res[2]['erros_criticos'])
    # Registro 3 Nome obrigatorio
    assert any("obrigatório" in str(e) for e in res[3]['erros_criticos'])
