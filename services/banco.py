import sqlite3
import json
import os
import io
import openpyxl
from openpyxl.styles import numbers
import pandas as pd
from utils.cpf import limpar_cpf, validar_cpf
from utils.datas import validar_data
from services.higienizacao import higienizar_texto_nome

DB_PATH = "conversor_esocial.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return conn

def init_db():
    conn = get_connection()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS registros_folha (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            aba TEXT NOT NULL,
            linha INTEGER NOT NULL,
            cpf TEXT,
            nome TEXT,
            data_nascimento TEXT,
            total_bruto REAL DEFAULT 0.0,
            total_liquido REAL DEFAULT 0.0,
            cbo TEXT,
            inss REAL DEFAULT 0.0,
            status TEXT NOT NULL,
            erros_json TEXT,
            alertas_json TEXT,
            aprovado_usuario INTEGER DEFAULT 0,
            historico_json TEXT
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sess_aba ON registros_folha (session_id, aba)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cpf ON registros_folha (session_id, aba, cpf)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS registros_reinf_r4010 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            aba TEXT NOT NULL,
            linha INTEGER NOT NULL,
            cpf TEXT,
            nome TEXT,
            data_fato_gerador TEXT,
            rendimento_bruto REAL DEFAULT 0.0,
            parcela_isenta REAL DEFAULT 0.0,
            observacao_pagamento TEXT,
            status TEXT NOT NULL,
            erros_json TEXT,
            alertas_json TEXT,
            aprovado_usuario INTEGER DEFAULT 0
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reinf_sess_aba ON registros_reinf_r4010 (session_id, aba)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reinf_cpf ON registros_reinf_r4010 (session_id, aba, cpf)")
        conn.commit()
    finally:
        conn.close()

def limpar_banco(session_id: str = None):
    init_db()
    conn = get_connection()
    try:
        if session_id:
            conn.execute("DELETE FROM registros_folha WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM registros_reinf_r4010 WHERE session_id = ?", (session_id,))
        else:
            conn.execute("DELETE FROM registros_folha")
            conn.execute("DELETE FROM registros_reinf_r4010")
        conn.commit()
    finally:
        conn.close()

def salvar_registros_no_banco(session_id: str, aba: str, registros: list[dict]):
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM registros_folha WHERE session_id = ? AND aba = ?", (session_id, aba))
        
        preparados = []
        for r in registros:
            bruto = float(r.get('total_bruto', 0) or 0)
            liquido = float(r.get('total_liquido', 0) or 0)
            inss = float(r.get('inss', 0) or 0)
            
            if bruto == 0.0 and liquido > 0.0:
                bruto = liquido
            elif liquido == 0.0 and bruto > 0.0:
                liquido = bruto
                
            cbo_val = str(r.get('cbo', '') or '').strip()
            if not cbo_val:
                cbo_val = "225125"
                
            preparados.append((
                session_id,
                aba,
                r['linha'],
                r.get('cpf', ''),
                r.get('nome', ''),
                r.get('data_nascimento', ''),
                bruto,
                liquido,
                cbo_val,
                inss,
                r.get('status', '🟢 OK'),
                json.dumps(r.get('erros_criticos', []), ensure_ascii=False),
                json.dumps(r.get('alertas', []), ensure_ascii=False),
                1 if r.get('aprovado_usuario') else 0,
                json.dumps(r.get('historico_divergencia'), ensure_ascii=False) if r.get('historico_divergencia') else None
            ))
            
        conn.executemany("""
        INSERT INTO registros_folha (
            session_id, aba, linha, cpf, nome, data_nascimento,
            total_bruto, total_liquido, cbo, inss, status,
            erros_json, alertas_json, aprovado_usuario, historico_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, preparados)
        conn.commit()
    finally:
        conn.close()

def obter_estatisticas_aba(session_id: str, aba: str) -> dict:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status IN ('🟢 OK', '🟢 CONFERIDO') THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN status = '🟡 CONFERIR' THEN 1 ELSE 0 END) as warn_count,
            SUM(CASE WHEN status = '🔴 ERRO_CRITICO' THEN 1 ELSE 0 END) as danger_count,
            SUM(CASE WHEN status = '⚪ DESCARTADO' THEN 1 ELSE 0 END) as desc_count
        FROM registros_folha
        WHERE session_id = ? AND aba = ?
        """, (session_id, aba))
        row = cur.fetchone()
        return {
            'total': row['total'] or 0,
            'ok': row['ok_count'] or 0,
            'warn': row['warn_count'] or 0,
            'danger': row['danger_count'] or 0,
            'descartados': row['desc_count'] or 0
        }
    finally:
        conn.close()

def obter_registros_banco(session_id: str, aba: str, apenas_pendencias: bool = False, limite: int = 1000) -> list[dict]:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        if apenas_pendencias:
            query = """
            SELECT * FROM registros_folha
            WHERE session_id = ? AND aba = ? AND status IN ('🟡 CONFERIR', '🔴 ERRO_CRITICO')
            ORDER BY linha ASC LIMIT ?
            """
            cur.execute(query, (session_id, aba, limite))
        else:
            query = """
            SELECT * FROM registros_folha
            WHERE session_id = ? AND aba = ?
            ORDER BY linha ASC LIMIT ?
            """
            cur.execute(query, (session_id, aba, limite))
            
        rows = cur.fetchall()
        resultado = []
        for r in rows:
            resultado.append({
                'id': r['id'],
                'linha': r['linha'],
                'cpf': r['cpf'],
                'nome': r['nome'],
                'data_nascimento': r['data_nascimento'],
                'total_bruto': f"{r['total_bruto']:.2f}",
                'total_liquido': f"{r['total_liquido']:.2f}",
                'cbo': r['cbo'],
                'inss': f"{r['inss']:.2f}",
                'status': r['status'],
                'erros_criticos': json.loads(r['erros_json']) if r['erros_json'] else [],
                'alertas': json.loads(r['alertas_json']) if r['alertas_json'] else [],
                'aprovado_usuario': bool(r['aprovado_usuario']),
                'historico_divergencia': json.loads(r['historico_json']) if r['historico_json'] else None
            })
        return resultado
    finally:
        conn.close()

def descartar_todas_pendencias_banco(session_id: str, aba: str) -> int:
    """
    Marca todos os registros com erro ou pendência (🔴 ERRO_CRITICO ou 🟡 CONFERIR)
    da aba atual como ⚪ DESCARTADO em lote. Retorna a quantidade de registros descartados.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        alertas = json.dumps(["Descartado em lote pelo usuário para liberação do arquivo principal"], ensure_ascii=False)
        cur.execute("""
        UPDATE registros_folha
        SET status = '⚪ DESCARTADO', alertas_json = ?
        WHERE session_id = ? AND aba = ? AND status IN ('🔴 ERRO_CRITICO', '🟡 CONFERIR')
        """, (alertas, session_id, aba))
        qtd = cur.rowcount
        conn.commit()
        return qtd
    finally:
        conn.close()

def descartar_todas_pendencias_reinf_banco(session_id: str, aba: str) -> int:
    """
    Marca todos os registros com erro ou pendência (🔴 ERRO_CRITICO ou 🟡 CONFERIR)
    da aba atual do Reinf como ⚪ DESCARTADO em lote. Retorna a quantidade de registros descartados.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        alertas = json.dumps(["Descartado em lote pelo usuário para liberação do arquivo principal"], ensure_ascii=False)
        cur.execute("""
        UPDATE registros_reinf_r4010
        SET status = '⚪ DESCARTADO', alertas_json = ?
        WHERE session_id = ? AND aba = ? AND status IN ('🔴 ERRO_CRITICO', '🟡 CONFERIR')
        """, (alertas, session_id, aba))
        qtd = cur.rowcount
        conn.commit()
        return qtd
    finally:
        conn.close()

def atualizar_registro_banco(registro_id: int, novo_cpf: str, novo_nome: str, nova_data: str,
                             novo_bruto: float, novo_liquido: float, novo_cbo: str, novo_inss: float,
                             acao: str = 'corrigir') -> dict:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        cpf_clean = limpar_cpf(novo_cpf)
        nome_clean = higienizar_texto_nome(novo_nome)
        
        if acao == 'aprovar':
            status = "🟢 CONFERIDO"
            erros = []
            alertas = []
            aprovado = 1
        elif acao == 'descartar':
            status = "⚪ DESCARTADO"
            erros = []
            alertas = ["Linha descartada manualmente pelo usuário"]
            aprovado = 1
        else:
            erros = []
            if not cpf_clean:
                erros.append("CPF vazio")
            else:
                is_valid, msg = validar_cpf(cpf_clean)
                if not is_valid:
                    erros.append(f"CPF inválido: {msg}")
                    
            if not nome_clean:
                erros.append("Nome é obrigatório e está vazio")
                
            if not nova_data:
                erros.append("Data de nascimento é obrigatória e está vazia")
            else:
                is_dt, msg_dt = validar_data(nova_data)
                if not is_dt:
                    erros.append(f"Data de nascimento inválida: {msg_dt}")
                    
            status = "🔴 ERRO_CRITICO" if erros else "🟢 CONFERIDO"
            alertas = []
            aprovado = 1

        cur.execute("""
        UPDATE registros_folha
        SET cpf = ?, nome = ?, data_nascimento = ?, total_bruto = ?, total_liquido = ?,
            cbo = ?, inss = ?, status = ?, erros_json = ?, alertas_json = ?, aprovado_usuario = ?
        WHERE id = ?
        """, (
            cpf_clean, nome_clean, nova_data, novo_bruto, novo_liquido,
            novo_cbo, novo_inss, status, json.dumps(erros, ensure_ascii=False),
            json.dumps(alertas, ensure_ascii=False), aprovado, registro_id
        ))
        conn.commit()
        return {'status': status, 'erros': erros}
    finally:
        conn.close()

def contar_divergencias_pendentes_banco(session_id: str, aba: str) -> int:
    """
    Conta quantos registros ainda pendentes (não aprovados manualmente) possuem
    divergência identificada em relação à folha do mês anterior (Nome e/ou Data
    de Nascimento diferentes).
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT COUNT(*) as qtd FROM registros_folha
        WHERE session_id = ? AND aba = ? AND historico_json IS NOT NULL
              AND aprovado_usuario = 0 AND status IN ('🟡 CONFERIR', '🔴 ERRO_CRITICO')
        """, (session_id, aba))
        row = cur.fetchone()
        return row['qtd'] or 0
    finally:
        conn.close()

