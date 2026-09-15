import pandas as pd
from services.comparacao import comparar_com_folha_anterior

def test_comparacao_divergencia_nome():
    registros_atuais = [
        {
            'linha': 2,
            'cpf': '11144477735',
            'nome': 'JOAO SILVA',
            'data_nascimento': '10/05/1995',
            'status': '🟢 OK',
            'erros_criticos': [],
            'alertas': [],
            'aprovado_usuario': False
        }
    ]
    
    df_anterior = pd.DataFrame([
        {'CPF': '11144477735', 'Nome': 'JOAO DA SILVA', 'Nascimento': '10/05/1995'}
    ])
    
    col_map_ant = {'cpf': 'CPF', 'nome': 'Nome', 'data_nascimento': 'Nascimento'}
    res = comparar_com_folha_anterior(registros_atuais, df_anterior, col_map_ant)
    
    assert len(res) == 1
    assert res[0]['status'] == '🟡 CONFERIR'
    assert any("Divergência de nome" in str(a) for a in res[0]['alertas'])
