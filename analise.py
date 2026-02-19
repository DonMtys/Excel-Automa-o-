from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


@dataclass
class AnalysisSummary:
    total_rows: int = 0
    unique_emails: int = 0
    invalid_emails: int = 0
    missing_emails: int = 0
    rows_with_trimmed_email: int = 0
    duplicate_exact_rows: int = 0


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def normalize_email(value: str | None) -> str:
    return normalize_text(value).lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze(input_path: Path, output_dir: Path) -> AnalysisSummary:
    output_dir.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    missing_emails = 0
    invalid_emails = 0
    rows_with_trimmed_email = 0
    duplicate_exact_rows = 0

    unique_emails: set[str] = set()
    domain_counter: Counter[str] = Counter()
    repeated_email_counter: Counter[str] = Counter()
    row_count_by_document: Counter[str] = Counter()
    unique_email_count_by_document: defaultdict[str, set[str]] = defaultdict(set)
    unique_email_count_by_taxpayer: defaultdict[str, set[str]] = defaultdict(set)

    invalid_rows: list[dict[str, str]] = []
    duplicate_rows: list[dict[str, str]] = []
    seen_exact_rows: set[tuple[str, str, str, str]] = set()

    treated_file_path = output_dir / "dados_tratados.csv"
    with input_path.open("r", encoding="utf-8-sig", newline="") as src, treated_file_path.open(
        "w", encoding="utf-8", newline=""
    ) as treated_file:
        reader = csv.DictReader(src)
        if reader.fieldnames is None:
            raise ValueError("Arquivo CSV sem cabecalho.")

        original_fieldnames = reader.fieldnames
        treated_fieldnames = original_fieldnames + [
            "EMAIL_TRATADO",
            "EMAIL_VALIDO",
            "LINHA_DUPLICADA_EXATA",
        ]
        treated_writer = csv.DictWriter(treated_file, fieldnames=treated_fieldnames)
        treated_writer.writeheader()

        for line_number, row in enumerate(reader, start=2):
            total_rows += 1

            creditor_name = normalize_text(row.get("NOME_CREDOR"))
            document = normalize_text(row.get("CPF_CNPJ"))
            taxpayer = normalize_text(row.get("NOME_CONTRIBUINTE"))
            raw_email = row.get("E-MAIL") or ""
            clean_email = normalize_email(raw_email)
            email_had_trailing_or_leading_spaces = raw_email != raw_email.strip()

            if email_had_trailing_or_leading_spaces:
                rows_with_trimmed_email += 1

            row_count_by_document[document] += 1
            repeated_email_counter[clean_email] += 1

            if not clean_email:
                missing_emails += 1
                email_is_valid = False
            else:
                unique_emails.add(clean_email)
                email_is_valid = is_valid_email(clean_email)
                if email_is_valid:
                    if "@" in clean_email:
                        domain_counter[clean_email.split("@", 1)[1]] += 1
                    unique_email_count_by_document[document].add(clean_email)
                    unique_email_count_by_taxpayer[taxpayer].add(clean_email)
                else:
                    invalid_emails += 1
                    invalid_rows.append(
                        {
                            "LINHA_CSV": str(line_number),
                            "NOME_CREDOR": creditor_name,
                            "CPF_CNPJ": document,
                            "NOME_CONTRIBUINTE": taxpayer,
                            "E_MAIL_ORIGINAL": raw_email,
                            "E_MAIL_TRATADO": clean_email,
                        }
                    )

            row_identity = (creditor_name, document, taxpayer, clean_email)
            is_duplicate_exact = row_identity in seen_exact_rows
            if is_duplicate_exact:
                duplicate_exact_rows += 1
                duplicate_rows.append(
                    {
                        "LINHA_CSV": str(line_number),
                        "NOME_CREDOR": creditor_name,
                        "CPF_CNPJ": document,
                        "NOME_CONTRIBUINTE": taxpayer,
                        "E_MAIL_TRATADO": clean_email,
                    }
                )
            else:
                seen_exact_rows.add(row_identity)

            treated_writer.writerow(
                {
                    **row,
                    "EMAIL_TRATADO": clean_email,
                    "EMAIL_VALIDO": "SIM" if email_is_valid else "NAO",
                    "LINHA_DUPLICADA_EXATA": "SIM" if is_duplicate_exact else "NAO",
                }
            )

    top_domains = [
        {"DOMINIO": domain, "QUANTIDADE": str(count)}
        for domain, count in domain_counter.most_common(20)
    ]
    top_repeated_emails = [
        {"E_MAIL": email, "QUANTIDADE": str(count)}
        for email, count in repeated_email_counter.most_common(20)
        if email
    ]
    top_documents_by_rows = [
        {"CPF_CNPJ": document, "TOTAL_LINHAS": str(count)}
        for document, count in row_count_by_document.most_common(20)
        if document
    ]
    top_documents_by_unique_emails = [
        {"CPF_CNPJ": document, "E_MAILS_UNICOS": str(len(emails))}
        for document, emails in sorted(
            unique_email_count_by_document.items(), key=lambda item: len(item[1]), reverse=True
        )[:20]
        if document
    ]
    top_taxpayer_by_unique_emails = [
        {"NOME_CONTRIBUINTE": taxpayer, "E_MAILS_UNICOS": str(len(emails))}
        for taxpayer, emails in sorted(
            unique_email_count_by_taxpayer.items(), key=lambda item: len(item[1]), reverse=True
        )[:20]
        if taxpayer
    ]

    write_csv(output_dir / "top_dominios.csv", ["DOMINIO", "QUANTIDADE"], top_domains)
    write_csv(output_dir / "top_emails_repetidos.csv", ["E_MAIL", "QUANTIDADE"], top_repeated_emails)
    write_csv(output_dir / "top_documentos_por_linhas.csv", ["CPF_CNPJ", "TOTAL_LINHAS"], top_documents_by_rows)
    write_csv(
        output_dir / "top_documentos_por_emails_unicos.csv",
        ["CPF_CNPJ", "E_MAILS_UNICOS"],
        top_documents_by_unique_emails,
    )
    write_csv(
        output_dir / "top_contribuintes_por_emails_unicos.csv",
        ["NOME_CONTRIBUINTE", "E_MAILS_UNICOS"],
        top_taxpayer_by_unique_emails,
    )
    write_csv(
        output_dir / "emails_invalidos.csv",
        ["LINHA_CSV", "NOME_CREDOR", "CPF_CNPJ", "NOME_CONTRIBUINTE", "E_MAIL_ORIGINAL", "E_MAIL_TRATADO"],
        invalid_rows,
    )
    write_csv(
        output_dir / "linhas_duplicadas_exatas.csv",
        ["LINHA_CSV", "NOME_CREDOR", "CPF_CNPJ", "NOME_CONTRIBUINTE", "E_MAIL_TRATADO"],
        duplicate_rows,
    )

    summary = AnalysisSummary(
        total_rows=total_rows,
        unique_emails=len(unique_emails),
        invalid_emails=invalid_emails,
        missing_emails=missing_emails,
        rows_with_trimmed_email=rows_with_trimmed_email,
        duplicate_exact_rows=duplicate_exact_rows,
    )

    summary_file = output_dir / "resumo.txt"
    with summary_file.open("w", encoding="utf-8") as file:
        file.write("RESUMO DA ANALISE\n")
        file.write(f"Arquivo de origem: {input_path}\n")
        file.write(f"Total de linhas: {summary.total_rows}\n")
        file.write(f"E-mails unicos: {summary.unique_emails}\n")
        file.write(f"E-mails invalidos: {summary.invalid_emails}\n")
        file.write(f"E-mails ausentes: {summary.missing_emails}\n")
        file.write(f"E-mails com espacos no inicio/fim: {summary.rows_with_trimmed_email}\n")
        file.write(f"Linhas duplicadas exatas: {summary.duplicate_exact_rows}\n")

    return summary


def infer_default_csv_path() -> Path:
    expected = Path("E_MAIL-CLIENTES-18022026.csv")
    if expected.exists():
        return expected

    csv_files = sorted(Path(".").glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("Nenhum arquivo CSV encontrado no diretorio atual.")
    return csv_files[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Analise de base de e-mails de contribuintes.")
    parser.add_argument(
        "--arquivo",
        type=Path,
        default=infer_default_csv_path(),
        help="Caminho do CSV de entrada.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=Path("resultado_analise"),
        help="Diretorio onde os relatorios serao salvos.",
    )
    args = parser.parse_args()

    summary = analyze(args.arquivo, args.saida)
    print("Analise concluida.")
    print(f"Total de linhas: {summary.total_rows}")
    print(f"E-mails unicos: {summary.unique_emails}")
    print(f"E-mails invalidos: {summary.invalid_emails}")
    print(f"E-mails ausentes: {summary.missing_emails}")
    print(f"E-mails com espacos no inicio/fim: {summary.rows_with_trimmed_email}")
    print(f"Linhas duplicadas exatas: {summary.duplicate_exact_rows}")
    print(f"Arquivos gerados em: {args.saida.resolve()}")


if __name__ == "__main__":
    main()
