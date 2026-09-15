import pytest
import pandas as pd
from services.reinf import auto_detectar_mapeamento_reinf, validar_base_reinf, gerar_dataframe_reinf_final
from services.banco import (
    limpar_banco, salvar_registros_reinf_no_banco, obter_estatisticas_reinf_aba,
    obter_registros_reinf_banco, atualizar_registro_reinf_banco, exportar_registros_reinf_banco_para_list
)

def test_reinf_auto_detectar_mapeamento():
    colunas = ['CPF', 'Data Crédito em Conta', 'Valor Líquido', 'Parcela Isenta', 'Tipo Residência']
    col_map, nao_mapeadas = auto_detectar_mapeamento_reinf(colunas)
    
    assert col_map['cpf'] == 'CPF'
    assert col_map['data_fato_gerador'] == 'Data Crédito em Conta'
    assert col_map['rendimento_bruto'] == 'Valor Líquido'
    assert col_map['parcela_isenta'] == 'Parcela Isenta'
    assert col_map['observacao_pagamento'] == 'Tipo Residência'

def test_reinf_validacao_base():
    data = {
        'CPF': ['11144477735', '99999999999'],
        'Data Crédito em Conta': ['02/12/2024', 'data_invalida'],
        'Valor Líquido': [1500.0, 2000.0],
        'Parcela Isenta': [0.0, 100.0],
        'Tipo Residência': ['Médica', 'Multiprofissional']
    }
    df = pd.DataFrame(data)
    col_map, _ = auto_detectar_mapeamento_reinf(list(df.columns))
    
    resultados = validar_base_reinf(df, col_map)
    assert len(resultados) == 2
    assert resultados[0]['status'] == '🟢 OK'
    assert resultados[1]['status'] == '🔴 ERRO_CRITICO'

def test_reinf_banco_sqlite_e_exportacao():
    session_id = "test_reinf_session"
    aba = "nov24"
    
    limpar_banco(session_id)
    
    registros = [{
        'linha': 2,
        'cpf': '11144477735',
        'nome': 'MARIA SILVA',
        'data_fato_gerador': '02/12/2024',
        'rendimento_bruto': '3000.00',
        'parcela_isenta': '0.00',
        'observacao_pagamento': 'OB 12345',
        'status': '🟢 OK',
        'erros_criticos': [],
        'alertas': []
    }]
    
    salvar_registros_reinf_no_banco(session_id, aba, registros)
    
    stats = obter_estatisticas_reinf_aba(session_id, aba)
    assert stats['total'] == 1
    assert stats['ok'] == 1
    
    regs_exp = exportar_registros_reinf_banco_para_list(session_id, aba)
    assert len(regs_exp) == 1
    
    df_final = gerar_dataframe_reinf_final(regs_exp)
    assert list(df_final.columns) == ['cpf', 'data_fato_gerador', 'rendimento_bruto', 'parcela_isenta', 'observacao_pagamento']
    assert df_final.iloc[0]['cpf'] == '11144477735'
    assert df_final.iloc[0]['data_fato_gerador'] == '02/12/2024'
    assert df_final.iloc[0]['rendimento_bruto'] == '3000.00'
    
    limpar_banco(session_id)
