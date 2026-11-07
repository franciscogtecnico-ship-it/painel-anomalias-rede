import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import base64
import os
import unicodedata

# 1. Configuração da página
st.set_page_config(page_title="Painel BI - Manutenção de Rede", layout="wide")

# Função para ler a imagem de fundo e converter para CSS
@st.cache_data
def carregar_imagem_fundo(caminho_imagem):
    if os.path.exists(caminho_imagem):
        with open(caminho_imagem, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            return f"background-image: url('data:image/jpeg;base64,{b64}'); background-size: cover; background-position: center;"
    return "background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);"

estilo_fundo_rede = carregar_imagem_fundo("image_a8440a.jpg")

# Estilização CSS (Banner compacto)
st.markdown(f"""
<style>
div.stButton > button {{
    border-radius: 8px;
    font-weight: bold;
    border: 1px solid #1e3a8a;
    background-color: #f8fafc;
    color: #1e3a8a;
    transition: all 0.3s ease;
    width: 100%;
}}
div.stButton > button:hover {{
    background-color: #cbd5e1;
    color: #1e3a8a;
    border-color: #1e3a8a;
}}

.rede-eletrica-container {{
    {estilo_fundo_rede}
    border-radius: 8px;
    padding: 0px;
    margin-bottom: 10px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    position: relative;
    overflow: hidden;
    height: 85px;
}}
.rede-overlay {{
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background-color: rgba(15, 23, 42, 0.45); 
    z-index: 1;
}}
.rede-svg {{
    position: relative;
    z-index: 2;
    display: block;
}}
</style>
""", unsafe_allow_html=True)

# Função auxiliar para remover acentos e padronizar textos de forma segura
def remover_acentos(texto):
    if pd.isna(texto):
        return ""
    texto_str = str(texto)
    if texto_str.lower() == 'nan':
        return ""
    nfkd_form = unicodedata.normalize('NFKD', texto_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).upper()

# 2. Carregar e Cruzar Banco de Dados
@st.cache_data
def carregar_dados():
    df_principal = pd.read_excel('Anomalias.xlsm', sheet_name='Anomalias')
    df_plano = pd.read_excel('Anomalias.xlsm', sheet_name='PLANO')
    
    try:
        df_ose = pd.read_excel('Anomalias.xlsm', sheet_name='OSE')
    except Exception:
        df_ose = pd.DataFrame(columns=['OSE', 'EMPRESA'])

    df_principal.columns = df_principal.columns.str.strip()
    df_plano.columns = df_plano.columns.str.strip()
    df_ose.columns = df_ose.columns.str.strip()

    # Tratamento das chaves de ligação
    df_principal['Número da OS'] = df_principal['Número da OS'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_principal['Número da OSE'] = df_principal['Número da OSE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_plano['OS'] = df_plano['OS'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_ose['OSE'] = df_ose['OSE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    df_principal['Latitude'] = pd.to_numeric(df_principal['Latitude'], errors='coerce')
    df_principal['Longitude'] = pd.to_numeric(df_principal['Longitude'], errors='coerce')

    # Cruzamento 1: PLANO (usando Número da OS)
    df_completo = pd.merge(df_principal, df_plano, left_on='Número da OS', right_on='OS', how='left')
    df_completo['EQUIPAMENTO'] = df_completo['EQUIPAMENTO'].fillna('Sem Equipamento Vinculado')

    # Cruzamento 2: EMPRESAS (Aba OSE ligada à Coluna 'Número da OSE' da aba Anomalias)
    if 'OSE' in df_ose.columns and 'EMPRESA' in df_ose.columns:
        df_completo = pd.merge(df_completo, df_ose[['OSE', 'EMPRESA']], left_on='Número da OSE', right_on='OSE', how='left')
    else:
        df_completo['EMPRESA'] = 'OUTRAS'

    def tratar_empresa(nome):
        if pd.isna(nome) or str(nome).strip() == '' or str(nome).lower() == 'nan': 
            return 'OUTRAS'
        return str(nome).upper().strip()

    df_completo['EMPRESA'] = df_completo['EMPRESA'].apply(tratar_empresa)
    df_completo['Status'] = df_completo['Status'].fillna('Sem Status')
    
    # Propagação Total da Empresa por Equipamento
    df_com_empresa = df_completo[df_completo['EMPRESA'] != 'OUTRAS']
    mapa_equip_empresa = df_com_empresa.drop_duplicates(subset=['EQUIPAMENTO']).set_index('EQUIPAMENTO')['EMPRESA'].to_dict()
    
    def preencher_por_equipamento(row):
        if row['EMPRESA'] == 'OUTRAS' and row['EQUIPAMENTO'] in mapa_equip_empresa:
            return mapa_equip_empresa[row['EQUIPAMENTO']]
        return row['EMPRESA']
        
    df_completo['EMPRESA'] = df_completo.apply(preencher_por_equipamento, axis=1)

    # Classificação de Anomalias Blindada e Abrangente
    def classificar_anomalia(texto):
        texto_limpo = remover_acentos(texto)
        if any(termo in texto_limpo for termo in ['ARVORE', 'ARV', 'PODA', 'VEGETACAO']):
            return 'ARVORE'
        elif any(termo in texto_limpo for termo in ['FAIXA', 'BAMBU', 'VEGETAL']):
            return 'FAIXA'
        else:
            return 'DEGRADACAO'

    df_completo['Tipo_Anomalia'] = df_completo['Anomalia'].apply(classificar_anomalia)
    return df_completo

df = carregar_dados()

cores_status = {}
for status in df['Status'].unique():
    if 'EXECUTAD' in str(status).upper(): 
        cores_status[status] = '#198754'
    else: 
        cores_status[status] = '#dc3545'

df['Cor_Mapa'] = df['Status'].map(cores_status)

# 3. Logótipo e Filtros Laterais
try:
    st.sidebar.image('image_3576ef.png', use_container_width=True)
except FileNotFoundError:
    st.sidebar.title("EQUATORIAL ENERGIA")

st.sidebar.header("Filtros Avançados")

lista_empresa = sorted([str(x) for x in df['EMPRESA'].dropna().unique()])
lista_subestacao = sorted([str(x) for x in df['Subestação'].dropna().unique()])
lista_alimentador = sorted([str(x) for x in df['Alimentador'].dropna().unique()])
lista_os = sorted([str(x) for x in df['Número da OS'].dropna().unique()])
lista_equipamento = sorted([str(x) for x in df['EQUIPAMENTO'].dropna().unique()])
lista_status = sorted([str(x) for x in df['Status'].dropna().unique()])
lista_tipo_anomalia = sorted([str(x) for x in df['Tipo_Anomalia'].dropna().unique()])

empresa_selecionada = st.sidebar.multiselect("1. Empresa Prestadora:", options=lista_empresa)
sub_selecionada = st.sidebar.multiselect("2. Subestação:", options=lista_subestacao)
alim_selecionado = st.sidebar.multiselect("3. Alimentador:", options=lista_alimentador)
os_selecionada = st.sidebar.multiselect("4. Número da OS:", options=lista_os)
equip_selecionado = st.sidebar.multiselect("5. Equipamento:", options=lista_equipamento)
status_selecionado = st.sidebar.multiselect("6. Status da Anomalia:", options=lista_status)
tipo_selecionado = st.sidebar.multiselect("7. Tipo de Anomalia:", options=lista_tipo_anomalia)

# 4. TÍTULO DO PAINEL E BOTÕES DE EMPRESA (Topo com destaque dinâmico)
st.title("📊 Painel de Indicadores (BI) - Manutenção da Rede")

empresas_disponiveis = sorted([str(e) for e in df['EMPRESA'].unique() if e != 'OUTRAS'])
if 'OUTRAS' in df['EMPRESA'].unique():
    empresas_disponiveis.append('OUTRAS')

if 'empresa_filtro_topo' not in st.session_state:
    st.session_state['empresa_filtro_topo'] = 'TODAS'

st.markdown("### 🏢 Seleção Rápida por Empresa Parceira:")
col_btns = st.columns(len(empresas_disponiveis) + 1)

def estilo_botao_ativo(ativo):
    if ativo:
        return """
        <style>
        div.stButton > button {
            background-color: #1e3a8a !important;
            color: white !important;
            border-color: #1e3a8a !important;
            box-shadow: 0 0 10px rgba(30, 58, 138, 0.5);
        }
        </style>
        """
    return ""

with col_btns[0]:
    is_active = (st.session_state['empresa_filtro_topo'] == 'TODAS')
    if is_active:
        st.markdown(estilo_botao_ativo(True), unsafe_allow_html=True)
    if st.button("🌐 TODAS", use_container_width=True):
        st.session_state['empresa_filtro_topo'] = 'TODAS'
        st.rerun()

for idx, emp in enumerate(empresas_disponiveis):
    with col_btns[idx + 1]:
        is_active = (st.session_state['empresa_filtro_topo'] == emp)
        if is_active:
            st.markdown(estilo_botao_ativo(True), unsafe_allow_html=True)
        if st.button(f"📌 {emp}", use_container_width=True):
            st.session_state['empresa_filtro_topo'] = emp
            st.rerun()

# 6. Aplicação Cumulativa dos Filtros (Calculada antes para afetar o gráfico superior)
df_filtrado = df.copy()

if st.session_state['empresa_filtro_topo'] != 'TODAS':
    df_filtrado = df_filtrado[df_filtrado['EMPRESA'] == st.session_state['empresa_filtro_topo']]

if empresa_selecionada:
    df_filtrado = df_filtrado[df_filtrado['EMPRESA'].isin(empresa_selecionada)]
if sub_selecionada:
    df_filtrado = df_filtrado[df_filtrado['Subestação'].isin(sub_selecionada)]
if alim_selecionado:
    df_filtrado = df_filtrado[df_filtrado['Alimentador'].isin(alim_selecionado)]
if os_selecionada:
    df_filtrado = df_filtrado[df_filtrado['Número da OS'].isin(os_selecionada)]
if equip_selecionado:
    df_filtrado = df_filtrado[df_filtrado['EQUIPAMENTO'].isin(equip_selecionado)]
if status_selecionado:
    df_filtrado = df_filtrado[df_filtrado['Status'].isin(status_selecionado)]
if tipo_selecionado:
    df_filtrado = df_filtrado[df_filtrado['Tipo_Anomalia'].isin(tipo_selecionado)]

# 5. BANNER DA REDE E GRÁFICO DE ANOMALIAS POR EMPRESA (Agora utiliza df_filtrado)
col_header_esq, col_header_dir = st.columns([2.1, 1])

with col_header_esq:
    st.markdown("""<div class="rede-eletrica-container">
<div class="rede-overlay"></div>
<svg class="rede-svg" viewBox="0 0 800 100" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:80px;">
<line x1="0" y1="15" x2="800" y2="15" stroke="#ef4444" stroke-width="2.5" />
<line x1="0" y1="25" x2="800" y2="25" stroke="#3b82f6" stroke-width="2.5" />
<line x1="0" y1="35" x2="800" y2="35" stroke="#eab308" stroke-width="2.5" />
<line x1="180" y1="10" x2="180" y2="95" stroke="#cbd5e1" stroke-width="6" />
<line x1="150" y1="22" x2="210" y2="22" stroke="#94a3b8" stroke-width="4" />
<path d="M 180 50 Q 205 45 215 55" fill="none" stroke="#f8fafc" stroke-width="2.5" />
<path d="M 210 55 L 220 55 L 217 60 L 213 60 Z" fill="#fef08a" stroke="#eab308" />
<circle cx="216" cy="63" r="3" fill="#fef08a" />
<line x1="400" y1="10" x2="400" y2="95" stroke="#cbd5e1" stroke-width="6" />
<line x1="370" y1="22" x2="430" y2="22" stroke="#94a3b8" stroke-width="4" />
<path d="M 400 50 Q 425 45 435 55" fill="none" stroke="#f8fafc" stroke-width="2.5" />
<path d="M 430 55 L 440 55 L 437 60 L 433 60 Z" fill="#fef08a" stroke="#eab308" />
<circle cx="436" cy="63" r="3" fill="#fef08a" />
<line x1="620" y1="10" x2="620" y2="95" stroke="#cbd5e1" stroke-width="6" />
<line x1="590" y1="22" x2="650" y2="22" stroke="#94a3b8" stroke-width="4" />
<rect x="628" y="35" width="15" height="20" rx="1.5" fill="#64748b" stroke="#f8fafc" stroke-width="1.2" />
<path d="M 620 62 Q 645 57 655 67" fill="none" stroke="#f8fafc" stroke-width="2.5" />
<path d="M 650 67 L 660 67 L 657 72 L 653 72 Z" fill="#fef08a" stroke="#eab308" />
<circle cx="656" cy="75" r="3" fill="#fef08a" />
</svg>
</div>""", unsafe_allow_html=True)

with col_header_dir:
    # Utiliza df_filtrado para que o gráfico reaja aos filtros aplicados
    df_resumo_empresas = df_filtrado['EMPRESA'].value_counts().reset_index()
    df_resumo_empresas.columns = ['Parceira', 'Total']
    
    fig_empresas = px.bar(
        df_resumo_empresas, 
        x='Total', 
        y='Parceira', 
        orientation='h',
        text='Total',
        title="<b>Anomalias por Empresa Parceira</b>"
    )
    fig_empresas.update_traces(marker_color='#1e3a8a', textposition='outside')
    fig_empresas.update_layout(
        xaxis_visible=False, 
        xaxis_showticklabels=False,
        yaxis={'categoryorder': 'total ascending'},
        margin=dict(l=0, r=10, t=25, b=0),
        height=85,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(size=11)
    )
    st.plotly_chart(fig_empresas, use_container_width=True)

st.markdown("---")

# 7. Indicadores Numéricos
total_registos = len(df_filtrado)
contagem_subestacao = df_filtrado['Subestação'].value_counts().reset_index()
contagem_subestacao.columns = ['Subestação', 'Quantidade de Anomalias']
contagem_anomalias = df_filtrado['Anomalia'].value_counts().reset_index()
contagem_anomalias.columns = ['Descrição da Anomalia', 'Quantidade']

c1, c2, c3 = st.columns(3)
with c1:
    st.metric(label="Total de Anomalias (Filtro Atual)", value=total_registos)
with c2:
    st.metric(label="Tipos de Anomalias Diferentes", value=len(contagem_anomalias))
with c3:
    equipamentos_afetados = df_filtrado[df_filtrado['EQUIPAMENTO'] != 'Sem Equipamento Vinculado']['EQUIPAMENTO'].nunique()
    st.metric(label="Equipamentos Afetados", value=equipamentos_afetados)

st.markdown("---")

# 8. Gráficos Principais
col_equip, col_mapa = st.columns(2)

with col_equip:
    st.subheader("Top 20 Equipamentos (por Status)")
    if not df_filtrado.empty:
        df_equip = df_filtrado[df_filtrado['EQUIPAMENTO'] != 'Sem Equipamento Vinculado']
        if not df_equip.empty:
            top_20_equips = df_equip['EQUIPAMENTO'].value_counts().head(20).index
            df_equip_top20 = df_equip[df_equip['EQUIPAMENTO'].isin(top_20_equips)]
            contagem_equip_status = df_equip_top20.groupby(['EQUIPAMENTO', 'Status']).size().reset_index(name='Quantidade')
            
            fig_equip = px.bar(contagem_equip_status, x='Quantidade', y='EQUIPAMENTO', color='Status', orientation='h', color_discrete_map=cores_status)
            fig_equip.update_layout(yaxis={'categoryorder': 'total ascending'}, barmode='stack')
            st.plotly_chart(fig_equip, use_container_width=True)
        else:
            st.info("Sem equipamentos vinculados para esta seleção.")
    else:
        st.info("Nenhuma anomalia encontrada.")

with col_mapa:
    st.subheader("Geolocalização (Traçado da Rede)")
    df_mapa = df_filtrado.dropna(subset=['Latitude', 'Longitude'])
    df_mapa = df_mapa[(df_mapa['Latitude'] != 0) & (df_mapa['Longitude'] != 0)]
    
    if not df_mapa.empty:
        fig_map = go.Figure()
        
        usa_novo_mapa = hasattr(go, 'Scattermap')
        TraceMapa = go.Scattermap if usa_novo_mapa else go.Scattermapbox
        chave_layout = "map" if usa_novo_mapa else "mapbox"
        
        if alim_selecionado or os_selecionada or equip_selecionado or sub_selecionada:
            fig_map.add_trace(TraceMapa(
                lat=df_mapa['Latitude'],
                lon=df_mapa['Longitude'],
                mode='lines',
                line=dict(width=2, color='rgba(100, 116, 139, 0.7)'),
                hoverinfo='none',
                showlegend=False
            ))
        
        for status, color in cores_status.items():
            df_status = df_mapa[df_mapa['Status'] == status]
            if not df_status.empty:
                fig_map.add_trace(TraceMapa(
                    lat=df_status['Latitude'],
                    lon=df_status['Longitude'],
                    mode='markers',
                    marker=dict(size=9, color=color),
                    name=status,
                    text=df_status['EQUIPAMENTO'].astype(str) + ' - ' + df_status['Anomalia'].astype(str),
                    hoverinfo='text'
                ))
        
        layout_args = {
            chave_layout: dict(
                style="carto-positron",
                center=dict(lat=df_mapa['Latitude'].mean(), lon=df_mapa['Longitude'].mean()),
                zoom=12.5 if (alim_selecionado or os_selecionada) else 6
            ),
            "margin": {"r": 0, "t": 0, "l": 0, "b": 0},
            "height": 450,
            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        }
        fig_map.update_layout(**layout_args)
        
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Nenhuma coordenada válida encontrada para traçar a rede.")

st.markdown("---")

# 9. Tabelas
col_sub, col_top = st.columns(2)

with col_sub:
    st.subheader("Anomalias por Subestação")
    if not contagem_subestacao.empty:
        fig_barras = px.bar(contagem_subestacao, x='Quantidade de Anomalias', y='Subestação', orientation='h', color='Subestação')
        fig_barras.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig_barras, use_container_width=True)
    else:
        st.info("Nenhuma subestação encontrada.")

with col_top:
    st.subheader("Tabela Resumo - Top 15 Anomalias")
    st.dataframe(contagem_anomalias.head(15), use_container_width=True)

st.markdown("---")

# 10. Exportação
st.subheader("Exportar e Visualizar Dados")

@st.cache_data
def converter_para_excel(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, index=False, sheet_name='Anomalias Filtradas')
    return output.getvalue()

df_export = df_filtrado.drop(columns=['Cor_Mapa'], errors='ignore')
st.download_button(
    label="📥 Baixar Tabela Filtrada (Excel)", 
    data=converter_para_excel(df_export), 
    file_name='Relatorio_Anomalias_Filtrado.xlsx', 
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)
st.dataframe(df_export)