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
DB_PATH = 'financehub_v5.db'
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
            # Prepara as datas
            df['date'] = pd.to_datetime(df['date'])
            df['month_year'] = df['date'].dt.to_period('M').astype(str)
            
            # --- FILTROS LATERAIS ---
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filtros")
            
            meses_disponiveis = sorted(df['month_year'].unique(), reverse=True)
            meses_selecionados = st.sidebar.multiselect("Selecione os Meses", meses_disponiveis, default=meses_disponiveis)
            
            categorias_disponiveis = sorted(df['category'].unique())
            categorias_selecionadas = st.sidebar.multiselect("Selecione as Categorias", categorias_disponiveis, default=categorias_disponiveis)
            
            # Aplica os filtros
            df_filtrado = df[(df['month_year'].isin(meses_selecionados)) & (df['category'].isin(categorias_selecionadas))]
            
            if df_filtrado.empty:
                st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                # --- MÉTRICAS PRINCIPAIS (KPIs) ---
                despesas = df_filtrado[df_filtrado['type'] == 'EXPENSE']
                entradas = df_filtrado[df_filtrado['type'] == 'INCOME']
                
                total_gasto = despesas['amount'].sum()
                total_entradas = entradas['amount'].sum()
                saldo = total_entradas - total_gasto
                
                maior_compra = despesas['amount'].max() if not despesas.empty else 0
                nome_maior_compra = despesas.loc[despesas['amount'].idxmax()]['description'] if not despesas.empty else "-"
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Gasto", f"R$ {total_gasto:,.2f}")
                col2.metric("Total Entradas", f"R$ {total_entradas:,.2f}")
                col3.metric("Saldo do Período", f"R$ {saldo:,.2f}", delta=f"R$ {saldo:,.2f}")
                col4.metric("Maior Compra", f"R$ {maior_compra:,.2f}", help=f"Estabelecimento: {nome_maior_compra}")
                
                st.markdown("---")
                
                # --- ÁREA DOS GRÁFICOS ---
                # Linha 1: Gráficos de Mês e Categoria
                col_grafico1, col_grafico2 = st.columns(2)
                
                with col_grafico1:
                    gastos_mes = despesas.groupby('month_year')['amount'].sum().reset_index()
                    fig1 = px.bar(gastos_mes, x='month_year', y='amount', title="📉 Despesas por Mês", text_auto='.2s', color_discrete_sequence=['#EF4444'])
                    fig1.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig1, use_container_width=True)
                    
                with col_grafico2:
                    gastos_cat = despesas.groupby('category')['amount'].sum().reset_index()
                    fig2 = px.pie(gastos_cat, values='amount', names='category', hole=0.5, title="🍩 Divisão por Categoria")
                    fig2.update_traces(textposition='inside', textinfo='percent')
                    st.plotly_chart(fig2, use_container_width=True)
                
                # Linha 2: Top Estabelecimentos e Evolução Diária
                col_grafico3, col_grafico4 = st.columns(2)
                
                with col_grafico3:
                    top_estabelecimentos = despesas.groupby('description')['amount'].sum().nlargest(10).reset_index()
                    fig3 = px.bar(top_estabelecimentos, x='amount', y='description', orientation='h', 
                                  title="🏆 Top 10 Estabelecimentos", color_discrete_sequence=['#3B82F6'])
                    fig3.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig3, use_container_width=True)
                    
                with col_grafico4:
                    gastos_diarios = despesas.groupby('date')['amount'].sum().reset_index()
                    fig4 = px.line(gastos_diarios, x='date', y='amount', title="📈 Evolução Diária de Gastos", markers=True, color_discrete_sequence=['#10B981'])
                    st.plotly_chart(fig4, use_container_width=True)
                
                # --- TABELA INTERATIVA ---
                st.markdown("---")
                st.subheader("📋 Histórico Detalhado")
                
                # Prepara a tabela para ficar mais bonita
                df_mostrar = df_filtrado[['date', 'description', 'category', 'amount', 'type']].copy()
                df_mostrar['date'] = df_mostrar['date'].dt.strftime('%d/%m/%Y')
                df_mostrar.columns = ['Data', 'Descrição', 'Categoria', 'Valor (R$)', 'Tipo']
                
                st.dataframe(df_mostrar.sort_values('Data', ascending=False), use_container_width=True, hide_index=True)
            
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.error(f"Erro ao carregar dados: {e}")

