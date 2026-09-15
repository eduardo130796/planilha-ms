from services.validacao import validar_base
from services.banco import (
    init_db, salvar_registros_no_banco,
    consolidar_folha_suplementar_sqlite, obter_registros_banco, limpar_banco
)
import pandas as pd

def test_fallback_valores_quando_apenas_liquido_ou_bruto_existe():
    session_id = "test_fallback_sess"
    aba = "nov24"
    limpar_banco(session_id)
    
    # Simula planilha que SO possui Valor Liquido (Valor Bruto ausente/zerado)
    df = pd.DataFrame([
        {'CPF': '111.444.777-35', 'Nome': 'JOAO SILVA', 'Nascimento': '10/05/1995', 'Valor Liquido': '3654.42'}
    ])
    col_map = {'cpf': 'CPF', 'nome': 'Nome', 'data_nascimento': 'Nascimento', 'total_liquido': 'Valor Liquido'}
    
    regs = validar_base(df, col_map)
    assert regs[0]['total_bruto'] == '3654.42' # Fallback automatico!
    assert regs[0]['total_liquido'] == '3654.42'
    
    salvar_registros_no_banco(session_id, aba, regs)
    
    # Aplica a opcao 2 (bruto_igual_liquido)
    consolidar_folha_suplementar_sqlite(session_id, aba, aplicar_regra_valores=True, opcao_inss="bruto_igual_liquido")
    
    regs_post = obter_registros_banco(session_id, aba)
    assert regs_post[0]['total_bruto'] == '3654.42' # NAO PODE FICAR ZERADO!
    assert regs_post[0]['total_liquido'] == '3654.42'
    assert regs_post[0]['inss'] == '0.00'
    
    limpar_banco(session_id)
