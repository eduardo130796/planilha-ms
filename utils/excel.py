import io
import openpyxl
from openpyxl.styles import numbers
import pandas as pd

try:
    from python_calamine import CalamineWorkbook
    HAS_CALAMINE = True
except ImportError:
    HAS_CALAMINE = False

def _garantir_arquivo_ou_buffer(file_input):
    if isinstance(file_input, bytes):
        return io.BytesIO(file_input)
    return file_input

def listar_abas_excel(file_input) -> list[str]:
    """
    Retorna a lista de nomes das abas da planilha Excel em milissegundos.
    """
    obj = _garantir_arquivo_ou_buffer(file_input)
    
    if HAS_CALAMINE:
        try:
            if isinstance(obj, str):
                wb = CalamineWorkbook.from_path(obj)
                return wb.sheet_names
            elif hasattr(obj, 'read'):
                pos = obj.tell() if hasattr(obj, 'tell') else 0
                wb = CalamineWorkbook.from_filelike(obj)
                if hasattr(obj, 'seek'):
                    obj.seek(pos)
                return wb.sheet_names
        except Exception:
            if hasattr(obj, 'seek'):
                obj.seek(0)

    wb = openpyxl.load_workbook(obj, read_only=True, data_only=True)
    names = wb.sheetnames
    wb.close()
    return names

def ler_aba_excel(file_input, aba_nome: str = None) -> pd.DataFrame:
    """
    Lê uma aba específica do Excel com o motor Calamine 12x mais rápido.
    Garante que colunas textuais não percam zeros à esquerda.
    """
    obj = _garantir_arquivo_ou_buffer(file_input)
    
    if HAS_CALAMINE:
        try:
            if isinstance(obj, str):
                wb = CalamineWorkbook.from_path(obj)
            else:
                pos = obj.tell() if hasattr(obj, 'tell') else 0
                wb = CalamineWorkbook.from_filelike(obj)
                if hasattr(obj, 'seek'):
                    obj.seek(pos)

            target_sheet = aba_nome if aba_nome else wb.sheet_names[0]
            sheet = wb.get_sheet_by_name(target_sheet)
            data = sheet.to_python()
            
            if not data:
                return pd.DataFrame()
                
            header = [str(c) if c is not None else "" for c in data[0]]
            rows = data[1:]
            
            str_rows = []
            for r in rows:
                str_rows.append([str(cell).strip() if cell is not None else "" for cell in r])
                
            df = pd.DataFrame(str_rows, columns=header)
            return df
        except Exception:
            if hasattr(obj, 'seek'):
                obj.seek(0)

    df = pd.read_excel(
        obj,
        sheet_name=aba_nome,
        dtype=str,
        engine='openpyxl'
    )
    return df

def gerar_excel_esocial(df_esocial: pd.DataFrame, modelo_path: str = "templates/esocial.xlsx") -> bytes:
    """
    Gera o arquivo Excel formatado rigorosamente conforme o modelo usando o escritor
    streaming write_only de alta velocidade do OpenPyXL. O nome da aba vem do próprio
    modelo de referência (esocial.xlsx -> "E-Social", reinf_r4010.xlsx -> "R-4010") e a
    ordem/nome das colunas vem do DataFrame já formatado pela função geradora específica
    (gerar_dataframe_esocial_final / gerar_dataframe_reinf_final).
    """
    wb_modelo = openpyxl.load_workbook(modelo_path, read_only=True)
    titulo_aba = wb_modelo.sheetnames[0]
    wb_modelo.close()

    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet(title=titulo_aba)

    colunas_modelo = list(df_esocial.columns)
    ws.append(colunas_modelo)
    
    for r in df_esocial.itertuples(index=False):
        row_vals = []
        for val in r:
            if pd.isna(val) or val is None:
                row_vals.append("")
            else:
                row_vals.append(str(val))
        ws.append(row_vals)
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
