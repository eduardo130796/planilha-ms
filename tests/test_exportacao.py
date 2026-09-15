import pandas as pd
from services.conversao import gerar_dataframe_esocial_final
from utils.excel import gerar_excel_esocial
from services.exportacao import validar_arquivo_final_exportado

def test_fluxo_exportacao():
    registros = [
        {
            'cpf': '1231231231',
            'nome': 'TESTE DA SILVA',
            'data_nascimento': '27/12/1986',
            'total_bruto': '4106.09',
            'total_liquido': '4106.09',
            'cbo': '225125',
            'inss': '451.66'
        }
    ]
    
    df_esocial = gerar_dataframe_esocial_final(registros)
    assert list(df_esocial.columns) == ['cpf', 'nome', 'data_nascimento', 'total_bruto', 'total_liquido', 'cbo', 'inss']
    
    excel_bytes = gerar_excel_esocial(df_esocial, modelo_path="templates/esocial.xlsx")
    assert len(excel_bytes) > 0
    
    val_res = validar_arquivo_final_exportado(excel_bytes, modelo_path="templates/esocial.xlsx")
    assert val_res['valido'] is True
    assert val_res['erros'] == []
