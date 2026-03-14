import streamlit as st
import pandas as pd
from supabase import create_client, Client
import time

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

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_usuarios():
    res = supabase.table('usuarios').select("*").execute()
    if not res.data:
        return pd.DataFrame(columns=['login', 'senha', 'perfil'])
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

# Função auxiliar para visualização limpa
def formatar_tabela_exibicao(df):
    df_exibicao = df.copy()
    if not df_exibicao.empty:
        df_exibicao['processo'] = df_exibicao.apply(
            lambda row: row['nome_tarefa'] if row.get('vinculado') == 'Não' else row.get('processo'), 
            axis=1
        )
    return df_exibicao

# --- CRIAÇÃO DO PRIMEIRO ADMIN ---
df_check_admin = carregar_usuarios()
if df_check_admin.empty:
    supabase.table('usuarios').insert({'login': 'admin', 'senha': 'admin', 'perfil': 'Administrador'}).execute()

# --- CONTROLE DE SESSÃO (LOGIN) ---
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None
if 'perfil_usuario' not in st.session_state:
    st.session_state['perfil_usuario'] = None

# --- TELA DE LOGIN ---
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

# --- TELA PRINCIPAL ---
def tela_principal():
    st.sidebar.title(f"Bem-vindo, {st.session_state['usuario_logado']}")
    st.sidebar.caption(f"Perfil: {st.session_state['perfil_usuario']}")
    st.sidebar.divider()

    df_processos = carregar_processos()
    df_prazos = carregar_prazos()
    df_usuarios = carregar_usuarios()
    lista_usuarios = df_usuarios['login'].tolist() if not df_usuarios.empty else ["admin"]

    # --- VISÃO DO ADMINISTRADOR ---
    if st.session_state['perfil_usuario'] == 'Administrador':
        menu_admin = st.sidebar.radio(
            "Navegação:", 
            ["Painel de Prazos", "Pendente de Revisão", "Cadastrar Prazo/Diligência", "Cadastrar Processo", "Histórico de Processo", "Gerenciar Usuários"]
        )
        
        st.sidebar.divider()
        if st.sidebar.button("Sair / Logout"):
            st.session_state['usuario_logado'] = None
            st.session_state['perfil_usuario'] = None
            if 'modo_edicao' in st.session_state: del st.session_state['modo_edicao']
            st.rerun()

        # 1. PAINEL DE PRAZOS
        if menu_admin == "Painel de Prazos":
            st.header("Painel Geral de Prazos")
            
            if not df_prazos.empty:
                # --- SISTEMA DE FILTROS ---
                with st.expander("🔍 Filtros de Busca", expanded=True):
                    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                    with col_f1:
                        filtro_busca = st.text_input("Buscar Processo / Cliente / Tarefa:")
                    with col_f2:
                        filtro_resp = st.multiselect("Responsável:", options=lista_usuarios)
                    with col_f3:
                        filtro_status = st.multiselect("Status:", options=["Ativo", "Concluído", "Pendente de Revisão", "Arquivado"], default=["Ativo", "Pendente de Revisão"])
                    with col_f4:
                        filtro_urgente = st.multiselect("Urgente:", options=["Sim", "Não"])
                
                # Aplica os filtros na base de dados
                df_filtrado = df_prazos.copy()
                
                if filtro_busca:
                    df_filtrado = df_filtrado[
                        df_filtrado['processo'].astype(str).str.contains(filtro_busca, case=False, na=False) |
                        df_filtrado['nome_tarefa'].astype(str).str.contains(filtro_busca, case=False, na=False) |
                        df_filtrado['nome_cliente'].astype(str).str.contains(filtro_busca, case=False, na=False)
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

                # ---- MODO DE VISUALIZAÇÃO ----
                if not st.session_state['modo_edicao']:
                    st.write("Marque a caixa de seleção na primeira coluna para Excluir ou Editar um registro.")
                    
                    if df_prazos_ordenado.empty:
                        st.warning("Nenhuma tarefa encontrada com os filtros selecionados.")
                    else:
                        df_exibicao = formatar_tabela_exibicao(df_prazos_ordenado)
                        df_exibicao.insert(0, "Selecionar", False) 
                        
                        # Coluna nome_cliente adicionada à exibição principal
                        colunas_mostrar = ['Selecionar', 'id_prazo', 'nome_cliente', 'processo', 'orgao_ente', 'data_inicio', 'data_fim', 'responsavel', 'urgente', 'status']
                        
                        tabela_interativa = st.data_editor(
                            df_exibicao[colunas_mostrar],
                            hide_index=True,
                            disabled=['id_prazo', 'nome_cliente', 'processo', 'orgao_ente', 'data_inicio', 'data_fim', 'responsavel', 'urgente', 'status'],
                            use_container_width=True
                        )
                        
                        linhas_selecionadas = tabela_interativa[tabela_interativa['Selecionar'] == True]
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🗑️ EXCLUIR"):
                                if not linhas_selecionadas.empty:
                                    for index, row in linhas_selecionadas.iterrows():
                                        supabase.table('prazos').delete().eq('id_prazo', row['id_prazo']).execute()
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
                
                # ---- MODO DE EDIÇÃO ATIVO ----
                else:
                    st.subheader("✏️ Edição Rápida")
                    st.write("Altere os valores diretamente nas células da tabela abaixo e clique em Salvar.")
                    
                    id_alvo = st.session_state['id_editar']
                    df_editar = df_prazos[df_prazos['id_prazo'] == id_alvo].copy()
                    
                    # Coluna nome_cliente adicionada para edição
                    colunas_editaveis = ['nome_cliente', 'processo', 'nome_tarefa', 'orgao_ente', 'tarefa', 'data_inicio', 'data_fim', 'responsavel', 'urgente', 'status', 'vinculado']
                    
                    df_editado = st.data_editor(
                        df_editar[colunas_editaveis],
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "responsavel": st.column_config.SelectboxColumn("Responsável", options=lista_usuarios),
                            "status": st.column_config.SelectboxColumn("Status", options=["Ativo", "Concluído", "Pendente de Revisão", "Arquivado"]),
                            "urgente": st.column_config.SelectboxColumn("Urgente", options=["Sim", "Não"]),
                            "vinculado": st.column_config.SelectboxColumn("Vinculado", options=["Sim", "Não"])
                        }
                    )
                    
                    col_salvar, col_cancelar = st.columns(2)
                    with col_salvar:
                        if st.button("💾 SALVAR"):
                            linha_atualizada = df_editado.iloc[0]
                            dados_atualizados = linha_atualizada.to_dict()
                            
                            supabase.table('prazos').update(dados_atualizados).eq('id_prazo', id_alvo).execute()
                            
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
            else:
                st.info("Nenhum prazo cadastrado no sistema ainda.")

        # 2. PENDENTE DE REVISÃO
        elif menu_admin == "Pendente de Revisão":
            st.header("Aprovação de Tarefas")
            
            df_revisao = pd.DataFrame() if df_prazos.empty else df_prazos[df_prazos['status'] == 'Pendente de Revisão']
            
            if not df_revisao.empty:
                df_exibicao = formatar_tabela_exibicao(df_revisao)
                colunas_mostrar = ['id_prazo', 'nome_cliente', 'processo', 'orgao_ente', 'data_fim', 'responsavel', 'urgente']
                st.dataframe(df_exibicao[colunas_mostrar], use_container_width=True)
                
                st.divider()
                st.subheader("Revisar Tarefa")
                with st.form("form_revisao", clear_on_submit=True):
                    id_alvo = st.selectbox("Selecione o ID do Prazo para revisar:", df_revisao['id_prazo'].tolist())
                    decisao = st.radio("Ação:", ["Aprovar (Marcar como Concluído)", "Recusar (Devolver para Ativo)"])
                    submit_revisao = st.form_submit_button("Confirmar Revisão")
                    
                    if submit_revisao:
                        novo_status = "Concluído" if "Aprovar" in decisao else "Ativo"
                        supabase.table('prazos').update({'status': novo_status}).eq('id_prazo', id_alvo).execute()
                        st.success(f"✅ Tarefa atualizada para: {novo_status}!")
                        time.sleep(2)
                        st.rerun()
            else:
                st.success("Tudo limpo! Nenhuma tarefa aguardando revisão no momento.")

        # 3. CADASTRAR PRAZO
        elif menu_admin == "Cadastrar Prazo/Diligência":
            st.header("Cadastrar Novo Prazo / Diligência")
            
            with st.form("form_novo_prazo", clear_on_submit=True):
                # Novo campo obrigatório
                nome_cliente = st.text_input("Nome do Cliente (*Obrigatório):")
                
                processo = st.text_input("Número do Processo (Opcional se não for vincular):")
                vincular = st.checkbox("Vincular Tarefa/Prazo ao Processo")
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
                    # Nova validação incluindo o nome do cliente
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
                        st.success("✅ Tarefa cadastrada e atribuída com sucesso!")
                        time.sleep(2)
                        st.rerun()

        # 4. CADASTRAR PROCESSO
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

        # 5. HISTÓRICO DE PROCESSO
        elif menu_admin == "Histórico de Processo":
            st.header("🔍 Histórico e Busca de Processos")
            col_b1, col_b2 = st.columns(2)
            with col_b1: busca_numero = st.text_input("Buscar pelo Número do Processo:", help="Apenas números.")
            with col_b2: busca_cliente = st.text_input("Buscar pelo Nome do Cliente:")
                
            if st.button("PESQUISAR"):
                resultados = df_processos.copy()
                if not resultados.empty:
                    if busca_numero:
                        busca_numero_limpo = busca_numero.replace(".", "").replace("-", "")
                        resultados = resultados[resultados['numero'].astype(str).str.contains(busca_numero_limpo, case=False, na=False)]
                    if busca_cliente:
                        resultados = resultados[resultados['cliente'].astype(str).str.contains(busca_cliente, case=False, na=False)]
                
                if not busca_numero and not busca_cliente:
                    st.warning("Preencha pelo menos um dos campos para pesquisar.")
                elif resultados.empty:
                    st.info("Nenhum processo encontrado.")
                else:
                    st.success(f"Encontramos {len(resultados)} processo(s)!")
                    for index, row in resultados.iterrows():
                        with st.expander(f"📁 Processo: {row['numero']} | Cliente: {row['cliente']}", expanded=True):
                            st.write(f"**Tipo:** {row['tipo']}")
                            st.divider()
                            st.subheader("Tarefas Vinculadas")
                            if not df_prazos.empty:
                                prazos_vinc = df_prazos[
                                    (df_prazos['processo'].astype(str).str.contains(str(row['numero']), case=False, na=False)) |
                                    (df_prazos['processo'].astype(str).str.contains(str(row['cliente']), case=False, na=False))
                                ]
                                if not prazos_vinc.empty:
                                    df_exibicao_hist = formatar_tabela_exibicao(prazos_vinc)
                                    col_hist = ['nome_tarefa', 'responsavel', 'data_fim', 'status', 'urgente']
                                    st.dataframe(df_exibicao_hist[col_hist], use_container_width=True)
                                else:
                                    st.write("📝 *Nenhuma tarefa vinculada a este processo.*")

        # 6. GERENCIAR USUÁRIOS
        elif menu_admin == "Gerenciar Usuários":
            st.header("Cadastrar Novo Usuário")
            with st.form("form_novo_usuario", clear_on_submit=True):
                novo_login = st.text_input("Novo Login:")
                nova_senha = st.text_input("Nova Senha:", type="password")
                novo_perfil = st.selectbox("Perfil:", ["Usuário", "Administrador"])
                submit_user = st.form_submit_button("Criar Usuário")
                
                if submit_user:
                    if novo_login and nova_senha:
                        if not df_usuarios.empty and novo_login in df_usuarios['login'].values:
                            st.error("Este login já existe! Escolha outro.")
                        else:
                            supabase.table('usuarios').insert({'login': novo_login, 'senha': nova_senha, 'perfil': novo_perfil}).execute()
                            st.success(f"✅ Usuário '{novo_login}' criado com sucesso!")
                            time.sleep(2)
                            st.rerun()
                    else:
                        st.error("Preencha login e senha.")

    # --- VISÃO DO USUÁRIO COMUM ---
    else:
        menu_user = st.sidebar.radio("Navegação:", ["Meus Prazos Ativos", "Pendente de Revisão"])
        
        st.sidebar.divider()
        if st.sidebar.button("Sair / Logout"):
            st.session_state['usuario_logado'] = None
            st.session_state['perfil_usuario'] = None
            st.rerun()

        if menu_user == "Meus Prazos Ativos":
            st.header("Meus Prazos e Diligências")
            
            meus_prazos = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Ativo')]
            
            if not meus_prazos.empty:
                meus_prazos = meus_prazos.sort_values(by='data_fim')
                df_exibicao = formatar_tabela_exibicao(meus_prazos)
                colunas_mostrar = ['id_prazo', 'nome_cliente', 'processo', 'orgao_ente', 'data_inicio', 'data_fim', 'urgente']
                st.dataframe(df_exibicao[colunas_mostrar], use_container_width=True)
                
                st.divider()
                st.subheader("Entregar Tarefa / Diligência")
                with st.form("form_entregar", clear_on_submit=True):
                    tarefa_concluida = st.selectbox("Selecione o ID da tarefa que você finalizou:", meus_prazos['id_prazo'].tolist())
                    submit_entregar = st.form_submit_button("Enviar para Revisão do Administrador")
                    
                    if submit_entregar:
                        supabase.table('prazos').update({'status': 'Pendente de Revisão'}).eq('id_prazo', tarefa_concluida).execute()
                        st.success("✅ Tarefa enviada para revisão com sucesso!")
                        time.sleep(2)
                        st.rerun()
            else:
                st.success("Você não tem prazos ativos no momento. Bom trabalho!")

        elif menu_user == "Pendente de Revisão":
            st.header("Minhas Tarefas em Revisão")
            minhas_revisoes = pd.DataFrame() if df_prazos.empty else df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Pendente de Revisão')]
            
            if not minhas_revisoes.empty:
                df_exibicao = formatar_tabela_exibicao(minhas_revisoes)
                colunas_mostrar = ['id_prazo', 'nome_cliente', 'processo', 'data_fim', 'urgente']
                st.dataframe(df_exibicao[colunas_mostrar], use_container_width=True)
            else:
                st.info("Você não tem nenhuma tarefa aguardando revisão.")

# --- MOTOR DO APLICATIVO ---
if st.session_state['usuario_logado'] is None:
    tela_login()
else:
    tela_principal()
