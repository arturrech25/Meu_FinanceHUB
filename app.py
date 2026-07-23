import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base, sessionmaker
import hashlib
from datetime import datetime
import textwrap
import io

try:
    import google.generativeai as genai
    HAS_AI = True
except ImportError:
    HAS_AI = False

# ==========================================
# CONFIGURAÇÃO INICIAL E BANCO DE DADOS
# ==========================================
st.set_page_config(page_title="FinanceHub", page_icon="💸", layout="wide")

DB_PATH = 'financehub_v7.db'
engine = create_engine(f'sqlite:///{DB_PATH}')
Base = declarative_base()

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    category = Column(String, default="Outros")
    hash_id = Column(String, unique=True, nullable=False)

class CategoryRule(Base):
    __tablename__ = 'category_rules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)

# Nova Tabela: Metas de Gastos
class Budget(Base):
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, unique=True, nullable=False)
    limit_amount = Column(Float, nullable=False)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

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

menu = st.sidebar.radio("Navegação", ["Dashboard", "Metas & Custos Fixos", "Importar Fatura", "Configurações", "Assistente IA"])

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
            
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filtros")
            
            meses_disponiveis = sorted(df['month_year'].unique(), reverse=True)
            meses_selecionados = st.sidebar.multiselect("Selecione os Meses", meses_disponiveis, default=[meses_disponiveis[0]] if meses_disponiveis else [])
            
            categorias_disponiveis = sorted(df['category'].unique())
            categorias_selecionadas = st.sidebar.multiselect("Filtrar Categorias", categorias_disponiveis, default=categorias_disponiveis)
            
            df_filtrado = df[(df['month_year'].isin(meses_selecionados)) & (df['category'].isin(categorias_selecionadas))]
            
            if df_filtrado.empty:
                st.info("Nenhum dado encontrado para os filtros selecionados.")
            else:
                despesas = df_filtrado[df_filtrado['type'] == 'EXPENSE']
                entradas = df_filtrado[df_filtrado['type'] == 'INCOME']
                
                total_gasto = despesas['amount'].sum()
                total_entradas = entradas['amount'].sum()
                saldo = total_entradas - total_gasto
                maior_compra = despesas['amount'].max() if not despesas.empty else 0
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Gasto", f"R$ {total_gasto:,.2f}")
                col4.metric("Maior Compra", f"R$ {maior_compra:,.2f}")
                
                st.markdown("---")
                
                col_grafico1, col_grafico2 = st.columns(2)
                with col_grafico1:
                    gastos_mes = despesas.groupby('month_year')['amount'].sum().reset_index()
                    fig1 = px.bar(gastos_mes, x='month_year', y='amount', title="📉 Evolução de Despesas", text_auto='.2s', color_discrete_sequence=['#EF4444'])
                    fig1.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig1, use_container_width=True)
                    
                with col_grafico2:
                    gastos_cat = despesas.groupby('category')['amount'].sum().reset_index()
                    fig2 = px.pie(gastos_cat, values='amount', names='category', hole=0.5, title="🍩 Despesas por Categoria (Período)")
                    fig2.update_traces(textposition='inside', textinfo='percent')
                    st.plotly_chart(fig2, use_container_width=True)
                
                st.markdown("---")
                st.subheader("📋 Histórico Detalhado (Editável)")
                
                df_mostrar = df_filtrado[['id', 'date', 'description', 'category', 'amount', 'type']].copy()
                df_mostrar['date'] = df_mostrar['date'].dt.strftime('%d/%m/%Y')
                
                edited_df = st.data_editor(
                    df_mostrar, use_container_width=True, hide_index=True,
                    column_config={
                        "id": None, "date": st.column_config.TextColumn("Data", disabled=True),
                        "description": st.column_config.TextColumn("Descrição", disabled=True),
                        "amount": st.column_config.NumberColumn("Valor (R$)", disabled=True),
                        "type": st.column_config.TextColumn("Tipo", disabled=True),
                        "category": st.column_config.SelectboxColumn("Categoria", options=categorias_disponiveis + ["Nova Categoria..."])
                    }
                )
                
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("💾 Salvar Categorias", type="primary"):
                        db = SessionLocal()
                        alteracoes = 0
                        for index, row in edited_df.iterrows():
                            old_cat = df_mostrar.loc[index, 'category']
                            if old_cat != row['category']:
                                db.query(Transaction).filter_by(id=row['id']).update({"category": row['category']})
                                alteracoes += 1
                        db.commit()
                        db.close()
                        if alteracoes > 0:
                            st.success(f"{alteracoes} atualizadas!")
                            st.rerun()
                
                # NOVO: Botão de Exportação para Excel
                with col_btn2:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_mostrar.drop(columns=['id']).to_excel(writer, index=False, sheet_name='Transações')
                    
                    st.download_button(
                        label="📥 Baixar Relatório em Excel",
                        data=buffer.getvalue(),
                        file_name=f"FinanceHub_Relatorio_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

    except Exception as e:
        st.error(f"Erro ao carregar dados do Dashboard: {e}")

# ==========================================
# TELA 2: METAS & CUSTOS FIXOS (NOVO)
# ==========================================
elif menu == "Metas & Custos Fixos":
    st.header("🎯 Metas e Radar de Custos Fixos")
    db = SessionLocal()
    df = pd.read_sql("SELECT * FROM transactions WHERE type='EXPENSE'", engine)
    
    if df.empty:
        st.warning("Você precisa importar transações primeiro.")
    else:
        df['date'] = pd.to_datetime(df['date'])
        df['month_year'] = df['date'].dt.to_period('M').astype(str)
        mes_atual = df['month_year'].max()
        
        tab1, tab2 = st.tabs(["🚦 Metas de Gastos", "🔄 Radar de Assinaturas"])
        
        # --- TAB 1: METAS ---
        with tab1:
            st.subheader(f"Acompanhamento do Mês: {mes_atual}")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.write("**Definir Nova Meta**")
                categorias_existentes = sorted(df['category'].unique())
                cat_meta = st.selectbox("Categoria", categorias_existentes)
                val_meta = st.number_input("Limite Máximo (R$)", min_value=0.0, step=50.0)
                if st.button("Salvar Meta"):
                    meta_existente = db.query(Budget).filter_by(category=cat_meta).first()
                    if meta_existente:
                        meta_existente.limit_amount = val_meta
                    else:
                        db.add(Budget(category=cat_meta, limit_amount=val_meta))
                    db.commit()
                    st.success("Meta atualizada!")
                    st.rerun()
            
            with col2:
                metas_db = db.query(Budget).all()
                if not metas_db:
                    st.info("Nenhuma meta definida. Crie uma ao lado.")
                else:
                    df_mes_atual = df[df['month_year'] == mes_atual]
                    for meta in metas_db:
                        gasto_atual = df_mes_atual[df_mes_atual['category'] == meta.category]['amount'].sum()
                        limite = meta.limit_amount
                        percentual = min(gasto_atual / limite, 1.0) if limite > 0 else 1.0
                        
                        cor_barra = "normal"
                        if percentual >= 0.9:
                            cor_barra = "error" # Vermelho
                        elif percentual >= 0.7:
                            cor_barra = "warning" # Amarelo
                            
                        st.write(f"**{meta.category}**: R$ {gasto_atual:.2f} de R$ {limite:.2f}")
                        st.progress(percentual, text=f"{percentual*100:.1f}% utilizado")

        # --- TAB 2: CUSTOS FIXOS ---
        with tab2:
            st.subheader("Radar de Recorrências (Seu custo de vida)")
            st.write("Identificamos essas despesas se repetindo em vários meses.")
            
            # Lógica: Agrupa por descrição, conta meses distintos e tira média
            assinaturas = df.groupby('description').agg(
                meses_cobrados=('month_year', 'nunique'),
                valor_medio=('amount', 'mean'),
                ultima_compra=('date', 'max')
            ).reset_index()
            
            assinaturas = assinaturas[assinaturas['meses_cobrados'] >= 2]
            assinaturas = assinaturas.sort_values('valor_medio', ascending=False)
            
            if assinaturas.empty:
                st.info("Nenhum custo recorrente identificado ainda.")
            else:
                custo_fixo_total = assinaturas['valor_medio'].sum()
                st.metric("Estimativa de Custo Fixo Base", f"R$ {custo_fixo_total:,.2f} / mês")
                
                assinaturas['ultima_compra'] = assinaturas['ultima_compra'].dt.strftime('%d/%m/%Y')
                assinaturas.columns = ['Descrição', 'Meses Cobrados', 'Valor Médio (R$)', 'Última Cobrança']
                st.dataframe(assinaturas, use_container_width=True, hide_index=True)
                
    db.close()

# ==========================================
# TELA 3: IMPORTAÇÃO E IA (NOVO BOTÃO MAGICO)
# ==========================================
elif menu == "Importar Fatura":
    st.header("📥 Importar e Categorizar")
    arquivos = st.file_uploader("Arraste seus arquivos .csv do C6 Bank aqui", type=["csv"], accept_multiple_files=True)
    
    if arquivos:
        if st.button("Processar Faturas"):
            try:
                db = SessionLocal()
                regras = {r.keyword.lower(): r.category for r in db.query(CategoryRule).all()}
                
                importados_total = ignorados_total = passo_atual = 0
                progress_bar = st.progress(0)
                total_linhas_geral = sum([len(pd.read_csv(arq, sep=';', encoding='utf-8')) for arq in arquivos])
                for arq in arquivos: arq.seek(0)
                ocorrencias = {} 
                
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
                        
                        if pd.isna(amount_raw) or amount_raw == '': continue
                        if any(termo in desc.lower() for termo in ["inclusão de pagamento", "pagamento efetuado", "iof", "estorno", "pagamento de fatura"]): continue
                        
                        dt_obj = datetime.strptime(str(date_val), "%d/%m/%Y").date()
                        val_str = str(amount_raw).strip().replace('.', '').replace(',', '.') if ',' in str(amount_raw) and '.' in str(amount_raw) else str(amount_raw).strip().replace(',', '.')
                        amount = float(val_str)
                        
                        categoria_definida = "Outros"
                        if categoria_c6 and categoria_c6.lower() != 'nan':
                            categoria_definida = categoria_c6.title()
                        else:
                            for palavra_chave, categoria_nome in regras.items():
                                if palavra_chave in desc.lower():
                                    categoria_definida = categoria_nome
                                    break
                        
                        chave_base = f"{dt_obj.strftime('%Y-%m-%d')}_{desc}_{amount}"
                        ocorrencias[chave_base] = ocorrencias.get(chave_base, 0) + 1
                        tx_hash = hashlib.sha256(f"{chave_base}_{ocorrencias[chave_base]}".encode('utf-8')).hexdigest()
                        
                        if db.query(Transaction).filter_by(hash_id=tx_hash).first():
                            ignorados_total += 1
                            continue
                        
                        db.add(Transaction(date=dt_obj, description=desc, amount=abs(amount), type="EXPENSE" if amount > 0 else "INCOME", category=categoria_definida, hash_id=tx_hash))
                        importados_total += 1
                db.commit()
                db.close()
                st.success(f"✅ {importados_total} salvas. {ignorados_total} ignoradas (já existiam).")
            except Exception as e:
                st.error(f"❌ Erro: {e}")
                
    st.markdown("---")
    st.subheader("🪄 Categorização Mágica com IA")
    st.write("Deixe o Gemini classificar automaticamente todas as suas compras que caíram em 'Outros'.")
    
    api_key_import = st.text_input("API Key do Google Gemini:", type="password", key="api_magic")
    
    if st.button("🪄 Auto-Categorizar 'Outros'"):
        if not api_key_import:
            st.warning("Insira a chave da API acima.")
        else:
            db = SessionLocal()
            compras_outros = db.query(Transaction).filter_by(category="Outros", type="EXPENSE").all()
            
            if not compras_outros:
                st.info("Nenhuma compra classificada como 'Outros' encontrada! 🎉")
            else:
                genai.configure(api_key=api_key_import)
                try:
                    modelos_validos = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    modelo = next((m for m in modelos_validos if 'flash' in m), modelos_validos[0])
                    model = genai.GenerativeModel(modelo)
                    
                    cats_existentes = list(set([r[0] for r in db.query(Transaction.category).distinct().all() if r[0] != "Outros"]))
                    if not cats_existentes: cats_existentes = ["Alimentação", "Transporte", "Saúde", "Educação", "Lazer"]
                    
                    descricoes_unicas = list(set([c.description for c in compras_outros]))
                    
                    with st.spinner(f"A IA está analisando {len(descricoes_unicas)} estabelecimentos..."):
                        prompt = f"""
                        Atue como um classificador financeiro. Analise a lista de descrições de compras de cartão de crédito.
                        Classifique CADA UMA em uma destas categorias permitidas: {', '.join(cats_existentes)}.
                        Se nenhuma se encaixar, crie uma nova categoria curta (1 palavra).
                        Retorne EXATAMENTE neste formato de tabela:
                        Descrição | Categoria
                        
                        Lista:
                        {', '.join(descricoes_unicas)}
                        """
                        
                        resposta = model.generate_content(prompt)
                        linhas = resposta.text.strip().split('\n')
                        
                        mapeamento_ia = {}
                        for linha in linhas:
                            if '|' in linha and 'Descrição' not in linha and '---' not in linha:
                                partes = linha.split('|')
                                if len(partes) >= 2:
                                    desc_ia = partes[0].strip()
                                    cat_ia = partes[1].strip()
                                    mapeamento_ia[desc_ia] = cat_ia
                        
                        alteradas = 0
                        for compra in compras_outros:
                            # Tenta encontrar a descrição no dicionário retornado pela IA
                            # Como a IA pode mudar levemente a string (remover espaços), fazemos um fallback seguro
                            cat_nova = mapeamento_ia.get(compra.description)
                            if cat_nova:
                                compra.category = cat_nova
                                alteradas += 1
                        
                        db.commit()
                        st.success(f"🪄 Mágica concluída! {alteradas} compras reclassificadas pela IA.")
                        st.balloons()
                        
                except Exception as e:
                    st.error(f"Erro na comunicação com a IA: {e}")
            db.close()

# ==========================================
# TELA 4: CONFIGURAÇÕES
# ==========================================
elif menu == "Configurações":
    st.header("⚙️ Configurações de Categorização")
    db = SessionLocal()
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Adicionar Nova Regra")
        nova_palavra = st.text_input("Palavra-chave").lower().strip()
        nova_categoria = st.text_input("Categoria").title().strip()
        if st.button("Salvar Regra") and nova_palavra and nova_categoria:
            if db.query(CategoryRule).filter_by(keyword=nova_palavra).first():
                st.warning("Esta palavra-chave já existe.")
            else:
                db.add(CategoryRule(keyword=nova_palavra, category=nova_categoria))
                db.commit()
                st.success("Regra salva!")
                st.rerun()
                
    with col2:
        st.subheader("Regras Atuais")
        regras = pd.read_sql("SELECT id, keyword as 'Palavra Chave', category as 'Categoria' FROM category_rules", engine)
        if not regras.empty:
            st.dataframe(regras, hide_index=True, use_container_width=True)
            del_id = st.number_input("ID para excluir", min_value=0, step=1)
            if st.button("Excluir Regra") and del_id > 0:
                db.query(CategoryRule).filter_by(id=del_id).delete()
                db.commit()
                st.rerun()
    db.close()

# ==========================================
# TELA 5: ASSISTENTE IA
# ==========================================
elif menu == "Assistente IA":
    st.header("🤖 Assistente Financeiro IA (Google Gemini)")
    if not HAS_AI: st.error("Falta a biblioteca google-generativeai")
    else:
        api_key = st.text_input("Insira sua API Key do Google Gemini:", type="password")
        if api_key:
            genai.configure(api_key=api_key)
            try:
                modelos_validos = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                modelo_escolhido = st.selectbox("🧠 Selecione o modelo da IA:", modelos_validos)
                model = genai.GenerativeModel(modelo_escolhido)
                
                df = pd.read_sql("SELECT date, description, amount, type, category FROM transactions", engine)
                if df.empty: st.warning("Banco de dados vazio.")
                else:
                    resumo_por_categoria = df.groupby(['category', 'type'])['amount'].sum().to_dict()
                    compras_recentes = df.sort_values(by='date', ascending=False).head(20).to_string(index=False)
                    contexto_dados = textwrap.dedent(f"Totais: {resumo_por_categoria}\nÚltimas 20 transações:\n{compras_recentes}")
                    
                    pergunta = st.chat_input("Pergunte algo aos seus dados...")
                    if pergunta:
                        with st.chat_message("user"): st.write(pergunta)
                        with st.chat_message("assistant"):
                            with st.spinner("Analisando..."):
                                try:
                                    st.write(model.generate_content(f"{contexto_dados}\n\nPergunta: {pergunta}").text)
                                except Exception as e:
                                    st.error(f"Erro: {e}")
            except Exception as e:
                st.error(f"Erro ao conectar: {e}")
