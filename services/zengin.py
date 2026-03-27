"""
全銀協フォーマット（総合振込）生成サービス。

レコード長: 120バイト固定 + CRLF
エンコード: Shift-JIS
名称フィールド: 半角カタカナ
"""
import calendar
from datetime import date

ENCODING = "shift_jis"
CRLF = b"\r\n"

ACCOUNT_TYPE_CODE = {"普通": "1", "当座": "2", "貯蓄": "4"}

# 全角カタカナ → 半角カタカナ変換テーブル（濁点・半濁点は2文字に展開）
_FULLKANA_MAP = {
    "ア": "ｱ", "イ": "ｲ", "ウ": "ｳ", "エ": "ｴ", "オ": "ｵ",
    "カ": "ｶ", "キ": "ｷ", "ク": "ｸ", "ケ": "ｹ", "コ": "ｺ",
    "サ": "ｻ", "シ": "ｼ", "ス": "ｽ", "セ": "ｾ", "ソ": "ｿ",
    "タ": "ﾀ", "チ": "ﾁ", "ツ": "ﾂ", "テ": "ﾃ", "ト": "ﾄ",
    "ナ": "ﾅ", "ニ": "ﾆ", "ヌ": "ﾇ", "ネ": "ﾈ", "ノ": "ﾉ",
    "ハ": "ﾊ", "ヒ": "ﾋ", "フ": "ﾌ", "ヘ": "ﾍ", "ホ": "ﾎ",
    "マ": "ﾏ", "ミ": "ﾐ", "ム": "ﾑ", "メ": "ﾒ", "モ": "ﾓ",
    "ヤ": "ﾔ", "ユ": "ﾕ", "ヨ": "ﾖ",
    "ラ": "ﾗ", "リ": "ﾘ", "ル": "ﾙ", "レ": "ﾚ", "ロ": "ﾛ",
    "ワ": "ﾜ", "ヲ": "ｦ", "ン": "ﾝ",
    "ァ": "ｧ", "ィ": "ｨ", "ゥ": "ｩ", "ェ": "ｪ", "ォ": "ｫ",
    "ッ": "ｯ", "ャ": "ｬ", "ュ": "ｭ", "ョ": "ｮ",
    "ガ": "ｶﾞ", "ギ": "ｷﾞ", "グ": "ｸﾞ", "ゲ": "ｹﾞ", "ゴ": "ｺﾞ",
    "ザ": "ｻﾞ", "ジ": "ｼﾞ", "ズ": "ｽﾞ", "ゼ": "ｾﾞ", "ゾ": "ｿﾞ",
    "ダ": "ﾀﾞ", "ヂ": "ﾁﾞ", "ヅ": "ﾂﾞ", "デ": "ﾃﾞ", "ド": "ﾄﾞ",
    "バ": "ﾊﾞ", "ビ": "ﾋﾞ", "ブ": "ﾌﾞ", "ベ": "ﾍﾞ", "ボ": "ﾎﾞ",
    "パ": "ﾊﾟ", "ピ": "ﾋﾟ", "プ": "ﾌﾟ", "ペ": "ﾍﾟ", "ポ": "ﾎﾟ",
    "ヴ": "ｳﾞ",
    "ー": "ｰ", "・": "･",
    "「": "｢", "」": "｣", "。": "｡", "、": "､",
    "　": " ",  # 全角スペース → 半角
}

# ひらがな → カタカナ変換オフセット
_HIRA_OFFSET = ord("ア") - ord("あ")


def to_half_kana(text: str) -> str:
    """全角カナ・ひらがなを半角カタカナに変換。その他の全角文字は半角に変換を試みる。"""
    if not text:
        return ""
    result = []
    for ch in text:
        # ひらがな → カタカナ
        if "あ" <= ch <= "ん":
            ch = chr(ord(ch) + _HIRA_OFFSET)
        # 全角カタカナ → 半角カタカナ
        if ch in _FULLKANA_MAP:
            result.append(_FULLKANA_MAP[ch])
        elif "Ａ" <= ch <= "Ｚ":
            result.append(chr(ord(ch) - 0xFEE0))
        elif "ａ" <= ch <= "ｚ":
            result.append(chr(ord(ch) - 0xFEE0).upper())
        elif "０" <= ch <= "９":
            result.append(chr(ord(ch) - 0xFEE0))
        else:
            result.append(ch)
    return "".join(result)


def _encode_field(value: str, byte_len: int, pad_char: str = " ", pad_left: bool = False) -> bytes:
    """
    文字列をShift-JISエンコードし、byte_len バイトに切り詰め/パディングして返す。
    pad_left=True のとき右詰め（数値用）。
    """
    encoded = value.encode(ENCODING, errors="replace")
    if len(encoded) > byte_len:
        encoded = encoded[:byte_len]
    pad = pad_char.encode(ENCODING) * (byte_len - len(encoded))
    if pad_left:
        return pad + encoded
    return encoded + pad


def _num_field(value: int, byte_len: int) -> bytes:
    """数値を右詰めゼロ埋めでバイト列に変換。"""
    return str(value).zfill(byte_len).encode(ENCODING)


