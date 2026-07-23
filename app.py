import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import hashlib
from datetime import datetime
import textwrap

# Tenta importar o pacote do Gemini (pip install google-generativeai)
try:
    import google.generativeai as genai
    HAS_AI = True
except ImportError:
    HAS_AI = False

# ==========================================
# CONFIGURAÇÃO INICIAL E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="FinanceHub", page_icon="💸", layout="wide")

DB_PATH = 'financehub_v6.db' # Atualizado para v6 para não dar conflito com o antigo
engine = create_engine(f'sqlite:///{DB_PATH}')
Base = declarative_base()

# Tabela de Transações
class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    category = Column(String, default="Outros")
    hash_id = Column(String, unique=True, nullable=False)

# Tabela de Regras de Categorização (Melhoria 3)
class CategoryRule(Base):
    __tablename__ = 'category_rules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

# Semeando regras iniciais se o banco estiver vazio
def seed_rules():
    db = SessionLocal()
    if db.query(CategoryRule).count() == 0:
        regras_iniciais = {
            'ifood': 'Alimentação', 'mcdonalds': 'Alimentação', 'padaria': 'Alimentação',
            'uber': 'Transporte', '99app': 'Transporte', 'posto': 'Combustível',
            'farmacia': 'Saúde', 'netflix': 'Assinaturas', 'spotify': 'Assinaturas',
            'amazon': 'Compras', 'mercado': 'Mercado'
        }
        for kw, cat in regras_iniciais.items():
            db.add(CategoryRule(keyword=kw, category=cat))
        db.commit()
    db.close()
seed_rules()

# ==========================================
# MENU E NAVEGAÇÃO
# ==========================================
st.title("💸 FinanceHub - Gestão Pessoal")
st.markdown("---")

menu = st.sidebar.radio("Navegação", ["Dashboard", "Importar Fatura", "Configurações", "Assistente IA"])

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
            
            # --- FILTROS LATERAIS ---
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filtros")
            
            meses_disponiveis = sorted(df['month_year'].unique(), reverse=True)
            meses_selecionados = st.sidebar.multiselect(
                "Selecione os Meses", 
                meses_disponiveis, 
                default=[meses_disponiveis[0]] if meses_disponiveis else []
            )
            
            categorias_disponiveis = sorted(df['category'].unique())
            categorias_selecionadas = st.sidebar.multiselect(
                "Filtrar Categorias", 
                categorias_disponiveis, 
                default=categorias_disponiveis
            )
            
            df_filtrado = df[(df['month_year'].isin(meses_selecionados)) & (df['category'].isin(categorias_selecionadas))]
            
            if df_filtrado.empty:
                st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                # --- MÉTRICAS ---
                despesas = df_filtrado[df_filtrado['type'] == 'EXPENSE']
                entradas = df_filtrado[df_filtrado['type'] == 'INCOME']
                
                total_gasto = despesas['amount'].sum()
                total_entradas = entradas['amount'].sum()
                saldo = total_entradas - total_gasto
                maior_compra = despesas['amount'].max() if not despesas.empty else 0
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Gasto", f"R$ {total_gasto:,.2f}")
                col2.metric("Maior Compra", f"R$ {maior_compra:,.2f}")
                
                st.markdown("---")
                
                # --- GRÁFICOS ---
                col_grafico1, col_grafico2 = st.columns(2)
                
                with col_grafico1:
                    # Agrupa apenas as DESPESAS por mês
                    gastos_mes = despesas.groupby('month_year')['amount'].sum().reset_index()
                    fig1 = px.bar(gastos_mes, x='month_year', y='amount', 
                                  title="📉 Evolução de Despesas", 
                                  text_auto='.2s', 
                                  color_discrete_sequence=['#EF4444'])
                    fig1.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig1, use_container_width=True)
                    
                with col_grafico2:
                    # Gráfico de pizza também focado só nas despesas
                    gastos_cat = despesas.groupby('category')['amount'].sum().reset_index()
                    fig2 = px.pie(gastos_cat, values='amount', names='category', hole=0.5, title="🍩 Despesas por Categoria (Período Selecionado)")
                    fig2.update_traces(textposition='inside', textinfo='percent')
                    st.plotly_chart(fig2, use_container_width=True)
                
                # --- TABELA EDITÁVEL ---
                st.markdown("---")
                st.subheader("📋 Histórico Detalhado (Editável)")
                st.caption("Altere a categoria diretamente na tabela e clique em Salvar.")
                
                # Prepara dados para o editor
                df_mostrar = df_filtrado[['id', 'date', 'description', 'category', 'amount', 'type']].copy()
                df_mostrar['date'] = df_mostrar['date'].dt.strftime('%d/%m/%Y')
                
                edited_df = st.data_editor(
                    df_mostrar, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "id": None, # Esconde o ID
                        "date": st.column_config.TextColumn("Data", disabled=True),
                        "description": st.column_config.TextColumn("Descrição", disabled=True),
                        "amount": st.column_config.NumberColumn("Valor (R$)", disabled=True),
                        "type": st.column_config.TextColumn("Tipo", disabled=True),
                        "category": st.column_config.SelectboxColumn("Categoria", options=categorias_disponiveis + ["Nova Categoria..."])
                    }
                )
                
                if st.button("💾 Salvar Alterações de Categoria", type="primary"):
                    db = SessionLocal()
                    alteracoes = 0
                    for index, row in edited_df.iterrows():
                        old_cat = df_mostrar.loc[index, 'category']
                        new_cat = row['category']
                        if old_cat != new_cat:
                            db.query(Transaction).filter_by(id=row['id']).update({"category": new_cat})
                            alteracoes += 1
                    db.commit()
                    db.close()
                    if alteracoes > 0:
                        st.success(f"{alteracoes} transações atualizadas! Recarregue a página para ver os gráficos atualizados.")
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detectada.")
                        
    except Exception as e:
        st.error(f"Erro ao carregar dados do Dashboard: {e}")
