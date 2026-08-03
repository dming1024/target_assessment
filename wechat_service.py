"""
WeChat Official Account Integration — Crypto & Messaging Utilities

Handles the "安全模式" (safe / encrypted mode) protocol:
  1. SHA1 signature verification
  2. AES-256-CBC message decryption
  3. AES-256-CBC reply encryption
  4. XML envelope construction
  5. Assessment-result-to-WeChat-text formatting
"""

import base64
import hashlib
import os
import random
import string
import struct
import time
import xml.etree.ElementTree as ET


# ── Configuration (must match WeChat Official Account backend) ─────────

WECHAT_TOKEN = "target_assessment"
WECHAT_AES_KEY = "UnecpDQrapQmfl8Dz0uzNXJ4s7r7jlO05oGrphR9kKG"
WECHAT_APP_ID = "wxd738c7e3c851dbee"


# ── Crypto helpers ──────────────────────────────────────────────────────

def _aes_key() -> bytes:
    """Decode the 43-char Base64 EncodingAESKey into a 32-byte AES key."""
    return base64.b64decode(WECHAT_AES_KEY + "=")


def _aes_iv() -> bytes:
    """IV is the first 16 bytes of the AES key (WeChat convention)."""
    return _aes_key()[:16]


def _get_cipher():
    """Lazy-import and instantiate an AES-256-CBC cipher."""
    from Crypto.Cipher import AES
    return AES.new(_aes_key(), AES.MODE_CBC, iv=_aes_iv())


def _pkcs7_pad(data: bytes, block_size: int = 32) -> bytes:
    """PKCS7 padding (WeChat uses 32-byte block size)."""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def _pkcs7_unpad(data: bytes) -> bytes:
    """Remove PKCS7 padding."""
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 32:
        raise ValueError(f"Invalid PKCS7 padding byte: {pad_len}")
    return data[:-pad_len]


# ── Signature ───────────────────────────────────────────────────────────

def calc_signature(token: str, timestamp: str, nonce: str,
                   msg_encrypt: str = "") -> str:
    """
    Calculate WeChat SHA1 signature.

    For GET verification:  SHA1(sort(token, timestamp, nonce, echostr))
    For POST verification: SHA1(sort(token, timestamp, nonce, msg_encrypt))

    WeChat supplies the 'msg_signature' query parameter; we recompute
    locally and compare.
    """
    arr = sorted([token, timestamp, nonce, msg_encrypt])
    raw = "".join(arr).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


# ── Message decryption ──────────────────────────────────────────────────

def decrypt_message(encrypted: str) -> str:
    """
    Decrypt a WeChat-encrypted message (safe mode).

    Protocol (WeChat official docs):
      ciphertext = Base64-decode(encrypted)
      plain      = AES-256-CBC-decrypt(ciphertext)
      plain      = un-PKCS7-pad(plain)
      parse plain:  random(16B) + msg_len(4B, network-order) + msg + AppID

    Returns the plaintext XML string.
    """
    from Crypto.Cipher import AES

    ciphertext = base64.b64decode(encrypted)
    cipher = AES.new(_aes_key(), AES.MODE_CBC, iv=_aes_iv())
    plain = cipher.decrypt(ciphertext)
    plain = _pkcs7_unpad(plain)

    # Skip 16 random bytes
    # Read 4-byte message length (big-endian)
    msg_len = struct.unpack(">I", plain[16:20])[0]
    msg = plain[20:20 + msg_len].decode("utf-8")
    # Remaining bytes after msg should be the AppID (we ignore)

    return msg


# ── Message encryption ──────────────────────────────────────────────────

def encrypt_message(msg: str) -> str:
    """
    Encrypt a plaintext reply into WeChat safe-mode format.

    Returns the Base64-encoded ciphertext string.
    """
    from Crypto.Cipher import AES

    random_bytes = os.urandom(16)
    msg_bytes = msg.encode("utf-8")
    msg_len_bytes = struct.pack(">I", len(msg_bytes))
    appid_bytes = WECHAT_APP_ID.encode("utf-8")

    plain = random_bytes + msg_len_bytes + msg_bytes + appid_bytes
    plain = _pkcs7_pad(plain)

    cipher = AES.new(_aes_key(), AES.MODE_CBC, iv=_aes_iv())
    ciphertext = cipher.encrypt(plain)
    return base64.b64encode(ciphertext).decode("ascii")


