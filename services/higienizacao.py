import re
import pandas as pd
from utils.cpf import limpar_cpf
from utils.datas import normalizar_data

def higienizar_texto_nome(nome_raw) -> str:
    """
    Higieniza nomes conforme regra #11:
    - Remove espaços no início e final
    - Substitui múltiplos espaços e quebras de linha por espaço único
    - Remove caracteres invisíveis (como \\xa0, \\u200b)
    - Converte para letras MAIÚSCULAS mantendo acentuação intacta.
    """
    if nome_raw is None or pd.isna(nome_raw):
        return ""
        
    val = str(nome_raw)
    
    # Remove caracteres invisíveis e controle
    val = re.sub(r'[\xa0\u200b\u200c\u200d\uFEFF\r\n\t]', ' ', val)
    
    # Coloca espaço único em lugar de múltiplos espaços
    val = re.sub(r'\s+', ' ', val)
    
    # Trim e maiúsculas
    val = val.strip().upper()
    return val

def higienizar_valor_numerico(val_raw) -> str:
    """
    Normaliza valores monetários e numéricos convertendo para string decimal com ponto.
    Exemplo: '4.106,09' -> '4106.09'
    """
    if val_raw is None or pd.isna(val_raw):
        return "0.00"
        
    val_str = str(val_raw).strip()
    if not val_str or val_str.lower() in ['nan', 'none', 'null']:
        return "0.00"
        
    # Remove símbolo de moeda e espaços
    val_str = re.sub(r'[R\$\s]', '', val_str)
    
    # Se contém vírgula e ponto: ex 1.234,56 -> 1234.56
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
        
    try:
        num = float(val_str)
        return f"{num:.2f}"
    except ValueError:
        return val_str

def higienizar_dataframe(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """
    Executa a higienização completa em uma cópia do DataFrame.
    col_map é da forma {'cpf': 'CPF', 'nome': 'Nome', ...}
    """
    df_hig = df.copy()
    
    # Higieniza Nome
    col_nome = col_map.get('nome')
    if col_nome and col_nome in df_hig.columns:
        df_hig[col_nome] = df_hig[col_nome].apply(higienizar_texto_nome)
            
    # Higieniza CPF
    col_cpf = col_map.get('cpf')
    if col_cpf and col_cpf in df_hig.columns:
        df_hig[col_cpf] = df_hig[col_cpf].apply(limpar_cpf)
            
    # Higieniza Data de Nascimento
    col_dt = col_map.get('data_nascimento')
    if col_dt and col_dt in df_hig.columns:
        df_hig[col_dt] = df_hig[col_dt].apply(normalizar_data)
            
    # Higieniza Valores Numéricos (bruto, liquido, inss)
    for col_key in ['total_bruto', 'total_liquido', 'inss']:
        col_orig = col_map.get(col_key)
        if col_orig and col_orig in df_hig.columns:
            df_hig[col_orig] = df_hig[col_orig].apply(higienizar_valor_numerico)
                
    # Higieniza CBO
    col_cbo = col_map.get('cbo')
    if col_cbo and col_cbo in df_hig.columns:
        df_hig[col_cbo] = df_hig[col_cbo].apply(lambda x: str(x).strip() if pd.notna(x) else "")
            
    return df_hig
