"""
計上管理 Blueprint
月別に仕訳CSV出力状況（計上済/未計上）を管理する。
"""
import io
import zipfile
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from app import db
from models import PaymentSchedule, Contract, Property

bp = Blueprint("accruals", __name__, url_prefix="/accruals")


@bp.route("/")
def index():
    """月別計上状況一覧"""
    # 全スケジュールから年月の組み合わせを集約
    rows = (db.session.query(
                PaymentSchedule.payment_year,
                PaymentSchedule.payment_month
            )
            .join(Contract, PaymentSchedule.contract_id == Contract.id)
            .join(Property, PaymentSchedule.property_id == Property.id)
            .filter(Contract.is_deleted == 0, Property.is_deleted == 0)
            .distinct()
            .order_by(PaymentSchedule.payment_year.desc(),
                      PaymentSchedule.payment_month.desc())
            .all())

    months = []
    for year, month in rows:
        schedules = (PaymentSchedule.query
                     .filter_by(payment_year=year, payment_month=month)
                     .join(Contract, PaymentSchedule.contract_id == Contract.id)
                     .filter(Contract.is_deleted == 0)
                     .all())
        total = len(schedules)
        journaled = sum(1 for s in schedules if s.journaled_at)
        total_amount = sum(s.total_amount for s in schedules)
        last_journaled = max(
            (s.journaled_at for s in schedules if s.journaled_at),
            default=None
        )
        months.append({
            "year": year,
            "month": month,
            "total": total,
            "journaled": journaled,
            "unjournaled": total - journaled,
            "total_amount": total_amount,
            "last_journaled": last_journaled,
            "all_journaled": journaled == total and total > 0,
        })

    return render_template("accruals/index.html", months=months)


@bp.route("/export")
def export():
    """指定年月の仕訳CSV を出力して計上済に更新"""
    from services.journal import generate_journal_csv

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month:
        flash("年月が不正です。", "error")
        return redirect(url_for("accruals.index"))

    schedules = (PaymentSchedule.query
                 .filter_by(payment_year=year, payment_month=month)
                 .join(Contract, PaymentSchedule.contract_id == Contract.id)
                 .filter(Contract.is_deleted == 0)
                 .all())

    if not schedules:
        flash("出力対象のスケジュールがありません。", "warning")
        return redirect(url_for("accruals.index"))

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


@bp.route("/reset", methods=["POST"])
def reset():
    """計上済フラグをリセット（再計上用）"""
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    if not year or not month:
        flash("年月が不正です。", "error")
        return redirect(url_for("accruals.index"))

    schedules = (PaymentSchedule.query
                 .filter_by(payment_year=year, payment_month=month)
                 .join(Contract, PaymentSchedule.contract_id == Contract.id)
                 .filter(Contract.is_deleted == 0)
                 .all())

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for s in schedules:
        s.journaled_at = None
        s.updated_at = now_str
    db.session.commit()

    flash(f"{year}年{month}月の計上済フラグをリセットしました。", "info")
    return redirect(url_for("accruals.index"))
