# 커뮤니티(유저) 기준 캐릭터 운용 메모: 추천 조합과 딜 사이클. 계산에는 쓰이지 않는 참고 정보입니다 (Global 2.3.7).
"""Player-reported team compositions and rotations per character (Global 2.3.7).

Game names and numbers come from the official client data; the entries here are what Korean players report in
community posts and comments (arca.live, DCinside, Ruliweb, player blogs).  They are deliberately not the official
recommendation, not staff-written summaries and never based on YouTube or other videos.  Every entry lists the posts it
draws on in "sources"; the count shown in the app is the number of those links (source_line), and hovering an entry
lists them.  Shown on the character profile in the Korean UI only; no calculation reads them.  Qt-free data.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

A = "https://arca.live/b/nevernesstoeverness/"
D = "https://gall.dcinside.com/mgallery/board/view/?id=nevernesstoeverness&no="
DM = "https://gall.dcinside.com/mini/board/view/?id=nevernesstoeverness1&no="
R = "https://bbs.ruliweb.com/community/board/300143/read/"

# Each source was opened and checked on 2026-11-11: a player's own post or comment, not an arca channel manager's
# summary, not a relay of CN-community posts, not built from a video (for a post that attaches the author's own clip
# only its text counts), naming this exact team (all four) or rotation.  A post that also disagrees is listed only when
# the note states its point (comments marked "의견").
GUIDES: dict[int, dict[str, Any]] = {
    1090: {     # 엘림 (KR launch day 2026-11-11; Korean players' CN-server posts from 2026-11-05 included)
        "checked": "2026-11-11",
        "teams": (
            {"members": ("신쿠", "아카네 린", "엘림", "일로이"),
             "note": "신쿠 메인딜 차지(빛) 파티(신아엘일). 아카네 린은 Q·E로 레모라만 깔고 교대해서 육성을 많이 하지 않아도 "
                     "된다는 평이고, 일로이는 블라썸·회복, 엘림은 빛 버프와 울티메이트 후 추가 공격을 맡습니다. 한국 서버 "
                     "출시일에 이 파티로 연회를 돌리거나 사이클을 익혔다는 글이 여럿 있습니다. 다만 아카네 린까지 요구해 "
                     "부담이 크고 아카네 린 파티보다 약하다는 의견(신쿠·엘림 돌파가 있어야 비슷하다는 계산 포함)과, 잡몹전은 "
                     "돌파 없이는 불편하다는 평도 있습니다.",
             "sources": (A + "188739603", A + "188742840", R + "77348588", D + "388308", D + "388064",
                         A + "188760556", A + "188471292", R + "77348988", D + "386570", D + "386858",
                         A + "188731460",       # 의견: 돌파가 있어야 아카네 린 파티와 비슷
                         DM + "8373")},         # 의견: 아카네 린까지 요구하는 게 과하고 아카네 린 파티보다 약함
            {"members": ("아카네 린", "레이븐", "엘림", "일로이"),
             "note": "아카네 린 메인딜 스테인·차지 파티(아레엘일). 기존 사키리·하니엘·제로 자리에 엘림을 넣으면 아카네 린이 "
                     "건 레모라를 한 번 더 걸고, 울티메이트로 파티 공격력·추가 공격 피해를 올리며 필드 밖에서 「추억」으로 "
                     "추가 공격합니다. 일로이는 블라썸·회복을 맡습니다. 쉽고 잡몹전에도 안정적이라는 평, 하니엘·사키리보다 "
                     "사이클이 매끄러웠다는 연회 후기, 레모라로 보스가 계속 느려져 편하다는 후기가 있습니다. 반면 일로이 대신 "
                     "사키리·링코·호토리를 넣자는 의견, 풀돌파나 저항 제약이 없는 조건에서는 엘림 없는 아레호일·아레사링이 "
                     "더 빠르거나 고점이 높다는 의견, 엘림 전용 무기가 빛속성 전용이라 빛 딜러 파티보다 효과가 덜하다며 "
                     "추천하지 않는 의견도 있습니다.",
             "sources": (D + "388705", A + "188746490", "https://meryll.tistory.com/62", A + "188760556",
                         A + "188731460", R + "77348988", D + "388440",
                         A + "188759493",       # + 의견: 일로이 자리에 호토리
                         A + "188719266",       # + 의견: 일로이 자리에 링코·사키리, 아카네 린 고돌파면 호토리
                         D + "387425",          # + 의견: 딜을 원하면 일로이 대신 사키리
                         D + "385295",          # + 의견: 풀돌파면 아레호일이 가장 빠름
                         A + "188471292",       # 레모라로 보스가 느려져 편함 + 의견: 저항 제약이 없으면 아레사링 고점이 더 높음
                         D + "388638")},        # + 의견: 전용 무기가 빛속성 전용, 추천하지 않음
            {"members": ("신쿠", "하토르", "엘림", "일로이"),
             "note": "아카네 린 대신 하토르가 레모라를 거는 신쿠 파티(신하엘일). 아카네 린을 다른 파티(아레사링 등)에 쓸 때의 "
                     "대안으로 추천됩니다. 다만 중국 서버에서 하토르의 레모라 유지에 문제가 있었다며 고쳐지기 전까지는 "
                     "아카네 린을 쓰라는 가이드 의견과, 하토르로 쓰니 약했다는 후기도 있습니다.",
             "sources": (A + "188207051", A + "188199870", A + "188471292", A + "188761863", D + "388033",
                         D + "385924",
                         A + "188739283",       # 의견: 레모라 유지 문제가 고쳐지기 전에는 아카네 린
                         DM + "8373")},         # 의견: 하토르로 쓰니 약함
        ),
        "rotations": (
            {"label": "기본 (명함~2돌, 유저 표기 EE평평평EQ)",
             "steps": ("바이레일 스킬 「떠나간 사람들」", "「비연속적 존재」(약한 → 보통 신호)",
                       "일반 공격 「채널 오류」 3단", "「너에게 안녕」(보통 → 강한 신호)",
                       "울티메이트 「어제와 같은 풍경」", "교대"),
             "condition": "강한 신호에서 울티메이트를 써야 울티메이트와 협동 공격 「추억」 배율이 높습니다. "
                          "교대 후 「추억」이 필드 밖에서 자동으로 이어집니다. E / E+평평평 / E+Q를 교대 사이사이에 나눠 "
                          "넣고 평평평은 퀵스왑으로 끊는 운용도 있습니다.",
             "sources": (A + "188739804", A + "188742335", D + "388704", D + "388705", A + "188760556",
                         A + "188199870", D + "384967",
                         A + "188742840")},     # 교대 사이사이에 나눠 넣고 평평평 퀵스왑
            {"label": "3돌(공명 Lv.3) 이상 (유저 표기 EEEQ)",
             "steps": ("「떠나간 사람들」", "「비연속적 존재」", "「너에게 안녕」",
                       "울티메이트 「어제와 같은 풍경」", "교대"),
             "condition": "공명 「나의 오랜 친구, 잘 지냈어?」로 약한 신호에서 바로 강한 신호가 되어 평타 3단(예열)을 "
                          "생략합니다. 같은 순서로도 딜 편차가 크다는 질문이 있고, 한 3돌 유저는 첫 사이클만 평타 없이 되고 "
                          "두 번째 사이클부터는 평평평이 다시 필요했다고 보고했습니다.",
             "sources": (D + "388117", A + "188742840", A + "188760556",
                         A + "188746490",       # 딜 편차 질문
                         D + "388748")},        # 두 번째 사이클부터 평평평이 다시 필요했다는 보고
            {"label": "신쿠 차지 파티 반복 (신아엘일)",
             "steps": ("신쿠 QEEEEEQQQQ", "일로이 교대(블라썸)", "아카네 린 EQ", "신쿠 울티메이트 게이지 채우기",
                       "엘림 EE평평평EQ", "일로이 교대(블라썸) EQ"),
             "condition": "오프닝: 신쿠 사이클 채우기 → 아카네 린 교대(레모라) QE → 엘림 EE평평평EQ → 일로이 교대(블라썸) EQ. "
                          "신쿠·엘림을 돌파하거나 일로이 평꾹평을 섞으면 사이클이 짧아지고, 엘림 3돌이면 평평평을 뺍니다. "
                          "엘림 스킬을 교대 사이사이에 나눠 넣는 순서도 있지만 어렵다는 반응이 있습니다.",
             "sources": (A + "188760556",
                         A + "188742840")},     # 나눠 넣는 순서(댓글: 어렵다), 3돌이면 평평평 생략
            {"label": "아카네 스테인 차지 파티 반복 (아레엘일)",
             "steps": ("엘림 EE평평평EQ", "일로이 교대(블라썸) EQ", "레이븐 EQ", "아카네 린 QE → 평강화E 반복 → Q",
                       "레이븐 Q"),
             "condition": "오프닝: 일로이 QE → 엘림 EE평평평EQ → 아카네 린 교대(레모라) → 레이븐 EQ → "
                          "아카네 린 QE·평강화E 반복·Q → 레이븐 Q. 레이븐·아카네 린 퀵스왑은 필수가 아닙니다.",
             "sources": (A + "188760556",)},
        ),
    },
}


def guide_for(character_id: int) -> dict[str, Any] | None:
    """The community notes of one character (None when there are none)."""
    guide = GUIDES.get(int(character_id))
    if not guide or not (guide.get("teams") or guide.get("rotations")):
        return None
    return guide


# community name per host; the shown counts are derived from the cited links, never typed in by hand
_SITES: tuple[tuple[str, str], ...] = (
    ("arca.live", "아카라이브"),
    ("gall.dcinside.com", "디시인사이드"),
    ("bbs.ruliweb.com", "루리웹"),
    (".tistory.com", "블로그"),
)


_OTHER_SITE = "기타"


def site_of(url: str) -> str:
    """Community name of a source link ("기타" for an unlisted or unreadable link)."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except (TypeError, ValueError, AttributeError):
        return _OTHER_SITE
    for suffix, name in _SITES:
        if host == suffix or (suffix.startswith(".") and host.endswith(suffix)):
            return name
    return _OTHER_SITE


