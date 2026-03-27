from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from datetime import datetime
from app import db
from models import Company, Contract, JournalPattern, Property, generate_property_no

bp = Blueprint("properties", __name__, url_prefix="/properties")

TAX_TYPES = ["課税", "非課税"]
ACCOUNT_TYPES = ["普通", "当座", "貯蓄"]


def _current_company_id():
    return session.get("current_company_id")


def _base_query():
    """会社フィルタ適用済みのPropertyクエリを返す"""
    q = Property.query.filter_by(is_deleted=0)
    cid = _current_company_id()
    if cid:
        q = q.filter_by(company_id=cid)
    return q


def _apply_contract(c, form):
    """フォームデータをContractインスタンスに反映"""
    c.contract_start = form.get("contract_start", "")
    c.contract_end = form.get("contract_end") or None
    c.auto_renewal = 1 if form.get("auto_renewal") else 0
    c.payment_day = int(form.get("payment_day") or 25)
    c.rent_amount = int(form.get("rent_amount") or 0)
    c.rent_tax_type = form.get("rent_tax_type", "非課税")
    c.mgmt_fee_amount = int(form.get("mgmt_fee_amount") or 0)
    c.mgmt_fee_tax_type = form.get("mgmt_fee_tax_type", "課税")
    c.parking_amount = int(form.get("parking_amount") or 0)
    c.parking_tax_type = form.get("parking_tax_type", "非課税")
    c.security_deposit = int(form.get("security_deposit") or 0)
    c.key_money = int(form.get("key_money") or 0)
    c.bank_name = form.get("bank_name") or None
    c.bank_code = form.get("bank_code") or None
    c.branch_name = form.get("branch_name") or None
    c.branch_code = form.get("branch_code") or None
    c.account_type = form.get("account_type", "普通")
    c.account_number = form.get("account_number") or None
    c.account_holder = form.get("account_holder") or None
    c.zengin_sender_name = form.get("zengin_sender_name") or None
    c.debit_account_code = form.get("debit_account_code") or None
    c.debit_account_name = form.get("debit_account_name") or "地代家賃"
    c.credit_account_code = form.get("credit_account_code") or None
    c.credit_account_name = form.get("credit_account_name") or "普通預金"
    c.dept_code = form.get("dept_code") or None
    c.notes = form.get("contract_notes") or None
    # 仕訳パターンFK（費目ごと）
    def _pat_id(key):
        v = form.get(key)
        return int(v) if v and v.isdigit() else None
    c.rent_journal_pattern_id = _pat_id("rent_journal_pattern_id")
    c.mgmt_fee_journal_pattern_id = _pat_id("mgmt_fee_journal_pattern_id")
    c.parking_journal_pattern_id = _pat_id("parking_journal_pattern_id")
    return c


def _journal_patterns():
    return JournalPattern.query.filter_by(is_deleted=0).order_by(JournalPattern.name).all()


@bp.route("/")
def index():
    from datetime import date
    today = date.today().isoformat()
    properties = (_base_query()
                  .order_by(Property.property_no.nullslast(), Property.name)
                  .all())
    companies = Company.query.filter_by(is_deleted=0).order_by(Company.code).all()
    return render_template("properties/index.html",
                           properties=properties,
                           companies=companies,
                           today=today)


@bp.route("/new", methods=["GET", "POST"])
def new():
    companies = Company.query.filter_by(is_deleted=0).order_by(Company.code).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        if not name or not address:
            flash("物件名と住所は必須です。", "error")
            return render_template("properties/form.html",
                                   prop=None, contract=None,
                                   companies=companies, form=request.form,
                                   tax_types=TAX_TYPES, account_types=ACCOUNT_TYPES,
                                   journal_patterns=_journal_patterns())

        company_id = request.form.get("company_id") or None
        if company_id:
            company_id = int(company_id)

        prop = Property(
            company_id=company_id,
            name=name,
            address=address,
            property_type=request.form.get("property_type", "その他"),
            landlord_name=request.form.get("landlord_name") or None,
            landlord_contact=request.form.get("landlord_contact") or None,
            notes=request.form.get("notes") or None,
        )

        # 物件番号採番
        if company_id:
            company = Company.query.get(company_id)
            if company:
                prop.property_no = generate_property_no(company)

        db.session.add(prop)
        db.session.flush()  # prop.id を確定

        # 契約情報（contract_start がある場合のみ作成）
        contract_start = request.form.get("contract_start", "").strip()
        if contract_start:
            c = Contract(property_id=prop.id)
            _apply_contract(c, request.form)
            db.session.add(c)

        db.session.commit()
        flash(f"物件「{name}」を登録しました。"
              + (f"  物件番号: {prop.property_no}" if prop.property_no else ""), "success")
        return redirect(url_for("properties.detail", id=prop.id))

    defaults = {
        "rent_tax_type": "非課税",
        "mgmt_fee_tax_type": "課税",
        "parking_tax_type": "非課税",
        "account_type": "普通",
        "payment_day": 25,
        "debit_account_name": "地代家賃",
        "credit_account_name": "普通預金",
        "company_id": _current_company_id() or "",
    }
    return render_template("properties/form.html",
                           prop=None, contract=None,
                           companies=companies, form=defaults,
                           tax_types=TAX_TYPES, account_types=ACCOUNT_TYPES,
                           journal_patterns=_journal_patterns())


