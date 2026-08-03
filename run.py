#!/usr/bin/env python3.8
"""
Target Assessment Tool - CLI

Usage:
    python run.py --gene EGFR --disease "NSCLC"
    python run.py --gene CLDN18 --disease "Gastric Cancer" --scenario adc
    python run.py --gene BRCA1 --disease "Ovarian Cancer" --scenario research --output-dir ./results
"""

import argparse
import json
import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from modules.gene_resolver import GeneResolver
from modules.data_manager import DataManager
from modules.scoring_engine import ScoringEngine
from modules.report_generator import ReportGenerator
from config import OUTPUTS_DIR, REPORTS_DIR, TABLES_DIR


def main():
    parser = argparse.ArgumentParser(
        description="靶点价值评估器 CLI · Target Assessment Tool — Command Line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python run.py --gene EGFR --disease NSCLC
              python run.py --gene CLDN18 --disease "Gastric Cancer" --scenario adc
              python run.py --gene BRCA1 --disease "Ovarian Cancer" --scenario research -o ./results
              python run.py --gene KRAS --disease NSCLC -w '{"disease_relevance": 0.25, "expression": 0.2, "dependency": 0.25}'
              python run.py --gene EGFR --disease NSCLC --weights ./my_weights.json
        """),
    )
    parser.add_argument("--gene", "-g", required=True, help="靶点基因符号 (e.g. EGFR, HER2, KRAS)")
    parser.add_argument("--disease", "-d", required=True, nargs="+",
                        help="疾病/癌种名称 (e.g. NSCLC, Breast Cancer)")
    parser.add_argument(
        "--scenario", "-s",
        default="general",
        choices=["research", "drug_development", "adc", "small_molecule", "general"],
        help="评估场景 (default: general)",
    )
    parser.add_argument(
        "--modality", "-m",
        default="any",
        choices=["any", "small_molecule", "antibody", "adc", "protac", "rna"],
        help="药物形式 (default: any)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="输出目录 (default: outputs/{reports,tables}/)",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式，只输出关键信息")
    parser.add_argument(
        "--weights", "-w",
        default=None,
        help=(
            "自定义维度权重。可以是 JSON 文件路径或 JSON 字符串。"
            "指定部分维度即可，其余维度保持场景默认值。"
            "例: --weights '{\"disease_relevance\": 0.25, \"expression\": 0.20, \"dependency\": 0.20}'"
        ),
    )

    args = parser.parse_args()
    args.disease = " ".join(args.disease)  # normalize nargs='+' list back to string

    # ------------------------------------------------------------------
    # Step 1: Resolve gene symbol
    # ------------------------------------------------------------------
    if not args.quiet:
        print(f"🔬 解析基因符号: {args.gene} ...", end=" ", flush=True)

    with GeneResolver() as resolver:
        gene_info = resolver.resolve(args.gene.strip())

    if gene_info.status == "empty_input":
        print(f"\n❌ 无法解析基因符号: {args.gene}")
        sys.exit(1)

    target_symbol = gene_info.symbol
    if not args.quiet:
        print(f"✓ {target_symbol} ({gene_info.full_name})")
        if gene_info.ensembl_id:
            print(f"   Ensembl ID: {gene_info.ensembl_id}")

    # ------------------------------------------------------------------
    # Step 2: Collect evidence
    # ------------------------------------------------------------------
    if not args.quiet:
        print(f"📡 收集多方证据 ...", end=" ", flush=True)

    dm = DataManager()
    evidence = dm.collect_evidence(
        target_symbol,
        args.disease.strip(),
        args.scenario,
        ensembl_id=gene_info.ensembl_id,
    )

    sources = evidence.get("data_sources", {}).get("real_sources", [])
    if not args.quiet:
        print(f"✓ ({len(sources)} data sources)")

    # ------------------------------------------------------------------
    # Step 2.5: Parse custom weights (if provided)
    # ------------------------------------------------------------------
    custom_weights = None
    if args.weights:
        raw = args.weights.strip()
        # Try as file path first, then as inline JSON string
        weights_path = Path(raw)
        if weights_path.is_file():
            try:
                custom_weights = json.loads(weights_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"\n❌ 权重文件 JSON 解析失败: {e}")
                sys.exit(1)
        else:
            try:
                custom_weights = json.loads(raw)
            except json.JSONDecodeError:
                print(f"\n❌ --weights 参数格式错误。请提供有效的 JSON 字符串或 JSON 文件路径。")
                print(f"   示例: --weights '{{\"disease_relevance\": 0.25, \"expression\": 0.20, \"dependency\": 0.20}}'")
                sys.exit(1)

        if not isinstance(custom_weights, dict):
            print(f"\n❌ --weights 必须是一个 JSON 对象 (dict)，而不是数组或其他类型。")
            sys.exit(1)

        if not args.quiet:
            print(f"⚖️  自定义权重: {custom_weights}")

    # ------------------------------------------------------------------
    # Step 3: Score
    # ------------------------------------------------------------------
    if not args.quiet:
        print(f"📊 多维评分 ...", end=" ", flush=True)

    engine = ScoringEngine(scenario=args.scenario, custom_weights=custom_weights,
                           gene_symbol=args.gene, disease=args.disease)
    score_result = engine.score(evidence)

    if not args.quiet:
        print(f"✓ 总分 {score_result['total_score']}/100 (Grade {score_result['grade']})")

    # ------------------------------------------------------------------
    # Step 4: Generate reports
    # ------------------------------------------------------------------
    gen = ReportGenerator()
    markdown_report = gen.generate_markdown(
        target_symbol=target_symbol,
        disease=args.disease.strip(),
        gene_info=gene_info.to_dict(),
        evidence=evidence,
        score_result=score_result,
    )

    # Determine output paths
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    disease_slug = args.disease.strip().replace(" ", "_").replace("/", "-")

    if args.output_dir:
        reports_dir = os.path.join(args.output_dir, "reports")
        tables_dir = os.path.join(args.output_dir, "tables")
    else:
        reports_dir = str(REPORTS_DIR)
        tables_dir = str(TABLES_DIR)

    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(tables_dir, exist_ok=True)

    # Save Markdown
    md_path = os.path.join(reports_dir, f"target_assessment_{target_symbol}_{disease_slug}_{timestamp}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_report)

    # Save HTML
    html_path = os.path.join(reports_dir, f"target_assessment_{target_symbol}_{disease_slug}_{timestamp}.html")
    gen.export_html(markdown_report, output_path=html_path)

    # Save Excel
    xlsx_path = os.path.join(tables_dir, f"evidence_{target_symbol}_{disease_slug}_{timestamp}.xlsx")
    gen.export_excel(evidence, score_result, output_path=xlsx_path)

    # ------------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print(f"  靶点价值评估报告")
    print("=" * 60)
    print(f"  基因: {target_symbol} ({gene_info.full_name})")
    print(f"  疾病: {args.disease.strip()}")
    print(f"  场景: {args.scenario}{' (自定义权重)' if custom_weights else ''}")
    print(f"  总分: {score_result['total_score']}/100  Grade: {score_result['grade']}")
    print(f"  结论: {score_result['recommendation']}")
    archetype = score_result.get("archetype", "balanced")
    archetype_labels = {
        "mutation_driven": "突变驱动型",
        "expression_driven": "表达驱动型",
        "dependency_driven": "依赖驱动型",
        "drug_target": "药物已验证型",
        "balanced": "均衡型",
    }
    print(f"  靶点原型: {archetype_labels.get(archetype, archetype)}")
    print("-" * 60)

    # Dimension scores
    scores = score_result["scores"]
    dim_labels = {
        "disease_relevance": "疾病相关性",
        "expression": "表达谱",
        "dependency": "依赖性",
        "mechanism": "机制通路",
        "druggability": "可药性",
        "safety": "安全性",
        "clinical_competition": "临床格局",
        "scenario_fit": "场景匹配",
    }
    dim_maxes = {
        "disease_relevance": 15, "expression": 15, "dependency": 15,
        "mechanism": 15, "druggability": 15, "safety": 10,
        "clinical_competition": 10, "scenario_fit": 5,
    }
    for dim_key, label in dim_labels.items():
        s = scores.get(dim_key, 0)
        max_s = dim_maxes[dim_key]
        bar = "█" * int(s / max_s * 20) + "░" * (20 - int(s / max_s * 20))
        print(f"  {label:　<8s} {bar} {s}/{max_s}")

    print("-" * 60)
    print(f"  📄 Markdown: {md_path}")
    print(f"  🌐 HTML:     {html_path}")
    print(f"  📊 Excel:    {xlsx_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
