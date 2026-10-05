from src.i18n_runtime import L as _L, LF as _LF
# 为实时战报页面和悬浮窗标明采集摘要实际使用的 DPS 计时方式。
def summary_clock_label(mode: str) -> str:
    return {
        "subtract_time_stop": _L('有效时间'),
        "wall_clock": _L('真实时间'),
    }.get(mode, _L('计时未知'))
