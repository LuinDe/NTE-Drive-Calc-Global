"""Translations (ko / en / ja) of the team-simulator resource texts (energy, Esper-Cycle gauge, cooldowns).

usage: i18n_resource_keys.py <out dir>   -> writes i18n_ko.json, i18n_en.json, i18n_ja.json ({zh key: translation})
for V/tools/l10n_add_keys.py.  ko follows design_final.md §7.4 where the key matches; terms follow the shipped tables
(终结能量 울티메이트 에너지 / Ultimate Energy / アルティメットエネルギー; 环合值 사이클 수치 / Cycle Value / サイクル値;
冷却 쿨타임 / cooldown / クールタイム; 援护技 서포트 스킬 / Support Skill / 支援スキル; 极轨终结 울티메이트 / Ultimate /
アルティメット; 变轨技能 바이레일 스킬 / Skill / スキル; 极限反击 극한 반격 / Extreme Counter / 極限カウンター).
"""
from __future__ import annotations

import json
import pathlib
import string
import sys

ROWS = [
    # (zh key, ko, en, ja)
    ('该顺序可释放更多极轨终结（{0} 次）', '이 순서가 울티메이트를 더 많이 발동함 ({0}회)',
     'This order casts more Ultimates ({0})', 'この順番はアルティメットをより多く発動（{0}回）'),
    ('资源模型：{0}', '자원 모델: {0}', 'Resource model: {0}', 'リソースモデル：{0}'),
    ('环合值按每次命中累积，第 1 轮开始时为 100，之后不再自动补满',
     '사이클 수치는 타격마다 누적하며, 1바퀴 시작 시 100이고 이후 자동으로 보충하지 않음',
     'Cycle Value builds up with every hit: 100 at the start of loop 1, never refilled automatically afterwards',
     'サイクル値はヒットごとに蓄積し、1周目の開始時は100、以降は自動で補充しない'),
    ('第 {0} 轮开始时 {1} 的环合值补满 100（缺少数据时的固定规则）',
     '{0}바퀴 시작 시 {1}의 사이클 수치를 100으로 보충 (데이터 부족 시 고정 규칙)',
     "{1}'s Cycle Value is set to 100 at the start of loop {0} (fixed rule for missing data)",
     '{0}周目の開始時に{1}のサイクル値を100にする（データ不足時の固定ルール）'),
    ('{0} 的极轨终结按终结能量检查（消耗 {1}）；能量不足时跳过',
     '{0}의 울티메이트는 울티메이트 에너지를 검사함 (소모 {1}), 부족하면 건너뜀',
     "{0}'s Ultimate checks Ultimate Energy (cost {1}); skipped when short",
     '{0}のアルティメットはアルティメットエネルギーを判定（消費 {1}）、不足時はスキップ'),
    ('开场时极轨终结能量已满（实测：首次释放均在战斗初期）',
     '시작 시 울티메이트 에너지가 가득 참 (실측: 첫 발동이 모두 전투 초반)',
     'Ultimate Energy is full at the start (measured: every first cast came early in the battle)',
     '開始時のアルティメットエネルギーは満タン（実測：初回発動はすべて戦闘序盤）'),
    ('终结能量获取 = 每次命中的充能量 ×（1 + 充能效率）', '울티메이트 에너지 획득 = 타격당 충전량 × (1 + 에너지 충전 효율)',
     'Ultimate Energy gain = charge per hit × (1 + Charge Efficiency)',
     'アルティメットエネルギー獲得 = ヒットごとのチャージ量 ×（1 + チャージ効率）'),
    ('冷却未结束时插入等待后再使用（共 {0:.1f} 秒）', '쿨타임이 끝나지 않으면 대기 후 사용 (총 {0:.1f}초)',
     'A skill whose cooldown is not ready is used after a wait ({0:.1f} s in total)',
     'クールタイム中のスキルは待機してから使用（合計 {0:.1f}秒）'),
    ('冷却与时计按包含时停的实际时间计算', '쿨타임과 시계는 시간 정지를 포함한 실제 시간 기준으로 계산',
     'Cooldowns and clocks run on real time, Time Stops included',
     'クールタイムと時計は時間停止を含む実時間で計算'),
    ('冷却与时计按扣除时停后的战斗时间计算', '쿨타임과 시계는 시간 정지를 뺀 전투 시간 기준으로 계산',
     'Cooldowns and clocks run on battle time without Time Stops',
     'クールタイムと時計は時間停止を除いた戦闘時間で計算'),
    ('{0} 使用自身资源「{1}」，按游戏数据计算', '{0}은(는) 자체 자원 「{1}」을(를) 사용하며 게임 데이터로 계산',
     '{0} uses its own resource "{1}", calculated from game data', '{0}は固有リソース「{1}」を使用し、ゲームデータで計算'),
    ('{0} 等待「{1}」蓄满约 {2:.1f} 秒（视为队友行动的时间，未计入时间轴）',
     '{0}이(가) 「{1}」이(가) 가득 찰 때까지 약 {2:.1f}초 대기 (동료 행동 시간으로 간주, 타임라인 미반영)',
     '{0} waits about {2:.1f} s for "{1}" to fill (counted as teammates\' time, not added to the timeline)',
     '{0}は「{1}」が満タンになるまで約 {2:.1f}秒待機（味方の行動時間とみなし、タイムラインには加えない）'),
    ('按自定义循环的资源模型：{0}', '직접 입력 사이클의 자원 모델: {0}', 'Resource model of the custom cycle: {0}',
     '直接入力サイクルのリソースモデル：{0}'),
    ('每次命中的终结能量都会累计并显示；消耗量未知的队员不检查能量',
     '타격마다 얻는 울티메이트 에너지는 모두 누적해 표시하며, 소모량을 모르는 팀원은 에너지를 검사하지 않음',
     'Ultimate Energy from every hit is tracked and shown; members whose cost is unknown are not checked',
     'ヒットごとのアルティメットエネルギーはすべて累計して表示。消費量が不明なメンバーはエネルギーを判定しない'),
    ('{0} 的终结能量消耗未知，不检查能量（照常释放）', '{0}의 울티메이트 에너지 소모량을 알 수 없어 검사하지 않음 (그대로 발동)',
     "{0}: Ultimate Energy cost unknown, not checked (the Ultimate is cast as usual)",
     '{0}のアルティメットエネルギー消費量が不明のため判定しない（通常どおり発動）'),
    ('{0} 的终结能量消耗 {1} 来自游戏已不引用的旧数据表，未用于检查',
     '{0}의 울티메이트 에너지 소모량 {1}은(는) 게임이 더 이상 참조하지 않는 옛 데이터 표의 값이라 검사에 쓰지 않음',
     "{0}'s Ultimate Energy cost {1} comes from an old data table the game no longer uses; not used for the check",
     '{0}のアルティメットエネルギー消費 {1} はゲームが参照しなくなった旧データ表の値のため、判定に使わない'),
    ('社区资料的终结能量消耗（100/120）与每次命中的充能量是否同一单位尚未确认，只作显示',
     '커뮤니티 자료의 울티메이트 에너지 소모량(100/120)이 타격당 충전량과 같은 단위인지 아직 확인되지 않아 표시만 함',
     'Whether the community Ultimate Energy costs (100/120) use the same unit as the charge per hit is not confirmed yet; shown only',
     'コミュニティ情報のアルティメットエネルギー消費（100/120）がヒットごとのチャージ量と同じ単位かは未確認のため、表示のみ'),
    ('{0} 的 {1} 冷却时间未知，不检查', '{0}의 {1} 쿨타임을 알 수 없어 검사하지 않음',
     "{0}: {1} cooldown unknown, not checked", '{0}の{1}のクールタイムが不明のため判定しない'),
    ('{0} 的冷却时间：{1}（社区资料，可信度低）', '{0}의 쿨타임: {1} (커뮤니티 자료, 신뢰도 낮음)',
     '{0} cooldowns: {1} (community data, low confidence)', '{0}のクールタイム：{1}（コミュニティ情報、信頼度：低）'),
    ('{0} 的援护技与极限反击在游戏数据中没有冷却设定，仅受环合值与闪避冷却限制',
     '{0}의 서포트 스킬과 극한 반격은 게임 데이터에 쿨타임 설정이 없어 사이클 수치와 회피 쿨타임으로만 제한',
     '{0}: Support Skill and Extreme Counter have no cooldown of their own in the game data; only Cycle Value and the dodge cooldown limit them',
     '{0}の支援スキルと極限カウンターはゲームデータにクールタイム設定がなく、サイクル値と回避のクールタイムだけで制限される'),
    ('{0} 因终结能量不足跳过了 {1} 次极轨终结', '{0}: 울티메이트 에너지 부족으로 울티메이트 {1}회 건너뜀',
     '{0} skipped {1} Ultimate(s) for lack of Ultimate Energy', '{0}はアルティメットエネルギー不足でアルティメットを{1}回スキップ'),
    ('{0} 等待冷却共 {1:.1f} 秒', '{0}: 쿨타임 대기 총 {1:.1f}초', '{0} waited {1:.1f} s for cooldowns in total',
     '{0}のクールタイム待機 合計 {1:.1f}秒'),
    ('{0} 的 {1} 冷却超过 {2} 秒，已跳过（请检查数据）', '{0}의 {1} 쿨타임이 {2}초를 넘어 건너뜀 (데이터 확인 필요)',
     "{0}: {1} cooldown longer than {2} s, skipped (check the data)", '{0}の{1}のクールタイムが{2}秒を超えたためスキップ（データを確認してください）'),
    ('{0} 第 {1} 轮未进入形态（极轨终结被跳过），形态内动作未执行',
     '{0}: {1}바퀴에 형태에 진입하지 못해 (울티메이트 건너뜀) 형태 안 동작을 실행하지 않음',
     '{0} did not enter its form in loop {1} (Ultimate skipped); the form actions were not used',
     '{0}は{1}周目に形態に入れず（アルティメットをスキップ）、形態中の動作は未実行'),
    ('{0} 的自身资源「{1}」每次获得量的单位未确认，只显示不检查',
     '{0}의 자체 자원 「{1}」 획득 단위가 확인되지 않아 표시만 하고 검사하지 않음',
     '{0}: the unit of each "{1}" gain is not confirmed; shown, not checked',
     '{0}の固有リソース「{1}」の獲得単位が未確認のため、表示のみで判定しない'),
    ('{0} 的「{1}」在时停中的消耗起点与终结后的剩余量未确认，按较严格的读法计算',
     '{0}의 「{1}」 시간 정지 중 소모 시작 시점과 종결 후 잔량이 확인되지 않아 더 엄격한 해석으로 계산',
     "{0}: when \"{1}\" starts draining in the Time Stop and what is left after the finisher are not confirmed; the stricter reading is used",
     '{0}の「{1}」の時間停止中の消費開始と終結後の残量が未確認のため、厳しいほうの解釈で計算'),
    ('{0} 的“离场再入场”步骤无法在一次出场中模拟，按原地等待计算',
     '{0}의 "잠시 교체 후 재입장" 단계는 한 번의 출전 안에서 재현할 수 없어 제자리 대기로 계산',
     '{0}: the "swap out and back in" step cannot be simulated inside one visit; counted as waiting in place',
     '{0}の「一度交代して再登場」する手順は1回の登場内で再現できないため、その場で待機として計算'),
    ('{0} 的仅计时步骤按技能数据计入环合值（近似）', '{0}의 시간만 계산하는 단계는 스킬 데이터로 사이클 수치를 반영 (근사)',
     "{0}: time-only steps add Cycle Value from the skill data (approximate)",
     '{0}の時間のみの手順はスキルデータでサイクル値を加算（近似）'),
    ('{0} 有 {1} 个仅计时的步骤在游戏中会累积环合值（结果偏低）', '{0}의 시간만 반영된 단계 {1}개는 실제로는 사이클 수치를 쌓음 (결과가 낮게 나옴)',
     '{0} has {1} time-only step(s) that build Cycle Value in the game (result low)',
     '{0}の時間のみの手順{1}個はゲームではサイクル値を蓄積する（結果は低め）'),
    ('{0} 的能量与冷却相关效果未模拟：{1}', '{0}의 에너지·쿨타임 관련 효과 미구현: {1}',
     '{0}: energy and cooldown effects not simulated: {1}', '{0}のエネルギー・クールタイム関連効果は未実装：{1}'),
    ('盈蓄的终结能量未计入能量检查（偏保守）', '차지의 울티메이트 에너지는 에너지 검사에 반영하지 않음 (보수적)',
     "Charge's Ultimate Energy is not counted in the energy check (conservative)",
     '盈蓄によるアルティメットエネルギーはエネルギー判定に含めない（控えめ）'),
    ('环合效率修正（覆纹 −50% 等）未计入', '사이클 효율 보정 (헥스 −50% 등) 미반영',
     'Cycle efficiency modifiers (Hex −50% etc.) are not applied', 'サイクル効率補正（覆紋 −50% など）は未反映'),
    ('{0} 的第 {1} 步冷却类型未建模，未检查冷却', '{0}의 {1}번 단계는 쿨타임 종류가 모델에 없어 쿨타임을 검사하지 않음',
     "{0}: the cooldown kind of step {1} is not modelled; cooldown not checked",
     '{0}の手順{1}はクールタイムの種類が未モデル化のため判定しない'),
    ('{0} 的变轨技能可储存 {1} 次，每次 {2} 秒恢复（按依次恢复计算，含义未确认）',
     '{0}의 바이레일 스킬은 {1}회 저장되며 회당 {2}초에 회복 (차례대로 회복으로 계산, 의미 미확인)',
     "{0}'s Skill stores {1} uses, each back after {2} s (recharged one after another; meaning not confirmed)",
     '{0}のスキルは{1}回までストックでき、1回{2}秒で回復（順番に回復として計算、意味は未確認）'),
    ('旧规则（第 1、3 轮补满，不检查能量与冷却）', '기존 규칙 (1·3바퀴 보충, 에너지·쿨타임 미검사)',
     'Old rule (refill at loops 1 and 3, no energy / cooldown check)', '旧ルール（1・3周目に補充、エネルギー・クールタイムを判定しない）'),
    ('游戏数据 + 社区冷却', '게임 데이터 + 커뮤니티 쿨타임', 'Game data + community cooldowns', 'ゲームデータ + コミュニティのクールタイム'),
    ('非闭合时计', '열린 시계', 'Unclosed Timepiece', '非閉合の時計'),
    ('桀骜斗志', '야성의 투지', 'Untamed Fighting Spirit', '不羈の闘志'),
    ('变轨技能', '바이레일 스킬', 'Skill', 'スキル'),
    ('变轨技能（噤念/如此罪状）', '바이레일 스킬 (억눌린 생각/정죄의 일격)', 'Skill (Silenced Thought / Such Are the Charges)',
     'スキル（噤念/かくなる罪状）'),
    ('变轨技能（短按）', '바이레일 스킬 (짧게 누르기)', 'Skill (tap)', 'スキル（短押し）'),
    ('极轨终结', '울티메이트', 'Ultimate', 'アルティメット'),
    ('极限反击', '극한 반격', 'Extreme Counter', '極限カウンター'),
    ('闪避', '회피', 'Dodge', '回避'),
    ('说明文', '설명문', 'Description text', '説明文'),
    ('旧数据表', '옛 데이터 표', 'Old data table', '旧データ表'),
    ('推断', '추정', 'Inferred', '推定'),
    ('社区·低', '커뮤니티·낮음', 'Community · low', 'コミュニティ・低'),
    ('社区·极低', '커뮤니티·매우 낮음', 'Community · very low', 'コミュニティ・極低'),
    ('用户填写', '사용자 입력', 'Entered by user', 'ユーザー入力'),
    ('未知', '알 수 없음', 'Unknown', '不明'),
    ('6 觉醒自动援护技', '6각성 자동 서포트 스킬', 'Awakening 6 automatic Support Skill', '覚醒6の自動支援スキル'),
    ('「恶魔的礼物」的能量', '「악마의 선물」의 에너지', 'energy of "Devil\'s Gift"', '「悪魔の贈り物」のエネルギー'),
    ('6 觉醒协同攻击充能', '6각성 협동 공격 충전', 'Awakening 6 co-attack charge', '覚醒6の協同攻撃チャージ'),
    ('5 觉醒协同攻击触发的环合反应', '5각성 협동 공격이 일으키는 사이클 반응', 'Esper-Cycle reaction from the Awakening 5 co-attack',
     '覚醒5の協同攻撃によるサイクル反応'),
    ('3 觉醒返还时计', '3각성 시계 반환', 'Awakening 3 clock refund', '覚醒3の時計返還'),
    ('4 觉醒击败目标恢复时计', '4각성 처치 시 시계 회복', 'Awakening 4 clock refill on kill', '覚醒4の撃破時の時計回復'),
    ('变轨技能记录期间额外消耗的时计', '바이레일 스킬 기록 중 추가로 소모되는 시계', 'extra clock drained while the Skill records',
     'スキル記録中に追加で消費する時計'),
    ('持续施放延长冷却', '계속 시전 시 쿨타임 연장', 'cooldown extension while channelling', '継続発動によるクールタイム延長'),
    ('盈蓄时获得 120 点终结能量', '차지 시 울티메이트 에너지 120 획득', '120 Ultimate Energy on Charge', '盈蓄時にアルティメットエネルギー120獲得'),
    ('1 觉醒缩短冷却', '1각성 쿨타임 단축', 'Awakening 1 cooldown cut', '覚醒1のクールタイム短縮'),
    ('1 觉醒追加攻击 +2.5', '1각성 추가 공격 +2.5', 'Awakening 1 follow-up attack +2.5', '覚醒1の追撃 +2.5'),
    ('每层闪送之力 +5', '스피드퀵 1중첩마다 +5', '+5 per Power of Flash Delivery stack', '速達の力1層ごとに +5'),
    ('致约清算 +40', '계약 청산 +40', 'Pact Reckoning +40', '致約清算 +40'),
    ('6 觉醒 +50', '6각성 +50', 'Awakening 6 +50', '覚醒6 +50'),
    ('5 觉醒浮空时回满能量', '5각성 띄우기 시 에너지 완충', 'Awakening 5 full energy on lift', '覚醒5の浮かせ時にエネルギー全回復'),
    ('2 觉醒反击失败时回满能量', '2각성 반격 실패 시 에너지 완충', 'Awakening 2 full energy on a failed counter',
     '覚醒2のカウンター失敗時にエネルギー全回復'),
    ('达到破灭阈值时回满能量', '파멸 임계값 도달 시 에너지 완충', 'full energy at the Ruin Threshold', '破滅閾値到達時にエネルギー全回復'),
    ('盈蓄强化 +4', '차지 강화 +4', 'Charge boost +4', '盈蓄強化 +4'),
    ('角色未上线，数据待确认', '캐릭터 출시 전, 데이터 확인 대기', 'character not released yet, data pending', 'キャラクター未実装のためデータ確認待ち'),
    ('潜影结束动作的两种版本', '잠영 종료 동작의 두 가지 버전', 'two versions of the Shadow Dive exit', '潜影終了動作の2つのバージョン'),
    ('短按变轨技能的 2 秒冷却', '짧게 누르는 바이레일 스킬의 2초 쿨타임', '2 s cooldown of the tapped Skill', '短押しスキルの2秒クールタイム'),
    ('魔女形态极轨终结的冷却', '마녀 형태 울티메이트의 쿨타임', 'cooldown of the witch-form Ultimate', '魔女形態アルティメットのクールタイム'),
    ('4 觉醒「梦魇生花」', '4각성 「악몽에 피는 꽃」', 'Awakening 4 "Nightmare Blossom"', '覚醒4「悪夢に咲く花」'),
    ('终结能量不足（{0:.0f}/{1:.0f}），跳过', '울티메이트 에너지 부족 ({0:.0f}/{1:.0f}), 건너뜀',
     'Not enough Ultimate Energy ({0:.0f}/{1:.0f}), skipped', 'アルティメットエネルギー不足（{0:.0f}/{1:.0f}）、スキップ'),
    ('冷却还差 {0:.1f} 秒，超过最长等待，跳过', '쿨타임 {0:.1f}초 남음, 최대 대기 시간을 넘어 건너뜀',
     'Cooldown {0:.1f} s away, longer than the longest wait: skipped', 'クールタイム残り {0:.1f}秒、最長待機を超えたためスキップ'),
    ('严格检查：冷却未结束时等待（共 {0:.1f} 秒），终结能量不足时跳过极轨终结（{1} 次），超过最长等待时跳过（{2} 次）',
     '엄격 검사: 쿨타임이 끝나지 않으면 대기 (총 {0:.1f}초), 울티메이트 에너지 부족 시 울티메이트 건너뜀 ({1}회), 최대 대기 시간 초과 시 건너뜀 ({2}회)',
     'Strict check: waits for cooldowns ({0:.1f} s in total), skips Ultimates without enough Ultimate Energy ({1}), skips beyond the longest wait ({2})',
     '厳格チェック：クールタイム中は待機（合計 {0:.1f}秒）、アルティメットエネルギー不足のアルティメットはスキップ（{1}回）、最長待機を超えるとスキップ（{2}回）'),
    ('资源模型', '자원 모델', 'Resource model', 'リソースモデル'),
    ('- 冷却时间与极轨终结能量：按游戏数据检查（可选社区冷却）；缺少数据的队员在说明中标出（不检查）',
     '- 쿨타임과 울티메이트 에너지: 게임 데이터로 검사 (커뮤니티 쿨타임 선택 가능), 데이터가 없는 팀원은 설명에 표시 (검사 안 함)',
     '- Cooldowns and Ultimate Energy: checked with game data (community cooldowns optional); members without data are named in the explanation (not checked)',
     '- クールタイムとアルティメットエネルギー：ゲームデータで判定（コミュニティのクールタイムも選択可）。データのないメンバーは説明に表示（判定しない）'),
    ('3 轮循环 · 第 1 轮开始时环合值为 100，之后按命中累积（缺少数据的队员第 3 轮补满）',
     '3바퀴 · 1바퀴 시작 시 사이클 수치 100, 이후 타격으로 누적 (데이터 없는 팀원은 3바퀴에 보충)',
     '3 loops · Cycle Value 100 at the start of loop 1, then built up by hits (members without data refilled in loop 3)',
     '3周 · 1周目の開始時にサイクル値100、以降はヒットで蓄積（データのないメンバーは3周目に補充）'),
    ('- 循环：3 轮，第 1 轮开始时环合值为 100，之后按命中累积（缺少数据的队员在第 3 轮开始时补满 100）',
     '- 사이클: 3바퀴, 1바퀴 시작 시 사이클 수치 100, 이후 타격으로 누적 (데이터가 없는 팀원은 3바퀴 시작 시 100으로 보충)',
     '- Loops: 3; Cycle Value 100 at the start of loop 1, then built up by hits (members without data are refilled to 100 at the start of loop 3)',
     '- サイクル：3周、1周目の開始時にサイクル値100、以降はヒットで蓄積（データのないメンバーは3周目の開始時に100へ補充）'),
    ('等待 {0:.1f}s', '대기 {0:.1f}s', 'Wait {0:.1f}s', '待機 {0:.1f}s'),
    ('极轨终结 {0}/{1}', '울티 {0}/{1}', 'Ultimate {0}/{1}', 'アルティメット {0}/{1}'),
    ('能量未检查', '에너지 미검사', 'Energy not checked', 'エネルギー未判定'),
    ('固定环合值规则', '고정 사이클 수치 규칙', 'Fixed Cycle Value rule', '固定サイクル値ルール'),
    ('冷却未就绪，跳过', '쿨타임 미완료, 건너뜀', 'Cooldown not ready, skipped', 'クールタイム中のためスキップ'),
    ('等待冷却 {0:.1f} 秒（{1}）', '쿨타임 {0:.1f}초 대기 ({1})', 'Cooldown wait {0:.1f} s ({1})', 'クールタイム待機 {0:.1f}秒（{1}）'),
    ('等待时计 {0:.1f} 秒', '시계 {0:.1f}초 대기', 'Clock wait {0:.1f} s', '時計待機 {0:.1f}秒'),
    ('终结能量不足，跳过', '울티메이트 에너지 부족, 건너뜀', 'Not enough Ultimate Energy, skipped', 'アルティメットエネルギー不足のためスキップ'),
    ('未进入形态，未执行', '형태에 진입하지 않아 실행하지 않음', 'Form not entered; not used', '形態に入っていないため未実行'),
    ('额外的变轨技能（5 次普通攻击后，不计冷却）', '추가 바이레일 스킬 (일반 공격 5회 후, 쿨타임 없음)',
     'Extra Skill (after 5 Basic Attacks, no cooldown)', '追加のスキル（通常攻撃5回後、クールタイムなし）'),
    ('冷却未就绪（还差 {0:.1f} 秒）', '쿨타임 미완료 ({0:.1f}초 남음)', 'Cooldown not ready ({0:.1f} s left)',
     'クールタイム中（残り {0:.1f}秒）'),
    ('环合值 +{0:.1f}（按技能数据）', '사이클 수치 +{0:.1f} (스킬 데이터 기준)', 'Cycle Value +{0:.1f} (from skill data)',
     'サイクル値 +{0:.1f}（スキルデータ基準）'),
    ('按命中累积', '타격으로 누적', 'Built up by hits', 'ヒットで蓄積'),
    ('固定规则', '고정 규칙', 'Fixed rule', '固定ルール'),
    ('游戏数据 {0} · 社区 {1} · 未知 {2}', '게임 데이터 {0} · 커뮤니티 {1} · 알 수 없음 {2}',
     'Game data {0} · community {1} · unknown {2}', 'ゲームデータ {0} · コミュニティ {1} · 不明 {2}'),
    ('时计', '시계', 'Clock', '時計'),
    ('能量', '에너지', 'Energy', 'エネルギー'),
    ('获得 +{0:.0f}（消耗未知）', '획득 +{0:.0f} (소모 미상)', 'gained +{0:.0f} (cost unknown)', '獲得 +{0:.0f}（消費不明）'),
    ('跳过 Q', 'Q 건너뜀', 'Q skipped', 'Q スキップ'),
    ('第 {0} 轮开始：{1} 环合值补满 100（固定规则）', '{0}바퀴 시작: {1} 사이클 수치 100 보충 (고정 규칙)',
     "Loop {0} starts: {1}'s Cycle Value set to 100 (fixed rule)", '{0}周目開始：{1}のサイクル値を100に補充（固定ルール）'),
    ('社区资料（可信度低）：{0}', '커뮤니티 자료 (신뢰도 낮음): {0}', 'Community data (low confidence): {0}',
     'コミュニティ情報（信頼度：低）：{0}'),
    ('资源与冷却', '자원·쿨타임', 'Resources & cooldowns', 'リソース・クールタイム'),
    ('E 冷却', 'E 쿨타임', 'E cooldown', 'E クールタイム'),
    ('Q 冷却', 'Q 쿨타임', 'Q cooldown', 'Q クールタイム'),
    ('援护技冷却', '서포트 스킬 쿨타임', 'Support Skill cooldown', '支援スキルのクールタイム'),
    ('极限反击冷却', '극한 반격 쿨타임', 'Extreme Counter cooldown', '極限カウンターのクールタイム'),
    ('实测上限 ≤ {0}（不作为数值）', '실측 상한 ≤ {0} (수치로 쓰지 않음)', 'Measured upper bound ≤ {0} (not used as a value)',
     '実測上限 ≤ {0}（数値としては使わない）'),
    ('终结能量获取 +{0:.0f}', '울티메이트 에너지 획득 +{0:.0f}', 'Ultimate Energy gained +{0:.0f}',
     'アルティメットエネルギー獲得 +{0:.0f}'),
    ('严格（等待冷却，能量不足跳过）', '엄격 (쿨타임 대기, 에너지 부족 시 건너뜀)', 'Strict (wait for cooldowns, skip on low energy)',
     '厳格（クールタイムを待機、エネルギー不足でスキップ）'),
    ('最长等待（秒）', '최대 대기 시간(초)', 'Longest wait (s)', '最長待機（秒）'),
    ('实测上限 ≤ {0} 秒（不作为数值）', '실측 상한 ≤ {0}초 (수치로 쓰지 않음)', 'Measured upper bound ≤ {0} s (not used as a value)',
     '実測上限 ≤ {0}秒（数値としては使わない）'),
    # retry 2026-10-14: step-table columns, Hotori's clock in custom cycles
    ('冷却', '쿨타임', 'Cooldown', 'クールタイム'),
    ('额外获得 +{0:g}', '추가 획득 +{0:g}', 'Extra gain +{0:g}', '追加獲得 +{0:g}'),
    ('等待时计 {0:.1f} 秒后使用', '시계 {0:.1f}초 대기 후 사용', 'Used after a {0:.1f} s clock wait',
     '時計を {0:.1f}秒待ってから使用'),
    ('时计不足（{0:.0f}/{1:.0f}，还差 {2:.1f} 秒）', '시계 부족 ({0:.0f}/{1:.0f}, {2:.1f}초 모자람)',
     'Clock short ({0:.0f}/{1:.0f}, {2:.1f} s left)', '時計不足（{0:.0f}/{1:.0f}、残り {2:.1f}秒）'),
    ('{0}：「{1}」上限 {2:g}，每秒 +{3:g}，变轨技能消耗 {4:g}，极轨终结需蓄满（游戏数据；检查方式为插入等待或严格时等待蓄满）',
     '{0}: 「{1}」 상한 {2:g}, 초당 +{3:g}, 바이레일 스킬 소모 {4:g}, 울티메이트는 가득 차야 사용 '
     '(게임 데이터, 검사 방식이 대기 삽입·엄격이면 가득 찰 때까지 대기)',
     '{0}: "{1}" cap {2:g}, +{3:g} per second, Skill costs {4:g}, Ultimate needs it full '
     '(game data; the Insert wait / Strict checks wait until it is full)',
     '{0}：「{1}」上限 {2:g}、毎秒 +{3:g}、スキル消費 {4:g}、アルティメットは満タンが必要'
     '（ゲームデータ。チェック方法が待機を挿入・厳格なら満タンまで待機）'),
    ('{0} 的 {1} 冷却 {2} 秒长于录像中两次使用之间扣除时停后的 {3} 秒（冷却是否在时停中计时、或被效果重置，尚未确认）',
     '{0}의 {1} 쿨타임 {2}초가 녹화에서 두 번 사용한 사이의 시간 정지를 뺀 {3}초보다 김 '
     '(쿨타임이 시간 정지 중에도 흐르는지, 효과로 초기화되는지 미확인)',
     "{0}'s {1} cooldown of {2} s is longer than the {3} s of battle time (Time Stops excluded) between two uses in "
     "the recordings (whether the cooldown runs during Time Stops or an effect resets it is unconfirmed)",
     '{0}の{1}のクールタイム {2}秒は、録画で2回使用した間の時間停止を除いた {3}秒より長い'
     '（クールタイムが時間停止中も進むのか、効果でリセットされるのかは未確認）'),
    ('{0}：「{1}」上限 {2:g}（每次获得量的单位未确认，只显示不检查）',
     '{0}: 「{1}」 상한 {2:g} (획득량 단위가 확인되지 않아 표시만 하고 검사하지 않음)',
     '{0}: "{1}" cap {2:g} (the unit of each gain is unconfirmed: shown, not checked)',
     '{0}：「{1}」上限 {2:g}（獲得量の単位が未確認のため表示のみ、判定しない）'),
    # fix phase 2026-10-14 (reviews numbers / logic-regression / ux-i18n, validation F1 / F2 / F7)
    ('{0} 等待「{1}」蓄满共约 {2:.1f} 秒（每次出场 {3} 秒；视为队友行动的时间，未计入时间轴）',
     '{0}이(가) 「{1}」이(가) 가득 찰 때까지 총 약 {2:.1f}초 대기 (출전마다 {3}초, 동료 행동 시간으로 간주해 타임라인에 넣지 않음)',
     '{0} waits about {2:.1f} s in total for "{1}" to fill ({3} s per visit; counted as teammates\' time, not added to '
     'the timeline)',
     '{0}は「{1}」が満タンになるまで合計約 {2:.1f}秒待機（出場ごとに {3}秒。味方の行動時間とみなし、タイムラインには加えない）'),
    ('冷却与能量的默认数值来自：{0}', '쿨타임·에너지 기본값 출처: {0}', 'Default cooldown / energy numbers from: {0}',
     'クールタイム・エネルギーの既定値の出典：{0}'),
    ('盈蓄给场上队员的终结能量已计入显示的能量（共 +{0}，{1} 次；不参与能量检查）',
     '차지가 필드의 팀원에게 주는 울티메이트 에너지를 표시 에너지에 포함 (총 +{0}, {1}회, 에너지 검사에는 쓰지 않음)',
     'Ultimate Energy that Charge gives the member on the field is included in the energy shown (+{0} in total, {1} '
     'times; not used by the energy check)',
     '盈蓄がフィールドのメンバーに与えるアルティメットエネルギーを表示エネルギーに含める（合計 +{0}、{1}回。エネルギーチェックには使わない）'),
    ('{0} 的冷却规则按觉醒与技能数据计算：{1}', '{0}의 쿨타임 규칙을 각성·스킬 데이터대로 계산: {1}',
     "{0}'s cooldown rules from awakening and skill data: {1}", '{0}のクールタイム規則を覚醒・スキルデータで計算：{1}'),
    ('{0} 没有终结能量与冷却数据：不检查冷却与能量，环合值按固定规则补满',
     '{0}은(는) 울티메이트 에너지·쿨타임 데이터가 없음: 쿨타임과 에너지를 검사하지 않고, 사이클 수치는 고정 규칙으로 보충',
     '{0} has no Ultimate Energy / cooldown data: cooldowns and energy are not checked, its Cycle Value follows the '
     'fixed refill rule',
     '{0}にはアルティメットエネルギー・クールタイムのデータがない：クールタイムとエネルギーをチェックせず、サイクル値は固定ルールで補充'),
    ('{0} 的变轨技能有 {3} 次命中（召唤物等）未排入时间轴：每次使用补计终结能量 {1} 与环合值 {2}（{4}；伤害未计入）',
     '{0}의 바이레일 스킬은 타격 {3}회(소환물 등)가 타임라인에 배치되지 않음: 사용할 때마다 울티메이트 에너지 {1}, 사이클 수치 {2}를 '
     '보충 계산 ({4}, 피해는 미포함)',
     "{0}'s Skill has {3} hits (summons etc.) that are not laid out on the timeline: each use adds {1} Ultimate Energy "
     "and {2} Cycle Value ({4}; their damage is not included)",
     '{0}のスキルは {3}ヒット（召喚物など）がタイムラインに配置されない：使用ごとにアルティメットエネルギー {1}、サイクル値 {2} を'
     '補って計算（{4}、ダメージは含まない）'),
    ('{0} 的变轨技能有一段命中未排入时间轴且次数未知：其终结能量与环合值未计入（结果偏低）',
     '{0}의 바이레일 스킬 일부 타격이 타임라인에 배치되지 않고 횟수도 알 수 없음: 그 울티메이트 에너지와 사이클 수치는 미포함 '
     '(결과가 낮게 나옴)',
     "Part of {0}'s Skill hits are not laid out on the timeline and their count is unknown: their Ultimate Energy "
     "and Cycle Value are not included (results are low)",
     '{0}のスキルの一部ヒットはタイムラインに配置されず回数も不明：そのアルティメットエネルギーとサイクル値は含まない（結果は低め）'),
    ('{0}、{1}', '{0}, {1}', '{0}, {1}', '{0}、{1}'),
    ('旧版直接输入数值表', '이전 직접 입력 수치표', 'Old custom-input table', '旧版の直接入力数値表'),
    ('极轨终结刷新变轨技能冷却', '울티메이트가 바이레일 스킬 쿨타임 초기화', 'Ultimate refreshes the Skill cooldown',
     'アルティメットでスキルのクールタイムをリセット'),
    ('极限反击刷新变轨技能冷却', '극한 반격이 바이레일 스킬 쿨타임 초기화', 'Extreme Counter refreshes the Skill cooldown',
     '極限カウンターでスキルのクールタイムをリセット'),
    ('5 次普通攻击后可额外使用一次变轨技能', '일반 공격 5회 후 바이레일 스킬 1회 추가 사용',
     'One extra Skill after 5 Basic Attacks', '通常攻撃5回の後にスキルを1回追加使用'),
    ('觉醒缩短变轨技能冷却', '각성으로 바이레일 스킬 쿨타임 단축', 'Awakening shortens the Skill cooldown',
     '覚醒でスキルのクールタイム短縮'),
    ('冷却从技能生效时开始计算', '쿨타임은 스킬이 발동한 시점부터 계산', 'The cooldown starts when the skill takes effect',
     'クールタイムはスキル発動時点から計算'),
    ('资源模型决定检查哪些数值：\n· 游戏数据 + 社区冷却（默认）：游戏数据，加上社区资料（prydwen）的变轨技能与极轨终结冷却\n'
     '· 游戏数据：只用游戏数据（卡厄斯的极轨终结冷却、浔的时计等）\n· 旧规则：不检查冷却与能量，第 1、3 轮开始时环合值补满 100\n'
     '缺少数据的队员在结果说明中标出，不检查',
     '자원 모델은 어떤 수치를 검사할지 정합니다:\n· 게임 데이터 + 커뮤니티 쿨타임(기본): 게임 데이터에 커뮤니티 자료(prydwen)의 '
     '바이레일 스킬·울티메이트 쿨타임을 더함\n· 게임 데이터: 게임 데이터만 사용 (카오스의 울티메이트 쿨타임, 호토리의 시계 등)\n'
     '· 기존 규칙: 쿨타임과 에너지를 검사하지 않고, 1·3바퀴 시작 시 사이클 수치를 100으로 보충\n'
     '데이터가 없는 팀원은 결과 설명에 표시하고 검사하지 않음',
     'The resource model decides which numbers are checked:\n· Game data + community cooldowns (default): game data '
     'plus the community (prydwen) Skill and Ultimate cooldowns\n· Game data: game data only (Chaos\'s Ultimate '
     'cooldown, Xun\'s clock, ...)\n· Old rule: no cooldown or energy check; every Cycle Value is refilled to 100 at '
     'the start of loops 1 and 3\nMembers without data are marked in the result\'s explanation and not checked',
     'リソースモデルはどの数値をチェックするかを決めます：\n· ゲームデータ + コミュニティのクールタイム（既定）：ゲームデータに'
     'コミュニティ資料（prydwen）のスキル・アルティメットのクールタイムを加える\n· ゲームデータ：ゲームデータのみ（カオスの'
     'アルティメットのクールタイム、潯の時計など）\n· 旧ルール：クールタイムとエネルギーをチェックせず、1・3周目の開始時に'
     'サイクル値を100に補充\nデータのないメンバーは結果の説明に表示し、チェックしない'),
    ('- 冷却时间与极轨终结能量：只按游戏数据检查；缺少数据的队员在说明中标出（不检查）',
     '- 쿨타임과 울티메이트 에너지: 게임 데이터로만 검사, 데이터가 없는 팀원은 설명에 표시 (검사 안 함)',
     '- Cooldowns and Ultimate Energy: checked with game data only; members without data are marked in the '
     'explanation (not checked)',
     '- クールタイムとアルティメットエネルギー：ゲームデータのみでチェック。データのないメンバーは説明に表示（チェックしない）'),
    ('- 冷却时间与极轨终结能量：按游戏数据检查（默认含社区冷却）；缺少数据的队员在说明中标出（不检查）',
     '- 쿨타임과 울티메이트 에너지: 게임 데이터로 검사 (기본값은 커뮤니티 쿨타임 포함), 데이터가 없는 팀원은 설명에 표시 (검사 안 함)',
     '- Cooldowns and Ultimate Energy: checked with game data (community cooldowns included by default); members '
     'without data are marked in the explanation (not checked)',
     '- クールタイムとアルティメットエネルギー：ゲームデータでチェック（既定でコミュニティのクールタイムを含む）。'
     'データのないメンバーは説明に表示（チェックしない）'),
    ('冷却未检查', '쿨타임 미검사', 'Cooldown not checked', 'クールタイム未チェック'),
    ('未检查', '미검사', 'Not checked', '未チェック'),
    ('（只显示不检查）', '(표시만, 검사 안 함)', '(shown, not checked)', '（表示のみ、チェックしない）'),
    ('极轨终结能量', '울티메이트 에너지', 'Ultimate Energy', 'アルティメットエネルギー'),
    ('终结能量获得 +{0:.0f}（消耗未知）', '울티메이트 에너지 획득 +{0:.0f} (소모량 미상)',
     'Ultimate Energy gained +{0:.0f} (cost unknown)', 'アルティメットエネルギー獲得 +{0:.0f}（消費量不明）'),
    ('时计补足 {0:.1f} 秒', '시계 보충 {0:.1f}초', 'Clock credited {0:.1f} s', '時計補充 {0:.1f}秒'),
    ('每次出场 {0} 秒；视为队友行动的时间，未计入时间轴', '출전마다 {0}초, 동료 행동 시간으로 간주해 타임라인에 넣지 않음',
     "{0} s per visit; counted as teammates' time, not added to the timeline",
     '出場ごとに {0}秒。味方の行動時間とみなし、タイムラインには加えない'),
    ('援护技与极限反击：游戏数据中没有冷却设定（全体队员）', '서포트 스킬과 극한 반격: 게임 데이터에 쿨타임 설정 없음 (팀원 전원)',
     'Support Skill and Extreme Counter: no cooldown setting in the game data (all members)',
     '支援スキルと極限カウンター：ゲームデータにクールタイム設定なし（メンバー全員）'),
    ('留空：插入等待不限时，严格最多 60 秒；仅对插入等待/严格有效',
     '비워 두면: 대기 삽입은 제한 없음, 엄격은 최대 60초. 대기 삽입·엄격에서만 적용',
     'Blank: Insert wait has no limit, Strict waits at most 60 s; used only by Insert wait / Strict',
     '空欄：待機を挿入は無制限、厳格は最大60秒。待機を挿入・厳格でのみ有効'),
]

