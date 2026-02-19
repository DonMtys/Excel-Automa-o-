from __future__ import annotations

import io
import re
import unicodedata
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PLOTLY_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}

PLACEHOLDER_LOCALS = {
    "0",
    "00",
    "000",
    "x",
    "xx",
    "xxx",
    "xxxx",
    "teste",
    "test",
    "email",
    "naotem",
    "sem",
    "sememail",
    "naoconsta",
    "null",
    "none",
    "desconhecido",
}

PLACEHOLDER_DOMAINS = {
    "desconhecido.com",
    "sem.email",
    "naotem.com",
    "naotem.com.br",
    "naoconsta.com.br",
    "email.com",
    "teste.com",
    "test.com",
}

COMMON_TYPO_DOMAINS = {
    "gamil.com",
    "gmial.com",
    "gmail.con",
    "gmai.com",
    "hotnail.com",
    "hotmai.com",
    "hotmal.com",
    "yaho.com",
    "yhoo.com",
    "yahool.com",
    "outlok.com",
    "outllok.com",
    "otlook.com",
}

BRAZIL_UFS = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}

UF_TO_STATE_NAME = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapa",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceara",
    "DF": "Distrito Federal",
    "ES": "Espirito Santo",
    "GO": "Goias",
    "MA": "Maranhao",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Para",
    "PB": "Paraiba",
    "PR": "Parana",
    "PE": "Pernambuco",
    "PI": "Piaui",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondonia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "Sao Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}

# Coordenadas de referencia (capitais), usadas no mapa por UF.
UF_TO_COORD = {
    "AC": (-8.77, -70.55),
    "AL": (-9.62, -36.82),
    "AP": (1.41, -51.77),
    "AM": (-3.10, -60.02),
    "BA": (-12.97, -38.50),
    "CE": (-3.73, -38.54),
    "DF": (-15.79, -47.88),
    "ES": (-20.32, -40.34),
    "GO": (-16.67, -49.25),
    "MA": (-2.53, -44.30),
    "MT": (-15.60, -56.10),
    "MS": (-20.45, -54.62),
    "MG": (-19.92, -43.94),
    "PA": (-1.45, -48.50),
    "PB": (-7.12, -34.86),
    "PR": (-25.43, -49.27),
    "PE": (-8.05, -34.90),
    "PI": (-5.09, -42.80),
    "RJ": (-22.90, -43.20),
    "RN": (-5.79, -35.21),
    "RS": (-30.03, -51.23),
    "RO": (-8.76, -63.90),
    "RR": (2.82, -60.67),
    "SC": (-27.59, -48.55),
    "SP": (-23.55, -46.63),
    "SE": (-10.91, -37.07),
    "TO": (-10.18, -48.33),
}

# Pequenos offsets para reduzir sobreposicao dos nomes no mapa.
UF_LABEL_OFFSET = {
    "AL": (0.5, -0.1),
    "AP": (0.5, 0.15),
    "CE": (0.35, 0.2),
    "MA": (0.2, 0.35),
    "PB": (0.6, 0.05),
    "PE": (0.55, -0.15),
    "PI": (0.35, 0.1),
    "RN": (0.7, 0.2),
    "SE": (0.4, -0.2),
}

FIELD_LABELS = {
    "source": "Coluna de origem (opcional)",
    "document": "Coluna de CPF/CNPJ (opcional)",
    "name": "Coluna de nome (opcional)",
    "email": "Coluna de e-mail (obrigatoria)",
    "region": "Coluna de regiao (opcional)",
}

HEADER_ALIASES = {
    "source": {"origem", "nome_credor", "credor", "fonte", "orgao"},
    "document": {"cpf_cnpj", "cpfcnpj", "cpf", "cnpj", "documento", "doc"},
    "name": {"nome", "nome_contribuinte", "cliente", "nome_cliente"},
    "email": {"email", "e_mail", "e-mail", "mail", "correio_eletronico"},
    "region": {"regiao", "regiao_creci", "regional", "creci", "regiao_uf"},
}


def normalize_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_header(value: Any) -> str:
    text = normalize_text(value)
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def extract_brazil_uf(value: Any) -> str:
    text = normalize_text(value).upper()
    if not text:
        return ""

    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    slash_match = re.findall(r"/\s*([A-Z]{2})\b", normalized)
    if slash_match and slash_match[-1] in BRAZIL_UFS:
        return slash_match[-1]

    end_match = re.search(r"\b([A-Z]{2})\b\s*$", normalized)
    if end_match and end_match.group(1) in BRAZIL_UFS:
        return end_match.group(1)

    tokens = re.findall(r"\b([A-Z]{2})\b", normalized)
    valid_tokens = [token for token in tokens if token in BRAZIL_UFS]
    if valid_tokens:
        return valid_tokens[-1]

    return ""


def looks_like_no_header(columns: list[Any]) -> bool:
    normalized = [normalize_header(col) for col in columns]
    known_headers = set().union(*HEADER_ALIASES.values())
    if any(col in known_headers for col in normalized):
        return False

    suspicious = 0
    for col in columns:
        text = normalize_text(col).lower()
        if "@" in text:
            suspicious += 1
        digits = re.sub(r"\D+", "", text)
        if len(digits) in {11, 14}:
            suspicious += 1
    return suspicious > 0


def detect_csv_delimiter(file_bytes: bytes) -> str:
    sample = file_bytes[:8192].decode("utf-8", errors="ignore")
    comma_count = sample.count(",")
    semicolon_count = sample.count(";")
    return ";" if semicolon_count > comma_count else ","


def read_table(uploaded_file: Any) -> pd.DataFrame:
    suffix = uploaded_file.name.lower().split(".")[-1]
    file_bytes = uploaded_file.getvalue()
    buffer = io.BytesIO(file_bytes)

    if suffix == "csv":
        delimiter = detect_csv_delimiter(file_bytes)
        df = pd.read_csv(buffer, dtype=str, header=0, sep=delimiter, keep_default_na=False)
        if looks_like_no_header(list(df.columns)):
            buffer = io.BytesIO(file_bytes)
            df = pd.read_csv(buffer, dtype=str, header=None, sep=delimiter, keep_default_na=False)
            df.columns = [f"col_{i + 1}" for i in range(df.shape[1])]
    elif suffix in {"xlsx", "xls"}:
        df = pd.read_excel(buffer, dtype=str, header=0)
        df = df.fillna("")
        if looks_like_no_header(list(df.columns)):
            buffer = io.BytesIO(file_bytes)
            df = pd.read_excel(buffer, dtype=str, header=None).fillna("")
            df.columns = [f"col_{i + 1}" for i in range(df.shape[1])]
    else:
        raise ValueError("Formato nao suportado. Use CSV, XLSX ou XLS.")

    df.columns = [normalize_text(col) for col in df.columns]
    return df.fillna("")


