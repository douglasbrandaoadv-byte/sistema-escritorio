import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÕES DE ARQUIVOS (BANCOS DE DADOS SIMPLES) ---
ARQUIVO_USUARIOS = 'usuarios.csv'
ARQUIVO_PROCESSOS = 'processos.csv'
ARQUIVO_PRAZOS = 'prazos.csv'

# Função para garantir que os arquivos existam com as colunas corretas
def inicializar_banco():
    if not os.path.exists(ARQUIVO_USUARIOS):
        df_users = pd.DataFrame([{'login': 'admin', 'senha': 'admin', 'perfil': 'Administrador'}])
        df_users.to_csv(ARQUIVO_USUARIOS, index=False)
    
    if not os.path.exists(ARQUIVO_PROCESSOS):
        pd.DataFrame(columns=['id_processo', 'tipo', 'numero', 'cliente']).to_csv(ARQUIVO_PROCESSOS, index=False)
        
    if not os.path.exists(ARQUIVO_PRAZOS):
        # Atualizado com as novas colunas solicitadas
        pd.DataFrame(columns=[
            'id_prazo', 'processo', 'orgao_ente', 'tarefa', 
            'data_inicio', 'data_fim', 'responsavel', 'urgente', 'status'
        ]).to_csv(ARQUIVO_PRAZOS, index=False)

def carregar_dados(arquivo):
    return pd.read_csv(arquivo)

def salvar_dados(df, arquivo):
    df.to_csv(arquivo, index=False)

inicializar_banco()

# --- CONTROLE DE SESSÃO (LOGIN) ---
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None
if 'perfil_usuario' not in st.session_state:
    st.session_state['perfil_usuario'] = None

# --- TELA DE LOGIN ---
def tela_login():
    st.title("⚖️ Sistema de Gestão Jurídica")
    st.subheader("Acesso ao Sistema")
    
    login_input = st.text_input("Login")
    senha_input = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        df_users = carregar_dados(ARQUIVO_USUARIOS)
        usuario = df_users[(df_users['login'] == login_input) & (df_users['senha'] == senha_input)]
        
        if not usuario.empty:
            st.session_state['usuario_logado'] = usuario.iloc[0]['login']
            st.session_state['perfil_usuario'] = usuario.iloc[0]['perfil']
            st.rerun()
        else:
            st.error("Login ou senha incorretos.")

