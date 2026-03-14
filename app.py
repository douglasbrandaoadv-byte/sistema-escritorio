import streamlit as st
import pandas as pd
import os

# --- CONFIGURAÇÕES DE ARQUIVOS (BANCOS DE DADOS SIMPLES) ---
ARQUIVO_USUARIOS = 'usuarios.csv'
ARQUIVO_PROCESSOS = 'processos.csv'
ARQUIVO_PRAZOS = 'prazos.csv'

# Função para garantir que os arquivos existam
def inicializar_banco():
    if not os.path.exists(ARQUIVO_USUARIOS):
        # Cria um usuário administrador padrão: login 'admin', senha 'admin'
        df_users = pd.DataFrame([{'login': 'admin', 'senha': 'admin', 'perfil': 'Administrador'}])
        df_users.to_csv(ARQUIVO_USUARIOS, index=False)
    
    if not os.path.exists(ARQUIVO_PROCESSOS):
        pd.DataFrame(columns=['id_processo', 'tipo', 'numero', 'cliente']).to_csv(ARQUIVO_PROCESSOS, index=False)
        
    if not os.path.exists(ARQUIVO_PRAZOS):
        pd.DataFrame(columns=['id_prazo', 'processo', 'diligencia', 'data_limite', 'responsavel', 'status']).to_csv(ARQUIVO_PRAZOS, index=False)

# Funções de Leitura e Gravação
def carregar_dados(arquivo):
    return pd.read_csv(arquivo)

def salvar_dados(df, arquivo):
    df.to_csv(arquivo, index=False)

# Inicializa os arquivos no primeiro carregamento
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
        # Verifica se existe um usuário com o login e senha informados
        usuario = df_users[(df_users['login'] == login_input) & (df_users['senha'] == senha_input)]
        
        if not usuario.empty:
            st.session_state['usuario_logado'] = usuario.iloc[0]['login']
            st.session_state['perfil_usuario'] = usuario.iloc[0]['perfil']
            st.rerun() # Atualiza a página para entrar no sistema
        else:
            st.error("Login ou senha incorretos.")

# --- TELA PRINCIPAL (APÓS LOGIN) ---
def tela_principal():
    st.sidebar.title(f"Bem-vindo, {st.session_state['usuario_logado']}")
    st.sidebar.write(f"Perfil: {st.session_state['perfil_usuario']}")
    
    if st.sidebar.button("Sair"):
        st.session_state['usuario_logado'] = None
        st.session_state['perfil_usuario'] = None
        st.rerun()

    # Carrega os dados para uso na tela
    df_processos = carregar_dados(ARQUIVO_PROCESSOS)
    df_prazos = carregar_dados(ARQUIVO_PRAZOS)
    df_usuarios = carregar_dados(ARQUIVO_USUARIOS)

    # --- VISÃO DO ADMINISTRADOR ---
    if st.session_state['perfil_usuario'] == 'Administrador':
        aba1, aba2, aba3, aba4 = st.tabs(["Painel de Prazos", "Cadastrar Prazo/Diligência", "Cadastrar Processo", "Gerenciar Usuários"])
        
        with aba1:
            st.header("Todos os Prazos")
            if not df_prazos.empty:
                st.dataframe(df_prazos)
                
                st.subheader("Redistribuir ou Arquivar Prazo")
                id_prazo_alvo = st.selectbox("Selecione o Prazo:", df_prazos['id_prazo'].tolist())
                novo_responsavel = st.selectbox("Novo Responsável:", df_usuarios['login'].tolist())
                novo_status = st.selectbox("Status:", ["Ativo", "Arquivado"])
                
                if st.button("Atualizar Prazo"):
                    # Atualiza a linha correspondente no banco de dados
                    df_prazos.loc[df_prazos['id_prazo'] == id_prazo_alvo, 'responsavel'] = novo_responsavel
                    df_prazos.loc[df_prazos['id_prazo'] == id_prazo_alvo, 'status'] = novo_status
                    salvar_dados(df_prazos, ARQUIVO_PRAZOS)
                    st.success("Prazo atualizado com sucesso!")
                    st.rerun()
            else:
                st.info("Nenhum prazo cadastrado.")

        with aba2:
            st.header("Novo Prazo / Diligência")
            if not df_processos.empty:
                processo_sel = st.selectbox("Vincular ao Processo:", df_processos['numero'].tolist())
                diligencia = st.text_input("Descrição da Diligência/Tarefa:")
                data_limite = st.date_input("Data Limite:")
                responsavel = st.selectbox("Atribuir ao Usuário:", df_usuarios['login'].tolist())
                
                if st.button("Salvar Prazo"):
                    novo_id = f"PZ-{len(df_prazos) + 1}"
                    novo_prazo = pd.DataFrame([{
                        'id_prazo': novo_id, 'processo': processo_sel, 
                        'diligencia': diligencia, 'data_limite': data_limite, 
                        'responsavel': responsavel, 'status': 'Ativo'
                    }])
                    df_prazos = pd.concat([df_prazos, novo_prazo], ignore_index=True)
                    salvar_dados(df_prazos, ARQUIVO_PRAZOS)
                    st.success("Prazo atribuído com sucesso!")
            else:
                st.warning("Cadastre um processo primeiro.")

        with aba3:
            st.header("Novo Processo")
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

        with aba4:
            st.header("Cadastrar Novo Usuário")
            novo_login = st.text_input("Novo Login:")
            nova_senha = st.text_input("Nova Senha:", type="password")
            novo_perfil = st.selectbox("Perfil:", ["Usuário", "Administrador"])
            
            if st.button("Criar Usuário"):
                if novo_login and nova_senha:
                    novo_user = pd.DataFrame([{'login': novo_login, 'senha': nova_senha, 'perfil': novo_perfil}])
                    df_usuarios = pd.concat([df_usuarios, novo_user], ignore_index=True)
                    salvar_dados(df_usuarios, ARQUIVO_USUARIOS)
                    st.success(f"Usuário {novo_login} criado!")
                else:
                    st.error("Preencha login e senha.")

    # --- VISÃO DO USUÁRIO COMUM ---
    else:
        st.header("Meus Prazos e Diligências")
        # Filtra os prazos para mostrar apenas os do usuário logado e que estejam ativos
        meus_prazos = df_prazos[(df_prazos['responsavel'] == st.session_state['usuario_logado']) & (df_prazos['status'] == 'Ativo')]
        
        if not meus_prazos.empty:
            st.dataframe(meus_prazos[['processo', 'diligencia', 'data_limite']])
        else:
            st.success("Você não tem prazos ativos no momento. Bom trabalho!")

# --- MOTOR DO APLICATIVO ---
# Decide qual tela mostrar com base no login
if st.session_state['usuario_logado'] is None:
    tela_login()
else:
    tela_principal()
