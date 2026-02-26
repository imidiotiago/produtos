import streamlit as st
import requests
import pandas as pd
import re
import io

def clean_text(text):
    if isinstance(text, str):
        return re.sub(r'[^ -~]', '', text)
    return text

def extract_codigo_barras(codigos_barras):
    if isinstance(codigos_barras, list) and codigos_barras:
        primeiro_codigo = codigos_barras[0].get('codigoBarras', '') if isinstance(codigos_barras[0], dict) else ''
        return clean_text(primeiro_codigo)
    return ''

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
        return response.json().get("access_token") if response.status_code == 200 else None
    except:
        return None

st.set_page_config(page_title="Consulta WMS", layout="wide")
st.title("📦 Consulta de Cadastro de Produtos WMS")

with st.sidebar:
    c_id = st.text_input("WMS Client ID", type="password")
    c_secret = st.text_input("WMS Client Secret", type="password")
    u_id = st.text_input("Unidade ID (UUID)", value="ac275b55-90f8-44b8-b8cb-bdcfca969526")

if st.button("🚀 Iniciar Consulta"):
    if not all([c_id, c_secret, u_id]):
        st.warning("Preencha as credenciais.")
    else:
        with st.status("Processando...", expanded=True) as status:
            access_token = gera_token_dinamico(c_id, c_secret)
            if access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                all_data = []
                page = 1
                api_url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"

                while True:
                    params = {"page": page, "pageSize": 500, "unidadeId": u_id}
                    api_response = requests.get(api_url, params=params, headers=headers, timeout=60)
                    
                    if api_response.status_code == 200:
                        data = api_response.json()
                        produtos = data.get('items', [])
                        if not produtos: break

                        for p in produtos:
                            # EXTRAÇÃO DIRETA DA CATEGORIA
                            cat_obj = p.get('categoriaProduto')
                            nome_categoria = clean_text(cat_obj.get('descricao')) if (cat_obj and isinstance(cat_obj, dict)) else "SEM CATEGORIA"
                            
                            # Características
                            c_lote = any('Lote' in str(c.get('descricao')) for c in p.get('caracteristicas', []))
                            c_val = any('Validade' in str(c.get('descricao')) for c in p.get('caracteristicas', []))
                            
                            for sku in p.get('skus', []):
                                if not isinstance(sku, dict): continue
                                all_data.append({
                                    'Código': clean_text(p.get('codigo')),
                                    'Descrição': clean_text(p.get('descricaoComercial')),
                                    'Categoria': nome_categoria, # <--- Mapeado diretamente do campo 'descricao' do JSON
                                    'Unidade Medida': clean_text(p.get('unidadeMedida')),
                                    'Descrição SKU': clean_text(sku.get('descricao')),
                                    'Código de Barras': extract_codigo_barras(sku.get('codigosBarras')),
                                    'Situação': clean_text(sku.get('situacao')),
                                    'Lote': c_lote,
                                    'Validade': c_val
                                })

                        if not data.get('hasNext'): break
                        page += 1
                    else: break

                if all_data:
                    df = pd.DataFrame(all_data)
                    status.update(label="Consulta Finalizada!", state="complete")
                    st.dataframe(df, use_container_width=True)
                    
                    # Gerar Excel
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="produtos_wms.xlsx")
