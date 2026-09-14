import pandas as pd
from utils.cpf import limpar_cpf, validar_cpf
from utils.datas import validar_data

def validar_base(df: pd.DataFrame, col_map: dict) -> list[dict]:
    """
    Executa a validação linha a linha do DataFrame com base no mapeamento de colunas.
    Não executa exclusão automática por palavras-chave para garantir que nenhum nome real seja descartado.
    """
    col_cpf = col_map.get('cpf')
    col_nome = col_map.get('nome')
    col_dt_nasc = col_map.get('data_nascimento')
    col_bruto = col_map.get('total_bruto')
    col_liquido = col_map.get('total_liquido')
    col_cbo = col_map.get('cbo')
    col_inss = col_map.get('inss')
    
    # Pré-calcula duplicidades de CPF na base
    cpfs = []
    if col_cpf and col_cpf in df.columns:
        for idx, row in df.iterrows():
            c = limpar_cpf(row.get(col_cpf, ""))
            cpfs.append(c)
                
    cpf_counts = pd.Series(cpfs).value_counts().to_dict() if cpfs else {}
    
    cpf_linhas_map = {}
    for idx, cpf in enumerate(cpfs, start=2):
        if cpf:
            cpf_linhas_map.setdefault(cpf, []).append(idx)

    resultados = []
    
    for idx, row in df.iterrows():
        linha_excel = idx + 2
        
        cpf_val = limpar_cpf(row.get(col_cpf, "")) if col_cpf else ""
        nome_val = str(row.get(col_nome, "")).strip() if col_nome and pd.notna(row.get(col_nome)) else ""
        dt_nasc_val = str(row.get(col_dt_nasc, "")).strip() if col_dt_nasc and pd.notna(row.get(col_dt_nasc)) else ""
        bruto_val = str(row.get(col_bruto, "0.00")).strip() if col_bruto and pd.notna(row.get(col_bruto)) else "0.00"
        liquido_val = str(row.get(col_liquido, "0.00")).strip() if col_liquido and pd.notna(row.get(col_liquido)) else "0.00"
        cbo_val = str(row.get(col_cbo, "")).strip() if col_cbo and pd.notna(row.get(col_cbo)) else ""
        inss_val = str(row.get(col_inss, "0.00")).strip() if col_inss and pd.notna(row.get(col_inss)) else "0.00"

        # Fallback Inteligente entre Valor Bruto e Valor Líquido se um deles vier zerado/ausente
        try:
            b_float = float(bruto_val)
        except ValueError:
            b_float = 0.0
            
        try:
            l_float = float(liquido_val)
        except ValueError:
            l_float = 0.0
            
        if b_float == 0.0 and l_float > 0.0:
            bruto_val = f"{l_float:.2f}"
        elif l_float == 0.0 and b_float > 0.0:
            liquido_val = f"{b_float:.2f}"

        erros_criticos = []
        alertas_amarelos = []
        
        # 1. Validação do CPF
        if not cpf_val:
            erros_criticos.append("CPF vazio")
        else:
            is_valid, msg_cpf = validar_cpf(cpf_val)
            if not is_valid:
                erros_criticos.append(f"CPF inválido: {msg_cpf}")
            elif cpf_counts.get(cpf_val, 0) > 1:
                outras_linhas = [str(l) for l in cpf_linhas_map.get(cpf_val, []) if l != linha_excel]
                erros_criticos.append(f"CPF duplicado (aparece também na(s) linha(s) {', '.join(outras_linhas)})")
                
        # 2. Validação do Nome
        if not nome_val:
            erros_criticos.append("Nome do beneficiário é obrigatório e está vazio")
            
        # 3. Validação da Data de Nascimento
        if not dt_nasc_val:
            erros_criticos.append("Data de nascimento é obrigatória e está vazia")
        else:
            is_dt_valid, msg_dt = validar_data(dt_nasc_val)
            if not is_dt_valid:
                erros_criticos.append(f"Data de nascimento inválida: {msg_dt}")
                
        # Define Status
        if erros_criticos:
            status = "🔴 ERRO_CRITICO"
        elif alertas_amarelos:
            status = "🟡 CONFERIR"
        else:
            status = "🟢 OK"
            
        resultados.append({
            'linha': linha_excel,
            'cpf': cpf_val,
            'nome': nome_val,
            'data_nascimento': dt_nasc_val,
            'total_bruto': bruto_val,
            'total_liquido': liquido_val,
            'cbo': cbo_val,
            'inss': inss_val,
            'status': status,
            'erros_criticos': erros_criticos,
            'alertas': alertas_amarelos,
            'aprovado_usuario': False,
            'historico_divergencia': None
        })
        
    return resultados
