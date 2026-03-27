from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
from app import db
from models import JournalPattern

bp = Blueprint("journal_patterns", __name__, url_prefix="/journal-patterns")


@bp.route("/")
def index():
    patterns = (JournalPattern.query
                .filter_by(is_deleted=0)
                .order_by(JournalPattern.name)
                .all())
    return render_template("journal_patterns/index.html", patterns=patterns)


@bp.route("/api")
def api_list():
    """フォームのJS自動補完用JSON API"""
    patterns = (JournalPattern.query
                .filter_by(is_deleted=0)
                .order_by(JournalPattern.name)
                .all())
    return jsonify([{
        "id": p.id,
        "name": p.name,
        "debit_account_code": p.debit_account_code or "",
        "debit_account_name": p.debit_account_name,
        "credit_account_code": p.credit_account_code or "",
        "credit_account_name": p.credit_account_name,
        "dept_code": p.dept_code or "",
    } for p in patterns])


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("パターン名は必須です。", "error")
            return render_template("journal_patterns/form.html", pattern=None, form=request.form)

        p = JournalPattern(
            name=name,
            debit_account_code=request.form.get("debit_account_code") or None,
            debit_account_name=request.form.get("debit_account_name") or "地代家賃",
            credit_account_code=request.form.get("credit_account_code") or None,
            credit_account_name=request.form.get("credit_account_name") or "普通預金",
            dept_code=request.form.get("dept_code") or None,
            notes=request.form.get("notes") or None,
        )
        db.session.add(p)
        db.session.commit()
        flash(f"仕訳パターン「{name}」を登録しました。", "success")
        return redirect(url_for("journal_patterns.index"))

    defaults = {"debit_account_name": "地代家賃", "credit_account_name": "普通預金"}
    return render_template("journal_patterns/form.html", pattern=None, form=defaults)


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
def edit(id):
    p = JournalPattern.query.get_or_404(id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("パターン名は必須です。", "error")
            return render_template("journal_patterns/form.html", pattern=p, form=request.form)

        p.name = name
        p.debit_account_code = request.form.get("debit_account_code") or None
        p.debit_account_name = request.form.get("debit_account_name") or "地代家賃"
        p.credit_account_code = request.form.get("credit_account_code") or None
        p.credit_account_name = request.form.get("credit_account_name") or "普通預金"
        p.dept_code = request.form.get("dept_code") or None
        p.notes = request.form.get("notes") or None
        p.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        flash(f"仕訳パターン「{name}」を更新しました。", "success")
        return redirect(url_for("journal_patterns.index"))

    return render_template("journal_patterns/form.html", pattern=p, form=p)


@bp.route("/<int:id>/delete", methods=["POST"])
def delete(id):
    p = JournalPattern.query.get_or_404(id)
    p.is_deleted = 1
    p.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    flash(f"仕訳パターン「{p.name}」を削除しました。", "warning")
    return redirect(url_for("journal_patterns.index"))
