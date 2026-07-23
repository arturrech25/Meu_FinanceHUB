import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, Column, Integer, String, Float, Date
from sqlalchemy.orm import declarative_base, sessionmaker
import hashlib
from datetime import datetime
import textwrap
import io
import requests

# Importações Avançadas (AgGrid e Lottie)
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from streamlit_lottie import st_lottie

try:
    import google.generativeai as genai
    HAS_AI = True
except ImportError:
    HAS_AI = False

# ==========================================
# CONFIGURAÇÃO INICIAL E CSS AVANÇADO
# ==========================================
st.set_page_config(page_title="FinanceHub Premium", page_icon="💳", layout="wide")

st.markdown("""
<style>
    /* Esconde cabeçalho padrão e rodape */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Customização da Barra de Rolagem (Estilo App Nativo) */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0E1117; }
    ::-webkit-scrollbar-thumb { background: #2A2D35; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #FF8A00; }
    
    /* Botões Glow (Primários) */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #FF8A00 0%, #E57A00 100%);
        color: white;
        border: none;
        box-shadow: 0 4px 15px rgba(255, 138, 0, 0.3);
        transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(255, 138, 0, 0.6);
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# Função para carregar animações Lottie da Web
@st.cache_data
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# Função para desenhar Cartões VIP HTML/CSS
def render_metric_card(title, value, subtitle=""):
    html = f"""
    <div style='background: linear-gradient(135deg, #1E2129 0%, #14171F 100%);
                border: 1px solid #2A2D35; border-radius: 15px; padding: 25px;
                box-shadow: 0 8px 20px rgba(0,0,0,0.4); border-left: 4px solid #FF8A00;
                font-family: sans-serif; transition: transform 0.3s ease, border-color 0.3s ease;'
                onmouseover='this.style.transform="translateY(-5px)"; this.style.borderColor="#FF8A00";'
                onmouseout='this.style.transform="translateY(0)"; this.style.borderColor="#2A2D35";'>
        <div style='color: #A0AEC0; font-size: 13px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase;'>{title}</div>
        <div style='color: #FFFFFF; font-size: 38px; font-weight: 800; margin: 10px 0; font-family: "Courier New", monospace;'>{value}</div>
        <div style='color: #48BB78; font-size: 13px; font-weight: 600;'>{subtitle}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==========================================
# BANCO DE DADOS
# ==========================================
DB_PATH = 'financehub_v8.db'
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

class Budget(Base):
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, unique=True, nullable=False)
    limit_amount = Column(Float, nullable=False)

class SubscriptionRule(Base):
    __tablename__ = 'subscription_rules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, unique=True, nullable=False)

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def seed_rules():
    db = SessionLocal()
    if db.query(CategoryRule).count() == 0:
        regras_iniciais = {
            'ifood': 'Alimentação', 'uber': 'Transporte', 'posto': 'Combustível',
            'netflix': 'Assinaturas', 'spotify': 'Assinaturas', 'mercado': 'Mercado'
        }
        for kw, cat in regras_iniciais.items():
            db.add(CategoryRule(keyword=kw, category=cat))
        db.commit()

    if db.query(SubscriptionRule).count() == 0:
        assinaturas_iniciais = [
            'netflix', 'spotify', 'amazon prime', 'prime video', 'globoplay', 'disney', 'star+', 'max', 'hbo',
            'apple tv', 'paramount', 'crunchyroll', 'youtube premium', 'youtube music', 'apple music', 'deezer', 'amazon music',
            'google one', 'icloud', 'microsoft', 'office 365', 'dropbox', 'adobe', 'canva', 'chatgpt', 'openai', 'notion', 'zoom',
            'smart fit', 'bluefit', 'gympass', 'wellhub', 'totalpass',
            'claro', 'vivo', 'tim', 'oi',
            'ifood', 'rappi', 'ze delivery',
            'xbox', 'playstation', 'nintendo',
            'sem parar', 'veloe', 'conectcar',
            'mercado livre', 'meli+', 'wine', 'tag livros', 'folha', 'estadao', 'o globo',
            'tinder', 'duolingo', 'babbel'
        ]
        for sub in assinaturas_iniciais:
            db.add(SubscriptionRule(keyword=sub))
        db.commit()
    db.close()