def guess_by_alias(columns: list[str]) -> dict[str, str | None]:
    normalized_map = {col: normalize_header(col) for col in columns}
    guessed: dict[str, str | None] = {key: None for key in FIELD_LABELS}

    for field, aliases in HEADER_ALIASES.items():
        for col, normalized in normalized_map.items():
            if normalized in aliases:
                guessed[field] = col
                break
    return guessed


def score_email_column(series: pd.Series) -> float:
    sample = series.astype(str).str.strip().str.lower().head(1000)
    if len(sample) == 0:
        return 0.0
    return float((sample.str.contains("@")).mean())


def score_document_column(series: pd.Series) -> float:
    sample = series.astype(str).str.strip().head(1000)
    if len(sample) == 0:
        return 0.0
    digits = sample.str.replace(r"\D+", "", regex=True)
    return float(((digits.str.len() == 11) | (digits.str.len() == 14)).mean())


def score_name_column(series: pd.Series) -> float:
    sample = series.astype(str).str.strip().head(1000)
    if len(sample) == 0:
        return 0.0
    has_space = sample.str.contains(" ")
    has_letter = sample.str.contains(r"[A-Za-z]", regex=True)
    return float((has_space & has_letter).mean())


def guess_columns(df: pd.DataFrame) -> dict[str, str | None]:
    columns = list(df.columns)
    guessed = guess_by_alias(columns)

    if len(columns) >= 5 and all(guessed.get(field) is None for field in guessed):
        guessed["source"] = columns[0]
        guessed["document"] = columns[1]
        guessed["name"] = columns[2]
        guessed["email"] = columns[3]
        guessed["region"] = columns[4]
        return guessed

    if guessed["email"] is None:
        scored = sorted(((col, score_email_column(df[col])) for col in columns), key=lambda x: x[1], reverse=True)
        guessed["email"] = scored[0][0] if scored and scored[0][1] > 0 else None

    if guessed["document"] is None:
        scored = sorted(((col, score_document_column(df[col])) for col in columns), key=lambda x: x[1], reverse=True)
        guessed["document"] = scored[0][0] if scored and scored[0][1] > 0 else None

    if guessed["name"] is None:
        scored = sorted(((col, score_name_column(df[col])) for col in columns), key=lambda x: x[1], reverse=True)
        guessed["name"] = scored[0][0] if scored and scored[0][1] > 0 else None

    if guessed["source"] is None and len(columns) > 0:
        guessed["source"] = columns[0]

    if guessed["region"] is None and len(columns) >= 5:
        guessed["region"] = columns[4]

    return guessed


def pick_column(df: pd.DataFrame, selected_col: str | None) -> pd.Series:
    if not selected_col:
        return pd.Series([""] * len(df))
    return df[selected_col].astype(str).fillna("").str.strip()


def classify_email(email: str) -> list[str]:
    reasons: list[str] = []
    email = email.strip().lower().rstrip(",")
    if not email:
        return reasons

    if not EMAIL_REGEX.match(email):
        reasons.append("formato_invalido")

    if "@" in email:
        local, domain = email.split("@", 1)
    else:
        local, domain = email, ""

    if local in PLACEHOLDER_LOCALS or domain in PLACEHOLDER_DOMAINS:
        reasons.append("placeholder_lixo")

    if domain in COMMON_TYPO_DOMAINS:
        reasons.append("dominio_typo")

    return reasons


def domain_family(domain: str) -> str:
    domain = domain.lower().strip()
    if not domain:
        return "Sem dominio"
    if "gmail" in domain:
        return "Gmail"
    if any(key in domain for key in ["hotmail", "outlook", "live", "msn"]):
        return "Hotmail / Outlook"
    if any(key in domain for key in ["yahoo", "ymail", "yahool"]):
        return "Yahoo"
    if any(key in domain for key in ["uol", "bol", "ig", "terra", "oi", "globo"]):
        return "Portais BR"
    if domain.endswith(".gov.br"):
        return "Governo"
    if "creci" in domain:
        return "CRECI"
    return "Outros"


def repeat_bucket(value: int) -> str:
    if value <= 1:
        return "1 vez"
    if value == 2:
        return "2 vezes"
    if value == 3:
        return "3 vezes"
    if value <= 5:
        return "4-5 vezes"
    if value <= 10:
        return "6-10 vezes"
    return "11+ vezes"


def build_plot_theme(
    fig: Any,
    margin_left: int = 12,
    margin_right: int = 12,
    margin_top: int = 26,
    margin_bottom: int = 12,
) -> Any:
    fig.update_layout(
        margin=dict(t=margin_top, l=margin_left, r=margin_right, b=margin_bottom),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.55)",
        font=dict(family="Space Grotesk, sans-serif", color="#E5EDF5"),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(148,163,184,0.22)",
            tickfont=dict(color="#D7E3F2", size=12),
            title_font=dict(color="#D7E3F2", size=12),
            automargin=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148,163,184,0.22)",
            tickfont=dict(color="#D7E3F2", size=12),
            title_font=dict(color="#D7E3F2", size=12),
            automargin=True,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    return fig


