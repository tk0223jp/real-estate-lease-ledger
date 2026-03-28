from decimal import Decimal
from datetime import datetime
from app import db
from config import Config


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False, unique=True)
    name = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)
    is_deleted = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           onupdate=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    properties = db.relationship(
        "Property", backref="company", lazy=True,
        primaryjoin="and_(Company.id==Property.company_id, Property.is_deleted==0)"
    )


class JournalPattern(db.Model):
    """仕訳パターンマスタ — 費目ごとに科目コードの組み合わせを登録する"""
    __tablename__ = "journal_patterns"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    debit_account_code = db.Column(db.Text)
    debit_account_name = db.Column(db.Text, nullable=False, default="地代家賃")
    credit_account_code = db.Column(db.Text)
    credit_account_name = db.Column(db.Text, nullable=False, default="普通預金")
    dept_code = db.Column(db.Text)
    notes = db.Column(db.Text)
    is_deleted = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           onupdate=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def generate_property_no(company):
    """物件番号を採番: P + 2桁会社コード + 7桁連番"""
    prefix = f"P{company.code}"
    last = (Property.query
            .filter(Property.property_no.like(f"{prefix}%"))
            .order_by(Property.property_no.desc())
            .first())
    if last and last.property_no and len(last.property_no) == 10:
        try:
            seq = int(last.property_no[3:]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:07d}"


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)
    property_no = db.Column(db.String(10), unique=True, nullable=True)
    name = db.Column(db.Text, nullable=False)
    address = db.Column(db.Text, nullable=False)
    property_type = db.Column(db.Text, nullable=False, default="その他")
    landlord_name = db.Column(db.Text)
    landlord_contact = db.Column(db.Text)
    notes = db.Column(db.Text)
    is_deleted = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           onupdate=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    contracts = db.relationship("Contract", backref="property", lazy=True,
                                primaryjoin="and_(Contract.property_id==Property.id, Contract.is_deleted==0)")

    PROPERTY_TYPES = ["事務所", "駐車場", "倉庫", "店舗", "その他"]

    @property
    def active_contract(self):
        """最新のアクティブ契約を返す（解約済み・期限切れを除く）"""
        from datetime import date
        today = date.today().isoformat()
        return (Contract.query
                .filter_by(property_id=self.id, is_deleted=0)
                .filter(Contract.terminated_at.is_(None))
                .filter(
                    db.or_(Contract.contract_end.is_(None), Contract.contract_end >= today)
                )
                .order_by(Contract.contract_start.desc())
                .first())


