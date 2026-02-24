import streamlit as st
import requests
import pandas as pd
import re
import io

# --- FUNÇÕES DE UTILIDADE ---
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
        "client_id": client_id, 
        "client_secret": client_secret,
        "grant_type": "client_credentials", 
        "scope": "authorization_api"
    }
    try:
        res = requests.post(url, data=data, timeout=15)
        return res.json().get("access_token") if res.status_code == 200 else None
    except:
        return None

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="WMS SKU Detail", layout="wide")
st.title("📦 Consulta Analítica de SKUs (Dimensões e Peso)")

with st.sidebar:
    st.header("🔑 Credenciais WMS")
    c_id = st.text_input("Client ID", type="password", key="wms_cid")
    c_secret = st.text_input("Client Secret", type="password", key="wms_sec")
    
    st.divider()
    
    st.header("📍 Localização")
    u_id = st.text_input("Unidade ID (UUID)", placeholder="Cole o ID da unidade aqui...", key="wms_uid")
    
    st.caption("🔒 Dados protegidos por sessão.")

# --- BOTÃO DE EXECUÇÃO ---
if st.button("🚀 Iniciar Extração de Dados"):
    if not all([c_id, c_secret, u_id]):
        st.error("⚠️ Preencha todos os campos na barra lateral.")
    else:
        token = gera_token_wms(c_id, c_secret)
        
        if not token:
            st.error("❌ Falha na autenticação. Verifique Client ID e Secret.")
        else:
            all_data = []
            page = 1
            progress_text = st.empty()
            
            API_SKUS = "https://supply.logistica.totvs.app/wms/query/api/v1/skus"

            with st.spinner("Buscando dados técnicos dos SKUs..."):
                while True:
                    params = {
                        "page": page, 
                        "pageSize": 500, 
                        "unidadeId": u_id.strip()
                    }
                    
                    try:
                        res = requests.get(API_SKUS, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=60)
                        
                        if res.status_code == 200:
                            data = res.json()
                            skus = data.get('items', [])
                            
                            if not skus:
                                break
                            
                            for sku in skus:
                                # Extração de Dimensões
                                dim = sku.get('dimensao') or {}
                                altura = dim.get('altura', 0)
                                largura = dim.get('largura', 0)
                                comprimento = dim.get('comprimento', 0)
                                
                                # Extração de Peso (Novo Campo)
                                peso = sku.get('peso', 0.0)
                                
                                # Dados do Produto Pai
                                prod = sku.get('produto') or {}
                                
                                all_data.append({
                                    'Código Produto': clean_text(prod.get('codigo')),
                                    'Descrição Comercial': clean_text(prod.get('descricaoComercial')),
                                    'Descrição SKU': clean_text(sku.get('descricao')),
                                    'Código de Barras': extract_codigo_barras(sku.get('codigosBarras')),
                                    'Situação': clean_text(sku.get('situacao')),
                                    'Peso (kg)': peso if peso is not None else 0.0,
                                    'Altura': altura if altura is not None else 0.0,
                                    'Largura': largura if largura is not None else 0.0,
                                    'Comprimento': comprimento if comprimento is not None else 0.0,
                                    'Fracionado': "Sim" if sku.get('fracionado') else "Não",
                                    'Qtd Unid. Internas': sku.get('quantidadeUnidadesProduto', 1)
                                })
                            
                            progress_text.info(f"⏳ Processando: {len(all_data)} SKUs (Página {page})...")
                            
                            if not data.get('hasNext'):
                                break
                            page += 1
                        else:
                            st.error(f"Erro na API de SKUs: {res.status_code}")
                            break
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                        break

            if all_data:
                progress_text.empty()
                df = pd.DataFrame(all_data)
                
                st.success(f"✅ Extração concluída! {len(all_data)} SKUs catalogados.")
                
                # Exibição dos dados na tela
                st.dataframe(df, use_container_width=True)
                
                # Preparação do arquivo Excel para download
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='SKUs_Detalhado')
                
                st.download_button(
                    label="📥 Baixar Planilha Técnica",
                    data=buf.getvalue(),
                    file_name="cadastro_tecnico_skus.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ Nenhum SKU encontrado para os critérios informados.")
