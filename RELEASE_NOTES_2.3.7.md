# NTE Drive Calc Global 2.3.7

## 한국어

원작자: **[hxwd94666](https://github.com/hxwd94666) · [NTE Drive Calc original project](https://github.com/hxwd94666/NTE-Drive-Calculator)** 및 NTE Drive Calc contributors. Global은 LuinDe가 독립 유지보수하는 비공식 다국어 파생 프로젝트입니다.

엘림이 2026년 11월 11일 1.5 「지금 거신 번호는」 업데이트로 한국 서버에 정식 출시되어, 중국 서버 기준이던 엘림 자료를 한국 서버 기준으로 바꿨습니다.

- **한국 서버 공식 텍스트:** 엘림의 스킬·각성·공명·패시브·아크 이름과 설명을 한국 서버 게임 텍스트(이환 데이터베이스 [nte.nanoka.cc](https://nte.nanoka.cc/)의 라이브 1.5.4 한국어 데이터)로 바꿨습니다. 예: 「일반 공격: 일시적 오류」, 「바이레일 스킬: 일렉트릭 드림즈」(떠나간 사람들·비연속적 존재·너에게 안녕), 「울티메이트: 어제와 같은 풍경」, 「서포트 스킬: 난 여기 있어」, 패시브 「릴레이 노드」·「유비무환」, 각성 「404 고립된 섬을 바라보며」, 공명 「나의 오랜 친구, 잘 지냈어?」, 아크 효과 「음성사서함 #재발신」. 중국어로 남아 있던 스킬 상세 설명과 스킬 레벨 항목도 모두 한국어로 표시됩니다.
- **육성 재료 이름:** 같은 데이터 기준으로 바꿨습니다. 비틀 코인, 폰즈, 라이징·베테랑·특급 헌터 가이드, 맨홀 갱스터·마스터·보스, 당근 동화·은화·금화, 아크 돌파 재료(사과씨·나선형 선율·리퀴드 드림·냉디저트·드라마 코어), 연한 염료 등.
- **커뮤니티 추천 조합·딜 사이클:** 엘림 캐릭터 도감의 프로필 탭에 유저들이 실제로 쓰는 파티 조합과 딜 사이클을 참고용으로 표시합니다(한국어 화면). 아카라이브·디시인사이드·루리웹·블로그에 유저가 쓴 글과 댓글을 기준으로 했고, 공식 추천·운영진 정리글과 유튜브 등 영상을 근거로 한 글은 뺐고, 본인 플레이 영상이 첨부된 글은 영상이 아닌 글과 댓글 내용만 참고했습니다. 항목마다 참고한 글 수가 표시되고, 항목에 마우스를 올리면 글 주소가 보입니다. 계산에는 반영되지 않습니다.
- **수치:** 한국 서버의 엘림 능력치(Lv.80 HP 15,392 · 공격력 660 · 방어력 909)와 「카트리지」 속성(Ⅲ형 특화: Ⅲ형 드라이브 1개 장착마다 치명 확률 +8%)이 기존 데이터와 같아 능력치·스킬 계수·아크·장비 배치는 바꾸지 않았습니다.
- **홈 화면:** 작업 공간의 대표 이미지를 아카네 린에서 엘림(PNG)으로 바꿨습니다.
- **시작 오류 해결:** 2.3.3～2.3.5에서 "독립 캐릭터 카탈로그를 사용할 수 없습니다" 오류로 프로그램이 시작되지 않던 문제를 해결했습니다. 엘림 전신 이미지는 PNG로 들어 있고 설치 프로그램이 예전 WebP 파일을 지웁니다. 앞으로 카탈로그 파일이 검증에 실패해도(2.3.3～2.3.5의 이미지 형식 오류, 손상된 이미지 목록 파일 등) 프로그램이 멈추지 않고 전체 게임 데이터베이스로 시작한 뒤 경고를 표시합니다.

> **2.3.5 이하 사용자:** 프로그램 안 업데이트를 쓸 수 없으므로(2.3.3～2.3.5는 시작 오류, 2.3.3 이하는 Global 업데이트 기능이 없거나 이전 서명 키를 쓰기 때문) 이 릴리스의 설치 파일을 직접 실행해 주세요. 기존 설치 위치와 사용자 데이터는 유지됩니다. 2.3.6 사용자는 프로그램 안에서 업데이트할 수 있습니다.

엘림의 팀 DPS 시뮬레이션·사이클 기반 효율표 제외(게임 데이터에 타격 타이밍 정보가 없음)와 실제 게임 연결 상태의 가방 동기화 미검증은 이전과 같습니다. [엘림 자료와 검증 방법](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/v2.3.7/build_tools/ELYMS.md)

## 中文

原作者：**[hxwd94666](https://github.com/hxwd94666) · [NTE Drive Calc original project](https://github.com/hxwd94666/NTE-Drive-Calculator)** 及 NTE Drive Calc contributors。Global 是 LuinDe 独立维护的非官方多语言衍生项目。

曳尔沐已于 2026 年 11 月 11 日随 1.5 版本登陆韩国服务器，本版将原先基于国服的曳尔沐资料改为以韩服为准。

- **韩服官方文本**：韩语界面中曳尔沐的技能、觉醒、共鸣、被动与弧盘名称及说明，改用韩服游戏文本（异环数据库 [nte.nanoka.cc](https://nte.nanoka.cc/) 的正式服 1.5.4 韩语数据）。此前仍为中文的技能详细说明与技能等级项目也全部以韩语显示。
- **养成材料名称**：韩语界面的养成材料名称同样按该数据更新（甲硬币、方斯、猎人攻略、井屑系列、萝卜币、弧盘突破材料、淡色染剂等）。
- **社区推荐配队与输出循环**：韩语界面的曳尔沐角色图鉴资料页显示玩家实际使用的配队与输出循环，仅供参考。依据 Arca Live、DCinside、Ruliweb 与博客上的玩家帖子和评论，不采用官方推荐、管理员整理帖以及以 YouTube 等视频为依据的帖子；附有玩家本人游戏视频的帖子只参考正文与评论的文字，不参考视频。每项显示所参考的帖子数，鼠标悬停可查看帖子地址。不参与计算。
- **数值**：韩服确认的属性（80 级生命 15,392 · 攻击 660 · 防御 909）与「卡带」属性（Ⅲ型特化：每装配一个Ⅲ型驱动暴击率 +8%）与现有数据一致，属性、技能倍率、弧盘与装备布局均未改动。
- **首页**：工作台头像由明音凛改为曳尔沐（PNG）。
- **修复启动错误**：修复 2.3.3–2.3.5 因“独立角色目录不可用”而无法启动的问题。曳尔沐立绘以 PNG 提供，安装程序会删除旧的 WebP 文件。今后角色目录文件未通过校验时（如 2.3.3–2.3.5 的图片格式错误、损坏的图片清单文件），程序也不会中断，而是使用完整游戏数据库启动并显示警告。

> **2.3.5 及更早版本的用户**：无法使用应用内更新（2.3.3–2.3.5 因启动错误，2.3.3 及更早版本因没有 Global 更新功能或使用旧签名密钥），请直接运行本版安装程序。安装位置与用户数据会保留。2.3.6 用户可在应用内更新。

曳尔沐仍不参与队伍 DPS 模拟与基于循环的效率表（游戏数据中没有命中时机信息），连接实际游戏时的背包同步仍未验证。[曳尔沐资料与验证方法](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/v2.3.7/build_tools/ELYMS.md)

## English

Original author: **[hxwd94666](https://github.com/hxwd94666) · [NTE Drive Calc original project](https://github.com/hxwd94666/NTE-Drive-Calculator)** and NTE Drive Calc contributors. Global is an unofficial multilingual derivative independently maintained by LuinDe.

Elyms launched on the Korean server with version 1.5 on 2026-11-11, so her data now follows the Korean server instead of the CN server.

- **Official Korean-server text:** in the Korean UI, Elyms' skill, Awakening, Resonance, passive and Arc names and descriptions now use the Korean server's game text (live 1.5.4 Korean data of the NTE database [nte.nanoka.cc](https://nte.nanoka.cc/)). Her previously Chinese detailed skill texts and skill-level entries are now Korean as well.
- **Cultivation material names:** the Korean UI's material names follow the same data (Beetle Coin, Fons, hunter guides, manhole materials, carrot coins, Arc breakthrough materials, dye, etc.).
- **Community teams and rotations:** the Korean UI's Elyms catalog profile shows the teams and rotations players actually use, for reference only. They come from players' posts and comments on Arca Live, DCinside, Ruliweb and blogs; official recommendations, staff summaries and posts based on YouTube or other videos are excluded, and for posts that attach the player's own gameplay clip only the text of the post and its comments is used, never the clip. Each entry shows how many posts it cites, and hovering over it lists their addresses. No calculation uses them.
- **Values:** the stats confirmed on the Korean server (Lv. 80 HP 15,392 · ATK 660 · DEF 909) and the Cartridge Attributes (Type III Specialization: +8% CRIT Rate for each Type III Drive equipped) match the existing data, so stats, skill multipliers, Arc values and the equipment layout are unchanged.
- **Home page:** the Workbench avatar now shows Elyms (PNG) instead of Akane Rin.
- **Startup error fixed:** 2.3.3–2.3.5 could stop at startup with "Standalone character catalog unavailable". Elyms' full-body artwork ships as PNG and the installer removes the old WebP file. A catalog that fails validation (such as the 2.3.3–2.3.5 image format error or a damaged image list file) no longer stops the program: it starts with the complete game database and shows a warning.

> **Users of 2.3.5 or earlier:** in-app updates are not available (2.3.3–2.3.5 because of the startup error, 2.3.3 and earlier because they have no Global updater or trust the old signing key), so run this release's installer manually. The installation folder and user data are kept. 2.3.6 users can update in-app.

Elyms is still excluded from team DPS simulation and rotation-based efficiency tables (the game data has no hit timings for her), and inventory sync with a live game session remains unverified. [Elyms data and validation](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/v2.3.7/build_tools/ELYMS.md)

## 日本語

原作者：**[hxwd94666](https://github.com/hxwd94666) · [NTE Drive Calc original project](https://github.com/hxwd94666/NTE-Drive-Calculator)** および NTE Drive Calc contributors。Global は LuinDe が独立して保守する非公式多言語派生プロジェクトです。

イェルムが 2026 年 11 月 11 日のバージョン 1.5 で韓国サーバーに実装されたため、中国版基準だったイェルムの資料を韓国サーバー基準に切り替えました。

- **韓国サーバーの公式テキスト**：韓国語 UI のイェルムのスキル・覚醒・共鳴・パッシブ・アークの名称と説明を、韓国サーバーのゲームテキスト（異環データベース [nte.nanoka.cc](https://nte.nanoka.cc/) のライブ版 1.5.4 韓国語データ）に変更しました。中国語のまま残っていたスキル詳細とスキルレベル項目もすべて韓国語で表示されます。
- **育成素材の名称**：韓国語 UI の育成素材名も同じデータに合わせました（甲硬貨、方斯、ハンター攻略本、マンホール素材、ニンジン硬貨、アーク突破素材、染料など）。
- **コミュニティの推奨編成・ローテーション**：韓国語 UI のイェルム図鑑プロフィールに、プレイヤーが実際に使う編成とローテーションを参考として表示します。Arca Live・DCinside・Ruliweb・ブログのプレイヤーの投稿とコメントに基づき、公式推奨・コミュニティ管理人のまとめ記事と YouTube などの動画を根拠にした投稿は除き、本人のプレイ動画が付いた投稿は動画ではなく本文とコメントの文章のみ参考にしています。各項目に参照した投稿数を表示し、項目にマウスを乗せると投稿のアドレスが表示されます。計算には使いません。
- **数値**：韓国サーバーで確認したステータス（Lv.80 HP 15,392・攻撃力 660・防御力 909）と「カートリッジ」属性（Ⅲ型特化：Ⅲ型ドライブ 1 個につき会心率 +8%）が既存データと同じため、ステータス・スキル倍率・アーク・装備配置は変更していません。
- **ホーム画面**：ワークベンチの代表画像を明音凛からイェルム（PNG）に変更しました。
- **起動エラーの修正**：2.3.3～2.3.5 で「独立キャラクターカタログが利用できません」と表示され起動できない問題を修正しました。イェルムの全身イラストは PNG で同梱され、インストーラーが古い WebP ファイルを削除します。今後カタログファイルが検証に通らない場合（2.3.3～2.3.5 の画像形式エラーや破損した画像リストファイルなど）も停止せず、完全なゲームデータベースで起動して警告を表示します。

> **2.3.5 以前をお使いの方**：アプリ内更新を利用できません（2.3.3～2.3.5 は起動エラー、2.3.3 以前は Global の更新機能がないか旧署名鍵を使うため）。このリリースのインストーラーを手動で実行してください。インストール先とユーザーデータは保持されます。2.3.6 からはアプリ内で更新できます。

イェルムのチーム DPS シミュレーション・ローテーション効率表は引き続き対象外（ゲームデータにヒットタイミング情報がないため）で、実際のゲーム接続でのインベントリ同期も未検証です。[イェルムの資料と検証方法](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/v2.3.7/build_tools/ELYMS.md)
