import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

st.set_page_config(page_title="Painel CCO - Rio Ouro", page_icon="🚌", layout="wide")
st.title("🚌 Centro de Inteligência Operacional - Viação Rio Ouro")
st.markdown("---")

# ==========================================
# 1. CONEXÃO COM O COFRE LOCAL (Banco de Dados)
# ==========================================
@st.cache_data
def carregar_banco():
    try:
        # Liga direto no arquivo .db que você acabou de criar
        conexao = sqlite3.connect('banco_cco_qualificacao.db')
        df = pd.read_sql_query("SELECT * FROM fato_viagens", conexao)
        conexao.close()
        return df
    except Exception as e:
        return pd.DataFrame()

df_viagens = carregar_banco()

if df_viagens.empty:
    st.error("⚠️ Banco de dados não encontrado ou vazio. Rode o alimentar_banco.py primeiro.")
else:
    # 2. MENU EXECUTIVO DE NAVEGAÇÃO
    aba1, aba2, aba3, aba4 = st.tabs(["📊 Visão Diária", "📈 Histórico Executivo", "🏆 Pódio de Ouro", "🚦 Análise de Trânsito"])

    # ==========================================
    # ABA 1: VISÃO DIÁRIA (O Seletor de Datas)
    # ==========================================
    with aba1:
        # Puxa os dias disponíveis no banco para o gerente escolher
        datas_disponiveis = sorted(df_viagens['data_operacao'].unique(), reverse=True)
        dia_selecionado = st.selectbox("📅 Selecione a Data da Operação:", datas_disponiveis)
        
        # Filtra a tabela só para o dia escolhido
        df_dia = df_viagens[df_viagens['data_operacao'] == dia_selecionado].copy()
        
        # KPIs Diários
        col1, col2, col3, col4 = st.columns(4)
        total_prog = len(df_dia)
        total_real = df_dia['status_realizada'].sum()
        taxa = (total_real / total_prog) * 100 if total_prog > 0 else 0
        
        col1.metric("Viagens Programadas", total_prog)
        col2.metric("Viagens Realizadas", total_real)
        col3.metric("Cumprimento de Escala", f"{taxa:.1f}%")
        col4.metric("Buracos (Perdas)", total_prog - total_real)
        
        st.markdown("---")
        
        # Gráfico de Cumprimento por Linha
        st.subheader("Cumprimento de Escala por Linha")
        tabela_linhas = df_dia.groupby('linha').agg(Prog=('carro', 'count'), Real=('status_realizada', 'sum')).reset_index()
        tabela_linhas['Cumprimento (%)'] = (tabela_linhas['Real'] / tabela_linhas['Prog'] * 100).round(1)
        
        fig_linhas = px.bar(tabela_linhas, x='linha', y='Cumprimento (%)', text='Cumprimento (%)', color='linha', template="plotly_dark")
        fig_linhas.update_layout(yaxis=dict(range=[0, 110]))
        st.plotly_chart(fig_linhas, use_container_width=True)

    # ==========================================
    # ABA 2: HISTÓRICO EXECUTIVO (A Tendência)
    # ==========================================
    with aba2:
        st.subheader("📈 Evolução da Operação ao Longo dos Dias")
        
        df_historico = df_viagens.groupby('data_operacao').agg(Prog=('carro', 'count'), Real=('status_realizada', 'sum')).reset_index()
        df_historico['Cumprimento (%)'] = (df_historico['Real'] / df_historico['Prog'] * 100).round(1)
        
        fig_hist = px.line(df_historico, x='data_operacao', y='Cumprimento (%)', text='Cumprimento (%)', markers=True, template="plotly_dark")
        fig_hist.update_traces(textposition="top center", line=dict(color='#00e5a0', width=4), marker=dict(size=10))
        fig_hist.update_yaxes(range=[0, 110], title="Cumprimento de Escala (%)")
        fig_hist.update_xaxes(title="Data")
        st.plotly_chart(fig_hist, use_container_width=True)

    # ==========================================
    # ABA 3: O PÓDIO DE OURO
    # ==========================================
    with aba3:
        st.subheader("🏆 Top 10 Profissionais - Viagens Cravadas (-5 a +5 min)")
        
        # Matemática para descobrir quem saiu no horário exato
        df_viagens['viagem_perfeita'] = df_viagens['dif_saida_minutos'].apply(lambda x: 1 if pd.notna(x) and -5 <= x <= 5 else 0)
        
        df_motoristas = df_viagens[(df_viagens['motorista'] != 'Não Informado') & (df_viagens['motorista'].notna())]
        tabela_podio = df_motoristas.groupby('motorista').agg(Total_Viagens=('carro', 'count'), Perfeitas=('viagem_perfeita', 'sum')).reset_index()
        tabela_podio = tabela_podio[tabela_podio['Total_Viagens'] >= 3] # Filtro de justiça (mínimo 3 viagens)
        tabela_podio['Taxa de Perfeição (%)'] = (tabela_podio['Perfeitas'] / tabela_podio['Total_Viagens'] * 100).round(1)
        
        # Pega os 10 melhores
        tabela_podio = tabela_podio.sort_values('Perfeitas', ascending=False).head(10).sort_values('Perfeitas', ascending=True)
        
        fig_podio = px.bar(tabela_podio, x='Perfeitas', y='motorista', orientation='h', text='Taxa de Perfeição (%)', color='Taxa de Perfeição (%)', template="plotly_dark", color_continuous_scale="Viridis")
        fig_podio.update_traces(textposition='outside')
        fig_podio.update_xaxes(title="Número de Viagens Perfeitas")
        fig_podio.update_yaxes(title="Matrícula do Motorista")
        st.plotly_chart(fig_podio, use_container_width=True)
        # ==========================================
        # ABA 4: CAUSA RAIZ (TRÂNSITO VS ATRASO)
        # ==========================================
    with aba4:
        st.subheader("🚦 Impacto do Trânsito na Operação (Causa Raiz)")
        
        try:
            import json
            # Carrega o arquivo de trânsito
            with open("transito_cco_filtro_trecho_2026-05-15.json", 'r', encoding='utf-8') as f:
                dados_transito = json.load(f)
                
            df_transito = pd.DataFrame(dados_transito['grade'])
            df_transito['Hora'] = pd.to_datetime(df_transito['horario'], format='%H:%M', errors='coerce').dt.hour
            
            # Divide a tela em duas partes
            col_mapa, col_cruz = st.columns([1, 1])
            
            with col_mapa:
                st.markdown("**Mapa de Retenção Viária**")
                heatmap_transito = df_transito.groupby(['via', 'horario'])['nivel'].max().reset_index()
                matriz_transito = heatmap_transito.pivot(index='via', columns='horario', values='nivel').fillna(1)
                
                fig_transito = px.imshow(
                    matriz_transito,
                    labels=dict(x="Horário", y="Via (Trecho)", color="Gravidade"),
                    color_continuous_scale=[(0, "green"), (0.33, "yellow"), (0.66, "orange"), (1, "red")],
                    aspect="auto",
                    template="plotly_dark"
                )
                fig_transito.update_xaxes(side="top")
                st.plotly_chart(fig_transito, use_container_width=True)
                
            with col_cruz:
                st.markdown("**Prova Matemática: Atraso vs Engarrafamento**")
                
                # Usa as viagens do dia que está selecionado na Aba 1
                df_cruz = df_dia.copy()
                df_cruz['Hora'] = pd.to_datetime(df_cruz['prog_saida'], format='%H:%M', errors='coerce').dt.hour
                
                linhas_validas = sorted(df_cruz['linha'].dropna().unique())
                
                if len(linhas_validas) > 0:
                    linha_alvo = st.selectbox("Selecione a Linha:", linhas_validas)
                    via_alvo = st.selectbox("Selecione a Via do Trajeto:", sorted(df_transito['via'].dropna().unique()))
                    
                    df_linha = df_cruz[df_cruz['linha'] == linha_alvo].groupby('Hora')['dif_saida_minutos'].mean().reset_index()
                    df_via = df_transito[df_transito['via'] == via_alvo].groupby('Hora')['nivel'].max().reset_index()
                    
                    df_cruzamento = pd.merge(df_linha, df_via, on='Hora', how='inner')
                    
                    if not df_cruzamento.empty:
                        import plotly.graph_objects as go
                        from plotly.subplots import make_subplots
                        
                        fig_cruz = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        # Barras Laranjas (Atraso da Linha)
                        fig_cruz.add_trace(go.Bar(x=df_cruzamento['Hora'], y=df_cruzamento['dif_saida_minutos'], name="Atraso Médio (Min)", marker_color='#ff9f4d'), secondary_y=False)
                        
                        # Linha Vermelha (Nível de Trânsito da Via)
                        fig_cruz.add_trace(go.Scatter(x=df_cruzamento['Hora'], y=df_cruzamento['nivel'], name="Nível Trânsito", line=dict(color='#ff4d6d', width=4)), secondary_y=True)
                        
                        fig_cruz.update_layout(template="plotly_dark", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
                        fig_cruz.update_yaxes(title_text="Atraso (Minutos)", secondary_y=False)
                        fig_cruz.update_yaxes(title_text="Trânsito (1=Livre, 5=Incidente)", range=[0, 5], showgrid=False, secondary_y=True)
                        
                        st.plotly_chart(fig_cruz, use_container_width=True)
                    else:
                        st.info("Sem dados cruzados para esta seleção de linha e via.")
                else:
                    st.warning("Nenhuma viagem encontrada para este dia.")
                    
        except Exception as e:
            st.error(f"Erro ao carregar os dados de trânsito: Verifique se o ficheiro 'transito_cco_filtro_trecho_2026-05-15.json' está na pasta.")