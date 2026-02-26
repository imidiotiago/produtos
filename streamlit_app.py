import streamlit as st
import requests
import pandas as pd
import re
import io

# --- UTILITÁRIOS ---
def clean_text(text):
    if text is None: return ""
    return re.sub(r'[^ -~]', '', str(text))

def extract_codigo_barras(codigos_barras):
    if isinstance(codigos_barras, list) and codigos_barras:
        item = codigos_barras[0]
        return clean_text(item.get('codigoBarras', '')) if isinstance(item, dict) else ''
    return ''

def gera_token_dinamico(client_id, client_secret):
    AUTH_URL = "https://supply.rac.totvs.app/totvs.rac/connect/token"
    try:
        r = requests.post(AUTH_URL, data={
            "client_id": client_id, "client_secret": client_secret,
            "grant_type": "client_credentials", "scope": "authorization_api"
        }, timeout=15)
        return r.json().get("access_token")
    except: return None

# --- UI ---
st.set_page_config(page_title="WMS Debug", layout="wide")
st.title("📦 Consulta WMS - Teste de Categoria")

with st.sidebar:
    c_id = st.text_input("Client ID", type="password")
    c_secret = st.text_input("Client Secret", type="password")
    u_id = st.text_input("Unidade ID", value="ac275b55-90f8-44b8-b8cb-bdcfca969526")

if st.button("🚀 Executar e Depurar"):
    token = gera_token_dinamico(c_id, c_secret)
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        api_url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"
        params = {"page": 1, "pageSize": 10, "unidadeId": u_id}
        
        res = requests.get(api_url, params=params, headers=headers)
        if res.status_code == 200:
            data = res.json()
            items = data.get('items', [])
            
            if items:
                # --- ÁREA DE DEBUG (PARA VOCÊ VER O QUE ESTÁ ACONTECENDO) ---
                st.subheader("🔍 Diagnóstico do Primeiro Item")
                primeiro_p = items[0]
                cat_bruta = primeiro_p.get('categoriaProduto')
                
                col1, col2 = st.columns(2)
                col1.write("**O que veio no campo 'categoriaProduto':**")
                col1.json(cat_bruta)
                
                # --- PROCESSAMENTO ---
                all_rows = []
                for p in items:
                    # Tenta pegar a descrição de 3 formas diferentes por segurança
                    cat_obj = p.get('categoriaProduto') or {}
                    
                    # 1. Tenta p['categoriaProduto']['descricao']
                    # 2. Se falhar, tenta p['categoriaProduto'] (caso a API mude e mande string)
                    # 3. Se falhar, põe "Vazio na API"
                    if isinstance(cat_obj, dict):
                        desc_final = cat_obj.get('descricao', 'Sem Descrição no Objeto')
                    else:
                        desc_final = str(cat_obj) if cat_obj else "Nulo"

                    for sku in p.get('skus', []):
                        all_rows.append({
                            "Código": p.get('codigo'),
                            "Produto": p.get('descricaoComercial'),
                            "CATEGORIA_TESTE": desc_final, # Coluna que estamos caçando
                            "SKU": sku.get('descricao')
                        })
                
                st.subheader("📊 Resultado da Tabela")
                st.table(all_rows)
            else:
                st.warning("Nenhum produto retornado.")
        else:
            st.error(f"Erro na API: {res.status_code}")
