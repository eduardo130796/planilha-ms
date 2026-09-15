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
    descartar_todas_pendencias_banco, descartar_todas_pendencias_reinf_banco,
    contar_divergencias_pendentes_banco, aplicar_correcoes_folha_anterior_banco
)
from utils.excel import gerar_excel_esocial
from utils.cpf import formatar_cpf_mascara

# -----------------------------------------------------------------------------
# CONSTANTES DE NAVEGAÇÃO E TIPOS DE PLANILHA
# -----------------------------------------------------------------------------
MODULO_ESOCIAL = "📄 eSocial"
MODULO_REINF = "📑 EFD-Reinf"

# Cada "tipo" representa um modelo de folha diferente que pode ser recebido
# (hoje só Residência Médica; novos convênios/folhas podem ser adicionados
# aqui como novas entradas, sem mexer no restante do código).
TIPOS_PLANILHA_ESOCIAL = {
    "🏥 Residência Médica": {
        "cbo_padrao": "225125",
        "descricao": "Bolsistas/residentes com CBO padrão de médico residente."
    },
    "➕ Outro / Genérico": {
        "cbo_padrao": "",
        "descricao": "Planilha sem modelo específico. Informe o CBO manualmente."
    },
}

STEPPER_ESOCIAL = ["Enviar planilha", "Conferir pendências", "Baixar arquivo"]
STEPPER_REINF = ["Enviar planilha", "Conferir pendências", "Baixar arquivo(s)"]

# Configuração da Página
st.set_page_config(
    page_title="Conversor eSocial & EFD-Reinf",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# ESTILIZAÇÃO GLOBAL (design system)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root{
    --brand-50:#EEF2FF; --brand-100:#E0E7FF; --brand-500:#6366F1; --brand-600:#4F46E5; --brand-700:#4338CA;
    --ok-500:#16A34A; --ok-50:#F0FDF4;
    --warn-500:#D97706; --warn-50:#FFFBEB;
    --danger-500:#DC2626; --danger-50:#FEF2F2;
    --ink-900:#0F172A; --ink-600:#475569; --ink-400:#94A3B8;
    --surface:#FFFFFF; --page:#F8FAFC; --border:#E2E8F0;
    --radius-lg:18px; --radius-md:12px; --radius-sm:8px;
    --shadow-sm:0 1px 2px rgba(15,23,42,.05);
    --shadow-md:0 8px 24px rgba(15,23,42,.07);
}

