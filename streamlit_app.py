import streamlit as st
import requests
import pandas as pd
import re
import io

# 1. Funções de Limpeza (Internas para não depender de outros arquivos)
def clean_text(text):
    if isinstance(text, str):
        return re.sub(r'[^ -~]', '', text)
    return text

def extract_codigo_barras(codigos_barras):
    if isinstance(codigos_barras, list) and codigos_barras:
        primeiro = codigos_barras[0].get('codigoBarras', '') if isinstance(codigos_barras[0], dict) else ''
        return clean_text(primeiro)
    return ''

def gera_token_wms(client_id, client_secret):
    url = "https://supply.rac.totvs.app/totvs.rac/connect/token"
    data = {
        "client_id": client_id, "client_secret": client_secret,
        "grant_type": "client_credentials", "scope": "authorization_api"
    }
    try:
        res = requests.post(url, data=data, timeout=15)
        return res.json().get("access_token") if res.status_code == 200 else None
    except: return None

# 2. Interface Streamlit
st.set_page_config(page_title="WMS SKU Query", layout="wide")
st.title("📦 Consulta de Produtos WMS SaaS")

with st.sidebar:
    st.header("🔑 Credenciais WMS")
    c_id = st.text_input("Client ID", type="password")
    c_secret = st.text_input("Client Secret", type="password")
    u_id = st.text_input("Unidade ID", value="ac275b55-90f8-44b8-b8cb-bdcfca969526")

if st.button("🚀 Iniciar Consulta"):
    if not all([c_id, c_secret, u_id]):
        st.error("Preencha todos os campos na barra lateral.")
    else:
        token = gera_token_wms(c_id, c_secret)
        if not token:
            st.error("Falha na autenticação. Verifique Client ID e Secret.")
        else:
            all_data = []
            page = 1
            with st.spinner(f"Lendo dados..."):
                while True:
                    url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"
                    params = {"page": page, "pageSize": 500, "unidadeId": u_id}
                    res = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
                    
                    if res.status_code == 200:
                        items = res.json().get('items', [])
                        if not items: break
                        
                        for p in items:
                            c_lote = any('Lote' in c.get('descricao', '') for c in p.get('caracteristicas', []))
                            c_val = any('Data de Validade' in c.get('descricao', '') for c in p.get('caracteristicas', []))
                            for sku in p.get('skus', []):
                                all_data.append({
                                    'Código': clean_text(p.get('codigo')),
                                    'Descrição': clean_text(p.get('descricaoComercial')),
                                    'SKU': clean_text(sku.get('descricao')),
                                    'EAN': extract_codigo_barras(sku.get('codigosBarras')),
                                    'Lote': c_lote, 'Validade': c_val
                                })
                        if not res.json().get('hasNext'): break
                        page += 1
                    else: break

            if all_data:
                df = pd.DataFrame(all_data)
                st.success(f"{len(all_data)} SKUs encontrados.")
                st.dataframe(df, use_container_width=True)
                
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w:
                    df.to_excel(w, index=False)
                st.download_button("📥 Baixar Excel", buf.getvalue(), "produtos.xlsx")