def build_analysis(df: pd.DataFrame, mapping: dict[str, str | None]) -> dict[str, Any]:
    base = pd.DataFrame()
    base["ORIGEM"] = pick_column(df, mapping.get("source"))
    base["CPF_CNPJ"] = pick_column(df, mapping.get("document"))
    base["NOME"] = pick_column(df, mapping.get("name"))
    base["E_MAIL"] = pick_column(df, mapping.get("email"))
    base["REGIAO"] = pick_column(df, mapping.get("region"))

    base["CPF_CNPJ_NORM"] = base["CPF_CNPJ"].str.replace(r"\D+", "", regex=True)
    base["E_MAIL_NORM"] = base["E_MAIL"].str.strip().str.lower().str.rstrip(",")
    base["DOMINIO"] = (
        base["E_MAIL_NORM"].where(base["E_MAIL_NORM"].str.contains("@", regex=False), "")
        .str.split("@", n=1)
        .str[-1]
        .fillna("")
    )

    non_empty_email = base[base["E_MAIL_NORM"] != ""].copy()
    email_counts = non_empty_email["E_MAIL_NORM"].value_counts()

    repeated_email_counts = email_counts[email_counts > 1]

    base["QTD_REPETICOES_EMAIL"] = base["E_MAIL_NORM"].map(email_counts).fillna(0).astype(int)
    base["EMAIL_REPETIDO"] = base["QTD_REPETICOES_EMAIL"] > 1

    classification = base["E_MAIL_NORM"].apply(classify_email)
    base["SUSPEITO_RAZOES"] = classification.apply(lambda x: ";".join(x))
    base["EMAIL_SUSPEITO"] = base["SUSPEITO_RAZOES"] != ""
    base["EMAIL_FORMATO_VALIDO"] = base["E_MAIL_NORM"].apply(lambda x: bool(EMAIL_REGEX.match(x)))
    base["FAMILIA_DOMINIO"] = base["DOMINIO"].apply(domain_family)
    base["FAIXA_REPETICAO"] = base["QTD_REPETICOES_EMAIL"].apply(repeat_bucket)
    base["UF_REGIAO"] = base["REGIAO"].apply(extract_brazil_uf)

    base["STATUS_EMAIL"] = "Unico limpo"
    base.loc[base["QTD_REPETICOES_EMAIL"] > 1, "STATUS_EMAIL"] = "Repetido"
    base.loc[base["EMAIL_SUSPEITO"], "STATUS_EMAIL"] = "Suspeito"
    base.loc[(base["E_MAIL_NORM"] != "") & (~base["EMAIL_FORMATO_VALIDO"]), "STATUS_EMAIL"] = "Invalido"
    base.loc[base["E_MAIL_NORM"] == "", "STATUS_EMAIL"] = "Sem email"

    repeated_rows = base[base["EMAIL_REPETIDO"]].copy().sort_values(
        by=["QTD_REPETICOES_EMAIL", "E_MAIL_NORM"], ascending=[False, True]
    )
    unique_email_rows = base[base["E_MAIL_NORM"] != ""].drop_duplicates(subset=["E_MAIL_NORM"], keep="first").copy()
    suspect_rows = base[base["EMAIL_SUSPEITO"]].copy()
    invalid_rows = base[(base["E_MAIL_NORM"] != "") & (~base["EMAIL_FORMATO_VALIDO"])].copy()

    repeated_summary = (
        repeated_email_counts.rename_axis("E_MAIL_NORM")
        .reset_index(name="QTD_REPETICOES_EMAIL")
        .sort_values(by=["QTD_REPETICOES_EMAIL", "E_MAIL_NORM"], ascending=[False, True])
    )

    domain_series = (
        non_empty_email[non_empty_email["E_MAIL_NORM"].str.contains("@", regex=False)]["E_MAIL_NORM"]
        .str.split("@", n=1)
        .str[1]
    )
    top_domains = domain_series.value_counts().rename_axis("DOMINIO").reset_index(name="QUANTIDADE")

    gmail_like = int(domain_series.str.contains("gmail", regex=False).sum())
    hotmail_like = int(domain_series.str.contains(r"hotmail|live|outlook|msn", regex=True).sum())
    yahoo_like = int(domain_series.str.contains(r"yahoo|ymail|yahool", regex=True).sum())

    doc_emails = (
        base[(base["CPF_CNPJ_NORM"] != "") & (base["E_MAIL_NORM"] != "")]
        .groupby("CPF_CNPJ_NORM")["E_MAIL_NORM"]
        .nunique()
    )
    unique_clients = int(base.loc[base["CPF_CNPJ_NORM"] != "", "CPF_CNPJ_NORM"].nunique())
    clients_with_multi_email = int((doc_emails > 1).sum()) if len(doc_emails) else 0

    metrics = {
        "total_rows": int(len(base)),
        "emails_total": int((base["E_MAIL_NORM"] != "").sum()),
        "emails_unique": int(base["E_MAIL_NORM"].nunique() - (1 if "" in set(base["E_MAIL_NORM"]) else 0)),
        "repeated_distinct": int(len(repeated_email_counts)),
        "repeated_rows": int(len(repeated_rows)),
        "invalid_format_rows": int(len(invalid_rows)),
        "suspect_rows": int(len(suspect_rows)),
        "unique_clients": unique_clients,
        "clients_multi_email": clients_with_multi_email,
        "gmail_like": gmail_like,
        "hotmail_like": hotmail_like,
        "yahoo_like": yahoo_like,
    }

    return {
        "metrics": metrics,
        "base": base,
        "repeated_rows": repeated_rows,
        "repeated_summary": repeated_summary,
        "unique_email_rows": unique_email_rows,
        "suspect_rows": suspect_rows,
        "invalid_rows": invalid_rows,
        "top_domains": top_domains,
    }


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def render_download(label: str, df: pd.DataFrame, file_name: str) -> None:
    st.download_button(label=label, data=to_csv_bytes(df), file_name=file_name, mime="text/csv")