def aplicar_correcoes_folha_anterior_banco(session_id: str, aba: str) -> int:
    """
    Aplica em lote, para todos os registros pendentes desta aba com divergência
    identificada, o Nome e a Data de Nascimento vindos da folha do mês anterior
    (já conferida). Revalida cada registro e libera automaticamente os que não
    tiverem mais nenhuma pendência. Retorna a quantidade de registros atualizados.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM registros_folha
        WHERE session_id = ? AND aba = ? AND historico_json IS NOT NULL
              AND aprovado_usuario = 0 AND status IN ('🟡 CONFERIR', '🔴 ERRO_CRITICO')
        """, (session_id, aba))
        candidatos = cur.fetchall()

        qtd = 0
        for atual in candidatos:
            hist = json.loads(atual['historico_json'])
            nome_ant = hist.get('nome_anterior', '') or ''
            dt_ant = hist.get('data_nascimento_anterior', '') or ''

            nome_final = higienizar_texto_nome(nome_ant) if nome_ant else atual['nome']
            dt_final = dt_ant if dt_ant else atual['data_nascimento']

            erros = []
            cpf_clean = atual['cpf']
            if not cpf_clean:
                erros.append("CPF vazio")
            else:
                is_valid, msg = validar_cpf(cpf_clean)
                if not is_valid:
                    erros.append(f"CPF inválido: {msg}")

            if not nome_final:
                erros.append("Nome é obrigatório e está vazio")

            if not dt_final:
                erros.append("Data de nascimento é obrigatória e está vazia")
            else:
                is_dt, msg_dt = validar_data(dt_final)
                if not is_dt:
                    erros.append(f"Data de nascimento inválida: {msg_dt}")

            status = "🔴 ERRO_CRITICO" if erros else "🟢 CONFERIDO"

            cur.execute("""
            UPDATE registros_folha
            SET nome = ?, data_nascimento = ?, status = ?, erros_json = ?, alertas_json = '[]',
                aprovado_usuario = 1, historico_json = NULL
            WHERE id = ?
            """, (nome_final, dt_final, status, json.dumps(erros, ensure_ascii=False), atual['id']))
            qtd += 1

        conn.commit()
        return qtd
    finally:
        conn.close()

