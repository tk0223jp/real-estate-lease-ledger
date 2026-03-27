from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import db
from models import Company

bp = Blueprint("companies", __name__, url_prefix="/companies")


@bp.route("/")
def index():
    companies = Company.query.filter_by(is_deleted=0).order_by(Company.code).all()
    return render_template("companies/index.html", companies=companies)


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        name = request.form.get("name", "").strip()
        notes = request.form.get("notes", "").strip()

        if not code or not name:
            flash("会社コードと会社名は必須です。", "error")
            return render_template("companies/form.html", company=None,
                                   form=request.form)
        if len(code) != 2 or not code.isdigit():
            flash("会社コードは2桁の数字で入力してください。", "error")
            return render_template("companies/form.html", company=None,
                                   form=request.form)
        if Company.query.filter_by(code=code, is_deleted=0).first():
            flash(f"会社コード「{code}」は既に使用されています。", "error")
            return render_template("companies/form.html", company=None,
                                   form=request.form)

        c = Company(code=code, name=name, notes=notes or None)
        db.session.add(c)
        db.session.commit()
        flash(f"会社「{name}」を登録しました。", "success")
        return redirect(url_for("companies.index"))

    return render_template("companies/form.html", company=None, form={})


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id):
    company = Company.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("会社名は必須です。", "error")
            return render_template("companies/form.html", company=company,
                                   form=request.form)

        company.name = name
        company.notes = notes or None
        db.session.commit()
        flash(f"会社「{name}」を更新しました。", "success")
        return redirect(url_for("companies.index"))

    return render_template("companies/form.html", company=company, form=company)


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id):
    company = Company.query.get_or_404(id)
    company.is_deleted = 1
    db.session.commit()
    flash(f"会社「{company.name}」を削除しました。", "success")
    return redirect(url_for("companies.index"))


@bp.route("/switch", methods=["POST"])
def switch():
    company_id = request.form.get("company_id", "")
    if company_id:
        session["current_company_id"] = int(company_id)
    else:
        session.pop("current_company_id", None)
    return redirect(request.referrer or url_for("index"))
