from services.validacao import validar_base
from services.banco import (
    init_db, salvar_registros_no_banco,
    atualizar_registro_banco, obter_registros_banco, limpar_banco
)
import pandas as pd

def test_descarte_manual_de_linha():
    session_id = "test_descarte_manual_sess"
    aba = "nov24"
    limpar_banco(session_id)
    
    df = pd.DataFrame([
        {'CPF': '111.444.777-35', 'Nome': 'VANDA CARDOSO', 'Nascimento': '10/05/1995'},
        {'CPF': '000.000.000-00', 'Nome': 'LINHA COM ERRO OU TOTAL', 'Nascimento': '10/05/1995'}
    ])
    col_map = {'cpf': 'CPF', 'nome': 'Nome', 'data_nascimento': 'Nascimento'}
    
    regs = validar_base(df, col_map)
    assert len(regs) == 2
    assert regs[0]['status'] == '🟢 OK'
    assert regs[1]['status'] == '🔴 ERRO_CRITICO' # Inicialmente erro critico
    
    salvar_registros_no_banco(session_id, aba, regs)
    
    # Usuario clica no botao [ 🗑️ Descartar ] para a linha com erro
    regs_db = obter_registros_banco(session_id, aba, apenas_pendencias=True)
    id_erro = regs_db[0]['id']
    
    atualizar_registro_banco(
        id_erro, regs_db[0]['cpf'], regs_db[0]['nome'], regs_db[0]['data_nascimento'],
        0.0, 0.0, "", 0.0, acao='descartar'
    )
    
    regs_atualizados = obter_registros_banco(session_id, aba)
    row_desc = next(r for r in regs_atualizados if r['id'] == id_erro)
    assert row_desc['status'] == '⚪ DESCARTADO'
    
    limpar_banco(session_id)

def test_descarte_todas_pendencias_em_lote():
    from services.banco import descartar_todas_pendencias_banco, obter_estatisticas_aba
    session_id = "test_lote_sess"
    aba = "nov24"
    limpar_banco(session_id)
    
    df = pd.DataFrame([
        {'CPF': '111.444.777-35', 'Nome': 'JOAO SILVA', 'Nascimento': '10/05/1995'},
        {'CPF': '000.000.000-00', 'Nome': 'ERRO 1', 'Nascimento': '10/05/1995'},
        {'CPF': '111.111.111-11', 'Nome': 'ERRO 2', 'Nascimento': '10/05/1995'}
    ])
    col_map = {'cpf': 'CPF', 'nome': 'Nome', 'data_nascimento': 'Nascimento'}
    regs = validar_base(df, col_map)
    salvar_registros_no_banco(session_id, aba, regs)
    
    stats_antes = obter_estatisticas_aba(session_id, aba)
    assert stats_antes['danger'] == 2
    assert stats_antes['ok'] == 1
    
    # Descarta todas as pendencias em lote
    qtd = descartar_todas_pendencias_banco(session_id, aba)
    assert qtd == 2
    
    stats_depois = obter_estatisticas_aba(session_id, aba)
    assert stats_depois['danger'] == 0
    assert stats_depois['descartados'] == 2
    assert stats_depois['ok'] == 1
    
    limpar_banco(session_id)
