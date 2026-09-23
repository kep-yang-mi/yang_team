#!/usr/bin/env python3
"""jev.py — TypeSafe Jev(System One) 결정 클라이언트 + 하네스 결정 지점 래퍼.

**상태(2026-09-23): 보류.** 사용자 지시로 Jev 연동은 후속 업데이트로 미룬다. 키가 비어 있으므로 모든 래퍼는
규칙 기반 폴백으로 동작하며 파이프라인 어디에서도 호출되지 않는다. 키를 넣은 뒤 `python3 api/jev.py --selftest`
로 연결을 확인하고, 그때 클린저·심판·승인 gate에서 이 모듈을 부르면 된다(각 래퍼의 docstring이 진입점).

왜 Jev인가: 이 하네스에는 "생성"이 아니라 **판정**인 지점이 있다 — 조직명이 어느 조직인지, 자유 텍스트
퇴직사유가 어느 범주인지, 루브릭 항목이 몇 점인지, 이 액션이 사람 승인 대상인지. Jev는 문자열을 만들지 않고
**타입이 정해진 확률 분포**를 돌려주므로(choice/score/noul), 값이 계약 밖으로 나갈 수 없고 재시도·파싱이 없다.

핵심 규칙 세 가지
  1. **키가 없으면 규칙 기반으로 폴백한다.** Jev는 품질을 올리는 보조이지 의존성이 아니다. 폴백 경로는
     항상 살아 있어야 데모와 재실행이 키 없이도 같은 파이프라인을 돈다.
  2. **응답은 캐시한다**(`_workspace/jev-cache/`). 같은 입력 → 같은 판정이어야 대사(reconciliation)가 성립한다.
  3. **낮은 확신은 사람에게 넘긴다.** confidence < 임계값이면 자동 채택하지 않고 `unresolved`/`needsReview`로
     표시한다(approval-gate-policy, claims-boundary-policy).

환경변수: TYPESAFE_API_KEY(없으면 폴백), TYPESAFE_MODEL(기본 jev-latest), TYPESAFE_BASE_URL.
표준 라이브러리만 사용한다.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.environ.get("ZERO_HR_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "_workspace", "jev-cache")
ENV_FILE = os.path.join(ROOT, ".env.local")
DEFAULT_MODEL = "jev-latest"
DEFAULT_BASE = "https://api.typesafe.ai/v1"
TIMEOUT = 20
CONF_MIN = 0.60          # 이 아래는 자동 채택하지 않는다
LOG_REL = os.path.join("_workspace", "jev-decisions.jsonl")


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------

def load_env(path=ENV_FILE):
    """`.env.local` 을 읽어 os.environ 에 없는 값만 채운다(값을 출력하지 않는다)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and not os.environ.get(k):
                os.environ[k] = v


def available():
    load_env()
    return bool(os.environ.get("TYPESAFE_API_KEY"))


def _cfg():
    load_env()
    return (os.environ.get("TYPESAFE_API_KEY"),
            os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL,
            (os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE).rstrip("/"))


# ---------------------------------------------------------------------------
# 호출
# ---------------------------------------------------------------------------

def _cache_path(payload):
    key = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:32]
    return os.path.join(CACHE_DIR, key + ".json")


def ask(state, questions, model=None, use_cache=True):
    """Jev 한 번 호출. questions = {id: {type: choice|score|noul, instructions, criteria?}}.

    한 요청에 여러 질문을 섞을 수 있고 각 질문은 병렬·독립으로 평가된다 — 결정 지점을 쪼개서 한 번에 묻는다.
    반환: {"ok": bool, "answers": {...}, "source": "jev"|"cache"|"fallback", "error": str|None}
    """
    api_key, default_model, base = _cfg()
    payload = {"state": state, "model": model or default_model, "questions": questions}
    if use_cache:
        path = _cache_path(payload)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                cached = json.load(fh)
            return {"ok": True, "answers": cached.get("answers", {}), "source": "cache", "error": None,
                    "usage": cached.get("usage"), "model": cached.get("model")}
    if not api_key:
        return {"ok": False, "answers": {}, "source": "fallback", "error": "TYPESAFE_API_KEY 없음"}
    req = urllib.request.Request(
        base + "/systemone",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer %s" % api_key, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        return {"ok": False, "answers": {}, "source": "fallback", "error": "HTTP %s %s" % (exc.code, detail)}
    except Exception as exc:
        return {"ok": False, "answers": {}, "source": "fallback", "error": "%s: %s" % (type(exc).__name__, exc)}
    if use_cache:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(payload), "w", encoding="utf-8") as fh:
            json.dump(body, fh, ensure_ascii=False, indent=2)
    return {"ok": True, "answers": body.get("answers", {}), "source": "jev", "error": None,
            "usage": body.get("usage"), "model": body.get("model")}


