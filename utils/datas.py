from datetime import datetime, date
import pandas as pd

def normalizar_data(data_raw) -> str:
    """
    Normaliza valores de data para a string padronizada 'DD/MM/YYYY'.
    Suporta datetime, pd.Timestamp, strings em vários formatos e numéricos do Excel.
    """
    if data_raw is None or pd.isna(data_raw):
        return ""
        
    if isinstance(data_raw, (datetime, date, pd.Timestamp)):
        return data_raw.strftime('%d/%m/%Y')
        
    val_str = str(data_raw).strip()
    if not val_str or val_str.lower() in ['nan', 'nat', 'none', 'null', '0']:
        return ""
        
    # Tratamento de data no formato ISO YYYY-MM-DD HH:MM:SS ou YYYY-MM-DD
    if ' ' in val_str:
        val_str = val_str.split(' ')[0]
        
    # Formatos comuns
    formatos = [
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d.%m.%Y',
        '%Y/%m/%d'
    ]
    
    for fmt in formatos:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.strftime('%d/%m/%Y')
        except ValueError:
            pass
            
    # Tenta usar pd.to_datetime para casos atípicos
    try:
        dt = pd.to_datetime(val_str, dayfirst=True)
        if not pd.isna(dt):
            return dt.strftime('%d/%m/%Y')
    except Exception:
        pass
        
    return val_str

def validar_data(data_str: str) -> tuple[bool, str]:
    """
    Valida a data de nascimento.
    Retorna (True, "") para válida, ou (False, "Motivo") para inválida.
    """
    if not data_str:
        return False, "Data de nascimento vazia"
        
    try:
        dt = datetime.strptime(data_str, '%d/%m/%Y').date()
    except ValueError:
        return False, f"Data com formato inválido (esperado DD/MM/YYYY, informado: '{data_str}')"
        
    hoje = date.today()
    if dt > hoje:
        return False, f"Data no futuro não é permitida ('{data_str}')"
        
    if dt.year < 1900:
        return False, f"Ano de nascimento muito antigo ('{dt.year}')"
        
    return True, ""
