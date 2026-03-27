"""
仕訳CSV生成サービス（汎用形式、UTF-8 BOM付き）。

1スケジュールにつき費目ごとに最大3行出力:
  - 賃料
  - 管理費（金額>0の場合）
  - 駐車場代（金額>0の場合）

仕訳パターンが費目に設定されている場合はパターン側の科目コードを優先し、
設定がない場合は契約マスタの debit/credit フィールドをフォールバックとして使用する。
"""
import csv
import io
import calendar
from decimal import Decimal
from config import Config

HEADERS = [
    "伝票日付",
    "借方勘定科目コード",
    "借方勘定科目名",
    "借方金額",
    "借方消費税区分",
    "借方消費税額",
    "貸方勘定科目コード",
    "貸方勘定科目名",
    "貸方金額",
    "摘要",
    "部門コード",
]


def _tax(amount: int, tax_type: str) -> int:
    if tax_type == "課税":
        return int(Decimal(str(amount)) * Config.CONSUMPTION_TAX_RATE)
    return 0


def _payment_date(year: int, month: int, payment_day: int) -> str:
    last_day = calendar.monthrange(year, month)[1]
    day = min(payment_day, last_day)
    return f"{year}/{month:02d}/{day:02d}"


def _make_row(date_str, debit_code, debit_name, amount, tax_type, tax_amount,
              credit_code, credit_name, summary, dept_code):
    return [
        date_str,
        debit_code or "",
        debit_name,
        amount + tax_amount,        # 借方金額（税込）
        tax_type,
        tax_amount,
        credit_code or "",
        credit_name,
        amount + tax_amount,        # 貸方金額（税込）
        summary,
        dept_code or "",
    ]


def _resolve_accounts(pattern, contract):
    """仕訳パターンまたは契約マスタから科目コード/名を返す"""
    if pattern:
        return (
            pattern.debit_account_code,
            pattern.debit_account_name,
            pattern.credit_account_code,
            pattern.credit_account_name,
            pattern.dept_code or (contract.dept_code if contract else ""),
        )
    if contract:
        return (
            contract.debit_account_code,
            contract.debit_account_name,
            contract.credit_account_code,
            contract.credit_account_name,
            contract.dept_code,
        )
    return ("", "地代家賃", "", "普通預金", "")


def generate_journal_csv(schedules: list) -> str:
    """
    仕訳CSVを文字列（UTF-8）で返す。
    呼び出し元で .encode('utf-8-sig') してダウンロードする。
    """
    from app import db
    from models import Contract, JournalPattern, Property

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(HEADERS)

    for s in schedules:
        contract = db.session.get(Contract, s.contract_id)
        prop = db.session.get(Property, s.property_id)
        prop_name = prop.name if prop else f"物件ID:{s.property_id}"

        date_str = _payment_date(s.payment_year, s.payment_month,
                                 contract.payment_day if contract else 25)
        base_summary = f"{prop_name} {s.payment_year}年{s.payment_month}月分"

        # パターン解決（費目ごと）
        rent_pat = (db.session.get(JournalPattern, contract.rent_journal_pattern_id)
                    if contract and contract.rent_journal_pattern_id else None)
        mgmt_pat = (db.session.get(JournalPattern, contract.mgmt_fee_journal_pattern_id)
                    if contract and contract.mgmt_fee_journal_pattern_id else None)
        park_pat = (db.session.get(JournalPattern, contract.parking_journal_pattern_id)
                    if contract and contract.parking_journal_pattern_id else None)

        # 賃料行
        d_code, d_name, c_code, c_name, dept = _resolve_accounts(rent_pat, contract)
        rent_tax = _tax(s.rent_amount, s.rent_tax_type)
        writer.writerow(_make_row(
            date_str, d_code, d_name,
            s.rent_amount, s.rent_tax_type, rent_tax,
            c_code, c_name,
            base_summary + " 賃料", dept
        ))

        # 管理費行（金額>0のとき）
        if s.mgmt_fee_amount:
            d_code, d_name, c_code, c_name, dept = _resolve_accounts(mgmt_pat, contract)
            mgmt_tax = _tax(s.mgmt_fee_amount, s.mgmt_fee_tax_type)
            writer.writerow(_make_row(
                date_str, d_code, d_name,
                s.mgmt_fee_amount, s.mgmt_fee_tax_type, mgmt_tax,
                c_code, c_name,
                base_summary + " 管理費", dept
            ))

        # 駐車場代行（金額>0のとき）
        if s.parking_amount:
            d_code, d_name, c_code, c_name, dept = _resolve_accounts(park_pat, contract)
            parking_tax = _tax(s.parking_amount, s.parking_tax_type)
            writer.writerow(_make_row(
                date_str, d_code, d_name,
                s.parking_amount, s.parking_tax_type, parking_tax,
                c_code, c_name,
                base_summary + " 駐車場代", dept
            ))

    return output.getvalue()
