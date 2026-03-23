import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import time

# --- TENTA IMPORTAR O CALENDÁRIO COM SEGURANÇA ---
try:
    from streamlit_calendar import calendar
    HAS_CALENDAR = True
except ImportError:
    HAS_CALENDAR = False

# --- CONFIGURAÇÃO DE SEGURANÇA (SUPABASE) ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Erro de conexão. Verifique os Segredos (Secrets) no painel do Streamlit.")
    st.stop()

# --- FUNÇÕES DE BANCO DE DADOS E AUDITORIA ---
def carregar_usuarios():
    res = supabase.table('usuarios').select("*").execute()
    if not res.data:
        return pd.DataFrame(columns=['id', 'login', 'senha', 'perfil'])
    return pd.DataFrame(res.data)

def carregar_processos():
    res = supabase.table('processos').select("*").execute()
    if not res.data:
        return pd.DataFrame(columns=['id_processo', 'tipo', 'numero', 'cliente'])
    return pd.DataFrame(res.data)

def carregar_prazos():
    res = supabase.table('prazos').select("*").execute()
    if not res.data:
        return pd.DataFrame(columns=['id_prazo', 'processo', 'nome_cliente', 'nome_tarefa', 'orgao_ente', 'tarefa', 'data_inicio', 'data_fim', 'responsavel', 'urgente', 'status', 'vinculado'])
    return pd.DataFrame(res.data)

def registrar_movimentacao(id_prazo, acao, usuario):
    try:
        data_hora = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M:%S")
        dados = {'id_prazo': id_prazo, 'acao': acao, 'usuario': usuario, 'data_hora': data_hora}
        supabase.table('historico_tarefas').insert(dados).execute()
    except Exception as e:
        pass

def criar_notificacao(id_prazo, usuario_destino, mensagem, menu_atual):
    try:
        data_hora = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M:%S")
        dados = {
            'id_prazo': id_prazo,
            'usuario_destino': usuario_destino,
            'mensagem': mensagem,
            'menu_atual': menu_atual,
            'lida': 'Não',
            'data_hora': data_hora
        }
        supabase.table('notificacoes').insert(dados).execute()
    except Exception as e:
        pass

def formatar_tabela_exibicao(df):
    df_exibicao = df.copy()
    if not df_exibicao.empty:
        df_exibicao['processo'] = df_exibicao.apply(
            lambda row: row['nome_tarefa'] if row.get('vinculado') == 'Não' else row.get('processo'), 
            axis=1
        )
    return df_exibicao

# --- SISTEMA DE INTELIGÊNCIA VISUAL (CORES DE ALERTA) ---
def colorir_prazos(row):
    cor_padrao = [''] * len(row)
    status_inativos = ["Concluído", "Arquivado", "Protocolado/Entregue", "Protocolado Sem Revisão", "Aguardando Protocolo/Entrega"]
    
    if row.get('status') in status_inativos:
        return cor_padrao
        
    try:
        hoje = datetime.now(timezone(timedelta(hours=-3))).date()
        data_fim_str = str(row['data_fim']).split(" ")[0]
        data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        dias_uteis = np.busday_count(hoje.strftime('%Y-%m-%d'), data_fim.strftime('%Y-%m-%d'))
        
        if dias_uteis <= 1:
            return ['background-color: rgba(255, 99, 71, 0.3)'] * len(row) # Vermelho
        elif dias_uteis == 2:
            return ['background-color: rgba(255, 235, 59, 0.4)'] * len(row) # Amarelo
        else:
            return cor_padrao
    except:
        return cor_padrao

def exibir_detalhes_tarefa(dados_completos):
    icone_urgente = "🚨 " if dados_completos['urgente'] == "Sim" else "📁 "
    with st.expander(f"{icone_urgente} {dados_completos['nome_tarefa']} | Cliente: {dados_completos['nome_cliente']}", expanded=True):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.write(f"**Cliente:** {dados_completos['nome_cliente']}")
            st.write(f"**Processo Vinculado:** {dados_completos['processo']}")
            st.write(f"**Órgão / Ente:** {dados_completos['orgao_ente'] if dados_completos['orgao_ente'] else 'Não informado'}")
            st.write(f"**Responsável:** {dados_completos['responsavel']}")
        with col_d2:
            st.write(f"**Status:** {dados_completos['status']}")
            st.write(f"**Urgência:** {dados_completos['urgente']}")
            st.write(f"**Data de Início:** {dados_completos['data_inicio']}")
            st.write(f"**Prazo Final:** {dados_completos['data_fim']}")
        
        st.write("**Descrição Detalhada / Diligência:**")
        if pd.notna(dados_completos['tarefa']) and str(dados_completos['tarefa']).strip() != "":
            st.info(dados_completos['tarefa'])
        else:
            st.write("*Nenhuma descrição detalhada informada.*")

STATUS_OPTIONS = [
    "Ativo", 
    "Pendente de Revisão", 
    "Devolvido Para Alteração", 
    "Aguardando Protocolo/Entrega", 
    "Protocolado Sem Revisão", 
    "Protocolado/Entregue", 
    "Arquivado"
]

config_visual_colunas = {
    "id_prazo": None, 
    "Selecionar": st.column_config.CheckboxColumn("✓", width="small"),
    "processo": st.column_config.TextColumn("Processo / Tarefa", width="large"),
    "responsavel": st.column_config.TextColumn("Responsável", width="small"),
    "data_fim": st.column_config.TextColumn("Prazo Final", width="small"),
    "urgente": st.column_config.TextColumn("Urgente", width="small"),
    "status": st.column_config.TextColumn("Status", width="small"),
    "nome_cliente": st.column_config.TextColumn("Cliente", width="medium"),
    "orgao_ente": st.column_config.TextColumn("Órgão", width="medium")
}

df_check_admin = carregar_usuarios()
if df_check_admin.empty:
    supabase.table('usuarios').insert({'login': 'admin', 'senha': 'admin', 'perfil': 'Administrador'}).execute()

