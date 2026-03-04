import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client, Client

# 1. PRIMEIRO COMANDO DO STREAMLIT (Obrigatório)
st.set_page_config(page_title="Projeções Financeiras - Visol", layout="wide")

# --- SETUP DE CONEXÃO COM BANCO DE DADOS ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

@st.cache_data(ttl=60) # Cache de 60 segundos para performance
def carregar_cenario_padrao():
    try:
        # Busca a linha onde is_default é verdadeiro
        response = supabase.table("cenarios_visol").select("*").eq("is_default", True).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        st.error(f"Erro de conexão com o banco: {e}")
    return None

# --- TELA DE LOGIN (BARREIRA DE SEGURANÇA) ---
def check_password():
    """Retorna True se o usuário inseriu uma senha válida e define o nível de acesso."""
    def password_entered():
        senha_digitada = st.session_state["password"]
        
        # Verifica se é o Admin (Você)
        if senha_digitada == st.secrets["senha_visol"]:
            st.session_state["password_correct"] = True
            st.session_state["role"] = "admin"
            del st.session_state["password"]
            
        # Verifica se é o Investidor
        elif "senha_investidor" in st.secrets and senha_digitada == st.secrets["senha_investidor"]:
            st.session_state["password_correct"] = True
            st.session_state["role"] = "investor"
            del st.session_state["password"]
            
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔑 Digite a senha de acesso (Data Room Visol):", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔑 Digite a senha de acesso (Data Room Visol):", type="password", on_change=password_entered, key="password")
        st.error("Senha incorreta. Tente novamente.")
        return False
    return True

if not check_password():
    st.stop()

# Define a variável global de permissão
is_admin = st.session_state.get("role") == "admin"

