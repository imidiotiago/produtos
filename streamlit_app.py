import streamlit as st
import requests
import pandas as pd
import re
import io

# --- FUNÇÕES DE UTILIDADE (SUAS FUNÇÕES ORIGINAIS) ---
def clean_text(text):
    if isinstance(text, str):
        return re.sub(r'[^ -~]', '', text)
    return text

def extract_codigo_barras(codigos_barras):
    if isinstance(codigos_barras, list) and codigos_barras:
        primeiro_codigo = codigos_barras[0].get('codigoBarras', '') if isinstance(codigos_barras[0], dict) else ''
        return clean_text(primeiro_codigo)
    return ''

# --- FUNÇÃO PARA GERAR TOKEN DINAMICAMENTE ---
def gera_token_dinamico(client_id, client_secret):
    AUTH_URL = "https://supply.rac.totvs.app/totvs.rac/connect/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "authorization_api"
    }
    try:
        response = requests.post(AUTH_URL, data=token_data, timeout=15)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            st.error(f"Erro na Autenticação: {response.status_code} - Verifique Client ID e Secret")
            return None
    except Exception as e:
        st.error(f"Falha na conexão de autenticação: {e}")
        return None

# --- CONFIGURAÇÃO DA INTERFACE STREAMLIT ---
st.set_page_config(page_title="Consulta de Produtos WMS", layout="wide")
st.title("📦 Consulta de Cadastro de Produtos WMS")

# BARRA LATERAL PARA CREDENCIAIS
with st.sidebar:
    st.header("🔑 Credenciais da Base")
    c_id = st.text_input("WMS Client ID", type="password")
    c_secret = st.text_input("WMS Client Secret", type="password")
    u_id = st.text_input("Unidade ID (UUID)", value="ac275b55-90f8-44b8-b8cb-bdcfca969526")
    
    st.divider()
    st.caption("Insira as credenciais da base que deseja consultar.")

# --- PROCESSO DE CONSULTA ---
if st.button("🚀 Iniciar Consulta de Produtos"):
    if not all([c_id, c_secret, u_id]):
        st.warning("⚠️ Por favor, preencha o Client ID, Secret e Unidade ID na barra lateral.")
    else:
        with st.status("Executando consulta...", expanded=True) as status:
            st.write("Solicitando Token de Acesso...")
            access_token = gera_token_dinamico(c_id, c_secret)

            if access_token:
                st.write("Token obtido. Iniciando paginação...")
                headers = {"Authorization": f"Bearer {access_token}"}
                all_data = []
                page = 1
                api_url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"

                while True:
                    st.write(f"Buscando Página {page}...")
                    params = {
                        "page": page,
                        "pageSize": 500, # Reduzido para maior estabilidade na web
                        "unidadeId": u_id
                    }
                    
                    try:
                        api_response = requests.get(api_url, params=params, headers=headers, timeout=60)
                        if api_response.status_code == 200:
                            data = api_response.json()
                            produtos = data.get('items', [])
                            
                            if not produtos:
                                break

                            for produto in produtos:
                                controla_lote = any('Lote' in c.get('descricao', '') for c in produto.get('caracteristicas', []))
                                controla_data_validade = any('Data de Validade' in c.get('descricao', '') for c in produto.get('caracteristicas', []))
                                unidade_medida_principal = clean_text(produto.get('unidadeMedida', ''))
                                
                                skus_list = produto.get('skus', [])
                                for sku in skus_list:
                                    if not isinstance(sku, dict): continue
                                    
                                    situacao_sku = clean_text(sku.get('situacao', sku.get('status', '')))
                                    
                                    all_data.append({
                                        'Código': clean_text(produto.get('codigo')),
                                        'Descrição': clean_text(produto.get('descricaoComercial')),
                                        'Unidade Medida': unidade_medida_principal,
                                        'Descrição SKU': clean_text(sku.get('descricao', '')),
                                        'Código de Barras': extract_codigo_barras(sku.get('codigosBarras')),
                                        'Situação SKU': situacao_sku,
                                        'Controla Lote': controla_lote,
                                        'Controla Validade': controla_data_validade
                                    })

                            if not data.get('hasNext'):
                                break
                            page += 1
                        else:
                            st.error(f"Erro na API na página {page}: {api_response.status_code}")
                            break
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                        break

                if all_data:
                    df = pd.DataFrame(all_data)
                    status.update(label="Consulta Finalizada!", state="complete", expanded=False)
                    
                    st.success(f"✅ {len(all_data)} SKUs encontrados!")
                    
                    # Mostrar prévia
                    st.dataframe(df, use_container_width=True)

                    # Botão de Download
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 Baixar Lista de Produtos (Excel)",
                        data=buffer.getvalue(),
                        file_name=f"produtos_wms_{u_id[:8]}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    status.update(label="Nenhum dado encontrado.", state="error")