# ── XML helpers ─────────────────────────────────────────────────────────

def parse_encrypted_xml(xml_body: str) -> dict:
    """
    Parse the encrypted XML POST body from WeChat.

    Returns dict with keys: ToUserName, Encrypt (and optionally AgentID).
    """
    root = ET.fromstring(xml_body)
    result = {}
    for child in root:
        result[child.tag] = child.text or ""
    return result


def parse_message_xml(xml_body: str) -> dict:
    """
    Parse the decrypted inner XML into a dict of message fields.

    Returns dict with keys like:
      ToUserName, FromUserName, CreateTime, MsgType, Content, MsgId, ...
    """
    root = ET.fromstring(xml_body)
    result = {}
    for child in root:
        result[child.tag] = child.text or ""
    return result


def build_text_reply_xml(to_user: str, from_user: str, content: str) -> str:
    """
    Build the plaintext (inner) XML for a text reply.

    WeChat requires a <xml> envelope with specific field order,
    but ElementTree will canonicalise. To be safe, we build it by hand.
    """
    create_time = str(int(time.time()))
    # CDATA-wrapped fields for safe transmission
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{create_time}</CreateTime>"
        f"<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{_escape_cdata(content)}]]></Content>"
        "</xml>"
    )


def build_encrypted_envelope(encrypted_msg: str, timestamp: str,
                             nonce: str) -> str:
    """
    Wrap an encrypted message in the outer <xml> envelope WeChat expects.

    The envelope includes MsgSignature, TimeStamp, Nonce, and Encrypt fields.
    """
    msg_signature = calc_signature(
        WECHAT_TOKEN, timestamp, nonce, encrypted_msg,
    )
    return (
        "<xml>"
        f"<Encrypt><![CDATA[{encrypted_msg}]]></Encrypt>"
        f"<MsgSignature><![CDATA[{msg_signature}]]></MsgSignature>"
        f"<TimeStamp>{timestamp}</TimeStamp>"
        f"<Nonce><![CDATA[{nonce}]]></Nonce>"
        "</xml>"
    )


def _escape_cdata(text: str) -> str:
    """Escape text so it doesn't break CDATA sections."""
    return text.replace("]]>", "]]]]><![CDATA[>")


# ── User-input normalisation ────────────────────────────────────────────

def normalize_gene_text(text: str) -> str:
    """Extract and normalise a gene symbol from free-form user input."""
    # Remove common WeChat noise
    cleaned = text.strip()
    # Take only the first line / first word if multiple are given
    cleaned = cleaned.split("\n")[0].strip()
    # Remove common Chinese punctuation appended by WeChat
    cleaned = cleaned.rstrip("，。！？、；：""''）】》」")
    cleaned = cleaned.lstrip("（【《「")
    return cleaned.upper()


# ── Assessment formatting for WeChat ────────────────────────────────────

