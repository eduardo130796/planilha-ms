import pandas as pd
import streamlit as st
from utils.excel import listar_abas_excel, ler_aba_excel

def analisar_arquivo_excel_rapido(file_bytes_ou_path) -> dict:
    """
    Retorna metadados das abas de forma instantânea sem ler todas as células.
    """
    abas_nomes = listar_abas_excel(file_bytes_ou_path)
    resumo_abas = [{'nome': nome} for nome in abas_nomes]
        
    return {
        'total_abas': len(abas_nomes),
        'abas': resumo_abas,
        'abas_nomes': abas_nomes
    }

@st.cache_data(show_spinner="Carregando e processando aba do Excel...")
def carregar_dados_aba_cached(file_bytes_ou_path, aba_nome: str) -> pd.DataFrame:
    """
    Lê a aba do Excel com cache do Streamlit. Executa APENAS UMA VEZ por aba/arquivo,
    garantindo performance ultra-rápida nas interações subsequentes.
    """
    df = ler_aba_excel(file_bytes_ou_path, aba_nome=aba_nome)
    df = df.dropna(how='all').copy()
    return df
