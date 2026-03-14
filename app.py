import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Nome do nosso arquivo que servirá de banco de dados
ARQUIVO_DADOS = 'dados_escritorio.csv'

# Função para ler o banco de dados
def carregar_dados():
    # Se o arquivo já existir, ele lê as informações
    if os.path.exists(ARQUIVO_DADOS):
        return pd.read_csv(ARQUIVO_DADOS)
    # Se não existir (primeiro acesso), ele cria as colunas vazias
    else:
        return pd.DataFrame(columns=['Data e Hora', 'Condomínio', 'Tipo', 'Descrição'])

# Função para salvar as novas informações no banco de dados
def salvar_dados(planilha):
    planilha.to_csv(ARQUIVO_DADOS, index=False)

# --- COMEÇO DA TELA DO SISTEMA ---

st.title("Sistema do Escritório 🏢")
st.write("Preencha os dados abaixo para registrar uma nova ação e salvar no banco de dados.")

st.subheader("Nova Ocorrência")

# Nossas caixas de preenchimento
condominio = st.selectbox("Selecione o Condomínio:", ["Edifício Villa Imperial", "Residencial Jardins", "Outro"])
tipo = st.selectbox("Tipo de Ação:", ["Notificação", "Manutenção", "Contrato", "Reunião"])
descricao = st.text_area("Descrição detalhada da ocorrência:")

# O que acontece quando clica no botão Salvar
if st.button("Salvar Registro"):
    if descricao == "":
        st.error("Por favor, preencha a descrição antes de salvar!")
    else:
        # Pega a data e hora do momento do clique
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Cria a "linha" com os dados novos
        novo_registro = pd.DataFrame([{
            'Data e Hora': data_atual,
            'Condomínio': condominio,
            'Tipo': tipo,
            'Descrição': descricao
        }])
        
        # Carrega a planilha antiga, junta com a linha nova e salva tudo
        planilha_atual = carregar_dados()
        planilha_atualizada = pd.concat([planilha_atual, novo_registro], ignore_index=True)
        salvar_dados(planilha_atualizada)
        
        st.success("✅ Registro salvo com sucesso e armazenado na base de dados!")

st.divider() # Cria uma linha separadora na tela

# --- MOSTRAR OS DADOS SALVOS ---
st.subheader("📂 Registros Salvos (Banco de Dados)")

# Carrega e exibe a tabela atualizada
dados_para_mostrar = carregar_dados()

if not dados_para_mostrar.empty:
    st.dataframe(dados_para_mostrar, use_container_width=True)
else:
    st.info("Nenhum registro encontrado. A base de dados está vazia.")
