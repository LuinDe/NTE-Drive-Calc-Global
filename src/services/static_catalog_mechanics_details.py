# 构建公式与反事实模型详情，隔离于目录查询和效果关系编排。
"""Pure detail projections for formula and counterfactual mechanics."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from src.services.static_catalog_formula_presenters import (
    CounterfactualMatrixRow,
    FormulaDetailView,
)
from src.services.static_catalog_mechanics_models import (
    CatalogLink,
    EvidenceStage,
    FORMULA_CHAPTER_BY_KEY,
    FORMULA_FAMILY_BY_KEY,
    MODEL_FAMILY_BY_KEY,
    MechanicsDetail,
    PLACEHOLDER_NAME,
    PlayerField,
    PlayerSection,
    encode_record,
)
from src.services.static_catalog_terminology_service import (
    StaticCatalogTerminologyService,
)


_PLAYER_FORMULAS: dict[
    str,
    tuple[str, str, tuple[tuple[str, str], ...]],
] = {
    "panel_attribute": (
        _L('角色面板属性'),
        _L('面板值 = 基础值 ×（1 + 百分比加成）+ 固定加成'),
        ((_L('基础值'), _L('取当前角色的人物、弧盘和其他正式基础值；不取受击目标。')),
         (_L('百分比加成'), _L('取当前角色装备、养成与命中时有效 Buff 的同属性百分比项。')),
         (_L('固定加成'), _L('取当前角色装备、账号家具加成与命中时有效 Buff 的同属性固定项。'))),
    ),
    "skill_multiplier": (
        "技能倍率",
        _L('技能倍率 = 等级倍率 ×（1 + 倍率修正合计）'),
        ((_L('等级倍率'), _L('取攻击方本条正式伤害项；按该技能当前有效等级读取倍率档。')),
         (_L('倍率修正'), _L('取攻击方当前养成与 Buff 中，正式作用于该技能标签的倍率修正。'))),
    ),
    "direct_damage": (
        _L('直伤计算'),
        _L('最终直伤 = 向下取整[max(0, 技能倍率 × 对应面板 × 增伤 × 暴击 × 防御 × 抗性 × 易伤 × Π独立增伤)]'),
        (("技能倍率", _L('取攻击方本条正式伤害项与当前有效技能等级。')),
         (_L('对应面板'), _L('取攻击方命中时的攻击、生命或防御面板；具体哪一种由伤害项指定。')),
         (_L('增伤区'), _L('取攻击方命中时适用于本击的通用、属性、技能与状态增伤。')),
         ("暴击", _L('暴击率/固定策略与暴击伤害取攻击方或本机制正式规则。')),
         (_L('防御区'), _L('角色等级和防御穿透取攻击方；防御与防御降低取受击目标。')),
         (_L('抗性区'), _L('属性穿透取攻击方；对应属性抗性与减抗取受击目标。')),
         (_L('易伤区'), _L('取受击目标在本击时点承受的伤害提升。')),
         (_L('独立增伤'), _L('取所有明确作用于攻击方本击的独立最终乘数，逐项相乘。'))),
    ),
    "damage_increase": (
        _L('增伤'),
        _L('增伤倍率 = 1 + 各类增伤合计'),
        ((_L('增伤合计'), _L('取攻击方命中时适用于本击的通用、属性、技能和状态增伤；同区相加。')),),
    ),
    "vulnerability": (
        _L('易伤'),
        _L('易伤倍率 = 1 + 目标受伤提升合计'),
        ((_L('受伤提升'), _L('只取本次受击目标在命中时有效的受伤提升 Debuff；不取攻击方增伤。')),),
    ),
    "critical": (
        "暴击",
        _L('未暴击 = 向下取整(完整精度伤害)；暴击 = 向下取整[完整精度伤害 × (1 + 暴击伤害)]；期望 = (1-r)×未暴击 + r×暴击'),
        (("暴击率", _L('普通直伤取攻击方命中时暴击率；固定 50% 或不可暴击机制以正式策略覆盖。')),
         ("暴击伤害", _L('取攻击方命中时暴击伤害；受击目标不提供此变量。'))),
    ),
    "defense": (
        "防御",
        _L('目标有效防御 = [防御基础×(1+防御提升)+固定防御]÷6×(1-防御穿透)×(1-防御降低)；防御倍率 = (角色等级+100)÷(目标有效防御+角色等级+100)'),
        ((_L('角色等级'), _L('取本次伤害来源角色等级。')),
         (_L('防御穿透'), _L('取本次伤害来源角色命中时的防御穿透或防御无视。')),
         (_L('目标防御'), _L('优先取本次受击目标冻结属性包的基础、百分比和固定防御。')),
         (_L('防御降低'), _L('取本次受击目标命中时有效的防御降低。'))),
    ),
    "resistance": (
        _L('抗性'),
        _L('有效抗性 X = 基础抗性-减抗-属性穿透；X≥0 时抗性倍率=1-X；X<0 时抗性倍率=1-X÷1.10'),
        ((_L('伤害属性'), _L('取本条正式伤害项或逐击已确认的实际属性。')),
         (_L('基础抗性'), _L('取本次受击目标对该伤害属性的冻结战前抗性。')),
         (_L('减抗'), _L('取受击目标命中时有效、且匹配该属性的减抗。')),
         (_L('属性穿透'), _L('取伤害来源角色命中时匹配该属性的穿透。'))),
    ),
    "independent_final_damage": (
        _L('独立最终增伤'),
        _L('独立增伤 = 每个明确独立最终增伤逐项相乘'),
        ((_L('独立最终增伤'), _L('取正式效果中同时满足攻击方、受击目标、逐击标签与触发条件的最终增伤；逐项相乘。')),),
    ),
    "dot_damage": (
        "持续伤害",
        _L('单次持续伤害 = 直伤同类乘区 × 状态层数 × 持续伤害专属增伤'),
        ((_L('直伤同类乘区'), _L('攻击方提供技能倍率、面板、增伤、穿透和暴伤；受击目标提供防御、抗性、减益和易伤。')),
         (_L('状态层数'), _L('取同半场、同一受击目标在本跳前的正式状态层数或受限结算系数。')),
         (_L('持续伤害种类'), _L('取同一受击目标在本跳前仍有效、带正式 DOT 身份的种类数。'))),
    ),
    "topple_damage": (
        "倾陷伤害",
        _L('倾陷伤害 = 等级曲线 × 倾陷强度 × 倾陷上限 × 防御 × 抗性'),
        ((_L('等级曲线'), _L('团队中每名同半场角色分别取自己的等级对应倾陷曲线。')),
         ("倾陷强度", _L('每名角色分别取自己的倾陷强度和倾陷伤害提高。')),
         (_L('倾陷上限'), _L('全队各格共同取本次受击目标的倾陷上限或冻结档位覆盖。')),
         (_L('防御/抗性'), _L('每格穿透取该角色；防御、对应属性抗性和减益取受击目标。'))),
    ),
    "weave_followup": (
        _L('覆纹追加伤害'),
        _L('覆纹追加 = 原伤害实际值 × [(复制比例 + 灵可复制比例加成) × (1 + 追击增伤%) × 强度区 + 限制(强度区 - 1, 0, 100)] × 最终乘数'),
        ((_L('原伤害实际值'), _L('取被覆纹记录的攻击方真实伤害；正式 DOT 等可记录来源同样保留，不重新计算预计值。')),
         ("环合强度", _L('取被记录原伤害的实际来源角色；不比较环合双方，也不固定取 QTE 触发者。')),
         (_L('复制比例'), _L('基础为 20%。')),
         (_L('灵可复制比例加成 / 追击增伤%'), _L('弱点感应启用时各为 10%，未启用时各为 0%；(20% + 10%) × (1 + 10%) = 33%。')),
         (_L('解释范围'), _L('当前 33% 的拆分解释；追击增伤只乘复制部分。游戏内部拆分尚未独立确认，其他来源不直接代入。')),
         (_L('强度区'), _L('1 + 20% × 环合强度 / (环合强度 + 180)；环合强度最低按 0 计算。')),
         (_L('限制'), _L('把强度区减一的结果限制在 0 到 100 之间。')),
         (_L('最终乘数'), _L('当前核心模型取 1；保留原伤已结算的增伤，不除掉原增伤区，也不将整次覆纹再乘 1.10。')),
         (_L('伤害属性'), _L('继承每条原伤害的实际属性；受击目标提供该属性抗性。'))),
    ),
    "settlement_rounding": (
        _L('最终伤害向下取整'),
        _L('最终伤害 = 向下取整（不小于零的完整精度伤害）'),
        ((_L('完整精度伤害'), _L('取该公式所有适用乘区相乘后的结果；中间过程不取整。')),),
    ),
    "max_hp_settlement": (
        _L('生命上限下降结算'),
        _L('有效伤害 = 本次伤害 + 按当前生命比例折算的生命上限下降'),
        ((_L('生命上限变化'), _L('取同半场、同一受击目标已确认的新旧最大生命前沿。')),
         (_L('结算前生命'), _L('取该目标生命上限下降前附近逐击的最小可靠当前生命。')),
         (_L('来源归属'), _L('只在正式事件或已审计机制能绑定来源时归到角色；目标数据本身不证明来源。'))),
    ),
}


_PLAYER_FORMULA_STEPS: dict[str, tuple[str, ...]] = {
    "panel_attribute": (
        _L('汇总当前角色的人物、弧盘等正式基础值。'),
        _L('把同属性百分比来源同区相加，再乘基础值。'),
        _L('最后加入同属性固定值来源。'),
    ),
    "skill_multiplier": (
        _L('用攻击方本条伤害项绑定的技能与有效技能等级选倍率档。'),
        _L('筛选正式作用于本技能标签的倍率修正并相加。'),
        _L('用等级倍率乘以一加修正合计。'),
    ),
    "direct_damage": (
        _L('确认本击伤害项、缩放面板、属性、暴击策略与攻击方。'),
        _L('依次计算技能倍率、面板、增伤、暴击、防御、抗性和易伤。'),
        _L('把每个适用的独立最终增伤逐项相乘。'),
        _L('全程保留完整精度，只在最终出口向下取整。'),
    ),
    "damage_increase": (
        _L('按本击来源、属性、技能和状态标签筛选攻击方增伤。'),
        _L('同一增伤区内先相加。'),
        _L('合计加 1 得到增伤倍率。'),
    ),
    "vulnerability": (
        _L('绑定本击的受击目标。'),
        _L('筛选命中时仍有效且适用于本击的目标受伤提升。'),
        _L('同区相加后加 1 得到易伤倍率。'),
    ),
    "critical": (
        _L('先完成除暴击外的完整精度伤害。'),
        _L('按普通、固定暴击率、不可暴击或未知策略选择分支。'),
        _L('未暴击与暴击候选分别在最终出口取整，再按暴击率计算期望。'),
    ),
    "defense": (
        _L('从受击目标冻结属性包重建原始防御。'),
        _L('应用攻击方防御穿透和目标防御降低。'),
        _L('用伤害来源角色等级计算最终防御倍率。'),
    ),
    "resistance": (
        _L('按本击伤害属性读取受击目标对应基础抗性。'),
        _L('减去目标动态减抗与攻击方对应属性穿透。'),
        _L('根据有效抗性正负选择分段公式。'),
    ),
    "independent_final_damage": (
        _L('逐项核对正式效果的来源、目标、标签和触发条件。'),
        _L('每个满足条件的最终增伤先转为一加增量。'),
        _L('所有独立项逐项相乘，不并入通用增伤区。'),
    ),
    "dot_damage": (
        _L('确认正式 DOT 身份、来源角色和本次受击目标。'),
        _L('从同半场、同目标的命中前状态读取层数或受限系数。'),
        _L('按持续直伤乘区和正式暴击策略计算本跳，再应用 DOT 专属最终区。'),
        _L('只在本跳最终出口取整。'),
    ),
    "topple_damage": (
        _L('固定同半场完整阵容与同一受击目标。'),
        _L('每名角色分别读取等级曲线、倾陷强度、穿透和固有伤害属性。'),
        _L('逐角色计算后求和，并在最终出口取整。'),
    ),
    "weave_followup": (
        _L('记录每条符合条件的实际伤害及其属性，包括正式 DOT 等被记录来源。'),
        _L('读取每条被记录原伤害实际来源角色的环合强度。'),
        _L('基础复制比例加上灵可复制比例加成，乘以一加追击增伤和强度区，再加入强度区减一的限制项。'),
        _L('12 秒结束时逐条追加并最终取整。'),
    ),
    "settlement_rounding": (
        _L('保留公式中间乘区的完整精度。'),
        _L('把最终结果限制为不小于零。'),
        _L('只在机制定义的最终出口向下取整。'),
    ),
    "max_hp_settlement": (
        _L('绑定同半场、同目标连续的旧/新最大生命前沿。'),
        _L('用结算前当前生命占旧最大生命的比例折算有效损失。'),
        _L('只把已确认来源的结算归到对应角色。'),
    ),
}


class StaticCatalogMechanicsDetailProjector:
    """Project formula/model domain facts without owning catalog lookup state."""

    def __init__(self, terminology_service: StaticCatalogTerminologyService) -> None:
        self._terminology = terminology_service

    def formula_detail(self, formula: FormulaDetailView) -> MechanicsDetail:
        title, expression, player_variables = self.player_formula(formula)
        variables = tuple(
            PlayerField(label, meaning, "accent")
            for label, meaning in player_variables
        )
        steps = _PLAYER_FORMULA_STEPS.get(formula.key, ())
        sections = (
            PlayerSection(_L('完整公式'), (PlayerField("公式", expression, "formula"),)),
            PlayerSection(_L('计算顺序'), (PlayerField(
                _L('逐步过程'),
                "\n".join(
                    f"{index}. {step}"
                    for index, step in enumerate(steps, start=1)
                ),
                "accent",
            ),)),
            PlayerSection(_L('变量来源'), variables),
            PlayerSection(
                _L('判定与限制'),
                tuple(
                    PlayerField(_L('适用条件'), value, "accent")
                    for value in formula.applicable_when
                ) + tuple(
                    PlayerField(_L('边界'), value, "warning")
                    for value in formula.limitations
                ),
            ),
        )
        return MechanicsDetail(
            record_id=encode_record("formula", formula.key),
            card_kind="formula",
            title=title,
            subtitle=expression,
            family_key=FORMULA_FAMILY_BY_KEY[formula.key],
            badges=(FORMULA_CHAPTER_BY_KEY.get(formula.key, "公式"),),
            status=None,
            owner_label=_L('全局公式'),
            owner_link=None,
            redirect_only=False,
            sections=sections,
            identity_fields=(),
            evidence_stages=(),
            related_links=(),
            audit_references=tuple(
                f"{source.location}::{source.symbol}" for source in formula.sources
            ),
        )

    @staticmethod
    def player_formula(
        formula: FormulaDetailView,
    ) -> tuple[str, str, tuple[tuple[str, str], ...]]:
        """Return the curated Chinese projection; internal symbols never reach Qt."""
        try:
            return _PLAYER_FORMULAS[formula.key]
        except KeyError as exc:
            raise LookupError(_LF('公式缺少玩家中文投影：{0}').format((formula.key))) from exc

    def model_detail(self, model: CounterfactualMatrixRow) -> MechanicsDetail:
        consumer = (
            _L('已接入战报反事实')
            if model.consumer_entries
            else _L('尚未接入生产反事实')
        )
        if model.key == "native_counterfactual_core":
            consumer = _L('差分验证组件，未接入生产')
        covered_entities = (
            (model.covered_entities,)
            if isinstance(model.covered_entities, str)
            else model.covered_entities
        )
        sections = (
            PlayerSection(_L('怎么做的'), (PlayerField(
                _L('建模方案'),
                self.player_model_text(model.modeling_scheme),
            ),)),
            PlayerSection(
                _L('当前覆盖'),
                tuple(
                    PlayerField(
                        _L('覆盖'),
                        self.player_model_text(value),
                        "success",
                    )
                    for value in covered_entities
                ) or (PlayerField(_L('覆盖'), _L('尚无可确认对象'), "warning"),),
            ),
            PlayerSection(
                _L('缺口与限制'),
                tuple(
                    PlayerField(_L('缺口'), self._human_gap(code), "warning")
                    for code in model.gap_codes
                ) + tuple(
                    PlayerField(
                        _L('限制'),
                        self.player_model_text(value),
                        "warning",
                    )
                    for value in model.limitations
                ),
            ),
        )
        return MechanicsDetail(
            record_id=encode_record("model", model.key),
            card_kind="model",
            title=model.mechanism,
            subtitle=model.scope,
            family_key=MODEL_FAMILY_BY_KEY[model.key],
            badges=(model.status_label, model.category),
            status=model.status,
            owner_label=_L('公共机制'),
            owner_link=None,
            redirect_only=False,
            sections=sections,
            identity_fields=(),
            evidence_stages=self._evidence_stages(model, consumer),
            related_links=self._model_links(model),
            audit_references=model.evidence,
            notice=consumer,
        )

    def player_model_text(self, value: str) -> str:
        text = str(value)
        for property_id in ("DefIgnore", "UnbalMax"):
            if property_id not in text:
                continue
            label = self._formal_attribute_name(property_id)
            replacement = (
                label
                if label == PLACEHOLDER_NAME
                else f"{label}（{property_id}）"
            )
            text = text.replace(property_id, replacement)
        replacements = (
            ("(scope_half,target_id)", _L('（半场、目标身份）')),
            ("Core v4 max_hp_reduction", _L('Core v4 最大生命下降事件')),
            (_L('8 Buff / 56 逐击公开差分'), _L('8 个 Buff、56 次逐击公开差分')),
            (
                "complete/partial/unavailable/not_applicable",
                _L('完整、部分、不可用、不适用'),
            ),
            ("not_applicable", _L('不适用')),
            ("unavailable", "不可用"),
            ("partial", _L('部分覆盖')),
            ("complete", _L('完整')),
            ("unknown", "未知"),
            ("nullable", _L('未量化状态')),
            ("ratio=1", _L('倍率 1')),
            ("contract", _L('契约')),
            (_L('UI 文案'), _L('界面文案')),
        )
        for source, target in replacements:
            text = text.replace(source, target)
        return text

    def _formal_attribute_name(self, property_id: str) -> str:
        term = self._terminology.resolve("equipment_attribute", property_id)
        if term.name_available and term.display_name:
            return term.display_name
        return PLACEHOLDER_NAME

    @staticmethod
    def _model_links(
        model: CounterfactualMatrixRow,
    ) -> tuple[tuple[str, CatalogLink], ...]:
        formula_by_model = {
            "buff_ge_attributes": "damage_increase",
            "formal_dot_classification": "dot_damage",
            "dot_state_replay": "dot_damage",
            "topple_base_formula": "topple_damage",
            "topple_special_states": "topple_damage",
            "max_hp_settlement": "max_hp_settlement",
            "fixed_axis_replay": "direct_damage",
        }
        key = formula_by_model.get(model.key)
        if key is None:
            return ()
        return ((
            _L('查看相关公式'),
            CatalogLink(
                "combat_mechanics",
                encode_record("formula", key),
                "formula",
            ),
        ),)

    @staticmethod
    def _human_gap(code: str) -> str:
        translations = {
            "native_production_consumer_unavailable": _L('尚未接入生产反事实'),
            "native_stateful_mechanics_unavailable": _L('状态机制尚未迁移'),
            "summon_lifecycle_axis_unavailable": _L('缺少召唤物生命周期轴'),
            "summon_spatial_state_unavailable": _L('缺少召唤物空间状态'),
            "summon_resource_state_unavailable": _L('缺少召唤物资源状态'),
            "player_shield_axis_unavailable": _L('缺少玩家护盾状态轴'),
            "dot_application_event_missing": _L('缺少正式 DOT 施加事件'),
            "dot_state_kind_unmodeled": _L('仍有 DOT 类型尚未建模'),
            "dot_axis_incomplete": _L('逐击轴不完整'),
            "attachment_lifecycle_unobserved": _L('附着物生命周期尚未观测完整'),
            "attachment_owner_unresolved": _L('附着物来源归属尚未确认'),
            "buff_property_consumer_missing": _L('Buff 属性缺少已确认的公式消费者'),
            "buff_target_condition_unresolved": _L('Buff 目标条件尚未确认'),
            "buff_trigger_unresolved": _L('Buff 触发条件尚未确认'),
            "max_hp_axis_continuity_unavailable": _L('最大生命状态轴不连续'),
            "max_hp_source_attribution_unresolved": _L('最大生命变化来源尚未确认'),
            "topple_duration_unreliable": _L('倾陷持续时间证据不可靠'),
            "topple_special_settlement_unobserved": _L('倾陷特殊结算尚未观测'),
            "treatment_event_evidence_missing": _L('缺少正式治疗事件证据'),
            "treatment_formula_source_unresolved": _L('治疗公式来源尚未确认'),
        }
        return translations.get(code, _L('缺口说明暂未本地化'))

    @staticmethod
    def _evidence_stages(
        model: CounterfactualMatrixRow,
        consumer_summary: str,
    ) -> tuple[EvidenceStage, ...]:
        gaps = " ".join(model.gap_codes)
        unavailable = model.status == "unavailable"
        partial = model.status == "partial"

        def state(*tokens: str) -> str:
            if any(token in gaps for token in tokens):
                return "unavailable" if unavailable else "partial"
            return "complete" if not partial else "partial"

        return (
            EvidenceStage(
                "definition",
                _L('正式定义'),
                "complete",
                _L('机制身份与适用范围已登记'),
            ),
            EvidenceStage(
                "trigger",
                _L('触发证据'),
                state("trigger", "event"),
                _L('按正式逐击或已审计事件判断，不从文案补猜'),
            ),
            EvidenceStage(
                "state",
                _L('状态轴'),
                state("state", "axis", "lifecycle", "duration"),
                _L('层数、持续时间与目标范围按当前证据传播'),
            ),
            EvidenceStage(
                "hit",
                _L('逐击投影'),
                state("owner", "target", "spatial"),
                _L('保留真实逐击，不生成缺失动作或命中'),
            ),
            EvidenceStage(
                "formula",
                _L('公式消费'),
                state("formula", "consumer"),
                _L('只进入已确认的伤害乘区或专用结算'),
            ),
            EvidenceStage(
                "production",
                _L('生产反事实'),
                "complete" if model.status == "complete" and model.consumer_entries
                else "partial" if model.consumer_entries
                else "unavailable",
                consumer_summary,
            ),
        )
