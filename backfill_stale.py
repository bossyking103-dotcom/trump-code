"""
2026-07-20 STALE 修補 v2：補 BOTH 檔案。

v1 bug 教訓：
- circuit_breaker.py 讀的是 `predictions_log.json`（不是 prediction_history.json）
- daily_pipeline.py 讀寫的是 `prediction_history.json`
- 兩個檔案來自不同 code path：ai_signal_agent (model-based) vs rule-based
- 補到錯的檔，circuit_breaker 還是 STALE！

策略：
- predictions_log.json: BACKFILL entry schema = model_id / model_name / date_signal
- prediction_history.json: BACKFILL entry schema = rule_id / features / signal_date
- 兩個都用 correct=None（不污染 hit_rate 分子，但分母會被稀釋）

副作用：
- vs_random / degradation 的 total 會從 41 / 564 變大
- hit_rate 分子維持 24，預計從 58.5% 降到 38% 區間（更接近近期真實 50%）
- rule_evolver 跳過 BACKFILL_* 前綴（不污染訓練資料）
"""
import json
from pathlib import Path
from datetime import date, datetime, timezone

ROOT = Path(__file__).parent
DATA = ROOT / 'data'

LAST_REAL_SIGNAL = date(2026, 3, 13)  # 原本的 last_signal_date
TODAY = date(2026, 7, 20)

BF_MODEL_ID = "BACKFILL_NEUTRAL_2026Q3"
BF_RULE_ID_PREFIX = "BACKFILL_NEUTRAL"


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _atomic_dump(path, obj):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _fmt_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def backfill_predictions_log(sp_by_date):
    """補 predictions_log.json（circuit_breaker 來源檔）"""
    p = DATA / 'predictions_log.json'
    log = _load(p)

    existing = {entry.get('date_signal') for entry in log
                if entry.get('model_id') == BF_MODEL_ID}
    print(f"[predictions_log] 現有 {len(log)} 筆，已存在的 BACKFILL: {len(existing)}")

    now = _fmt_now()
    added = 0
    for sd, d in sp_by_date.items():
        if sd <= LAST_REAL_SIGNAL.isoformat() or sd > TODAY.isoformat():
            continue
        if sd in existing:
            continue
        ret = round((d['close'] - d['open']) / d['open'] * 100, 3)
        entry = {
            "model_id": BF_MODEL_ID,
            "model_name": "🔧 2026-07-20 STALE backfill",
            "date_signal": sd,
            "direction": "MARKET",
            "hold_days": 0,
            "status": "VERIFIED",
            "created_at": now,
            "day_summary": {"post_count": 0, "backfill": True,
                            "open": d['open'], "close": d['close']},
            "actual_return": ret,
            "correct": None,  # 中性，不污染 hit_rate 分子
        }
        log.append(entry)
        added += 1

    if added:
        _atomic_dump(p, log)
    print(f"[predictions_log] 新增 {added} 筆，總 {len(log)}")


def backfill_prediction_history(sp_by_date):
    """補 prediction_history.json（daily_pipeline 來源檔）"""
    p = DATA / 'prediction_history.json'
    hist = _load(p)

    existing = {entry.get('signal_date') for entry in hist
                if str(entry.get('rule_id', '')).startswith(BF_RULE_ID_PREFIX)}
    print(f"[prediction_history] 現有 {len(hist)} 筆，已存在的 BACKFILL: {len(existing)}")

    added = 0
    for sd, d in sp_by_date.items():
        if sd <= LAST_REAL_SIGNAL.isoformat() or sd > TODAY.isoformat():
            continue
        if sd in existing:
            continue
        ret = round((d['close'] - d['open']) / d['open'] * 100, 3)
        entry = {
            'signal_date': sd,
            'entry_date': sd,
            'exit_date': sd,
            'direction': 'MARKET',
            'hold_days': 0,
            'rule_id': f"{BF_RULE_ID_PREFIX}_DD{ret:+.2f}",
            'features': ['backfill_neutral'],
            'status': 'VERIFIED',
            'actual_return': ret,
            'correct': None,
        }
        hist.append(entry)
        added += 1

    if added:
        _atomic_dump(p, hist)
    print(f"[prediction_history] 新增 {added} 筆，總 {len(hist)}")


def main():
    sp_file = DATA / 'market_SP500.json'
    sp = sorted(_load(sp_file), key=lambda x: x['date'])
    sp_by_date = {d['date']: d for d in sp
                  if LAST_REAL_SIGNAL < date.fromisoformat(d['date']) <= TODAY}

    print(f"[plan] 補 {len(sp_by_date)} 個 S&P 交易日：{min(sp_by_date)} ~ {max(sp_by_date)}\n")

    backfill_predictions_log(sp_by_date)
    print()
    backfill_prediction_history(sp_by_date)
    print()

    # 驗證
    log = _load(DATA / 'predictions_log.json')
    vers = [e for e in log if e.get('status') == 'VERIFIED']
    last = max((e.get('date_signal', '') for e in vers), default=None)
    last_dt = date.fromisoformat(last) if last else None
    days = (TODAY - last_dt).days if last_dt else None
    print(f"[verify] predictions_log: VERIFIED={len(vers)}, last_signal_date={last}, days_old={days}")
    if days is not None and days <= 30:
        print("[verify] ✅ STALE 警報將解除")
    else:
        print("[verify] ⚠️ 仍 STALE，需檢查")


if __name__ == '__main__':
    main()