def consolidar_folha_suplementar_sqlite(session_id: str, aba: str, aplicar_regra_valores: bool = False, opcao_inss: str = "bruto_igual_liquido", percentual_inss: float = 0.0, cbo_padrao: str = ""):
    """
    Agrupa lançamentos duplicados do mesmo CPF em uma única linha (resolve o erro de
    "CPF duplicado") somando os valores de Bruto/Líquido/INSS dos lançamentos agrupados.

    Por padrão (aplicar_regra_valores=False) os valores somados são mantidos exatamente
    como vieram da planilha original — nada é recalculado. Isso é o esperado quando a
    planilha já chega com Bruto/Líquido/INSS corretos e só é preciso juntar os lançamentos.

    Se aplicar_regra_valores=True, os valores agregados são recalculados conforme:
    - 'bruto_igual_liquido': Define Valor Bruto = Valor Líquido (INSS = 0)
    - 'gross_up_inss': Calcula o Valor Bruto a partir do Líquido aplicando Gross Up:
       Bruto = Líquido / (1 - %INSS) e INSS = Bruto - Líquido.
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        
        cur.execute("""
        SELECT cpf, nome, data_nascimento,
               MAX(NULLIF(TRIM(cbo), '')) as cbo,
               SUM(total_bruto) as soma_bruto,
               SUM(total_liquido) as soma_liquido,
               SUM(inss) as soma_inss,
               COUNT(*) as qtd,
               MIN(linha) as linha_primeira
        FROM registros_folha
        WHERE session_id = ? AND aba = ? AND cpf != '' AND status != '⚪ DESCARTADO'
        GROUP BY cpf
        """, (session_id, aba))
        
        grupos = cur.fetchall()
        
        cur.execute("SELECT * FROM registros_folha WHERE session_id = ? AND aba = ? AND (cpf IS NULL OR cpf = '')", (session_id, aba))
        sem_cpf = cur.fetchall()
        
        cur.execute("DELETE FROM registros_folha WHERE session_id = ? AND aba = ?", (session_id, aba))
        
        novos_registros = []
        for g in grupos:
            bruto_orig = float(g['soma_bruto'] or 0)
            liquido_orig = float(g['soma_liquido'] or 0)
            inss_orig = float(g['soma_inss'] or 0)
            
            if aplicar_regra_valores:
                val_liquido_base = liquido_orig if liquido_orig > 0 else bruto_orig
                if opcao_inss in ('gross_up_inss', 'percentual_inss') and percentual_inss > 0:
                    p_dec = percentual_inss / 100.0
                    if p_dec < 1.0:
                        bruto_calc = round(val_liquido_base / (1.0 - p_dec), 2)
                        inss_calc = round(bruto_calc - val_liquido_base, 2)
                        liquido_calc = val_liquido_base
                    else:
                        bruto_calc = val_liquido_base
                        inss_calc = 0.0
                        liquido_calc = val_liquido_base
                else: # bruto_igual_liquido
                    bruto_calc = val_liquido_base
                    inss_calc = 0.0
                    liquido_calc = val_liquido_base
            else:
                # Mantém os valores originais da planilha: apenas soma os lançamentos do mesmo CPF.
                bruto_calc = round(bruto_orig, 2)
                liquido_calc = round(liquido_orig if liquido_orig > 0 else bruto_orig, 2)
                inss_calc = round(inss_orig, 2)

            cpf_val = g['cpf']
            nome_val = g['nome']
            dt_val = g['data_nascimento']

            # CBO: preserva o CBO já preenchido na planilha; o padrão informado no painel
            # (ou o fallback "225125") só é usado quando a linha não tem CBO nenhum.
            cbo_val = str(g['cbo'] or "").strip() or str(cbo_padrao).strip() or "225125"
            
            erros = []
            is_v, msg_c = validar_cpf(cpf_val)
            if not is_v:
                erros.append(f"CPF inválido: {msg_c}")
            if not nome_val:
                erros.append("Nome é obrigatório")
            if not dt_val:
                erros.append("Data de nascimento é obrigatória")
            else:
                is_dt, msg_d = validar_data(dt_val)
                if not is_dt:
                    erros.append(f"Data inválida: {msg_d}")
                    
            status = "🔴 ERRO_CRITICO" if erros else "🟢 OK"
            
            novos_registros.append((
                session_id, aba, g['linha_primeira'], cpf_val, nome_val, dt_val,
                bruto_calc, liquido_calc, cbo_val, inss_calc, status,
                json.dumps(erros, ensure_ascii=False), json.dumps([]), 0, None
            ))

        for sc in sem_cpf:
            cbo_sc = str(cbo_padrao).strip() if cbo_padrao else str(sc['cbo'] or "").strip()
            novos_registros.append((
                session_id, aba, sc['linha'], sc['cpf'], sc['nome'], sc['data_nascimento'],
                sc['total_bruto'], sc['total_liquido'], cbo_sc, sc['inss'], sc['status'],
                sc['erros_json'], sc['alertas_json'], sc['aprovado_usuario'], sc['historico_json']
            ))

        cur.executemany("""
        INSERT INTO registros_folha (
            session_id, aba, linha, cpf, nome, data_nascimento,
            total_bruto, total_liquido, cbo, inss, status,
            erros_json, alertas_json, aprovado_usuario, historico_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, novos_registros)
        conn.commit()
    finally:
        conn.close()