class Contract(db.Model):
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)

    # 契約期間
    contract_start = db.Column(db.Text, nullable=False)
    contract_end = db.Column(db.Text)
    auto_renewal = db.Column(db.Integer, nullable=False, default=0)
    payment_day = db.Column(db.Integer, nullable=False, default=25)

    # 月額費用
    rent_amount = db.Column(db.Integer, nullable=False, default=0)
    rent_tax_type = db.Column(db.Text, nullable=False, default="非課税")
    mgmt_fee_amount = db.Column(db.Integer, nullable=False, default=0)
    mgmt_fee_tax_type = db.Column(db.Text, nullable=False, default="課税")
    parking_amount = db.Column(db.Integer, nullable=False, default=0)
    parking_tax_type = db.Column(db.Text, nullable=False, default="非課税")

    # 初期費用
    security_deposit = db.Column(db.Integer, nullable=False, default=0)
    key_money = db.Column(db.Integer, nullable=False, default=0)

    # 振込先銀行口座
    bank_name = db.Column(db.Text)
    bank_code = db.Column(db.Text)
    branch_name = db.Column(db.Text)
    branch_code = db.Column(db.Text)
    account_type = db.Column(db.Text, default="普通")
    account_number = db.Column(db.Text)
    account_holder = db.Column(db.Text)
    zengin_sender_name = db.Column(db.Text)

    # 会計設定（フォールバック値）
    debit_account_code = db.Column(db.Text)
    debit_account_name = db.Column(db.Text, nullable=False, default="地代家賃")
    credit_account_code = db.Column(db.Text)
    credit_account_name = db.Column(db.Text, nullable=False, default="普通預金")
    dept_code = db.Column(db.Text)

    # 仕訳パターン FK（費目ごと）
    rent_journal_pattern_id = db.Column(db.Integer, db.ForeignKey("journal_patterns.id"), nullable=True)
    mgmt_fee_journal_pattern_id = db.Column(db.Integer, db.ForeignKey("journal_patterns.id"), nullable=True)
    parking_journal_pattern_id = db.Column(db.Integer, db.ForeignKey("journal_patterns.id"), nullable=True)

    # 費目別仕訳科目
    rent_debit_account_code = db.Column(db.Text)
    rent_debit_account_name = db.Column(db.Text, nullable=False, default="地代家賃")
    rent_credit_account_code = db.Column(db.Text)
    rent_credit_account_name = db.Column(db.Text, nullable=False, default="普通預金")
    mgmt_debit_account_code = db.Column(db.Text)
    mgmt_debit_account_name = db.Column(db.Text, nullable=False, default="地代家賃")
    mgmt_credit_account_code = db.Column(db.Text)
    mgmt_credit_account_name = db.Column(db.Text, nullable=False, default="普通預金")
    parking_debit_account_code = db.Column(db.Text)
    parking_debit_account_name = db.Column(db.Text, nullable=False, default="駐車場代")
    parking_credit_account_code = db.Column(db.Text)
    parking_credit_account_name = db.Column(db.Text, nullable=False, default="普通預金")

    # 解約情報
    terminated_at = db.Column(db.Text)            # 解約日（NULL = アクティブ）
    vacated_at = db.Column(db.Text)               # 旧・退去日（互換性のため残置）
    deposit_returned_at = db.Column(db.Text)      # 敷金返金日
    termination_reason = db.Column(db.Text)       # 解約理由

    notes = db.Column(db.Text)
    is_deleted = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           onupdate=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    payment_schedules = db.relationship("PaymentSchedule", backref="contract", lazy=True)

    # relationships to patterns
    rent_journal_pattern = db.relationship(
        "JournalPattern", foreign_keys=[rent_journal_pattern_id])
    mgmt_fee_journal_pattern = db.relationship(
        "JournalPattern", foreign_keys=[mgmt_fee_journal_pattern_id])
    parking_journal_pattern = db.relationship(
        "JournalPattern", foreign_keys=[parking_journal_pattern_id])

    TAX_TYPES = ["課税", "非課税"]
    ACCOUNT_TYPES = ["普通", "当座", "貯蓄"]

    def _tax(self, amount, tax_type):
        if tax_type == "課税":
            return int(Decimal(str(amount)) * Config.CONSUMPTION_TAX_RATE)
        return 0

    @property
    def is_terminated(self):
        return self.terminated_at is not None

    @property
    def has_active_deposit(self):
        """敷金残高が存在するか（返金日が未設定 or 今日以降）"""
        if self.security_deposit <= 0:
            return False
        if not self.deposit_returned_at:
            return True
        from datetime import date
        return self.deposit_returned_at >= date.today().isoformat()

    @property
    def rent_tax(self):
        return self._tax(self.rent_amount, self.rent_tax_type)

    @property
    def mgmt_fee_tax(self):
        return self._tax(self.mgmt_fee_amount, self.mgmt_fee_tax_type)

    @property
    def parking_tax(self):
        return self._tax(self.parking_amount, self.parking_tax_type)

    @property
    def total_tax_amount(self):
        return self.rent_tax + self.mgmt_fee_tax + self.parking_tax

    @property
    def transfer_amount(self):
        """振込金額（税込合計）"""
        return (self.rent_amount + self.rent_tax
                + self.mgmt_fee_amount + self.mgmt_fee_tax
                + self.parking_amount + self.parking_tax)

    @property
    def days_until_expiry(self):
        if not self.contract_end:
            return None
        from datetime import date
        end = date.fromisoformat(self.contract_end)
        return (end - date.today()).days


class PaymentSchedule(db.Model):
    __tablename__ = "payment_schedules"

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    payment_year = db.Column(db.Integer, nullable=False)
    payment_month = db.Column(db.Integer, nullable=False)

    # スナップショット
    rent_amount = db.Column(db.Integer, nullable=False, default=0)
    rent_tax_type = db.Column(db.Text, nullable=False, default="非課税")
    mgmt_fee_amount = db.Column(db.Integer, nullable=False, default=0)
    mgmt_fee_tax_type = db.Column(db.Text, nullable=False, default="課税")
    parking_amount = db.Column(db.Integer, nullable=False, default=0)
    parking_tax_type = db.Column(db.Text, nullable=False, default="非課税")
    total_amount = db.Column(db.Integer, nullable=False, default=0)
    tax_amount = db.Column(db.Integer, nullable=False, default=0)

    # 支払状態
    is_paid = db.Column(db.Integer, nullable=False, default=0)
    paid_date = db.Column(db.Text)

    # 計上状態
    journaled_at = db.Column(db.Text)  # 仕訳CSV出力日時（NULL=未計上）

    notes = db.Column(db.Text)
    created_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = db.Column(db.Text, nullable=False,
                           default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           onupdate=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    __table_args__ = (
        db.UniqueConstraint("contract_id", "payment_year", "payment_month",
                            name="uq_schedule_contract_ym"),
    )

    def _tax(self, amount, tax_type):
        if tax_type == "課税":
            return int(Decimal(str(amount)) * Config.CONSUMPTION_TAX_RATE)
        return 0

    @property
    def rent_tax(self):
        return self._tax(self.rent_amount, self.rent_tax_type)

    @property
    def mgmt_fee_tax(self):
        return self._tax(self.mgmt_fee_amount, self.mgmt_fee_tax_type)

    @property
    def parking_tax(self):
        return self._tax(self.parking_amount, self.parking_tax_type)

    @property
    def property_name(self):
        from app import db as _db
        prop = _db.session.get(Property, self.property_id)
        return prop.name if prop else ""
