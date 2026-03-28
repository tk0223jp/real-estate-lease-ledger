import calendar
import io
import zipfile
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from app import db
from models import Property, Contract, PaymentSchedule
from decimal import Decimal
from config import Config

bp = Blueprint("payments", __name__, url_prefix="/payments")


def _get_ym():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    return year, month


def _calc_total(c):
    """税込合計・消費税額を(total, tax)で返す"""
    def tax(amount, tax_type):
        if tax_type == "課税":
            return int(Decimal(str(amount)) * Config.CONSUMPTION_TAX_RATE)
        return 0

    t = tax(c.rent_amount, c.rent_tax_type)
    t += tax(c.mgmt_fee_amount, c.mgmt_fee_tax_type)
    t += tax(c.parking_amount, c.parking_tax_type)
    total = c.rent_amount + c.mgmt_fee_amount + c.parking_amount + t
    return total, t


@bp.route("/")
def index():
    year, month = _get_ym()
    schedules = (PaymentSchedule.query
                 .filter_by(payment_year=year, payment_month=month)
                 .join(Contract, PaymentSchedule.contract_id == Contract.id)
                 .join(Property, PaymentSchedule.property_id == Property.id)
                 .filter(Contract.is_deleted == 0, Property.is_deleted == 0)
                 .order_by(Contract.payment_day, Property.name)
                 .all())

    # payment_day ごとにグループ化
    last_day = calendar.monthrange(year, month)[1]
    groups = {}  # {payment_day: {"schedules": [...], "total": int, "unpaid_count": int}}
    for s in schedules:
        day = s.contract.payment_day if s.contract else 25
        if day not in groups:
            groups[day] = {"schedules": [], "total": 0, "unpaid_total": 0,
                           "unpaid_count": 0, "payment_date": date(year, month, min(day, last_day))}
        groups[day]["schedules"].append(s)
        groups[day]["total"] += s.total_amount
        if not s.is_paid:
            groups[day]["unpaid_total"] += s.total_amount
            groups[day]["unpaid_count"] += 1
    groups = dict(sorted(groups.items()))  # payment_day 昇順

    total_amount = sum(s.total_amount for s in schedules)
    paid_amount = sum(s.total_amount for s in schedules if s.is_paid)
    unpaid_count = sum(1 for s in schedules if not s.is_paid)

    return render_template("payments/index.html",
                           schedules=schedules,
                           groups=groups,
                           year=year, month=month,
                           total_amount=total_amount,
                           paid_amount=paid_amount,
                           unpaid_count=unpaid_count)


@bp.route("/generate", methods=["POST"])
def generate():
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    if not year or not month:
        flash("年月が不正です。", "error")
        return redirect(url_for("payments.index"))

    # 対象月の初日・末日
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # アクティブな契約を取得（解約済みを除外）
    contracts = (Contract.query
                 .join(Property, Contract.property_id == Property.id)
                 .filter(
                     Contract.is_deleted == 0,
                     Property.is_deleted == 0,
                     Contract.terminated_at.is_(None),
                     Contract.contract_start <= last_day.isoformat(),
                     db.or_(
                         Contract.contract_end.is_(None),
                         Contract.contract_end >= first_day.isoformat()
                     )
                 ).all())

    created = 0
    for c in contracts:
        exists = PaymentSchedule.query.filter_by(
            contract_id=c.id,
            payment_year=year,
            payment_month=month
        ).first()
        if exists:
            continue

        total, tax = _calc_total(c)
        s = PaymentSchedule(
            contract_id=c.id,
            property_id=c.property_id,
            payment_year=year,
            payment_month=month,
            rent_amount=c.rent_amount,
            rent_tax_type=c.rent_tax_type,
            mgmt_fee_amount=c.mgmt_fee_amount,
            mgmt_fee_tax_type=c.mgmt_fee_tax_type,
            parking_amount=c.parking_amount,
            parking_tax_type=c.parking_tax_type,
            total_amount=total,
            tax_amount=tax,
        )
        db.session.add(s)
        created += 1

    db.session.commit()
    if created:
        flash(f"{year}年{month}月の支払スケジュールを {created} 件生成しました。", "success")
    else:
        flash(f"{year}年{month}月は既に生成済みです（または対象契約なし）。", "info")
    return redirect(url_for("payments.index", year=year, month=month))


@bp.route("/<int:id>/paid", methods=["POST"])
def mark_paid(id):
    s = PaymentSchedule.query.get_or_404(id)
    s.is_paid = 1
    s.paid_date = date.today().isoformat()
    s.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    return redirect(url_for("payments.index", year=s.payment_year, month=s.payment_month))


@bp.route("/<int:id>/unpaid", methods=["POST"])
def mark_unpaid(id):
    s = PaymentSchedule.query.get_or_404(id)
    s.is_paid = 0
    s.paid_date = None
    s.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    return redirect(url_for("payments.index", year=s.payment_year, month=s.payment_month))


