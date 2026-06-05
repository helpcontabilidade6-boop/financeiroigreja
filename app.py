import re
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

from parser_bradesco import ler_excel_bradesco


CATEGORIAS = [
    "Dízimo",
    "Oferta",
    "Deposito em Dinheiro",
    "Rendimento Bancário",
    "Cartão de Crédito",
    "Água",
    "Energia",
    "Limpeza",
    "Pastor",
    "Internet",
    "Tarifa Bancária",
    "Contadora",
    "Convenção",
    "Aluguel",
    "Outros",
]

MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def normalizar_texto(texto):
    texto = "" if pd.isna(texto) else str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().upper()


def moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rotulo_competencia(periodo):
    return f"{MESES[periodo.month]} de {periodo.year}"


def classificar(nome, valor, tipo):
    nome = normalizar_texto(nome)
    tipo = normalizar_texto(tipo)

    if tipo == "ENTRADA":

       if "RENTAB.INVEST" in nome or "INVEST FACIL" in nome:
        return "Rendimento Bancário"

    if (
        "DEP DINHEIRO" in nome
        or "DEPOSITO" in nome
        or "DEPÓSITO" in nome
        or "CAIXA AG" in nome
    ):
        return "Depósito em Dinheiro"

    return "Dízimo" if valor > 100 else "Oferta"

    if "WELLINGTON" in nome:
        return "Pastor"

    if "RAQUEL" in nome:
        return "Limpeza"

    if "BRISANET" in nome or "INTERNET" in nome or "ACESSEWEBTELECOM" in nome:
        return "Internet"

    if "ENEL" in nome or "ENERGIA" in nome or "LUZ" in nome:
        return "Energia"

    if "CAGECE" in nome or "AGUA" in nome:
        return "Água"

    if "TARIFA" in nome or "CESTA" in nome or "MANUTENCAO" in nome:
        return "Tarifa Bancária"

    if "ANA KELLY" in nome or "CONTADOR" in nome:
        return "Contadora"

    if "CONVENCAO" in nome:
        return "Convenção"

    if "ALUGUEL" in nome:
        return "Aluguel"

    return "Outros"


st.set_page_config(page_title="Financeiro Igreja", layout="wide")

st.markdown("""
<div style='text-align:center;'>

# ⛪ IGREJA GILEADE

### Sistema Financeiro e Conciliação Bancária

<p style='color:gray'>
Controle de Entradas, Saídas, Dízimos e Ofertas
</p>

</div>

<hr>
""", unsafe_allow_html=True)
st.caption(
    "Prestação de contas, conciliação bancária e acompanhamento financeiro."
)

arquivos = st.file_uploader(
    "Selecione os extratos do Bradesco",
    type=["xls", "xlsx"],
    accept_multiple_files=True,
)

if not arquivos:
    st.info("Envie um ou mais arquivos Excel do Bradesco para começar.")
    st.stop()

planilhas = []

for arquivo in arquivos:
    df = ler_excel_bradesco(arquivo)

    if not df.empty:
        df["Arquivo"] = arquivo.name
        planilhas.append(df)

if not planilhas:
    st.error("Nenhuma movimentação foi encontrada nos arquivos enviados.")
    st.stop()

df_final = pd.concat(planilhas, ignore_index=True)
df_final["Valor"] = pd.to_numeric(df_final["Valor"], errors="coerce").fillna(0)
df_final["_DataMovimento"] = pd.to_datetime(
    df_final["Data"],
    dayfirst=True,
    errors="coerce",
)
df_final["_Competencia"] = df_final["_DataMovimento"].dt.to_period("M")

competencias = sorted(df_final["_Competencia"].dropna().unique())

if competencias:

    competencias = sorted(df_final["_Competencia"].dropna().unique())

if competencias:

    competencias_escolhidas = st.multiselect(
        "Competências",
        competencias,
        default=competencias,
        format_func=rotulo_competencia,
    )

    if competencias_escolhidas:
        df_final = df_final[
            df_final["_Competencia"].isin(
                competencias_escolhidas
            )
        ].copy()

# Remove registros repetidos entre extratos
qtde_antes = len(df_final)

df_final = df_final.drop_duplicates(
    subset=["Data", "Nome", "Valor", "Tipo"]
)

