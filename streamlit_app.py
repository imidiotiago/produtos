import streamlit as st
import requests
import pandas as pd
import re
import io

# --- FUNÇÕES DE UTILIDADE ---
def clean_text(text):
    if text is None:
        return ""
    if isinstance(text, str):
        # Remove caracteres não imprimíveis (comum em integrações TOTVS)
        return re.sub(r'[^ -~]', '', text)
    return str(text)

def extract_codigo_barras(codigos_barras):
    if isinstance(codigos_barras, list) and codigos_barras:
        primeiro = codigos_barras[0]
        if isinstance(primeiro, dict):
            return clean_text(primeiro.get('codigoBarras', ''))
    return ''

# --- FUNÇÃO DE AUTENTICAÇÃO ---
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
            st.error(f"Erro na Autenticação: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Falha na conexão de autenticação: {e}")
        return None

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Consulta de Produtos WMS", layout="wide")
st.title("📦 Consulta de Cadastro de Produtos WMS")

with st.sidebar:
    st.header("🔑 Credenciais da Base")
    c_id = st.text_input("WMS Client ID", type="password")
    c_secret = st.text_input("WMS Client Secret", type="password")
    u_id = st.text_input("Unidade ID (UUID)", value="ac275b55-90f8-44b8-b8cb-bdcfca969526")
    st.divider()
    st.caption("Insira as credenciais para iniciar a busca.")

# --- PROCESSO DE CONSULTA ---
if st.button("🚀 Iniciar Consulta de Produtos"):
    if not all([c_id, c_secret, u_id]):
        st.warning("⚠️ Por favor, preencha todos os campos na barra lateral.")
    else:
        with st.status("Processando dados...", expanded=True) as status:
            st.write("Solicitando Token...")
            access_token = gera_token_dinamico(c_id, c_secret)

            if access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                all_data = []
                page = 1
                api_url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"

                while True:
                    st.write(f"Buscando Página {page}...")
                    params = {
                        "page": page,
                        "pageSize": 500,
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
                                # --- EXTRAÇÃO DA CATEGORIA (FORÇADA) ---
                                cat_obj = produto.get('categoriaProduto')
                                if isinstance(cat_obj, dict):
                                    # Puxa o campo 'descricao' conforme o seu payload
                                    nome_categoria = clean_text(cat_obj.get('descricao', 'NÃO INFORMADO'))
                                else:
                                    nome_categoria = 'SEM CATEGORIA'

                                # Características (Lote e Validade)
                                caracteristicas = produto.get('caracteristicas', [])
                                controla_lote = any('Lote' in str(c.get('descricao', '')) for c in caracteristicas)
                                controla_validade = any('Validade' in str(c.get('descricao', '')) for c in caracteristicas)
                                
                                unidade_medida = clean_text(produto.get('unidadeMedida', ''))
                                cod_produto = clean_text(produto.get('codigo', ''))
                                desc_comercial = clean_text(produto.get('descricaoComercial', ''))
                                
                                # Loop de SKUs
                                skus_list = produto.get('skus', [])
                                for sku in skus_list:
                                    if not isinstance(sku, dict): continue
                                    
                                    situacao_sku = clean_text(sku.get('situacao', sku.get('status', '')))
                                    desc_sku = clean_text(sku.get('descricao', ''))
                                    barras = extract_codigo_barras(sku.get('codigosBarras'))
                                    
                                    # Montagem da linha garantindo que a coluna 'Categoria' exista
                                    all_data.append({
                                        'Código': cod_produto,
                                        'Descrição': desc_comercial,
                                        'Categoria': nome_categoria, # <--- Campo adicionado
                                        'Unidade Medida': unidade_medida,
                                        'Descrição SKU': desc_sku,
                                        'Código de Barras': barras,
                                        'Situação SKU': situacao_sku,
                                        'Controla Lote': controla_lote,
                                        'Controla Validade': controla_validade
                                    })

                            if not data.get('hasNext'):
                                break
                            page += 1
                        else:
                            st.error(f"Erro na API (Pág {page}): {api_response.status_code}")
                            break
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                        break

                if all_data:
                    df = pd.DataFrame(all_data)
                    status.update(label="Consulta Finalizada!", state="complete", expanded=False)
                    
                    st.success(f"✅ {len(all_data)} SKUs processados!")
                    
                    # Exibição na tela
                    st.dataframe(df, use_container_width=True)

                    # Exportação para Excel
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 Baixar Planilha Excel",
                        data=buffer.getvalue(),
                        file_name=f"produtos_wms_completo.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    status.update(label="Nenhum dado encontrado.", state="error")