seed_rules()

# ==========================================
# NAVEGAÇÃO
# ==========================================
st.sidebar.markdown("<h1 style='text-align: center; color: #FF8A00; font-weight: 900; margin-bottom: 0;'>💳 Wallet</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; color: #888; font-size: 12px; margin-bottom: 30px;'>FinanceHub Premium</p>", unsafe_allow_html=True)

menu = st.sidebar.radio("Menu Principal", ["Dashboard", "Metas & Custos Fixos", "Importar Fatura", "Configurações", "Assistente IA"])

# ==========================================
# TELA 1: DASHBOARD
# ==========================================
if menu == "Dashboard":
    try:
        df = pd.read_sql("SELECT * FROM transactions", engine)
        if df.empty:
            st.warning("Seu banco de dados está vazio. Vá na aba 'Importar Fatura'.")
        else:
            df['date'] = pd.to_datetime(df['date'])
            df['month_year'] = df['date'].dt.to_period('M').astype(str)
            df['day'] = df['date'].dt.day
            
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filtros do Dashboard")
            meses_disponiveis = sorted(df['month_year'].unique(), reverse=True)
            meses_selecionados = st.sidebar.multiselect("📅 Meses", meses_disponiveis, default=[meses_disponiveis[0]] if meses_disponiveis else [])
            
            categorias_disponiveis = sorted(df['category'].unique())
            categorias_selecionadas = st.sidebar.multiselect("🏷️ Categorias", categorias_disponiveis, default=categorias_disponiveis)
            
            df_filtrado = df[(df['month_year'].isin(meses_selecionados)) & (df['category'].isin(categorias_selecionadas))]
            
            if df_filtrado.empty:
                st.info("Nenhum dado encontrado.")
            else:
                despesas = df_filtrado[df_filtrado['type'] == 'EXPENSE']
                total_gasto = despesas['amount'].sum()
                
                col_metric, _ = st.columns([1, 2]) 
                with col_metric:
                    render_metric_card("Balance Total (Gastos)", f"R$ {total_gasto:,.2f}", f"Analisando {len(meses_selecionados)} mês(es)")
                st.write("") 
                
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    with st.container(border=True):
                        gastos_mes = despesas.groupby('month_year')['amount'].sum().reset_index()
                        fig1 = px.bar(gastos_mes, x='month_year', y='amount', title="📉 Evolução Mensal", text_auto='.2s')
                        fig1.update_traces(marker_color='#FF8A00', textfont_size=12, textposition="outside", cliponaxis=False)
                        fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title=None, xaxis=dict(showgrid=False), yaxis=dict(showgrid=False, visible=False))
                        st.plotly_chart(fig1, use_container_width=True)
                    
                with col_g2:
                    with st.container(border=True):
                        gastos_cat = despesas.groupby('category')['amount'].sum().reset_index()
                        fig2 = px.pie(gastos_cat, values='amount', names='category', hole=0.7, title="🍩 Categorias")
                        fig2.update_traces(textposition='inside', textinfo='percent', marker=dict(line=dict(color='#0E1117', width=3)))
                        fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400, margin=dict(t=40, b=0, l=0, r=0), legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
                        st.plotly_chart(fig2, use_container_width=True)
                
                col_g3, col_g4 = st.columns(2)
                with col_g3:
                    with st.container(border=True):
                        df_dias = despesas.copy()
                        df_dias['dia_semana'] = df_dias['date'].dt.day_name().map({'Monday':'Seg', 'Tuesday':'Ter', 'Wednesday':'Qua', 'Thursday':'Qui', 'Friday':'Sex', 'Saturday':'Sáb', 'Sunday':'Dom'})
                        gastos_semana = df_dias.groupby('dia_semana')['amount'].sum().reindex(['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']).reset_index().fillna(0)
                        fig3 = px.bar(gastos_semana, x='dia_semana', y='amount', title="📅 Hábitos por Dia", text_auto='.2s')
                        fig3.update_traces(marker_color='#FF8A00', opacity=0.9, textposition="outside", cliponaxis=False)
                        fig3.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title=None, yaxis_title=None, xaxis=dict(showgrid=False), yaxis=dict(showgrid=False, visible=False))
                        st.plotly_chart(fig3, use_container_width=True)
                        
                with col_g4:
                    with st.container(border=True):
                        top5_cat = despesas.groupby('category')['amount'].sum().reset_index().nlargest(5, 'amount').sort_values(by='amount', ascending=True)
                        fig4 = px.bar(top5_cat, x='amount', y='category', orientation='h', title="🏆 Top 5 Ralos", text_auto='.2s')
                        fig4.update_traces(marker_color='#FF8A00', textposition="outside", cliponaxis=False)
                        fig4.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', yaxis_title=None, xaxis_title=None, xaxis=dict(showgrid=False, visible=False))
                        st.plotly_chart(fig4, use_container_width=True)
                
                with st.expander("🛠️ Modo Planilha: Editar Histórico e Exportar", expanded=False):
                    st.markdown("<p style='color: #FF8A00; font-size: 14px;'>Dê um duplo clique na coluna 'Categoria' para alterar os dados. Depois clique em Salvar.</p>", unsafe_allow_html=True)
                    df_mostrar = df_filtrado[['id', 'date', 'description', 'category', 'amount', 'type']].copy()
                    df_mostrar['date'] = df_mostrar['date'].dt.strftime('%d/%m/%Y')
                    
                    gb = GridOptionsBuilder.from_dataframe(df_mostrar)
                    gb.configure_column("id", hide=True)
                    gb.configure_column("type", hide=True)
                    gb.configure_default_column(resizable=True, sortable=True, filter=True)
                    gb.configure_column("category", editable=True, cellEditor='agSelectCellEditor', cellEditorParams={'values': categorias_disponiveis + ["Nova..."]})
                    gridOptions = gb.build()
                    
                    grid_response = AgGrid(
                        df_mostrar,
                        gridOptions=gridOptions,
                        update_mode=GridUpdateMode.MODEL_CHANGED,
                        fit_columns_on_grid_load=True,
                        theme="alpine"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 Salvar Edições do Ag-Grid", type="primary", use_container_width=True):
                            db = SessionLocal()
                            alteracoes = 0
                            df_editado = pd.DataFrame(grid_response['data'])
                            for index, row in df_editado.iterrows():
                                old_cat = df_mostrar.loc[index, 'category']
                                if old_cat != row['category']:
                                    db.query(Transaction).filter_by(id=row['id']).update({"category": row['category']})
                                    alteracoes += 1
                            db.commit()
                            db.close()
                            if alteracoes > 0:
                                st.success(f"{alteracoes} linhas atualizadas no banco!")
                                st.rerun()
                                
                    with col_btn2:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            df_mostrar.drop(columns=['id', 'type']).to_excel(writer, index=False, sheet_name='Transações')
                        st.download_button("📥 Exportar Relatório .XLSX", data=buffer.getvalue(), file_name=f"Relatorio_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    except Exception as e:
        st.error(f"Erro: {e}")

# ==========================================
# TELA 2: METAS & CUSTOS FIXOS
# ==========================================
elif menu == "Metas & Custos Fixos":
    st.header("🎯 Inteligência Financeira")
    db = SessionLocal()
    df = pd.read_sql("SELECT * FROM transactions WHERE type='EXPENSE'", engine)
    
    if df.empty: st.warning("Importe transações primeiro.")
    else:
        df['date'] = pd.to_datetime(df['date'])
        df['month_year'] = df['date'].dt.to_period('M').astype(str)
        mes_atual = df['month_year'].max()
        
        tab1, tab2 = st.tabs(["🚦 Monitor de Metas (Budgets)", "🔄 Radar de Assinaturas"])
        
        with tab1:
            st.write(f"### Controle em Tempo Real ({mes_atual})")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown("<div style='background: #14171F; padding: 20px; border-radius: 10px; border: 1px solid #2A2D35;'>", unsafe_allow_html=True)
                cat_meta = st.selectbox("Categoria", sorted(df['category'].unique()))
                val_meta = st.number_input("Teto Mensal (R$)", min_value=0.0, step=100.0)
                if st.button("Definir Budget", type="primary", use_container_width=True):
                    meta_existente = db.query(Budget).filter_by(category=cat_meta).first()
                    if meta_existente: meta_existente.limit_amount = val_meta
                    else: db.add(Budget(category=cat_meta, limit_amount=val_meta))
                    db.commit()
                    st.success("Teto estabelecido!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                metas_db = db.query(Budget).all()
                if not metas_db: st.info("Defina limites para habilitar os termômetros.")
                else:
                    df_mes_atual = df[df['month_year'] == mes_atual]
                    for meta in metas_db:
                        gasto = df_mes_atual[df_mes_atual['category'] == meta.category]['amount'].sum()
                        limite = meta.limit_amount
                        pct = min((gasto / limite) * 100, 100) if limite > 0 else 100
                        cor_barra = "#48BB78" if pct < 75 else ("#F6E05E" if pct < 90 else "#F56565")
                        
                        html_bar = f"""
                        <div style='margin-bottom: 15px;'>
                            <div style='display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 5px;'>
                                <span style='font-weight: bold; color: white;'>{meta.category}</span>
                                <span style='color: #A0AEC0;'>R$ {gasto:.2f} / R$ {limite:.2f}</span>
                            </div>
                            <div style="width: 100%; background-color: #2A2D35; border-radius: 10px; overflow: hidden; height: 12px;">
                                <div style="width: {pct}%; background-color: {cor_barra}; height: 100%; border-radius: 10px; transition: width 0.8s ease;"></div>
                            </div>
                        </div>
                        """
                        st.markdown(html_bar, unsafe_allow_html=True)

        with tab2:
            st.subheader("Radar de Assinaturas e Serviços")
            
            regras_sub = db.query(SubscriptionRule).all()
            assinaturas_comuns = [r.keyword.lower() for r in regras_sub]
            
            if not assinaturas_comuns:
                st.warning("Sua lista de assinaturas conhecidas está vazia. Adicione termos abaixo.")
            else:
                # O \b impede falsos positivos como encontrar 'oi' em 'goimage'
                padrao = r'\b(' + '|'.join(assinaturas_comuns) + r')\b'
                df_assinaturas = df[df['description'].str.lower().str.contains(padrao, na=False, regex=True)]
                
                assinaturas = df_assinaturas.groupby('description').agg(
                    meses_cobrados=('month_year', 'nunique'), 
                    valor_medio=('amount', 'mean')
                ).reset_index()
                
                assinaturas = assinaturas[assinaturas['meses_cobrados'] >= 2].sort_values('valor_medio', ascending=False)
                
                if assinaturas.empty: 
                    st.info("Nenhuma assinatura cadastrada foi identificada com recorrência na sua fatura.")
                else:
                    render_metric_card("Seu Custo Fixo de Assinaturas", f"R$ {assinaturas['valor_medio'].sum():,.2f}")
                    st.write("")
                    assinaturas.columns = ['Serviço / Assinatura', 'Meses Cobrados', 'Média de Valor (R$)']
                    AgGrid(assinaturas, fit_columns_on_grid_load=True, theme="alpine")

            st.markdown("---")
            # --- GERENCIADOR DA LISTA DE ASSINATURAS ---
            with st.expander("⚙️ Gerenciar Lista de Assinaturas Conhecidas (Adicionar/Remover)"):
                col_add, col_del = st.columns(2)
                
                with col_add:
                    st.write("**Adicionar Nova Assinatura**")
                    nova_sub = st.text_input("Nome/Termo do serviço (ex: strava, nintendo):", key="input_add_sub").lower().strip()
                    if st.button("Adicionar à Lista", type="primary", key="btn_add_sub") and nova_sub:
                        if db.query(SubscriptionRule).filter_by(keyword=nova_sub).first():
                            st.warning("Esta assinatura já está na lista.")
                        else:
                            db.add(SubscriptionRule(keyword=nova_sub))
                            db.commit()
                            st.success(f"'{nova_sub}' adicionado!")
                            st.rerun()
                            
                with col_del:
                    st.write("**Remover Assinatura da Lista**")
                    df_regras_sub = pd.read_sql("SELECT id, keyword as 'Assinatura' FROM subscription_rules ORDER BY keyword", engine)
                    st.dataframe(df_regras_sub, use_container_width=True, hide_index=True, height=150)
                    
                    # ADICIONADA A KEY 'num_del_sub' AQUI PARA MATAR O ERRO DE ID DUPLICADO
                    sub_id_del = st.number_input("ID do item para excluir da lista:", min_value=0, step=1, key="num_del_sub")
                    if st.button("Excluir Assinatura", key="btn_del_sub") and sub_id_del > 0:
                        db.query(SubscriptionRule).filter_by(id=sub_id_del).delete()
                        db.commit()
                        st.success("Item removido da lista!")
                        st.rerun()
    db.close()

# ==========================================
# TELA 3: IMPORTAÇÃO E MAGIA
# ==========================================
elif menu == "Importar Fatura":
    st.header("📥 Processamento e Triagem")
    arquivos = st.file_uploader("Drop seus arquivos .csv aqui (C6 Bank)", type=["csv"], accept_multiple_files=True)
    
    if arquivos:
        if st.button("🚀 Processar Dumps", type="primary"):
            try:
                db = SessionLocal()
                regras = {r.keyword.lower(): r.category for r in db.query(CategoryRule).all()}
                importados = ignorados = passo = 0
                total_linhas = sum([len(pd.read_csv(a, sep=';', encoding='utf-8')) for a in arquivos])
                for a in arquivos: a.seek(0)
                ocorrencias = {} 
                bar = st.progress(0)
                
                for arquivo in arquivos:
                    df_up = pd.read_csv(arquivo, sep=';', encoding='utf-8')
                    df_up.columns = [c.strip().lower() for c in df_up.columns]
                    
                    for index, row in df_up.iterrows():
                        passo += 1
                        bar.progress(min(passo / total_linhas, 1.0))
                        
                        dt, desc, amt, cat_c6 = row.get('data de compra'), str(row.get('descrição', '')).strip(), row.get('valor (em r$)'), str(row.get('categoria', '')).strip()
                        if pd.isna(amt) or amt == '' or any(t in desc.lower() for t in ["inclusão de pagamento", "iof", "estorno", "pagamento de fatura"]): continue
                        
                        dt_obj = datetime.strptime(str(dt), "%d/%m/%Y").date()
                        val_str = str(amt).replace('.', '').replace(',', '.') if ',' in str(amt) and '.' in str(amt) else str(amt).replace(',', '.')
                        val = float(val_str)
                        
                        cat_def = cat_c6.title() if cat_c6 and cat_c6.lower() != 'nan' else "Outros"
                        if cat_def == "Outros":
                            for k, v in regras.items():
                                if k in desc.lower(): cat_def = v; break
                        
                        hash_base = f"{dt_obj.strftime('%Y-%m-%d')}_{desc}_{val}"
                        ocorrencias[hash_base] = ocorrencias.get(hash_base, 0) + 1
                        tx_hash = hashlib.sha256(f"{hash_base}_{ocorrencias[hash_base]}".encode('utf-8')).hexdigest()
                        
                        if db.query(Transaction).filter_by(hash_id=tx_hash).first(): ignorados += 1; continue
                        db.add(Transaction(date=dt_obj, description=desc, amount=abs(val), type="EXPENSE" if val > 0 else "INCOME", category=cat_def, hash_id=tx_hash))
                        importados += 1
                db.commit()
                db.close()
                st.success(f"✅ Sucesso! Inseridas: {importados} | Duplicadas ignoradas: {ignorados}")
            except Exception as e: st.error(f"Erro: {e}")

    st.markdown("---")
    col1, col2 = st.columns([1,2])
    with col1:
        lottie_magic = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_p8qulw7z.json")
        if lottie_magic: st_lottie(lottie_magic, height=200, key="magic")
        
    with col2:
        st.subheader("🪄 Auto-Triagem (Gemini AI)")
        st.write("A IA classificará compras marcadas como 'Outros' usando suas próprias categorias.")
        api_key_import = st.text_input("Sua Key do AI Studio:", type="password", key="api_magic")
        
        if st.button("Executar Triagem IA", type="primary", use_container_width=True):
            if not api_key_import: st.warning("Chave ausente.")
            else:
                db = SessionLocal()
                compras_outros = db.query(Transaction).filter_by(category="Outros", type="EXPENSE").all()
                if not compras_outros: st.info("Você não tem compras classificadas como 'Outros'!")
                else:
                    genai.configure(api_key=api_key_import)
                    try:
                        m_validos = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        model = genai.GenerativeModel(next((m for m in m_validos if 'flash' in m), m_validos[0]))
                        
                        cats_existentes = list(set([r[0] for r in db.query(Transaction.category).distinct().all() if r[0] != "Outros"]))
                        descricoes = list(set([c.description for c in compras_outros]))
                        
                        with st.spinner("Conectando aos neurônios do Google..."):
                            prompt = f"Categorize estas compras: {', '.join(descricoes)}. Categorias permitidas: {', '.join(cats_existentes)}. Retorne tabela: Descrição | Categoria"
                            linhas = model.generate_content(prompt).text.strip().split('\n')
                            mapeamento_ia = {p[0].strip(): p[1].strip() for l in linhas if '|' in l and len(p := l.split('|')) >= 2 and '---' not in l}
                            
                            alt = sum([1 for c in compras_outros if (nova := mapeamento_ia.get(c.description)) and (setattr(c, 'category', nova) or True)])
                            db.commit()
                            st.success(f"Triagem concluída. {alt} itens realocados!")
                    except Exception as e: st.error(f"Falha na IA: {e}")
                db.close()

# ==========================================
# TELA 4: CONFIGURAÇÕES
# ==========================================
elif menu == "Configurações":
    st.header("⚙️ Motor de Regras")
    db = SessionLocal()
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("Crie regras automáticas para cruzamento de dados na importação.")
        nova_palavra = st.text_input("Termo contido na fatura", key="input_nova_regra").lower().strip()
        nova_categoria = st.text_input("Categoria Destino", key="input_nova_cat").title().strip()
        if st.button("Injetar Regra", type="primary", key="btn_add_regra") and nova_palavra and nova_categoria:
            if db.query(CategoryRule).filter_by(keyword=nova_palavra).first(): st.warning("Regra em conflito.")
            else:
                db.add(CategoryRule(keyword=nova_palavra, category=nova_categoria))
                db.commit()
                st.success("Regra ativada.")
                st.rerun()
    with col2:
        regras = pd.read_sql("SELECT id, keyword as 'Palavra Chave', category as 'Categoria' FROM category_rules", engine)
        if not regras.empty:
            AgGrid(regras, fit_columns_on_grid_load=True, theme="alpine")
            # ADICIONADA A KEY 'num_del_regra' AQUI
            if st.button("Purgar Regra via ID", key="btn_del_regra") and (del_id := st.number_input("ID para excluir da lista:", min_value=0, step=1, key="num_del_regra")) > 0:
                db.query(CategoryRule).filter_by(id=del_id).delete()
                db.commit()
                st.rerun()
    db.close()

# ==========================================
# TELA 5: ASSISTENTE IA
# ==========================================
elif menu == "Assistente IA":
    st.header("🧠 Oráculo Financeiro")
    if not HAS_AI: st.error("Módulo google-generativeai inoperante.")
    else:
        col1, col2 = st.columns([2, 1])
        with col2:
            lottie_robot = load_lottieurl("https://assets2.lottiefiles.com/packages/lf20_0xbu0vpt.json")
            if lottie_robot: st_lottie(lottie_robot, height=250, key="robot")
            
        with col1:
            api_key = st.text_input("Autenticação Google AI:", type="password", key="api_chat")
            if api_key:
                genai.configure(api_key=api_key)
                try:
                    m_validos = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    modelo = st.selectbox("Processador lógico:", m_validos, key="select_model")
                    model = genai.GenerativeModel(modelo)
                    
                    df = pd.read_sql("SELECT * FROM transactions", engine)
                    if df.empty: st.warning("Sem contexto de dados para leitura.")
                    else:
                        contexto = f"Gastos: {df.groupby(['category', 'type'])['amount'].sum().to_dict()}\nÚltimas: {df.sort_values(by='date', ascending=False).head(20).to_string(index=False)}"
                        if pergunta := st.chat_input("Pergunte sobre seus dados financeiros..."):
                            st.chat_message("user").write(pergunta)
                            with st.chat_message("assistant"):
                                with st.spinner("Computando resposta baseada no histórico..."):
                                    try: st.write(model.generate_content(f"Contexto: {contexto}\n\nPergunta: {pergunta}").text)
                                    except Exception as e: st.error(f"Falha estrutural: {e}")
                except Exception as e: st.error(f"Erro de conexão central: {e}")