qtde_removidas = qtde_antes - len(df_final)

if qtde_removidas > 0:
    st.warning(
        f"⚠️ {qtde_removidas} movimentação(ões) duplicadas foram removidas."
    )
df_final["Categoria"] = df_final.apply(
    lambda linha: classificar(linha["Nome"], linha["Valor"], linha["Tipo"]),
    axis=1,
)
df_final = df_final.drop(columns=["_DataMovimento", "_Competencia"], errors="ignore")

total_entradas = df_final.loc[df_final["Tipo"] == "Entrada", "Valor"].sum()
total_saidas = df_final.loc[df_final["Tipo"] == "Saída", "Valor"].sum()
total_dizimos = df_final.loc[df_final["Categoria"] == "Dízimo", "Valor"].sum()
total_ofertas = df_final.loc[df_final["Categoria"] == "Oferta", "Valor"].sum()
saldo = total_entradas - total_saidas

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Entradas", moeda(total_entradas))
c2.metric("Dízimos", moeda(total_dizimos))
c3.metric("Ofertas", moeda(total_ofertas))
c4.metric("Saídas", moeda(total_saidas))
c5.metric("Saldo", moeda(saldo))

st.divider()

st.subheader("Resumo por Categoria")

resumo = (
    df_final.groupby(["Tipo", "Categoria"], as_index=False)["Valor"]
    .sum()
    .sort_values(["Tipo", "Valor"], ascending=[True, False])
)

st.dataframe(
    resumo,
    column_config={"Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f")},
    use_container_width=True,
    hide_index=True,
)

fig = px.bar(
    resumo,
    x="Categoria",
    y="Valor",
    color="Tipo",
    barmode="group",
    title="Movimentações por Categoria",
)
st.plotly_chart(fig, use_container_width=True)
from io import BytesIO
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


def gerar_pdf():
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    elementos = []

    elementos.append(
        Paragraph("IGREJA GILEADE", styles["Title"])
    )

    elementos.append(
        Paragraph(
            "Relatório Financeiro",
            styles["Heading2"],
        )
    )

    elementos.append(Spacer(1, 12))

    dados = [
        ["Indicador", "Valor"],
        ["Entradas", moeda(total_entradas)],
        ["Dízimos", moeda(total_dizimos)],
        ["Ofertas", moeda(total_ofertas)],
        ["Saídas", moeda(total_saidas)],
        ["Saldo", moeda(saldo)],
    ]

    tabela = Table(dados, colWidths=[180, 180])

    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )

    elementos.append(tabela)

    elementos.append(Spacer(1, 20))

    elementos.append(
        Paragraph(
            "Resumo por Categoria",
            styles["Heading2"],
        )
    )

    dados_resumo = [["Tipo", "Categoria", "Valor"]]

    for _, linha in resumo.iterrows():
        dados_resumo.append(
            [
                linha["Tipo"],
                linha["Categoria"],
                moeda(linha["Valor"]),
            ]
        )

    tabela_resumo = Table(
        dados_resumo,
        colWidths=[100, 200, 100],
    )

    tabela_resumo.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )

    elementos.append(tabela_resumo)

    elementos.append(Spacer(1, 30))

    elementos.append(
        Paragraph(
            "Tesouraria __________________________",
            styles["Normal"],
        )
    )

    elementos.append(
        Paragraph(
            "Pastor ______________________________",
            styles["Normal"],
        )
    )

    doc.build(elementos)

    buffer.seek(0)

    return buffer

st.subheader("Movimentações")

colunas_visiveis = ["Data", "Nome", "Valor", "Tipo", "Categoria"]

df_editado = st.data_editor(
    df_final[colunas_visiveis],
    column_config={
        "Categoria": st.column_config.SelectboxColumn("Categoria", options=CATEGORIAS),
        "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
    },
    disabled=["Data", "Nome", "Valor", "Tipo"],
    use_container_width=True,
    hide_index=True,
)

csv = df_editado.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "Baixar CSV",
    csv,
    "financeiro_igreja.csv",
    "text/csv",
)
pdf = gerar_pdf()

st.download_button(
    "📄 Baixar Relatório PDF",
    data=pdf,
    file_name="Relatorio_Financeiro_Gileade.pdf",
    mime="application/pdf",
)