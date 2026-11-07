# NTE Drive Calc Global 2.3.5

## 한국어

엘림이 있는 계정에서 가방 동기화가 `native.inventory.page / NATIVE_MAPPING_UNSUPPORTED`로 중단되던 오류를 수정했습니다. 수집용 Core의 캐릭터 표에 엘림(ID 1090)을 추가하고, 장비 배치 표에도 중국 본서버 1.5.4 기준 유효 칸과 권장 장비를 반영했습니다.

실제 Core에 합성 가방을 연결해 엘림이 장착한 드라이브 1개와 카트리지 1개가 계정 DB에 저장되는 것을 확인했습니다. 두 장비 모두 장착 상태와 소유자 1090이 유지됐습니다. 미등록 ID를 받은 경우에는 이전 가방을 보존합니다. 실게임 계정 대신 격리된 테스트 연결을 사용했습니다.

**v2.3.4 사용자는 프로그램 안에서 업데이트할 수 있습니다.** v2.3.3 이하 사용자는 서명 키 전환을 위해 이번 한 번 [Windows 설치 파일](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/download/v2.3.5/NTE_Drive_Calc_2.3.5_Multilingual_Setup.exe)을 직접 실행해 주세요. 기존 v2.3.4 게임 플러그인이 정상 연결돼 있었다면 게임 폴더에 다시 배포할 필요가 없습니다. [수정 내역과 검증 방법](https://github.com/LuinDe/NTE-Drive-Calc-Global/blob/v2.3.5/build_tools/ELYMS.md)

## English

Fixed native inventory sync stopping at `native.inventory.page` with `NATIVE_MAPPING_UNSUPPORTED` when Elyms was present. The bundled Core now includes her character ID (1090) and her CN 1.5.4 equipment layout.

Using a simulated plugin connection to the real Core, the sync service saved an equipped module and cartridge with Elyms as the owner of both. An unknown character ID still stops the read and preserves the previous inventory. Testing used an isolated inventory.

Update in-app from v2.3.4. On v2.3.3 or earlier, run the Windows installer once to switch signing keys. A working v2.3.4 in-game plugin setup can be used as-is.

## 日本語

イェルムがいると、ネイティブ所持品同期が `native.inventory.page` で `NATIVE_MAPPING_UNSUPPORTED` を返して停止する問題を修正しました。付属の Core にキャラクター ID 1090 と中国版1.5.4の装備配置を追加しました。

隔離した模擬接続と実際の Core で、ドライブ1個とカートリッジ1個がイェルムの装備としてアカウントDBに保存されることを確認しました。未登録IDの場合は直前の所持品が保持されます。

v2.3.4 からはアプリ内で更新できます。v2.3.3 以前は署名鍵の切り替えのため、今回のみインストーラーを手動で実行してください。正常に接続できていた v2.3.4 のゲーム側プラグインはそのまま使えます。

## 中文

修复持有曳尔沐时原生背包同步在 `native.inventory.page` 返回 `NATIVE_MAPPING_UNSUPPORTED` 的问题。随包 Core 的角色表新增曳尔沐（ID 1090），装备表新增国服 1.5.4 的配装布局。

在隔离的模拟插件连接中，使用实际 Core 验证了曳尔沐装备的一件驱动和一件卡带均能写入账号数据库，两件装备的归属 ID 均为 1090。遇到未收录的 ID 时仍会停止读取并保留上一次的背包。

v2.3.4 用户可在应用内更新。v2.3.3 及更早版本的用户请手动运行一次安装程序以切换签名密钥。已正常连接的 v2.3.4 游戏端插件无需重新部署。
