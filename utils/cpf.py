import re

def limpar_cpf(cpf_raw) -> str:
    """
    Normaliza o CPF garantindo retorno estritamente em string de apenas 11 números.
    Trata sufixos decimais do Excel (.0, .00, ,0, ,00), notação científica e zeros à esquerda.
    """
    if cpf_raw is None:
        return ""
        
    # Tratamento preliminar se for float nativo do Python
    if isinstance(cpf_raw, float):
        if str(cpf_raw).endswith('.0'):
            cpf_raw = int(cpf_raw)
        else:
            cpf_raw = f"{cpf_raw:.0f}"
            
    val = str(cpf_raw).strip()
    if not val or val.lower() in ['nan', 'none', 'null']:
        return ""
        
    # Se estiver em notação científica (ex: 1.2345678901e+10)
    if 'e+' in val.lower() or 'e-' in val.lower():
        try:
            val = f"{float(val):.0f}"
        except ValueError:
            pass
            
    # Remove sufixos decimais de números do Excel (ex: "14273686783.0" -> "14273686783")
    val = re.sub(r'[\.,]0+$', '', val)
    
    # Remove qualquer caractere não numérico
    val = re.sub(r'\D', '', val)
    
    if not val:
        return ""
        
    # Se ainda restar 12 dígitos terminados em '0' (ex: formato de precisão residual)
    if len(val) == 12 and val.endswith('0'):
        val = val[:11]
        
    if len(val) <= 11:
        return val.zfill(11)
        
    return val

def validar_cpf(cpf_clean: str) -> tuple[bool, str]:
    """
    Valida a consistência matemática do CPF.
    Retorna (True, "") para válido, ou (False, "Motivo") para inválido.
    """
    if not cpf_clean:
        return False, "CPF vazio"
        
    if len(cpf_clean) != 11 or not cpf_clean.isdigit():
        return False, f"CPF deve conter exatamente 11 dígitos (informado: {len(cpf_clean)})"
        
    # Sequências inválidas conhecidas (000.000.000-00, 111.111.111-11, etc)
    if cpf_clean in [s * 11 for s in "0123456789"]:
        return False, "CPF com dígitos repetidos é inválido"
        
    # Cálculo do primeiro dígito verificador
    soma_1 = sum(int(cpf_clean[i]) * (10 - i) for i in range(9))
    resto_1 = (soma_1 * 10) % 11
    digito_1 = 0 if resto_1 == 10 else resto_1
    
    if digito_1 != int(cpf_clean[9]):
        return False, "Dígito verificador do CPF inválido"
        
    # Cálculo do segundo dígito verificador
    soma_2 = sum(int(cpf_clean[i]) * (11 - i) for i in range(10))
    resto_2 = (soma_2 * 10) % 11
    digito_2 = 0 if resto_2 == 10 else resto_2
    
    if digito_2 != int(cpf_clean[10]):
        return False, "Dígito verificador do CPF inválido"
        
    return True, ""

def formatar_cpf_mascara(cpf_clean: str) -> str:
    """
    Aplica a máscara XXX.XXX.XXX-XX para exibição amigável na interface.
    """
    cpf_clean = limpar_cpf(cpf_clean)
    if len(cpf_clean) == 11:
        return f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}"
    return cpf_clean
