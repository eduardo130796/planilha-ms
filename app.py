import streamlit as st
import pandas as pd
import uuid
import io

from services.leitor_excel import analisar_arquivo_excel_rapido, carregar_dados_aba_cached
from services.higienizacao import higienizar_dataframe
from services.validacao import validar_base
from services.comparacao import comparar_com_folha_anterior
from services.conversao import auto_detectar_mapeamento, gerar_dataframe_esocial_final
from services.reinf import auto_detectar_mapeamento_reinf, validar_base_reinf, gerar_dataframe_reinf_final
from services.exportacao import gerar_nome_arquivo, gerar_pacote_zip_arquivos, validar_arquivo_final_exportado
from services.banco import (
    init_db, limpar_banco, salvar_registros_no_banco,
    obter_estatisticas_aba, obter_registros_banco,
    atualizar_registro_banco, consolidar_folha_suplementar_sqlite,
    exportar_registros_banco_para_list, gerar_relatorio_inconsistencias_bytes,
    salvar_registros_reinf_no_banco, obter_estatisticas_reinf_aba,
    obter_registros_reinf_banco, atualizar_registro_reinf_banco,
    exportar_registros_reinf_banco_para_list, gerar_relatorio_inconsistencias_reinf_bytes,
    descartar_todas_pendencias_banco, descartar_todas_pendencias_reinf_banco
)
from utils.excel import gerar_excel_esocial
from utils.cpf import formatar_cpf_mascara

