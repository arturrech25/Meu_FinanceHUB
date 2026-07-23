import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import os

# Configuração da Página Web
st.set_page_config(page_title="FinanceHub", page_icon="💸", layout="wide")

# Conecta ao seu banco de dados no Google Drive
DB_PATH = 'financehub.db'
engine = create_engine(f'sqlite:///{DB_PATH}')

# Título do App
st.title("💸 FinanceHub - Gestão Pessoal")
st.markdown("---")

# Cria um menu lateral
menu = st.sidebar.radio("Navegação", ["Dashboard", "Importar Fatura", "Assistente IA"])

# ==========================================
# TELA 1: DASHBOARD
# ==========================================
if menu == "Dashboard":
    st.header("📊 Seu Dashboard Financeiro")
    
    try:
        df = pd.read_sql("SELECT * FROM transactions", engine)
        if df.empty:
            st.warning("Seu banco de dados está vazio. Vá na aba 'Importar Fatura'.")
        else:
            df['date'] = pd.to_datetime(df['date'])
            df['month_year'] = df['date'].dt.to_period('M').astype(str)
            
            # Métricas no topo
            total_gasto = df[df['type'] == 'EXPENSE']['amount'].sum()
            total_entradas = df[df['type'] == 'INCOME']['amount'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Gasto (Histórico)", f"R$ {total_gasto:,.2f}")
            col2.metric("Total Entradas (Histórico)", f"R$ {total_entradas:,.2f}")
            col3.metric("Lançamentos Registrados", len(df))
            
            st.markdown("---")
            
            # Gráficos
            col_grafico1, col_grafico2 = st.columns(2)
            
            with col_grafico1:
                gastos_mes = df[df['type'] == 'EXPENSE'].groupby('month_year')['amount'].sum().reset_index()
                fig1 = px.bar(gastos_mes, x='month_year', y='amount', title="Despesas Mensais")
                st.plotly_chart(fig1, use_container_width=True)
                
            with col_grafico2:
                top_desc = df[df['type'] == 'EXPENSE'].groupby('category')['amount'].sum().nlargest(5).reset_index()
                fig2 = px.pie(top_desc, values='amount', names='category', hole=0.5, title="Top 5 Categorias")
                st.plotly_chart(fig2, use_container_width=True)
                
            st.subheader("Últimas Movimentações")
            st.dataframe(df.sort_values('date', ascending=False).head(10), use_container_width=True)
            
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

# ==========================================
# TELA 2: IMPORTAÇÃO
# ==========================================
elif menu == "Importar Fatura":
    st.header("📥 Importar nova Fatura (C6 Bank)")
    arquivo = st.file_uploader("Arraste seu arquivo .csv do C6 Bank aqui", type=["csv"])
    
    if arquivo is not None:
        if st.button("Processar Fatura"):
            # Aqui entraria a lógica de leitura e salvamento que fizemos antes
            # Para manter simples nesta visualização, apenas mostramos sucesso.
            st.success("Arquivo recebido com sucesso! O FinanceHub processará isso no sistema principal.")
            st.dataframe(pd.read_csv(arquivo, sep=';').head())

# ==========================================
# TELA 3: CHATBOT
# ==========================================
elif menu == "Assistente IA":
    st.header("💬 Converse com seus dados")
    pergunta = st.text_input("Qual a sua dúvida financeira?")
    
    if st.button("Perguntar") and pergunta:
        try:
            df = pd.read_sql("SELECT * FROM transactions", engine)
            if "total" in pergunta.lower() and "gasto" in pergunta.lower():
                total = df[df['type'] == 'EXPENSE']['amount'].sum()
                st.success(f"O seu gasto total acumulado é de R$ {total:,.2f}.")
            else:
                st.info("Desculpe, ainda estou aprendendo. Tente perguntar: 'Qual foi meu total gasto?'")
        except:
            st.error("Erro ao ler banco de dados.")
