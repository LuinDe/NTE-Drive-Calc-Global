# 构建“游戏资料库”伤害公式与反事实支持状态的只读领域投影。
"""Auditable read-only formula catalog and counterfactual support matrix."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.storage.sqlite.static_catalog_formula_queries import (
    StaticCatalogFormulaQueries,
    StaticFormulaEvidenceSnapshot,
)

EvidenceKind = Literal[
    "project_contract",
    "implementation",
    "public_behavior_test",
    "official_static",
    "repository_audit",
]
DataBoundary = Literal[
    "project_rule",
    "official_static_input",
    "runtime_derived",
    "observed_runtime",
]
SupportStatus = Literal["complete", "partial", "unavailable", "not_applicable"]


@dataclass(frozen=True, slots=True)
class CatalogEvidenceReference:
    kind: EvidenceKind
    path: str
    symbol: str
    note: str


@dataclass(frozen=True, slots=True)
class FormulaVariable:
    symbol: str
    meaning: str


@dataclass(frozen=True, slots=True)
class FormulaEntry:
    key: str
    section: str
    title: str
    expression: str
    boundary: DataBoundary
    variables: tuple[FormulaVariable, ...]
    applicable_when: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence: tuple[CatalogEvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class CounterfactualSupportEntry:
    key: str
    category: str
    mechanism: str
    scope: str
    status: SupportStatus
    modeling_scheme: str
    evidence: tuple[CatalogEvidenceReference, ...]
    consumer_entries: tuple[str, ...]
    gap_codes: tuple[str, ...]
    covered_dataset: str
    covered_entities: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StaticCatalogFormulaDomain:
    projection_version: str
    readonly: bool
    evidence_snapshot: StaticFormulaEvidenceSnapshot
    formulas: tuple[FormulaEntry, ...]
    counterfactual_support: tuple[CounterfactualSupportEntry, ...]


def _ref(
    kind: EvidenceKind,
    path: str,
    symbol: str,
    note: str,
) -> CatalogEvidenceReference:
    return CatalogEvidenceReference(kind=kind, path=path, symbol=symbol, note=note)


def _formula_entries(
    snapshot: StaticFormulaEvidenceSnapshot,
) -> tuple[FormulaEntry, ...]:
    contract = "docs/reference/damage-calculation.md"
    calculation = "src/services/damage_calculation_service.py"
    replay = "src/services/battle_hit_replay_service.py"
    static_note = (
        f"dataset={snapshot.dataset_id}; normalized skill_damage rows="
        f"{snapshot.skill_damage_rows}; these are inputs, not the project formula"
    )
    return (
        FormulaEntry(
            key="panel_attribute",
            section=_L('基础值与角色面板'),
            title=_L('角色面板属性'),
            expression="Panel = Base × (1 + Up) + Add",
            boundary="project_rule",
            variables=(
                FormulaVariable("Base", _L('人物、弧盘等基础值合计')),
                FormulaVariable("Up", _L('同一属性百分比加成合计')),
                FormulaVariable("Add", _L('同一属性固定值加成合计')),
            ),
            applicable_when=(_L('攻击、生命、防御面板重建'),),
            limitations=(
                _L('来源是否进入 Base、Up 或 Add 由各来源的正式属性定义决定。'),
                _L('文档公式是项目规则，不是 SQLite 字段。'),
            ),
            evidence=(
                _ref("project_contract", contract, _L('基础属性区'), _L('定义 Base/Up/Add 归类')),
                _ref(
                    "implementation",
                    calculation,
                    "calculate_attribute_value",
                    _L('纯函数实现面板合计'),
                ),
                _ref(
                    "public_behavior_test",
                    "tests/test_damage_calculation_service.py",
                    "test_direct_damage_returns_every_confirmed_multiplier",
                    _L('验证攻击、生命、防御三个面板值'),
                ),
            ),
        ),
        FormulaEntry(
            key="skill_multiplier",
            section=_L('基础值与角色面板'),
            title=_L('技能倍率与 CoefModify'),
            expression="SkillCoef = SourceTierCoef × (1 + Σ CoefModify)",
            boundary="project_rule",
            variables=(
                FormulaVariable("SourceTierCoef", _L('有效技能等级对应的正式倍率档')),
                FormulaVariable("CoefModify", _L('正式作用于该技能标签的倍率系数修正')),
            ),
            applicable_when=(_L('逐击已绑定正式 skill_damage 与技能等级证据'),),
            limitations=(
                _L('缺少唯一技能/伤害项绑定时保持 unknown，不默认按攻击倍率。'),
                _L('静态倍率数组只是输入；等级映射与修正公式属于项目规则。'),
            ),
            evidence=(
                _ref("project_contract", contract, _L('技能倍率系数修正'), _L('定义乘法修正')),
                _ref(
                    "implementation",
                    "src/services/battle_skill_damage_evidence_service.py",
                    "BattleSkillDamageEvidenceService.load",
                    _L('装配正式倍率、属性与暴击策略证据'),
                ),
                _ref("official_static", "data/game_static.sqlite3", "skill_damage", static_note),
                _ref(
                    "official_static",
                    "data/game_static.sqlite3",
                    "skill_damage_modifier",
                    f"normalized modifier rows={snapshot.skill_damage_modifier_rows}",
                ),
            ),
        ),
        FormulaEntry(
            key="direct_damage",
            section=_L('直伤乘区'),
            title=_L('直伤总公式'),
            expression=(
                "Direct = SkillCoef × ScalingPanel × DamageUp × Crit × Defense "
                "× Resistance × Vulnerability × Π Independent"
            ),
            boundary="project_rule",
            variables=(
                FormulaVariable("ScalingPanel", _L('伤害项指定的攻击/生命/防御面板')),
                FormulaVariable("Independent", _L('每个明确独立最终来源的乘数')),
            ),
            applicable_when=(_L('普通直伤且必需技能、面板、目标公式输入可解析'),),
            limitations=(_L('DOT、倾陷、覆纹与生命上限结算使用各自出口。'),),
            evidence=(
                _ref("project_contract", contract, _L('直伤总公式'), _L('项目金标准乘区顺序')),
                _ref(
                    "implementation",
                    calculation,
                    "DamageCalculationService.calculate_direct",
                    _L('返回全部已确认乘区'),
                ),
                _ref(
                    "implementation",
                    replay,
                    "BattleHitReplayService._replay_direct",
                    _L('固定轴逐击重放消费者'),
                ),
            ),
        ),
        FormulaEntry(
            key="damage_increase",
            section=_L('直伤乘区'),
            title=_L('增伤区'),
            expression="DamageUp = 1 + Σ damage_increase",
            boundary="project_rule",
            variables=(FormulaVariable("damage_increase", _L('通用/属性/技能/状态增伤')),),
            applicable_when=(_L('来源标签与当前逐击作用域匹配'),),
            limitations=(_L('敌方易伤与 FinalDamageUp 不进入本区。'),),
            evidence=(
                _ref("project_contract", contract, _L('增伤区'), _L('定义同区相加')),
                _ref("implementation", calculation, "calculate_additive_multiplier", _L('1+合计')),
            ),
        ),
        FormulaEntry(
            key="vulnerability",
            section=_L('直伤乘区'),
            title=_L('易伤区'),
            expression="Vulnerability = 1 + Σ target_damage_taken_up",
            boundary="project_rule",
            variables=(
                FormulaVariable("target_damage_taken_up", _L('目标身上的受伤提升 Debuff')),
            ),
            applicable_when=(_L('目标身份/作用域与 Debuff 区间可绑定'),),
            limitations=(_L('玩家侧增伤和 DOT 专属 FinalDamageUp 不进入本区。'),),
            evidence=(
                _ref("project_contract", contract, _L('易伤区'), _L('定义敌方独立加法区')),
                _ref("implementation", calculation, "calculate_additive_multiplier", _L('共享加法乘区函数')),
            ),
        ),
        FormulaEntry(
            key="critical",
            section=_L('直伤乘区'),
            title=_L('暴击分支与期望'),
            expression=(
                "NonCrit = floor(FullPrecision); Crit = floor(FullPrecision × "
                "(1 + CritDamage)); Expected = (1-r)×NonCrit + r×Crit"
            ),
            boundary="project_rule",
            variables=(
                FormulaVariable("r", _L('角色、固定、禁用或 unknown 暴击策略给出的暴击率')),
                FormulaVariable("CritDamage", _L('暴击伤害加成')),
            ),
            applicable_when=(_L('一次实际结算在所有其他乘区完成后选择暴击分支'),),
            limitations=(_L('unknown 暴击策略不得生成期望值或冒充未暴击。'),),
            evidence=(
                _ref("project_contract", contract, _L('暴击区'), _L('区分实际分支与统计期望')),
                _ref("implementation", replay, "BattleHitReplayService._replay_direct", _L('分别取整两个候选')),
                _ref(
                    "public_behavior_test",
                    "tests/test_battle_counterfactual_marginal_integration.py",
                    "test_unknown_crit_policy_remains_unquantified",
                    _L('unknown 暴击不量化'),
                ),
            ),
        ),
        FormulaEntry(
            key="defense",
            section=_L('目标减伤'),
            title=_L('防御区'),
            expression=(
                "EnemyDef = [DefBase×(1+DefUp)+DefAdd]/6 × (1-Pen) × "
                "(1-Reduction); Defense = (Level+100)/(EnemyDef+Level+100)"
            ),
            boundary="project_rule",
            variables=(
                FormulaVariable("Pen", _L('攻击方防御穿透/无视')),
                FormulaVariable("Reduction", _L('目标防御降低')),
            ),
            applicable_when=(_L('优先使用冻结敌方属性包；缺失时才用明确场景近似'),),
            limitations=(_L('目标画像未知且候选防御不等价时不可量化。'),),
            evidence=(
                _ref("project_contract", contract, _L('防御区'), _L('属性包优先与场景回退')),
                _ref("implementation", calculation, "calculate_enemy_defense_from_profile", "DefBase/6"),
                _ref("implementation", calculation, "calculate_defense_multiplier", _L('等级防御乘区')),
            ),
        ),
        FormulaEntry(
            key="resistance",
            section=_L('目标减伤'),
            title=_L('抗性区'),
            expression="X = BaseRes-Reduction-Pen; X≥0: 1-X; X<0: 1-X/1.10",
            boundary="project_rule",
            variables=(
                FormulaVariable("BaseRes", _L('冻结目标画像中该伤害属性的战前最终抗性')),
                FormulaVariable("Reduction/Pen", _L('动态减抗与攻击方属性穿透')),
            ),
            applicable_when=(_L('逐击伤害属性与目标画像可解析'),),
            limitations=(_L('怪物弱点目录不是额外增伤；不得按中文名猜抗性。'),),
            evidence=(
                _ref("project_contract", contract, _L('抗性区'), _L('正负抗分段')),
                _ref("implementation", calculation, "calculate_resistance_multiplier", _L('分段纯函数')),
            ),
        ),
        FormulaEntry(
            key="independent_final_damage",
            section=_L('特殊最终乘区'),
            title=_L('通用独立 FinalDamageUp'),
            expression="Independent = Π(1 + each explicit FinalDamageUp)",
            boundary="runtime_derived",
            variables=(
                FormulaVariable("FinalDamageUp", _L('正式效果且作用标签/条件已解析的独立最终增伤')),
            ),
            applicable_when=(_L('正式属性与逐击 Source/Target 条件均匹配'),),
            limitations=(
                _L('属性名相似不代表条件已满足。'),
                _L('DOT 双端标签限定的 FinalDamageUp 必须走 DOT 专属槽位。'),
            ),
            evidence=(
                _ref("project_contract", contract, _L('独立乘区'), _L('独立项逐项相乘')),
                _ref("implementation", replay, "BattleHitReplayService._replay_direct", _L('识别最终伤害属性')),
                _ref(
                    "official_static",
                    "data/game_static.sqlite3",
                    "buff_modifier.property_id=FinalDamageUp",
                    f"formal modifier rows={snapshot.final_damage_up_modifier_rows}",
                ),
            ),
        ),
        FormulaEntry(
            key="dot_damage",
            section="特殊伤害",
            title=_L('DOT 单跳与 DOT 专属最终乘区'),
            expression=(
                "DotTick = DirectLikeFormula(fixed crit policy) × StateStacks × "
                "[1 + min(PreHitDotKinds×25%, 100%)]"
            ),
            boundary="runtime_derived",
            variables=(
                FormulaVariable("StateStacks", _L('同一目标/半场的结算前 DOT 层数或系数')),
                FormulaVariable("PreHitDotKinds", _L('结算前仍有效的已审计 DOT 种类数')),
            ),
            applicable_when=(_L('正式 State.Damage.Dot 标签拥有伤害分类'),),
            limitations=(
                _L('当前状态重放只覆盖噩梦、蚀心、鸩火、浊燃及文档列出的短窗证据。'),
                _L('有 DOT 标签就是 DOT；不能用手工伤害通道白名单替代。'),
            ),
            evidence=(
                _ref("project_contract", contract, _L('DOT 专属最终乘区'), _L('结算前种类计数')),
                _ref(
                    "implementation",
                    "src/services/battle_dot_stack_state_service.py",
                    "reconstruct_dot_stack_states",
                    _L('按半场/目标逐击重放四类状态'),
                ),
                _ref(
                    "official_static",
                    "data/game_static.sqlite3",
                    "combat_blueprint_tag:State.Damage.Dot",
                    f"formal tag assets={snapshot.formal_dot_tag_assets}",
                ),
                _ref(
                    "official_static",
                    "data/game_static.sqlite3",
                    "buff_modifier:DOT-scoped FinalDamageUp",
                    f"formal tag-scoped rows={snapshot.dot_scoped_final_damage_up_modifier_rows}",
                ),
            ),
        ),
        FormulaEntry(
            key="topple_damage",
            section="特殊伤害",
            title="倾陷伤害",
            expression=(
                "Topple = LevelCurve × (1+Strength/300+ΣToppleUp) × "
                "max(1, UnbalMax/3) × Defense × Resistance"
            ),
            boundary="project_rule",
            variables=(
                FormulaVariable("LevelCurve", _L('角色等级对应的正式倾陷曲线')),
                FormulaVariable("UnbalMax", _L('目标倾陷上限或冻结档位覆盖')),
            ),
            applicable_when=(_L('倾陷结算行具有完整同半场角色和目标画像证据'),),
            limitations=(_L('失谐 15% 上限下降是项目默认模型，不冒充官方已验证基础比例。'),),
            evidence=(
                _ref("project_contract", contract, "倾陷伤害", _L('五乘区规则')),
                _ref("implementation", calculation, "DamageCalculationService.calculate_topple", _L('五乘区纯函数')),
                _ref(
                    "public_behavior_test",
                    "tests/test_damage_calculation_service.py",
                    "test_topple_damage_uses_only_its_five_confirmed_multipliers",
                    _L('锁定五乘区范围'),
                ),
            ),
        ),
        FormulaEntry(
            key="weave_followup",
            section="特殊伤害",
            title=_L('覆纹追加伤害'),
            expression="Weave = ActualDamage × [(C+L)×(1+P)×R + clamp(R-1,0,100)] × F",
            boundary="project_rule",
            variables=(
                FormulaVariable("S", _L('被记录原伤害实际来源角色的环合强度，最低为 0')),
                FormulaVariable("C / L / P", _L('C 为 20%；弱点感应启用时 L、P 各 10%，否则各 0%；(20% + 10%) × (1 + 10%) = 33%')),
                FormulaVariable("R / F", _L('R = 1+0.20×S/(S+180)；最终乘数 F 当前取 1')),
            ),
            applicable_when=(_L('正式覆纹追加伤害继承被记录原伤害的属性'),),
            limitations=(_L('当前 33% 的拆分解释，非已独立确认的游戏结算顺序；P 只乘复制部分，其他追击增伤不直接代入。'),),
            evidence=(
                _ref("project_contract", contract, _L('环合基础规则'), _L('覆纹强度乘区')),
            ),
        ),
        FormulaEntry(
            key="settlement_rounding",
            section=_L('结算'),
            title=_L('最终伤害向下取整'),
            expression="Settlement = floor(max(0, FullPrecisionDamage))",
            boundary="project_rule",
            variables=(FormulaVariable("FullPrecisionDamage", _L('所有适用乘区完整精度乘积')),),
            applicable_when=(_L('一次实际直伤、DOT、特殊伤害、覆纹或倾陷出口'),),
            limitations=(_L('中间属性与乘区不取整；暴击期望允许小数。'),),
            evidence=(
                _ref("project_contract", contract, _L('直伤总公式'), _L('最终出口统一向下取整')),
                _ref(
                    "implementation",
                    "src/services/battle_hit_replay_support.py",
                    "settle_replay_damage",
                    _L('固定轴确定性结算出口'),
                ),
                _ref(
                    "public_behavior_test",
                    "tests/test_battle_hit_replay_service.py",
                    "test_replay_settlement_floors_only_after_all_factors",
                    _L('小数伤害只在最终出口向下取整'),
                ),
            ),
        ),
        FormulaEntry(
            key="max_hp_settlement",
            section=_L('结算'),
            title=_L('生命上限下降结算'),
            expression=(
                "HpRatio = clamp(PreSettlementHp/OldMax, 0, 1); "
                "EffectiveHpLoss = (OldMax-NewMax) × HpRatio; "
                "EffectiveDamage = HitDamage + ΣEffectiveHpLoss"
            ),
            boundary="observed_runtime",
            variables=(
                FormulaVariable("OldMax/NewMax", _L('同半场同目标的已确认最大生命前沿')),
                FormulaVariable("PreSettlementHp", _L('下降前附近逐击的最小可靠当前生命')),
            ),
            applicable_when=(_L('Core 正式下降或可归因的连续最大生命观测存在'),),
            limitations=(
                _L('描述估算单列展示，不计入正式有效伤害。'),
                _L('目标身份混合或轴连续性不足时不得跨目标归因。'),
            ),
            evidence=(
                _ref("project_contract", contract, _L('战报最大生命下降结算'), _L('生命上限结算口径')),
                _ref(
                    "implementation",
                    "src/services/battle_target_vital_analysis_service.py",
                    "BattleTargetVitalAnalysisService.derive",
                    _L('按(scope_half,target_id)维护观测前沿'),
                ),
                _ref(
                    "implementation",
                    "src/services/battle_counterfactual_analysis_service.py",
                    "BattleCounterfactualAnalysisService.analyze",
                    _L('把正式生命结算加入有效伤害'),
                ),
            ),
        ),
    )


def _support_entries(
    snapshot: StaticFormulaEvidenceSnapshot,
) -> tuple[CounterfactualSupportEntry, ...]:
    dataset = snapshot.dataset_id
    static_db = "data/game_static.sqlite3"
    return (
        CounterfactualSupportEntry(
            key="fixed_axis_replay",
            category=_L('核心不变量'),
            mechanism=_L('固定轴逐击反事实'),
            scope=_L('保留原动作、逐击、时间、半场与目标，只替换冻结构筑输入'),
            status="complete",
            modeling_scheme=_L('逐击公式候选与原击成对重放；未知分量进入量化状态而非补零。'),
            evidence=(
                _ref("implementation", "src/services/battle_build_counterfactual_service.py", "BattleBuildCounterfactualService.compare", _L('固定轴构筑入口')),
                _ref("public_behavior_test", "tests/test_battle_build_counterfactual_service.py", "BattleBuildCounterfactualServiceTests", _L('覆盖固定轴结果与缺口传播')),
            ),
            consumer_entries=("BattleBuildCounterfactualService.compare", "BattleBuffCounterfactualService.calculate"),
            gap_codes=(),
            covered_dataset=dataset,
            covered_entities=(_L('冻结逐击'), _L('冻结目标画像'), _L('冻结暴击分支')),
            limitations=(_L('不生成缺失动作或缺失命中。'),),
        ),
        CounterfactualSupportEntry(
            key="character_passives",
            category=_L('角色机制'),
            mechanism=_L('角色突破被动'),
            scope=_L('已显式登记的常驻、逐击限定、叠层与生命上限被动'),
            status="partial",
            modeling_scheme=_L('按突破阶段启用；常驻属性、状态适配器和显式派生伤害分别投影。'),
            evidence=(
                _ref("implementation", "src/services/battle_character_passive_service.py", "BattleCharacterPassiveService", _L('显式被动目录与解锁判断')),
                _ref("implementation", "src/services/battle_creation_passive_counterfactual_service.py", "BattleCreationPassiveCounterfactualService", _L('派生伤害的 partial/unavailable 传播')),
                _ref("public_behavior_test", "tests/test_battle_character_passive_service.py", "BattleCharacterPassiveServiceTests", _L('角色/技能作用域与叠层边界')),
            ),
            consumer_entries=("BattleBuffCounterfactualPlanService.prepare", "BattleCreationPassiveCounterfactualService.calculate"),
            gap_codes=("passive_event_evidence_missing", "creation_downstream_unresolved"),
            covered_dataset=dataset,
            covered_entities=("白藏", "阿德勒", "法帝娅", "零", "达芙蒂尔", "翳", "薄荷", "哈尼娅", "海月", "真红", "浔"),
            limitations=(_L('目标状态、资源、空间或召唤生命周期缺少正式事件时仍未知。'),),
        ),
        CounterfactualSupportEntry(
            key="awakening_six_effects",
            category=_L('角色机制'),
            mechanism=_L('六个觉醒效果与三/六觉共鸣'),
            scope=_L('结构化选中效果、技能等级白名单及已审计角色专属状态'),
            status="partial",
            modeling_scheme=_L('冻结具体 effect_id；通用结构化修改与角色专属时序分开消费。'),
            evidence=(
                _ref("official_static", static_db, "character_awaken_effect", f"normalized effects={snapshot.awakening_effect_rows}"),
                _ref("official_static", static_db, "character_awaken_skill_level_bonus", f"structured bonuses={snapshot.awakening_skill_level_bonus_rows}"),
                _ref("implementation", "src/services/battle_daffodill_awakening_service.py", "BattleDaffodillAwakeningService", _L('达芙蒂尔洞察/倾陷专属重放')),
                _ref("public_behavior_test", "tests/test_battle_daffodill_awakening_service.py", "BattleDaffodillAwakeningServiceTests", _L('效果选择、层数与结算限制')),
            ),
            consumer_entries=("BattleConfirmedAwakeningBuffService.get", "BattleDaffodillAwakeningService.infer"),
            gap_codes=("awakening_special_adapter_missing", "awakening_runtime_state_unresolved"),
            covered_dataset=dataset,
            covered_entities=(_L('结构化技能等级修改'), _L('残虹 Q 资格'), _L('达芙蒂尔洞察'), _L('薄荷觉醒 Buff'), _L('海月六觉层数')),
            limitations=(_L('存在静态觉醒记录不等于其运行时触发和消费已建模。'),),
        ),
        CounterfactualSupportEntry(
            key="fork_and_weapon_skills",
            category=_L('装备机制'),
            mechanism=_L('弧盘/空幕/武器技能'),
            scope=_L('正式参数、静态修改、已审计触发/周期/状态/残余规则'),
            status="partial",
            modeling_scheme=_L('基础面板与逐击动态状态分离；按动作、标签、有效时钟和目标条件生成区间。'),
            evidence=(
                _ref("official_static", static_db, "fork_item", f"normalized forks={snapshot.fork_rows}"),
                _ref("official_static", static_db, "fork_modify_value", f"normalized modifiers={snapshot.fork_modifier_rows}"),
                _ref("implementation", "src/services/battle_fork_damage_completion_service.py", "BattleForkDamageCompletionService", _L('显式弧盘完成规则目录')),
                _ref("public_behavior_test", "tests/test_battle_fork_damage_completion_service.py", "test_remaining_catalog_entries_have_explicit_completion_rules", _L('登记项具有显式完成策略')),
            ),
            consumer_entries=("BattleForkDamageStateService.infer_specialized", "BattleBuffCounterfactualPlanService.prepare"),
            gap_codes=("fork_runtime_condition_unresolved", "fork_random_outcome_unobserved", "weapon_state_axis_missing"),
            covered_dataset=dataset,
            covered_entities=(_L('触发型'), _L('周期型'), _L('状态型'), _L('暴击触发型'), _L('静态属性型')),
            limitations=(_L('随机、AND 条件、玩家状态或目标控制状态可能只能 partial/unavailable。'),),
        ),
        CounterfactualSupportEntry(
            key="buff_ge_attributes",
            category="Buff/GE",
            mechanism=_L('结构化 Buff/GameplayEffect 属性'),
            scope=_L('已解析 property、操作、数值、Source/Target 标签与区间'),
            status="partial",
            modeling_scheme=_L('静态定义只提供候选；运行时适配器证明触发与作用域后才投影到逐击。'),
            evidence=(
                _ref("official_static", static_db, "buff_definition", f"buff={snapshot.buff_definition_rows}; GE={snapshot.gameplay_effect_definition_rows}"),
                _ref("official_static", static_db, "buff_modifier", f"normalized modifiers={snapshot.buff_modifier_rows}"),
                _ref("implementation", "src/services/battle_buff_attribute_projection_service.py", "BattleBuffAttributeProjectionService", _L('逐击属性消费者')),
            ),
            consumer_entries=("BattleBuffCounterfactualBatchExecutor.calculate_ratios", "BattleHitCounterfactualRatioService.compare"),
            gap_codes=("buff_trigger_unresolved", "buff_target_condition_unresolved", "buff_property_consumer_missing"),
            covered_dataset=dataset,
            covered_entities=(_L('面板属性'), _L('增伤'), _L('易伤'), "防御无视", _L('抗性穿透'), _L('正式最终伤害属性')),
            limitations=(_L('函数或 GE 存在不证明触发、目标、层数和持续时间完整。'),),
        ),
        CounterfactualSupportEntry(
            key="formal_dot_classification",
            category="DOT",
            mechanism=_L('正式 DOT 分类'),
            scope=_L('导入 Gameplay Tag 为 State.Damage.Dot 的伤害'),
            status="complete",
            modeling_scheme=_L('正式标签优先拥有分类；名称和手工通道不覆盖标签。'),
            evidence=(
                _ref("official_static", static_db, "combat_blueprint_tag", f"DOT rows={snapshot.formal_dot_tag_rows}; assets={snapshot.formal_dot_tag_assets}"),
                _ref("implementation", "src/services/battle_axis_hit_projection_service.py", "_classification", _L('正式标签分类入口')),
                _ref("public_behavior_test", "tests/test_battle_counterfactual_analysis_service.py", "test_formal_damage_tags_own_dot_and_attachment_classification", _L('正式标签拥有 DOT/附着物分类')),
            ),
            consumer_entries=("project_battle_axis_hits", "BattleSkillDamageEvidenceService.load"),
            gap_codes=(),
            covered_dataset=dataset,
            covered_entities=("State.Damage.Dot",),
            limitations=(_L('complete 只表示分类，不表示每种 DOT 的层数/施加/结算状态都已重放。'),),
        ),
        CounterfactualSupportEntry(
            key="dot_state_replay",
            category="DOT",
            mechanism=_L('DOT 层数、持续时间与专属 FinalDamageUp'),
            scope=_L('噩梦、蚀心、鸩火、浊燃及早雾 DOT 种类乘区'),
            status="partial",
            modeling_scheme=_L('按(scope_half,target_id)使用结算前状态；触发击结算后才更新。'),
            evidence=(
                _ref("implementation", "src/services/battle_dot_stack_state_service.py", "reconstruct_dot_stack_states", _L('四类状态逐击重建')),
                _ref("public_behavior_test", "tests/test_battle_dot_stack_state_service.py", "test_sagiri_dot_final_multiplier_counts_kinds_not_layers", _L('按种类而非层数计数')),
                _ref("official_static", static_db, "buff_modifier:DOT-scoped FinalDamageUp", f"formal rows={snapshot.dot_scoped_final_damage_up_modifier_rows}"),
            ),
            consumer_entries=("BattleHitReplayService._replay_direct", "BattleHitCounterfactualRatioService.compare"),
            gap_codes=("dot_application_event_missing", "dot_state_kind_unmodeled", "dot_axis_incomplete"),
            covered_dataset=dataset,
            covered_entities=("噩梦", "蚀心", "鸩火", "浊燃", "State.Damage.Dot"),
            limitations=(_L('未审计 DOT 类型和缺失正式施加事件保持 unknown。'),),
        ),
        CounterfactualSupportEntry(
            key="topple_base_formula",
            category="倾陷",
            mechanism=_L('基础倾陷五乘区'),
            scope=_L('完整同半场阵容与冻结目标倾陷画像下的角色贡献'),
            status="complete",
            modeling_scheme=_L('逐角色重放等级、倾陷强度、目标上限、防御和抗性并汇总。'),
            evidence=(
                _ref("implementation", "src/services/damage_calculation_service.py", "DamageCalculationService.calculate_topple", _L('五乘区公式')),
                _ref("implementation", "src/services/battle_topple_hit_replay_service.py", "BattleToppleHitReplayService.replay", _L('战报逐角色消费者')),
                _ref("public_behavior_test", "tests/test_battle_topple_hit_replay_service.py", "test_split_topple_uses_only_the_complete_same_half_roster", _L('阵容完整性边界')),
            ),
            consumer_entries=("BattleToppleHitReplayService.replay", "battle_topple_marginal.topple_ratio"),
            gap_codes=(),
            covered_dataset=dataset,
            covered_entities=(_L('等级曲线'), "倾陷强度", "UnbalMax", "防御", _L('抗性')),
            limitations=(_L('complete 仅针对基础五乘区；特殊角色结算另列 partial。'),),
        ),
        CounterfactualSupportEntry(
            key="topple_special_states",
            category="倾陷",
            mechanism=_L('倾陷专属觉醒、窗口与额外结算'),
            scope=_L('达芙蒂尔洞察/觉醒、轨外倾陷窗口及已审计额外伤害'),
            status="partial",
            modeling_scheme=_L('在基础倾陷重放上叠加显式窗口、候选结算与可靠持续时间要求。'),
            evidence=(
                _ref("implementation", "src/services/battle_daffodill_awakening_service.py", "BattleDaffodillAwakeningService", _L('洞察层与觉醒专属规则')),
                _ref("public_behavior_test", "tests/test_battle_daffodill_awakening_service.py", "test_resonance_six_requires_reliable_topple_duration", _L('缺少可靠持续时间不判完成')),
            ),
            consumer_entries=("BattleDaffodillMarginalService.derived_rows", "BattleBuildCounterfactualService.compare"),
            gap_codes=("topple_duration_unreliable", "topple_special_settlement_unobserved"),
            covered_dataset=dataset,
            covered_entities=("达芙蒂尔", _L('轨外倾陷增益')),
            limitations=(_L('存在倾陷 GE 不等于角色专属消费链已完成。'),),
        ),
        CounterfactualSupportEntry(
            key="attachments",
            category=_L('召唤物/附着物'),
            mechanism=_L('正式附着物伤害'),
            scope=_L('State.Damage.Attachment 分类和已审计附着物倍率/被动'),
            status="partial",
            modeling_scheme=_L('正式标签分类；已有逐击只重放明确来源与倍率，不补造缺失攻击。'),
            evidence=(
                _ref("official_static", static_db, "combat_blueprint_tag:State.Damage.Attachment", f"formal assets={snapshot.formal_attachment_tag_assets}"),
                _ref("public_behavior_test", "tests/test_battle_skill_damage_evidence_service.py", "test_kuhara_effect_two_doubles_only_attachment_damage", _L('附着物专属觉醒作用域')),
                _ref("implementation", "src/services/battle_fork_trigger_refinement_service.py", "BattleForkTriggerRefinementService", _L('附着物限定动态规则')),
            ),
            consumer_entries=("project_battle_axis_hits", "BattleSkillDamageEvidenceService.load"),
            gap_codes=("attachment_owner_unresolved", "attachment_lifecycle_unobserved"),
            covered_dataset=dataset,
            covered_entities=("State.Damage.Attachment", _L('库哈拉种子'), _L('已登记附着物弧盘规则')),
            limitations=(_L('召唤物出现、消失、频率和漏失逐击不能由静态定义补造。'),),
        ),
        CounterfactualSupportEntry(
            key="summon_lifecycle",
            category=_L('召唤物/附着物'),
            mechanism=_L('召唤物生命周期与派生命中生成'),
            scope=_L('没有完整正式事件轴的召唤创建、存续、空间和资源循环'),
            status="unavailable",
            modeling_scheme=_L('只保留已观测逐击；缺失生命周期不生成候选命中。'),
            evidence=(
                _ref("implementation", "src/services/battle_creation_passive_evaluation_service.py", "BattleCreationPassiveEvaluationService", _L('显式返回 partial/unavailable')),
                _ref("public_behavior_test", "tests/test_battle_creation_passive_counterfactual_service.py", "test_lifecycle_spatial_and_resource_passives_preserve_unknown_state", _L('生命周期缺口保持 unknown')),
            ),
            consumer_entries=("BattleCreationPassiveCounterfactualService.calculate",),
            gap_codes=("summon_lifecycle_axis_unavailable", "summon_spatial_state_unavailable", "summon_resource_state_unavailable"),
            covered_dataset=dataset,
            covered_entities=(_L('已观测创建伤害归类'),),
            limitations=(_L('unavailable 不等于零伤害或机制未触发。'),),
        ),
        CounterfactualSupportEntry(
            key="healing_damage_coupling",
            category=_L('治疗/护盾'),
            mechanism=_L('治疗事件驱动的伤害 Buff'),
            scope=_L('已审计治疗事件、周期和治疗后属性区间'),
            status="partial",
            modeling_scheme=_L('先生成治疗事件，再由伤害 Buff 消费；不从技能动作兜底猜治疗。'),
            evidence=(
                _ref("implementation", "src/services/battle_treatment_event_service.py", "BattleTreatmentEventService", _L('独立治疗事件轴')),
                _ref("implementation", "src/services/battle_treatment_buff_service.py", "BattleTreatmentBuffService", _L('治疗后伤害 Buff 消费者')),
                _ref("public_behavior_test", "tests/test_battle_character_passive_service.py", "test_eiroi_healing_passive_is_not_materialized_from_actions", _L('动作不冒充治疗')),
            ),
            consumer_entries=("BattleTreatmentReplayService.infer", "BattleBuffCounterfactualPlanService.prepare"),
            gap_codes=("treatment_event_evidence_missing", "treatment_formula_source_unresolved"),
            covered_dataset=dataset,
            covered_entities=("伊洛伊", "错误的门", _L('已审计伤害转治疗事件')),
            limitations=(_L('未审计角色、缺少动画/技能证据或未知治疗公式仍不可量化。'),),
        ),
        CounterfactualSupportEntry(
            key="healing_without_damage_consumer",
            category=_L('治疗/护盾'),
            mechanism=_L('不影响伤害公式的纯治疗量'),
            scope=_L('只改变生命恢复且没有伤害 Buff/结算消费者的事件'),
            status="not_applicable",
            modeling_scheme=_L('可作为事件证据展示，但不进入伤害反事实增量。'),
            evidence=(
                _ref("implementation", "src/services/battle_treatment_replay_service.py", "BattleTreatmentReplayProjection", _L('治疗事件和伤害 Buff 投影分离')),
            ),
            consumer_entries=("StaticCatalogFormulaService",),
            gap_codes=(),
            covered_dataset=dataset,
            covered_entities=(_L('纯治疗输出')),
            limitations=(_L('not_applicable 只针对伤害反事实；不是治疗模拟已完整。'),),
        ),
        CounterfactualSupportEntry(
            key="shield_state",
            category=_L('治疗/护盾'),
            mechanism=_L('玩家护盾状态与护盾量反事实'),
            scope=_L('需要可靠历史护盾获得、消耗和逐击前状态轴的机制'),
            status="unavailable",
            modeling_scheme=_L('当前不从 UI 文案、动作或伤害误差反推护盾状态。'),
            evidence=(
                _ref("public_behavior_test", "tests/test_battle_fork_damage_completion_service.py", "test_missing_player_state_uses_high_hp_and_no_shield_defaults", _L('明确记录缺失玩家状态时的有限默认')),
                _ref("repository_audit", "src/services/battle_fork_damage_state_service.py", "BattleForkDamageStateService", _L('状态规则不构成通用历史护盾轴')),
            ),
            consumer_entries=("BattleForkDamageStateService.infer_specialized",),
            gap_codes=("player_shield_axis_unavailable",),
            covered_dataset=dataset,
            covered_entities=(),
            limitations=(_L('默认无盾仅属于明确规则分支，不能证明实际无盾。'),),
        ),
        CounterfactualSupportEntry(
            key="max_hp_settlement",
            category=_L('生命结算'),
            mechanism=_L('目标最大生命下降与有效生命损失'),
            scope=_L('Core v4 正式下降、单目标连续观测及已审计来源归因'),
            status="partial",
            modeling_scheme=_L('按(scope_half,target_id)维护最大生命前沿；正式事件计伤，描述估算单列。'),
            evidence=(
                _ref("implementation", "src/services/battle_target_vital_analysis_service.py", "BattleTargetVitalAnalysisService.derive", _L('正式/观测生命前沿')),
                _ref("public_behavior_test", "tests/test_battle_target_vital_analysis_service.py", "test_lacrimosa_description_estimate_is_excluded_from_formal_damage", _L('估算不混入正式伤害')),
                _ref("public_behavior_test", "tests/test_battle_counterfactual_settlement_analysis.py", "test_max_hp_settlement_is_not_reported_as_hp_overlap_correction", _L('结算渠道独立')),
            ),
            consumer_entries=("BattleCounterfactualAnalysisService.analyze", "BattleBuildCounterfactualService.compare"),
            gap_codes=("max_hp_axis_continuity_unavailable", "max_hp_source_attribution_unresolved"),
            covered_dataset=dataset,
            covered_entities=("Core v4 max_hp_reduction", _L('法帝娅已审计被动'), _L('拉克里莫萨五觉观测归因')),
            limitations=(_L('多目标身份冲突、缺轴或仅说明文本时不生成正式伤害。'),),
        ),
        CounterfactualSupportEntry(
            key="native_counterfactual_core",
            category=_L('执行器'),
            mechanism=_L('独立 C++ 反事实核心'),
            scope=_L('独立 C++20 差分切片及尚未接入的生产执行入口'),
            status="partial",
            modeling_scheme=_L('固定轴无状态直伤切片已独立验证；矩阵不选择、启用或回退执行器。'),
            evidence=(
                _ref("implementation", "native/counterfactual-core/src/engine.cpp", "counterfactual::calculate", _L('受限纯计算 sidecar')),
                _ref("public_behavior_test", "tools/counterfactual/run_cpp_differential.py", "main", _L('Python oracle 逐击差分')),
                _ref("repository_audit", "src/services/battle_marginal_counterfactual_projection_service.py", "BattleMarginalCounterfactualProjectionService.apply", _L('当前消费者仍走 Python 服务')),
                _ref("repository_audit", "src/services/battle_buff_counterfactual_batch_executor.py", "BattleBuffCounterfactualBatchExecutor", _L('当前批量公式执行为 Python')),
            ),
            consumer_entries=(),
            gap_codes=("native_production_consumer_unavailable", "native_stateful_mechanics_unavailable"),
            covered_dataset=dataset,
            covered_entities=(_L('加法面板/增伤/暴击'), _L('目标抗性'), "DefIgnore", _L('8 Buff / 56 逐击公开差分')),
            limitations=(_L('DOT、倾陷、反应、状态机和进程生命周期未迁移；不得把 unavailable 转换成 ratio=1。'),),
        ),
        CounterfactualSupportEntry(
            key="unknown_preservation",
            category=_L('核心不变量'),
            mechanism=_L('未知与不适用状态传播'),
            scope=_L('complete/partial/unavailable/not_applicable 量化状态'),
            status="complete",
            modeling_scheme=_L('按已量化伤害桶和缺口传播；unavailable 数值保持 nullable。'),
            evidence=(
                _ref("implementation", "src/domain/battle_counterfactual_quantification.py", "BattleCounterfactualRatio", _L('四态量化 contract')),
                _ref("public_behavior_test", "tests/test_battle_partial_quantification_buff_ui.py", "test_unavailable_does_not_render_zero_gain", _L('不可用不显示零收益')),
            ),
            consumer_entries=("BattleBuffCounterfactualService.calculate", "BattleMarginalCalculationService.calculate"),
            gap_codes=(),
            covered_dataset=dataset,
            covered_entities=("complete", "partial", "unavailable", "not_applicable"),
            limitations=(_L('complete 只针对状态传播 contract，不提升具体机制证据等级。'),),
        ),
    )


class StaticCatalogFormulaService:
    """Load a release-static/code audit projection without touching account data."""

    PROJECTION_VERSION = "static-catalog-formula-v3"

    def __init__(self, database_path: str | Path | None = None) -> None:
        self._database_path = database_path

    def load(self) -> StaticCatalogFormulaDomain:
        with StaticCatalogFormulaQueries(self._database_path) as queries:
            snapshot = queries.evidence_snapshot()
        return self.from_snapshot(snapshot)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: StaticFormulaEvidenceSnapshot,
    ) -> StaticCatalogFormulaDomain:
        return StaticCatalogFormulaDomain(
            projection_version=cls.PROJECTION_VERSION,
            readonly=True,
            evidence_snapshot=snapshot,
            formulas=_formula_entries(snapshot),
            counterfactual_support=_support_entries(snapshot),
        )