# --- TELA PRINCIPAL (APÓS LOGIN) ---
def tela_principal():
    # Menu Lateral (Sidebar)
    st.sidebar.title(f"Bem-vindo, {st.session_state['usuario_logado']}")
    st.sidebar.caption(f"Perfil: {st.session_state['perfil_usuario']}")
    st.sidebar.divider()

    df_processos = carregar_dados(ARQUIVO_PROCESSOS)
    df_prazos = carregar_dados(ARQUIVO_PRAZOS)
    df_usuarios = carregar_dados(ARQUIVO_USUARIOS)

    # --- VISÃO DO ADMINISTRADOR ---
    if st.session_state['perfil_usuario'] == 'Administrador':
        # Transformando as abas em Menu Lateral
        menu_admin = st.sidebar.radio(
            "Navegação:", 
            ["Painel de Prazos", "Cadastrar Prazo/Diligência", "Cadastrar Processo", "Gerenciar Usuários"]
        )
        
        st.sidebar.divider()
        if st.sidebar.button("Sair / Logout"):
            st.session_state['usuario_logado'] = None
            st.session_state['perfil_usuario'] = None
            st.rerun()

        # 1. TELA: PAINEL DE PRAZOS
        if menu_admin == "Painel de Prazos":
            st.header("Painel Geral de Prazos")
            if not df_prazos.empty:
                # Mostra a tabela com os dados
                st.dataframe(df_prazos, use_container_width=True)
                
                st.divider()
                st.subheader("Ações: Redistribuir ou Arquivar")
                id_prazo_alvo = st.selectbox("Selecione o ID do Prazo:", df_prazos['id_prazo'].tolist())
                novo_responsavel = st.selectbox("Novo Responsável:", df_usuarios['login'].tolist())
                novo_status = st.selectbox("Status:", ["Ativo", "Arquivado"])
                
                if st.button("Atualizar Prazo"):
                    df_prazos.loc[df_prazos['id_prazo'] == id_prazo_alvo, 'responsavel'] = novo_responsavel
                    df_prazos.loc[df_prazos['id_prazo'] == id_prazo_alvo, 'status'] = novo_status
                    salvar_dados(df_prazos, ARQUIVO_PRAZOS)
                    st.success("Prazo atualizado com sucesso!")
                    st.rerun()
            else:
                st.info("Nenhum prazo cadastrado no sistema ainda.")

        # 2. TELA: CADASTRAR PRAZO/DILIGÊNCIA (Totalmente Reformulada)
        elif menu_admin == "Cadastrar Prazo/Diligência":
            st.header("Cadastrar Novo Prazo / Diligência")
            
            # Novos campos solicitados
            processo = st.text_input("Nome ou Número do Processo:")
            orgao = st.text_input("Órgão / Ente (Ex: 1ª Vara Cível, INSS, etc.):")
            tarefa = st.text_area("Descrição da Tarefa / Diligência:")
            
            # Colocando as datas lado a lado para economizar espaço
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("Data de Início da Tarefa:")
            with col2:
                data_fim = st.date_input("Data Final / Prazo Fatal:")
                
            responsavel = st.selectbox("Atribuir Tarefa ao Usuário:", df_usuarios['login'].tolist())
            
            urgente = st.checkbox("🚨 URGENTE")
            
            # Botão CADASTRAR
            if st.button("CADASTRAR"):
                # Validação simples para não salvar vazio
                if processo == "" or tarefa == "":
                    st.error("Por favor, preencha pelo menos o Processo e a Tarefa antes de cadastrar.")
                else:
                    novo_id = f"PZ-{len(df_prazos) + 1}"
                    # Cria a nova linha com os dados preenchidos
                    novo_prazo = pd.DataFrame([{
                        'id_prazo': novo_id, 
                        'processo': processo, 
                        'orgao_ente': orgao,
                        'tarefa': tarefa, 
                        'data_inicio': data_inicio, 
                        'data_fim': data_fim, 
                        'responsavel': responsavel, 
                        'urgente': "Sim" if urgente else "Não",
                        'status': 'Ativo'
                    }])
                    # Junta com a tabela existente e salva
                    df_prazos = pd.concat([df_prazos, novo_prazo], ignore_index=True)
                    salvar_dados(df_prazos, ARQUIVO_PRAZOS)
                    st.success("✅ Tarefa cadastrada e atribuída com sucesso!")

        # 3. TELA: CADASTRAR PROCESSO
        elif menu_admin == "Cadastrar Processo":
            st.header("Cadastrar Novo Processo")
            tipo_proc = st.selectbox("Tipo:", ["Judicial", "Extrajudicial"])
            num_proc = st.text_input("Número do Processo / Identificador:")
            cliente = st.text_input("Nome do Cliente:")
            
            if st.button("Salvar Processo"):
                if num_proc and cliente:
                    novo_id = f"PR-{len(df_processos) + 1}"
                    novo_proc = pd.DataFrame([{'id_processo': novo_id, 'tipo': tipo_proc, 'numero': num_proc, 'cliente': cliente}])
                    df_processos = pd.concat([df_processos, novo_proc], ignore_index=True)
                    salvar_dados(df_processos, ARQUIVO_PROCESSOS)
                    st.success("Processo cadastrado!")
                else:
                    st.error("Preencha todos os campos.")

        # 4. TELA: GERENCIAR USUÁRIOS
        elif menu_admin == "Gerenciar Usuários":
            st.header("Cadastrar Novo Usuário")
            novo_login = st.text_input("Novo Login:")
            nova_senha = st.text_input("Nova Senha:", type="password")
            novo_perfil = st.selectbox("Perfil:", ["Usuário", "Administrador"])
            
            if st.button("Criar Usuário"):
                if novo_login and nova_senha:
                    # Verifica se o login já existe
                    if novo_login in df_usuarios['login'].values:
                        st.error("Este login já existe! Escolha outro.")
                    else:
                        novo_user = pd.DataFrame([{'login': novo_login, 'senha': nova_senha, 'perfil': novo_perfil}])
                        df_usuarios = pd.concat([df_usuarios, novo_user], ignore_index=True)
                        salvar_dados(df_usuarios, ARQUIVO_USUARIOS)
                        st.success(f"Usuário '{novo_login}' criado com sucesso!")
                else:
                    st.error("Preencha login e senha.")

    # --- VISÃO DO USUÁRIO COMUM ---
    else:
        st.sidebar.divider()
        if st.sidebar.button("Sair / Logout"):
            st.session_state['usuario_logado'] = None
            st.session_state['perfil_usuario'] = None
            st.rerun()

        st.header("Meus Prazos e Diligências")
        
        # Filtra os prazos para mostrar apenas os do usuário logado e que estejam ativos
        meus_prazos = df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Ativo')]
        
        if not meus_prazos.empty:
            # Reorganiza a tabela para exibir de forma limpa para o usuário
            tabela_exibicao = meus_prazos[['processo', 'orgao_ente', 'tarefa', 'data_inicio', 'data_fim', 'urgente']]
            st.dataframe(tabela_exibicao, use_container_width=True)
        else:
            st.success("Você não tem prazos ativos no momento. Bom trabalho!")

# --- MOTOR DO APLICATIVO ---
if st.session_state['usuario_logado'] is None:
    tela_login()
else:
    tela_principal()
