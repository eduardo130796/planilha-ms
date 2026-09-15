from datetime import datetime
import pandas as pd
from utils.cpf import limpar_cpf, validar_cpf
from utils.datas import validar_data, normalizar_data
from services.higienizacao import higienizar_texto_nome

SINONIMOS_REINF_R4010 = {
    'cpf': ['cpf', 'cpf_residente', 'n° cpf', 'num_cpf', 'cpf do residente', 'cpf residente'],
    'data_fato_gerador': ['data_fato_gerador', 'data fato gerador', 'fato gerador', 'data ob', 'data_ob', 'data da ob', 'data crédito em conta', 'data credito', 'data_credito', 'data_pagamento', 'data pagamento', 'dt_pgto', 'data', 'data de pagamento'],
    'rendimento_bruto': ['rendimento_bruto', 'rendimento bruto', 'total_bruto', 'valor bruto', 'valor líquido', 'valor liquido', 'bolsa', 'bruto', 'valor recebido', 'valor atualizado (r$)', 'valor líquido (r$)', 'valor'],
    'parcela_isenta': ['parcela_isenta', 'parcela isenta', 'isento', 'valor_isento', 'valor isento', 'rendimento_isento', 'rendimento isento'],
    'observacao_pagamento': ['observacao_pagamento', 'observacao pagamento', 'observacao', 'observação', 'obs', 'tipo residência', 'tipo residencia', 'competência', 'competencia', 'ordem bancária', 'ordem bancaria', 'protocolo singular', 'ordenação de despesa', 'finalidade']
}

def auto_detectar_mapeamento_reinf(colunas_entrada: list[str]) -> tuple[dict, list[str]]:
    """
    Associa automaticamente as colunas da planilha de entrada aos campos do EFD-Reinf R-4010.
    """
    col_map = {
        'cpf': None,
        'data_fato_gerador': None,
        'rendimento_bruto': None,
        'parcela_isenta': None,
        'observacao_pagamento': None
    }
    
    colunas_norm = {col: str(col).strip().lower() for col in colunas_entrada}
    colunas_usadas = set()
    
    # 1. Busca por correspondência exata ou sinônimos
    for campo_reinf, sinonimos in SINONIMOS_REINF_R4010.items():
        for col_orig, norm_orig in colunas_norm.items():
            if norm_orig in sinonimos and col_orig not in colunas_usadas:
                col_map[campo_reinf] = col_orig
                colunas_usadas.add(col_orig)
                break
                
    # 2. Busca por sub-strings para campos não encontrados
    for campo_reinf, sinonimos in SINONIMOS_REINF_R4010.items():
        if col_map[campo_reinf] is None:
            for col_orig, norm_orig in colunas_norm.items():
                if col_orig not in colunas_usadas:
                    if any(sin in norm_orig for sin in sinonimos):
                        col_map[campo_reinf] = col_orig
                        colunas_usadas.add(col_orig)
                        break
                        
    colunas_nao_mapeadas = [c for c in colunas_entrada if c not in colunas_usadas]
    return col_map, colunas_nao_mapeadas

def mapear_colunas_com_prioridade(colunas_entrada: list[str], mapeamento_prioritario: dict) -> tuple[dict, list[str]]:
    """
    Mapeia as colunas dando prioridade a nomes exatos conhecidos de um modelo específico
    de planilha (ex.: Auxílio Moradia), e usa a detecção automática genérica como reforço
    para os campos que não constarem no mapeamento prioritário — evitando ambiguidades
    da lista genérica de sinônimos (ex.: 'Ordem Bancária' também é sinônimo genérico de
    observação, mas não deve vencer 'Finalidade' num modelo que já define isso).
    `mapeamento_prioritario` é da forma {'campo_saida': ['Nome Exato 1', 'Nome Exato 2']}.
    """
    colunas_norm = {col: str(col).strip().lower() for col in colunas_entrada}
    col_map = {
        'cpf': None,
        'data_fato_gerador': None,
        'rendimento_bruto': None,
        'parcela_isenta': None,
        'observacao_pagamento': None
    }
    colunas_usadas = set()

    for campo, candidatos in mapeamento_prioritario.items():
        candidatos_norm = [str(c).strip().lower() for c in candidatos]
        for col_orig, norm_orig in colunas_norm.items():
            if norm_orig in candidatos_norm and col_orig not in colunas_usadas:
                col_map[campo] = col_orig
                colunas_usadas.add(col_orig)
                break

    colunas_restantes = [c for c in colunas_entrada if c not in colunas_usadas]
    col_map_auto, _ = auto_detectar_mapeamento_reinf(colunas_restantes)
    for campo, valor in col_map_auto.items():
        if col_map[campo] is None and valor is not None:
            col_map[campo] = valor
            colunas_usadas.add(valor)

    colunas_nao_mapeadas = [c for c in colunas_entrada if c not in colunas_usadas]
    return col_map, colunas_nao_mapeadas

