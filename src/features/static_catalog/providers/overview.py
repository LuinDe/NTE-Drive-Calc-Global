# 将全量静态表覆盖登记映射到公共资料库契约。
"""Public provider for the audited 125-table static release registry."""

from __future__ import annotations
from src.i18n_runtime import L as _L, LF as _LF

from pathlib import Path

from src.features.static_catalog.contracts import (
    CatalogDetail,
    CatalogDomain,
    CatalogField,
    CatalogItem,
    CatalogPage,
    CatalogSection,
    CatalogValueSource,
    StaticCatalogRelease,
)
from src.storage.sqlite.static_catalog_overview_queries import (
    STATIC_TABLE_CATALOG,
    StaticCatalogOverviewQueries,
    StaticTableOverview,
)


_STATE_LABELS = {
    "A": _L('完整正式目录'),
    "B": _L('已公开，含高级证据'),
    "C": _L('可展示，存在结构化缺口'),
    "D": _L('仅有正式 ID 或有限证据'),
    "E": _L('空表或发行 payload 明确省略'),
}


class StaticCatalogOverviewProvider:
    """Expose every normalized table, including empty and omitted-payload facts."""

    domain = CatalogDomain(
        key="coverage",
        label=_L('覆盖总览'),
        description=_L('发行静态库 125 张表的逐表行数、领域与可展示状态'),
        order=0,
    )

    def __init__(self, database_path: str) -> None:
        self._queries = StaticCatalogOverviewQueries(database_path)
        self._rows = self._queries.list_tables()

    def close(self) -> None:
        self._queries.close()

    @staticmethod
    def _ensure_release(release: StaticCatalogRelease, database_path: str) -> None:
        if release.database_path != Path(database_path).resolve():
            raise RuntimeError(_L('覆盖总览与当前冻结发行路径不一致'))

    def search(
        self,
        release: StaticCatalogRelease,
        *,
        query: str,
        offset: int,
        limit: int,
    ) -> CatalogPage:
        self._ensure_release(release, str(self._queries.database_path))
        needle = query.casefold()
        matched = tuple(
            row
            for row in self._rows
            if not needle
            or needle in row.name.casefold()
            or needle in row.domain.casefold()
            or needle in _STATE_LABELS[row.coverage_state].casefold()
        )
        return CatalogPage(
            items=tuple(self._item(row) for row in matched[offset : offset + limit]),
            total=len(matched),
            offset=offset,
            limit=limit,
        )

    def detail(
        self, release: StaticCatalogRelease, record_id: str
    ) -> CatalogDetail | None:
        self._ensure_release(release, str(self._queries.database_path))
        row = next((item for item in self._rows if item.name == record_id), None)
        if row is None:
            return None
        notes = []
        if row.name == "source_row" and release.source_payloads_omitted:
            notes.append(_L('发行清单明确省略 source_row.payload_json；来源键和内容哈希仍可追溯。'))
        if row.rows == 0:
            notes.append(_L('该表属于正式 schema，但本次发行没有记录；不会用 0 伪装未知业务值。'))
        return CatalogDetail(
            item=self._item(row),
            sections=(
                CatalogSection(
                    title=_L('逐表覆盖审计'),
                    fields=(
                        self._field(_L('正式表名'), row.name, copyable=True),
                        self._field(_L('数据领域'), row.domain),
                        self._field(_L('记录数'), f"{row.rows:,}"),
                        self._field(_L('覆盖状态'), f"{row.coverage_state} · {_STATE_LABELS[row.coverage_state]}"),
                        self._field("Dataset", release.dataset_id, copyable=True),
                        self._field("Schema", f"v{release.schema_version}"),
                        self._field("Importer", f"v{release.importer_version}"),
                        self._field(_L('只读'), _L('是') if release.read_only else _L('否')),
                    ),
                ),
            ),
            notes=tuple(notes),
        )

    @staticmethod
    def _item(row: StaticTableOverview) -> CatalogItem:
        return CatalogItem(
            domain_key="coverage",
            record_id=row.name,
            title=row.name,
            subtitle=_LF('{0} · {1:,} 行 · 状态 {2}').format((row.domain), (row.rows), (row.coverage_state)),
        )

    @staticmethod
    def _field(label: str, value: str, *, copyable: bool = False) -> CatalogField:
        return CatalogField(label, value, CatalogValueSource.OFFICIAL_STATIC, copyable)


def registered_static_table_count() -> int:
    """Executable gate used by tests and composition audits."""

    return len(STATIC_TABLE_CATALOG)