def exportar_registros_banco_para_list(session_id: str, aba: str) -> list[dict]:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM registros_folha
        WHERE session_id = ? AND aba = ? AND status IN ('🟢 OK', '🟢 CONFERIDO')
        ORDER BY linha ASC
        """, (session_id, aba))
        rows = cur.fetchall()
        resultado = []
        for r in rows:
            resultado.append({
                'id': r['id'],
                'linha': r['linha'],
                'cpf': r['cpf'],
                'nome': r['nome'],
                'data_nascimento': r['data_nascimento'],
                'total_bruto': f"{r['total_bruto']:.2f}",
                'total_liquido': f"{r['total_liquido']:.2f}",
                'cbo': r['cbo'],
                'inss': f"{r['inss']:.2f}",
                'status': r['status']
            })
        return resultado
    finally:
        conn.close()

def gerar_relatorio_inconsistencias_bytes(session_id: str, aba: str) -> bytes:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT linha, cpf, nome, data_nascimento, total_bruto, total_liquido, status, erros_json, alertas_json
        FROM registros_folha
        WHERE session_id = ? AND aba = ? AND status IN ('🔴 ERRO_CRITICO', '🟡 CONFERIR', '⚪ DESCARTADO')
        ORDER BY linha ASC
        """, (session_id, aba))
        rows = cur.fetchall()
        
        dados = []
        for r in rows:
            erros = json.loads(r['erros_json']) if r['erros_json'] else []
            alertas = json.loads(r['alertas_json']) if r['alertas_json'] else []
            detalhes = " | ".join(erros + alertas)
            dados.append({
                'Linha Excel': r['linha'],
                'CPF': r['cpf'],
                'Nome': r['nome'],
                'Data Nascimento': r['data_nascimento'],
                'Valor Bruto': r['total_bruto'],
                'Valor Líquido': r['total_liquido'],
                'Status': r['status'],
                'Motivo / Inconsistência': detalhes
            })
            
    finally:
        conn.close()
            
    df_inc = pd.DataFrame(dados)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inconsistencias"
    
    if not dados:
        ws.append(["Nenhuma inconsistência encontrada nesta aba."])
    else:
        ws.append(list(df_inc.columns))
        for r in df_inc.itertuples(index=False):
            ws.append(list(r))
            
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# -----------------------------------------------------------------------------
# FUNÇÕES ESPECÍFICAS PARA O MÓDULO EFD-REINF (R-4010)
# -----------------------------------------------------------------------------