if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None
if 'perfil_usuario' not in st.session_state:
    st.session_state['perfil_usuario'] = None

def tela_login():
    st.title("⚖️ Sistema de Gestão Jurídica")
    st.subheader("Acesso ao Sistema")
    
    with st.form("form_login", clear_on_submit=True):
        login_input = st.text_input("Login")
        senha_input = st.text_input("Senha", type="password")
        submit_login = st.form_submit_button("Entrar")
        
        if submit_login:
            df_users = carregar_usuarios()
            usuario = df_users[(df_users['login'] == login_input) & (df_users['senha'] == senha_input)]
            
            if not usuario.empty:
                st.session_state['usuario_logado'] = usuario.iloc[0]['login']
                st.session_state['perfil_usuario'] = usuario.iloc[0]['perfil']
                st.rerun()
            else:
                st.error("Login ou senha incorretos.")

def tela_principal():
    st.sidebar.title(f"Bem-vindo, {st.session_state['usuario_logado']}")
    st.sidebar.caption(f"Perfil: {st.session_state['perfil_usuario']}")
    st.sidebar.divider()

    df_processos = carregar_processos()
    df_prazos = carregar_prazos()
    df_usuarios = carregar_usuarios()
    lista_usuarios = df_usuarios['login'].tolist() if not df_usuarios.empty else ["admin"]

    # ==========================================
    # VISÃO DO ADMINISTRADOR
    # ==========================================
    if st.session_state['perfil_usuario'] == 'Administrador':
        menu_admin = st.sidebar.radio(
            "Navegação:", 
            [
                "CADASTRAR TAREFAS",
                "PAINEL DE PRAZOS", 
                "P/ REVISÃO", 
                "PENDENTE DE CORREÇÃO", 
                "P/PROTOCOLO ou ENVIO", 
                "CONCLUÍDOS", 
                "HISTÓRICO DAS TAREFAS", 
                "Cadastrar Processo", 
                "Gerenciar Usuários"
            ]
        )
        
        st.sidebar.divider()
        if st.sidebar.button("Sair / Logout"):
            st.session_state['usuario_logado'] = None
            st.session_state['perfil_usuario'] = None
            for key in ['modo_edicao', 'modo_edicao_user']:
                if key in st.session_state: del st.session_state[key]
            st.rerun()

        # 1. CADASTRAR TAREFAS
        if menu_admin == "CADASTRAR TAREFAS":
            st.header("Cadastrar Nova Tarefa / Diligência")
            
            with st.form("form_novo_prazo", clear_on_submit=True):
                nome_cliente = st.text_input("Nome do Cliente (*Obrigatório):")
                processo = st.text_input("Número do Processo (Opcional se não for vincular):")
                vincular = st.checkbox("Vincular Tarefa ao Processo")
                nome_tarefa = st.text_input("Nome da Tarefa (*Obrigatório - Ex: Protocolar Petição, Buscar Documento):")
                orgao = st.text_input("Órgão / Ente (Ex: 1ª Vara Cível, INSS, etc.):")
                tarefa = st.text_area("Descrição detalhada da Tarefa / Diligência:")
                
                col1, col2 = st.columns(2)
                with col1: data_inicio = st.date_input("Data de Início da Tarefa:")
                with col2: data_fim = st.date_input("Data Final / Prazo Fatal:")
                    
                responsavel = st.selectbox("Atribuir Tarefa ao Usuário:", lista_usuarios)
                urgente = st.checkbox("🚨 URGENTE")
                
                submit_prazo = st.form_submit_button("CADASTRAR")
                
                if submit_prazo:
                    if nome_cliente == "" or nome_tarefa == "":
                        st.error("Os campos 'Nome do Cliente' e 'Nome da Tarefa' são obrigatórios.")
                    elif vincular and processo == "":
                        st.error("Para vincular, você precisa digitar o Número do Processo acima.")
                    else:
                        novo_id = f"PZ-{len(df_prazos) + 1}"
                        processo_salvar = processo if vincular else "Não vinculado"
                        
                        dados_prazo = {
                            'id_prazo': novo_id, 'processo': processo_salvar, 'nome_cliente': nome_cliente, 'nome_tarefa': nome_tarefa,
                            'orgao_ente': orgao, 'tarefa': tarefa, 'data_inicio': str(data_inicio), 
                            'data_fim': str(data_fim), 'responsavel': responsavel, 
                            'urgente': "Sim" if urgente else "Não", 'status': 'Ativo', 'vinculado': "Sim" if vincular else "Não"
                        }
                        supabase.table('prazos').insert(dados_prazo).execute()
                        registrar_movimentacao(novo_id, "Tarefa Cadastrada no Sistema", st.session_state['usuario_logado'])
                        criar_notificacao(novo_id, responsavel, f"Nova Tarefa Atribuída: {nome_tarefa}", "Meus Prazos Ativos")
                        
                        st.success("✅ Tarefa cadastrada e atribuída com sucesso!")
                        time.sleep(2)
                        st.rerun()

        # 2. PAINEL DE PRAZOS
        elif menu_admin == "PAINEL DE PRAZOS":
            st.header("Painel Geral de Prazos")
            
            if not df_prazos.empty:
                with st.expander("🔍 Filtros de Busca", expanded=True):
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        filtro_cliente = st.text_input("Cliente:")
                    with col_f2:
                        filtro_proc_tar = st.text_input("Processo/Tarefa:")
                        
                    col_f3, col_f4, col_f5 = st.columns(3)
                    with col_f3:
                        filtro_resp = st.multiselect("Responsável:", options=lista_usuarios)
                    with col_f4:
                        filtro_status = st.multiselect("Status:", options=STATUS_OPTIONS, default=["Ativo", "Pendente de Revisão", "Devolvido Para Alteração", "Aguardando Protocolo/Entrega"])
                    with col_f5:
                        filtro_urgente = st.multiselect("Urgente:", options=["Sim", "Não"])
                
                df_filtrado = df_prazos.copy()
                
                if filtro_cliente:
                    df_filtrado = df_filtrado[df_filtrado['nome_cliente'].astype(str).str.contains(filtro_cliente, case=False, na=False)]
                if filtro_proc_tar:
                    df_filtrado = df_filtrado[
                        df_filtrado['processo'].astype(str).str.contains(filtro_proc_tar, case=False, na=False) |
                        df_filtrado['nome_tarefa'].astype(str).str.contains(filtro_proc_tar, case=False, na=False)
                    ]
                if filtro_resp:
                    df_filtrado = df_filtrado[df_filtrado['responsavel'].isin(filtro_resp)]
                if filtro_status:
                    df_filtrado = df_filtrado[df_filtrado['status'].isin(filtro_status)]
                if filtro_urgente:
                    df_filtrado = df_filtrado[df_filtrado['urgente'].isin(filtro_urgente)]

                df_prazos_ordenado = df_filtrado.sort_values(by='data_fim', ascending=True)

                if 'modo_edicao' not in st.session_state:
                    st.session_state['modo_edicao'] = False
                if 'id_editar' not in st.session_state:
                    st.session_state['id_editar'] = None

                tab_lista, tab_calendario = st.tabs(["📋 Visualização em Lista", "📅 Visualização em Calendário"])

                with tab_lista:
                    if not st.session_state['modo_edicao']:
                        st.write("Marque a caixa de seleção na primeira coluna para Excluir, Editar ou Ver Detalhes.")
                        
                        if df_prazos_ordenado.empty:
                            st.warning("Nenhuma tarefa encontrada com os filtros selecionados.")
                        else:
                            df_exibicao = formatar_tabela_exibicao(df_prazos_ordenado)
                            df_exibicao.insert(0, "Selecionar", False) 
                            colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                            
                            df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                            
                            tabela_interativa = st.data_editor(
                                df_estilizado,
                                hide_index=True,
                                disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente'],
                                use_container_width=True,
                                column_config=config_visual_colunas
                            )
                            
                            linhas_selecionadas = tabela_interativa[tabela_interativa['Selecionar'] == True]
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("🗑️ EXCLUIR"):
                                    if not linhas_selecionadas.empty:
                                        for index, row in linhas_selecionadas.iterrows():
                                            supabase.table('prazos').delete().eq('id_prazo', row['id_prazo']).execute()
                                            registrar_movimentacao(row['id_prazo'], "Tarefa Excluída", st.session_state['usuario_logado'])
                                        st.success("✅ Registros excluídos com sucesso!")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.warning("Selecione pelo menos uma linha marcando a caixa de seleção.")
                                        
                            with col2:
                                if st.button("✏️ EDITAR"):
                                    if len(linhas_selecionadas) == 1:
                                        st.session_state['modo_edicao'] = True
                                        st.session_state['id_editar'] = linhas_selecionadas.iloc[0]['id_prazo']
                                        st.rerun()
                                    elif len(linhas_selecionadas) > 1:
                                        st.warning("Por favor, selecione apenas UMA linha para editar por vez.")
                                    else:
                                        st.warning("Selecione uma linha marcando a caixa de seleção para editar.")

                            if not linhas_selecionadas.empty:
                                st.divider()
                                st.subheader("📄 Detalhes do Registro Selecionado")
                                for index, row in linhas_selecionadas.iterrows():
                                    id_sel = row['id_prazo']
                                    dados_completos = df_prazos[df_prazos['id_prazo'] == id_sel].iloc[0]
                                    exibir_detalhes_tarefa(dados_completos)
                    
                    else:
                        st.subheader("✏️ Edição Rápida")
                        st.write("Altere os valores diretamente nas células da tabela abaixo e clique em Salvar.")
                        
                        id_alvo = st.session_state['id_editar']
                        df_editar = df_prazos[df_prazos['id_prazo'] == id_alvo].copy()
                        
                        colunas_editaveis = ['processo', 'nome_tarefa', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente', 'tarefa', 'vinculado']
                        
                        df_editado = st.data_editor(
                            df_editar[colunas_editaveis],
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "processo": st.column_config.TextColumn("Processo / Tarefa"),
                                "responsavel": st.column_config.SelectboxColumn("Responsável", options=lista_usuarios),
                                "data_fim": st.column_config.TextColumn("Prazo Final"),
                                "urgente": st.column_config.SelectboxColumn("Urgente", options=["Sim", "Não"]),
                                "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
                                "nome_cliente": st.column_config.TextColumn("Cliente"),
                                "orgao_ente": st.column_config.TextColumn("Órgão"),
                                "vinculado": st.column_config.SelectboxColumn("Vinculado", options=["Sim", "Não"])
                            }
                        )
                        
                        col_salvar, col_cancelar = st.columns(2)
                        with col_salvar:
                            if st.button("💾 SALVAR"):
                                linha_atualizada = df_editado.iloc[0]
                                dados_atualizados = linha_atualizada.to_dict()
                                supabase.table('prazos').update(dados_atualizados).eq('id_prazo', id_alvo).execute()
                                registrar_movimentacao(id_alvo, "Edição Manual de Dados/Status na Tabela", st.session_state['usuario_logado'])
                                st.success("✅ Cadastro alterado com sucesso!")
                                st.session_state['modo_edicao'] = False
                                st.session_state['id_editar'] = None
                                time.sleep(2)
                                st.rerun()
                                
                        with col_cancelar:
                            if st.button("❌ CANCELAR"):
                                st.session_state['modo_edicao'] = False
                                st.session_state['id_editar'] = None
                                st.rerun()
                
                with tab_calendario:
                    if not HAS_CALENDAR:
                        st.error("⚠️ O módulo do calendário ainda não está ativo. Aguarde o Streamlit Cloud atualizar e recarregue a página.")
                    else:
                        st.write("Clique no evento dentro do calendário para ver todos os detalhes aqui embaixo.")
                        
                        eventos_calendario = []
                        for _, row in df_prazos_ordenado.iterrows():
                            if pd.isna(row.get('data_fim')) or str(row.get('data_fim')).strip() == "":
                                continue
                                
                            cor_fundo = "#3b82f6" 
                            if row['status'] in ['Protocolado/Entregue', 'Concluído']:
                                cor_fundo = "#10b981" 
                            elif row['status'] == 'Pendente de Revisão':
                                cor_fundo = "#f59e0b" 
                            elif row['status'] == 'Devolvido Para Alteração':
                                cor_fundo = "#ec4899" 
                            elif row['status'] == 'Protocolado Sem Revisão':
                                cor_fundo = "#8b5cf6" 
                            elif row['status'] == 'Aguardando Protocolo/Entrega':
                                cor_fundo = "#0ea5e9" 
                            elif row['urgente'] == 'Sim':
                                cor_fundo = "#ef4444" 
                            
                            data_limpa = str(row['data_fim']).strip().split(" ")[0]
                                
                            eventos_calendario.append({
                                "title": f"{row['nome_cliente']} - {row['nome_tarefa']}",
                                "start": data_limpa, 
                                "id": str(row['id_prazo']),
                                "backgroundColor": cor_fundo,
                                "borderColor": cor_fundo,
                                "allDay": True 
                            })
                            
                        opcoes_calendario = {
                            "initialView": "dayGridMonth",
                            "headerToolbar": {
                                "left": "prev,next today",
                                "center": "title",
                                "right": "dayGridMonth,timeGridWeek,listMonth",
                            },
                        }
                        
                        cal_data = calendar(events=eventos_calendario, options=opcoes_calendario, custom_css="""
                            .fc-event-title { font-weight: bold; padding: 2px; }
                            .fc-event-time { display: none; }
                        """)
                        
                        if isinstance(cal_data, dict) and cal_data.get("callback") == "eventClick":
                            event_id_clicado = cal_data["eventClick"]["event"]["id"]
                            st.divider()
                            st.subheader("📄 Detalhes da Tarefa Selecionada")
                            
                            tarefa_selecionada = df_prazos[df_prazos['id_prazo'] == event_id_clicado]
                            if not tarefa_selecionada.empty:
                                dados_completos_cal = tarefa_selecionada.iloc[0]
                                exibir_detalhes_tarefa(dados_completos_cal)

            else:
                st.info("Nenhum prazo cadastrado no sistema ainda.")

        # 3. P/ REVISÃO (ADMIN)
        elif menu_admin == "P/ REVISÃO":
            st.header("Aprovação de Tarefas (P/ REVISÃO)")
            st.write("Marque as tarefas e escolha a ação desejada.")
            
            df_revisao = pd.DataFrame() if df_prazos.empty else df_prazos[df_prazos['status'] == 'Pendente de Revisão']
            
            if not df_revisao.empty:
                df_exibicao = formatar_tabela_exibicao(df_revisao)
                df_exibicao.insert(0, "Selecionar", False) 
                colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                tabela_revisao = st.data_editor(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente'],
                    column_config=config_visual_colunas
                )
                
                linhas_selecionadas = tabela_revisao[tabela_revisao['Selecionar'] == True]
                
                st.divider()
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("P/ PROTOCOLO ou ENVIO"):
                        if not linhas_selecionadas.empty:
                            for index, row in linhas_selecionadas.iterrows():
                                supabase.table('prazos').update({'status': 'Aguardando Protocolo/Entrega'}).eq('id_prazo', row['id_prazo']).execute()
                                registrar_movimentacao(row['id_prazo'], "Aprovado - Aguardando Protocolo Final", st.session_state['usuario_logado'])
                                criar_notificacao(row['id_prazo'], row['responsavel'], "Tarefa APROVADA! Avance para o protocolo final.", "P/PROTOCOLO ou ENVIO")
                            st.success("✅ Tarefa(s) aprovada(s) com sucesso!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma tarefa na tabela.")
                            
                with col_btn2:
                    if st.button("Enviar P/ CORREÇÃO"):
                        if not linhas_selecionadas.empty:
                            for index, row in linhas_selecionadas.iterrows():
                                supabase.table('prazos').update({'status': 'Devolvido Para Alteração'}).eq('id_prazo', row['id_prazo']).execute()
                                registrar_movimentacao(row['id_prazo'], "Devolvido para Correção", st.session_state['usuario_logado'])
                                criar_notificacao(row['id_prazo'], row['responsavel'], "Tarefa DEVOLVIDA! Verifique as correções necessárias.", "PENDENTE DE CORREÇÃO")
                            st.success("✅ Tarefa(s) devolvida(s) para o responsável realizar ajustes!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma tarefa na tabela.")
            else:
                st.success("Tudo limpo! Nenhuma tarefa aguardando revisão no momento.")

        # 4. PENDENTE DE CORREÇÃO (ADMIN)
        elif menu_admin == "PENDENTE DE CORREÇÃO":
            st.header("Demandas Devolvidas (PENDENTE DE CORREÇÃO)")
            st.write("Visualização de todas as tarefas da equipe que foram devolvidas e aguardam ajustes.")
            
            df_devolvidos = pd.DataFrame() if df_prazos.empty else df_prazos[df_prazos['status'] == 'Devolvido Para Alteração']
            
            if not df_devolvidos.empty:
                df_exibicao = formatar_tabela_exibicao(df_devolvidos)
                colunas_mostrar = ['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                st.dataframe(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    column_config=config_visual_colunas
                )
            else:
                st.success("Tudo limpo! Nenhuma demanda devolvida para alteração.")

        # 5. P/PROTOCOLO ou ENVIO (ADMIN)
        elif menu_admin == "P/PROTOCOLO ou ENVIO":
            st.header("Tarefas Protocoladas Sem Revisão (P/PROTOCOLO ou ENVIO)")
            st.write("Selecione as tarefas enviadas pela equipe e escolha se deseja confirmar a entrega ou arquivar.")
            
            df_protocolado = pd.DataFrame() if df_prazos.empty else df_prazos[df_prazos['status'] == 'Protocolado Sem Revisão']
            
            if not df_protocolado.empty:
                df_exibicao = formatar_tabela_exibicao(df_protocolado)
                df_exibicao.insert(0, "Selecionar", False)
                colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                tabela_protocolado = st.data_editor(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente'],
                    column_config=config_visual_colunas
                )
                
                linhas_selecionadas_prot = tabela_protocolado[tabela_protocolado['Selecionar'] == True]
                
                st.divider()
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("Confirmar (Protocolado/Entregue)"):
                        if not linhas_selecionadas_prot.empty:
                            for index, row in linhas_selecionadas_prot.iterrows():
                                supabase.table('prazos').update({'status': 'Protocolado/Entregue'}).eq('id_prazo', row['id_prazo']).execute()
                                registrar_movimentacao(row['id_prazo'], "Confirmado e Baixado como Entregue", st.session_state['usuario_logado'])
                            st.success("✅ Tarefa(s) confirmada(s) como Entregue/Protocolada!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma tarefa na tabela.")
                            
                with col_btn2:
                    if st.button("Arquivar"):
                        if not linhas_selecionadas_prot.empty:
                            for index, row in linhas_selecionadas_prot.iterrows():
                                supabase.table('prazos').update({'status': 'Arquivado'}).eq('id_prazo', row['id_prazo']).execute()
                                registrar_movimentacao(row['id_prazo'], "Movido para Arquivo", st.session_state['usuario_logado'])
                            st.success("✅ Tarefa(s) enviada(s) para o Arquivo.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma tarefa na tabela.")
            else:
                st.success("Tudo limpo! Nenhuma tarefa protocolada sem revisão no momento.")
                
        # 6. CONCLUÍDOS (ADMIN - COM FILTROS AVANÇADOS)
        elif menu_admin == "CONCLUÍDOS":
            st.header("Processos e Tarefas Concluídas")
            st.write("Histórico consolidado de todas as demandas finalizadas e entregues ao cliente ou protocoladas.")
            
            df_finalizados = pd.DataFrame() if df_prazos.empty else df_prazos[df_prazos['status'] == 'Protocolado/Entregue']
            
            if not df_finalizados.empty:
                with st.expander("🔍 Filtros de Busca", expanded=True):
                    col_c1, col_c2, col_c3 = st.columns(3)
                    with col_c1:
                        filtro_resp_c = st.multiselect("Filtrar por Usuário (Responsável):", options=lista_usuarios)
                    with col_c2:
                        filtro_cliente_c = st.text_input("Filtrar por Cliente:")
                    with col_c3:
                        filtro_data_c = st.text_input("Filtrar por Data (Prazo Final Ex: 2026-03-19):")
                
                df_filtrado_c = df_finalizados.copy()
                
                if filtro_resp_c:
                    df_filtrado_c = df_filtrado_c[df_filtrado_c['responsavel'].isin(filtro_resp_c)]
                if filtro_cliente_c:
                    df_filtrado_c = df_filtrado_c[df_filtrado_c['nome_cliente'].astype(str).str.contains(filtro_cliente_c, case=False, na=False)]
                if filtro_data_c:
                    df_filtrado_c = df_filtrado_c[df_filtrado_c['data_fim'].astype(str).str.contains(filtro_data_c)]
                
                if not df_filtrado_c.empty:
                    df_exibicao = formatar_tabela_exibicao(df_filtrado_c)
                    colunas_mostrar = ['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                    df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                    
                    st.dataframe(
                        df_estilizado, 
                        use_container_width=True, hide_index=True,
                        column_config=config_visual_colunas
                    )
                else:
                    st.info("Nenhuma demanda encontrada com esses filtros.")
            else:
                st.info("Nenhuma demanda finalizada nesta categoria ainda.")

        # 7. HISTÓRICO DAS TAREFAS (AUDITORIA)
        elif menu_admin == "HISTÓRICO DAS TAREFAS":
            st.header("⏳ Histórico e Rastreio de Tarefas")
            st.write("Acompanhe toda a linha do tempo e as movimentações de cada tarefa no sistema.")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1: busca_tarefa = st.text_input("Buscar por Processo / Tarefa:")
            with col_b2: busca_cliente = st.text_input("Buscar por Cliente:")
                
            df_filtrado = df_prazos.copy()
            if not df_filtrado.empty:
                if busca_tarefa:
                    df_filtrado = df_filtrado[
                        df_filtrado['processo'].astype(str).str.contains(busca_tarefa, case=False, na=False) |
                        df_filtrado['nome_tarefa'].astype(str).str.contains(busca_tarefa, case=False, na=False)
                    ]
                if busca_cliente:
                    df_filtrado = df_filtrado[df_filtrado['nome_cliente'].astype(str).str.contains(busca_cliente, case=False, na=False)]
                
                if not df_filtrado.empty:
                    df_exibicao = formatar_tabela_exibicao(df_filtrado)
                    df_exibicao.insert(0, "Selecionar", False)
                    colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'status', 'nome_cliente']
                    
                    tabela_hist = st.data_editor(
                        df_exibicao[colunas_mostrar], 
                        use_container_width=True, hide_index=True,
                        disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'status', 'nome_cliente'],
                        column_config=config_visual_colunas
                    )
                    
                    linhas_selecionadas_hist = tabela_hist[tabela_hist['Selecionar'] == True]
                    
                    if not linhas_selecionadas_hist.empty:
                        st.divider()
                        st.subheader("📜 Linha do Tempo da Tarefa")
                        for index, row in linhas_selecionadas_hist.iterrows():
                            id_alvo = row['id_prazo']
                            st.markdown(f"**Rastreio do ID:** `{id_alvo}` | **Tarefa:** {row['processo']}")
                            
                            res_hist = supabase.table('historico_tarefas').select('*').eq('id_prazo', id_alvo).order('id', desc=False).execute()
                            if res_hist.data:
                                df_h = pd.DataFrame(res_hist.data)
                                st.dataframe(
                                    df_h[['data_hora', 'acao', 'usuario']], 
                                    use_container_width=True, hide_index=True,
                                    column_config={
                                        "data_hora": st.column_config.TextColumn("Data / Hora", width="medium"), 
                                        "acao": st.column_config.TextColumn("Movimentação / Menu", width="large"), 
                                        "usuario": st.column_config.TextColumn("Perfil Responsável", width="medium")
                                    }
                                )
                            else:
                                st.info("Nenhuma movimentação detalhada registrada para esta tarefa ainda.")
                else:
                    st.info("Nenhuma tarefa encontrada com esses filtros.")
            else:
                st.info("Nenhuma tarefa cadastrada no sistema.")

        # 8. CADASTRAR PROCESSO
        elif menu_admin == "Cadastrar Processo":
            st.header("Cadastrar Novo Processo")
            with st.form("form_novo_processo", clear_on_submit=True):
                tipo_proc = st.selectbox("Tipo:", ["Judicial", "Extrajudicial"])
                num_proc = st.text_input("Número do Processo (Apenas números):")
                cliente = st.text_input("Nome do Cliente:")
                submit_proc = st.form_submit_button("Salvar Processo")
                
                if submit_proc:
                    if num_proc and cliente:
                        num_proc_limpo = num_proc.replace(".", "").replace("-", "")
                        novo_id = f"PR-{len(df_processos) + 1}"
                        dados_proc = {'id_processo': novo_id, 'tipo': tipo_proc, 'numero': num_proc_limpo, 'cliente': cliente}
                        supabase.table('processos').insert(dados_proc).execute()
                        st.success("✅ Processo cadastrado com sucesso!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Preencha o Número e o Cliente.")

        # 9. GERENCIAR USUÁRIOS
        elif menu_admin == "Gerenciar Usuários":
            st.header("👥 Gerenciar Usuários")
            
            with st.expander("➕ Cadastrar Novo Usuário", expanded=False):
                with st.form("form_novo_usuario", clear_on_submit=True):
                    novo_login = st.text_input("Novo Login (Nome de usuário):")
                    nova_senha = st.text_input("Nova Senha:", type="password")
                    novo_perfil = st.selectbox("Perfil:", ["Usuário", "Administrador"])
                    submit_user = st.form_submit_button("Criar Usuário")
                    
                    if submit_user:
                        novo_login_limpo = novo_login.strip() 
                        if novo_login_limpo and nova_senha:
                            if not df_usuarios.empty and novo_login_limpo in df_usuarios['login'].values:
                                st.error("Este login já existe! Escolha outro.")
                            else:
                                supabase.table('usuarios').insert({'login': novo_login_limpo, 'senha': nova_senha, 'perfil': novo_perfil}).execute()
                                st.success(f"✅ Usuário '{novo_login_limpo}' criado com sucesso!")
                                time.sleep(2)
                                st.rerun()
                        else:
                            st.error("Preencha login e senha.")

            st.divider()
            st.subheader("Usuários Cadastrados")
            
            if not df_usuarios.empty:
                if 'modo_edicao_user' not in st.session_state:
                    st.session_state['modo_edicao_user'] = False
                if 'id_editar_user' not in st.session_state:
                    st.session_state['id_editar_user'] = None

                if not st.session_state['modo_edicao_user']:
                    df_exibicao_user = df_usuarios.copy()
                    df_exibicao_user.insert(0, "Selecionar", False)
                    
                    colunas_user = ['Selecionar', 'id', 'login', 'senha', 'perfil']
                    
                    tabela_users = st.data_editor(
                        df_exibicao_user[colunas_user],
                        hide_index=True,
                        disabled=['id', 'login', 'senha', 'perfil'], 
                        use_container_width=True,
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn("✓", width="small"),
                            "id": None,
                            "login": st.column_config.TextColumn("Login/Usuário"),
                            "senha": st.column_config.TextColumn("Senha Atual"), 
                            "perfil": st.column_config.TextColumn("Perfil de Acesso")
                        }
                    )
                    
                    linhas_selecionadas_user = tabela_users[tabela_users['Selecionar'] == True]
                    
                    col_u1, col_u2 = st.columns(2)
                    with col_u1:
                        if st.button("🗑️ EXCLUIR USUÁRIO"):
                            if not linhas_selecionadas_user.empty:
                                for index, row in linhas_selecionadas_user.iterrows():
                                    if row['login'] == 'admin':
                                        st.error("⚠️ Não é possível excluir o usuário Administrador Principal ('admin').")
                                    else:
                                        supabase.table('usuarios').delete().eq('id', row['id']).execute()
                                st.success("✅ Ação concluída!")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.warning("Selecione pelo menos um usuário marcando a caixa.")
                                
                    with col_u2:
                        if st.button("✏️ EDITAR USUÁRIO"):
                            if len(linhas_selecionadas_user) == 1:
                                if linhas_selecionadas_user.iloc[0]['login'] == 'admin':
                                    st.warning("⚠️ O login 'admin' é protegido e não pode ser editado. Crie outro administrador se necessário.")
                                else:
                                    st.session_state['modo_edicao_user'] = True
                                    st.session_state['id_editar_user'] = linhas_selecionadas_user.iloc[0]['id']
                                    st.rerun()
                            elif len(linhas_selecionadas_user) > 1:
                                st.warning("Por favor, selecione apenas UM usuário para editar por vez.")
                            else:
                                st.warning("Selecione um usuário marcando a caixa para editar.")

                else:
                    st.subheader("✏️ Alterar Senha ou Perfil")
                    id_alvo_u = st.session_state['id_editar_user']
                    df_editar_user = df_usuarios[df_usuarios['id'] == id_alvo_u].copy()
                    
                    df_editado_user = st.data_editor(
                        df_editar_user[['login', 'senha', 'perfil']],
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "login": st.column_config.TextColumn("Login (Não editável)", disabled=True), 
                            "senha": st.column_config.TextColumn("Nova Senha"),
                            "perfil": st.column_config.SelectboxColumn("Perfil", options=["Usuário", "Administrador"])
                        }
                    )
                    
                    col_salvar_u, col_cancelar_u = st.columns(2)
                    with col_salvar_u:
                        if st.button("💾 SALVAR ALTERAÇÃO"):
                            linha_atualizada_u = df_editado_user.iloc[0]
                            dados_atualizados_u = {'senha': linha_atualizada_u['senha'], 'perfil': linha_atualizada_u['perfil']}
                            supabase.table('usuarios').update(dados_atualizados_u).eq('id', int(id_alvo_u)).execute()
                            
                            st.success("✅ Dados do usuário atualizados com sucesso!")
                            st.session_state['modo_edicao_user'] = False
                            st.session_state['id_editar_user'] = None
                            time.sleep(2)
                            st.rerun()
                            
                    with col_cancelar_u:
                        if st.button("❌ CANCELAR"):
                            st.session_state['modo_edicao_user'] = False
                            st.session_state['id_editar_user'] = None
                            st.rerun()

    # ==========================================
    # VISÃO DO USUÁRIO COMUM
    # ==========================================
    else:
        # AVISO DE NOTIFICAÇÕES NÃO LIDAS NO TOPO
        try:
            res_nao_lidas = supabase.table('notificacoes').select('*').eq('usuario_destino', st.session_state['usuario_logado']).eq('lida', 'Não').execute()
            if res_nao_lidas.data:
                st.warning(f"🔔 **Atenção:** Você tem {len(res_nao_lidas.data)} nova(s) notificação(ões)! Verifique a aba 'NOTIFICAÇÕES'.")
        except:
            pass

        menu_user = st.sidebar.radio(
            "Navegação:", 
            [
                "NOTIFICAÇÕES",
                "Meus Prazos Ativos", 
                "P/ REVISÃO", 
                "PENDENTE DE CORREÇÃO", 
                "P/PROTOCOLO ou ENVIO", 
                "CONCLUÍDOS"
            ]
        )
        
        st.sidebar.divider()
        if st.sidebar.button("Sair / Logout"):
            st.session_state['usuario_logado'] = None
            st.session_state['perfil_usuario'] = None
            st.rerun()

        # TELA 0: NOTIFICAÇÕES
        if menu_user == "NOTIFICAÇÕES":
            st.header("🔔 Central de Notificações")
            st.write("Veja as tarefas que foram encaminhadas ou devolvidas para você. Selecione as lidas e clique no botão para retirar o destaque.")
            
            try:
                res_notif = supabase.table('notificacoes').select('*').eq('usuario_destino', st.session_state['usuario_logado']).order('id', desc=True).execute()
                df_notif = pd.DataFrame(res_notif.data)
            except:
                df_notif = pd.DataFrame()

            if not df_notif.empty:
                def colorir_notificacoes(row):
                    if row['lida'] == 'Não':
                        return ['background-color: rgba(59, 130, 246, 0.2); font-weight: bold'] * len(row)
                    return [''] * len(row)

                df_notif.insert(0, "Selecionar", False)
                col_mostrar = ['Selecionar', 'id', 'data_hora', 'id_prazo', 'mensagem', 'menu_atual', 'lida']
                df_estilizado_notif = df_notif[col_mostrar].style.apply(colorir_notificacoes, axis=1)
                
                tabela_notif = st.data_editor(
                    df_estilizado_notif,
                    hide_index=True,
                    disabled=['id', 'data_hora', 'id_prazo', 'mensagem', 'menu_atual', 'lida'],
                    use_container_width=True,
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn("✓", width="small"),
                        "id": None, 
                        "data_hora": st.column_config.TextColumn("Data/Hora", width="small"),
                        "id_prazo": st.column_config.TextColumn("ID", width="small"),
                        "mensagem": st.column_config.TextColumn("Notificação", width="large"),
                        "menu_atual": st.column_config.TextColumn("Menu de Destino", width="medium"),
                        "lida": st.column_config.TextColumn("Lida", width="small")
                    }
                )
                
                linhas_sel = tabela_notif[tabela_notif['Selecionar'] == True]
                if st.button("Marcar como Ciente / Lida"):
                    if not linhas_sel.empty:
                        for idx, row in linhas_sel.iterrows():
                            if row['lida'] == 'Não':
                                supabase.table('notificacoes').update({'lida': 'Sim'}).eq('id', row['id']).execute()
                        st.success("✅ Notificações atualizadas!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Selecione pelo menos uma notificação na caixa da esquerda.")
            else:
                st.info("Você não tem nenhuma notificação.")

        # TELA 1: MEUS PRAZOS ATIVOS
        elif menu_user == "Meus Prazos Ativos":
            st.header("Meus Prazos e Diligências")
            
            meus_prazos = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Ativo')]
            
            if not meus_prazos.empty:
                st.write("Marque a caixa de seleção da(s) tarefa(s) que deseja atualizar e escolha a ação abaixo:")
                
                meus_prazos = meus_prazos.sort_values(by='data_fim')
                df_exibicao = formatar_tabela_exibicao(meus_prazos)
                df_exibicao.insert(0, "Selecionar", False)
                
                colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                tabela_interativa_user = st.data_editor(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente'],
                    column_config=config_visual_colunas
                )
                
                linhas_selecionadas_user = tabela_interativa_user[tabela_interativa_user['Selecionar'] == True]
                
                st.divider()
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("Enviar para P/ REVISÃO"):
                        if not linhas_selecionadas_user.empty:
                            for index, row in linhas_selecionadas_user.iterrows():
                                supabase.table('prazos').update({'status': 'Pendente de Revisão'}).eq('id_prazo', row['id_prazo']).execute()
                                registrar_movimentacao(row['id_prazo'], "Enviado P/ REVISÃO (Usuário)", st.session_state['usuario_logado'])
                            st.success("✅ Tarefa(s) enviada(s) para revisão com sucesso!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma tarefa marcando a caixa de seleção na tabela acima.")
                            
                with col_btn2:
                    if st.button("P/PROTOCOLO ou ENVIO"):
                        if not linhas_selecionadas_user.empty:
                            for index, row in linhas_selecionadas_user.iterrows():
                                supabase.table('prazos').update({'status': 'Protocolado Sem Revisão'}).eq('id_prazo', row['id_prazo']).execute()
                                registrar_movimentacao(row['id_prazo'], "Enviado Direto P/ PROTOCOLO (Usuário)", st.session_state['usuario_logado'])
                            st.success("✅ Tarefa(s) protocolada(s) sem revisão com sucesso!")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.warning("Selecione pelo menos uma tarefa marcando a caixa de seleção na tabela acima.")
            else:
                st.success("Você não tem prazos ativos no momento. Bom trabalho!")

        # TELA 2: P/ REVISÃO
        elif menu_user == "P/ REVISÃO":
            st.header("Minhas Tarefas (P/ REVISÃO)")
            minhas_revisoes = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Pendente de Revisão')]
            
            if not minhas_revisoes.empty:
                df_exibicao = formatar_tabela_exibicao(minhas_revisoes)
                colunas_mostrar = ['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                st.dataframe(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    column_config=config_visual_colunas
                )
            else:
                st.info("Você não tem nenhuma tarefa aguardando revisão.")

        # TELA 3: PENDENTE DE CORREÇÃO
        elif menu_user == "PENDENTE DE CORREÇÃO":
            st.header("Demandas Devolvidas (PENDENTE DE CORREÇÃO)")
            
            tarefas_devolvidas = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Devolvido Para Alteração')]
            
            if not tarefas_devolvidas.empty:
                st.write("Realize as alterações exigidas pelo administrador, selecione as tarefas abaixo e envie novamente para revisão.")
                df_exibicao = formatar_tabela_exibicao(tarefas_devolvidas)
                df_exibicao.insert(0, "Selecionar", False)
                
                colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                tabela_devolvidas = st.data_editor(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente'],
                    column_config=config_visual_colunas
                )
                
                linhas_selecionadas_dev = tabela_devolvidas[tabela_devolvidas['Selecionar'] == True]
                
                if st.button("Reenviar Para Revisão"):
                    if not linhas_selecionadas_dev.empty:
                        for index, row in linhas_selecionadas_dev.iterrows():
                            supabase.table('prazos').update({'status': 'Pendente de Revisão'}).eq('id_prazo', row['id_prazo']).execute()
                            registrar_movimentacao(row['id_prazo'], "Reenviado P/ REVISÃO após Correção", st.session_state['usuario_logado'])
                        st.success("✅ Tarefa(s) reenviada(s) para revisão!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.warning("Selecione pelo menos uma tarefa na tabela.")
            else:
                st.success("Você não possui tarefas devolvidas para alteração no momento.")

        # TELA 4: P/PROTOCOLO ou ENVIO (AÇÃO)
        elif menu_user == "P/PROTOCOLO ou ENVIO":
            st.header("P/PROTOCOLO ou ENVIO")
            
            tarefas_aprovadas = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Aguardando Protocolo/Entrega')]
            
            if not tarefas_aprovadas.empty:
                st.write("Estas tarefas foram aprovadas. Após o protocolo ou entrega final, selecione as caixas e conclua a etapa.")
                df_exibicao = formatar_tabela_exibicao(tarefas_aprovadas)
                df_exibicao.insert(0, "Selecionar", False)
                
                colunas_mostrar = ['Selecionar', 'id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                tabela_protocolo = st.data_editor(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    disabled=['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente'],
                    column_config=config_visual_colunas
                )
                
                linhas_selecionadas_prot = tabela_protocolo[tabela_protocolo['Selecionar'] == True]
                
                if st.button("Enviar para CONCLUÍDOS"):
                    if not linhas_selecionadas_prot.empty:
                        for index, row in linhas_selecionadas_prot.iterrows():
                            supabase.table('prazos').update({'status': 'Protocolado/Entregue'}).eq('id_prazo', row['id_prazo']).execute()
                            registrar_movimentacao(row['id_prazo'], "Marcado como Concluído (Entregue)", st.session_state['usuario_logado'])
                        st.success("✅ Tarefa(s) concluída(s) e registrada(s) como protocolada/entregue!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.warning("Selecione pelo menos uma tarefa na tabela.")
            else:
                st.success("Nenhuma tarefa aguardando protocolo ou entrega neste momento.")
                
        # TELA 5: CONCLUÍDOS (LEITURA)
        elif menu_user == "CONCLUÍDOS":
            st.header("Processos e Tarefas Concluídas")
            st.write("Seu histórico de tarefas aprovadas e finalizadas com sucesso.")
            
            minhas_finalizadas = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Protocolado/Entregue')]
            
            if not minhas_finalizadas.empty:
                df_exibicao = formatar_tabela_exibicao(minhas_finalizadas)
                colunas_mostrar = ['id_prazo', 'processo', 'responsavel', 'data_fim', 'urgente', 'status', 'nome_cliente', 'orgao_ente']
                df_estilizado = df_exibicao[colunas_mostrar].style.apply(colorir_prazos, axis=1)
                
                st.dataframe(
                    df_estilizado, 
                    use_container_width=True, hide_index=True,
                    column_config=config_visual_colunas
                )
            else:
                st.info("Nenhuma demanda sua finalizada nesta categoria ainda.")

# --- MOTOR DO APLICATIVO ---
if st.session_state['usuario_logado'] is None:
    tela_login()
else:
    tela_principal()
