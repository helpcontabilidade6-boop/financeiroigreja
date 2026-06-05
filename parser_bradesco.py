import re
import unicodedata

import pandas as pd


def _normalizar_texto(texto):
    texto = "" if pd.isna(texto) else str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip().upper()


def converter_valor(valor):
    if pd.isna(valor):
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()

    if texto == "" or texto.lower() == "nan":
        return None

    negativo = texto.startswith("-") or texto.endswith("-") or texto.startswith("(")
    texto = texto.replace("R$", "").replace(" ", "")
    texto = texto.replace("-", "").replace("(", "").replace(")", "")

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        numero = float(texto)
    except ValueError:
        return None

    return -numero if negativo else numero


def _achar_coluna(df, termos):
    for coluna in df.columns:
        nome = _normalizar_texto(coluna)

        if all(termo in nome for termo in termos):
            return coluna

    return None


def _linha_parece_saida(descricao):
    descricao = _normalizar_texto(descricao)

    if "PIX RECEBIDO" in descricao or "REM:" in descricao:
        return False

    termos_saida = [
        "PIX ENVIADO",
        "PAGAMENTO",
        "PAGTO",
        "TRANSFERENCIA ENTRE CONTAS",
        "TRANSF CC",
        "TED",
        "DOC",
        "TARIFA",
        "CESTA",
        "MANUTENCAO",
        "GASTOS CARTAO",
    ]
    return any(termo in descricao for termo in termos_saida)


def _ler_planilha_com_cabecalho(arquivo):
    bruto = pd.read_excel(arquivo, header=None, dtype=str)

    for indice, linha in bruto.iterrows():
        textos = [_normalizar_texto(valor) for valor in linha.tolist()]
        tem_lancamento = any("LANCAMENTO" in texto or "HISTORICO" in texto for texto in textos)
        tem_valor = any("CREDITO" in texto or "DEBITO" in texto or "VALOR" in texto for texto in textos)

        if tem_lancamento and tem_valor:
            return pd.read_excel(arquivo, header=indice, dtype=str)

    return pd.read_excel(arquivo, header=8, dtype=str)


def ler_excel_bradesco(arquivo):
    df = _ler_planilha_com_cabecalho(arquivo)

    coluna_data = _achar_coluna(df, ["DATA"])
    coluna_descricao = (
        _achar_coluna(df, ["LANCAMENTO"])
        or _achar_coluna(df, ["HISTORICO"])
        or _achar_coluna(df, ["DESCRICAO"])
    )
    coluna_credito = _achar_coluna(df, ["CREDITO"])
    coluna_debito = _achar_coluna(df, ["DEBITO"])
    coluna_valor = _achar_coluna(df, ["VALOR"])

    registros = []

    if coluna_descricao is None:
        return pd.DataFrame(columns=["Data", "Nome", "Valor", "Tipo"])

    for _, linha in df.iterrows():
        descricao = str(linha.get(coluna_descricao, "")).strip()
        descricao_normalizada = _normalizar_texto(descricao)

        if (
            descricao == ""
            or descricao.lower() == "nan"
            or "SALDO ANTERIOR" in descricao_normalizada
            or "SALDO DO DIA" in descricao_normalizada
            or "TOTAL" == descricao_normalizada
        ):
            continue

        data = str(linha.get(coluna_data, "")).strip() if coluna_data else ""
        credito = converter_valor(linha.get(coluna_credito)) if coluna_credito else None
        debito = converter_valor(linha.get(coluna_debito)) if coluna_debito else None

        movimentou = False

        if credito is not None and credito > 0 and not _linha_parece_saida(descricao):
            registros.append(
                {
                    "Data": data,
                    "Nome": descricao,
                    "Valor": credito,
                    "Tipo": "Entrada",
                }
            )
            movimentou = True

        if debito is not None and debito > 0:
            registros.append(
                {
                    "Data": data,
                    "Nome": descricao,
                    "Valor": debito,
                    "Tipo": "Saída",
                }
            )
            movimentou = True

        if credito is not None and credito < 0:
            registros.append(
                {
                    "Data": data,
                    "Nome": descricao,
                    "Valor": abs(credito),
                    "Tipo": "Saída",
                }
            )
            movimentou = True

        if debito is not None and debito < 0:
            registros.append(
                {
                    "Data": data,
                    "Nome": descricao,
                    "Valor": abs(debito),
                    "Tipo": "Saída",
                }
            )
            movimentou = True

        if credito is not None and credito > 0 and _linha_parece_saida(descricao) and not movimentou:
            registros.append(
                {
                    "Data": data,
                    "Nome": descricao,
                    "Valor": credito,
                    "Tipo": "Saída",
                }
            )
            movimentou = True

        if coluna_valor and not movimentou:
            valor = converter_valor(linha.get(coluna_valor))

            if valor is None or valor == 0:
                continue

            tipo = "Entrada"

            if valor < 0 or _linha_parece_saida(descricao):
                tipo = "Saída"

            registros.append(
                {
                    "Data": data,
                    "Nome": descricao,
                    "Valor": abs(valor),
                    "Tipo": tipo,
                }
            )

    return pd.DataFrame(registros, columns=["Data", "Nome", "Valor", "Tipo"])
