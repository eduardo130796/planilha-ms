import pytest
from services.banco import (
    init_db, salvar_registros_no_banco, obter_estatisticas_aba,
    obter_registros_banco, consolidar_folha_suplementar_sqlite,
    atualizar_registro_banco, limpar_banco
)

def test_banco_sqlite_consolidacao_e_inss():
    session_id = "test_session_123"
    aba = "nov24"
    
    # Limpa antes de testar
    limpar_banco(session_id)
    
    # Simula 2 registros do mesmo CPF (Folha Suplementar)
    registros = [
        {
            'linha': 2,
            'cpf': '11144477735',
            'nome': 'JOAO SILVA',
            'data_nascimento': '10/05/1995',
            'total_bruto': '2000.00',
            'total_liquido': '1800.00',
            'cbo': '225125',
            'inss': '200.00',
            'status': '🟢 OK',
            'erros_criticos': [],
            'alertas': []
        },
        {
            'linha': 3,
            'cpf': '11144477735',
            'nome': 'JOAO SILVA',
            'data_nascimento': '10/05/1995',
            'total_bruto': '1000.00',
            'total_liquido': '900.00',
            'cbo': '225125',
            'inss': '100.00',
            'status': '🟢 OK',
            'erros_criticos': [],
            'alertas': []
        }
    ]
    
    salvar_registros_no_banco(session_id, aba, registros)
    
    stats = obter_estatisticas_aba(session_id, aba)
    assert stats['total'] == 2
    
    # Executa consolidação por CPF com INSS calculado em 10%
    consolidar_folha_suplementar_sqlite(session_id, aba, aplicar_regra_valores=True, opcao_inss="percentual_inss", percentual_inss=10.0)
    
    stats_post = obter_estatisticas_aba(session_id, aba)
    assert stats_post['total'] == 1 # Agrupado em 1 único registro!
    
    regs_post = obter_registros_banco(session_id, aba)
    r = regs_post[0]
    assert r['cpf'] == '11144477735'
    assert float(r['total_bruto']) == 3000.00 # 2000 + 1000
    assert float(r['inss']) == 300.00 # 10% de 3000
    assert float(r['total_liquido']) == 2700.00 # 3000 - 300

    limpar_banco(session_id)


def test_banco_sqlite_consolidacao_mantem_valores_e_cbo_originais_por_padrao():
    """Por padrão, agrupar por CPF deve apenas SOMAR os valores já preenchidos na
    planilha (sem recalcular Bruto/Líquido/INSS) e preservar o CBO de cada linha,
    usando o CBO padrão do painel só quando a linha não tiver CBO nenhum."""
    session_id = "test_session_cbo_valores"
    aba = "dez24"

    limpar_banco(session_id)

    registros = [
        {
            'linha': 2, 'cpf': '11144477735', 'nome': 'JOAO SILVA', 'data_nascimento': '10/05/1995',
            'total_bruto': '2000.00', 'total_liquido': '1800.00', 'cbo': '225124', 'inss': '200.00',
            'status': '🟢 OK', 'erros_criticos': [], 'alertas': []
        },
        {
            'linha': 3, 'cpf': '11144477735', 'nome': 'JOAO SILVA', 'data_nascimento': '10/05/1995',
            'total_bruto': '1000.00', 'total_liquido': '900.00', 'cbo': '225124', 'inss': '100.00',
            'status': '🟢 OK', 'erros_criticos': [], 'alertas': []
        }
    ]
    salvar_registros_no_banco(session_id, aba, registros)

    # Não passa aplicar_regra_valores (usa o padrão False) e informa um CBO de fallback
    # diferente do CBO que já vem preenchido na planilha ('225124').
    consolidar_folha_suplementar_sqlite(session_id, aba, cbo_padrao="999999")

    regs_post = obter_registros_banco(session_id, aba)
    assert len(regs_post) == 1
    r = regs_post[0]
    assert float(r['total_bruto']) == 3000.00   # soma pura, sem recalcular
    assert float(r['total_liquido']) == 2700.00 # soma pura, sem recalcular
    assert float(r['inss']) == 300.00           # soma pura, sem recalcular
    assert r['cbo'] == '225124'                 # preserva o CBO já preenchido, ignora o padrão

    limpar_banco(session_id)
