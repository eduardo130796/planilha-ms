import pandas as pd
from utils.cpf import limpar_cpf
from utils.datas import normalizar_data
from services.higienizacao import higienizar_texto_nome

def comparar_com_folha_anterior(registros_atuais: list[dict], df_anterior: pd.DataFrame, col_map_anterior: dict) -> list[dict]:
    """
    Cruza a folha atual com a folha do mês anterior usando CPF como chave principal.
    Identifica alterações em Nome e Data de Nascimento.
    col_map_anterior é da forma {'cpf': 'CPF', 'nome': 'Nome', ...}
    """
    col_cpf = col_map_anterior.get('cpf')
    col_nome = col_map_anterior.get('nome')
    col_dt_nasc = col_map_anterior.get('data_nascimento')
    
    if not col_cpf or col_cpf not in df_anterior.columns:
        return registros_atuais
        
    # Constrói dicionário de busca por CPF na folha anterior
    mapa_anterior = {}
    for _, row in df_anterior.iterrows():
        cpf_ant = limpar_cpf(row.get(col_cpf, ""))
        if cpf_ant:
            nome_ant = higienizar_texto_nome(row.get(col_nome, "")) if col_nome else ""
            dt_nasc_ant = normalizar_data(row.get(col_dt_nasc, "")) if col_dt_nasc else ""
            mapa_anterior[cpf_ant] = {
                'nome': nome_ant,
                'data_nascimento': dt_nasc_ant
            }
            
    registros_comparados = []
    
    for reg in registros_atuais:
        cpf_atual = reg['cpf']
        reg_copy = reg.copy()
        
        if cpf_atual and cpf_atual in mapa_anterior:
            dado_ant = mapa_anterior[cpf_atual]
            divergencias = []
            
            # Comparação de Nome
            if dado_ant['nome'] and reg_copy['nome'] and dado_ant['nome'] != reg_copy['nome']:
                divergencias.append(
                    f"🟡 Divergência de nome (Anterior: '{dado_ant['nome']}' | Atual: '{reg_copy['nome']}')"
                )
                
            # Comparação de Data de Nascimento
            if dado_ant['data_nascimento'] and reg_copy['data_nascimento'] and dado_ant['data_nascimento'] != reg_copy['data_nascimento']:
                divergencias.append(
                    f"🔴 Divergência de data de nascimento (Anterior: '{dado_ant['data_nascimento']}' | Atual: '{reg_copy['data_nascimento']}')"
                )
                
            if divergencias:
                reg_copy['historico_divergencia'] = {
                    'nome_anterior': dado_ant['nome'],
                    'data_nascimento_anterior': dado_ant['data_nascimento'],
                    'divergencias': divergencias
                }
                
                # Atualiza os alertas e status se o usuário ainda não tiver aprovado
                if not reg_copy['aprovado_usuario']:
                    tem_erro_vermelho = any("🔴" in d for d in divergencias)
                    if tem_erro_vermelho and reg_copy['status'] != "🔴 ERRO_CRITICO":
                        reg_copy['status'] = "🔴 ERRO_CRITICO"
                        reg_copy['erros_criticos'].extend([d for d in divergencias if "🔴" in d])
                    elif not tem_erro_vermelho and reg_copy['status'] == "🟢 OK":
                        reg_copy['status'] = "🟡 CONFERIR"
                        reg_copy['alertas'].extend([d for d in divergencias if "🟡" in d])
                        
        registros_comparados.append(reg_copy)
        
    return registros_comparados
