import re
import io
import zipfile
import openpyxl
import pandas as pd
from utils.excel import gerar_excel_esocial

def gerar_nome_arquivo(nome_aba: str, competencia_detectada: str = None) -> str:
    """
    Gera automaticamente o nome padronizado do arquivo Excel conforme regra #30:
    eSocial_Folha_Ordinaria_[COMPETENCIA_OU_ABA].xlsx
    """
    sufixo = competencia_detectada if competencia_detectada else nome_aba
    sufixo_limpo = re.sub(r'[^\w\-]', '_', str(sufixo).strip())
    return f"eSocial_Folha_Ordinaria_{sufixo_limpo}.xlsx"

def gerar_pacote_zip_arquivos(arquivos_excel: list[tuple[str, bytes]]) -> bytes:
    """
    Cria um buffer ZIP em memória contendo múltiplos arquivos Excel para download em lote.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, excel_bytes in arquivos_excel:
            zip_file.writestr(filename, excel_bytes)
            
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def validar_arquivo_final_exportado(excel_bytes: bytes, modelo_path: str = "templates/esocial.xlsx") -> dict:
    """
    Executa a validação final (regra #28) sobre o buffer de saída do Excel antes do download.
    Verifica nomes de colunas, quantidade, ordem, ausência de 'Unnamed' ou índices.
    """
    wb_gerado = openpyxl.load_workbook(io.BytesIO(excel_bytes), read_only=True)
    ws_gerado = wb_gerado.active
    
    colunas_esperadas = ['cpf', 'nome', 'data_nascimento', 'total_bruto', 'total_liquido', 'cbo', 'inss']
    colunas_encontradas = [str(cell.value) for cell in next(ws_gerado.iter_rows(max_row=1))]
    
    erros_validacao_final = []
    
    if colunas_encontradas != colunas_esperadas:
        erros_validacao_final.append(
            f"Estrutura de colunas incorreta. Esperado: {colunas_esperadas}, Encontrado: {colunas_encontradas}"
        )
        
    for col in colunas_encontradas:
        if 'unnamed' in col.lower() or 'index' in col.lower():
            erros_validacao_final.append(f"Coluna auxiliar não permitida detectada: '{col}'")
            
    wb_gerado.close()
    
    return {
        'valido': len(erros_validacao_final) == 0,
        'erros': erros_validacao_final,
        'qtd_colunas': len(colunas_encontradas),
        'colunas': colunas_encontradas
    }
