"""Parse ADIB bank and credit card statement CSVs into transaction dicts."""

import csv
import io
import re
from pathlib import Path

ACCOUNT_MAP: dict[str, str] = {
    "11404538810001": "Card-5747",
    "11404538810002": "810002",
    "11404538920001": "920001",
    "11404538920002": "920002",
}

SKIP_DESCRIPTIONS: set[str] = {
    "FOREIGN TRANSACTION FEE",
    "VAT ON FOREIGN TRANSACTIO",
    "AED TRF WITHIN UAE CHARGES",
    "PDC LODGEMENT CHARGE",
    "CASH ADVANCE FEE",
    "VAT ON CASH ADVANCE FEE",
    "FINANCE CHARGES",
}


def _read_file(filepath: str) -> str:
    """Read file with utf-8, falling back to latin-1."""
    path = Path(filepath)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _convert_date(date_str: str) -> str:
    """Convert DD/MM/YYYY to MM/DD/YYYY."""
    parts = date_str.strip().split("/")
    if len(parts) == 3:
        return f"{parts[1]}/{parts[0]}/{parts[2]}"
    return date_str


def _parse_amount(value: str) -> float:
    """Parse a numeric string, stripping commas and quotes."""
    cleaned = value.strip().strip('"').replace(",", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _should_skip(description: str) -> bool:
    """Return True if the description matches a fee/charge pattern to skip."""
    desc_upper = description.upper().strip()
    return any(pattern in desc_upper for pattern in SKIP_DESCRIPTIONS)


def parse_bank_csv(filepath: str) -> list[dict]:
    """Parse an ADIB bank account statement CSV.

    Expected format: 6 header lines (account info), then data rows with columns:
    Posting Date, Value Date, Reference No, Description, Debit Amount, Credit Amount, Balance
    """
    text = _read_file(filepath)
    lines = text.splitlines()

    # Extract account number from first line
    account_number = ""
    if lines:
        first_line = lines[0].strip().strip('"').strip(",").strip('"')
        # e.g. "Account Number: 11404538810001 AED"
        if "Account Number:" in first_line:
            part = first_line.split("Account Number:")[1].strip()
            account_number = part.split()[0].strip()

    account = ACCOUNT_MAP.get(account_number, account_number)

    # Skip the 6 header lines; row 7 is the column header
    data_lines = lines[6:]  # index 6 = column header row
    if not data_lines:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(data_lines)))
    transactions: list[dict] = []

    for row in reader:
        description = row.get("Description", "").strip().strip('"')
        if _should_skip(description):
            continue

        debit = _parse_amount(row.get("Debit Amount", "0"))
        credit = _parse_amount(row.get("Credit Amount", "0"))

        if debit == 0 and credit == 0:
            continue

        # Prefer Value Date, fall back to Posting Date
        value_date = (row.get("Value Date") or "").strip().strip('"')
        posting_date = (row.get("Posting Date") or "").strip().strip('"')
        raw_date = value_date if value_date else posting_date

        if credit > 0:
            amount = credit
            flow_type = "Inflow"
        else:
            amount = debit
            flow_type = "Outflow"

        transactions.append({
            "account": account,
            "date": _convert_date(raw_date),
            "amount": amount,
            "flow_type": flow_type,
            "description": description,
            "reference_no": (row.get("Reference No") or "").strip().strip('"'),
            "currency": "AED",
        })

    return transactions


def parse_cc_csv(filepath: str) -> list[dict]:
    """Parse an ADIB credit card statement CSV.

    Expected format: 5 header lines, then data rows with columns:
    Transaction Date, Description, Cr/Dr, Amount in AED
    Card header rows (Primary Card Number:...) are skipped.
    """
    text = _read_file(filepath)
    lines = text.splitlines()

    # Find the header row with column names
    header_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Transaction Date,"):
            header_idx = i
            break

    if header_idx is None:
        return []

    data_lines = lines[header_idx:]
    reader = csv.DictReader(io.StringIO("\n".join(data_lines)))
    transactions: list[dict] = []

    # Detect card number from card header rows
    card_account = "Card-5516"  # default
    for row in reader:
        description = row.get("Description", "").strip().strip('"')

        # Extract card number from header rows and skip them
        if not description:
            continue
        txn_date_field = (row.get("Transaction Date") or "").strip().strip('"')
        if "Card Number:" in txn_date_field:
            # CSV splits "Primary Card Number:4455XXXXXXXX0615-Islamic Emirati"
            # into the Transaction Date column
            match = re.search(r"XXXX(\d{4})", txn_date_field)
            if match:
                card_account = f"Card-{match.group(1)}"
            continue
        if "Card Number:" in description:
            match = re.search(r"XXXX(\d{4})", description)
            if match:
                card_account = f"Card-{match.group(1)}"
            continue

        if _should_skip(description):
            continue

        amount = _parse_amount(row.get("Amount in AED", "0"))
        if amount == 0:
            continue

        cr_dr = (row.get("Cr/Dr") or "").strip().strip('"').upper()
        flow_type = "Inflow" if cr_dr == "CR" else "Outflow"

        raw_date = (row.get("Transaction Date") or "").strip().strip('"')

        transactions.append({
            "account": card_account,
            "date": _convert_date(raw_date),
            "amount": amount,
            "flow_type": flow_type,
            "description": description,
            "reference_no": "",
            "currency": "AED",
        })

    return transactions