# ==========================================
# TELA 2: IMPORTAÇÃO
# ==========================================
elif menu == "Importar Fatura":
    st.header("📥 Importar novas Faturas (C6 Bank)")
    
    # MUDANÇA AQUI: accept_multiple_files=True
    arquivos = st.file_uploader("Arraste seus arquivos .csv do C6 Bank aqui", type=["csv"], accept_multiple_files=True)
    
    # Se a lista de arquivos não estiver vazia
    if arquivos:
        if st.button("Processar Faturas"):
            try:
                db = SessionLocal()
                
                # Busca as regras dinâmicas do banco
                regras_db = db.query(CategoryRule).all()
                regras = {r.keyword.lower(): r.category for r in regras_db}
                
                importados_total = 0
                ignorados_total = 0
                
                # Barra de progresso geral
                progress_bar = st.progress(0)
                passo_atual = 0
                
                # Conta o total de linhas em todas as planilhas para a barra de progresso
                total_linhas_geral = sum([len(pd.read_csv(arq, sep=';', encoding='utf-8')) for arq in arquivos])
                
                # Reseta o ponteiro dos arquivos após a contagem
                for arq in arquivos:
                    arq.seek(0)
                
                ocorrencias = {} 
                st.info(f"Processando {len(arquivos)} arquivo(s)...")
                
                # Laço para passar por cada arquivo upado
                for arquivo in arquivos:
                    df_upload = pd.read_csv(arquivo, sep=';', encoding='utf-8')
                    df_upload.columns = [c.strip().lower() for c in df_upload.columns]
                    
                    for index, row in df_upload.iterrows():
                        passo_atual += 1
                        progress_bar.progress(min(passo_atual / total_linhas_geral, 1.0))
                        
                        date_val = row.get('data de compra')
                        desc = str(row.get('descrição', 'Desconhecido')).strip()
                        amount_raw = row.get('valor (em r$)')
                        categoria_c6 = str(row.get('categoria', '')).strip()
                        
                        if pd.isna(amount_raw) or amount_raw == '': 
                            continue
                            
                        desc_lower = desc.lower()
                        termos_ignorados = ["inclusão de pagamento", "pagamento efetuado", "iof", "estorno", "pagamento de fatura"]
                        if any(termo in desc_lower for termo in termos_ignorados):
                            continue
                        
                        dt_obj = datetime.strptime(str(date_val), "%d/%m/%Y").date()
                        
                        val_str = str(amount_raw).strip().replace('.', '').replace(',', '.') if ',' in str(amount_raw) and '.' in str(amount_raw) else str(amount_raw).strip().replace(',', '.')
                        amount = float(val_str)
                        t_type = "EXPENSE" if amount > 0 else "INCOME"
                        
                        # Categorização inteligente (C6 -> Banco de Regras -> Outros)
                        categoria_definida = "Outros"
                        if categoria_c6 and categoria_c6.lower() != 'nan':
                            categoria_definida = categoria_c6.title()
                        else:
                            for palavra_chave, categoria_nome in regras.items():
                                if palavra_chave in desc_lower:
                                    categoria_definida = categoria_nome
                                    break
                        
                        # Resolução da colisão do Hash
                        chave_base = f"{dt_obj.strftime('%Y-%m-%d')}_{desc}_{amount}"
                        ocorrencias[chave_base] = ocorrencias.get(chave_base, 0) + 1
                        
                        raw_str = f"{chave_base}_{ocorrencias[chave_base]}".encode('utf-8')
                        tx_hash = hashlib.sha256(raw_str).hexdigest()
                        
                        if db.query(Transaction).filter_by(hash_id=tx_hash).first():
                            ignorados_total += 1
                            continue
                        
                        nova_compra = Transaction(
                            date=dt_obj, description=desc, amount=abs(amount), 
                            type=t_type, category=categoria_definida, hash_id=tx_hash
                        )
                        db.add(nova_compra)
                        importados_total += 1
                
                # Salva tudo no banco de uma vez só no final
                db.commit()
                db.close()
                
                st.success(f"✅ Importação finalizada! {importados_total} compras salvas. {ignorados_total} ignoradas (já existiam).")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Erro ao processar as planilhas: {e}")