# Se for investidor, injeta CSS para esconder a barra lateral completamente
if not is_admin:
    st.markdown("""
        <style>
            [data-testid="collapsedControl"] {display: none;}
            [data-testid="stSidebar"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# O RESTANTE DO CÓDIGO SÓ RODA SE A SENHA ESTIVER CORRETA
# ==========================================

cenario_db = carregar_cenario_padrao()

# Se o banco falhar, usa os valores hardcoded. Se funcionar, usa os do banco.
def_meses = cenario_db["meses_projecao"] if cenario_db else 36
def_caixa = float(cenario_db["caixa_inicial"]) if cenario_db else 8200.0
def_clientes = cenario_db["clientes_iniciais"] if cenario_db else 77
def_ticket = float(cenario_db["ticket_medio"]) if cenario_db else 300.0
def_crescimento = float(cenario_db["crescimento_vendas"]) if cenario_db else 0.10
def_churn = float(cenario_db["churn_mensal"]) if cenario_db else 0.02
def_inflacao_cac = float(cenario_db["inflacao_cac"]) if cenario_db else 0.05
def_aporte = float(cenario_db["aporte_valor"]) if cenario_db else 500000.0
def_mes_aporte = cenario_db["mes_aporte"] if cenario_db else 6


# --- FUNÇÕES DE FORMATAÇÃO BRASILEIRA ---
def format_br(valor, decimais=2):
    """Formata números para o padrão brasileiro (ex: 1.234.567,89)"""
    if pd.isna(valor):
        return ""
    formato = f"{{:,.{decimais}f}}"
    valor_str = formato.format(valor)
    return "R$ " + valor_str.replace(",", "X").replace(".", ",").replace("X", ".")

def format_pct_br(valor, decimais=1):
    """Formata percentuais para o padrão brasileiro (ex: 1,5%)"""
    if pd.isna(valor):
        return ""
    return f"{valor*100:.{decimais}f}%".replace(".", ",")

# --- CONFIGURAÇÃO DA PÁGINA ---

st.title("📊 Visol - Projeções Financeiras e KPIs SaaS")

# --- PARÂMETROS BASE ---
clientes_iniciais = 77
mrr_inicial = 11550
caixa_inicial = 8200 
fomento_faperj = 29400  
parcela_emprestimo = 1365
meses_restantes_emprestimo = 18 

# --- DEFINIÇÃO DOS CENÁRIOS ---
cenarios = {
    "Pessimista (Atual)": {
        "vendas_mes": 4, "arpa_novo": 150, "churn_rate": 0.01, "ticket_implementacao": 750, 
        "add_mkt": 0, "add_vendas": 0, "add_outros": 0
    },
    "Realista (Foco Premium)": {
        "vendas_mes": 12, "arpa_novo": 200, "churn_rate": 0.01, "ticket_implementacao": 750, 
        "add_mkt": 1500, "add_vendas": 0, "add_outros": 0
    },
    "Otimista (Premium + Chat)": {
        "vendas_mes": 20, "arpa_novo": 250, "churn_rate": 0.01, "ticket_implementacao": 750, 
        "add_mkt": 1500, "add_vendas": 1800, "add_outros": 3000
    }
}

# --- INTERFACE LATERAL (SIDEBAR) ---
st.sidebar.header("1. Configurações de Simulação")
cenario_selecionado = st.sidebar.selectbox("Selecione o Cenário", list(cenarios.keys()))
meses_projecao = st.sidebar.slider("Meses de Projeção", 6, 60, value=def_meses)

st.sidebar.markdown("---")
st.sidebar.header("2. Produtos Adicionais (Cross-sell)")
incluir_addon = st.sidebar.checkbox("Habilitar Produto Adicional", value=True)

if incluir_addon:
    num_addons = st.sidebar.number_input("Quantidade de Produtos", min_value=1, max_value=5, value=1)
    lista_addons = []
    for i in range(num_addons):
        st.sidebar.markdown(f"**Produto {i+1}**")
        nome = st.sidebar.text_input(f"Nome", f"Produto {i+1}", key=f"nome_{i}")
        preco = st.sidebar.number_input(f"Preço por Cliente (R$)", value=50.0, step=10.0, key=f"preco_{i}")
        attach = st.sidebar.slider(f"Attach Rate (%)", 0, 100, 20, key=f"attach_{i}") / 100.0
        mes_inicio = st.sidebar.number_input(f"Mês de Lançamento", min_value=1, max_value=60, value=3, key=f"mes_{i}")
        
        lista_addons.append({
            "nome": nome,
            "preco": preco,
            "attach": attach,
            "mes_inicio": mes_inicio
        })
else:
    lista_addons = []

st.sidebar.markdown("---")
st.sidebar.header("3. Eficiência Comercial")
incremento_semestral_vendas = st.sidebar.number_input("Incremento Semestral de Vendas (%)", min_value=0.0, value=def_crescimento, step=1.0, help="Aumento composto na produtividade da equipe a cada 6 meses.")

st.sidebar.markdown("---")
st.sidebar.header("4. Eventos e CAPEX (Intersolar)")
incluir_intersolar = st.sidebar.checkbox("Participar da Intersolar (Anual)", value=False)

if incluir_intersolar:
    intersolar_custo_ano1 = st.sidebar.number_input("Custo Base (Ano 1 - R$)", min_value=0.0, value=35000.0, step=5000.0)
    intersolar_aumento_anual = st.sidebar.number_input("Aumento de Custo Anual (R$)", min_value=0.0, value=10000.0, step=1000.0)
    intersolar_retorno_ano1 = st.sidebar.number_input("Retorno Base (Clientes no Ano 1)", min_value=0, value=45, step=5)
    intersolar_eficiencia_anual = st.sidebar.number_input("Ganho de Eficiência Anual no Retorno (%)", min_value=0.0, value=10.0, step=1.0)
else:
    intersolar_custo_ano1 = 0
    intersolar_aumento_anual = 0
    intersolar_retorno_ano1 = 0
    intersolar_eficiencia_anual = 0

st.sidebar.markdown("---")
st.sidebar.header("5. Captação de Investimento")
aporte_investimento = st.sidebar.number_input("Valor da Captação (R$)", min_value=0.0, value=def_aporte, step=50000.0)
mes_aporte = st.sidebar.number_input("Mês de Entrada do Aporte", min_value=1, max_value=60, value=def_mes_aporte)

params = cenarios[cenario_selecionado]

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Painel Admin (Visol)")

st.sidebar.markdown("---")

# Garante que apenas o Admin veja e possa clicar no botão
if is_admin:
    st.sidebar.subheader("⚙️ Painel Admin (Visol)")
    if st.sidebar.button("💾 Salvar Cenário Atual como Padrão"):
        try:
            # 1. Remove o status de "padrão" apenas do cenário que atualmente é o padrão
            supabase.table("cenarios_visol").update({"is_default": False}).eq("is_default", True).execute()
            
            # 2. Insere o novo cenário mapeando as variáveis corretas do seu código
            novo_cenario = {
                "nome_cenario": f"Cenário: {cenario_selecionado}",
                "is_default": True,
                "meses_projecao": meses_projecao,
                "caixa_inicial": caixa_inicial,
                "clientes_iniciais": clientes_iniciais,
                "ticket_medio": def_ticket, 
                "crescimento_vendas": incremento_semestral_vendas, 
                "churn_mensal": params["churn_rate"], 
                "inflacao_cac": def_inflacao_cac, 
                "aporte_valor": aporte_investimento, 
                "mes_aporte": mes_aporte 
            }
            supabase.table("cenarios_visol").insert(novo_cenario).execute()
            
            # Limpa o cache para forçar a leitura dos novos dados
            carregar_cenario_padrao.clear()
            st.sidebar.success("✅ Cenário salvo! Investidores agora verão estes números.")
        except Exception as e:
            st.sidebar.error(f"Erro ao salvar no banco: {e}")

# ==========================================
# VARIÁVEIS DE CUSTOS BASE (Carregadas na memória para o motor funcionar)
# ==========================================
default_opex = pd.DataFrame({
    "Categoria": ["Folha de Pagamento", "GSuite (Equipe)", "Google Cloud", "Integrações", "IA", "Contabilidade", "Marketing", "Viagens/Extraordinárias", "Servidores (Rateio)"],
    "Valor Mensal (R$)": [15800.00, 349.30, 90.00, 1000.00, 319.90, 300.00, 1500.00, 600.00, 70.42]
})

# Valores padrão que o motor vai usar se o usuário for investidor (já que ele não pode editar)
edited_opex = default_opex
opex_base_total = edited_opex["Valor Mensal (R$)"].sum()
marketing_row = edited_opex[edited_opex["Categoria"].str.contains("Marketing", case=False, na=False)]
marketing_base = marketing_row["Valor Mensal (R$)"].sum() if not marketing_row.empty else 0.0
inflacao_opex_anual = def_inflacao_cac
inflacao_cac_anual = def_inflacao_cac
lista_gatilhos = [{"nome": "Analista CS 1", "clientes_alvo": 150, "valor": 4000.0}]

# ==========================================
# ESTRUTURA DE ABAS CONDICIONAL (RBAC)
# ==========================================
if is_admin:
    # Admin vê as 4 abas
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Projeções", "💎 Valuation SaaS", "⚙️ Gestão de Custos", "🌪️ Análise de Sensibilidade"])
    
    # ABA 3: GESTÃO DE CUSTOS (Visível apenas para Admin)
    with tab3:
        st.header("Gestão de Custos e Alavancagem Operacional")
        
        st.subheader("1. Custos Operacionais Base (OPEX)")
        # Sobrescreve as variáveis padrão com os inputs da tela editável
        edited_opex = st.data_editor(default_opex, num_rows="dynamic", use_container_width=True)
        opex_base_total = edited_opex["Valor Mensal (R$)"].sum()
        
        marketing_row = edited_opex[edited_opex["Categoria"].str.contains("Marketing", case=False, na=False)]
        marketing_base = marketing_row["Valor Mensal (R$)"].sum() if not marketing_row.empty else 0.0
        
        st.metric("OPEX Base Total", format_br(opex_base_total))
        
        st.markdown("---")
        st.subheader("2. Reajustes e Inflação")
        col_inf1, col_inf2 = st.columns(2)
        with col_inf1:
            inflacao_opex_anual = st.number_input("Reajuste Anual do OPEX (IPCA/Dissídio) %", min_value=0.0, value=def_inflacao_cac, step=1.0)
        with col_inf2:
            inflacao_cac_anual = st.number_input("Degradação Anual do CAC (%)", min_value=0.0, value=def_inflacao_cac, step=1.0)
            
        st.markdown("---")
        st.subheader("3. Gatilhos de OPEX (Step-Functions)")
        num_gatilhos = st.number_input("Quantidade de Gatilhos", min_value=0, max_value=5, value=1)
        
        lista_gatilhos = []
        for i in range(num_gatilhos):
            st.markdown(f"**Gatilho {i+1}**")
            cg1, cg2, cg3 = st.columns(3)
            with cg1:
                nome_gatilho = st.text_input("Descrição", f"Analista CS {i+1}", key=f"gatilho_nome_{i}")
            with cg2:
                clientes_alvo = st.number_input("A cada X clientes", min_value=1, value=150, key=f"gatilho_clientes_{i}")
            with cg3:
                valor_gatilho = st.number_input("Adicionar (R$)", min_value=0.0, value=4000.0, step=500.0, key=f"gatilho_valor_{i}")
                
            lista_gatilhos.append({
                "nome": nome_gatilho,
                "clientes_alvo": clientes_alvo,
                "valor": valor_gatilho
            })
else:
    # Investidor vê apenas 3 abas (tab3 é omitida da interface, mas as variáveis já foram carregadas acima)
    tab1, tab2, tab4 = st.tabs(["📈 Projeções", "💎 Valuation SaaS", "🌪️ Análise de Sensibilidade"])

# --- MOTOR DE PROJEÇÃO FINANCEIRA ---
def projetar_fluxo(params_simulacao, meses, incluir_intersolar, lista_addons, aporte_investimento, mes_aporte, 
                   inflacao_cac_anual, inflacao_opex_anual, lista_gatilhos, opex_base_total, marketing_base,
                   incremento_semestral_vendas, intersolar_custo_ano1, intersolar_aumento_anual, 
                   intersolar_retorno_ano1, intersolar_eficiencia_anual):
    
    dados = []
    clientes_atuais = clientes_iniciais
    mrr_atual = mrr_inicial
    caixa_atual = caixa_inicial
    comissao_pendente_mes_anterior = 0 
    
    clientes_addon_anterior = {i: 0 for i in range(len(lista_addons))}
    
    for mes in range(1, meses + 1):
        fator_eficiencia_comercial = (1 + (incremento_semestral_vendas / 100)) ** ((mes - 1) // 6)
        vendas_base_mes = params_simulacao["vendas_mes"] * fator_eficiencia_comercial
        
        saida_capex = 0
        clientes_extras_intersolar = 0
        
        if incluir_intersolar:
            if mes >= 9 and (mes - 9) % 12 == 0:
                ano_evento = (mes - 9) // 12
                saida_capex = intersolar_custo_ano1 + (ano_evento * intersolar_aumento_anual)
            
            if mes >= 10:
                mes_pos_evento = (mes - 10) % 12
                if mes_pos_evento < 3:
                    ano_evento_retorno = (mes - 10) // 12
                    custo_evento_ref = intersolar_custo_ano1 + (ano_evento_retorno * intersolar_aumento_anual)
                    retorno_total = intersolar_retorno_ano1 * (custo_evento_ref / intersolar_custo_ano1) * ((1 + (intersolar_eficiencia_anual/100)) ** ano_evento_retorno)
                    clientes_extras_intersolar = retorno_total / 3 
                    
        novos_clientes = vendas_base_mes + clientes_extras_intersolar
                
        clientes_churn = clientes_atuais * params_simulacao["churn_rate"]
        clientes_atuais = clientes_atuais + novos_clientes - clientes_churn
        
        novo_mrr_core = novos_clientes * params_simulacao["arpa_novo"]
        mrr_churn = clientes_churn * (mrr_atual / max(clientes_atuais, 1))
        mrr_atual = mrr_atual + novo_mrr_core - mrr_churn
        
        receita_addons_total = 0
        novo_mrr_addons_total = 0
        
        for i, addon in enumerate(lista_addons):
            if mes >= addon["mes_inicio"]:
                clientes_addon_atual = clientes_atuais * addon["attach"]
                receita_addons_total += clientes_addon_atual * addon["preco"]
                
                if clientes_addon_atual > clientes_addon_anterior[i]:
                    novo_mrr_addons_total += (clientes_addon_atual - clientes_addon_anterior[i]) * addon["preco"]
                
                clientes_addon_anterior[i] = clientes_addon_atual
        
        mrr_total_mes = mrr_atual + receita_addons_total
        receita_implementacao = novos_clientes * params_simulacao["ticket_implementacao"]
        receita_bruta = mrr_total_mes + receita_implementacao
        
        entrada_fomento = fomento_faperj if mes == 1 else 0
        entrada_aporte = aporte_investimento if mes == mes_aporte else 0
        
        impostos = receita_bruta * 0.06
        novo_mrr_total_comissionavel = novo_mrr_core + novo_mrr_addons_total
        
        if novos_clientes <= 4:
            comissao_total_gerada = (novo_mrr_total_comissionavel * 1.0) + (receita_implementacao * 0.1)
        elif novos_clientes <= 6:
            comissao_total_gerada = (novo_mrr_total_comissionavel * 1.20) + (receita_implementacao * 0.15)
        else:
            comissao_total_gerada = (novo_mrr_total_comissionavel * 1.40) + (receita_implementacao * 0.20)
            
        comissao_paga_mes = (comissao_total_gerada / 2) + comissao_pendente_mes_anterior
        comissao_pendente_mes_anterior = comissao_total_gerada / 2
            
        fator_inflacao_opex = (1 + (inflacao_opex_anual / 100)) ** (mes / 12)
        opex_base_mes = opex_base_total * fator_inflacao_opex
        
        opex_gatilhos = 0
        for gatilho in lista_gatilhos:
            multiplicador = int(clientes_atuais // gatilho["clientes_alvo"])
            opex_gatilhos += multiplicador * gatilho["valor"]
            
        opex_total = opex_base_mes + params_simulacao["add_mkt"] + params_simulacao["add_vendas"] + params_simulacao["add_outros"] + opex_gatilhos
        saida_emprestimo = parcela_emprestimo if mes <= meses_restantes_emprestimo else 0
        
        saidas_totais = opex_total + impostos + comissao_paga_mes + saida_emprestimo + saida_capex
        
        fluxo_mes = receita_bruta + entrada_fomento + entrada_aporte - saidas_totais
        caixa_atual += fluxo_mes
        
        fator_inflacao_cac = (1 + (inflacao_cac_anual / 100)) ** (mes / 12)
        custo_marketing_mes = (marketing_base + params_simulacao["add_mkt"]) * fator_inflacao_cac
        
        if saida_capex > 0:
            custo_marketing_mes += saida_capex
            
        custo_vendas = comissao_total_gerada + params_simulacao["add_vendas"]
        cac = (custo_marketing_mes + custo_vendas) / novos_clientes if novos_clientes > 0 else 0
        
        arpa_blended = mrr_total_mes / clientes_atuais if clientes_atuais > 0 else 0
        
        fator_desagio_ltv = 0.5 
        lifetime_teorico = 1 / params_simulacao["churn_rate"] if params_simulacao["churn_rate"] > 0 else 0
        lifetime_aplicado = lifetime_teorico * fator_desagio_ltv
        ltv = arpa_blended * lifetime_aplicado
        
        dados.append({
            "Mês": mes,
            "Novos Clientes": novos_clientes,
            "Clientes Ativos": clientes_atuais,
            "MRR Licenças (R$)": mrr_atual,
            "MRR Add-ons (R$)": receita_addons_total,
            "MRR Total (R$)": mrr_total_mes,
            "Receita Implementação (R$)": receita_implementacao,
            "Receita Bruta (R$)": receita_bruta,
            "Fomento FAPERJ (R$)": entrada_fomento,
            "Aporte Investidor (R$)": entrada_aporte,
            "OPEX Base (R$)": opex_base_mes,
            "OPEX Gatilhos (R$)": opex_gatilhos,
            "OPEX Total (R$)": opex_total,
            "Impostos (R$)": impostos,
            "Comissões Pagas (R$)": comissao_paga_mes,
            "Empréstimo (R$)": saida_emprestimo,
            "CAPEX (R$)": saida_capex,
            "Saídas Totais (R$)": saidas_totais,
            "Fluxo do Mês (R$)": fluxo_mes,
            "Caixa Acumulado (R$)": caixa_atual,
            "ARPA Blended (R$)": arpa_blended,
            "CAC (R$)": cac,
            "LTV (R$)": ltv
        })
        
    return pd.DataFrame(dados)

df_projecao = projetar_fluxo(
    params, meses_projecao, incluir_intersolar, lista_addons, 
    aporte_investimento, mes_aporte, inflacao_cac_anual, 
    inflacao_opex_anual, lista_gatilhos, opex_base_total, marketing_base,
    incremento_semestral_vendas, intersolar_custo_ano1, intersolar_aumento_anual, 
    intersolar_retorno_ano1, intersolar_eficiencia_anual
)

# --- EXPORTAÇÃO DE DADOS (SIDEBAR) ---
st.sidebar.markdown("---")
st.sidebar.header("6. Exportação (Data Room)")
csv_data = df_projecao.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="📥 Baixar DRE Projetado (CSV)",
    data=csv_data,
    file_name=f"visol_projecao_{cenario_selecionado.split()[0].lower()}.csv",
    mime="text/csv"
)

# ==========================================
# ABA 1: PROJEÇÕES FINANCEIRAS
# ==========================================
with tab1:
    st.header(f"Projeção: Cenário {cenario_selecionado}")

    ult_mes = df_projecao.iloc[-1]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("MRR Total Final", format_br(ult_mes['MRR Total (R$)']))
    col2.metric("Receita Bruta Final", format_br(ult_mes['Receita Bruta (R$)']))
    col3.metric("Caixa Final", format_br(ult_mes['Caixa Acumulado (R$)']))
    col4.metric("Clientes Finais", int(ult_mes['Clientes Ativos']))

    st.markdown("---")
    st.subheader("Métricas SaaS (Unit Economics)")
    col5, col6, col7, col8 = st.columns(4)
    cac_medio = df_projecao['CAC (R$)'].mean()
    ltv_medio = df_projecao['LTV (R$)'].mean()
    ltv_cac_ratio = ltv_medio / cac_medio if cac_medio > 0 else 0
    arpa_final = ult_mes['ARPA Blended (R$)']

    col5.metric("CAC Médio", format_br(cac_medio))
    col6.metric("LTV Estimado (Conservador)", format_br(ltv_medio))
    col7.metric("Relação LTV:CAC", f"{ltv_cac_ratio:.1f}x".replace(".", ","))
    col8.metric("ARPA Final (Blended)", format_br(arpa_final))

    st.markdown("---")
    col_graf1, col_graf2 = st.columns(2)
    with col_graf1:
        st.subheader("Composição da Receita")
        if len(lista_addons) > 0:
            st.bar_chart(df_projecao, x="Mês", y=["MRR Licenças (R$)", "MRR Add-ons (R$)", "Receita Implementação (R$)"])
        else:
            st.bar_chart(df_projecao, x="Mês", y=["MRR Licenças (R$)", "Receita Implementação (R$)"])

    with col_graf2:
        st.subheader("Evolução do Caixa Acumulado (Runway)")
        st.line_chart(df_projecao, x="Mês", y="Caixa Acumulado (R$)")

    st.subheader("DRE Simplificado e Fluxo de Caixa (Mensal)")
    colunas_moeda = [col for col in df_projecao.columns if "(R$)" in col]
    
    st.dataframe(
        df_projecao.style.format({col: format_br for col in colunas_moeda}),
        use_container_width=True
    )

# ==========================================
# ABA 2: VALUATION SAAS
# ==========================================
with tab2:
    st.header("Valuation da Visol (Método de Múltiplos de ARR)")
    
    arr_atual = mrr_inicial * 12
    mrr_projetado = ult_mes['MRR Total (R$)']
    arr_projetado = mrr_projetado * 12
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ARR Atual (Mês 0)", format_br(arr_atual))
    c2.metric(f"ARR Projetado (Mês {meses_projecao})", format_br(arr_projetado))
    c3.metric("Taxa de Churn Mensal", format_pct_br(params['churn_rate']))
    
    crescimento = (arr_projetado/arr_atual)-1
    c4.metric("Crescimento Projetado (ARR)", format_pct_br(crescimento))

    st.markdown("---")
    col_val1, col_val2 = st.columns([1, 2])
    
      with col_val1:
        st.markdown("**Definição do Múltiplo**")
        # O parâmetro disabled=not is_admin bloqueia a edição se o usuário não for admin
        multiplo_arr = st.slider(
            "Múltiplo de ARR Aplicado", 
            1.0, 15.0, 4.0, 0.5, 
            disabled=not is_admin
        )
        base_calculo = st.radio(
            "Base do ARR", 
            ["ARR Atual (Trailing)", "ARR Projetado (Forward)"], 
            index=1, 
            disabled=not is_admin
        )
        
        arr_base = arr_projetado if base_calculo == "ARR Projetado (Forward)" else arr_atual
        valuation_pre_money = arr_base * multiplo_arr
        st.info(f"**Valuation Pre-Money:**\n{format_br(valuation_pre_money)}")
          
    with col_val2:
        st.markdown("**Impacto da Captação no Cap Table**")
        if aporte_investimento > 0:
            valuation_post_money = valuation_pre_money + aporte_investimento
            equity_cedido = (aporte_investimento / valuation_post_money) * 100
            
            st.write(f"- **Aporte Solicitado:** {format_br(aporte_investimento)}")
            st.write(f"- **Valuation Post-Money:** {format_br(valuation_post_money)}")
            st.write(f"- **Equity Cedido ao Investidor:** {format_pct_br(equity_cedido/100, 2)}")
        else:
            st.info("Insira um valor em 'Captação de Investimento' na barra lateral.")

# ==========================================
# ABA 4: ANÁLISE DE SENSIBILIDADE
# ==========================================
with tab4:
    st.header("Análise de Sensibilidade (Matriz de Risco)")
    st.markdown("Mapeamento dos limites de ruptura da operação cruzando variações na **Taxa de Churn** vs **Volume de Vendas Base**.")
    
    st.subheader(f"Impacto no Caixa Final (Mês {meses_projecao})")
    
    variacoes_vendas = [-0.30, -0.15, 0.0, 0.15, 0.30] 
    taxas_churn_simulacao = [0.005, 0.01, 0.015, 0.02, 0.03] 
    
    vendas_base = params["vendas_mes"]
    
    indices_churn = [format_pct_br(c) for c in taxas_churn_simulacao]
    colunas_vendas = [f"{int(v*100)}%" for v in variacoes_vendas]
    
    matriz_caixa = pd.DataFrame(index=indices_churn, columns=colunas_vendas)
    
    for churn, idx_churn in zip(taxas_churn_simulacao, indices_churn):
        for var_venda, col_venda in zip(variacoes_vendas, colunas_vendas):
            
            params_sim = params.copy()
            params_sim["churn_rate"] = churn
            params_sim["vendas_mes"] = vendas_base * (1 + var_venda)
            
            df_sim = projetar_fluxo(
                params_sim, meses_projecao, incluir_intersolar, lista_addons, 
                aporte_investimento, mes_aporte, inflacao_cac_anual, 
                inflacao_opex_anual, lista_gatilhos, opex_base_total, marketing_base,
                incremento_semestral_vendas, intersolar_custo_ano1, intersolar_aumento_anual, 
                intersolar_retorno_ano1, intersolar_eficiencia_anual
            )
            
            caixa_final_sim = df_sim.iloc[-1]['Caixa Acumulado (R$)']
            matriz_caixa.at[idx_churn, col_venda] = caixa_final_sim

    matriz_caixa = matriz_caixa.astype(float)

    st.markdown("**Eixo Y:** Taxa de Churn Mensal | **Eixo X:** Variação no Volume de Vendas Base")
    
    st.dataframe(
        matriz_caixa.style.format(lambda x: format_br(x, decimais=0))
        .background_gradient(cmap="RdYlGn", axis=None),
        use_container_width=True
    )