def format_assessment_for_wechat(result: dict) -> str:
    """
    Convert a run_assessment() result dict into a WeChat-friendly text block.

    Principles:
      - Keep under 800 chars (Chinese-friendly length)
      - Use 4-section format: 结论 / 评分 / 核心依据 / 提示
      - Never dump raw JSON
    """
    gene = result.get("gene", "N/A")
    total_score = result.get("total_score", 0)
    grade = result.get("grade", "?")
    grade_label = result.get("grade_label", "")
    recommendation = result.get("recommendation", "")
    archetype = result.get("archetype", "")
    scores = result.get("scores", {})
    evidence = result.get("evidence", {})
    disease = result.get("disease", "pan-cancer")

    # ── Dim labels ──
    dim_labels = {
        "disease_relevance": "疾病相关性",
        "expression": "表达谱",
        "dependency": "功能依赖性",
        "mechanism": "机制证据",
        "druggability": "可成药性",
        "safety": "安全性",
        "clinical_competition": "竞争格局",
        "scenario_fit": "场景适配",
    }

    # ── Build score lines ──
    key_dims = [
        "disease_relevance", "expression", "dependency",
        "druggability", "safety",
    ]
    score_lines = []
    for dim in key_dims:
        raw = scores.get(dim, 0)
        label = dim_labels.get(dim, dim)
        max_val = 15 if dim != "safety" else 10
        score_lines.append(f"  {label}：{raw:.1f}/{max_val}")

    # ── Top evidence ──
    top_evidence = _extract_top_evidence(result)

    # ── Disease label ──
    disease_display = disease if disease != "pan-cancer" else "泛癌"

    # ── Archetype label ──
    archetype_labels = {
        "expression_driven": "表达驱动型",
        "dependency_driven": "依赖驱动型",
        "mutation_driven": "突变驱动型",
        "drug_target": "已知药物靶点型",
        "balanced": "均衡型",
    }
    archetype_text = archetype_labels.get(archetype, archetype)

    lines = [
        f"【靶点评估结果】",
        f"基因：{gene}",
        f"评估场景：{disease_display}",
        f"靶点类型：{archetype_text}",
        f"",
        f"综合评分：{total_score:.1f}/100（等级 {grade}）",
        f"{grade_label}",
        f"",
        f"详细评分（维度/满分）：",
    ] + score_lines + [
        f"",
        f"核心依据：",
    ] + [f"{i}. {e}" for i, e in enumerate(top_evidence, 1)] + [
        f"",
        f"提示：如需查看完整报告，请访问 http://nsfchelp.cn, 或加我微信:yxtj1024",
    ]

    return "\n".join(lines)


def _extract_top_evidence(result: dict) -> list:
    """Extract 3-5 top evidence items from the assessment result."""
    items = []
    evidence = result.get("evidence", {})
    scores = result.get("scores", {})

    # Disease relevance
    disease = evidence.get("disease_relevance", {})
    if disease.get("target_cancer_overexpression") == "high":
        items.append("肿瘤组织中显著高表达")
    if disease.get("literature_level") == "high":
        items.append("文献证据丰富")
    elif disease.get("literature_level") == "moderate":
        items.append("存在一定文献支持")
    if disease.get("opentargets_association"):
        items.append("Open Targets 数据库支持疾病关联")

    # Expression
    expr = evidence.get("expression", {})
    if expr.get("tumor_normal_diff") == "significant":
        items.append("肿瘤-正常组织表达差异显著，靶向窗口好")

    # Dependency
    dep = evidence.get("dependency", {})
    if dep.get("target_cancer_dependency") == "strong":
        items.append("CRISPR 筛选显示强功能依赖性")

    # Druggability
    drug = evidence.get("druggability", {})
    approved = drug.get("approved_drugs", 0)
    if approved > 0:
        items.append(f"已有 {approved} 款获批药物，可成药性已验证")

    # Safety
    safety = evidence.get("safety", {})
    if safety.get("normal_tissue_risk") == "low":
        items.append("正常组织风险低，安全性窗口较好")
    if safety.get("is_common_essential"):
        items.append("⚠ 该基因为常见必需基因，安全性需重点关注")

    # Fill up to at least 3 items
    if not items:
        items.append("基础数据中证据信号较弱，建议补充实验验证")

    return items[:5]


# ── Help / fallback ─────────────────────────────────────────────────────

HELP_TEXT = (
    "欢迎使用靶点评估助手！\n\n"
    "请输入一个基因名称，我会为你评估其作为药物靶点的潜力。\n\n"
    "示例基因：TP53、EGFR、KRAS、CD274、ERBB2、BRCA1、VEGFA\n\n"
    "你也可以指定癌种，例如：\n"
    "  EGFR 肺癌\n"
    "  KRAS 结直肠癌\n\n"
    "如需完整报告，请访问：http://nsfchelp.cn"
)