# user decision D3 (2026-10-14): a team member whose skill is not ready swaps out at once; alone it waits
ROWS_SWAP = [
    ('技能未就绪（冷却未结束，或已知消耗的终结能量不足）时立即切换到下一名队员：本次出场剩余步骤不执行，援护技登场按通常规则判定；所有队员都未就绪时等待最早就绪的队员',
     '스킬이 준비되지 않으면(쿨타임 미완료, 또는 소모량을 아는 울티메이트 에너지 부족) 즉시 다음 팀원으로 교체: 이번 출전의 남은 '
     '단계는 실행하지 않고 서포트 스킬 입장은 평소 규칙대로 판정하며, 모든 팀원이 준비되지 않았으면 가장 먼저 준비되는 팀원을 기다림',
     'A skill that is not ready (cooldown running, or a known Ultimate cost the energy cannot pay) swaps to the next '
     'member at once: the rest of the visit is not run and the Support Skill entry follows the usual rule; when no '
     'member is ready, the simulator waits for the one ready first',
     'スキルが準備できていない（クールタイム中、または消費量が判明しているアルティメットのエネルギー不足）ときはすぐ次のメンバーに'
     '交代：この出場の残りのステップは実行せず、支援スキルでの登場は通常のルールどおり。全員が準備できていないときは最も早く準備'
     'できるメンバーを待機'),
    ('单人没有可切换的队员：技能未就绪时原地等待（等待期间不攻击）',
     '혼자라 교체할 팀원이 없음: 스킬이 준비되지 않으면 제자리에서 기다림 (기다리는 동안 공격하지 않음)',
     'Solo, there is no member to swap to: a skill that is not ready is waited for in place (no attacks while waiting)',
     '単独のため交代できるメンバーがいない：スキルが準備できていなければその場で待機（待機中は攻撃しない）'),
    ('{0} 因技能未就绪提前切换 {1} 次（共 {2} 个步骤未执行）',
     '{0}: 스킬 미준비로 즉시 교체 {1}회 (실행하지 않은 단계 총 {2}개)',
     '{0}: early swaps (skill not ready): {1}; steps not run: {2}',
     '{0}はスキル未準備のため早めに交代 {1}回（実行しなかったステップ 計{2}個）'),
    ('{0} 因技能未就绪提前切换 {1} 次', '{0}: 스킬 미준비로 즉시 교체 {1}회',
     '{0}: early swaps (skill not ready): {1}', '{0}はスキル未準備のため早めに交代 {1}回'),
    ('所有队员的技能都未就绪：{0} 原地等待 {1:.1f} 秒（{2} 最早就绪）',
     '모든 팀원의 스킬 미준비: {0} 제자리 대기 {1:.1f}초 (가장 먼저 준비: {2})',
     'No member had a skill ready: {0} waited {1:.1f} s in place ({2} was ready first)',
     '全員のスキルが準備できていない：{0}がその場で {1:.1f}秒待機（{2}が最も早く準備完了）'),
    ('终结能量不足（{0:.0f}/{1:.0f}）→ 立即切换', '울티메이트 에너지 부족 ({0:.0f}/{1:.0f}) → 즉시 교체',
     'Not enough Ultimate Energy ({0:.0f}/{1:.0f}) → swap out at once', 'アルティメットエネルギー不足（{0:.0f}/{1:.0f}）→ すぐ交代'),
    ('时计不足（还差 {0:.1f} 秒）→ 立即切换', '시계 부족 ({0:.1f}초 남음) → 즉시 교체',
     'Clock not full ({0:.1f} s left) → swap out at once', '時計不足（残り {0:.1f}秒）→ すぐ交代'),
    ('冷却未就绪（{0}，还差 {1:.1f} 秒）→ 立即切换', '쿨타임 미완료 ({0}, {1:.1f}초 남음) → 즉시 교체',
     'Cooldown not ready ({0}, {1:.1f} s left) → swap out at once', 'クールタイム中（{0}、残り {1:.1f}秒）→ すぐ交代'),
    ('本次出场其余 {0} 个步骤未执行', '이번 출전의 나머지 {0}단계는 실행하지 않음',
     'Other steps of this visit not run: {0}', 'この出場の残り {0}ステップは実行しない'),
    ('未就绪，立即切换', '미준비, 즉시 교체', 'Not ready, swapped out at once', '未準備のためすぐ交代'),
    ('已提前切换，未执行', '이미 교체되어 실행 안 함', 'Already swapped out, not run', '交代済みのため未実行'),
    ('所有队员都未就绪：等待 {0:.1f} 秒（{1} 最早就绪）', '모든 팀원 미준비: {0:.1f}초 대기 (가장 먼저 준비: {1})',
     'No member ready: waited {0:.1f} s ({1} ready first)', '全員が準備できていない：{0:.1f}秒待機（{1}が最も早く準備完了）'),
    ('立即切换', '즉시 교체', 'Swapped out', 'すぐ交代'),
    ('提前切换 {0} 次', '즉시 교체 {0}회', 'Early swaps {0}', '早め交代 {0}回'),
    ('- 技能未就绪（冷却未结束，或已知消耗的终结能量不足）时立即切换到下一名队员；单人时原地等待',
     '- 스킬이 준비되지 않으면(쿨타임 미완료, 또는 소모량을 아는 울티메이트 에너지 부족) 즉시 다음 팀원으로 교체, 혼자일 때는 '
     '제자리에서 대기',
     '- A skill that is not ready (cooldown running, or a known Ultimate cost not covered) swaps to the next member at '
     'once; solo, it is waited for in place',
     '- スキルが準備できていない（クールタイム中、または消費量が判明しているアルティメットのエネルギー不足）ときはすぐ次のメンバー'
     'に交代。単独ならその場で待機'),
    ('严格（未就绪时立即切换；单人时等待）', '엄격 (준비 안 되면 즉시 교체, 혼자면 대기)',
     'Strict (swap out when not ready; wait when solo)', '厳格（未準備ならすぐ交代、単独なら待機）'),
    ('{0}：「{1}」上限 {2:g}，每秒 +{3:g}，变轨技能消耗 {4:g}，极轨终结需蓄满（游戏数据；插入等待时等待蓄满；严格时与冷却相同：队伍中立即切换，单人时等待）',
     '{0}: 「{1}」 상한 {2:g}, 초당 +{3:g}, 바이레일 스킬 소모 {4:g}, 울티메이트는 가득 차야 사용 (게임 데이터, 대기 삽입이면 '
     '가득 찰 때까지 대기, 엄격이면 쿨타임과 같이 팀에서는 즉시 교체·혼자면 대기)',
     '{0}: "{1}" cap {2:g}, +{3:g} per second, Skill costs {4:g}, Ultimate needs it full (game data; Insert wait '
     'waits until it is full; Strict treats it like a cooldown: swap out in a team, wait when solo)',
     '{0}：「{1}」上限 {2:g}、毎秒 +{3:g}、スキル消費 {4:g}、アルティメットは満タンが必要（ゲームデータ。待機を挿入なら満タン'
     'まで待機、厳格ならクールタイムと同じくチームではすぐ交代・単独なら待機）'),
    ('严格检查：技能未就绪或终结能量不足时立即切换到后面输入的下一名队员（{0} 次），该队员这一段其余输入不执行；后面没有其他队员或所有队员都未就绪时等待冷却（共 {1:.1f} 秒），终结能量不足时跳过（{2} 次），超过最长等待时跳过（{3} 次）',
     '엄격 검사: 스킬이 준비되지 않거나 울티메이트 에너지가 부족하면 뒤에 입력한 다음 팀원으로 즉시 교체 ({0}회), 그 팀원의 이번 '
     '구간 나머지 입력은 실행하지 않음. 뒤에 다른 팀원이 없거나 모든 팀원이 준비되지 않았으면 쿨타임 대기 (총 {1:.1f}초), '
     '울티메이트 에너지 부족 시 건너뜀 ({2}회), 최대 대기 시간 초과 시 건너뜀 ({3}회)',
     "Strict check: a skill that is not ready, or an Ultimate without enough Ultimate Energy, swaps to the next "
     "member typed after it at once ({0}×); that member's other inputs of this stretch are not run. With no member "
     "typed after it, or when no member is ready, cooldowns are waited for ({1:.1f} s in total), Ultimates without "
     "enough energy are skipped ({2}×) and waits beyond the longest wait are skipped ({3}×)",
     '厳格チェック：スキルが準備できていない、またはアルティメットエネルギー不足のときは後に入力した次のメンバーにすぐ交代（{0}回）、'
     'そのメンバーのこの区間の残りの入力は実行しない。後に他のメンバーがいない、または全員が準備できていないときはクールタイムを'
     '待機（合計 {1:.1f}秒）、エネルギー不足のアルティメットはスキップ（{2}回）、最長待機を超えるとスキップ（{3}回）'),
    # user decision 2026-10-18: a cooldown with less than SWAP_MIN_WAIT_S (0.3 s) of battle time left is waited for
    ('技能未就绪（冷却未结束，或已知消耗的终结能量不足）时立即切换到下一名队员：本次出场剩余步骤不执行，援护技登场按通常规则判定；冷却还差不到 {0:.1f} 秒（战斗时间）时原地等待后使用；所有队员都未就绪时等待最早就绪的队员',
     '스킬이 준비되지 않으면(쿨타임 미완료, 또는 소모량을 아는 울티메이트 에너지 부족) 즉시 다음 팀원으로 교체: 이번 출전의 남은 '
     '단계는 실행하지 않고 서포트 스킬 입장은 평소 규칙대로 판정하며, 쿨타임이 {0:.1f}초(전투 시간) 미만 남았으면 제자리에서 '
     '기다렸다 사용하고, 모든 팀원이 준비되지 않았으면 가장 먼저 준비되는 팀원을 기다림',
     'A skill that is not ready (cooldown running, or a known Ultimate cost the energy cannot pay) swaps to the next '
     'member at once: the rest of the visit is not run and the Support Skill entry follows the usual rule; a cooldown '
     'with less than {0:.1f} s (battle time) left is waited for in place and the skill used; when no member is ready, '
     'the simulator waits for the one ready first',
     'スキルが準備できていない（クールタイム中、または消費量が判明しているアルティメットのエネルギー不足）ときはすぐ次のメンバーに'
     '交代：この出場の残りのステップは実行せず、支援スキルでの登場は通常のルールどおり。クールタイムの残りが {0:.1f}秒（戦闘時間）'
     '未満ならその場で待ってから使用。全員が準備できていないときは最も早く準備できるメンバーを待機'),
    ('{0} 冷却还差不到 {3:.1f} 秒时原地等待后使用：{1} 次，共 {2:.2f} 秒',
     '{0}: 쿨타임이 {3:.1f}초 미만 남아 기다렸다 사용 {1}회 (총 {2:.2f}초)',
     '{0}: waited for a cooldown with less than {3:.1f} s left, then used the skill: {1}× ({2:.2f} s in total)',
     '{0}：クールタイム残り {3:.1f}秒未満のため待ってから使用 {1}回（計 {2:.2f}秒）'),
    ('等待冷却 {0:.2f} 秒（< {1:.1f} 秒，不切换；{2}）', '쿨타임 {0:.2f}초 대기 (< {1:.1f}초, 교체 안 함 · {2})',
     'Waited {0:.2f} s for the cooldown (< {1:.1f} s, no swap; {2})', 'クールタイム {0:.2f}秒待機（< {1:.1f}秒、交代しない・{2}）'),
    ('等待冷却 {0:.2f} 秒后使用（< {1:.1f} 秒，不切换）', '쿨타임 {0:.2f}초 대기 후 사용 (< {1:.1f}초, 교체 안 함)',
     'Waited {0:.2f} s for the cooldown, then used (< {1:.1f} s, no swap)',
     'クールタイム {0:.2f}秒待機してから使用（< {1:.1f}秒、交代しない）'),
    ('- 技能未就绪（冷却未结束，或已知消耗的终结能量不足）时立即切换到下一名队员（冷却还差不到 {0:.1f} 秒时等待后使用）；单人时原地等待',
     '- 스킬이 준비되지 않으면(쿨타임 미완료, 또는 소모량을 아는 울티메이트 에너지 부족) 즉시 다음 팀원으로 교체(쿨타임이 '
     '{0:.1f}초 미만 남았으면 기다렸다 사용), 혼자일 때는 제자리에서 대기',
     '- A skill that is not ready (cooldown running, or a known Ultimate cost not covered) swaps to the next member at '
     'once (a cooldown with less than {0:.1f} s left is waited for); solo, it is waited for in place',
     '- スキルが準備できていない（クールタイム中、または消費量が判明しているアルティメットのエネルギー不足）ときはすぐ次のメンバー'
     'に交代（クールタイム残り {0:.1f}秒未満なら待ってから使用）。単独ならその場で待機'),
    ('严格检查：技能未就绪或终结能量不足时立即切换到后面输入的下一名队员（{0} 次），该队员这一段其余输入不执行；冷却还差不到 {4:.1f} 秒、后面没有其他队员或所有队员都未就绪时等待冷却（共 {1:.1f} 秒），终结能量不足时跳过（{2} 次），超过最长等待时跳过（{3} 次）',
     '엄격 검사: 스킬이 준비되지 않거나 울티메이트 에너지가 부족하면 뒤에 입력한 다음 팀원으로 즉시 교체 ({0}회), 그 팀원의 이번 '
     '구간 나머지 입력은 실행하지 않음. 쿨타임이 {4:.1f}초 미만 남았거나, 뒤에 다른 팀원이 없거나, 모든 팀원이 준비되지 '
     '않았으면 쿨타임 대기 (총 {1:.1f}초), 울티메이트 에너지 부족 시 건너뜀 ({2}회), 최대 대기 시간 초과 시 건너뜀 ({3}회)',
     "Strict check: a skill that is not ready, or an Ultimate without enough Ultimate Energy, swaps to the next "
     "member typed after it at once ({0}×); that member's other inputs of this stretch are not run. With less than "
     "{4:.1f} s of cooldown left, with no member typed after it, or when no member is ready, cooldowns are waited for "
     "({1:.1f} s in total), Ultimates without enough energy are skipped ({2}×) and waits beyond the longest wait are "
     "skipped ({3}×)",
     '厳格チェック：スキルが準備できていない、またはアルティメットエネルギー不足のときは後に入力した次のメンバーにすぐ交代（{0}回）、'
     'そのメンバーのこの区間の残りの入力は実行しない。クールタイム残りが {4:.1f}秒未満、後に他のメンバーがいない、または全員が'
     '準備できていないときはクールタイムを待機（合計 {1:.1f}秒）、エネルギー不足のアルティメットはスキップ（{2}回）、最長待機を'
     '超えるとスキップ（{3}回）'),
]
ROWS += ROWS_SWAP


def fields(text: str) -> list:
    return sorted((f[1], f[2]) for f in string.Formatter().parse(text) if f[1] is not None)


def main() -> int:
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    keys = [r[0] for r in ROWS]
    if len(keys) != len(set(keys)):
        raise SystemExit("duplicate key")
    for i, lang in enumerate(("ko", "en", "ja"), 1):
        table = {}
        for row in ROWS:
            key, text = row[0], row[i]
            if lang == "ja":            # review F-UX3: "check" is チェック everywhere (custom panel: チェック方法)
                text = text.replace("判定", "チェック")
            if fields(key) != fields(text):
                raise SystemExit(f"{lang}: format fields differ: {key!r} -> {text!r}")
            table[key] = text
        (out / f"i18n_{lang}.json").write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ROWS)} keys x 3 languages -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
