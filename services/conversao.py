import pandas as pd

SINONIMOS_ESOCIAL = {
    'cpf': ['cpf', 'cpf_residente', 'n° cpf', 'num_cpf', 'cpf do residente', 'cpf residente'],
    'nome': ['nome', 'nome do residente', 'nome do residente / médico', 'nome do residente / profissional', 'nome completo', 'servidor / residente', 'profissional'],
    'data_nascimento': ['data_nascimento', 'data nascimento', 'data de nascimento', 'dt. nascimento', 'dt_nasc', 'nascimento', 'data nasc'],
    'total_bruto': ['total_bruto', 'valor bruto', 'valor inicial / bolsa (r$)', 'bruto', 'valor bruto (r$)', 'bolsa', 'remuneração bruta', 'valor recebido'],
    'total_liquido': ['total_liquido', 'valor líquido', 'valor liquido', 'líquido', 'liquido', 'valor atualizado (r$)', 'valor liquido (r$)'],
    'cbo': ['cbo', 'código cbo', 'codigo cbo', 'cbo / cargo', 'cbo_codigo', 'cbo residente'],
    'inss': ['inss', 'desconto inss', 'contribuição inss', 'inss (r$)', 'patronal']
}

def auto_detectar_mapeamento(colunas_entrada: list[str]) -> tuple[dict, list[str]]:
    """
    Associa automaticamente as colunas da planilha de entrada aos campos do eSocial
    utilizando a lista estendida de sinônimos estritos.
    """
    col_map = {
        'cpf': None,
        'nome': None,
        'data_nascimento': None,
        'total_bruto': None,
        'total_liquido': None,
        'cbo': None,
        'inss': None
    }
    
    colunas_norm = {col: str(col).strip().lower() for col in colunas_entrada}
    colunas_usadas = set()
    
    # 1. Busca por correspondência exata ou sinônimos
    for campo_esocial, sinonimos in SINONIMOS_ESOCIAL.items():
        for col_orig, norm_orig in colunas_norm.items():
            if norm_orig in sinonimos and col_orig not in colunas_usadas:
                col_map[campo_esocial] = col_orig
                colunas_usadas.add(col_orig)
                break
                
    # 2. Busca por sub-strings para campos não encontrados
    for campo_esocial, sinonimos in SINONIMOS_ESOCIAL.items():
        if col_map[campo_esocial] is None:
            for col_orig, norm_orig in colunas_norm.items():
                if col_orig not in colunas_usadas:
                    if any(sin in norm_orig for sin in sinonimos):
                        col_map[campo_esocial] = col_orig
                        colunas_usadas.add(col_orig)
                        break
                        
    colunas_nao_mapeadas = [c for c in colunas_entrada if c not in colunas_usadas]
    return col_map, colunas_nao_mapeadas

def gerar_dataframe_esocial_final(registros: list[dict]) -> pd.DataFrame:
    """
    Converte a lista de registros liberados no DataFrame final formatado rigorosamente
    conforme as colunas do modelo eSocial:
    ['cpf', 'nome', 'data_nascimento', 'total_bruto', 'total_liquido', 'cbo', 'inss']
    """
    colunas_modelo = ['cpf', 'nome', 'data_nascimento', 'total_bruto', 'total_liquido', 'cbo', 'inss']
    
    linhas_finais = []
    for reg in registros:
        linhas_finais.append({
            'cpf': reg.get('cpf', ''),
            'nome': reg.get('nome', ''),
            'data_nascimento': reg.get('data_nascimento', ''),
            'total_bruto': reg.get('total_bruto', '0.00'),
            'total_liquido': reg.get('total_liquido', '0.00'),
            'cbo': reg.get('cbo', ''),
            'inss': reg.get('inss', '0.00')
        })
        
    df_esocial = pd.DataFrame(linhas_finais, columns=colunas_modelo)
    return df_esocial
