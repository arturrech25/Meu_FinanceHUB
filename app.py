import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import os
import hashlib
from datetime import datetime
from sqlalchemy.orm import sessionmaker

# Configuração da Página Web
st.set_page_config(page_title="FinanceHub", page_icon="💸", layout="wide")

# Conecta ao seu banco de dados no Google Drive
DB_PATH = 'financehub.db'
engine = create_engine(f'sqlite:///{DB_PATH}')
from sqlalchemy import Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Planta baixa da nossa tabela
class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    category = Column(String, default="Outros")
    hash_id = Column(String, unique=True, nullable=False)

# Essa é a linha mágica que constrói a tabela se ela não existir
Base.metadata.create_all(engine)

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
# ==========================================
# TELA 2: IMPORTAÇÃO
# ==========================================
elif menu == "Importar Fatura":
    st.header("📥 Importar nova Fatura (C6 Bank)")
    arquivo = st.file_uploader("Arraste seu arquivo .csv do C6 Bank aqui", type=["csv"])
    
    if arquivo is not None:
        if st.button("Processar Fatura"):
            try:
                # 1. Lê a planilha do jeito que o C6 manda (separado por ;)
                df_upload = pd.read_csv(arquivo, sep=';', encoding='utf-8')
                df_upload.columns = [c.strip().lower() for c in df_upload.columns]
                
                # 2. Conecta no banco de dados para salvar
                SessionLocal = sessionmaker(bind=engine)
                db = SessionLocal()
                
                importados = 0
                ignorados = 0
                
                # Barra de progresso visual no site
                progress_bar = st.progress(0)
                total_linhas = len(df_upload)
                
                for index, row in df_upload.iterrows():
                    # Atualiza barrinha de progresso
                    progress_bar.progress(min((index + 1) / total_linhas, 1.0))
                    
                    date_val = row.get('data de compra')
                    desc = str(row.get('descrição', 'Desconhecido'))
                    amount_raw = row.get('valor (em r$)')
                    
                    # Se não tiver valor, pula a linha
                    if pd.isna(amount_raw) or amount_raw == '': 
                        continue
                    
                    # Converte data
                    dt_obj = datetime.strptime(str(date_val), "%d/%m/%Y").date()
                    
                    # Converte moeda com segurança (nova regra de conversão)
                    val_str = str(amount_raw).strip()
                    if ',' in val_str and '.' in val_str:
                        val_str = val_str.replace('.', '').replace(',', '.')
                    elif ',' in val_str:
                        val_str = val_str.replace(',', '.')
                    
                    amount = float(val_str)
                    
                    t_type = "EXPENSE" if amount > 0 else "INCOME"
                    
                    # Cria o código único (hash)
                    raw_str = f"{dt_obj.strftime('%Y-%m-%d')}_{desc}_{amount}".encode('utf-8')
                    tx_hash = hashlib.sha256(raw_str).hexdigest()
                    
                    # Verifica no banco se já existe
                    if db.query(Transaction).filter_by(hash_id=tx_hash).first():
                        ignorados += 1
                        continue
                    
                    # Salva
                    nova_compra = Transaction(
                        date=dt_obj, 
                        description=desc, 
                        amount=abs(amount), 
                        type=t_type, 
                        hash_id=tx_hash
                    )
                    db.add(nova_compra)
                    importados += 1
                
                # Salva de vez no banco
                db.commit()
                db.close()
                
                st.success(f"✅ Importação finalizada! {importados} compras novas adicionadas. {ignorados} ignoradas (já existiam).")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Erro ao ler a planilha: {e}")

# ==========================================
# TELA 3: CHATBOT (Opcional - Recoloquei aqui caso tenha apagado sem querer)
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
