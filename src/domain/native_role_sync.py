from src.i18n_runtime import L as _L, LF as _LF
# 定义角色稀疏同步的实际保存数量与未采用字段说明。
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NativeRoleSyncResult:
    saved_count: int
    warnings: tuple[str, ...] = ()

    @property
    def message(self) -> str:
        summary = (_LF('已同步 {0} 个角色的已确认字段。').format((self.saved_count)) if self.saved_count
                   else _L('本次未写入新的角色状态。'))
        if self.warnings:
            return summary + _L('\n以下字段未同步，保留原配置：\n') + '\n'.join(self.warnings)
        return summary + _L('其余养成配置保持原值。')