def validar_base_reinf(df: pd.DataFrame, col_map: dict) -> list[dict]:
    """
    Executa a validação linha a linha para a base EFD-Reinf R-4010.
    """
    col_cpf = col_map.get('cpf')
    col_dt_fg = col_map.get('data_fato_gerador')
    col_bruto = col_map.get('rendimento_bruto')
    col_isento = col_map.get('parcela_isenta')
    col_obs = col_map.get('observacao_pagamento')
    
    cpfs = []
    if col_cpf and col_cpf in df.columns:
        for idx, row in df.iterrows():
            c = limpar_cpf(row.get(col_cpf, ""))
            cpfs.append(c)
                
    resultados = []
    for idx, row in df.iterrows():
        linha_excel = idx + 2
        
        cpf_val = limpar_cpf(row.get(col_cpf, "")) if col_cpf else ""
        dt_fg_val = normalizar_data(row.get(col_dt_fg, "")) if col_dt_fg and pd.notna(row.get(col_dt_fg)) else ""
        bruto_val = str(row.get(col_bruto, "0.00")).strip() if col_bruto and pd.notna(row.get(col_bruto)) else "0.00"
        isento_val = str(row.get(col_isento, "0.00")).strip() if col_isento and pd.notna(row.get(col_isento)) else "0.00"
        obs_val = str(row.get(col_obs, "")).strip() if col_obs and pd.notna(row.get(col_obs)) else ""
        
        nome_val = str(row.get('Nome', row.get('nome', ''))).strip() if pd.notna(row.get('Nome', row.get('nome', ''))) else ""

        try:
            b_float = float(bruto_val)
        except ValueError:
            b_float = 0.0
            bruto_val = "0.00"

        try:
            i_float = float(isento_val)
        except ValueError:
            i_float = 0.0
            isento_val = "0.00"

        erros_criticos = []
        alertas_amarelos = []
        
        # 1. Validação do CPF
        if not cpf_val:
            erros_criticos.append("CPF vazio")
        else:
            is_valid, msg_cpf = validar_cpf(cpf_val)
            if not is_valid:
                erros_criticos.append(f"CPF inválido: {msg_cpf}")
                
        # 2. Validação da Data do Fato Gerador
        if not dt_fg_val:
            erros_criticos.append("Data do Fato Gerador é obrigatória e está vazia")
        else:
            is_dt_valid, msg_dt = validar_data(dt_fg_val)
            if not is_dt_valid:
                erros_criticos.append(f"Data do fato gerador inválida: {msg_dt}")
                
        status = "🔴 ERRO_CRITICO" if erros_criticos else "🟢 OK"
            
        resultados.append({
            'linha': linha_excel,
            'cpf': cpf_val,
            'nome': nome_val,
            'data_fato_gerador': dt_fg_val,
            'rendimento_bruto': f"{b_float:.2f}",
            'parcela_isenta': f"{i_float:.2f}",
            'observacao_pagamento': obs_val,
            'status': status,
            'erros_criticos': erros_criticos,
            'alertas': alertas_amarelos
        })
        
    return resultados

def calcular_competencia(data_fato_gerador: str) -> str:
    """
    Deriva a competência (AAAA-MM) a partir da Data do Fato Gerador (DD/MM/YYYY).
    Registros sem data válida caem na competência 'SEM_DATA' para não serem perdidos.
    """
    try:
        dt = datetime.strptime(str(data_fato_gerador).strip(), '%d/%m/%Y')
        return dt.strftime('%Y-%m')
    except (ValueError, TypeError):
        return "SEM_DATA"

def dividir_registros_por_competencia(registros: list[dict]) -> dict[str, list[dict]]:
    """
    Agrupa registros do EFD-Reinf já validados pela competência derivada da Data do
    Fato Gerador. Útil quando a planilha de origem traz vários meses "achatados" em uma
    única lista (ex.: auxílio-moradia), permitindo tratar cada competência como se fosse
    uma aba independente no restante da conferência.
    """
    grupos: dict[str, list[dict]] = {}
    for reg in registros:
        competencia = calcular_competencia(reg.get('data_fato_gerador', ''))
        grupos.setdefault(competencia, []).append(reg)
    return grupos

def gerar_dataframe_reinf_final(registros: list[dict]) -> pd.DataFrame:
    """
    Converte os registros liberados do Reinf R-4010 no DataFrame final.
    Colunas: ['cpf', 'data_fato_gerador', 'rendimento_bruto', 'parcela_isenta', 'observacao_pagamento']
    """
    colunas_modelo = ['cpf', 'data_fato_gerador', 'rendimento_bruto', 'parcela_isenta', 'observacao_pagamento']
    
    linhas_finais = []
    for reg in registros:
        linhas_finais.append({
            'cpf': reg.get('cpf', ''),
            'data_fato_gerador': reg.get('data_fato_gerador', ''),
            'rendimento_bruto': reg.get('rendimento_bruto', '0.00'),
            'parcela_isenta': reg.get('parcela_isenta', '0.00'),
            'observacao_pagamento': reg.get('observacao_pagamento', '')
        })
        
    return pd.DataFrame(linhas_finais, columns=colunas_modelo)
