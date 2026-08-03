# Target Assessment REST API — Design Spec

## Summary

在一个现有项目中新增一个 FastAPI REST API。可以通过 HTTP 调用，获取靶点评估结果，可以被从 R、Python、微信公众号或其他HTTP客户端调用。

Add a FastAPI REST API layer on top of the existing target assessment engine,
consumable from R, Python, WeChat Official Account backends, or any HTTP client.

## Endpoints

| Method | Path       | Description                  |
|--------|------------|------------------------------|
| POST   | `/assess`  | Run target assessment        |
| GET    | `/health`  | Health check                 |
| GET    | `/docs`    | Swagger UI (FastAPI built-in)|

## POST `/assess`

### Request (JSON)

| Field    | Type   | Required | Default        | Description                            |
|----------|--------|----------|----------------|----------------------------------------|
| gene     | string | yes      | —              | HGNC symbol or alias                   |
| disease  | string | no       | `"pan-cancer"` | Disease / cancer type                  |
| scenario | string | no       | `"general"`    | research / drug_development / adc / small_molecule / general |
| format   | string | no       | `"full"`       | `full` or `summary`                    |

### Response `format=full`

```json
{
  "gene": {"symbol": "EGFR", "full_name": "...", "ensembl_id": "..."},
  "disease": "pan-cancer",
  "scenario": "general",
  "total_score": 60.2,
  "grade": "C",
  "grade_label": "谨慎推进",
  "recommendation": "...",
  "archetype": "mutation_driven",
  "scores": {"disease_relevance": {"score": 9.8, "max": 15}, ...},
  "evidence": {...}
}
```

### Response `format=summary`

```json
{
  "gene": "EGFR",
  "disease": "pan-cancer",
  "total_score": 60.2,
  "grade": "C",
  "recommendation": "...",
  "archetype": "mutation_driven",
  "scores": {"disease_relevance": 9.8, "expression": 4.2, ...}
}
```

### Error response

```json
{"error": true, "message": "...", "code": "GENE_NOT_FOUND"}
```

## Files Changed

- `api.py` — new file, FastAPI app + Pydantic models + route handlers
- `requirements.txt` — add `fastapi`, `uvicorn`

## Startup

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## Callers

- **Python**: `requests.post("http://host:8000/assess", json={"gene": "EGFR"})`
- **R**: `httr::POST("http://host:8000/assess", body = list(gene = "EGFR"), encode = "json")`
- **WeChat backend**: same as Python caller, then format WeChat reply from JSON result
