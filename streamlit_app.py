import streamlit as st
import requests
import pandas as pd
import re
import io

# --- FUNÇÕES DE LIMPEZA E EXTRAÇÃO ---
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
st.set_page_config(page_title="WMS SKU Query", layout="wide")
st.title("📦 Consulta de Produtos WMS")

with st.sidebar:
    st.header("🔑 Credenciais WMS")
    # Campos protegidos para as chaves
    c_id = st.text_input("Client ID", type="password", key="wms_cid")
    c_secret = st.text_input("Client Secret", type="password", key="wms_sec")
    
    st.divider()
    
    st.header("📍 Localização")
    # NOVO: Campo para informar o ID da Unidade/Depósito
    u_id = st.text_input("Unidade ID (UUID)", placeholder="Cole o ID da unidade aqui...", key="wms_uid")
    
    st.caption("🔒 Os dados inseridos ficam salvos apenas nesta sessão do navegador.")

# --- BOTÃO DE EXECUÇÃO ---
if st.button("🚀 Iniciar Consulta de SKUs"):
    if not all([c_id, c_secret, u_id]):
        st.error("⚠️ Por favor, preencha o Client ID, Client Secret e o Unidade ID na barra lateral.")
    else:
        token = gera_token_wms(c_id, c_secret)
        
        if not token:
            st.error("❌ Falha na autenticação. Verifique se o Client ID e Secret estão corretos.")
        else:
            all_data = []
            page = 1
            progress_text = st.empty() # Espaço para o contador de progresso
            
            with st.spinner("Conectando à API e coletando dados..."):
                while True:
                    url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"
                    params = {
                        "page": page, 
                        "pageSize": 500, 
                        "unidadeId": u_id.strip()
                    }
                    
                    try:
                        res = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=60)
                        
                        if res.status_code == 200:
                            data = res.json()
                            items = data.get('items', [])
                            
                            if not items:
                                break
                            
                            for p in items:
                                # Verifica controle de lote e validade
                                c_lote = any('Lote' in c.get('descricao', '') for c in p.get('caracteristicas', []))
                                c_val = any('Data de Validade' in c.get('descricao', '') for c in p.get('caracteristicas', []))
                                
                                for sku in p.get('skus', []):
                                    all_data.append({
                                        'Código': clean_text(p.get('codigo')),
                                        'Descrição': clean_text(p.get('descricaoComercial')),
                                        'Unidade Medida': clean_text(p.get('unidadeMedida', '')),
                                        'SKU': clean_text(sku.get('descricao')),
                                        'EAN': extract_codigo_barras(sku.get('codigosBarras')),
                                        'Situação': clean_text(sku.get('situacao', sku.get('status', ''))),
                                        'Lote': "Sim" if c_lote else "Não",
                                        'Validade': "Sim" if c_val else "Não"
                                    })
                            
                            # Atualiza o contador na tela
                            progress_text.info(f"⏳ Processando: {len(all_data)} SKUs encontrados até agora (Página {page})...")
                            
                            if not data.get('hasNext'):
                                break
                            page += 1
                        else:
                            st.error(f"Erro na API (Página {page}): Status {res.status_code}")
                            break
                    except Exception as e:
                        st.error(f"Erro de conexão: {e}")
                        break

            if all_data:
                progress_text.empty() # Limpa o texto de progresso
                df = pd.DataFrame(all_data)
                
                st.success(f"✅ Consulta finalizada! Total de {len(all_data)} SKUs processados.")
                
                # Exibe a tabela na tela
                st.dataframe(df, use_container_width=True)
                
                # Gerar Excel para download
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 Baixar Planilha de Produtos (Excel)",
                    data=buf.getvalue(),
                    file_name=f"produtos_wms_unidade_{u_id[:8]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ Nenhum produto encontrado para esta Unidade ID.")
