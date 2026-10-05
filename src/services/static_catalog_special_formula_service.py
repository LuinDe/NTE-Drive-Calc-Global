# 构建战斗机制图鉴的命名 DOT、全部环合与特殊结算公式。
"""Player-readable special formula records backed by read-only static curves."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from dataclasses import dataclass
from pathlib import Path

from src.services.static_catalog_mechanics_models import PlayerField, PlayerSection
from src.storage.sqlite.static_catalog_formula_queries import (
    StaticCatalogFormulaQueries,
)
from src.storage.sqlite.static_game_data_dao import StaticGameDataError


@dataclass(frozen=True, slots=True)
class SpecialFormulaRecord:
    key: str
    family_key: str
    chapter: str
    title: str
    subtitle: str
    sections: tuple[PlayerSection, ...]
    aliases: tuple[str, ...] = ()
    status: str = "complete"
    notice: str = ""


def _field(label: str, value: str, tone: str = "neutral") -> PlayerField:
    return PlayerField(label, value, tone)


def _section(
    title: str,
    *fields: tuple[str, str] | tuple[str, str, str],
) -> PlayerSection:
    return PlayerSection(title, tuple(_field(*field) for field in fields))


def _formula_sections(
    formula: str,
    steps: tuple[str, ...],
    variables: tuple[tuple[str, str], ...],
    boundaries: tuple[str, ...],
) -> tuple[PlayerSection, ...]:
    return (
        _section(
            _L('完整公式'),
            ("公式", formula, "formula"),
            (_L('计算顺序'), "\n".join(
                f"{index}. {step}" for index, step in enumerate(steps, start=1)
            ), "accent"),
        ),
        _section(
            _L('变量来源'),
            *((label, value, "accent") for label, value in variables),
        ),
        _section(
            _L('判定与限制'),
            *((_L('边界'), value, "warning") for value in boundaries),
        ),
    )


def _number(value: float) -> str:
    if value.is_integer():
        return f"{value:,.0f}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


class StaticCatalogSpecialFormulaService:
    """Load named formulas without reading account data or runtime battle state."""

    _CURVE_IDS = {
        "creation": "GE_ActorReaction_1_Damage",
        "creation_special": "GE_ActorReaction_1_1019_Damage",
        "scorch": "Buff_Reaction_5_new",
        "scorch_zankou": "Buff_Reaction_5_new_1036",
        "nova": "Buff_Reaction_4_new",
    }

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = database_path

    def load(self) -> tuple[SpecialFormulaRecord, ...]:
        with StaticCatalogFormulaQueries(self._database_path) as queries:
            curves = {
                curve.source_effect_id: curve.values
                for curve in queries.reaction_damage_curves()
            }
            topple_levels = queries.topple_level_curve()
        missing = set(self._CURVE_IDS.values()) - set(curves)
        if missing:
            raise StaticGameDataError(
                _L('静态库缺少战斗机制图鉴所需环合曲线：')
                + "、".join(sorted(missing))
            )
        return (
            self._reaction_tiers(curves),
            self._creation(),
            self._weave(),
            self._scorch(),
            self._nova(),
            self._infusion(),
            self._delay(),
            self._charge(),
            self._dissonance(),
            self._nightmare(),
            self._erosion(),
            self._pigeon_fire(),
            self._topple(topple_levels),
            self._daffodill_topple(),
            self._nightmare_max_hp(),
            self._fadia_shared_damage(),
        )

    def _reaction_tiers(
        self,
        curves: dict[str, tuple[float, ...]],
    ) -> SpecialFormulaRecord:
        columns = {
            label: curves[effect_id]
            for label, effect_id in (
                ("创生", self._CURVE_IDS["creation"]),
                (_L('创生特殊项'), self._CURVE_IDS["creation_special"]),
                ("浊燃", self._CURVE_IDS["scorch"]),
                (_L('残虹浊燃'), self._CURVE_IDS["scorch_zankou"]),
                ("黯星", self._CURVE_IDS["nova"]),
            )
        }
        tier_sections = []
        for group_start in range(0, 16, 4):
            fields = []
            for tier in range(group_start, group_start + 4):
                level_start = tier * 5 + 1
                level_end = level_start + 4
                values = " ｜ ".join(
                    f"{label} {_number(points[tier])}"
                    for label, points in columns.items()
                )
                fields.append((
                    _LF('源档 {0} · 角色等级 {1}–{2}').format((tier), (level_start), (level_end)),
                    values,
                    "tier",
                ))
            tier_sections.append(_section(
                _LF('官方基础值 · 源档 {0}–{1}').format((group_start), (group_start + 3)),
                *fields,
            ))
        return SpecialFormulaRecord(
            key="reaction_tiers",
            family_key="states",
            chapter=_L('环合基础'),
            title=_L('环合归属与 16 档基础值'),
            subtitle=_L('创生/黯星/浊燃比较双方；覆纹/浸染逐击读取实际伤害来源。'),
            aliases=(_L('环合基础'), "0-5", _L('档位'), _L('双方属性'), _L('取谁')),
            sections=(
                _section(
                    _L('归属规则'),
                    (
                        _L('先比较谁'),
                        _L('创生、黯星、浊燃比较两名环合参与者各自的“环合强度 × 角色等级基础值”并取较高者。覆纹、浸染不比较双方，按实际造成对应伤害的角色逐击取值。'),
                        "formula",
                    ),
                    (
                        _L('覆纹与浸染取谁'),
                        _L('覆纹取每条被记录原伤害的实际来源角色；浸染取 12 秒区间内每条受益伤害自己的来源角色。触发环合的 QTE 角色只负责触发，不固定提供后续逐击的环合强度。'),
                        "formula",
                    ),
                    (
                        _L('角色侧变量'),
                        _L('创生/黯星/浊燃由比较胜出角色提供；覆纹/浸染由实际伤害来源角色提供。每张环合卡片会逐项列明。'),
                        "accent",
                    ),
                    (
                        _L('受击目标提供'),
                        _L('敌方防御、对应伤害属性抗性、动态减抗和受到伤害提升；不从中文怪物名猜取。'),
                        "accent",
                    ),
                    (
                        _L('档位公式'),
                        _L('源档 = floor((归属角色等级 - 1) ÷ 5)；1–5 级取源档 0，76–80 级取源档 15。'),
                        "formula",
                    ),
                ),
                *tier_sections,
                _section(
                    _L('静态来源说明'),
                    (
                        _L('创生特殊项'),
                        _L('这是静态库中独立存在的第二条创生曲线。资源名后缀不能作为角色归属证据，因此图鉴只按“创生特殊项”展示。'),
                        "warning",
                    ),
                    (
                        _L('残虹浊燃'),
                        _L('静态库中另有残虹专属浊燃曲线；当前 16 档与普通浊燃完全相同，但仍按独立正式来源展示。'),
                        "warning",
                    ),
                    (
                        _L('数值边界'),
                        _L('表内数字来自当前发行静态库的正式 16 档曲线；公式如何消费这些数字仍以各环合卡片为准。'),
                        "accent",
                    ),
                ),
            ),
        )

    @staticmethod
    def _creation() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_creation",
            family_key="states",
            chapter="环合",
            title=_L('环合·创生'),
            subtitle=_L('等级基础值 × 环合强度区 × 防御 × 抗性 × 易伤；不暴击。'),
            aliases=(_L('光灵'), "创生花", _L('创生株')),
            sections=_formula_sections(
                _L('单朵创生伤害 = 向下取整[等级基础值 × (1 + 环合强度/600) × 防御区 × 抗性区 × 易伤区]'),
                (
                    _L('从两名环合参与者中选出归属角色。'),
                    _L('按归属角色等级读取创生 16 档基础值。'),
                    _L('使用归属角色的环合强度和目标侧防御/属性抗性。'),
                    _L('乘目标易伤后，在最终出口向下取整。'),
                ),
                (
                    (_L('归属角色'), _L('取两名环合参与者中“环合强度 × 等级基础值”较高者。')),
                    (_L('等级基础值'), _L('取归属角色等级对应的创生源档；80 级为 9,000。')),
                    ("环合强度", _L('取归属角色命中时的环合强度，不取另一名参与者，也不相加。')),
                    (_L('防御区'), _L('角色等级与防御穿透取归属角色；防御属性和防御降低取受击目标。')),
                    (_L('抗性区'), _L('伤害属性由正式逐击/伤害项确认；穿透取归属角色，抗性与减抗取受击目标。')),
                    (_L('易伤区'), _L('取受击目标在该时点的受到伤害提升。')),
                ),
                (
                    _L('创生不读取攻击/生命/防御面板，不读取通用或属性增伤，不暴击。'),
                    _L('一个创生株生成 5 个创生花、最多 3 株属于状态与命中数量，不乘进单朵公式。'),
                ),
            ),
        )

    @staticmethod
    def _weave() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="weave_followup",
            family_key="states",
            chapter="环合",
            title=_L('环合·覆纹'),
            subtitle=_L('记录符合条件的灵/咒实际伤害，12 秒结束时按原伤属性追加。'),
            aliases=(_L('灵咒'), "弱点感应"),
            sections=_formula_sections(
                _L('覆纹追加 = 原伤害实际值 × [(复制比例 + 灵可复制比例加成) × (1 + 追击增伤%) × 强度区 + 限制(强度区 - 1, 0, 100)] × 最终乘数'),
                (
                    _L('记录每条符合条件的灵/咒实际伤害及其属性；正式 DOT 等被记录来源同样适用。'),
                    _L('基础复制比例加上灵可复制比例加成，再乘以一加追击增伤。'),
                    _L('用原伤害实际来源角色的环合强度计算强度区；复制部分乘强度区后，再加入强度区减一的限制项。'),
                    _L('将原伤害实际值乘以上述合计和最终乘数，继承该条原伤害的属性。'),
                    _L('12 秒结束时分别追加，再在最终出口取整。'),
                ),
                (
                    (_L('原伤害实际值'), _L('取被覆纹记录的那一条真实伤害；不重新用预计面板生成。')),
                    (_L('伤害属性'), _L('继承每条原伤害的攻击方属性：灵伤仍是灵，咒伤仍是咒。')),
                    ("环合强度", _L('取被记录原伤害的实际来源角色；不取触发覆纹的 QTE 角色，也不比较环合双方。')),
                    (_L('复制比例'), _L('基础为 20%。')),
                    (_L('灵可复制比例加成'), _L('队伍启用灵可“弱点感应”时为 10%，未启用时为 0%。')),
                    (_L('追击增伤%'), _L('本页按弱点感应启用时 10%、未启用时 0% 拆分；只乘复制部分，不乘后面的限制项。')),
                    (_L('复制部分合计'), _L('未启用弱点感应：(20% + 0%) × (1 + 0%) = 20%；启用后：(20% + 10%) × (1 + 10%) = 33%。')),
                    (_L('强度区'), _L('1 + 20% × 环合强度 / (环合强度 + 180)；环合强度最低按 0 计算。')),
                    (_L('限制'), _L('把强度区减一的结果限制在 0 到 100 之间。')),
                    (_L('原伤增伤'), _L('保留原伤害已经结算的增伤，不除掉原增伤区；若原伤本身已吃到追击增伤，其收益保留在实际值中。')),
                    (_L('最终乘数'), _L('当前核心模型取 1；不重复乘入原伤的最终增伤。')),
                ),
                (
                    _L('覆纹不读取环合 16 档基础伤害表；它以已发生并被正式记录的实际伤害为基数。'),
                    _L('这是当前 33% 结果的拆分解释，尚未独立确认游戏内部按这两个 10% 分步结算；其他追击增伤来源不据此直接代入。'),
                    _L('33% 是复制部分合计，最终追加伤害还受环合强度影响，并非固定为原伤的 33%，也不将整次覆纹再乘 1.10。'),
                    _L('状态被提前移除时默认不立刻结算，除非专属效果明确要求。'),
                ),
            ),
        )

    @staticmethod
    def _scorch() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_scorch",
            family_key="states",
            chapter="环合",
            title=_L('环合·浊燃'),
            subtitle=_L('16 档基础值 × 结算前层数 × 环合强度区 × 目标侧乘区 × DOT/暴击。'),
            aliases=(_L('咒暗'), "DOT", "持续伤害"),
            sections=_formula_sections(
                _L('浊燃单跳 = 向下取整[等级基础值 × 结算前层数 × (1 + 环合强度/600) × 防御区 × 抗性区 × 易伤区 × DOT专属最终区 × 暴击分支]'),
                (
                    _L('分别计算两名环合参与者的“等级基础值 × 环合强度”，取较高者作为归属角色。'),
                    _L('读取同半场、同目标在本跳前的浊燃层数。'),
                    _L('计算环合强度、目标防御/抗性、DOT 专属最终区。'),
                    _L('按固定 50% 暴击策略保留未暴击/暴击分支并最终取整。'),
                ),
                (
                    (_L('归属角色'), _L('比较两名环合参与者各自的“等级基础值 × 环合强度”并取较高者；不固定取 QTE 角色，也不相加。')),
                    (_L('等级基础值'), _L('每名参与者先按自身等级读取适用的浊燃源档；普通与残虹专属曲线当前 80 级均为 2,700。')),
                    (_L('结算前层数'), _L('普通浊燃固定 1 层；残虹替换状态由同半场、同目标的正式 DOT 施加轴推进，最多 3 层。')),
                    ("环合强度", _L('每名参与者使用自己的环合强度参与归属比较；胜出后，本次浊燃冻结胜出者的强度与角色侧变量。')),
                    (_L('防御区'), _L('角色等级/穿透取归属角色，敌方防御/减防取受击目标。')),
                    (_L('抗性区'), _L('普通浊燃取逐击确认的实际属性；残虹专属固定取咒属性。穿透取归属角色，抗性取目标。')),
                    (_L('DOT专属最终区'), _L('取命中前目标上仍有效的正式 DOT 种类和明确限定 DOT 的最终增伤。')),
                    ("暴击", _L('固定暴击率 50%；不读取角色暴击率，但读取归属角色暴击伤害。')),
                ),
                (
                    _L('浊燃不读取角色攻击面板，也不读取通用/属性伤害提升。'),
                    _L('浊燃自身跳伤不递归为残虹浊燃加层；缺少正式施加事件时不能从最终伤害反推任意层数。'),
                ),
            ),
        )

    @staticmethod
    def _nova() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_nova",
            family_key="states",
            chapter="环合",
            title=_L('环合·黯星'),
            subtitle=_L('5 秒后结算心灵伤害；不走防御区，仍走心灵抗性与易伤。'),
            aliases=(_L('暗魂'), "心灵伤害"),
            sections=_formula_sections(
                _L('单个黯星 = 向下取整[等级基础值 × (1 + 环合强度/600) × 心灵抗性区 × 易伤区]'),
                (
                    _L('每次暗+魂触发时分别计算两名参与者的“等级基础值 × 环合强度”。'),
                    _L('取结果较高者作为本次黯星实例归属，并冻结其等级基础值。'),
                    _L('计算该归属角色环合强度与心灵穿透。'),
                    _L('乘受击目标的心灵抗性和易伤后取整。'),
                ),
                (
                    (_L('实例归属'), _L('比较两名环合参与者各自的“等级基础值 × 环合强度”并取较高者；不同触发实例分别保留各自胜出者。')),
                    (_L('等级基础值'), _L('双方先按各自等级读取黯星源档；胜出实例冻结对应值，80 级为 45,000。')),
                    ("环合强度", _L('双方各取自己的环合强度参与比较；胜出实例只消费胜出者的强度，不相加。')),
                    (_L('防御区'), _L('心灵伤害按 100% 防御穿透处理，防御区固定为 1。')),
                    (_L('抗性区'), _L('心灵穿透取该实例归属角色；心灵抗性与减抗取受击目标。')),
                    (_L('易伤区'), _L('取受击目标在结算时点的受到伤害提升。')),
                ),
                (
                    _L('黯星不读取攻击面板、通用增伤或暴击。'),
                    _L('多个实例的最终统一结算需保留各实例自己的来源属性，不能把双方环合强度相加后只算一次。'),
                ),
            ),
        )

    @staticmethod
    def _infusion() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_infusion",
            family_key="states",
            chapter="环合",
            title=_L('环合·浸染'),
            subtitle=_L('QTE 触发后持续 12 秒；全队后续逐击分别读取各自伤害来源角色的环合强度。'),
            aliases=(_L('魂相'), _L('团队增伤'), _L('全队增伤')),
            sections=_formula_sections(
                _L('本击浸染最终乘区 = 1.20 × [1 + 20% × 本击来源环合强度 / (本击来源环合强度 + 180)]；受益逐击 = 原完整伤害 × 本击浸染最终乘区'),
                (
                    _L('由正式魂+相 QTE 结算确认浸染触发。'),
                    _L('从 QTE 结算后建立 12 秒团队增伤区间；触发 QTE 本击不吃。'),
                    _L('区间内每条后续逐击读取该击实际伤害来源角色的环合强度。'),
                    _L('在该击原完整公式末端乘对应的浸染最终乘区。'),
                ),
                (
                    (_L('QTE 触发者'), _L('只负责触发或刷新浸染状态；其环合强度不会冻结为全队 12 秒共用值。')),
                    (_L('本击伤害来源'), _L('取区间内当前这条受益伤害的实际来源角色；该角色提供本击浸染公式的环合强度。')),
                    (_L('基础增伤'), _L('取正式环合常量 20%，构成前置 1.20。')),
                    (_L('环合强度修正'), _L('使用本击伤害来源角色的环合强度：1 + 20%×环合强度/(环合强度+180)。')),
                    ("持续时间", _L('取正式环合常量 12 秒；从触发 QTE 结算后开始，后续触发刷新区间。')),
                    (_L('受益者'), _L('队伍所有角色在区间内的后续逐击；不同角色的伤害会因各自环合强度不同而得到不同乘区。')),
                ),
                (
                    _L('浸染是团队最终增伤 Buff，不生成独立“浸染伤害”，也不记录伤害后在 12 秒末统一结算。'),
                    _L('团队倾陷与非逐击最大生命结算当前不默认消费该最终乘区。'),
                    _L('若逐击不能确认实际伤害来源，状态可以显示，但该击环合强度收益必须保持未解析，不能回退到 QTE 触发者或相邻伤害。'),
                ),
            ),
        )

    @staticmethod
    def _delay() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_delay",
            family_key="states",
            chapter="环合",
            title=_L('环合·延滞'),
            subtitle=_L('相+光；5 秒减攻减速，本身没有伤害公式。'),
            aliases=(_L('相光'), _L('减攻'), _L('减速')),
            status="not_applicable",
            sections=_formula_sections(
                _L('延滞伤害 = 不适用；状态持续 5 秒'),
                (_L('识别相+光触发。'), _L('对目标建立 5 秒延滞状态。')),
                ((_L('状态对象'), _L('受击目标；后续只有明确要求延滞状态的机制消费。')),),
                (_L('延滞不生成伤害逐击，不能填入直伤或环合伤害。'),),
            ),
        )

    @staticmethod
    def _charge() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_charge",
            family_key="states",
            chapter="环合",
            title=_L('环合·盈蓄'),
            subtitle=_L('光+灵+相；创生花命中延滞目标时获得 10 点额外终结能量。'),
            aliases=(_L('光灵相'), _L('终结能量')),
            status="not_applicable",
            sections=_formula_sections(
                _L('额外终结能量 = 10（创生花命中处于延滞的目标时）'),
                (_L('确认目标延滞状态。'), _L('确认命中来自创生花。'), _L('给予 10 点终结能量。')),
                (
                    (_L('延滞状态'), _L('取本次受击目标在命中前的状态轴。')),
                    (_L('创生花命中'), _L('取正式创生伤害/命中证据，不从中文技能名猜测。')),
                ),
                (_L('盈蓄改变资源，不直接生成伤害。'),),
            ),
        )

    @staticmethod
    def _dissonance() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="reaction_dissonance",
            family_key="states",
            chapter="环合",
            title=_L('环合·失谐'),
            subtitle=_L('暗+魂+咒；目标同时有黯星与浊燃时扣除倾陷值，本身不造成伤害。'),
            aliases=(_L('暗魂咒'), _L('倾陷扣除')),
            status="partial",
            notice=_L('15% 是当前项目弱证据默认值，固定值、等级系数和联机修正仍待确认。'),
            sections=_formula_sections(
                _L('当前项目投影：失谐倾陷扣除 = 受击目标倾陷上限 × 15%'),
                (_L('检查同一目标同时存在黯星与浊燃。'), _L('读取该目标倾陷上限。'), _L('扣除 15%，不生成伤害逐击。')),
                (
                    (_L('黯星/浊燃状态'), _L('取同半场、同目标的状态轴，不跨目标拼接。')),
                    (_L('倾陷上限'), _L('只取受击目标冻结属性包中的倾陷上限，不取任一参与角色。')),
                ),
                (_L('15% 尚非完整官方运行公式；只参与倾陷条时序，不进入倾陷伤害乘区。'),),
            ),
        )

    @staticmethod
    def _named_dot(
        *,
        key: str,
        title: str,
        aliases: tuple[str, ...],
        source: str,
        state: str,
        boundary: str,
    ) -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key=key,
            family_key="states",
            chapter=_L('持续直伤'),
            title=title,
            subtitle=_L('正式技能倍率 × 本跳状态系数 × 攻击方逐击面板 × 目标侧乘区 × DOT/暴击。'),
            aliases=aliases,
            sections=_formula_sections(
                _L('本跳伤害 = 向下取整[技能基础倍率 × 本跳状态系数 × 攻击方对应面板 × 增伤区 × 防御区 × 抗性区 × 易伤区 × 独立最终区 × DOT专属最终区 × 暴击分支]'),
                (
                    _L('从正式伤害项与有效技能等级读取本跳基础倍率。'),
                    _L('从同半场、同目标状态轴读取命中前状态系数。'),
                    _L('读取伤害来源角色命中时面板与 Buff。'),
                    _L('读取受击目标防御、对应抗性、减益与 DOT 状态后取整。'),
                ),
                (
                    (_L('技能基础倍率'), source),
                    (_L('本跳状态系数'), state),
                    (_L('面板/增伤/暴伤'), _L('取本条持续直伤的来源角色在命中时的冻结养成、装备和有效 Buff。')),
                    (_L('防御/抗性/易伤'), _L('取本条逐击的受击目标；穿透取伤害来源角色，减防/减抗/易伤取目标。')),
                    (_L('DOT专属最终区'), _L('取命中前同一目标仍有效的正式 DOT 种类与明确限定 DOT 的最终增伤。')),
                    ("暴击", _L('固定暴击率 50%；不取角色暴击率，暴击分支仍取来源角色暴击伤害。')),
                ),
                (boundary,),
            ),
        )

    @classmethod
    def _nightmare(cls) -> SpecialFormulaRecord:
        return cls._named_dot(
            key="dot_nightmare",
            title=_L('持续直伤·噩梦'),
            aliases=("安魂曲", _L('噩梦层数')),
            source=_L('取安魂曲噩梦正式伤害项和当前有效普通攻击技能等级；普通/六觉分支各用自己的倍率档。'),
            state=_L('每个有效正式直伤命中后施加 1 层；本跳只读更早层，最多 10 层。每层独立持续 3 秒，四觉后 6 秒。'),
            boundary=_L('三觉提前结算是“逐层剩余跳数求和并清空”的独立公式；当前缺少稳定关联时不得冒充普通单跳。'),
        )

    @classmethod
    def _erosion(cls) -> SpecialFormulaRecord:
        return cls._named_dot(
            key="dot_erosion",
            title=_L('持续直伤·蚀心'),
            aliases=("残虹", _L('蚀心层数')),
            source=_L('取残虹蚀心正式伤害项和当前有效普通攻击技能等级。'),
            state=_L('正式活跃层数与本跳有效系数分开；只在“单份”或“本击前正式层数”中按实伤选择，最多 10 层。'),
            boundary=_L('不得开放 1–10 任意拟合；缺施加事件时系数 1 仅表示至少一份，并保持低置信。'),
        )

    @classmethod
    def _pigeon_fire(cls) -> SpecialFormulaRecord:
        return cls._named_dot(
            key="dot_pigeon_fire",
            title=_L('持续直伤·鸩火'),
            aliases=(_L('鸠火'), "残虹", _L('鸩火层数')),
            source=_L('取残虹鸩火正式伤害项和当前有效极轨终结技能等级。'),
            state=_L('“血宴入梦时”最终施加点一次加 5 层，最多 10 层、持续 30 秒；普通攻击和 DOT 跳伤不加层。'),
            boundary=_L('扩散复制层数、剩余时间和周期，但单目标轴不得凭此制造其他目标的伤害逐击。'),
        )

    @staticmethod
    def _topple(level_values: tuple[float, ...]) -> SpecialFormulaRecord:
        level_sections = tuple(
            _section(
                _LF('官方倾陷基础 · {0}–{1} 级').format((start), (start + 9)),
                (
                    _L('逐级数值'),
                    " ｜ ".join(
                        _LF('{0}级 {1}').format((level), (_number(level_values[level - 1])))
                        for level in range(start, start + 10)
                    ),
                    "tier",
                ),
            )
            for start in range(1, 81, 10)
        )
        return SpecialFormulaRecord(
            key="topple_damage",
            family_key="settlement",
            chapter="倾陷",
            title=_L('团队倾陷伤害'),
            subtitle=_L('同半场每名角色分别算五乘区，再把所有角色贡献相加。'),
            aliases=("倾陷", _L('白条'), _L('逐角色求和')),
            sections=_formula_sections(
                _L('团队倾陷 = Σ同半场角色 i [等级基础_i × (1 + 倾陷强度_i/300 + Σ倾陷提高_i) × 敌方倾陷上限区 × 防御区_i × 抗性区_i]'),
                (
                    _L('固定本击所在半场的完整出伤角色阵容。'),
                    _L('每名角色用自己的等级、倾陷强度、属性和穿透单独算一格。'),
                    _L('每格读取同一受击目标的倾陷上限、防御和对应属性抗性。'),
                    _L('把所有角色格相加，最终向下取整。'),
                ),
                (
                    (_L('角色集合'), _L('取本击同半场全部正式出伤角色；Core 挂名的触发角色不是唯一伤害所有者。')),
                    (_L('等级基础'), _L('每名角色取自己的等级对应官方 1–80 级倾陷曲线；80 级为 3,603。')),
                    ("倾陷强度", _L('每名角色取自己的“基础×(1+提升)+固定额外”，双方/全队不先合并。')),
                    (_L('倾陷伤害提高'), _L('只进入提供该效果的角色格；倾陷状态本身不会自动提供易伤。')),
                    (_L('倾陷上限区'), _L('取同一受击目标的 UnbalMax；普通为 max(1, UnbalMax/3)，争锋高阶 Boss 档固定 25。')),
                    (_L('防御区'), _L('每格用该角色等级和防御穿透，目标防御/减防来自同一受击目标。')),
                    (_L('抗性区'), _L('每格按该角色固有伤害属性取自己的穿透，并读取目标对应属性抗性/减抗。')),
                ),
                (
                    _L('倾陷不读取攻击/生命/防御缩放面板、通用增伤、易伤、暴击或独立最终增伤。'),
                    _L('半场阵容或目标画像不完整时必须标记不可完整重放，不能从另一半场补齐。'),
                ),
            ) + level_sections,
        )

    @staticmethod
    def _daffodill_topple() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="daffodill_extra_topple",
            family_key="settlement",
            chapter="倾陷",
            title=_L('达芙蒂尔·额外倾陷'),
            subtitle=_L('使用达芙蒂尔个人倾陷五乘区；候选五觉额外次数为 1 + 洞察层数。'),
            aliases=(_L('洞察'), _L('五觉'), _L('额外倾陷伤害')),
            sections=_formula_sections(
                _L('单次个人倾陷 = 达芙蒂尔等级基础 × 达芙蒂尔倾陷强度区 × 目标倾陷上限区 × 达芙蒂尔防御区 × 暗属性抗性区；候选五觉总次数 = 1 + 洞察层数'),
                (
                    _L('在已有正式倾陷时点读取洞察层数。'),
                    _L('用达芙蒂尔自己的个人倾陷五乘区算单次值。'),
                    _L('零觉已有一次；候选五觉再按每层洞察追加一次。'),
                ),
                (
                    (_L('人物属性'), _L('等级、倾陷强度、防御穿透、暗属性穿透都取达芙蒂尔，不取团队其他角色。')),
                    (_L('目标属性'), _L('倾陷上限、防御、暗抗与对应减益取本次受击目标。')),
                    (_L('洞察层数'), _L('取达芙蒂尔专用固定轴状态；三觉前一层，三觉后最多两层。')),
                ),
                (
                    _L('出现额外倾陷 GE 只证明公式锚点，不自动证明已启用五觉。'),
                    _L('候选新增行基线为零，不替换原团队倾陷伤害。'),
                ),
            ),
        )

    @staticmethod
    def _nightmare_max_hp() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="nightmare_max_hp_settlement",
            family_key="settlement",
            chapter=_L('生命结算'),
            title=_L('安魂曲五觉·噩梦生命上限削减'),
            subtitle=_L('来源噩梦本体伤害的 200%；有效生命损失再按结算前生命比例折算。'),
            aliases=(_L('最大生命'), _L('安魂曲五觉'), _L('噩梦200%')),
            sections=_formula_sections(
                _L('预计最大生命削减 = 来源噩梦伤害 × 200%；有效生命损失 = 最大生命下降 × clamp(结算前生命/旧最大生命, 0, 1)'),
                (
                    _L('只绑定正式噩梦逐击，不接受相邻生命样本或普通直伤。'),
                    _L('按该来源噩梦的候选/原始公式比联动削减值。'),
                    _L('按目标结算前生命比例折算为有效伤害。'),
                ),
                (
                    (_L('来源噩梦'), _L('取同一目标、归因明确的安魂曲正式噩梦逐击；伤害变化继承该逐击公式比。')),
                    (_L('最大生命前沿'), _L('旧/新最大生命和结算前生命都取同半场、同目标的连续生命轴。')),
                    (_L('归属角色'), _L('归属安魂曲；目标生命数据只决定有效损失，不改变来源角色。')),
                ),
                (_L('描述估算与 Core 正式最大生命下降必须分开；缺目标连续轴时保持部分/不可用。'),),
            ),
        )

    @staticmethod
    def _fadia_shared_damage() -> SpecialFormulaRecord:
        return SpecialFormulaRecord(
            key="fadia_shared_damage",
            family_key="settlement",
            chapter="共享伤害",
            title=_L('法帝娅·破灭体验共享伤害'),
            subtitle=_L('共享法帝娅实际承受伤害的 300%/600%，并受她生命上限的 8%/25% 累计上限约束。'),
            aliases=("法帝娅", _L('破灭体验'), "共享伤害"),
            status="partial",
            sections=_formula_sections(
                _L('本次可共享 = min(法帝娅实际承受伤害 × 共享比例, 累计上限 - 已累计)；累计上限 = 法帝娅生命上限 × 上限比例'),
                (
                    _L('先取得法帝娅本次真实承受伤害。'),
                    _L('按普通 300%/8% 或二觉 600%/25% 计算。'),
                    _L('受累计上限截断；效果移除时按正式规则补足差额。'),
                ),
                (
                    (_L('实际承受伤害'), _L('只取法帝娅本人经过护盾与队伍分摊后的可靠承伤，不取敌人原始出伤封包。')),
                    (_L('共享比例/上限比例'), _L('取法帝娅该机制的普通或二觉分支。')),
                    (_L('生命上限'), _L('取法帝娅当前生命上限，不取受击敌人或共享目标。')),
                    (_L('累计值'), _L('取本次机制实例已共享的历史累计。')),
                ),
                (_L('当前战报承伤证据可能早于护盾/分摊结算；证据不足时不得直接乘 3 或乘 6。'),),
            ),
        )


__all__ = ["SpecialFormulaRecord", "StaticCatalogSpecialFormulaService"]
