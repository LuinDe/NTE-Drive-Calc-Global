# 커뮤니티(유저) 기준 캐릭터 운용 메모: 추천 조합과 딜 사이클. 계산에는 쓰이지 않는 참고 정보입니다 (Global 2.3.7).
"""Player-reported team compositions and rotations per character (Global 2.3.7).

Game names and numbers come from the official client data; the entries here are what Korean players report in
community posts (arca.live, DCinside, Ruliweb, player blogs).  They are deliberately not the official recommendation,
not staff-written summaries and never come from video sites.  Counts are independent player sources (one author
counted once).  Shown on the character profile in the Korean UI only; no calculation reads them.  Qt-free data.
"""
from __future__ import annotations

from typing import Any

GUIDES: dict[int, dict[str, Any]] = {
    1090: {     # 엘림 · checked 2026-11-11 (KR launch day; CN-server posts from 2026-11-05 included)
        "teams": (
            {"members": ("신쿠", "아카네 린", "엘림", "일로이"),
             "note": "신쿠 메인딜 차지(빛) 파티(신아엘일). 아카네 린은 Q·E로 레모라만 깔고 교대하고, 일로이는 블라썸·회복, "
                     "엘림은 빛 버프와 울티메이트 후 추가 공격을 맡습니다. 한국 서버 출시일 실사용 보고가 가장 많습니다. "
                     "· 플레이어 출처 20곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188742840",
                         "https://arca.live/b/nevernesstoeverness/188739603",
                         "https://arca.live/b/nevernesstoeverness/188555067",
                         "https://arca.live/b/nevernesstoeverness/188471292",
                         "https://arca.live/b/nevernesstoeverness/188207195")},
            {"members": ("아카네 린", "레이븐", "엘림", "일로이"),
             "note": "아카네 린 메인딜 스테인·차지 파티(아레엘일). 기존 사키리·하니엘·제로 자리에 엘림이 들어가 레모라와 "
                     "빛 버프를 주고, 일로이가 블라썸·회복을 맡습니다. 레모라로 보스가 계속 느려져 편하다는 평이 많습니다. "
                     "· 플레이어 출처 15곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188746490",
                         "https://arca.live/b/nevernesstoeverness/188759493",
                         "https://gall.dcinside.com/mgallery/board/view/?id=nevernesstoeverness&no=388705",
                         "https://meryll.tistory.com/62")},
            {"members": ("신쿠", "하토르", "엘림", "일로이"),
             "note": "아카네 린 대신 하토르가 레모라를 거는 신쿠 파티(신하엘일). 아카네 린을 다른 파티에 쓸 때의 대안입니다. "
                     "엘림의 레모라 재부여(7.5초)가 시간 정지 중에도 흘러 하토르와 맞지 않는다는 보고가 있어, 수정 전에는 "
                     "아카네 린 쪽을 권하는 의견이 많습니다. · 플레이어 출처 10곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188207051",
                         "https://arca.live/b/nevernesstoeverness/188597642",
                         "https://arca.live/b/nevernesstoeverness/188761863",
                         "https://gall.dcinside.com/mini/board/view/?id=nevernesstoeverness1&no=8373")},
        ),
        "rotations": (
            {"label": "기본 (명함~2돌, 유저 표기 EE평평평EQ)",
             "steps": ("바이레일 스킬 「떠나간 사람들」", "「비연속적 존재」(약한 → 보통 신호)",
                       "일반 공격 「채널 오류」 3단", "「너에게 안녕」(보통 → 강한 신호)",
                       "울티메이트 「어제와 같은 풍경」", "교대"),
             "condition": "강한 신호에서 울티메이트를 써야 울티메이트와 협동 공격 「추억」 배율이 높습니다. "
                          "교대 후 「추억」이 필드 밖에서 자동으로 이어집니다. · 플레이어 출처 13곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188410059",
                         "https://arca.live/b/nevernesstoeverness/188739804",
                         "https://arca.live/b/nevernesstoeverness/188742335",
                         "https://arca.live/b/nevernesstoeverness/188760556")},
            {"label": "3돌(공명 Lv.3) 이상 (유저 표기 EEEQ)",
             "steps": ("「떠나간 사람들」", "「비연속적 존재」", "「너에게 안녕」",
                       "울티메이트 「어제와 같은 풍경」", "교대"),
             "condition": "공명 「나의 오랜 친구, 잘 지냈어?」로 약한 신호에서 바로 강한 신호가 되어 평타 3단을 생략합니다. "
                          "두 번째 사이클부터는 평타가 다시 필요했다는 보고도 있습니다. · 플레이어 출처 5곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188410059",
                         "https://arca.live/b/nevernesstoeverness/188746490",
                         "https://gall.dcinside.com/mgallery/board/view/?id=nevernesstoeverness&no=388748")},
            {"label": "신쿠 차지 파티 반복 (신아엘일)",
             "steps": ("신쿠 QEEEEEQQQQ", "일로이 교대(블라썸)", "아카네 린 EQ", "신쿠 울티메이트 게이지 채우기",
                       "엘림 EE평평평EQ", "일로이 교대(블라썸) EQ"),
             "condition": "오프닝: 신쿠 사이클 채우기 → 아카네 린 교대(레모라) QE → 엘림 EE평평평EQ → 일로이 교대(블라썸) EQ. "
                          "신쿠·엘림을 돌파하거나 일로이 평꾹평을 섞으면 사이클이 짧아지고, 엘림 3돌이면 평평평을 뺍니다. "
                          "· 플레이어 출처 2곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188760556",
                         "https://arca.live/b/nevernesstoeverness/188742840")},
            {"label": "아카네 스테인 차지 파티 반복 (아레엘일)",
             "steps": ("엘림 EE평평평EQ", "일로이 교대(블라썸) EQ", "레이븐 EQ", "아카네 린 QE → 평강화E 반복 → Q",
                       "레이븐 Q"),
             "condition": "오프닝: 일로이 QE → 엘림 EE평평평EQ → 아카네 린 교대(레모라) → 레이븐 EQ → "
                          "아카네 린 QE·평강화E 반복·Q → 레이븐 Q. 레이븐·아카네 린 퀵스왑은 필수가 아닙니다. "
                          "· 플레이어 출처 3곳",
             "sources": ("https://arca.live/b/nevernesstoeverness/188760556",
                         "https://arca.live/b/nevernesstoeverness/188410059")},
        ),
        "footnote": "아카라이브·디시인사이드·루리웹·플레이어 블로그의 유저 글 기준(2026-11-11 확인, 출처는 서로 다른 작성자 수). "
                    "공식 추천 조합·운영진 정리글·영상은 근거에서 제외했습니다. 계산에는 반영되지 않는 참고 정보입니다.",
    },
}


def guide_for(character_id: int) -> dict[str, Any] | None:
    """The community notes of one character (None when there are none)."""
    guide = GUIDES.get(int(character_id))
    if not guide or not (guide.get("teams") or guide.get("rotations")):
        return None
    return guide