def sources_of(entry: dict[str, Any]) -> tuple[str, ...]:
    """The entry's links as a tuple of strings (a lone string, e.g. a one-link tuple missing its comma, counts once)."""
    raw = entry.get("sources") or ()
    if isinstance(raw, str):
        raw = (raw,)
    return tuple(url for url in raw if isinstance(url, str) and url)


def _site_counts(urls: Iterable[str]) -> dict[str, int]:
    counts = {name: 0 for _suffix, name in _SITES}
    counts[_OTHER_SITE] = 0
    for url in urls:
        counts[site_of(url)] += 1
    return {name: count for name, count in counts.items() if count}


def source_line(entry: dict[str, Any]) -> str:
    """'참고한 플레이어 글 N개 (site n · …)' for one team or rotation."""
    sources = sources_of(entry)
    parts = " · ".join(f"{name} {count}" for name, count in _site_counts(sources).items())
    return f"참고한 플레이어 글 {len(sources)}개 ({parts})" if sources else "참고한 플레이어 글 없음"


def source_tooltip(entry: dict[str, Any]) -> str:
    sources = sources_of(entry)
    return "참고한 글\n" + "\n".join(sources) if sources else ""


def footnote_for(guide: dict[str, Any]) -> str:
    entries = tuple(guide.get("teams") or ()) + tuple(guide.get("rotations") or ())
    sites = "·".join(_site_counts(url for entry in entries for url in sources_of(entry)))
    basis = f"{sites}에 유저가 쓴 글과 댓글 기준" if sites else "유저가 쓴 글과 댓글 기준"
    checked = f"({guide['checked']} 확인)" if guide.get("checked") else ""
    return (f"{basis}{checked}. 숫자는 항목마다 참고한 글 수이고, 항목에 마우스를 올리면 글 주소가 보입니다. "
            "공식 추천 조합·운영진 정리글과 유튜브 등 영상을 근거로 한 글은 뺐고, 본인 플레이 영상이 첨부된 글은 "
            "본문 내용만 참고했습니다. 계산에는 반영되지 않는 참고 정보입니다.")