@bp.route("/<int:id>")
def detail(id):
    prop = Property.query.get_or_404(id)
    contract = prop.active_contract
    all_contracts = (Contract.query
                     .filter_by(property_id=id, is_deleted=0)
                     .order_by(Contract.contract_start.desc())
                     .all())
    return render_template("properties/detail.html",
                           prop=prop, contract=contract,
                           all_contracts=all_contracts)


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id):
    prop = Property.query.get_or_404(id)
    contract = prop.active_contract
    companies = Company.query.filter_by(is_deleted=0).order_by(Company.code).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        if not name or not address:
            flash("物件名と住所は必須です。", "error")
            return render_template("properties/form.html",
                                   prop=prop, contract=contract,
                                   companies=companies, form=request.form,
                                   tax_types=TAX_TYPES, account_types=ACCOUNT_TYPES,
                                   journal_patterns=_journal_patterns())

        # 会社変更時の物件番号採番
        new_company_id = request.form.get("company_id") or None
        if new_company_id:
            new_company_id = int(new_company_id)
        if new_company_id != prop.company_id:
            prop.company_id = new_company_id
            if new_company_id and not prop.property_no:
                company = Company.query.get(new_company_id)
                if company:
                    prop.property_no = generate_property_no(company)

        prop.name = name
        prop.address = address
        prop.property_type = request.form.get("property_type", "その他")
        prop.landlord_name = request.form.get("landlord_name") or None
        prop.landlord_contact = request.form.get("landlord_contact") or None
        prop.notes = request.form.get("notes") or None
        prop.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 契約更新
        contract_start = request.form.get("contract_start", "").strip()
        if contract_start:
            if contract:
                _apply_contract(contract, request.form)
                contract.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                c = Contract(property_id=prop.id)
                _apply_contract(c, request.form)
                db.session.add(c)

        db.session.commit()
        flash(f"物件「{name}」を更新しました。", "success")
        return redirect(url_for("properties.detail", id=prop.id))

    form = {
        "company_id": prop.company_id or "",
        "name": prop.name,
        "address": prop.address,
        "property_type": prop.property_type,
        "landlord_name": prop.landlord_name or "",
        "landlord_contact": prop.landlord_contact or "",
        "notes": prop.notes or "",
    }
    if contract:
        form.update({
            "contract_start": contract.contract_start,
            "contract_end": contract.contract_end or "",
            "auto_renewal": contract.auto_renewal,
            "payment_day": contract.payment_day,
            "rent_amount": contract.rent_amount,
            "rent_tax_type": contract.rent_tax_type,
            "mgmt_fee_amount": contract.mgmt_fee_amount,
            "mgmt_fee_tax_type": contract.mgmt_fee_tax_type,
            "parking_amount": contract.parking_amount,
            "parking_tax_type": contract.parking_tax_type,
            "security_deposit": contract.security_deposit,
            "key_money": contract.key_money,
            "bank_name": contract.bank_name or "",
            "bank_code": contract.bank_code or "",
            "branch_name": contract.branch_name or "",
            "branch_code": contract.branch_code or "",
            "account_type": contract.account_type or "普通",
            "account_number": contract.account_number or "",
            "account_holder": contract.account_holder or "",
            "zengin_sender_name": contract.zengin_sender_name or "",
            "debit_account_code": contract.debit_account_code or "",
            "debit_account_name": contract.debit_account_name or "地代家賃",
            "credit_account_code": contract.credit_account_code or "",
            "credit_account_name": contract.credit_account_name or "普通預金",
            "dept_code": contract.dept_code or "",
            "contract_notes": contract.notes or "",
            "rent_journal_pattern_id": contract.rent_journal_pattern_id or "",
            "mgmt_fee_journal_pattern_id": contract.mgmt_fee_journal_pattern_id or "",
            "parking_journal_pattern_id": contract.parking_journal_pattern_id or "",
        })
    else:
        form.update({
            "rent_tax_type": "非課税",
            "mgmt_fee_tax_type": "課税",
            "parking_tax_type": "非課税",
            "account_type": "普通",
            "payment_day": 25,
            "debit_account_name": "地代家賃",
            "credit_account_name": "普通預金",
        })

    return render_template("properties/form.html",
                           prop=prop, contract=contract,
                           companies=companies, form=form,
                           tax_types=TAX_TYPES, account_types=ACCOUNT_TYPES,
                           journal_patterns=_journal_patterns())


@bp.route("/<int:id>/terminate", methods=["GET", "POST"])
def terminate(id):
    prop = Property.query.get_or_404(id)
    contract = prop.active_contract
    if not contract:
        flash("解約対象のアクティブな契約がありません。", "error")
        return redirect(url_for("properties.detail", id=id))

    if request.method == "POST":
        terminated_at = request.form.get("terminated_at", "").strip()
        if not terminated_at:
            flash("解約日は必須です。", "error")
            return render_template("properties/terminate.html", prop=prop, contract=contract)

        contract.terminated_at = terminated_at
        contract.vacated_at = request.form.get("vacated_at") or None
        contract.termination_reason = request.form.get("termination_reason") or None
        contract.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        flash(f"物件「{prop.name}」の解約処理を完了しました。", "success")
        return redirect(url_for("properties.detail", id=id))

    return render_template("properties/terminate.html", prop=prop, contract=contract)


@bp.route("/extract-contract", methods=["POST"])
def extract_contract():
    """契約書ファイルをAIで解析してJSON返却"""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "ファイルが選択されていません。"}), 400

    media_type = file.content_type or "application/octet-stream"
    allowed = {"application/pdf", "image/jpeg", "image/png", "image/jpg", "image/webp"}
    if media_type not in allowed:
        return jsonify({"error": f"対応していないファイル形式です（{media_type}）。PDF/JPEG/PNGを使用してください。"}), 400

    file_bytes = file.read()
    from services.extractor import extract_from_contract
    result = extract_from_contract(file_bytes, media_type)
    return jsonify(result)


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id):
    prop = Property.query.get_or_404(id)
    prop.is_deleted = 1
    prop.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    flash(f"物件「{prop.name}」を削除しました。", "warning")
    return redirect(url_for("properties.index"))
