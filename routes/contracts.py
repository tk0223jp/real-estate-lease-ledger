from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from app import db
from models import Property, Contract

bp = Blueprint("contracts", __name__, url_prefix="/contracts")


def _form_to_contract(c, form):
    c.property_id = int(form["property_id"])
    c.contract_start = form["contract_start"]
    c.contract_end = form.get("contract_end") or None
    c.auto_renewal = 1 if form.get("auto_renewal") else 0
    c.payment_day = int(form.get("payment_day", 25))

    c.rent_amount = int(form.get("rent_amount") or 0)
    c.rent_tax_type = form.get("rent_tax_type", "非課税")
    c.mgmt_fee_amount = int(form.get("mgmt_fee_amount") or 0)
    c.mgmt_fee_tax_type = form.get("mgmt_fee_tax_type", "課税")
    c.parking_amount = int(form.get("parking_amount") or 0)
    c.parking_tax_type = form.get("parking_tax_type", "非課税")

    c.security_deposit = int(form.get("security_deposit") or 0)
    c.key_money = int(form.get("key_money") or 0)

    c.bank_name = form.get("bank_name", "").strip()
    c.bank_code = form.get("bank_code", "").strip()
    c.branch_name = form.get("branch_name", "").strip()
    c.branch_code = form.get("branch_code", "").strip()
    c.account_type = form.get("account_type", "普通")
    c.account_number = form.get("account_number", "").strip()
    c.account_holder = form.get("account_holder", "").strip()
    c.zengin_sender_name = form.get("zengin_sender_name", "").strip()

    c.debit_account_code = form.get("debit_account_code", "").strip()
    c.debit_account_name = form.get("debit_account_name", "地代家賃").strip()
    c.credit_account_code = form.get("credit_account_code", "").strip()
    c.credit_account_name = form.get("credit_account_name", "普通預金").strip()
    c.dept_code = form.get("dept_code", "").strip()

    c.notes = form.get("notes", "").strip()
    return c


@bp.route("/")
def index():
    contracts = (Contract.query
                 .join(Property, Contract.property_id == Property.id)
                 .filter(Contract.is_deleted == 0, Property.is_deleted == 0)
                 .order_by(Contract.contract_end.asc().nullslast(), Property.name)
                 .all())

    today = date.today()
    return render_template("contracts/index.html", contracts=contracts, today=today)


@bp.route("/new", methods=["GET", "POST"])
def new():
    properties = Property.query.filter_by(is_deleted=0).order_by(Property.name).all()
    if request.method == "POST":
        c = Contract()
        _form_to_contract(c, request.form)
        if not c.contract_start:
            flash("契約開始日は必須です。", "error")
            return render_template("contracts/form.html", c=c, properties=properties,
                                   action="new", **_select_options())
        db.session.add(c)
        db.session.commit()
        flash("契約を登録しました。", "success")
        return redirect(url_for("contracts.detail", id=c.id))

    c = Contract()
    c.property_id = request.args.get("property_id", type=int)
    c.debit_account_name = "地代家賃"
    c.credit_account_name = "普通預金"
    c.rent_tax_type = "非課税"
    c.mgmt_fee_tax_type = "課税"
    c.parking_tax_type = "非課税"
    c.account_type = "普通"
    c.payment_day = 25
    return render_template("contracts/form.html", c=c, properties=properties,
                           action="new", **_select_options())


@bp.route("/<int:id>")
def detail(id):
    c = Contract.query.filter_by(id=id, is_deleted=0).first_or_404()
    return render_template("contracts/detail.html", c=c)


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id):
    c = Contract.query.filter_by(id=id, is_deleted=0).first_or_404()
    properties = Property.query.filter_by(is_deleted=0).order_by(Property.name).all()
    if request.method == "POST":
        _form_to_contract(c, request.form)
        if not c.contract_start:
            flash("契約開始日は必須です。", "error")
            return render_template("contracts/form.html", c=c, properties=properties,
                                   action="edit", **_select_options())
        c.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        flash("契約を更新しました。", "success")
        return redirect(url_for("contracts.detail", id=c.id))

    return render_template("contracts/form.html", c=c, properties=properties,
                           action="edit", **_select_options())


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id):
    c = Contract.query.filter_by(id=id, is_deleted=0).first_or_404()
    c.is_deleted = 1
    c.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    flash("契約を削除しました。", "warning")
    return redirect(url_for("contracts.index"))


def _select_options():
    return {
        "tax_types": Contract.TAX_TYPES,
        "account_types": Contract.ACCOUNT_TYPES,
    }
