# Global 인앱 업데이트 서비스 패키지 (NTE Drive Calc Global 추가 모듈)
"""In-app update of NTE Drive Calc Global.

Only the GitHub Releases of ``LuinDe/NTE-Drive-Calc-Global`` are ever consulted (``src.app.global_release``).
Modules: ``models`` (types, error codes), ``verify`` (integrity gates), ``notes`` (release notes per language),
``state`` (app-wide state file), ``client`` (release discovery + download), ``launcher`` (installer hand-off),
``env`` (environment self-heal after a relaunch through Setup).
"""