# ==========================================
# TELA 3: CONFIGURAÇÕES (REGRAS DINÂMICAS)
# ==========================================
elif menu == "Configurações":
    st.header("⚙️ Configurações de Categorização")
    st.write("Adicione palavras-chave para que o sistema categorize suas compras automaticamente nas próximas importações.")
    
    db = SessionLocal()
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Adicionar Nova Regra")
        nova_palavra = st.text_input("Palavra-chave (ex: uber, ifood, farmacia)").lower().strip()
        nova_categoria = st.text_input("Categoria (ex: Transporte, Alimentação)").title().strip()
        
        if st.button("Salvar Regra"):
            if nova_palavra and nova_categoria:
                existe = db.query(CategoryRule).filter_by(keyword=nova_palavra).first()
                if existe:
                    st.warning("Esta palavra-chave já existe nas regras.")
                else:
                    db.add(CategoryRule(keyword=nova_palavra, category=nova_categoria))
                    db.commit()
                    st.success(f"Regra '{nova_palavra}' -> '{nova_categoria}' salva!")
                    st.rerun()
            else:
                st.error("Preencha ambos os campos.")
                
    with col2:
        st.subheader("Regras Atuais")
        regras = pd.read_sql("SELECT id, keyword as 'Palavra Chave', category as 'Categoria' FROM category_rules", engine)
        if not regras.empty:
            st.dataframe(regras, hide_index=True, use_container_width=True)
            # Função de deletar regra
            del_id = st.number_input("ID da regra para excluir", min_value=0, step=1)
            if st.button("Excluir Regra") and del_id > 0:
                db.query(CategoryRule).filter_by(id=del_id).delete()
                db.commit()
                st.rerun()
        else:
            st.info("Nenhuma regra configurada.")
            
    db.close()

# ==========================================
# TELA 4: ASSISTENTE IA (GEMINI)
# ==========================================
elif menu == "Assistente IA":
    st.header("🤖 Assistente Financeiro IA (Google Gemini)")
    
    if not HAS_AI:
        st.error("A biblioteca do Google Gemini não está instalada. Para usar esta função, pare a aplicação e digite no terminal: `pip install google-generativeai`")
    else:
        st.info("Obtenha sua API Key grátis em: https://aistudio.google.com/app/apikey")
        api_key = st.text_input("Insira sua API Key do Google Gemini:", type="password")
        
        if api_key:
            genai.configure(api_key=api_key)
            
            # MUDANÇA AQUI: Trocamos o nome do modelo para a versão suportada atual
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            df = pd.read_sql("SELECT date, description, amount, type, category FROM transactions", engine)
            
            if df.empty:
                st.warning("Seu banco de dados está vazio. Importe transações primeiro.")
            else:
                st.success("IA conectada e pronta para ler seus dados!")
                
                # Criando um resumo dos dados para não estourar o limite de tokens
                resumo_por_categoria = df.groupby(['category', 'type'])['amount'].sum().to_dict()
                compras_recentes = df.sort_values(by='date', ascending=False).head(20).to_string(index=False)
                
                contexto_dados = textwrap.dedent(f"""
                Você é um consultor financeiro pessoal amigável e direto. 
                Aqui está um resumo dos gastos do usuário:
                Totais por categoria/tipo: {resumo_por_categoria}
                
                Últimas 20 transações:
                {compras_recentes}
                """)
                
                pergunta = st.chat_input("Ex: Quais categorias estão drenando meu dinheiro?")
                
                if pergunta:
                    with st.chat_message("user"):
                        st.write(pergunta)
                        
                    with st.chat_message("assistant"):
                        with st.spinner("Analisando suas finanças..."):
                            prompt = f"{contexto_dados}\n\nO usuário pergunta: {pergunta}"
                            try:
                                resposta = model.generate_content(prompt)
                                st.write(resposta.text)
                            except Exception as e:
                                st.error(f"Erro na IA: {e}")