def salvar_registros_reinf_no_banco(session_id: str, aba: str, registros: list[dict]):
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM registros_reinf_r4010 WHERE session_id = ? AND aba = ?", (session_id, aba))
        
        preparados = []
        for r in registros:
            bruto = float(r.get('rendimento_bruto', 0) or 0)
            isento = float(r.get('parcela_isenta', 0) or 0)
            
            preparados.append((
                session_id,
                aba,
                r['linha'],
                r.get('cpf', ''),
                r.get('nome', ''),
                r.get('data_fato_gerador', ''),
                bruto,
                isento,
                r.get('observacao_pagamento', ''),
                r.get('status', '🟢 OK'),
                json.dumps(r.get('erros_criticos', []), ensure_ascii=False),
                json.dumps(r.get('alertas', []), ensure_ascii=False),
                1 if r.get('aprovado_usuario') else 0
            ))
            
        conn.executemany("""
        INSERT INTO registros_reinf_r4010 (
            session_id, aba, linha, cpf, nome, data_fato_gerador,
            rendimento_bruto, parcela_isenta, observacao_pagamento, status,
            erros_json, alertas_json, aprovado_usuario
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, preparados)
        conn.commit()
    finally:
        conn.close()

def obter_estatisticas_reinf_aba(session_id: str, aba: str) -> dict:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status IN ('🟢 OK', '🟢 CONFERIDO') THEN 1 ELSE 0 END) as ok_count,
            SUM(CASE WHEN status = '🟡 CONFERIR' THEN 1 ELSE 0 END) as warn_count,
            SUM(CASE WHEN status = '🔴 ERRO_CRITICO' THEN 1 ELSE 0 END) as danger_count,
            SUM(CASE WHEN status = '⚪ DESCARTADO' THEN 1 ELSE 0 END) as desc_count
        FROM registros_reinf_r4010
        WHERE session_id = ? AND aba = ?
        """, (session_id, aba))
        row = cur.fetchone()
        return {
            'total': row['total'] or 0,
            'ok': row['ok_count'] or 0,
            'warn': row['warn_count'] or 0,
            'danger': row['danger_count'] or 0,
            'descartados': row['desc_count'] or 0
        }
    finally:
        conn.close()