html, body, [class*="css"] { font-family:'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }

[data-testid="stAppViewContainer"] > .main { background: var(--page); }
.main .block-container { padding-top: 1.3rem; padding-bottom: 3rem; max-width: 1360px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] .block-container { padding-top: 1.6rem; }

.brand { display:flex; align-items:center; gap:10px; margin-bottom: 10px; }
.brand-icon { font-size: 1.7rem; line-height:1; }
.brand-title { font-weight: 800; font-size: 1.05rem; color: var(--ink-900); line-height:1.15; }
.brand-subtitle { font-size: .74rem; color: var(--ink-400); font-weight:500; }

.side-label { font-size:.72rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color: var(--brand-600); margin: 2px 0 6px 2px; }

/* ---------- Hero header ---------- */
.hero {
    background: linear-gradient(135deg, var(--brand-700) 0%, var(--brand-600) 55%, #6D28D9 100%);
    color: #fff; padding: 26px 30px; border-radius: var(--radius-lg);
    margin-bottom: 18px; box-shadow: var(--shadow-md); position:relative; overflow:hidden;
}
.hero::after{ content:""; position:absolute; right:-40px; top:-50px; width:190px; height:190px; background:rgba(255,255,255,.08); border-radius:50%; }
.hero::before{ content:""; position:absolute; right:60px; bottom:-60px; width:120px; height:120px; background:rgba(255,255,255,.06); border-radius:50%; }
.hero-badge { display:inline-block; background:rgba(255,255,255,.16); padding:3px 11px; border-radius:999px; font-size:.72rem; font-weight:700; margin-bottom:10px; letter-spacing:.03em; }
.hero h1 { color:#fff; font-size:1.65rem; font-weight:800; margin:0 0 4px 0; }
.hero p { color:rgba(255,255,255,.85); font-size:.92rem; margin:0; max-width: 680px; }

/* ---------- Stepper ---------- */
.stepper { display:flex; align-items:flex-start; gap:0; margin: 6px 0 20px 0; }
.step { display:flex; flex-direction:column; align-items:center; gap:6px; min-width: 86px; }
.step-circle { width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.82rem; border:2px solid var(--border); color:var(--ink-400); background:var(--surface); transition: all .2s ease; }
.step-label { font-size:.72rem; font-weight:600; color:var(--ink-400); text-align:center; line-height:1.2; }
.step-done .step-circle { background: var(--ok-500); border-color: var(--ok-500); color:#fff; }
.step-done .step-label { color: var(--ink-600); }
.step-active .step-circle { background: var(--brand-600); border-color: var(--brand-600); color:#fff; box-shadow:0 0 0 4px var(--brand-100); }
.step-active .step-label { color: var(--brand-700); font-weight:700; }
.step-connector { flex:1; height:2px; background: var(--border); margin: 15px 2px 0 2px; min-width: 20px; }
.step-connector-done { background: var(--ok-500); }

/* ---------- Metric cards ---------- */
.metric-card { position:relative; background: var(--surface); border:1px solid var(--border); border-radius: var(--radius-md); padding:16px 16px 13px; box-shadow: var(--shadow-sm); transition: transform .15s ease, box-shadow .15s ease; overflow:hidden; }
.metric-card::before { content:""; position:absolute; top:0; left:0; right:0; height:3px; }
.metric-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.metric-card .metric-icon { font-size:1.05rem; margin-bottom:2px; opacity:.85; }
.metric-card .value { font-size:1.6rem; font-weight:800; line-height:1.1; }
.metric-card .label { font-size:.75rem; color: var(--ink-600); font-weight:600; margin-top:3px; }
.metric-total::before { background: var(--brand-500); }
.metric-ok::before { background: var(--ok-500); }
.metric-warn::before { background: var(--warn-500); }
.metric-danger::before { background: var(--danger-500); }
.metric-desc::before { background: var(--ink-400); }
.metric-total .value{ color: var(--brand-600); }
.metric-ok .value{ color: var(--ok-500); }
.metric-warn .value{ color: var(--warn-500); }
.metric-danger .value{ color: var(--danger-500); }
.metric-desc .value{ color: var(--ink-400); }

/* ---------- Superfícies genéricas ---------- */
[data-testid="stExpander"] { border:1px solid var(--border); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); background: var(--surface); }
[data-testid="stForm"] { border:1px solid var(--border); border-radius: var(--radius-md); background: var(--surface); }
[data-testid="stFileUploader"] { border-radius: var(--radius-sm); }
[data-testid="stAlert"] { border-radius: var(--radius-md); }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: var(--radius-md) !important; }

/* ---------- Botões ---------- */
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button, [data-testid="stFormSubmitButton"] button, [data-testid="stBaseButton-secondaryFormSubmit"] {
    border-radius: 10px !important; font-weight:600 !important; transition: transform .1s ease, box-shadow .15s ease;
}
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover {
    transform: translateY(-1px); box-shadow: var(--shadow-sm);
}

/* ---------- Estado vazio ---------- */
.empty-state { text-align:center; padding: 48px 24px; border:1.5px dashed var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.empty-state .emoji { font-size:2.4rem; margin-bottom:10px; }
.empty-state h3 { margin:0 0 6px 0; color: var(--ink-900); font-weight:700; }
.empty-state p { color: var(--ink-600); font-size:.9rem; margin:0 auto; max-width: 480px; }

/* ---------- Títulos de seção ---------- */
.section-title { font-weight:700; color:var(--ink-900); font-size:1.05rem; margin: 6px 0 10px 0; }

/* ---------- Rodapé de arquivo ---------- */
.file-chip { display:inline-flex; align-items:center; gap:6px; background: var(--brand-50); color: var(--brand-700); padding: 4px 12px; border-radius: 999px; font-size:.82rem; font-weight:600; margin-right:8px; }
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
if 'tipo_planilha_esocial' not in st.session_state:
    st.session_state['tipo_planilha_esocial'] = list(TIPOS_PLANILHA_ESOCIAL.keys())[0]

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES DE UI
# -----------------------------------------------------------------------------
def render_stepper(labels: list[str], current_index: int):
    """Desenha um indicador de progresso (stepper) horizontal.
    Passos com índice < current_index aparecem como concluídos,
    o passo == current_index aparece como ativo, os demais como pendentes.
    """
    partes = ['<div class="stepper">']
    for i, label in enumerate(labels):
        if i < current_index:
            estado, icone = "done", "✓"
        elif i == current_index:
            estado, icone = "active", str(i + 1)
        else:
            estado, icone = "upcoming", str(i + 1)

        partes.append(f'''
        <div class="step step-{estado}">
            <div class="step-circle">{icone}</div>
            <div class="step-label">{label}</div>
        </div>
        ''')
        if i < len(labels) - 1:
            conector_estado = "done" if i < current_index else ""
            partes.append(f'<div class="step-connector step-connector-{conector_estado}"></div>')
    partes.append('</div>')
    st.markdown("".join(partes), unsafe_allow_html=True)


def render_metric_cards(stats: dict):
    m_c1, m_c2, m_c3, m_c4, m_c5 = st.columns(5)
    with m_c1:
        st.markdown(f'''<div class="metric-card metric-total"><div class="metric-icon">📋</div><div class="value">{stats['total']:,}</div><div class="label">Total de Registros</div></div>''', unsafe_allow_html=True)
    with m_c2:
        st.markdown(f'''<div class="metric-card metric-ok"><div class="metric-icon">🟢</div><div class="value">{stats['ok']:,}</div><div class="label">OK / Conferidos</div></div>''', unsafe_allow_html=True)
    with m_c3:
        st.markdown(f'''<div class="metric-card metric-warn"><div class="metric-icon">🟡</div><div class="value">{stats['warn']:,}</div><div class="label">Conferir (Alertas)</div></div>''', unsafe_allow_html=True)
    with m_c4:
        st.markdown(f'''<div class="metric-card metric-danger"><div class="metric-icon">🔴</div><div class="value">{stats['danger']:,}</div><div class="label">Erros Críticos</div></div>''', unsafe_allow_html=True)
    with m_c5:
        st.markdown(f'''<div class="metric-card metric-desc"><div class="metric-icon">⚪</div><div class="value">{stats['descartados']:,}</div><div class="label">Descartadas</div></div>''', unsafe_allow_html=True)


def render_empty_state(emoji: str, titulo: str, texto: str):
    st.markdown(f'''
    <div class="empty-state">
        <div class="emoji">{emoji}</div>
        <h3>{titulo}</h3>
        <p>{texto}</p>
    </div>
    ''', unsafe_allow_html=True)


def status_para_badge(status: str) -> tuple[str, str]:
    """Converte o status salvo no banco em (cor, rótulo curto) para st.badge."""
    if "OK" in status or "CONFERIDO" in status:
        return "green", "OK"
    if "CONFERIR" in status:
        return "orange", "Conferir"
    if "ERRO" in status:
        return "red", "Erro crítico"
    if "DESCARTADO" in status:
        return "gray", "Descartado"
    return "gray", status


def render_configuracoes_aba(chave_config: str, session_id: str, aba_para_aplicar: str = None):
    """Painel de configuração de agrupamento por CPF / CBO / valores.

    `chave_config` identifica o conjunto de widgets (nome da aba, ou "lote" no modo em lote).
    Quando `aba_para_aplicar` é informado, o próprio botão de agrupar já aplica a consolidação
    nessa aba (modo de aba única). No modo em lote, `aba_para_aplicar` fica None: o botão não
    aparece aqui e as configurações escolhidas são aplicadas pelo botão "Processar lote".

    Retorna (agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, percentual_inss).
    """
    st.markdown('<div class="section-title">🧩 Agrupar lançamentos duplicados por CPF</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption("Se a mesma pessoa (CPF) aparecer em mais de uma linha, o eSocial bloqueia por 'CPF duplicado'. Marque a opção abaixo para somar automaticamente os lançamentos do mesmo CPF em uma única linha — o Bruto, Líquido, INSS e CBO que já vêm preenchidos na planilha são preservados, nada é recalculado por padrão.")

        agrupar_cpf = st.checkbox("☑ Somar e agrupar lançamentos duplicados do mesmo CPF", value=False, key=f"chk_agrupar_{chave_config}")

        with st.expander("🔧 Opções avançadas (CBO de fallback e recálculo de valores)", expanded=False):
            cbo_sugerido = TIPOS_PLANILHA_ESOCIAL[st.session_state['tipo_planilha_esocial']]["cbo_padrao"]
            cbo_padrao = st.text_input(
                "CBO de fallback:", value=cbo_sugerido, key=f"txt_cbo_{chave_config}",
                help="Só é usado quando a linha NÃO tem nenhum CBO preenchido. O CBO que já vem na planilha nunca é sobrescrito."
            )
            aplicar_regra_valores = st.checkbox(
                "Recalcular Bruto/Líquido/INSS automaticamente (em vez de apenas somar os valores originais)",
                value=False, key=f"chk_recalc_{chave_config}"
            )
            opcao_inss = "bruto_igual_liquido"
            perc_inss = 0.0
            if aplicar_regra_valores:
                regra_inss = st.radio(
                    "Selecione a regra de cálculo dos valores:",
                    options=[
                        ("bruto_igual_liquido", "Valor Líquido = Valor Bruto (zera o INSS)"),
                        ("gross_up_inss", "Calcular Valor Bruto a partir do Líquido (Gross Up pelo % INSS)")
                    ],
                    format_func=lambda x: x[1],
                    index=0,
                    key=f"radio_inss_{chave_config}"
                )
                opcao_inss = regra_inss[0]
                if opcao_inss == "gross_up_inss":
                    perc_inss = st.number_input("Informe a Alíquota de INSS (%):", min_value=0.0, max_value=30.0, value=11.0, step=0.5, key=f"num_perc_{chave_config}")

        if aba_para_aplicar:
            if st.button("Agrupar lançamentos duplicados por CPF", icon="🧩", type="primary", width="stretch", disabled=not agrupar_cpf, key=f"btn_aplicar_cfg_{chave_config}"):
                consolidar_folha_suplementar_sqlite(session_id, aba_para_aplicar, aplicar_regra_valores=aplicar_regra_valores, opcao_inss=opcao_inss, percentual_inss=perc_inss, cbo_padrao=cbo_padrao)
                st.session_state['arquivos_gerados_cache'].pop(aba_para_aplicar, None)
                st.toast("Lançamentos agrupados por CPF!", icon="🧩")
                st.success(f"Lançamentos duplicados agrupados com sucesso na aba '{aba_para_aplicar}'!")
                st.rerun()
            if not agrupar_cpf:
                st.caption("Marque a opção acima para habilitar o agrupamento.")

    return agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, perc_inss


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

def processar_lote_abas_esocial(file_bytes, abas_ordem, agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, perc_inss, df_anterior_raw=None, col_map_ant=None):
    """Processa TODAS as abas (competências) de uma planilha com vários meses de uma vez.

    Cada aba é comparada com a aba anterior da própria planilha (a competência do mês
    passado vira automaticamente a referência da competência seguinte). A folha anterior
    enviada no menu lateral, se houver, é usada como referência apenas para a 1ª aba do lote.
    As configurações de agrupamento por CPF/CBO/valores são aplicadas igualmente a todas as abas.

    Retorna uma lista de dicts com o resumo (estatísticas) de cada aba processada.
    """
    session_id = st.session_state['session_id']
    df_prev_hig, col_map_prev = None, None
    if df_anterior_raw is not None and col_map_ant is not None:
        df_prev_hig = higienizar_dataframe(df_anterior_raw, col_map_ant)
        col_map_prev = col_map_ant

    resumo = []
    for aba_nome in abas_ordem:
        df_raw = carregar_dados_aba_cached(file_bytes, aba_nome)
        col_map, _ = auto_detectar_mapeamento(list(df_raw.columns))
        df_hig = higienizar_dataframe(df_raw, col_map)
        registros = validar_base(df_hig, col_map)

        if df_prev_hig is not None and col_map_prev is not None:
            registros = comparar_com_folha_anterior(registros, df_prev_hig, col_map_prev)

        salvar_registros_no_banco(session_id, aba_nome, registros)
        st.session_state['abas_processadas_db'].add(aba_nome)

        if agrupar_cpf:
            consolidar_folha_suplementar_sqlite(session_id, aba_nome, aplicar_regra_valores=aplicar_regra_valores, opcao_inss=opcao_inss, percentual_inss=perc_inss, cbo_padrao=cbo_padrao)

        resumo.append({'aba': aba_nome, **obter_estatisticas_aba(session_id, aba_nome)})

        # a competência recém-processada vira a referência da próxima competência do lote
        df_prev_hig, col_map_prev = df_hig, col_map

    return resumo


def render_aplicar_lote_e_resultado(file_bytes, session_id, aba_atual, abas_disponiveis, agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, perc_inss, df_anterior_raw, col_map_ant):
    """Depois que o usuário ajustou a configuração da aba atual (agrupar por CPF, CBO,
    etc.), oferece aplicar essa MESMA configuração às demais abas/competências da
    planilha de uma vez — comparando automaticamente cada uma com a anterior da
    própria planilha — em vez de repetir o processo aba por aba."""
    outras_abas = [a for a in abas_disponiveis if a != aba_atual]
    if not outras_abas:
        return

    resumo_config = "agrupando os lançamentos duplicados por CPF" if agrupar_cpf else "sem agrupar por CPF"
    st.markdown('<div class="section-title">📦 Aplicar esta configuração às outras competências</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption(f"Esta planilha tem mais {len(outras_abas)} aba(s) — provavelmente outras competências (meses). Você pode aplicar a mesma configuração usada em '{aba_atual}' ({resumo_config}) a todas elas de uma vez, comparando automaticamente cada competência com a anterior da própria planilha.")

        if st.button(f"Processar as {len(abas_disponiveis)} competências com esta configuração", icon="📦", type="primary", width="stretch", key=f"btn_aplicar_lote_{aba_atual}"):
            with st.status(f"Processando {len(abas_disponiveis)} competências...", expanded=True) as status_box:
                resumo = processar_lote_abas_esocial(
                    file_bytes, abas_disponiveis, agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, perc_inss,
                    df_anterior_raw=df_anterior_raw, col_map_ant=col_map_ant
                )
                st.session_state['resumo_lote_esocial'] = resumo
                st.session_state['arquivos_gerados_cache'] = {
                    k: v for k, v in st.session_state['arquivos_gerados_cache'].items() if k not in abas_disponiveis
                }
                st.session_state.pop('lote_zip_bytes_pronto', None)
                for r in resumo:
                    st.write(f"✔️ **{r['aba']}** — {r['total']} registro(s)")
                status_box.update(label=f"{len(abas_disponiveis)} competências processadas!", state="complete")
            st.toast("Lote processado!", icon="🎉")
            st.rerun()

        resumo = st.session_state.get('resumo_lote_esocial')
        if not resumo or set(r['aba'] for r in resumo) != set(abas_disponiveis):
            return

        st.write("")
        st.markdown("**Resultado por competência:**")

        linhas_resumo = []
        for r in resumo:
            liberado = (r['warn'] + r['danger']) == 0
            linhas_resumo.append({
                "Competência (aba)": r['aba'],
                "Total": r['total'],
                "OK": r['ok'],
                "Conferir": r['warn'],
                "Erros": r['danger'],
                "Status": "🟢 Liberado" if liberado else "🔒 Bloqueado",
            })
        st.dataframe(pd.DataFrame(linhas_resumo), hide_index=True, height=min(320, 46 + 36 * len(linhas_resumo)))

        abas_liberadas = [r['aba'] for r in resumo if (r['warn'] + r['danger']) == 0]
        abas_bloqueadas = [r['aba'] for r in resumo if (r['warn'] + r['danger']) > 0]

        col_zip, col_rev = st.columns(2)
        with col_zip:
            if abas_liberadas:
                if st.button(f"Gerar planilhas eSocial das {len(abas_liberadas)} competência(s) liberada(s)", icon="⚡", type="primary", width="stretch", key="btn_gerar_lote"):
                    with st.status("Gerando planilhas eSocial...", expanded=False) as status_box:
                        arquivos_zip = []
                        for aba_nome in abas_liberadas:
                            a_regs = exportar_registros_banco_para_list(session_id, aba_nome)
                            df_final = gerar_dataframe_esocial_final(a_regs)
                            excel_bytes = gerar_excel_esocial(df_final, modelo_path="templates/esocial.xlsx")
                            nome_arquivo = gerar_nome_arquivo(aba_nome)
                            arquivos_zip.append((nome_arquivo, excel_bytes))
                            st.session_state['arquivos_gerados_cache'][aba_nome] = (nome_arquivo, excel_bytes)
                        zip_bytes = gerar_pacote_zip_arquivos(arquivos_zip)
                        st.session_state['lote_zip_bytes_pronto'] = zip_bytes
                        status_box.update(label="Planilhas geradas com sucesso!", state="complete")
                    st.toast("Pacote ZIP gerado!", icon="🎉")

                if 'lote_zip_bytes_pronto' in st.session_state:
                    st.download_button(
                        label=f"Baixar pacote ZIP com {len(abas_liberadas)} planilha(s)",
                        icon="📦",
                        data=st.session_state['lote_zip_bytes_pronto'],
                        file_name="eSocial_Lote_Competencias.zip",
                        mime="application/zip",
                        width="stretch",
                        type="primary",
                        key="dl_lote_zip_ready"
                    )
            else:
                st.warning("Nenhuma competência liberada ainda — resolva as pendências ao lado primeiro.")

        with col_rev:
            if abas_bloqueadas:
                st.markdown(f"**{len(abas_bloqueadas)} competência(s) com pendências:**")
                aba_revisar = st.selectbox("Escolha uma competência para revisar:", options=abas_bloqueadas, key="select_aba_revisar_lote", label_visibility="collapsed")
                if st.button(f"Abrir '{aba_revisar}' para revisar", icon="🔎", width="stretch", key="btn_revisar_aba_lote"):
                    st.session_state['_aba_revisar_pendente'] = aba_revisar
                    st.rerun()
            else:
                st.success("🎉 Todas as competências estão liberadas!")


def render_esocial_arquivo_carregado():
        file_bytes = st.session_state['folha_bytes']
        session_id = st.session_state['session_id']

        analise_meta = analisar_arquivo_excel_rapido(file_bytes)
        abas_disponiveis = analise_meta['abas_nomes']

        info_col, badge_col = st.columns([3, 2])
        with info_col:
            st.markdown(f'<span class="file-chip">📄 {st.session_state["folha_nome"]}</span><span class="file-chip">📁 {analise_meta["total_abas"]} aba(s)</span>', unsafe_allow_html=True)

        df_anterior_raw = None
        col_map_ant = None
        if st.session_state['folha_anterior_bytes'] is not None:
            ant_bytes = st.session_state['folha_anterior_bytes']
            meta_ant = analisar_arquivo_excel_rapido(ant_bytes)
            if meta_ant['total_abas'] > 0:
                primeira_aba_ant = meta_ant['abas_nomes'][0]
                df_anterior_raw = carregar_dados_aba_cached(ant_bytes, primeira_aba_ant)
                col_map_ant, _ = auto_detectar_mapeamento(list(df_anterior_raw.columns))
                with badge_col:
                    st.badge("Comparação com folha anterior ativa", icon="🔁", color="violet")

        st.write("")

        aba_revisar_pendente = st.session_state.pop('_aba_revisar_pendente', None)
        if aba_revisar_pendente:
            # Precisa acontecer ANTES do widget do seletor ser instanciado nesta mesma
            # execução — Streamlit não permite alterar o session_state de um widget
            # depois que ele já foi renderizado na mesma rodada do script.
            st.session_state['seletor_aba_principal'] = aba_revisar_pendente

        if analise_meta['total_abas'] == 1:
            aba_atual = abas_disponiveis[0]
        else:
            if st.session_state.get('seletor_aba_principal') not in abas_disponiveis:
                st.session_state['seletor_aba_principal'] = abas_disponiveis[0]
            aba_atual = st.selectbox(
                "📂 **Qual aba você deseja abrir?**",
                options=abas_disponiveis,
                key="seletor_aba_principal"
            )

        st.session_state['abas_selecionadas'] = [aba_atual]

        if aba_atual not in st.session_state['abas_processadas_db']:
            carregar_e_salvar_aba_no_banco(aba_atual, file_bytes, df_anterior_raw, col_map_ant)

        agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, perc_inss = render_configuracoes_aba(aba_atual, session_id, aba_para_aplicar=aba_atual)

        if len(abas_disponiveis) > 1:
            render_aplicar_lote_e_resultado(
                file_bytes, session_id, aba_atual, abas_disponiveis,
                agrupar_cpf, cbo_padrao, aplicar_regra_valores, opcao_inss, perc_inss,
                df_anterior_raw, col_map_ant
            )

        stats = obter_estatisticas_aba(session_id, aba_atual)

        step_idx = 1 if (stats['warn'] + stats['danger'] > 0) else (2 if aba_atual not in st.session_state['arquivos_gerados_cache'] else 3)
        render_stepper(STEPPER_ESOCIAL, current_index=step_idx)

        st.markdown(f'<div class="section-title">🔎 Conferência da aba: {aba_atual}</div>', unsafe_allow_html=True)
        render_metric_cards(stats)

        st.write("")

        if st.session_state['folha_anterior_bytes'] is not None:
            qtd_divergencias = contar_divergencias_pendentes_banco(session_id, aba_atual)
            if qtd_divergencias > 0:
                st.warning(f"🟡 **{qtd_divergencias} registro(s)** têm Nome e/ou Data de Nascimento diferentes da folha do mês anterior.")
                c_bulk1, c_bulk2 = st.columns([2, 1])
                with c_bulk1:
                    st.caption("A folha anterior já foi conferida no mês passado. Em vez de corrigir linha por linha, você pode aplicar de uma vez o Nome/Data de Nascimento da folha anterior em todos os registros divergentes desta aba.")
                with c_bulk2:
                    if st.button(f"Atualizar {qtd_divergencias} registro(s) com a folha anterior", icon="🔄", type="primary", width="stretch", key=f"btn_bulk_divergencia_{aba_atual}"):
                        qtd_atualizados = aplicar_correcoes_folha_anterior_banco(session_id, aba_atual)
                        st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                        st.toast(f"{qtd_atualizados} registro(s) atualizados!", icon="🎉")
                        st.success(f"🎉 {qtd_atualizados} registro(s) atualizados com os dados da folha anterior!")
                        st.rerun()

        somente_pendencias = st.checkbox("☑ Mostrar somente pendências (Erros / Alertas)", value=(stats['warn'] + stats['danger'] > 0), key=f"chk_pend_{aba_atual}")

        registros_exibidos = obter_registros_banco(session_id, aba_atual, apenas_pendencias=somente_pendencias, limite=1000)

        col_tabela, col_edicao = st.columns([1.5, 1])

        id_selecionado = None
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
                        "Bruto (R$)": float(r['total_bruto']),
                        "INSS (R$)": float(r['inss']),
                        "Líquido (R$)": float(r['total_liquido']),
                        "Problema / Detalhes": motivo,
                        "Status": r['status']
                    })

                df_tabela = pd.DataFrame(tabela_data)
                evento_tabela = st.dataframe(
                    df_tabela,
                    hide_index=True,
                    height=360,
                    column_config={
                        "Bruto (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                        "INSS (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Líquido (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    },
                    on_select="rerun",
                    selection_mode="single-row",
                    key=f"grid_esocial_{aba_atual}_{somente_pendencias}",
                )
                st.caption("💡 Clique em uma linha da tabela para conferir/corrigir o registro no painel ao lado.")

                linhas_sel = evento_tabela.selection.rows if evento_tabela and evento_tabela.selection else []
                idx_sel = linhas_sel[0] if linhas_sel and linhas_sel[0] < len(registros_exibidos) else 0
                id_selecionado = registros_exibidos[idx_sel]['id']

        with col_edicao:
            st.markdown("### Conferir / Tratar Registro")
            if id_selecionado:
                reg_sel = next(r for r in registros_exibidos if r['id'] == id_selecionado)
                cor_badge, label_badge = status_para_badge(reg_sel['status'])

                with st.container(border=True):
                    bc1, bc2 = st.columns([1, 2])
                    with bc1:
                        st.badge(label_badge, color=cor_badge)
                    with bc2:
                        st.markdown(f"**Linha {reg_sel['linha']}**")

                    if reg_sel.get('historico_divergencia'):
                        hist = reg_sel['historico_divergencia']
                        st.warning("⚠️ **Divergência com a folha anterior:**")
                        for d in hist['divergencias']:
                            st.markdown(f"- {d}")

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
                            submit_aprovar = st.form_submit_button("Aprovar", icon="✅", width="stretch")
                        with btn_c2:
                            submit_corrigir = st.form_submit_button("Salvar", icon="💾", width="stretch")
                        with btn_c3:
                            submit_descartar = st.form_submit_button("Descartar", icon="🗑️", width="stretch")

                if submit_aprovar:
                    if reg_sel['erros_criticos']:
                        st.error("🔴 Não é possível aprovar um registro com Erro Crítico. Você pode Corrigir ou Descartar a linha.")
                    else:
                        atualizar_registro_banco(reg_sel['id'], novo_cpf, novo_nome, nova_data, novo_bruto, novo_liquido, novo_cbo, novo_inss, acao='aprovar')
                        st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                        st.toast(f"Linha {reg_sel['linha']} aprovada!", icon="✅")
                        st.success(f"Linha {reg_sel['linha']} aprovada!")
                        st.rerun()

                if submit_corrigir:
                    atualizar_registro_banco(reg_sel['id'], novo_cpf, novo_nome, nova_data, novo_bruto, novo_liquido, novo_cbo, novo_inss, acao='corrigir')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.toast(f"Linha {reg_sel['linha']} atualizada!", icon="💾")
                    st.success(f"Linha {reg_sel['linha']} atualizada e validada!")
                    st.rerun()

                if submit_descartar:
                    atualizar_registro_banco(reg_sel['id'], novo_cpf, novo_nome, nova_data, novo_bruto, novo_liquido, novo_cbo, novo_inss, acao='descartar')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.toast(f"Linha {reg_sel['linha']} descartada.", icon="🗑️")
                    st.warning(f"Linha {reg_sel['linha']} descartada da exportação principal!")
                    st.rerun()

        st.divider()
        st.markdown('<div class="section-title">📦 Geração e Download do Arquivo eSocial</div>', unsafe_allow_html=True)

        if st.button(f"Gerar relatório de inconsistências / descartes da aba '{aba_atual}' (.xlsx)", icon="📄", key=f"btn_inc_{aba_atual}"):
            bytes_inc = gerar_relatorio_inconsistencias_bytes(session_id, aba_atual)
            st.download_button(
                label=f"Baixar Relatorio_Inconsistencias_{aba_atual}.xlsx",
                icon="⬇️",
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
                if st.button(f"Descartar todas as {st_aba['danger'] + st_aba['warn']} pendências em lote e liberar arquivo", icon="🗑️", type="secondary", width="stretch", key=f"btn_desc_lote_{aba_atual}"):
                    qtd_d = descartar_todas_pendencias_banco(session_id, aba_atual)
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.toast(f"{qtd_d} pendência(s) descartada(s)!", icon="🎉")
                    st.success(f"🎉 {qtd_d} registro(s) com pendências foram descartados em lote! O arquivo eSocial foi liberado.")
                    st.rerun()
            with c_desc2:
                bytes_inc = gerar_relatorio_inconsistencias_bytes(session_id, aba_atual)
                st.download_button(
                    label="Baixar planilha de inconsistências (.xlsx)",
                    icon="📄",
                    data=bytes_inc,
                    file_name=f"Inconsistencias_{aba_atual}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    key=f"dl_inc_lote_{aba_atual}"
                )
            st.button("Gerar arquivo eSocial principal", icon="⬇️", disabled=True, key="btn_gerar_disabled")
        else:
            st.success(f"🟢 **ARQUIVO DA ABA '{aba_atual}' LIBERADO** — Registros validados 100% prontos!")
            nome_sugerido = gerar_nome_arquivo(aba_atual)

            if st.button("Gerar planilha eSocial (.xlsx)", icon="⚡", type="primary", width="stretch", key="btn_gerar_single"):
                with st.status("Gerando arquivo Excel no formato oficial do eSocial...", expanded=False) as status_box:
                    a_regs = exportar_registros_banco_para_list(session_id, aba_atual)
                    df_final = gerar_dataframe_esocial_final(a_regs)
                    excel_bytes = gerar_excel_esocial(df_final, modelo_path="templates/esocial.xlsx")
                    st.session_state['arquivos_gerados_cache'][aba_atual] = (nome_sugerido, excel_bytes)
                    status_box.update(label=f"Planilha eSocial da aba '{aba_atual}' gerada com sucesso!", state="complete")
                st.toast("Planilha eSocial gerada!", icon="🎉")

            if aba_atual in st.session_state['arquivos_gerados_cache']:
                nome_f, bytes_f = st.session_state['arquivos_gerados_cache'][aba_atual]
                st.download_button(
                    label=f"Baixar {nome_f}",
                    icon="⬇️",
                    data=bytes_f,
                    file_name=nome_f,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    type="primary",
                    key="dl_single_ready"
                )


def carregar_e_salvar_reinf_aba_no_banco(aba_nome, file_bytes):
    session_id = st.session_state['session_id']
    df_raw = carregar_dados_aba_cached(file_bytes, aba_nome)
    col_map, _ = auto_detectar_mapeamento_reinf(list(df_raw.columns))

    registros = validar_base_reinf(df_raw, col_map)
    salvar_registros_reinf_no_banco(session_id, aba_nome, registros)
    st.session_state['abas_processadas_reinf_db'].add(aba_nome)

# --- MENU LATERAL ---
with st.sidebar:
    st.markdown('''
    <div class="brand">
        <div class="brand-icon">📊</div>
        <div>
            <div class="brand-title">Conversor eSocial</div>
            <div class="brand-subtitle">& EFD-Reinf</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    modulo_selecionado = st.segmented_control(
        "Módulo",
        options=[MODULO_ESOCIAL, MODULO_REINF],
        default=MODULO_ESOCIAL,
        key="segmented_modulo",
        label_visibility="collapsed",
        width="stretch",
    )
    if not modulo_selecionado:
        modulo_selecionado = MODULO_ESOCIAL

    st.divider()

    if modulo_selecionado == MODULO_ESOCIAL:
        st.markdown('<div class="side-label">1 · Tipo de planilha</div>', unsafe_allow_html=True)
        tipo_planilha = st.selectbox(
            "Qual o modelo da folha que você vai subir?",
            options=list(TIPOS_PLANILHA_ESOCIAL.keys()),
            index=list(TIPOS_PLANILHA_ESOCIAL.keys()).index(st.session_state['tipo_planilha_esocial']),
            key="select_tipo_planilha",
            label_visibility="collapsed",
            help="Define o CBO padrão sugerido e o modelo esperado de colunas. Novos tipos de folha podem ser adicionados futuramente."
        )
        st.session_state['tipo_planilha_esocial'] = tipo_planilha
        st.caption(TIPOS_PLANILHA_ESOCIAL[tipo_planilha]["descricao"])

        st.markdown('<div class="side-label">2 · Folha deste mês</div>', unsafe_allow_html=True)
        arquivo_folha = st.file_uploader("Upload da Folha Atual (.xlsx)", type=["xlsx"], key="file_folha_atual", label_visibility="collapsed")

        if arquivo_folha is not None:
            if st.session_state['folha_nome'] != arquivo_folha.name or st.session_state['folha_bytes'] is None:
                st.session_state['folha_bytes'] = arquivo_folha.getvalue()
                st.session_state['folha_nome'] = arquivo_folha.name
                st.session_state['abas_processadas_db'] = set()
                st.session_state['arquivos_gerados_cache'] = {}
                st.session_state.pop('resumo_lote_esocial', None)
                st.session_state.pop('lote_zip_bytes_pronto', None)
                limpar_banco(st.session_state['session_id'])
        if st.session_state['folha_bytes'] is not None:
            st.badge(st.session_state['folha_nome'], icon="✅", color="green", width="stretch")

        st.markdown('<div class="side-label">3 · Folha anterior (opcional)</div>', unsafe_allow_html=True)
        arquivo_anterior = st.file_uploader("Upload Folha Anterior (.xlsx)", type=["xlsx"], key="file_folha_ant", label_visibility="collapsed")

        if arquivo_anterior is not None:
            if st.session_state['folha_anterior_nome'] != arquivo_anterior.name:
                st.session_state['folha_anterior_bytes'] = arquivo_anterior.getvalue()
                st.session_state['folha_anterior_nome'] = arquivo_anterior.name
                st.session_state['abas_processadas_db'] = set()
                st.session_state['arquivos_gerados_cache'] = {}
                st.session_state.pop('resumo_lote_esocial', None)
                st.session_state.pop('lote_zip_bytes_pronto', None)
                limpar_banco(st.session_state['session_id'])
        elif st.session_state['folha_anterior_bytes'] is not None and arquivo_anterior is None:
            st.session_state['folha_anterior_bytes'] = None
            st.session_state['folha_anterior_nome'] = None
            st.session_state['abas_processadas_db'] = set()
            st.session_state['arquivos_gerados_cache'] = {}
            st.session_state.pop('resumo_lote_esocial', None)
            st.session_state.pop('lote_zip_bytes_pronto', None)
            limpar_banco(st.session_state['session_id'])
        if st.session_state['folha_anterior_bytes'] is not None:
            st.badge(st.session_state['folha_anterior_nome'], icon="🔁", color="violet", width="stretch")
    else:
        st.markdown('<div class="side-label">1 · Planilha EFD-Reinf</div>', unsafe_allow_html=True)
        arquivo_reinf = st.file_uploader("Upload do Arquivo R-4010 (.xlsx)", type=["xlsx"], key="file_reinf_atual", label_visibility="collapsed")

        if arquivo_reinf is not None:
            if st.session_state['reinf_nome'] != arquivo_reinf.name or st.session_state['reinf_bytes'] is None:
                st.session_state['reinf_bytes'] = arquivo_reinf.getvalue()
                st.session_state['reinf_nome'] = arquivo_reinf.name
                st.session_state['abas_processadas_reinf_db'] = set()
                st.session_state['arquivos_gerados_cache'] = {}
                limpar_banco(st.session_state['session_id'])
        if st.session_state['reinf_bytes'] is not None:
            st.badge(st.session_state['reinf_nome'], icon="✅", color="green", width="stretch")

    st.divider()
    if st.button("Limpar sessão / nova planilha", icon="🗑️", type="tertiary", width="stretch"):
        limpar_banco(st.session_state['session_id'])
        st.session_state['folha_bytes'] = None
        st.session_state['folha_nome'] = None
        st.session_state['reinf_bytes'] = None
        st.session_state['reinf_nome'] = None
        st.session_state['abas_processadas_db'] = set()
        st.session_state['abas_processadas_reinf_db'] = set()
        st.session_state['arquivos_gerados_cache'] = {}
        st.session_state.pop('resumo_lote_esocial', None)
        st.session_state.pop('lote_zip_bytes_pronto', None)
        st.rerun()

# -----------------------------------------------------------------------------
# MÓDULO 1: eSocial (S-1200 / S-1210)
# -----------------------------------------------------------------------------
if modulo_selecionado == MODULO_ESOCIAL:
    st.markdown("""
    <div class="hero">
        <div class="hero-badge">S-1200 · S-1210</div>
        <h1>Conversor eSocial – Folha Ordinária & Suplementar</h1>
        <p>Conversão ultrarrápida (motor Calamine 12x mais rápido), descarte manual de pendências e relatório de inconsistências.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📘 Como usar (passo a passo)", expanded=st.session_state['folha_bytes'] is None):
        st.markdown("""
        1. **No menu à esquerda**, escolha o *Tipo de Planilha* e faça o upload da folha deste mês.
        2. *(Opcional)* Faça upload da **folha do mês anterior** para o sistema comparar Nome e Data de Nascimento automaticamente.
        3. **Revise a tabela abaixo**: 🔴 é erro que precisa ser corrigido, 🟡 é um alerta para conferir, 🟢 já está OK.
        4. **Clique em uma linha da tabela** para abrir o registro no painel de conferência ao lado.
        5. Corrija linha por linha, ou use os botões de **ação em lote** (aplicar dados da folha anterior / descartar pendências) para resolver tudo de uma vez.
        6. Quando o arquivo estiver **liberado**, clique em **GERAR PLANILHA ESOCIAL** e baixe o resultado.
        7. Se a planilha tiver **várias abas** (uma por mês/competência), ajuste a configuração da 1ª aba normalmente e depois use **"Aplicar esta configuração às outras competências"** para conferir e gerar todas de uma só vez.
        """)

    if st.session_state['folha_bytes'] is None:
        render_stepper(STEPPER_ESOCIAL, current_index=0)
        render_empty_state(
            "📤",
            "Envie a Folha Ordinária / Suplementar",
            "Use o menu à esquerda para escolher o <b>Tipo de Planilha</b> e fazer upload do arquivo <code>.xlsx</code> para iniciar a conferência automática."
        )
    else:
        render_esocial_arquivo_carregado()

# -----------------------------------------------------------------------------
# MÓDULO 2: EFD-Reinf (R-4010) – Pagamentos a Pessoa Física
# -----------------------------------------------------------------------------
else:
    st.markdown("""
    <div class="hero">
        <div class="hero-badge">R-4010</div>
        <h1>Conversor EFD-Reinf – Pagamentos a Pessoa Física</h1>
        <p>Conversão de rendimentos e pagamentos para o modelo oficial do EFD-Reinf R-4010 com validação de CPF e data do fato gerador.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state['reinf_bytes'] is None:
        render_stepper(STEPPER_REINF, current_index=0)
        render_empty_state(
            "📤",
            "Envie a planilha EFD-Reinf R-4010",
            "Use o menu à esquerda para fazer upload do arquivo <code>.xlsx</code> com os pagamentos a pessoa física."
        )
    else:
        file_bytes = st.session_state['reinf_bytes']
        session_id = st.session_state['session_id']

        analise_meta = analisar_arquivo_excel_rapido(file_bytes)
        abas_disponiveis = analise_meta['abas_nomes']

        st.markdown(f'<span class="file-chip">📄 {st.session_state["reinf_nome"]}</span><span class="file-chip">📁 {analise_meta["total_abas"]} aba(s)</span>', unsafe_allow_html=True)
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

        step_idx = 1 if (stats['warn'] + stats['danger'] > 0) else (2 if aba_atual not in st.session_state['arquivos_gerados_cache'] else 3)
        render_stepper(STEPPER_REINF, current_index=step_idx)

        st.markdown(f'<div class="section-title">🔎 Conferência da aba (REINF R-4010): {aba_atual}</div>', unsafe_allow_html=True)
        render_metric_cards(stats)

        st.write("")
        somente_pendencias = st.checkbox("☑ Mostrar somente pendências (Erros / Alertas)", value=(stats['warn'] + stats['danger'] > 0), key=f"chk_reinf_pend_{aba_atual}")

        registros_exibidos = obter_registros_reinf_banco(session_id, aba_atual, apenas_pendencias=somente_pendencias, limite=1000)

        col_tabela, col_edicao = st.columns([1.5, 1])

        id_selecionado = None
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
                        "Rendimento Bruto (R$)": float(r['rendimento_bruto']),
                        "Parcela Isenta (R$)": float(r['parcela_isenta']),
                        "Observação": r['observacao_pagamento'],
                        "Status": r['status']
                    })

                df_tabela = pd.DataFrame(tabela_data)
                evento_tabela = st.dataframe(
                    df_tabela,
                    hide_index=True,
                    height=360,
                    column_config={
                        "Rendimento Bruto (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Parcela Isenta (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    },
                    on_select="rerun",
                    selection_mode="single-row",
                    key=f"grid_reinf_{aba_atual}_{somente_pendencias}",
                )
                st.caption("💡 Clique em uma linha da tabela para conferir/corrigir o registro no painel ao lado.")

                linhas_sel = evento_tabela.selection.rows if evento_tabela and evento_tabela.selection else []
                idx_sel = linhas_sel[0] if linhas_sel and linhas_sel[0] < len(registros_exibidos) else 0
                id_selecionado = registros_exibidos[idx_sel]['id']

        with col_edicao:
            st.markdown("### Conferir / Tratar Registro R-4010")
            if id_selecionado:
                reg_sel = next(r for r in registros_exibidos if r['id'] == id_selecionado)
                cor_badge, label_badge = status_para_badge(reg_sel['status'])

                with st.container(border=True):
                    bc1, bc2 = st.columns([1, 2])
                    with bc1:
                        st.badge(label_badge, color=cor_badge)
                    with bc2:
                        st.markdown(f"**Linha {reg_sel['linha']}**")

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
                            submit_aprovar = st.form_submit_button("Aprovar", icon="✅", width="stretch")
                        with btn_c2:
                            submit_corrigir = st.form_submit_button("Salvar", icon="💾", width="stretch")
                        with btn_c3:
                            submit_descartar = st.form_submit_button("Descartar", icon="🗑️", width="stretch")

                if submit_aprovar:
                    if reg_sel['erros_criticos']:
                        st.error("🔴 Não é possível aprovar um registro com Erro Crítico. Você pode Corrigir ou Descartar a linha.")
                    else:
                        atualizar_registro_reinf_banco(reg_sel['id'], novo_cpf, nova_data, novo_bruto, nova_isenta, nova_obs, acao='aprovar')
                        st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                        st.toast(f"Linha {reg_sel['linha']} aprovada!", icon="✅")
                        st.success(f"Linha {reg_sel['linha']} aprovada!")
                        st.rerun()

                if submit_corrigir:
                    atualizar_registro_reinf_banco(reg_sel['id'], novo_cpf, nova_data, novo_bruto, nova_isenta, nova_obs, acao='corrigir')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.toast(f"Linha {reg_sel['linha']} atualizada!", icon="💾")
                    st.success(f"Linha {reg_sel['linha']} atualizada e validada!")
                    st.rerun()

                if submit_descartar:
                    atualizar_registro_reinf_banco(reg_sel['id'], novo_cpf, nova_data, novo_bruto, nova_isenta, nova_obs, acao='descartar')
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.toast(f"Linha {reg_sel['linha']} descartada.", icon="🗑️")
                    st.warning(f"Linha {reg_sel['linha']} descartada da exportação principal!")
                    st.rerun()

        st.divider()
        st.markdown('<div class="section-title">📦 Geração e Download do Arquivo EFD-Reinf R-4010</div>', unsafe_allow_html=True)

        if st.button(f"Gerar relatório de inconsistências / descartes da aba '{aba_atual}' (.xlsx)", icon="📄", key=f"btn_reinf_inc_{aba_atual}"):
            bytes_inc = gerar_relatorio_inconsistencias_reinf_bytes(session_id, aba_atual)
            st.download_button(
                label=f"Baixar Relatorio_Inconsistencias_Reinf_{aba_atual}.xlsx",
                icon="⬇️",
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
                if st.button(f"Descartar todas as {st_aba['danger'] + st_aba['warn']} pendências em lote e liberar arquivo", icon="🗑️", type="secondary", width="stretch", key=f"btn_reinf_desc_lote_{aba_atual}"):
                    qtd_d = descartar_todas_pendencias_reinf_banco(session_id, aba_atual)
                    st.session_state['arquivos_gerados_cache'].pop(aba_atual, None)
                    st.toast(f"{qtd_d} pendência(s) descartada(s)!", icon="🎉")
                    st.success(f"🎉 {qtd_d} registro(s) com pendências foram descartados em lote! O arquivo EFD-Reinf foi liberado.")
                    st.rerun()
            with c_desc2:
                bytes_inc = gerar_relatorio_inconsistencias_reinf_bytes(session_id, aba_atual)
                st.download_button(
                    label="Baixar planilha de inconsistências (.xlsx)",
                    icon="📄",
                    data=bytes_inc,
                    file_name=f"Inconsistencias_Reinf_{aba_atual}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    key=f"dl_reinf_inc_lote_{aba_atual}"
                )
            st.button("Gerar arquivo EFD-Reinf R-4010 principal", icon="⬇️", disabled=True, key="btn_reinf_gerar_disabled")
        else:
            st.success("🟢 **ARQUIVO PRINCIPAL LIBERADO** — Registros R-4010 validados 100% prontos!")

            if len(st.session_state['abas_selecionadas']) == 1:
                a_nome = st.session_state['abas_selecionadas'][0]
                nome_sugerido = f"EFD_Reinf_R4010_{a_nome}.xlsx"

                if st.button("Gerar planilha EFD-Reinf R-4010 (.xlsx)", icon="⚡", type="primary", width="stretch", key="btn_reinf_gerar_single"):
                    with st.status("Gerando arquivo Excel no formato oficial do EFD-Reinf R-4010...", expanded=False) as status_box:
                        a_regs = exportar_registros_reinf_banco_para_list(session_id, a_nome)
                        df_final = gerar_dataframe_reinf_final(a_regs)
                        excel_bytes = gerar_excel_esocial(df_final, modelo_path="templates/reinf_r4010.xlsx")
                        st.session_state['arquivos_gerados_cache'][a_nome] = (nome_sugerido, excel_bytes)
                        status_box.update(label="Planilha EFD-Reinf R-4010 gerada com sucesso!", state="complete")
                    st.toast("Planilha EFD-Reinf gerada!", icon="🎉")

                if a_nome in st.session_state['arquivos_gerados_cache']:
                    nome_f, bytes_f = st.session_state['arquivos_gerados_cache'][a_nome]
                    st.download_button(
                        label=f"Baixar {nome_f}",
                        icon="⬇️",
                        data=bytes_f,
                        file_name=nome_f,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch",
                        type="primary",
                        key="dl_reinf_single_ready"
                    )
            else:
                if st.button("Gerar pacote de arquivos R-4010 das abas selecionadas (ZIP)", icon="⚡", type="primary", width="stretch", key="btn_reinf_gerar_multi"):
                    with st.status("Gerando planilhas Excel R-4010 e empacotando em ZIP...", expanded=False) as status_box:
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
                        status_box.update(label="Pacote ZIP EFD-Reinf R-4010 gerado com sucesso!", state="complete")
                    st.toast("Pacote ZIP gerado!", icon="🎉")

                if 'reinf_zip_bytes_pronto' in st.session_state:
                    st.download_button(
                        label="Baixar todos os arquivos R-4010 (pacote ZIP)",
                        icon="📦",
                        data=st.session_state['reinf_zip_bytes_pronto'],
                        file_name="EFD_Reinf_R4010.zip",
                        mime="application/zip",
                        width="stretch",
                        type="primary",
                        key="dl_reinf_zip_ready"
                    )