# ==========================================
# TELA 2: IMPORTAÇÃO
# ==========================================
elif menu == "Importar Fatura":
    st.header("📥 Importar nova Fatura (C6 Bank)")
    arquivo = st.file_uploader("Arraste seu arquivo .csv do C6 Bank aqui", type=["csv"])
    
    if arquivo is not None:
        if st.button("Processar Fatura"):
            try:
                df_upload = pd.read_csv(arquivo, sep=';', encoding='utf-8')
                df_upload.columns = [c.strip().lower() for c in df_upload.columns]
                
                SessionLocal = sessionmaker(bind=engine)
                db = SessionLocal()
                
                importados = 0
                ignorados = 0
                
                # --- O CÉREBRO DA CATEGORIZAÇÃO (Você pode adicionar mais palavras aqui) ---
                regras = {
                    'ifood': 'Alimentação',
                    'mcdonalds': 'Alimentação',
                    'restaurante': 'Alimentação',
                    'padaria': 'Alimentação',
                    'uber': 'Transporte',
                    '99app': 'Transporte',
                    'posto': 'Combustível',
                    'farmacia': 'Saúde',
                    'netflix': 'Assinaturas',
                    'spotify': 'Assinaturas',
                    'amazon': 'Compras',
                    'stanley': 'Compras',
                    'mercado': 'Mercado',
                    'supermercado': 'Mercado',
                    'pgto': 'Pagamento da Fatura'
                }
                
                progress_bar = st.progress(0)
                total_linhas = len(df_upload)
                
                for index, row in df_upload.iterrows():
                    progress_bar.progress(min((index + 1) / total_linhas, 1.0))
                    
                    date_val = row.get('data de compra')
                    desc = str(row.get('descrição', 'Desconhecido'))
                    amount_raw = row.get('valor (em r$)')
                    
                    # 💡 AQUI: Pegamos a categoria oficial do banco C6!
                    categoria_c6 = str(row.get('categoria', '')).strip()
                    
                    if pd.isna(amount_raw) or amount_raw == '': 
                        continue
                        
                    # 🚫 TRAVA DE PAGAMENTOS: Ignora pagamentos de fatura, IOF e estornos
                    desc_lower = desc.lower()
                    termos_ignorados = ["inclusão de pagamento", "pagamento efetuado", "iof", "estorno", "pagamento de fatura"]
                    
                    if any(termo in desc_lower for termo in termos_ignorados):
                        continue # Pula essa linha da planilha e não salva!
                    
                    dt_obj = datetime.strptime(str(date_val), "%d/%m/%Y").date()
                    
                    val_str = str(amount_raw).strip()
                    if ',' in val_str and '.' in val_str:
                        val_str = val_str.replace('.', '').replace(',', '.')
                    elif ',' in val_str:
                        val_str = val_str.replace(',', '.')
                    
                    amount = float(val_str)
                    t_type = "EXPENSE" if amount > 0 else "INCOME"
                    
                    # --- SISTEMA DE CATEGORIZAÇÃO INTELIGENTE ---
                    # 1. Tenta usar a categoria do C6 Bank
                    if categoria_c6 and categoria_c6.lower() != 'nan' and categoria_c6 != '':
                        categoria_definida = categoria_c6.title() # Deixa a primeira letra maiúscula
                    else:
                        # 2. Se o C6 não souber, usa nossas regras
                        categoria_definida = "Outros"
                        desc_lower = desc.lower()
                        for palavra_chave, categoria_nome in regras.items():
                            if palavra_chave in desc_lower:
                                categoria_definida = categoria_nome
                                break
                    
                    raw_str = f"{dt_obj.strftime('%Y-%m-%d')}_{desc}_{amount}".encode('utf-8')
                    tx_hash = hashlib.sha256(raw_str).hexdigest()
                    
                    if db.query(Transaction).filter_by(hash_id=tx_hash).first():
                        ignorados += 1
                        continue
                    
                    nova_compra = Transaction(
                        date=dt_obj, 
                        description=desc, 
                        amount=abs(amount), 
                        type=t_type, 
                        category=categoria_definida, 
                        hash_id=tx_hash
                    )
                    db.add(nova_compra)
                    importados += 1
                
                db.commit()
                db.close()
                
                st.success(f"✅ Importação finalizada! {importados} compras categorizadas e salvas. {ignorados} ignoradas (já existiam).")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Erro ao ler a planilha: {e}")
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