# Configuração da Página
st.set_page_config(
    page_title="Conversor eSocial & EFD-Reinf",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
        max-width: 1350px;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        color: #F8FAFC;
        padding: 20px 26px;
        border-radius: 12px;
        margin-bottom: 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
    .main-header h1 {
        color: #FFFFFF;
        font-size: 2.0rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .main-header p {
        color: #94A3B8;
        font-size: 1.0rem;
        margin: 0;
    }

    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 14px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .metric-card .value {
        font-size: 1.55rem;
        font-weight: 700;
    }
    .metric-card .label {
        font-size: 0.80rem;
        color: #64748B;
        font-weight: 500;
        margin-top: 2px;
    }
    .val-ok { color: #16A34A; }
    .val-warn { color: #D97706; }
    .val-danger { color: #DC2626; }
    .val-desc { color: #64748B; }
    .val-total { color: #2563EB; }
</style>
""", unsafe_allow_html=True)

# Inicializa Banco Local SQLite
init_db()

# Session State
if 'session_id' not in st.session_state:
    st.session_state['session_id'] = str(uuid.uuid4())
if 'folha_bytes' not in st.session_state:
    st.session_state['folha_bytes'] = None
if 'folha_nome' not in st.session_state:
    st.session_state['folha_nome'] = None
if 'reinf_bytes' not in st.session_state:
    st.session_state['reinf_bytes'] = None
if 'reinf_nome' not in st.session_state:
    st.session_state['reinf_nome'] = None
if 'folha_anterior_bytes' not in st.session_state:
    st.session_state['folha_anterior_bytes'] = None
if 'folha_anterior_nome' not in st.session_state:
    st.session_state['folha_anterior_nome'] = None
if 'abas_processadas_db' not in st.session_state:
    st.session_state['abas_processadas_db'] = set()
if 'abas_processadas_reinf_db' not in st.session_state:
    st.session_state['abas_processadas_reinf_db'] = set()
if 'abas_selecionadas' not in st.session_state:
    st.session_state['abas_selecionadas'] = []
if 'arquivos_gerados_cache' not in st.session_state:
    st.session_state['arquivos_gerados_cache'] = {}

# Funções Auxiliares de Carregamento
def carregar_e_salvar_aba_no_banco(aba_nome, file_bytes, df_anterior_raw=None, col_map_ant=None):
    session_id = st.session_state['session_id']
    df_raw = carregar_dados_aba_cached(file_bytes, aba_nome)
    col_map, _ = auto_detectar_mapeamento(list(df_raw.columns))
    
    df_hig = higienizar_dataframe(df_raw, col_map)
    registros = validar_base(df_hig, col_map)
    
    if df_anterior_raw is not None and col_map_ant is not None:
        df_ant_hig = higienizar_dataframe(df_anterior_raw, col_map_ant)
        registros = comparar_com_folha_anterior(registros, df_ant_hig, col_map_ant)
        
    salvar_registros_no_banco(session_id, aba_nome, registros)
    st.session_state['abas_processadas_db'].add(aba_nome)

def carregar_e_salvar_reinf_aba_no_banco(aba_nome, file_bytes):
    session_id = st.session_state['session_id']
    df_raw = carregar_dados_aba_cached(file_bytes, aba_nome)
    col_map, _ = auto_detectar_mapeamento_reinf(list(df_raw.columns))
    
    registros = validar_base_reinf(df_raw, col_map)
    salvar_registros_reinf_no_banco(session_id, aba_nome, registros)
    st.session_state['abas_processadas_reinf_db'].add(aba_nome)

# --- MENU LATERAL ---
with st.sidebar:
    st.markdown("## 📌 Módulo do Sistema")
    modulo_selecionado = st.radio(
        "Selecione o módulo de conversão:",
        options=[
            "📄 eSocial (S-1200 / S-1210)",
            "📑 EFD-Reinf (R-4010)"
        ],
        index=0,
        key="radio_modulo"
    )
    st.divider()

    if modulo_selecionado == "📄 eSocial (S-1200 / S-1210)":
        st.subheader("1. Upload Folha eSocial (.xlsx)")
        arquivo_folha = st.file_uploader("Upload da Folha Atual (.xlsx)", type=["xlsx"], key="file_folha_atual")
        
        if arquivo_folha is not None:
            if st.session_state['folha_nome'] != arquivo_folha.name or st.session_state['folha_bytes'] is None:
                st.session_state['folha_bytes'] = arquivo_folha.getvalue()
                st.session_state['folha_nome'] = arquivo_folha.name
                st.session_state['abas_processadas_db'] = set()
                st.session_state['arquivos_gerados_cache'] = {}
                limpar_banco(st.session_state['session_id'])
                
        st.divider()
        st.subheader("2. Folha Anterior (Opcional)")
        arquivo_anterior = st.file_uploader("Upload Folha Anterior (.xlsx)", type=["xlsx"], key="file_folha_ant")
        
        if arquivo_anterior is not None:
            if st.session_state['folha_anterior_nome'] != arquivo_anterior.name:
                st.session_state['folha_anterior_bytes'] = arquivo_anterior.getvalue()
                st.session_state['folha_anterior_nome'] = arquivo_anterior.name
                st.session_state['abas_processadas_db'] = set()
                st.session_state['arquivos_gerados_cache'] = {}
                limpar_banco(st.session_state['session_id'])
        elif st.session_state['folha_anterior_bytes'] is not None and arquivo_anterior is None:
            st.session_state['folha_anterior_bytes'] = None
            st.session_state['folha_anterior_nome'] = None
            st.session_state['abas_processadas_db'] = set()
            st.session_state['arquivos_gerados_cache'] = {}
            limpar_banco(st.session_state['session_id'])
    else:
        st.subheader("1. Upload Planilha EFD-Reinf (.xlsx)")
        arquivo_reinf = st.file_uploader("Upload do Arquivo R-4010 (.xlsx)", type=["xlsx"], key="file_reinf_atual")
        
        if arquivo_reinf is not None:
            if st.session_state['reinf_nome'] != arquivo_reinf.name or st.session_state['reinf_bytes'] is None:
                st.session_state['reinf_bytes'] = arquivo_reinf.getvalue()
                st.session_state['reinf_nome'] = arquivo_reinf.name
                st.session_state['abas_processadas_reinf_db'] = set()
                st.session_state['arquivos_gerados_cache'] = {}
                limpar_banco(st.session_state['session_id'])

    st.divider()
    if st.button("🗑️ Limpar Sessão / Nova Planilha", use_container_width=True):
        limpar_banco(st.session_state['session_id'])
        st.session_state['folha_bytes'] = None
        st.session_state['folha_nome'] = None
        st.session_state['reinf_bytes'] = None
        st.session_state['reinf_nome'] = None
        st.session_state['abas_processadas_db'] = set()
        st.session_state['abas_processadas_reinf_db'] = set()
        st.session_state['arquivos_gerados_cache'] = {}
        st.rerun()

# -----------------------------------------------------------------------------
# MÓDULO 1: eSocial (S-1200 / S-1210)
# -----------------------------------------------------------------------------
if modulo_selecionado == "📄 eSocial (S-1200 / S-1210)":
    st.markdown("""
    <div class="main-header">
        <h1>Conversor eSocial – Folha Ordinária & Suplementar (S-1200 / S-1210)</h1>
        <p>Conversão ultrarrápida (motor Calamine 12x mais rápido), descarte manual de pendências e relatório de inconsistências.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state['folha_bytes'] is None:
        st.info("👈 Selecione o arquivo da **Folha Ordinária / Suplementar (.xlsx)** no menu lateral para iniciar.")
    else:
        file_bytes = st.session_state['folha_bytes']
        session_id = st.session_state['session_id']
        
        analise_meta = analisar_arquivo_excel_rapido(file_bytes)
        abas_disponiveis = analise_meta['abas_nomes']
        
        st.markdown(f"""
        **Arquivo:** `{st.session_state['folha_nome']}` &nbsp;|&nbsp; 
        **Abas encontradas:** `{analise_meta['total_abas']}`
        """)
        
        df_anterior_raw = None
        col_map_ant = None
        if st.session_state['folha_anterior_bytes'] is not None:
            ant_bytes = st.session_state['folha_anterior_bytes']
            meta_ant = analisar_arquivo_excel_rapido(ant_bytes)
            if meta_ant['total_abas'] > 0:
                primeira_aba_ant = meta_ant['abas_nomes'][0]
                df_anterior_raw = carregar_dados_aba_cached(ant_bytes, primeira_aba_ant)
                col_map_ant, _ = auto_detectar_mapeamento(list(df_anterior_raw.columns))
                st.success(f" Folha anterior `{st.session_state['folha_anterior_nome']}` ativa para conferência histórica.")

        st.write("")
        
        if analise_meta['total_abas'] == 1:
            aba_atual = abas_disponiveis[0]
        else:
            aba_atual = st.selectbox(
                "📂 **Qual aba você deseja abrir?**",
                options=abas_disponiveis,
                index=0,
                key="seletor_aba_principal"
            )
            
        st.session_state['abas_selecionadas'] = [aba_atual]

        if aba_atual not in st.session_state['abas_processadas_db']:
            carregar_e_salvar_aba_no_banco(aba_atual, file_bytes, df_anterior_raw, col_map_ant)

        with st.expander("⚙️ **Configurações da Aba (Folha Suplementar, CBO & Calculadora de INSS/Líquido)**", expanded=False):
            st.caption("Ajuste as regras de consolidação por CPF, código CBO e cálculo automático para gerar a planilha completa sem erros.")
            
            cfg_col1, cfg_col2 = st.columns(2)
            with cfg_col1:
                st.markdown("**1. Consolidação & Código CBO:**")
                agrupar_cpf = st.checkbox("☑ Somar e agrupar lançamentos por CPF (Folha Suplementar)", value=False, key=f"chk_agrupar_{aba_atual}")
                cbo_padrao = st.text_input("Código CBO Padrão:", value="225125", key=f"txt_cbo_{aba_atual}", help="Será utilizado se a planilha não contiver a coluna CBO ou se o campo estiver em branco.")
                
            with cfg_col2:
                st.markdown("**2. Regra para Valor Bruto, Líquido e INSS:**")
                regra_inss = st.radio(
                    "Selecione a regra de cálculo dos valores:",
                    options=[
                        ("bruto_igual_liquido", "Valor Líquido = Valor Bruto (Sem INSS - valor que vem da folha)"),
                        ("gross_up_inss", "Calcular Valor Bruto a partir do Líquido (Gross Up pelo % INSS)")
                    ],
                    format_func=lambda x: x[1],
                    index=0,
                    key=f"radio_inss_{aba_atual}"
                )
                
                perc_inss = 0.0
                if regra_inss[0] == "gross_up_inss":
                    perc_inss = st.number_input("Informe a Alíquota de INSS (%):", min_value=0.0, max_value=30.0, value=11.0, step=0.5, key=f"num_perc_{aba_atual}")

            if st.button("⚡ Aplicar Regras de CBO e INSS no Banco", type="secondary", use_container_width=True, key=f"btn_aplicar_cfg_{aba_atual}"):
                modo_inss_str = regra_inss[0]
                consolidar_folha_suplementar_sqlite(session_id, aba_atual, opcao_inss=modo_inss_str, percentual_inss=perc_inss, cbo_padrao=cbo_padrao)
                st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                st.success(f"Regras de CBO e INSS aplicadas com sucesso para a aba '{aba_atual}'!")
                st.rerun()

        stats = obter_estatisticas_aba(session_id, aba_atual)
        
        st.subheader(f"CONFERÊNCIA DA ABA: {aba_atual}")
        m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
        with m_c1:
            st.markdown(f'''<div class="metric-card"><div class="value val-total">{stats['total']:,}</div><div class="label">Total de Registros</div></div>''', unsafe_allow_html=True)
        with m_c2:
            st.markdown(f'''<div class="metric-card"><div class="value val-ok">{stats['ok']:,}</div><div class="label">🟢 OK / Conferidos</div></div>''', unsafe_allow_html=True)
        with m_c3:
            st.markdown(f'''<div class="metric-card"><div class="value val-warn">{stats['warn']:,}</div><div class="label">🟡 Conferir (Alertas)</div></div>''', unsafe_allow_html=True)
        with m_c4:
            st.markdown(f'''<div class="metric-card"><div class="value val-danger">{stats['danger']:,}</div><div class="label">🔴 Erros Críticos</div></div>''', unsafe_allow_html=True)
        with m_c5:
            st.markdown(f'''<div class="metric-card"><div class="value val-desc">{stats['descartados']:,}</div><div class="label">⚪ Descartadas</div></div>''', unsafe_allow_html=True)

        st.write("")
        somente_pendencias = st.checkbox("☑ Mostrar somente pendências (Erros / Alertas)", value=(stats['warn'] + stats['danger'] > 0), key=f"chk_pend_{aba_atual}")

        registros_exibidos = obter_registros_banco(session_id, aba_atual, apenas_pendencias=somente_pendencias, limite=1000)

        col_tabela, col_edicao = st.columns([1.5, 1])

        with col_tabela:
            st.markdown(f"### Registros ({len(registros_exibidos):,} exibidos de {stats['total']:,})")
            if not registros_exibidos:
                st.success("🎉 Todos os registros desta aba estão 100% validados (🟢 OK).")
            else:
                tabela_data = []
                for r in registros_exibidos:
                    motivo = " | ".join(r['erros_criticos'] + r['alertas']) if (r['erros_criticos'] or r['alertas']) else "Registro válido"
                    tabela_data.append({
                        "Linha": r['linha'],
                        "CPF": formatar_cpf_mascara(r['cpf']),
                        "Nome": r['nome'],
                        "Bruto (R$)": r['total_bruto'],
                        "INSS (R$)": r['inss'],
                        "Líquido (R$)": r['total_liquido'],
                        "Problema / Detalhes": motivo,
                        "Status": r['status']
                    })
                
                df_tabela = pd.DataFrame(tabela_data)
                st.dataframe(df_tabela, use_container_width=True, hide_index=True, height=350)
                
                ids_pendentes = [r['id'] for r in registros_exibidos]
                id_selecionado = st.selectbox(
                    "🔍 Selecione a linha para conferir/corrigir:",
                    options=ids_pendentes,
                    format_func=lambda x: f"Linha {next(r['linha'] for r in registros_exibidos if r['id'] == x)} - {next(r['nome'] for r in registros_exibidos if r['id'] == x)}"
                )

        with col_edicao:
            st.markdown("### Conferir / Tratar Registro")
            if 'id_selecionado' in locals() and id_selecionado:
                reg_sel = next(r for r in registros_exibidos if r['id'] == id_selecionado)
                st.markdown(f"**Linha:** `{reg_sel['linha']}` &nbsp;|&nbsp; **Status:** {reg_sel['status']}")
                
                if reg_sel.get('historico_divergencia'):
                    hist = reg_sel['historico_divergencia']
                    st.warning("⚠️ **Divergência com a folha anterior:**")
                    for d in hist['divergencias']:
                        st.markdown(f"- {d}")

                st.divider()

                with st.form(key=f"form_edicao_db_{aba_atual}_{reg_sel['id']}"):
                    st.subheader("Editar Dados")
                    novo_cpf = st.text_input("CPF:", value=reg_sel['cpf'])
                    novo_nome = st.text_input("Nome:", value=reg_sel['nome'])
                    nova_data = st.text_input("Data de Nascimento (DD/MM/YYYY):", value=reg_sel['data_nascimento'])
                    
                    c_f1, c_f2 = st.columns(2)
                    with c_f1:
                        novo_bruto = st.number_input("Valor Bruto (R$):", value=float(reg_sel['total_bruto']), step=100.0)
                        novo_inss = st.number_input("INSS (R$):", value=float(reg_sel['inss']), step=10.0)
                    with c_f2:
                        novo_liquido = st.number_input("Valor Líquido (R$):", value=float(reg_sel['total_liquido']), step=100.0)
                        novo_cbo = st.text_input("CBO:", value=reg_sel['cbo'])

                    btn_c1, btn_c2, btn_c3 = st.columns(3)
                    with btn_c1:
                        submit_aprovar = st.form_submit_button("✅ Aprovar", use_container_width=True)
                    with btn_c2:
                        submit_corrigir = st.form_submit_button("💾 Salvar", use_container_width=True)
                    with btn_c3:
                        submit_descartar = st.form_submit_button("🗑️ Descartar", use_container_width=True)

                if submit_aprovar:
                    if reg_sel['erros_criticos']:
                        st.error("🔴 Não é possível aprovar um registro com Erro Crítico. Você pode Corrigir ou Descartar a linha.")
                    else:
                        atualizar_registro_banco(reg_sel['id'], novo_cpf, novo_nome, nova_data, novo_bruto, novo_liquido, novo_cbo, novo_inss, acao='aprovar')
                        st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                        st.success(f"Linha {reg_sel['linha']} aprovada!")
                        st.rerun()

                if submit_corrigir:
                    atualizar_registro_banco(reg_sel['id'], novo_cpf, novo_nome, nova_data, novo_bruto, novo_liquido, novo_cbo, novo_inss, acao='corrigir')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.success(f"Linha {reg_sel['linha']} atualizada e validada!")
                    st.rerun()

                if submit_descartar:
                    atualizar_registro_banco(reg_sel['id'], novo_cpf, novo_nome, nova_data, novo_bruto, novo_liquido, novo_cbo, novo_inss, acao='descartar')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.warning(f"Linha {reg_sel['linha']} descartada da exportação principal!")
                    st.rerun()

        st.divider()
        st.subheader("Geração e Download do Arquivo eSocial")

        if st.button(f"📄 GERAR RELATÓRIO DE INCONSISTÊNCIAS / DESCARTES DA ABA '{aba_atual}' (.XLSX)", key=f"btn_inc_{aba_atual}"):
            bytes_inc = gerar_relatorio_inconsistencias_bytes(session_id, aba_atual)
            st.download_button(
                label=f"⬇️ Baixar Relatorio_Inconsistencias_{aba_atual}.xlsx",
                data=bytes_inc,
                file_name=f"Inconsistencias_{aba_atual}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_inc_{aba_atual}"
            )
            
        st.write("")

        bloqueios_gerais = []
        if aba_atual not in st.session_state['abas_processadas_db']:
            carregar_e_salvar_aba_no_banco(aba_atual, file_bytes, df_anterior_raw, col_map_ant)
            
        st_aba = obter_estatisticas_aba(session_id, aba_atual)
        if st_aba['danger'] > 0:
            bloqueios_gerais.append(f"Aba '{aba_atual}': {st_aba['danger']} erro(s) crítico(s)")
        if st_aba['warn'] > 0:
            bloqueios_gerais.append(f"Aba '{aba_atual}': {st_aba['warn']} pendência(s) não analisada(s)")

        if bloqueios_gerais:
            st.error(f"🔒 **ARQUIVO DA ABA '{aba_atual}' BLOQUEADO** — Existem {st_aba['danger']} erro(s) e {st_aba['warn']} alerta(s) nesta aba.")
            st.info("💡 **Deseja desbloquear imediatamente para gerar o eSocial sem os erros?**\nVocê pode descartar todas as pendências em lote de uma só vez. As linhas descartadas serão movidas para a planilha de inconsistências.")
            
            c_desc1, c_desc2 = st.columns([1.5, 1])
            with c_desc1:
                if st.button(f"🗑️ DESCARTAR TODAS AS {st_aba['danger'] + st_aba['warn']} PENDÊNCIAS EM LOTE E LIBERAR ARQUIVO", type="secondary", use_container_width=True, key=f"btn_desc_lote_{aba_atual}"):
                    qtd_d = descartar_todas_pendencias_banco(session_id, aba_atual)
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.success(f"🎉 {qtd_d} registro(s) com pendências foram descartados em lote! O arquivo eSocial foi liberado.")
                    st.rerun()
            with c_desc2:
                bytes_inc = gerar_relatorio_inconsistencias_bytes(session_id, aba_atual)
                st.download_button(
                    label=f"📄 BAIXAR PLANILHA DE INCONSISTÊNCIAS (.XLSX)",
                    data=bytes_inc,
                    file_name=f"Inconsistencias_{aba_atual}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"dl_inc_lote_{aba_atual}"
                )
            st.button("⬇️ GERAR ARQUIVO ESOCIAL PRINCIPAL", disabled=True, key="btn_gerar_disabled")
        else:
            st.success(f"🟢 **ARQUIVO DA ABA '{aba_atual}' LIBERADO** — Registros validados 100% prontos!")
            nome_sugerido = gerar_nome_arquivo(aba_atual)
            
            if st.button("⚡ GERAR PLANILHA ESOCIAL (.XLSX)", type="primary", use_container_width=True, key="btn_gerar_single"):
                with st.spinner("Gerando arquivo Excel no formato oficial do eSocial..."):
                    a_regs = exportar_registros_banco_para_list(session_id, aba_atual)
                    df_final = gerar_dataframe_esocial_final(a_regs)
                    excel_bytes = gerar_excel_esocial(df_final, modelo_path="templates/esocial.xlsx")
                    st.session_state['arquivos_gerados_cache'][aba_atual] = (nome_sugerido, excel_bytes)
                    st.success(f"Planilha eSocial da aba '{aba_atual}' gerada com sucesso!")

            if aba_atual in st.session_state['arquivos_gerados_cache']:
                nome_f, bytes_f = st.session_state['arquivos_gerados_cache'][aba_atual]
                st.download_button(
                    label=f"⬇️ BAIXAR {nome_f}",
                    data=bytes_f,
                    file_name=nome_f,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary",
                    key="dl_single_ready"
                )

# -----------------------------------------------------------------------------
# MÓDULO 2: EFD-Reinf (R-4010) – Pagamentos a Pessoa Física
# -----------------------------------------------------------------------------
else:
    st.markdown("""
    <div class="main-header">
        <h1>Conversor EFD-Reinf – Pagamentos a Pessoa Física (R-4010)</h1>
        <p>Conversão de rendimentos e pagamentos para o modelo oficial do EFD-Reinf R-4010 com validação de CPF e data do fato gerador.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state['reinf_bytes'] is None:
        st.info("👈 Selecione o arquivo da planilha para o **EFD-Reinf R-4010 (.xlsx)** no menu lateral para iniciar.")
    else:
        file_bytes = st.session_state['reinf_bytes']
        session_id = st.session_state['session_id']
        
        analise_meta = analisar_arquivo_excel_rapido(file_bytes)
        abas_disponiveis = analise_meta['abas_nomes']
        
        st.markdown(f"""
        **Arquivo:** `{st.session_state['reinf_nome']}` &nbsp;|&nbsp; 
        **Abas encontradas:** `{analise_meta['total_abas']}`
        """)
        st.write("")

        if analise_meta['total_abas'] == 1:
            aba_atual = abas_disponiveis[0]
            st.session_state['abas_selecionadas'] = [aba_atual]
        else:
            col_aba1, col_aba2 = st.columns([2, 1])
            with col_aba1:
                aba_atual = st.selectbox(
                    "📂 **Qual aba você deseja abrir?**",
                    options=abas_disponiveis,
                    index=0,
                    key="seletor_aba_reinf_principal"
                )
            with col_aba2:
                exportar_todas = st.checkbox("📦 Processar e exportar TODAS as abas no final", value=True, key="chk_export_reinf_todas")
                
            if exportar_todas:
                st.session_state['abas_selecionadas'] = abas_disponiveis
            else:
                st.session_state['abas_selecionadas'] = [aba_atual]

        if aba_atual not in st.session_state['abas_processadas_reinf_db']:
            carregar_e_salvar_reinf_aba_no_banco(aba_atual, file_bytes)

        stats = obter_estatisticas_reinf_aba(session_id, aba_atual)
        
        st.subheader(f"CONFERÊNCIA DA ABA (REINF R-4010): {aba_atual}")
        m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
        with m_c1:
            st.markdown(f'''<div class="metric-card"><div class="value val-total">{stats['total']:,}</div><div class="label">Total de Registros</div></div>''', unsafe_allow_html=True)
        with m_c2:
            st.markdown(f'''<div class="metric-card"><div class="value val-ok">{stats['ok']:,}</div><div class="label">🟢 OK / Conferidos</div></div>''', unsafe_allow_html=True)
        with m_c3:
            st.markdown(f'''<div class="metric-card"><div class="value val-warn">{stats['warn']:,}</div><div class="label">🟡 Conferir (Alertas)</div></div>''', unsafe_allow_html=True)
        with m_c4:
            st.markdown(f'''<div class="metric-card"><div class="value val-danger">{stats['danger']:,}</div><div class="label">🔴 Erros Críticos</div></div>''', unsafe_allow_html=True)
        with m_c5:
            st.markdown(f'''<div class="metric-card"><div class="value val-desc">{stats['descartados']:,}</div><div class="label">⚪ Descartadas</div></div>''', unsafe_allow_html=True)

        st.write("")
        somente_pendencias = st.checkbox("☑ Mostrar somente pendências (Erros / Alertas)", value=(stats['warn'] + stats['danger'] > 0), key=f"chk_reinf_pend_{aba_atual}")

        registros_exibidos = obter_registros_reinf_banco(session_id, aba_atual, apenas_pendencias=somente_pendencias, limite=1000)

        col_tabela, col_edicao = st.columns([1.5, 1])

        with col_tabela:
            st.markdown(f"### Registros R-4010 ({len(registros_exibidos):,} exibidos de {stats['total']:,})")
            if not registros_exibidos:
                st.success("🎉 Todos os registros desta aba do Reinf estão 100% validados (🟢 OK).")
            else:
                tabela_data = []
                for r in registros_exibidos:
                    motivo = " | ".join(r['erros_criticos'] + r['alertas']) if (r['erros_criticos'] or r['alertas']) else "Registro válido"
                    tabela_data.append({
                        "Linha": r['linha'],
                        "CPF": formatar_cpf_mascara(r['cpf']),
                        "Nome / Ref": r['nome'],
                        "Data Fato Gerador": r['data_fato_gerador'],
                        "Rendimento Bruto (R$)": r['rendimento_bruto'],
                        "Parcela Isenta (R$)": r['parcela_isenta'],
                        "Observação": r['observacao_pagamento'],
                        "Status": r['status']
                    })
                
                df_tabela = pd.DataFrame(tabela_data)
                st.dataframe(df_tabela, use_container_width=True, hide_index=True, height=350)
                
                ids_pendentes = [r['id'] for r in registros_exibidos]
                id_selecionado = st.selectbox(
                    "🔍 Selecione a linha para conferir/corrigir:",
                    options=ids_pendentes,
                    format_func=lambda x: f"Linha {next(r['linha'] for r in registros_exibidos if r['id'] == x)} - CPF: {next(r['cpf'] for r in registros_exibidos if r['id'] == x)}"
                )

        with col_edicao:
            st.markdown("### Conferir / Tratar Registro R-4010")
            if 'id_selecionado' in locals() and id_selecionado:
                reg_sel = next(r for r in registros_exibidos if r['id'] == id_selecionado)
                st.markdown(f"**Linha:** `{reg_sel['linha']}` &nbsp;|&nbsp; **Status:** {reg_sel['status']}")
                st.divider()

                with st.form(key=f"form_reinf_edicao_db_{aba_atual}_{reg_sel['id']}"):
                    st.subheader("Editar Dados R-4010")
                    novo_cpf = st.text_input("CPF:", value=reg_sel['cpf'])
                    nova_data = st.text_input("Data do Fato Gerador (DD/MM/YYYY):", value=reg_sel['data_fato_gerador'])
                    
                    c_f1, c_f2 = st.columns(2)
                    with c_f1:
                        novo_bruto = st.number_input("Rendimento Bruto (R$):", value=float(reg_sel['rendimento_bruto']), step=100.0)
                    with c_f2:
                        nova_isenta = st.number_input("Parcela Isenta (R$):", value=float(reg_sel['parcela_isenta']), step=100.0)
                        
                    nova_obs = st.text_input("Observação do Pagamento:", value=reg_sel['observacao_pagamento'])

                    btn_c1, btn_c2, btn_c3 = st.columns(3)
                    with btn_c1:
                        submit_aprovar = st.form_submit_button("✅ Aprovar", use_container_width=True)
                    with btn_c2:
                        submit_corrigir = st.form_submit_button("💾 Salvar", use_container_width=True)
                    with btn_c3:
                        submit_descartar = st.form_submit_button("🗑️ Descartar", use_container_width=True)

                if submit_aprovar:
                    if reg_sel['erros_criticos']:
                        st.error("🔴 Não é possível aprovar um registro com Erro Crítico. Você pode Corrigir ou Descartar a linha.")
                    else:
                        atualizar_registro_reinf_banco(reg_sel['id'], novo_cpf, nova_data, novo_bruto, nova_isenta, nova_obs, acao='aprovar')
                        st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                        st.success(f"Linha {reg_sel['linha']} aprovada!")
                        st.rerun()

                if submit_corrigir:
                    atualizar_registro_reinf_banco(reg_sel['id'], novo_cpf, nova_data, novo_bruto, nova_isenta, nova_obs, acao='corrigir')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.success(f"Linha {reg_sel['linha']} atualizada e validada!")
                    st.rerun()

                if submit_descartar:
                    atualizar_registro_reinf_banco(reg_sel['id'], novo_cpf, nova_data, novo_bruto, nova_isenta, nova_obs, acao='descartar')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.warning(f"Linha {reg_sel['linha']} descartada da exportação principal!")
                    st.rerun()

        st.divider()
        st.subheader("Geração e Download do Arquivo EFD-Reinf R-4010")

        if st.button(f"📄 GERAR RELATÓRIO DE INCONSISTÊNCIAS / DESCARTES DA ABA '{aba_atual}' (.XLSX)", key=f"btn_reinf_inc_{aba_atual}"):
            bytes_inc = gerar_relatorio_inconsistencias_reinf_bytes(session_id, aba_atual)
            st.download_button(
                label=f"⬇️ Baixar Relatorio_Inconsistencias_Reinf_{aba_atual}.xlsx",
                data=bytes_inc,
                file_name=f"Inconsistencias_Reinf_{aba_atual}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_reinf_inc_{aba_atual}"
            )
            
        st.write("")

        bloqueios_gerais = []
        if aba_atual not in st.session_state['abas_processadas_reinf_db']:
            carregar_e_salvar_reinf_aba_no_banco(aba_atual, file_bytes)
            
        st_aba = obter_estatisticas_reinf_aba(session_id, aba_atual)
        if st_aba['danger'] > 0:
            bloqueios_gerais.append(f"Aba '{aba_atual}': {st_aba['danger']} erro(s) crítico(s)")
        if st_aba['warn'] > 0:
            bloqueios_gerais.append(f"Aba '{aba_atual}': {st_aba['warn']} pendência(s) não analisada(s)")

        if bloqueios_gerais:
            st.error(f"🔒 **ARQUIVO DA ABA '{aba_atual}' BLOQUEADO** — Existem {st_aba['danger']} erro(s) e {st_aba['warn']} alerta(s) nesta aba.")
            st.info("💡 **Deseja desbloquear imediatamente para gerar o EFD-Reinf sem os erros?**\nVocê pode descartar todas as pendências em lote de uma só vez. As linhas descartadas serão movidas para a planilha de inconsistências.")
            
            c_desc1, c_desc2 = st.columns([1.5, 1])
            with c_desc1:
                if st.button(f"🗑️ DESCARTAR TODAS AS {st_aba['danger'] + st_aba['warn']} PENDÊNCIAS EM LOTE E LIBERAR ARQUIVO", type="secondary", use_container_width=True, key=f"btn_reinf_desc_lote_{aba_atual}"):
                    qtd_d = descartar_todas_pendencias_reinf_banco(session_id, aba_atual)
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.success(f"🎉 {qtd_d} registro(s) com pendências foram descartados em lote! O arquivo EFD-Reinf foi liberado.")
                    st.rerun()
            with c_desc2:
                bytes_inc = gerar_relatorio_inconsistencias_reinf_bytes(session_id, aba_atual)
                st.download_button(
                    label=f"📄 BAIXAR PLANILHA DE INCONSISTÊNCIAS (.XLSX)",
                    data=bytes_inc,
                    file_name=f"Inconsistencias_Reinf_{aba_atual}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"dl_reinf_inc_lote_{aba_atual}"
                )
            st.button("⬇️ GERAR ARQUIVO EFD-REINF R-4010 PRINCIPAL", disabled=True, key="btn_reinf_gerar_disabled")
        else:
            st.success("🟢 **ARQUIVO PRINCIPAL LIBERADO** — Registros R-4010 validados 100% prontos!")
            
            if len(st.session_state['abas_selecionadas']) == 1:
                a_nome = st.session_state['abas_selecionadas'][0]
                nome_sugerido = f"EFD_Reinf_R4010_{a_nome}.xlsx"
                
                if st.button("⚡ GERAR PLANILHA EFD-REINF R-4010 (.XLSX)", type="primary", use_container_width=True, key="btn_reinf_gerar_single"):
                    with st.spinner("Gerando arquivo Excel no formato oficial do EFD-Reinf R-4010..."):
                        a_regs = exportar_registros_reinf_banco_para_list(session_id, a_nome)
                        df_final = gerar_dataframe_reinf_final(a_regs)
                        excel_bytes = gerar_excel_esocial(df_final, modelo_path="templates/reinf_r4010.xlsx")
                        st.session_state['arquivos_gerados_cache'][a_nome] = (nome_sugerido, excel_bytes)
                        st.success("Planilha EFD-Reinf R-4010 gerada com sucesso!")

                if a_nome in st.session_state['arquivos_gerados_cache']:
                    nome_f, bytes_f = st.session_state['arquivos_gerados_cache'][a_nome]
                    st.download_button(
                        label=f"⬇️ BAIXAR {nome_f}",
                        data=bytes_f,
                        file_name=nome_f,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        type="primary",
                        key="dl_reinf_single_ready"
                    )
            else:
                if st.button("⚡ GERAR PACOTE DE ARQUIVOS R-4010 DAS ABAS SELECIONADAS (ZIP)", type="primary", use_container_width=True, key="btn_reinf_gerar_multi"):
                    with st.spinner("Gerando planilhas Excel R-4010 e empacotando em ZIP..."):
                        arquivos_zip = []
                        for a_nome in st.session_state['abas_selecionadas']:
                            a_regs = exportar_registros_reinf_banco_para_list(session_id, a_nome)
                            df_final = gerar_dataframe_reinf_final(a_regs)
                            excel_bytes = gerar_excel_esocial(df_final, modelo_path="templates/reinf_r4010.xlsx")
                            nome_file = f"EFD_Reinf_R4010_{a_nome}.xlsx"
                            arquivos_zip.append((nome_file, excel_bytes))
                            st.session_state['arquivos_gerados_cache'][a_nome] = (nome_file, excel_bytes)
                            
                        zip_bytes = gerar_pacote_zip_arquivos(arquivos_zip)
                        st.session_state['reinf_zip_bytes_pronto'] = zip_bytes
                        st.success("Pacote ZIP EFD-Reinf R-4010 gerado com sucesso!")

                if 'reinf_zip_bytes_pronto' in st.session_state:
                    st.download_button(
                        label="📦 BAIXAR TODOS OS ARQUIVOS R-4010 (PACOTE ZIP)",
                        data=st.session_state['reinf_zip_bytes_pronto'],
                        file_name="EFD_Reinf_R4010.zip",
                        mime="application/zip",
                        use_container_width=True,
                        type="primary",
                        key="dl_reinf_zip_ready"
                    )