def format_number(value: int) -> str:
    return f"{value:,}"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        :root {
            --bg-main: #020617;
            --bg-soft: #0b1220;
            --panel: rgba(15, 23, 42, 0.76);
            --panel-strong: rgba(15, 23, 42, 0.92);
            --ink: #e8eef7;
            --muted: #9fb2c8;
            --line: #334155;
            --accent: #22d3ee;
            --accent-soft: rgba(34, 211, 238, 0.14);
            --warm: #f59e0b;
        }

        .stApp {
            background:
                radial-gradient(1100px 380px at 12% -12%, rgba(34, 211, 238, 0.22) 0%, transparent 58%),
                radial-gradient(920px 340px at 94% -8%, rgba(56, 189, 248, 0.12) 0%, transparent 52%),
                linear-gradient(180deg, var(--bg-main) 0%, var(--bg-soft) 100%);
            color: var(--ink);
        }

        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 1220px;
            padding-top: 1.35rem;
            padding-bottom: 2rem;
        }

        html, body, [class*="css"] {
            font-family: "Space Grotesk", sans-serif;
        }

        h1, h2, h3 {
            color: var(--ink);
            letter-spacing: -0.02em;
        }

        [data-testid="stFileUploader"] {
            border-radius: 16px;
            border: 1px dashed #475569;
            background: var(--panel);
            padding: 0.25rem 0.6rem 0.55rem 0.6rem;
            backdrop-filter: blur(4px);
        }

        [data-baseweb="select"] > div {
            border-radius: 12px !important;
            border: 1px solid var(--line) !important;
            background: var(--panel-strong) !important;
            min-height: 44px !important;
            opacity: 1 !important;
        }

        [data-baseweb="select"] * {
            color: var(--ink) !important;
            opacity: 1 !important;
            fill: var(--ink) !important;
        }

        [data-baseweb="select"] span {
            color: var(--ink) !important;
            font-weight: 600 !important;
        }

        [role="listbox"] {
            background: #0f172a !important;
            border: 1px solid var(--line) !important;
        }

        [role="option"] {
            color: var(--ink) !important;
            background: #0f172a !important;
        }

        [role="option"][aria-selected="true"] {
            background: rgba(34, 211, 238, 0.18) !important;
        }

        [data-testid="stWidgetLabel"] p {
            color: var(--ink) !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em;
        }

        [data-testid="stTextInput"] input {
            color: var(--ink) !important;
            background: var(--panel-strong) !important;
            border-radius: 12px !important;
            border: 1px solid var(--line) !important;
            font-weight: 600 !important;
        }

        [data-testid="stForm"] {
            border: 1px solid var(--line);
            background: rgba(15, 23, 42, 0.72);
            border-radius: 16px;
            padding: 0.6rem 0.75rem 0.25rem 0.75rem;
        }

        [data-testid="stForm"] [data-testid="baseButton-primary"] {
            border-radius: 12px;
            font-weight: 700;
            background: linear-gradient(135deg, #0b7285, #0f9ab3) !important;
            border: 1px solid transparent !important;
        }

        [data-testid="stForm"] [data-testid="baseButton-secondary"] {
            border-radius: 12px;
            font-weight: 700;
            border: 1px solid var(--line) !important;
            background: rgba(15, 23, 42, 0.92) !important;
            color: var(--ink) !important;
        }

        [data-testid="stDataFrame"] {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.35rem;
            backdrop-filter: blur(5px);
        }

        [data-testid="stDownloadButton"] button {
            border-radius: 12px;
            border: 1px solid transparent;
            background: linear-gradient(135deg, #0b7285, #0f9ab3);
            color: white;
            font-weight: 600;
            transition: transform 0.16s ease, box-shadow 0.16s ease;
        }

        [data-testid="stDownloadButton"] button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 22px rgba(11, 114, 133, 0.24);
        }

        .hero-panel {
            border-radius: 24px;
            border: 1px solid var(--line);
            background: linear-gradient(128deg, rgba(15, 23, 42, 0.95), rgba(15, 23, 42, 0.72));
            padding: 1.1rem 1.35rem 1.25rem 1.35rem;
            box-shadow: 0 18px 45px rgba(2, 6, 23, 0.45);
            animation: fadeUp 0.5s ease-out;
        }

        .hero-kicker {
            display: inline-block;
            background: var(--accent-soft);
            color: var(--accent);
            border: 1px solid rgba(11, 114, 133, 0.25);
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.18rem 0.62rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }

        .hero-title {
            font-size: 1.82rem;
            font-weight: 700;
            line-height: 1.12;
            margin: 0;
            color: var(--ink);
        }

        .hero-sub {
            margin-top: 0.5rem;
            color: var(--muted);
            font-size: 0.99rem;
        }

        .metric-card {
            border-radius: 18px;
            border: 1px solid var(--line);
            background: var(--panel-strong);
            padding: 0.92rem 0.95rem 0.86rem 0.95rem;
            min-height: 112px;
            box-shadow: 0 10px 28px rgba(2, 6, 23, 0.36);
            animation: fadeUp 0.45s ease-out;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 600;
        }

        .metric-value {
            font-family: "IBM Plex Mono", monospace;
            color: var(--ink);
            font-size: 1.75rem;
            margin-top: 0.36rem;
            font-weight: 500;
            line-height: 1.1;
        }

        .metric-foot {
            color: var(--warm);
            font-size: 0.77rem;
            margin-top: 0.34rem;
            font-weight: 600;
        }

        .section-head {
            margin-top: 0.2rem;
            margin-bottom: 0.35rem;
            color: var(--ink);
            font-size: 1.45rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .tiny-note {
            color: var(--muted);
            margin-bottom: 0.6rem;
            font-size: 0.92rem;
        }

        .dashboard-panel {
            border-radius: 18px;
            border: 1px solid var(--line);
            background: rgba(15, 23, 42, 0.88);
            padding: 0.7rem 0.85rem 0.45rem 0.85rem;
            box-shadow: 0 10px 26px rgba(2, 6, 23, 0.4);
        }

        .panel-title {
            font-size: 0.92rem;
            text-transform: uppercase;
            letter-spacing: 0.045em;
            font-weight: 700;
            color: var(--muted);
            margin-bottom: 0.25rem;
        }

        .panel-title-main {
            font-size: 1rem;
            font-weight: 700;
            color: var(--ink);
            margin-bottom: 0.12rem;
            letter-spacing: -0.01em;
        }

        .panel-sub {
            font-size: 0.82rem;
            color: var(--muted);
            margin-bottom: 0.38rem;
        }

        .stTabs [role="tablist"] {
            gap: 0.35rem;
        }

        .stTabs [role="tab"] {
            border: 1px solid var(--line);
            background: rgba(15, 23, 42, 0.7);
            border-radius: 999px;
            padding: 0.18rem 0.95rem;
            font-weight: 600;
            color: var(--muted);
        }

        .stTabs [aria-selected="true"] {
            color: var(--accent);
            border-color: rgba(11, 114, 133, 0.35);
            background: var(--accent-soft);
        }

        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 960px) {
            .hero-title { font-size: 1.5rem; }
            .metric-value { font-size: 1.4rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_row(items: list[tuple[str, int, str]]) -> None:
    cols = st.columns(len(items))
    for idx, item in enumerate(items):
        label, value, foot = item
        cols[idx].markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{format_number(value)}</div>
                <div class="metric-foot">{foot}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="Analise de Emails", layout="wide", initial_sidebar_state="collapsed")
    inject_styles()
    st.markdown(
        """
        <div class="hero-panel">
            <span class="hero-kicker">Data Quality Studio</span>
            <h1 class="hero-title">Sistema Profissional de Analise de E-mails</h1>
            <p class="hero-sub">
                Upload de CSV/XLSX com leitura automatica, mapa de colunas, indicadores executivos,
                tabela de dominios, repetidos, suspeitos e exportacao pronta em CSV.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("Selecione o arquivo", type=["csv", "xlsx", "xls"])
    if not uploaded_file:
        st.info("Envie um arquivo para iniciar a analise.")
        return

    try:
        df = read_table(uploaded_file)
    except Exception as exc:
        st.error(f"Falha ao ler arquivo: {exc}")
        return

    st.success(f"Arquivo carregado: {format_number(len(df))} linhas e {len(df.columns)} colunas.")
    with st.expander("Visualizar primeiras linhas"):
        st.dataframe(df.head(20), use_container_width=True)

    guessed = guess_columns(df)
    options = ["(nao usar)"] + list(df.columns)

    st.subheader("Mapeamento de colunas")
    selected: dict[str, str | None] = {}
    cols = st.columns(5)
    for idx, field in enumerate(FIELD_LABELS):
        default_col = guessed.get(field)
        default_index = options.index(default_col) if default_col in options else 0
        choice = cols[idx].selectbox(FIELD_LABELS[field], options=options, index=default_index, key=f"map_{field}")
        selected[field] = None if choice == "(nao usar)" else choice

    if not selected.get("email"):
        st.error("Selecione a coluna de e-mail para continuar.")
        return

    result = build_analysis(df, selected)
    metrics = result["metrics"]

    tab_overview, tab_quality, tab_export = st.tabs(["Visao geral", "Qualidade", "Exportar"])

    with tab_overview:
        st.markdown('<div class="section-head">Resumo executivo</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tiny-note">Indicadores principais para leitura rapida da base atual.</div>',
            unsafe_allow_html=True,
        )

        # filtros interativos (aplicacao manual via botao)
        dashboard_df = result["base"][result["base"]["E_MAIL_NORM"] != ""].copy()
        origem_opts = sorted([v for v in dashboard_df["ORIGEM"].dropna().unique().tolist() if v])
        regiao_opts = sorted([v for v in dashboard_df["REGIAO"].dropna().unique().tolist() if v])
        fam_opts = sorted([v for v in dashboard_df["FAMILIA_DOMINIO"].dropna().unique().tolist() if v])
        status_opts = sorted(dashboard_df["STATUS_EMAIL"].dropna().unique().tolist())

        default_filters = {
            "origem": "Todos",
            "regiao": "Todas",
            "familia": "Todas",
            "status": "Todos",
            "busca": "",
        }
        if "dashboard_filters" not in st.session_state:
            st.session_state["dashboard_filters"] = default_filters.copy()

        active_filters = st.session_state["dashboard_filters"]
        origem_choices = ["Todos"] + origem_opts
        regiao_choices = ["Todas"] + regiao_opts
        familia_choices = ["Todas"] + fam_opts
        status_choices = ["Todos"] + status_opts

        with st.form("overview_filters_form"):
            st.markdown(
                '<div class="tiny-note">Defina os filtros e clique em <b>Aplicar filtros</b> para atualizar os dashboards.</div>',
                unsafe_allow_html=True,
            )
            filter_cols = st.columns(5)
            with filter_cols[0]:
                origem_choice = st.selectbox(
                    "Origem",
                    origem_choices,
                    index=origem_choices.index(active_filters["origem"]) if active_filters["origem"] in origem_choices else 0,
                    key="flt_origem",
                )
            with filter_cols[1]:
                regiao_choice = st.selectbox(
                    "Regiao",
                    regiao_choices,
                    index=regiao_choices.index(active_filters["regiao"]) if active_filters["regiao"] in regiao_choices else 0,
                    key="flt_regiao",
                )
            with filter_cols[2]:
                familia_choice = st.selectbox(
                    "Familia de dominio",
                    familia_choices,
                    index=familia_choices.index(active_filters["familia"]) if active_filters["familia"] in familia_choices else 0,
                    key="flt_familia",
                )
            with filter_cols[3]:
                status_choice = st.selectbox(
                    "Status de e-mail",
                    status_choices,
                    index=status_choices.index(active_filters["status"]) if active_filters["status"] in status_choices else 0,
                    key="flt_status",
                )
            with filter_cols[4]:
                search_value = st.text_input(
                    "Busca (nome/email)",
                    value=active_filters["busca"],
                    placeholder="Ex: joao ou @gmail",
                    key="flt_busca",
                )

            action_cols = st.columns([1.2, 1.0, 3.8])
            apply_filters = action_cols[0].form_submit_button(
                "Aplicar filtros",
                type="primary",
                use_container_width=True,
            )
            clear_filters = action_cols[1].form_submit_button("Limpar", use_container_width=True)

        if clear_filters:
            st.session_state["dashboard_filters"] = default_filters.copy()
            st.rerun()

        if apply_filters:
            st.session_state["dashboard_filters"] = {
                "origem": origem_choice,
                "regiao": regiao_choice,
                "familia": familia_choice,
                "status": status_choice,
                "busca": search_value,
            }

        active_filters = st.session_state["dashboard_filters"]
        st.markdown(
            f"""
            <div class="tiny-note">
                <b>Filtros ativos:</b>
                origem={active_filters["origem"]} |
                regiao={active_filters["regiao"]} |
                familia={active_filters["familia"]} |
                status={active_filters["status"]} |
                busca={active_filters["busca"] or "-"}
            </div>
            """,
            unsafe_allow_html=True,
        )

        filtered = dashboard_df.copy()
        if active_filters["origem"] != "Todos":
            filtered = filtered[filtered["ORIGEM"] == active_filters["origem"]]
        if active_filters["regiao"] != "Todas":
            filtered = filtered[filtered["REGIAO"] == active_filters["regiao"]]
        if active_filters["familia"] != "Todas":
            filtered = filtered[filtered["FAMILIA_DOMINIO"] == active_filters["familia"]]
        if active_filters["status"] != "Todos":
            filtered = filtered[filtered["STATUS_EMAIL"] == active_filters["status"]]
        if active_filters["busca"].strip():
            pattern = active_filters["busca"].strip().lower()
            filtered = filtered[
                filtered["NOME"].str.lower().str.contains(pattern, na=False)
                | filtered["E_MAIL_NORM"].str.contains(pattern, na=False)
            ]

        filtered_total_rows = int(len(filtered))
        filtered_total_clients = int(filtered.loc[filtered["CPF_CNPJ_NORM"] != "", "CPF_CNPJ_NORM"].nunique())
        filtered_total_emails = int((filtered["E_MAIL_NORM"] != "").sum())

        filtered_no_repeat_email = filtered[filtered["E_MAIL_NORM"] != ""].drop_duplicates(
            subset=["E_MAIL_NORM"], keep="first"
        )
        filtered_rows_unique_no_repeat = int(len(filtered_no_repeat_email))
        filtered_clients_unique_no_repeat = int(
            filtered_no_repeat_email.loc[filtered_no_repeat_email["CPF_CNPJ_NORM"] != "", "CPF_CNPJ_NORM"].nunique()
        )
        filtered_emails_unique_no_repeat = int(filtered_no_repeat_email["E_MAIL_NORM"].nunique())

        client_email_counts = (
            filtered[(filtered["CPF_CNPJ_NORM"] != "") & (filtered["E_MAIL_NORM"] != "")]
            .groupby("CPF_CNPJ_NORM")["E_MAIL_NORM"]
            .nunique()
            .reset_index(name="QTD_EMAILS")
            .sort_values(by=["QTD_EMAILS", "CPF_CNPJ_NORM"], ascending=[False, True])
        )
        names_by_doc = (
            filtered[(filtered["CPF_CNPJ_NORM"] != "") & (filtered["NOME"] != "")][["CPF_CNPJ_NORM", "NOME"]]
            .drop_duplicates(subset=["CPF_CNPJ_NORM"], keep="first")
        )
        client_email_counts = client_email_counts.merge(names_by_doc, on="CPF_CNPJ_NORM", how="left")
        client_email_counts["NOME"] = client_email_counts["NOME"].fillna("")

        clients_two_or_more_df = client_email_counts[client_email_counts["QTD_EMAILS"] >= 2].copy()
        clients_exactly_two = int((client_email_counts["QTD_EMAILS"] == 2).sum())
        clients_two_or_more = int(len(clients_two_or_more_df))

        render_metric_row(
            [
                ("Total de linhas", filtered_total_rows, "Registros no filtro atual"),
                ("Total de clientes", filtered_total_clients, "Por CPF/CNPJ"),
                ("Total de e-mails", filtered_total_emails, "Com e-mail preenchido"),
            ]
        )
        render_metric_row(
            [
                ("Linhas unicas sem repeticao", filtered_rows_unique_no_repeat, "Uma linha por e-mail"),
                ("Clientes unicos sem repeticao", filtered_clients_unique_no_repeat, "No recorte sem e-mail duplicado"),
                ("E-mails unicos sem repeticao", filtered_emails_unique_no_repeat, "E-mails distintos"),
            ]
        )
        render_metric_row(
            [
                ("Clientes com 2+ e-mails", clients_two_or_more, "Clientes com mais de um e-mail"),
                ("Clientes com exatamente 2 e-mails", clients_exactly_two, "Foco para revisao rapida"),
            ]
        )

        st.markdown("**Clientes com 2+ e-mails e quantidade por cliente**")
        st.dataframe(
            clients_two_or_more_df[["CPF_CNPJ_NORM", "NOME", "QTD_EMAILS"]],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown('<div class="section-head">Painel interativo</div>', unsafe_allow_html=True)

        chart_col_1, chart_col_2, chart_col_3 = st.columns([1.1, 1.1, 1.8])
        status_counts = (
            filtered["STATUS_EMAIL"].value_counts().rename_axis("STATUS").reset_index(name="QUANTIDADE")
        )
        total_status = int(status_counts["QUANTIDADE"].sum())
        if total_status > 0:
            status_counts["PERCENTUAL"] = (status_counts["QUANTIDADE"] / total_status) * 100
        else:
            status_counts["PERCENTUAL"] = 0.0
        status_counts = status_counts.sort_values("PERCENTUAL", ascending=True)
        status_counts["LABEL_STATUS"] = status_counts.apply(
            lambda row: f"{row['QUANTIDADE']:,} ({row['PERCENTUAL']:.1f}%)", axis=1
        )
        family_counts = (
            filtered["FAMILIA_DOMINIO"].value_counts().rename_axis("FAMILIA").reset_index(name="QUANTIDADE")
        )
        total_familia = int(family_counts["QUANTIDADE"].sum())
        if total_familia > 0:
            family_counts["PERCENTUAL"] = (family_counts["QUANTIDADE"] / total_familia) * 100
        else:
            family_counts["PERCENTUAL"] = 0.0
        family_counts = family_counts.sort_values("QUANTIDADE", ascending=True)
        family_counts["LABEL_FAMILIA"] = family_counts.apply(
            lambda row: f"{row['QUANTIDADE']:,} ({row['PERCENTUAL']:.1f}%)", axis=1
        )
        top_domain_counts = (
            filtered[filtered["DOMINIO"] != ""]["DOMINIO"].value_counts().head(10).rename_axis("DOMINIO").reset_index(name="QUANTIDADE")
        )
        top_domain_counts = top_domain_counts.sort_values("QUANTIDADE", ascending=True)
        top_domain_counts["LABEL_DOMINIO"] = top_domain_counts["QUANTIDADE"].map(lambda x: f"{x:,}")

        with chart_col_1:
            st.markdown(
                """
                <div class="dashboard-panel">
                    <div class="panel-title-main">Dashboard 1: Distribuicao por status</div>
                    <div class="panel-sub">Mostra quantos e-mails estao limpos, repetidos, suspeitos ou invalidos.</div>
                    <div class="panel-title">Status</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig_status = px.bar(
                status_counts,
                x="PERCENTUAL",
                y="STATUS",
                orientation="h",
                color="STATUS",
                color_discrete_sequence=["#0b7285", "#14b8a6", "#c67622", "#ef4444", "#64748b"],
                text="LABEL_STATUS",
            )
            status_max = float(status_counts["PERCENTUAL"].max()) if not status_counts.empty else 0.0
            right_limit = max(status_max * 1.35, 10.0)
            fig_status.update_layout(showlegend=False, height=320, xaxis_title="Percentual (%)", yaxis_title="Status")
            fig_status.update_traces(textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#E2E8F0"))
            fig_status.update_xaxes(range=[0, right_limit], ticksuffix="%", rangemode="tozero", automargin=True)
            fig_status.update_yaxes(automargin=True)
            st.plotly_chart(
                build_plot_theme(fig_status, margin_left=150, margin_right=110),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

        with chart_col_2:
            st.markdown(
                """
                <div class="dashboard-panel">
                    <div class="panel-title-main">Dashboard 2: Familia de dominio</div>
                    <div class="panel-sub">Agrupa os e-mails por provedores (Gmail, Outlook, Yahoo, CRECI e outros).</div>
                    <div class="panel-title">Familia de dominio</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig_family = px.bar(
                family_counts,
                x="QUANTIDADE",
                y="FAMILIA",
                orientation="h",
                color="FAMILIA",
                color_discrete_sequence=["#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#6366f1", "#6b7280"],
                text="LABEL_FAMILIA",
            )
            max_family = int(family_counts["QUANTIDADE"].max()) if not family_counts.empty else 0
            fig_family.update_layout(showlegend=False, height=320, xaxis_title="Quantidade", yaxis_title="Familia")
            fig_family.update_traces(textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#E2E8F0"))
            fig_family.update_xaxes(range=[0, max(max_family * 1.25, 1)], automargin=True)
            fig_family.update_yaxes(automargin=True)
            st.plotly_chart(
                build_plot_theme(fig_family, margin_left=170, margin_right=110),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

        with chart_col_3:
            st.markdown(
                """
                <div class="dashboard-panel">
                    <div class="panel-title-main">Dashboard 3: Top dominios por volume</div>
                    <div class="panel-sub">Ranking dos dominios de e-mail com maior quantidade no recorte atual.</div>
                    <div class="panel-title">Top dominios</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig_domain = px.bar(
                top_domain_counts,
                x="QUANTIDADE",
                y="DOMINIO",
                orientation="h",
                color="QUANTIDADE",
                color_continuous_scale=["#9be7dc", "#16a085", "#0b7285"],
                text="LABEL_DOMINIO",
            )
            max_domain = int(top_domain_counts["QUANTIDADE"].max()) if not top_domain_counts.empty else 0
            fig_domain.update_layout(
                showlegend=False,
                height=320,
                xaxis_title="Quantidade",
                yaxis_title="Dominio",
                coloraxis_showscale=False,
            )
            fig_domain.update_traces(textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#E2E8F0"))
            fig_domain.update_xaxes(range=[0, max(max_domain * 1.25, 1)], automargin=True)
            fig_domain.update_yaxes(automargin=True)
            st.plotly_chart(
                build_plot_theme(fig_domain, margin_left=220, margin_right=110),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

        bottom_col_1, bottom_col_2 = st.columns(2)
        with bottom_col_1:
            repeated_top_df = (
                filtered[filtered["QTD_REPETICOES_EMAIL"] > 1][["E_MAIL_NORM", "QTD_REPETICOES_EMAIL"]]
                .drop_duplicates()
                .sort_values(by=["QTD_REPETICOES_EMAIL", "E_MAIL_NORM"], ascending=[False, True])
                .head(10)
                .copy()
            )
            repeated_top_df["EMAIL_EXIBICAO"] = repeated_top_df["E_MAIL_NORM"].apply(
                lambda x: x if len(x) <= 44 else f"{x[:41]}..."
            )
            repeated_top_df = repeated_top_df.sort_values("QTD_REPETICOES_EMAIL", ascending=True)
            repeated_top_df["LABEL_REP"] = repeated_top_df["QTD_REPETICOES_EMAIL"].map(lambda x: f"{x:,}")
            st.markdown(
                """
                <div class="dashboard-panel">
                    <div class="panel-title-main">Dashboard 4: Top 10 e-mails repetidos</div>
                    <div class="panel-sub">Lista os e-mails mais reincidentes para acao imediata de saneamento.</div>
                    <div class="panel-title">Top repetidos</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig_repeated = px.bar(
                repeated_top_df,
                x="QTD_REPETICOES_EMAIL",
                y="EMAIL_EXIBICAO",
                orientation="h",
                color="QTD_REPETICOES_EMAIL",
                color_continuous_scale=["#dbeafe", "#22d3ee", "#0b7285"],
                text="LABEL_REP",
            )
            max_repeated = int(repeated_top_df["QTD_REPETICOES_EMAIL"].max()) if not repeated_top_df.empty else 0
            fig_repeated.update_layout(
                showlegend=False,
                height=320,
                xaxis_title="Quantidade de repeticoes",
                yaxis_title="E-mail",
                coloraxis_showscale=False,
            )
            fig_repeated.update_traces(textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#E2E8F0"))
            fig_repeated.update_xaxes(range=[0, max(max_repeated * 1.25, 1)], automargin=True)
            fig_repeated.update_yaxes(automargin=True)
            st.plotly_chart(
                build_plot_theme(fig_repeated, margin_left=230, margin_right=110),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

        with bottom_col_2:
            uf_df = (
                filtered[filtered["UF_REGIAO"] != ""]["UF_REGIAO"]
                .value_counts()
                .rename_axis("UF")
                .reset_index(name="QUANTIDADE")
            )
            uf_df["ESTADO"] = uf_df["UF"].map(UF_TO_STATE_NAME)
            uf_df["LAT"] = uf_df["UF"].map(lambda uf: UF_TO_COORD.get(uf, (None, None))[0])
            uf_df["LON"] = uf_df["UF"].map(lambda uf: UF_TO_COORD.get(uf, (None, None))[1])
            uf_df = uf_df.dropna(subset=["LAT", "LON"]).copy()
            uf_df["LABEL_QTD"] = uf_df["QUANTIDADE"].map(lambda x: f"{x:,}")
            st.markdown(
                """
                <div class="dashboard-panel">
                    <div class="panel-title-main">Dashboard 5: Mapa do Brasil por estado</div>
                    <div class="panel-sub">Visual moderno por UF para identificar rapidamente os estados com maior volume.</div>
                    <div class="panel-title">Mapa Brasil (UF)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if uf_df.empty:
                st.info("Nao foi possivel identificar UFs no campo de regiao para montar o mapa.")
            else:
                max_qtd = int(uf_df["QUANTIDADE"].max()) if not uf_df.empty else 1
                uf_df["BUBBLE_SIZE"] = 10 + (uf_df["QUANTIDADE"] / max(max_qtd, 1)) * 44
                uf_df["LABEL_LAT"] = uf_df["LAT"] + uf_df["UF"].map(lambda uf: UF_LABEL_OFFSET.get(uf, (0.0, 0.0))[0])
                uf_df["LABEL_LON"] = uf_df["LON"] + uf_df["UF"].map(lambda uf: UF_LABEL_OFFSET.get(uf, (0.0, 0.0))[1])

                fig_region = go.Figure()
                fig_region.add_trace(
                    go.Scattergeo(
                        lon=uf_df["LON"],
                        lat=uf_df["LAT"],
                        mode="markers",
                        marker=dict(
                            size=uf_df["BUBBLE_SIZE"],
                            color=uf_df["QUANTIDADE"],
                            colorscale=[[0, "#38bdf8"], [0.5, "#22d3ee"], [1, "#06b6d4"]],
                            cmin=0,
                            cmax=max(max_qtd, 1),
                            opacity=0.88,
                            line=dict(color="rgba(255,255,255,0.85)", width=1.2),
                            colorbar=dict(
                                title=dict(text="Qtd", font=dict(color="#E2E8F0")),
                                tickfont=dict(color="#E2E8F0"),
                            ),
                        ),
                        customdata=uf_df[["ESTADO", "QUANTIDADE"]],
                        hovertemplate="<b>%{text}</b><br>Estado: %{customdata[0]}<br>Quantidade: %{customdata[1]:,}<extra></extra>",
                        text=uf_df["UF"],
                        showlegend=False,
                    )
                )
                fig_region.add_trace(
                    go.Scattergeo(
                        lon=uf_df["LABEL_LON"],
                        lat=uf_df["LABEL_LAT"],
                        mode="text",
                        text=uf_df["UF"] + " - " + uf_df["ESTADO"],
                        textfont=dict(color="#E2E8F0", size=10, family="Space Grotesk"),
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )
                fig_region.update_geos(
                    scope="south america",
                    projection_type="mercator",
                    center=dict(lat=-14.2, lon=-52.4),
                    lataxis_range=[-35.2, 6.3],
                    lonaxis_range=[-74.8, -33.5],
                    showland=True,
                    landcolor="#0f172a",
                    showcountries=True,
                    countrycolor="rgba(148,163,184,0.45)",
                    showsubunits=True,
                    subunitcolor="rgba(148,163,184,0.35)",
                    showocean=True,
                    oceancolor="#020617",
                    showlakes=True,
                    lakecolor="#020617",
                    coastlinecolor="rgba(148,163,184,0.35)",
                    bgcolor="#020617",
                )
                fig_region.update_layout(
                    height=380,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E2E8F0"),
                    margin=dict(l=8, r=8, t=18, b=8),
                )
                st.plotly_chart(fig_region, use_container_width=True, config=PLOTLY_CONFIG)

                st.markdown("**Estados por quantidade (ordenado)**")
                st.dataframe(
                    uf_df.sort_values("QUANTIDADE", ascending=False)
                    [["UF", "ESTADO", "QUANTIDADE"]],
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown('<div class="section-head">Tabelas analiticas</div>', unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            st.dataframe(
                top_domain_counts.sort_values("QUANTIDADE", ascending=False).head(10),
                use_container_width=True,
            )
        with right:
            repeated_filtered = (
                filtered[filtered["QTD_REPETICOES_EMAIL"] > 1][["E_MAIL_NORM", "QTD_REPETICOES_EMAIL"]]
                .drop_duplicates()
                .sort_values(by=["QTD_REPETICOES_EMAIL", "E_MAIL_NORM"], ascending=[False, True])
                .head(10)
            )
            st.dataframe(repeated_filtered, use_container_width=True)

    with tab_quality:
        st.markdown('<div class="section-head">Qualidade e risco de contato</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tiny-note">Amostras para revisao manual de e-mails com risco de erro ou inconsistencias.</div>',
            unsafe_allow_html=True,
        )
        q1, q2 = st.columns(2)
        with q1:
            st.markdown("**Amostra de e-mails suspeitos**")
            st.dataframe(result["suspect_rows"].head(80), use_container_width=True)
        with q2:
            st.markdown("**Amostra de e-mails invalidos**")
            st.dataframe(result["invalid_rows"].head(80), use_container_width=True)

    with tab_export:
        st.markdown('<div class="section-head">Exportacao de relatorios</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="tiny-note">Baixe os arquivos para acao operacional, auditoria e tratativa de dados.</div>',
            unsafe_allow_html=True,
        )

        d1, d2, d3 = st.columns(3)
        with d1:
            render_download("Baixar base tratada", result["base"], "base_tratada.csv")
            render_download("Baixar e-mails unicos", result["unique_email_rows"], "emails_unicos.csv")
        with d2:
            render_download(
                "Baixar linhas com e-mails repetidos",
                result["repeated_rows"],
                "emails_repetidos_linhas.csv",
            )
            render_download(
                "Baixar resumo de repetidos",
                result["repeated_summary"],
                "emails_repetidos_resumo.csv",
            )
        with d3:
            render_download("Baixar e-mails suspeitos", result["suspect_rows"], "emails_suspeitos.csv")
            render_download("Baixar e-mails invalidos", result["invalid_rows"], "emails_invalidos.csv")


if __name__ == "__main__":
    main()