def _build_header(sender_name: str, transfer_date: date,
                  ordering_bank_code: str = "0000",
                  ordering_bank_name: str = "",
                  ordering_branch_code: str = "000",
                  ordering_branch_name: str = "",
                  client_code: str = "0000000000") -> bytes:
    """ヘッダーレコード（120バイト）"""
    record = b""
    record += b"1"                                                        # 1: データ区分
    record += b"21"                                                       # 2-3: 種別コード（総合振込）
    record += b"0"                                                        # 4: コード区分（銀行コード）
    record += _encode_field(client_code, 10, "0", pad_left=True)          # 5-14: 振込依頼人コード
    record += _encode_field(to_half_kana(sender_name), 40)                # 15-54: 振込依頼人名
    record += transfer_date.strftime("%m%d").encode(ENCODING)             # 55-58: 取組日（MMDD）
    record += _encode_field(ordering_bank_code, 4, "0", pad_left=True)   # 59-62: 仕向銀行番号
    record += _encode_field(to_half_kana(ordering_bank_name), 15)        # 63-77: 仕向銀行名
    record += _encode_field(ordering_branch_code, 3, "0", pad_left=True) # 78-80: 仕向支店番号
    record += _encode_field(to_half_kana(ordering_branch_name), 15)      # 81-95: 仕向支店名
    record += b" " * 17                                                   # 96-112: ダミー
    record += b" " * 8                                                    # 113-120: 予備
    assert len(record) == 120, f"ヘッダーレコード長エラー: {len(record)}"
    return record


def _build_data(schedule, contract) -> bytes:
    """データレコード（120バイト）"""
    account_code = ACCOUNT_TYPE_CODE.get(contract.account_type or "普通", "1")
    record = b""
    record += b"2"                                                              # 1: データ区分
    record += _encode_field(contract.bank_code or "", 4, "0", pad_left=True)   # 2-5: 被仕向銀行番号
    record += _encode_field(to_half_kana(contract.bank_name or ""), 15)        # 6-20: 被仕向銀行名
    record += _encode_field(contract.branch_code or "", 3, "0", pad_left=True) # 21-23: 被仕向支店番号
    record += _encode_field(to_half_kana(contract.branch_name or ""), 15)      # 24-38: 被仕向支店名
    record += b" " * 4                                                          # 39-42: 手形交換所番号（スペース）
    record += account_code.encode(ENCODING)                                     # 43: 預金種目
    record += _encode_field(contract.account_number or "", 7, "0", pad_left=True) # 44-50: 口座番号
    record += _encode_field(to_half_kana(contract.account_holder or ""), 30)   # 51-80: 受取人名
    record += _num_field(schedule.total_amount, 10)                             # 81-90: 振込金額
    record += b"1"                                                              # 91: 新規コード（新規）
    record += _encode_field(str(schedule.contract_id), 10, "0", pad_left=True) # 92-101: 顧客コード1
    record += b" " * 10                                                         # 102-111: 顧客コード2
    record += b"7"                                                              # 112: 振込指定区分（電信）
    record += b" "                                                              # 113: 識別表示
    record += b" " * 7                                                          # 114-120: 予備
    assert len(record) == 120, f"データレコード長エラー: {len(record)}"
    return record


def _build_trailer(count: int, total_amount: int) -> bytes:
    """トレーラーレコード（120バイト）"""
    record = b""
    record += b"8"                              # 1: データ区分
    record += _num_field(count, 6)              # 2-7: 合計件数
    record += _num_field(total_amount, 12)      # 8-19: 合計金額
    record += b" " * 101                        # 20-120: ダミー
    assert len(record) == 120, f"トレーラーレコード長エラー: {len(record)}"
    return record


def _build_end() -> bytes:
    """エンドレコード（120バイト）"""
    record = b"9" + b" " * 119
    assert len(record) == 120
    return record


def generate_zengin(schedules: list, transfer_date: date) -> bytes:
    """
    全銀協フォーマットのバイト列を生成する。

    Args:
        schedules: PaymentSchedule のリスト（同一 zengin_sender_name であること）
        transfer_date: 取組日（振込実行日）

    Returns:
        Shift-JIS エンコード、CRLF 区切りのバイト列
    """
    from app import db
    from models import Contract

    if not schedules:
        raise ValueError("スケジュールが空です。")

    first_contract = db.session.get(Contract, schedules[0].contract_id)
    sender_name = first_contract.zengin_sender_name or ""

    lines = []
    lines.append(_build_header(sender_name, transfer_date))

    total_amount = 0
    for s in schedules:
        contract = db.session.get(Contract, s.contract_id)

        # バリデーション
        if contract.account_number and len(contract.account_number.strip()) != 7:
            raise ValueError(
                f"口座番号が7桁ではありません: {contract.property.name} "
                f"（{contract.account_number}）"
            )

        lines.append(_build_data(s, contract))
        total_amount += s.total_amount

    lines.append(_build_trailer(len(schedules), total_amount))
    lines.append(_build_end())

    return CRLF.join(lines) + CRLF
