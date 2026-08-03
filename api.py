
"""
Target Assessment REST API — FastAPI

Start:
    uvicorn api:app --host 0.0.0.0 --port 8008

Docs:
    http://localhost:8008/docs

Example:
    curl -X POST http://localhost:8008/assess \
        -H "Content-Type: application/json" \
        -d '{"gene": "EGFR"}'
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from assessment_core import run_assessment
from modules.gene_resolver import GeneResolver
from modules.data_manager import DataManager
from modules.scoring_engine import ScoringEngine
import wechat_service as wx

# ── Logging setup ─────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),  # terminal
        RotatingFileHandler(
            LOG_DIR / "api.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        ),
    ],
)

# Dedicated access log for gene queries
access_logger = logging.getLogger("access")
access_handler = RotatingFileHandler(
    LOG_DIR / "access.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
access_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
access_logger.addHandler(access_handler)
access_logger.setLevel(logging.INFO)
access_logger.propagate = False  # don't duplicate to root logger

logger = logging.getLogger(__name__)
app = FastAPI(
    title="Target Assessment API",
    description="靶点价值评估 REST API — 输入基因符号，返回多维度评估结果",
    version="0.3.0",
)


# ── Request model ─────────────────────────────────────────────────────────

class AssessRequest(BaseModel):
    gene: str = Field(..., description="HGNC gene symbol or alias / 基因符号或别名", examples=["EGFR"])
    disease: Optional[str] = Field(None, description="Disease / cancer type; pan-cancer if omitted / 疾病或癌种；不填则泛癌评估", examples=["NSCLC"])
    scenario: str = Field("general", description="Assessment scenario / 评估场景", examples=["general"])
    format: str = Field("full", description="Response format: full or summary / 返回格式", examples=["full"])


# ── Response models ────────────────────────────────────────────────────────

class GeneInfo(BaseModel):
    symbol: str
    full_name: str
    ensembl_id: str


class ScoreBreakdown(BaseModel):
    score: float
    max: int


class FullResponse(BaseModel):
    gene: GeneInfo
    disease: str
    scenario: str
    total_score: float
    grade: str
    grade_label: str
    recommendation: str
    archetype: str
    scores: Dict[str, ScoreBreakdown]
    evidence: Dict


class SummaryResponse(BaseModel):
    gene: str
    disease: str
    total_score: float
    grade: str
    grade_label: str
    recommendation: str
    archetype: str
    scores: Dict[str, float]


class HealthResponse(BaseModel):
    status: str
    offline_db: bool
    version: str


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    """Health check — verifies the service and offline DB are ready."""
    from modules.offline_provider import OfflineProvider
    offline_ok = OfflineProvider().is_available()
    return {
        "status": "ok" if offline_ok else "degraded — offline DB not found",
        "offline_db": offline_ok,
        "version": app.version,
    }


@app.post("/assess")
def assess(req: AssessRequest):
    """Run a target assessment and return scores + evidence."""

    gene_input = req.gene.strip()
    disease = req.disease.strip() if req.disease else "pan-cancer"
    scenario = req.scenario.strip()
    fmt = req.format.strip().lower()

    logger.info(
        f"Assess request: gene={gene_input} disease={disease} "
        f"scenario={scenario} format={fmt}"
    )
    access_logger.info(
        f"gene={gene_input} disease={disease} scenario={scenario} format={fmt}"
    )

    if fmt not in ("full", "summary"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid format '{fmt}'. Valid: full, summary",
        )

    result = run_assessment(gene=gene_input, disease=disease, scenario=scenario)

    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["error"])

    dim_max = result["evidence"].get("_dim_max", {})
    if not dim_max:
        from config import DIMENSION_MAX
        dim_max = DIMENSION_MAX

    if fmt == "summary":
        return SummaryResponse(
            gene=result["gene"],
            disease=result["disease"],
            total_score=result["total_score"],
            grade=result["grade"],
            grade_label=result["grade_label"],
            recommendation=result["recommendation"],
            archetype=result["archetype"],
            scores={k: v for k, v in result["scores"].items()},
        )

    # fmt == "full"
    evidence = result["evidence"]
    return FullResponse(
        gene=GeneInfo(
            symbol=result["gene"],
            full_name=result["full_name"],
            ensembl_id=result["ensembl_id"],
        ),
        disease=result["disease"],
        scenario=result["scenario"],
        total_score=result["total_score"],
        grade=result["grade"],
        grade_label=result["grade_label"],
        recommendation=result["recommendation"],
        archetype=result["archetype"],
        scores={
            k: ScoreBreakdown(score=v, max=dim_max.get(k, 1))
            for k, v in result["scores"].items()
        },
        evidence={
            "disease_relevance": evidence.get("disease_relevance", {}),
            "expression": evidence.get("expression", {}),
            "dependency": evidence.get("dependency", {}),
            "mechanism": evidence.get("mechanism", {}),
            "druggability": evidence.get("druggability", {}),
            "safety": evidence.get("safety", {}),
            "clinical_competition": evidence.get("clinical_competition", {}),
        },
    )


# ── WeChat Official Account callback ────────────────────────────────────────
#
# 公众号后台配置:
#   URL:             http://nsfchelp.cn/target/wechat
#   Token:           target_assessment
#   EncodingAESKey:  UnecpDQrapQmfl8Dz0uzNXJ4s7r7jlO05oGrphR9kKG
#   消息加密方式:     安全模式
#   数据格式:         XML


@app.get("/wechat")
def wechat_verify(
    signature: Optional[str] = Query(None),
    msg_signature: Optional[str] = Query(None),
    timestamp: Optional[str] = Query(None),
    nonce: Optional[str] = Query(None),
    echostr: Optional[str] = Query(None),
):
    """
    WeChat URL verification (GET).

    Handles three modes:
      - 明文模式 (plaintext):  signature = SHA1(sort(token, timestamp, nonce))
      - 安全模式 (encrypted):   msg_signature = SHA1(sort(token, timestamp, nonce, echostr))
      - 兼容模式 (compatibility): both signatures sent; prefer encrypted path
    """

    # ── Plaintext mode ──────────────────────────────────────────────────
    if signature and not msg_signature and all([timestamp, nonce, echostr]):
        expected_sig = wx.calc_signature(
            wx.WECHAT_TOKEN, timestamp, nonce,  # 3 params, no echostr
        )
        if signature != expected_sig:
            logger.warning(
                f"WeChat GET (plaintext) signature mismatch "
                f"got={signature} expected={expected_sig}"
            )
            raise HTTPException(
                status_code=403,
                detail="signature verification failed",
            )
        logger.info("WeChat URL verification succeeded (plaintext mode)")
        return PlainTextResponse(content=echostr, status_code=200)

    # ── Encrypted / safe mode ───────────────────────────────────────────
    if not all([msg_signature, timestamp, nonce, echostr]):
        logger.warning(
            f"WeChat GET missing params: "
            f"msg_signature={msg_signature} timestamp={timestamp} "
            f"nonce={nonce} echostr={bool(echostr)}"
        )
        return PlainTextResponse(
            "wechat endpoint ok — missing WeChat verification params",
            status_code=200,
        )

    expected_sig = wx.calc_signature(
        wx.WECHAT_TOKEN,
        timestamp,
        nonce,
        echostr,
    )

    if msg_signature != expected_sig:
        logger.warning(
            f"WeChat GET signature mismatch "
            f"got={msg_signature} expected={expected_sig}"
        )
        raise HTTPException(
            status_code=403,
            detail="signature verification failed",
        )

    try:
        decrypted = wx.decrypt_message(echostr)
    except Exception as e:
        logger.exception("decrypt echostr failed")
        raise HTTPException(
            status_code=400,
            detail=f"decrypt echostr failed: {e}",
        )

    logger.info("WeChat URL verification succeeded (encrypted mode)")
    return PlainTextResponse(content=decrypted, status_code=200)


@app.post("/wechat")
async def wechat_message(
    request: Request,
    signature: Optional[str] = Query(None),
    msg_signature: Optional[str] = Query(None),
    timestamp: str = Query(...),
    nonce: str = Query(...),
):
    """
    WeChat message callback (POST).

    Receives XML (encrypted or plaintext), extracts the user's gene query,
    runs assessment, and returns a text reply (encrypted if needed).
    """
    # Step 1: Read raw XML body
    xml_body = await request.body()
    xml_str = xml_body.decode("utf-8")

    # Step 2: Determine mode — encrypted (has <Encrypt>) vs plaintext
    envelope = wx.parse_encrypted_xml(xml_str)
    encrypt_field = envelope.get("Encrypt", "")

    if encrypt_field:
        # ── Encrypted / safe mode ───────────────────────────────────
        if not msg_signature:
            logger.error("Encrypted POST body but no msg_signature")
            raise HTTPException(status_code=400, detail="missing msg_signature")

        expected_sig = wx.calc_signature(
            wx.WECHAT_TOKEN, timestamp, nonce, encrypt_field,
        )
        if msg_signature != expected_sig:
            logger.warning(
                f"WeChat POST signature mismatch: got={msg_signature} expected={expected_sig}"
            )
            raise HTTPException(status_code=403, detail="signature verification failed")

        try:
            inner_xml_str = wx.decrypt_message(encrypt_field)
        except Exception as e:
            logger.error(f"Failed to decrypt WeChat message: {e}")
            raise HTTPException(status_code=400, detail=f"decrypt message failed: {e}")
    else:
        # ── Plaintext mode ──────────────────────────────────────────
        if signature:
            expected_sig = wx.calc_signature(
                wx.WECHAT_TOKEN, timestamp, nonce,  # 3 params only
            )
            if signature != expected_sig:
                logger.warning(
                    f"WeChat POST (plaintext) signature mismatch: "
                    f"got={signature} expected={expected_sig}"
                )
                raise HTTPException(status_code=403, detail="signature verification failed")
        inner_xml_str = xml_str

    # Step 3: Parse the inner message XML
    msg = wx.parse_message_xml(inner_xml_str)
    msg_type = msg.get("MsgType", "")
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")

    logger.info(
        f"WeChat message: type={msg_type} from={from_user} "
        f"content={msg.get('Content', '')[:80]}"
    )

    # Step 6: Handle the message
    if msg_type == "event":
        # Handle subscribe / menu click events
        event = msg.get("Event", "")
        if event == "subscribe":
            reply_text = (
                "感谢关注靶点评估助手！\n\n"
                "直接发送基因名称（如 TP53、EGFR、KRAS），"
                "即可获取该基因的药物靶点价值评估报告。\n\n"
                "如需帮助，请发送「帮助」。"
            )
        else:
            reply_text = wx.HELP_TEXT
    elif msg_type == "text":
        content = msg.get("Content", "").strip()
        if not content:
            reply_text = wx.HELP_TEXT
        elif content in ("帮助", "help", "?", "？", "菜单"):
            reply_text = wx.HELP_TEXT
        else:
            gene = wx.normalize_gene_text(content)
            logger.info(f"Assessing gene: {gene} (raw input: {content})")
            access_logger.info(
                f"source=wechat user={from_user} gene={gene} raw_input={content}"
            )

            result = run_assessment(gene=gene)
            if result["status"] == "error":
                reply_text = (
                    f"无法识别「{content}」对应的基因符号。\n\n"
                    f"请检查基因名拼写，尝试以下基因：\n"
                    f"TP53、EGFR、KRAS、CD274、ERBB2、BRCA1\n\n"
                    f"{wx.HELP_TEXT}"
                )
            else:
                reply_text = wx.format_assessment_for_wechat(result)
    else:
        # Image, voice, video, etc. — return help text
        reply_text = (
            "暂不支持该消息类型。\n"
            "请直接输入基因名称（如 TP53），获取靶点评估结果。"
        )

    # Step 7: Build reply XML
    inner_xml = wx.build_text_reply_xml(
        to_user=from_user,  # Swap: reply goes back to sender
        from_user=to_user,
        content=reply_text,
    )

    # Step 8: Encrypt if in safe mode, otherwise return plaintext
    if encrypt_field:
        try:
            encrypted_content = wx.encrypt_message(inner_xml)
        except Exception as e:
            logger.error(f"Failed to encrypt reply: {e}")
            raise HTTPException(status_code=500, detail=f"encrypt reply failed: {e}")

        envelope_xml = wx.build_encrypted_envelope(
            encrypted_msg=encrypted_content,
            timestamp=timestamp,
            nonce=nonce,
        )
        return Response(content=envelope_xml, media_type="application/xml")
    else:
        return Response(content=inner_xml, media_type="application/xml")

