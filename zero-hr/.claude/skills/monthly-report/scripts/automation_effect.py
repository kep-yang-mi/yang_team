#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""automation_effect.py — 기대 효과 ①(완전 자동화) 증빙. DATA_CONTRACT v2 §8.

_workspace/run_meta.json 의 durations(totalSeconds, 없으면 단계 합)를 pipelineSeconds 로 읽고 data/stats/automation-effect.json 을 쓴다.
수작업 공수 40h·검토 공수 8h·절감률 0.8은 계약 §8의 가정값이며 추정임을 note 에 명시한다(reconciliation-policy 5: 가정 명시).
핸드오프 로그: 실행 시작·종료 시 _workspace/handoff/10-report-automation-effect.md (10-report 단계의 인스턴스 로그 — render_report.py 의
10-report.md 를 덮어쓰지 않기 위해 별도 파일).
사용법: python3 automation_effect.py --root R --as-of 2026-09-23   (stdout 마지막 줄 = 요약 JSON 1행)
"""
import argparse
import datetime
import json
import os
import sys
from collections import OrderedDict

DEFAULT_ROOT = "/Users/yang/development/zero-hr"
DEFAULT_AS_OF = "2026-09-23"
RUN_META_REL = "_workspace/run_meta.json"
OUT_REL = "data/stats/automation-effect.json"
HANDOFF_REL = "_workspace/handoff/10-report-automation-effect.md"
MANUAL = OrderedDict([("수집·통합", 8), ("클린징", 12), ("집계·예측", 12), ("리포트 작성·배포", 8)])
REVIEW = OrderedDict([("미해결 항목 확인", 3), ("리포트 검토·승인(승인 gate)", 5)])
SECTIONS = ["시도한 것", "본 데이터·근거", "실패한 것", "검증된 것", "다음 agent 인계점"]


def write_handoff(root, as_of, phase, sections):
    path = os.path.join(root, HANDOFF_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = datetime.datetime.now().replace(microsecond=0).isoformat()
    lines = ["# 10-report-automation-effect — monthly-report-mailer · asOfDate %s · %s %s" % (as_of, phase, now), ""]
    for k in SECTIONS:
        lines.append("## " + k)
        lines.extend("- " + t for t in (sections.get(k) or ["없음"]))
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def pipeline_seconds(root):
    """(초, run_meta 존재 여부, 비고). totalSeconds 우선, 없으면 단계 durations 합."""
    path = os.path.join(root, RUN_META_REL)
    if not os.path.exists(path):
        return 0.0, False, "run_meta.json 부재 — pipelineSeconds 0"
    try:
        with open(path, encoding="utf-8") as f:
            durations = json.load(f).get("durations") or {}
        total = durations.get("totalSeconds")
        if not total:
            total = sum(float(v or 0) for k, v in durations.items() if k != "totalSeconds")
        return round(float(total), 1), True, "run_meta.durations 실측"
    except (ValueError, TypeError, AttributeError) as e:
        return 0.0, False, "run_meta.json 파싱 실패(%s) — pipelineSeconds 0" % type(e).__name__


def main(argv=None):
    p = argparse.ArgumentParser(description="자동화 효과 증빙 (DATA_CONTRACT v2 §8)")
    p.add_argument("--root", default=DEFAULT_ROOT)
    p.add_argument("--as-of", dest="as_of", default=DEFAULT_AS_OF)
    a = p.parse_args(argv)
    sections = OrderedDict((k, []) for k in SECTIONS)
    sections["시도한 것"].append("실행: `python3 automation_effect.py --root %s --as-of %s`" % (a.root, a.as_of))
    sections["다음 agent 인계점"].append("실행 중 — 종료 시 덮어씀")
    write_handoff(a.root, a.as_of, "시작", sections)
    sections["다음 agent 인계점"] = []
    try:
        seconds, from_meta, remark = pipeline_seconds(a.root)
        manual_hours, review_hours = sum(MANUAL.values()), sum(REVIEW.values())
        effect = OrderedDict([
            ("asOfDate", a.as_of),
            ("manualBaseline", OrderedDict([("hoursPerMonth", manual_hours), ("breakdown", MANUAL),
                                            ("basis", "중견 스타트업 HR 월간 인원 리포트 수작업 공수 추정(가정)")])),
            ("automated", OrderedDict([("pipelineSeconds", seconds), ("humanReviewHoursPerMonth", review_hours), ("breakdown", REVIEW)])),
            ("savingRate", round(1 - review_hours / float(manual_hours), 2)),
            ("note", "가정 기반 추정치. 고객사 실측으로 갱신" + ("" if from_meta else " (%s)" % remark)),
        ])
        out = os.path.join(a.root, OUT_REL)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(effect, f, ensure_ascii=False, indent=2)
        sections["본 데이터·근거"].append("`%s` %s · 근거: DATA_CONTRACT §8(수작업 40h·검토 8h·savingRate 0.8은 가정값)" % (RUN_META_REL, remark))
        if not from_meta:
            sections["실패한 것"].append("실측 없음 — pipelineSeconds 0. 오케스트레이터가 run_meta.json을 쓴 뒤 이 스크립트를 재실행하면 갱신")
        sections["검증된 것"].append("`%s` 작성: manualBaseline %sh · humanReview %sh · savingRate %s · pipelineSeconds %s · note에 '추정' 명시"
                                 % (OUT_REL, manual_hours, review_hours, effect["savingRate"], seconds))
        sections["다음 agent 인계점"].append("render_report.py(같은 --root/--as-of)가 이 파일을 읽어 '자동화 효과 (추정)' 절을 렌더 · product-builder(insight)가 그대로 내장")
        code, summary = 0, OrderedDict([("status", "ok"), ("output", OUT_REL), ("pipelineSeconds", seconds), ("runMetaFound", from_meta),
                                        ("savingRate", effect["savingRate"]), ("handoffLog", HANDOFF_REL)])
    except Exception as e:  # noqa: BLE001
        sections["실패한 것"].append("예외 %s: %s → 파일 미작성" % (type(e).__name__, str(e)[:200]))
        code, summary = 1, OrderedDict([("status", "error"), ("errorType", type(e).__name__), ("error", str(e)), ("handoffLog", HANDOFF_REL)])
    write_handoff(a.root, a.as_of, "종료 exit %d" % code, sections)
    print(json.dumps(summary, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