def obter_registros_reinf_banco(session_id: str, aba: str, apenas_pendencias: bool = False, limite: int = 1000) -> list[dict]:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        if apenas_pendencias:
            query = """
            SELECT * FROM registros_reinf_r4010
            WHERE session_id = ? AND aba = ? AND status IN ('🟡 CONFERIR', '🔴 ERRO_CRITICO')
            ORDER BY linha ASC LIMIT ?
            """
            cur.execute(query, (session_id, aba, limite))
        else:
            query = """
            SELECT * FROM registros_reinf_r4010
            WHERE session_id = ? AND aba = ?
            ORDER BY linha ASC LIMIT ?
            """
            cur.execute(query, (session_id, aba, limite))
            
        rows = cur.fetchall()
        resultado = []
        for r in rows:
            resultado.append({
                'id': r['id'],
                'linha': r['linha'],
                'cpf': r['cpf'],
                'nome': r['nome'],
                'data_fato_gerador': r['data_fato_gerador'],
                'rendimento_bruto': f"{r['rendimento_bruto']:.2f}",
                'parcela_isenta': f"{r['parcela_isenta']:.2f}",
                'observacao_pagamento': r['observacao_pagamento'],
                'status': r['status'],
                'erros_criticos': json.loads(r['erros_json']) if r['erros_json'] else [],
                'alertas': json.loads(r['alertas_json']) if r['alertas_json'] else [],
                'aprovado_usuario': bool(r['aprovado_usuario'])
            })
        return resultado
    finally:
        conn.close()

