from utils.excel import listar_abas_excel, ler_aba_excel
import os

def test_ler_excel_com_bytes():
    path = "templates/esocial.xlsx"
    with open(path, "rb") as f:
        file_bytes = f.read()
        
    abas = listar_abas_excel(file_bytes)
    assert len(abas) > 0
    
    df = ler_aba_excel(file_bytes, abas[0])
    assert df is not None
