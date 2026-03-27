"""
契約書PDFや画像からClaude APIを使って契約情報を自動抽出するサービス。

設定方法:
    ~/.claude/settings.json の env セクションに追加:
    {
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-xxxxxxxxxxxxxxxx"
      }
    }
"""
import base64
import json
import re

EXTRACTION_PROMPT = """この不動産賃貸借契約書から以下のJSON形式で情報を抽出してください。
見つからない項目はnullにしてください。

{
  "name": "物件名・建物名・部屋番号（例: Aビル 3F）",
  "address": "所在地・住所",
  "property_type": "事務所 / 駐車場 / 倉庫 / 店舗 / その他 のいずれか",
  "landlord_name": "貸主・賃貸人の氏名または法人名",
  "landlord_contact": "貸主の電話番号またはメールアドレス",
  "contract_start": "契約開始日（YYYY-MM-DD形式）",
  "contract_end": "契約終了日（YYYY-MM-DD形式）",
  "auto_renewal": true または false,
  "payment_day": 支払日の日付（数値1〜31）,
  "rent_amount": 賃料の金額（税抜、整数）,
  "rent_tax_type": "課税 または 非課税",
  "mgmt_fee_amount": 管理費の金額（税抜、整数、なければ0）,
  "mgmt_fee_tax_type": "課税 または 非課税",
  "parking_amount": 駐車場代の金額（税抜、整数、なければ0）,
  "parking_tax_type": "課税 または 非課税",
  "security_deposit": 保証金・敷金の金額（整数、なければ0）,
  "key_money": 礼金の金額（整数、なければ0）,
  "bank_name": "振込先銀行名",
  "bank_code": "銀行コード（4桁）",
  "branch_name": "支店名",
  "branch_code": "支店コード（3桁）",
  "account_type": "普通 または 当座 または 貯蓄",
  "account_number": "口座番号（7桁）",
  "account_holder": "口座名義"
}

必ずJSONオブジェクトのみを返してください。説明文は不要です。"""


def extract_from_contract(file_bytes: bytes, media_type: str) -> dict:
    """
    PDF/画像から契約情報を抽出してdictで返す。

    Args:
        file_bytes: ファイルのバイト列
        media_type: MIMEタイプ（application/pdf, image/jpeg, image/png など）

    Returns:
        抽出された契約情報のdict、またはエラー情報を含むdict
    """
    from config import Config

    if not Config.ANTHROPIC_API_KEY:
        return {
            "error": "ANTHROPIC_API_KEY が設定されていません。"
                     "~/.claude/settings.json の env セクションに ANTHROPIC_API_KEY を追加してください。"
        }

    try:
        import anthropic
    except ImportError:
        return {
            "error": "anthropic パッケージがインストールされていません。"
                     "pip install anthropic を実行してください。"
        }

    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")

        if media_type == "application/pdf":
            source_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": encoded,
                },
            }
        else:
            source_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": encoded,
                },
            }

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [source_block, {"type": "text", "text": EXTRACTION_PROMPT}],
            }],
        )

        raw = response.content[0].text.strip()
        # ```json ... ``` ブロックが含まれる場合は中身だけ取り出す
        m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if m:
            raw = m.group(1)

        return json.loads(raw)

    except Exception as e:
        return {"error": f"AI解析中にエラーが発生しました: {str(e)}"}