def atualizar_registro_reinf_banco(registro_id: int, novo_cpf: str, nova_data: str,
                                   novo_bruto: float, nova_isenta: float, nova_obs: str,
                                   acao: str = 'corrigir') -> dict:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cpf_clean = limpar_cpf(novo_cpf)
        
        if acao == 'aprovar':
            status = "🟢 CONFERIDO"
            erros = []
            alertas = []
            aprovado = 1
        elif acao == 'descartar':
            status = "⚪ DESCARTADO"
            erros = []
            alertas = ["Linha descartada manualmente pelo usuário"]
            aprovado = 1
        else:
            erros = []
            if not cpf_clean:
                erros.append("CPF vazio")
            else:
                is_valid, msg = validar_cpf(cpf_clean)
                if not is_valid:
                    erros.append(f"CPF inválido: {msg}")
                    
            if not nova_data:
                erros.append("Data do fato gerador é obrigatória")
            else:
                is_dt, msg_dt = validar_data(nova_data)
                if not is_dt:
                    erros.append(f"Data inválida: {msg_dt}")
                    
            status = "🔴 ERRO_CRITICO" if erros else "🟢 CONFERIDO"
            alertas = []
            aprovado = 1

        cur.execute("""
        UPDATE registros_reinf_r4010
        SET cpf = ?, data_fato_gerador = ?, rendimento_bruto = ?, parcela_isenta = ?,
            observacao_pagamento = ?, status = ?, erros_json = ?, alertas_json = ?, aprovado_usuario = ?
        WHERE id = ?
        """, (
            cpf_clean, nova_data, novo_bruto, nova_isenta,
            nova_obs, status, json.dumps(erros, ensure_ascii=False),
            json.dumps(alertas, ensure_ascii=False), aprovado, registro_id
        ))
        conn.commit()
        return {'status': status, 'erros': erros}
    finally:
        conn.close()

def exportar_registros_reinf_banco_para_list(session_id: str, aba: str) -> list[dict]:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM registros_reinf_r4010
        WHERE session_id = ? AND aba = ? AND status IN ('🟢 OK', '🟢 CONFERIDO')
        ORDER BY linha ASC
        """, (session_id, aba))
        rows = cur.fetchall()
        resultado = []
        for r in rows:
            resultado.append({
                'id': r['id'],
                'linha': r['linha'],
                'cpf': r['cpf'],
                'nome': r['nome'],
                'data_fato_gerador': r['data_fato_gerador'],
                'rendimento_bruto': f"{r['rendimento_bruto']:.2f}",
                'parcela_isenta': f"{r['parcela_isenta']:.2f}",
                'observacao_pagamento': r['observacao_pagamento'],
                'status': r['status']
            })
        return resultado
    finally:
        conn.close()

def gerar_relatorio_inconsistencias_reinf_bytes(session_id: str, aba: str) -> bytes:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
        SELECT linha, cpf, nome, data_fato_gerador, rendimento_bruto, parcela_isenta, observacao_pagamento, status, erros_json, alertas_json
        FROM registros_reinf_r4010
        WHERE session_id = ? AND aba = ? AND status IN ('🔴 ERRO_CRITICO', '🟡 CONFERIR', '⚪ DESCARTADO')
        ORDER BY linha ASC
        """, (session_id, aba))
        rows = cur.fetchall()
        
        dados = []
        for r in rows:
            erros = json.loads(r['erros_json']) if r['erros_json'] else []
            alertas = json.loads(r['alertas_json']) if r['alertas_json'] else []
            detalhes = " | ".join(erros + alertas)
            dados.append({
                'Linha Excel': r['linha'],
                'CPF': r['cpf'],
                'Nome': r['nome'],
                'Data Fato Gerador': r['data_fato_gerador'],
                'Rendimento Bruto': r['rendimento_bruto'],
                'Parcela Isenta': r['parcela_isenta'],
                'Observação': r['observacao_pagamento'],
                'Status': r['status'],
                'Motivo / Inconsistência': detalhes
            })
            
    finally:
        conn.close()
            
    df_inc = pd.DataFrame(dados)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inconsistencias_Reinf"
    
    if not dados:
        ws.append(["Nenhuma inconsistência encontrada nesta aba."])
    else:
        ws.append(list(df_inc.columns))
        for r in df_inc.itertuples(index=False):
            ws.append(list(r))
            
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