def log_decision(record):
    """판정 1건 1행. 무엇을 Jev에 물었고 무엇으로 정했는지 남긴다(handoff-log-policy의 근거)."""
    path = os.path.join(ROOT, LOG_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# 하네스 결정 지점 래퍼 — 모두 (값, 메타) 를 돌려주고 폴백을 가진다
# ---------------------------------------------------------------------------

def classify_department(raw_name, departments, job_family=None, fallback=None):
    """② 클린징: 규칙(별칭·편집거리)으로 못 고친 소속명을 조직에 배정한다.

    departments = {deptCode: "설명(조직명 + 하는 일)"}. 확신이 낮으면 채택하지 않고 미해결로 남긴다 —
    잘못 배정된 1명은 조직별 인원과 TO 과부족을 조용히 틀리게 만들기 때문이다.
    """
    state = "고객사 인원현황 마스터의 '소속' 값: %r\n직군: %s\n이 값은 조직 체계의 어떤 조직을 가리키는가?" % (
        raw_name, job_family or "(미상)")
    res = ask(state, {"department": {"type": "choice",
                                     "instructions": "이 소속 표기가 가리키는 조직",
                                     "criteria": departments}})
    if not res["ok"]:
        return fallback, {"decidedBy": "rule-fallback", "reason": res["error"], "confidence": None}
    ans = res["answers"].get("department", {})
    conf = ans.get("confidence", 0.0)
    meta = {"decidedBy": "jev:%s" % res["source"], "confidence": conf,
            "probabilities": ans.get("probabilities"), "unresolved": conf < CONF_MIN}
    log_decision({"point": "classify_department", "input": raw_name, "output": ans.get("choice"), **meta})
    if conf < CONF_MIN:
        return fallback, meta
    return ans.get("choice"), meta


def classify_separation_reason(free_text, reasons, fallback=None):
    """② 클린징: 자유 텍스트 퇴직사유를 정규 사유로. 퇴직 구분(자발/비자발) 집계의 입력이다."""
    res = ask("퇴사 예정자 파일의 '퇴직사유' 자유 기술: %r" % free_text,
              {"reason": {"type": "choice", "instructions": "정규 퇴직사유 분류", "criteria": reasons}})
    if not res["ok"]:
        return fallback, {"decidedBy": "rule-fallback", "reason": res["error"], "confidence": None}
    ans = res["answers"].get("reason", {})
    conf = ans.get("confidence", 0.0)
    meta = {"decidedBy": "jev:%s" % res["source"], "confidence": conf, "unresolved": conf < CONF_MIN}
    log_decision({"point": "classify_separation_reason", "input": free_text, "output": ans.get("choice"), **meta})
    return (ans.get("choice") if conf >= CONF_MIN else fallback), meta


def score_rubric_item(product_code, item, evidence_text, anchors, fallback=None):
    """제품 심판: 루브릭 항목 1개를 0~10 스케일로 채점한다.

    anchors = ["0점 기준", "3점", "5점", "8점", "10점"] 처럼 순서가 있는 수준 설명(2~10개).
    score 원시형은 순서 있는 수준의 분포와 기댓값을 돌려주므로, 심판의 "느낌"이 아니라 보정된 값이 남는다.
    """
    state = ("제품: %s\n루브릭 항목: %s\n\n페이지에서 관찰된 증거:\n%s" % (product_code, item, evidence_text))[:12000]
    res = ask(state, {"rubric": {"type": "score", "instructions": item, "criteria": anchors}})
    if not res["ok"]:
        return fallback, {"decidedBy": "judge-fallback", "reason": res["error"], "confidence": None}
    ans = res["answers"].get("rubric", {})
    levels = max(len(anchors) - 1, 1)
    score10 = round(float(ans.get("score", 0)) / levels * 10, 1)
    meta = {"decidedBy": "jev:%s" % res["source"], "confidence": ans.get("confidence"),
            "rawScore": ans.get("score"), "levels": len(anchors), "probabilities": ans.get("probabilities")}
    log_decision({"point": "score_rubric_item", "product": product_code, "item": item, "output": score10, **meta})
    return score10, meta


def needs_approval(action, payload_text, fallback=True):
    """승인 gate: 이 액션이 사람 승인 대상인가(noul = 명제의 확률). 기본값은 '필요하다'로 기운다."""
    state = "실행하려는 액션: %s\n내용: %s" % (action, payload_text[:4000])
    res = ask(state, {
        "external_effect": {"type": "noul", "instructions": "이 액션은 회사 밖으로 나가거나 되돌리기 어려운 효과를 만든다"},
        "sensitive": {"type": "noul", "instructions": "이 액션은 개인 식별정보나 민감정보에 접근하거나 노출한다"},
    })
    if not res["ok"]:
        return fallback, {"decidedBy": "policy-fallback", "reason": res["error"]}
    ext = float(res["answers"].get("external_effect", {}).get("noul", 0.0))
    sen = float(res["answers"].get("sensitive", {}).get("noul", 0.0))
    meta = {"decidedBy": "jev:%s" % res["source"], "externalEffect": ext, "sensitive": sen}
    log_decision({"point": "needs_approval", "action": action, "output": bool(ext >= 0.5 or sen >= 0.5), **meta})
    return bool(ext >= 0.5 or sen >= 0.5), meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def selftest():
    load_env()
    key, model, base = _cfg()
    out = {"keyPresent": bool(key), "model": model, "baseUrl": base, "cacheDir": os.path.relpath(CACHE_DIR, ROOT)}
    if not key:
        out["status"] = "fallback-only"
        out["note"] = ".env.local 의 TYPESAFE_API_KEY 가 비어 있다 — 모든 결정 지점이 규칙 기반으로 동작한다."
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    res = ask("Zero Company HR 하네스의 연결 점검 요청입니다.",
              {"reachable": {"type": "noul", "instructions": "이 문장은 연결 점검용이다"}}, use_cache=False)
    out["status"] = "ok" if res["ok"] else "error"
    out["source"] = res["source"]
    out["error"] = res["error"]
    out["usage"] = res.get("usage")
    out["modelReturned"] = res.get("model")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="TypeSafe Jev 클라이언트 / 하네스 결정 지점")
    ap.add_argument("--selftest", action="store_true", help="키 존재와 연결을 확인한다(값은 출력하지 않는다)")
    ap.add_argument("--ask", metavar="STATE", help="임시 질문: noul 하나로 물어본다")
    ap.add_argument("--instructions", default="이 문장은 참이다")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.ask:
        res = ask(args.ask, {"q": {"type": "noul", "instructions": args.instructions}})
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