@bp.route("/export/zengin")
def export_zengin():
    from services.zengin import generate_zengin
    year, month = _get_ym()
    schedules = (PaymentSchedule.query
                 .filter_by(payment_year=year, payment_month=month, is_paid=0)
                 .join(Contract, PaymentSchedule.contract_id == Contract.id)
                 .filter(Contract.is_deleted == 0)
                 .all())

    if not schedules:
        flash("出力対象の未払スケジュールがありません。", "warning")
        return redirect(url_for("payments.index", year=year, month=month))

    # 振込依頼人名の一致チェック
    sender_names = set(
        db.session.get(Contract, s.contract_id).zengin_sender_name or ""
        for s in schedules
    )
    if len(sender_names) > 1:
        flash("振込依頼人名が複数混在しているため全銀ファイルを生成できません。"
              "各契約の振込依頼人名を統一してください。", "error")
        return redirect(url_for("payments.index", year=year, month=month))

    transfer_date = date(year, month,
                         min(schedules[0].contract.payment_day,
                             calendar.monthrange(year, month)[1]))

    try:
        data = generate_zengin(schedules, transfer_date)
    except ValueError as e:
        flash(f"全銀ファイル生成エラー: {e}", "error")
        return redirect(url_for("payments.index", year=year, month=month))

    filename = f"zengin_{year}{month:02d}.txt"
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@bp.route("/export/journal")
def export_journal():
    from services.journal import generate_journal_csv
    year, month = _get_ym()
    schedules = (PaymentSchedule.query
                 .filter_by(payment_year=year, payment_month=month)
                 .join(Contract, PaymentSchedule.contract_id == Contract.id)
                 .filter(Contract.is_deleted == 0)
                 .all())

    if not schedules:
        flash("出力対象のスケジュールがありません。", "warning")
        return redirect(url_for("payments.index", year=year, month=month))

    csv_text = generate_journal_csv(schedules)

    # 計上済フラグを更新
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for s in schedules:
        s.journaled_at = now_str
        s.updated_at = now_str
    db.session.commit()

    filename = f"journal_{year}{month:02d}.csv"
    return Response(
        csv_text.encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@bp.route("/export/combined", methods=["POST"])
def export_combined():
    """指定支払日グループの全銀ファイル + 仕訳CSV を ZIP で出力し、未払を支払済に更新"""
    from services.zengin import generate_zengin
    from services.journal import generate_journal_csv

    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    payment_day = request.form.get("payment_day", type=int)
    transfer_date_str = request.form.get("transfer_date", "")

    if not all([year, month, payment_day, transfer_date_str]):
        flash("パラメータが不足しています。", "error")
        return redirect(url_for("payments.index"))

    try:
        transfer_date = date.fromisoformat(transfer_date_str)
    except ValueError:
        flash("振込実行日の形式が不正です（YYYY-MM-DD）。", "error")
        return redirect(url_for("payments.index", year=year, month=month))

    # 対象グループのスケジュール（未払のみ → 全銀用）
    all_schedules = (PaymentSchedule.query
                     .filter_by(payment_year=year, payment_month=month)
                     .join(Contract, PaymentSchedule.contract_id == Contract.id)
                     .filter(Contract.is_deleted == 0,
                             Contract.payment_day == payment_day)
                     .all())

    unpaid = [s for s in all_schedules if not s.is_paid]

    if not all_schedules:
        flash("対象スケジュールがありません。", "warning")
        return redirect(url_for("payments.index", year=year, month=month))

    # 全銀ファイル生成（未払のみ）
    zengin_data = None
    if unpaid:
        sender_names = set(
            db.session.get(Contract, s.contract_id).zengin_sender_name or ""
            for s in unpaid
        )
        if len(sender_names) > 1:
            flash("振込依頼人名が複数混在しているため全銀ファイルを生成できません。"
                  "各契約の振込依頼人名を統一してください。", "error")
            return redirect(url_for("payments.index", year=year, month=month))
        try:
            zengin_data = generate_zengin(unpaid, transfer_date)
        except ValueError as e:
            flash(f"全銀ファイル生成エラー: {e}", "error")
            return redirect(url_for("payments.index", year=year, month=month))

    # 仕訳CSV生成（グループ全件、振込実行日で伝票日付を上書き）
    csv_text = generate_journal_csv(all_schedules, transfer_date=transfer_date_str)

    # ZIP 作成
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if zengin_data:
            zf.writestr(f"zengin_{year}{month:02d}_{payment_day:02d}d.txt", zengin_data)
        zf.writestr(
            f"journal_{year}{month:02d}_{payment_day:02d}d.csv",
            csv_text.encode("utf-8-sig")
        )
    zip_buffer.seek(0)

    # 全銀ファイルに含めた未払スケジュールを支払済に更新、全件を計上済に更新
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if unpaid:
        for s in unpaid:
            s.is_paid = 1
            s.paid_date = transfer_date_str
            s.updated_at = now_str
    for s in all_schedules:
        s.journaled_at = now_str
        s.updated_at = now_str
    db.session.commit()

    filename = f"payment_{year}{month:02d}_{payment_day:02d}d.zip"
    return Response(
        zip_buffer.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
