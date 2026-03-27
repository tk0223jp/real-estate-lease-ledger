from flask import Flask, redirect, url_for, render_template, session
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from routes.properties import bp as properties_bp
    from routes.contracts import bp as contracts_bp
    from routes.payments import bp as payments_bp
    from routes.companies import bp as companies_bp
    from routes.journal_patterns import bp as journal_patterns_bp

    app.register_blueprint(properties_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(journal_patterns_bp)

    @app.context_processor
    def inject_company_context():
        from models import Company
        all_companies = Company.query.filter_by(is_deleted=0).order_by(Company.code).all()
        current_company_id = session.get("current_company_id")
        return dict(all_companies=all_companies, current_company_id=current_company_id)

    @app.route("/")
    def index():
        from datetime import date
        from models import Property, Contract, PaymentSchedule, Company
        today = date.today()
        year, month = today.year, today.month

        cid = session.get("current_company_id")
        prop_q = Property.query.filter_by(is_deleted=0)
        if cid:
            prop_q = prop_q.filter_by(company_id=cid)
        property_count = prop_q.count()

        contract_q = (Contract.query
                      .join(Property, Contract.property_id == Property.id)
                      .filter(Contract.is_deleted == 0, Property.is_deleted == 0))
        if cid:
            contract_q = contract_q.filter(Property.company_id == cid)
        contracts = contract_q.all()
        expiry_warn_count = sum(
            1 for c in contracts
            if c.days_until_expiry is not None and c.days_until_expiry <= 90
        )

        sched_q = (PaymentSchedule.query
                   .join(Property, PaymentSchedule.property_id == Property.id)
                   .filter(PaymentSchedule.payment_year == year,
                           PaymentSchedule.payment_month == month))
        if cid:
            sched_q = sched_q.filter(Property.company_id == cid)
        schedules = sched_q.all()
        monthly_total = sum(s.total_amount for s in schedules)
        monthly_count = len(schedules)
        unpaid_count = sum(1 for s in schedules if not s.is_paid)

        current_company = None
        if cid:
            current_company = Company.query.get(cid)

        return render_template("index.html",
                               year=year, month=month,
                               monthly_total=monthly_total,
                               monthly_count=monthly_count,
                               unpaid_count=unpaid_count,
                               property_count=property_count,
                               expiry_warn_count=expiry_warn_count,
                               current_company=current_company)

    with app.app_context():
        import models  # noqa: F401 — ensure models are registered
        db.create_all()

    return app
