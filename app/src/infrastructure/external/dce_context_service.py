"""Build semantic datasource context via the databao-context-engine library."""
from __future__ import annotations

import logging
import os
import shutil
from typing import Any, Dict, Optional

import duckdb

from databao_context_engine import DatasourceId, DatasourceType

from ...models.datasource import DatasourceDatabaseType, DatasourceFileType, DatasourceKind
from .dce_integration import get_domain_manager

logger = logging.getLogger(__name__)

_DCE_CONFIG_PREFIX = "daa"


class DceContextService:
    """Registers datasources in a DCE domain and builds indexed semantic context."""

    def __init__(self, domain_dir: str) -> None:
        self._domain_dir = domain_dir
        self._snapshots_dir = os.path.join(domain_dir, "snapshots")

    @property
    def _manager(self):
        return get_domain_manager(self._domain_dir)

    def datasource_config_name(self, registry_id: str) -> str:
        return f"{_DCE_CONFIG_PREFIX}/{registry_id}"

    def datasource_id(self, registry_id: str) -> DatasourceId:
        return DatasourceId.from_string_repr(f"{self.datasource_config_name(registry_id)}.yaml")

    async def build_context(
        self,
        registry_id: str,
        datasource_name: str,
        *,
        kind: DatasourceKind,
        type_value: str,
        config: Dict[str, Any],
    ) -> str:
        """Build and index DCE context; return YAML summary or empty string on failure."""
        try:
            dce_config = self._build_dce_config(
                registry_id=registry_id,
                datasource_name=datasource_name,
                kind=kind,
                type_value=type_value,
                config=config,
            )
            if dce_config is None:
                return ""

            ds_id = self.datasource_id(registry_id)
            self._manager.create_datasource_config(
                DatasourceType(full_type=dce_config["type"]),
                datasource_name=self.datasource_config_name(registry_id),
                config_content=dce_config,
                overwrite_existing=True,
            )
            results = self._manager.build_context(
                datasource_ids=[ds_id],
                should_index=True,
                should_enrich_context=False,
            )
            if not results:
                logger.warning("DCE build returned no results for %s", registry_id)
                return ""

            engine = self._manager.get_engine_for_domain()
            context = engine.get_datasource_context(ds_id)
            return context.context.strip()
        except Exception as exc:
            logger.warning("DCE context build failed for %s: %s", registry_id, exc, exc_info=True)
            return ""

    def remove_datasource(self, registry_id: str) -> None:
        """Remove DCE config, built context, and optional DuckDB snapshot."""
        ds_id = self.datasource_id(registry_id)
        layout = self._manager._project_layout

        config_path = ds_id.absolute_path_to_config_file(layout)
        context_path = ds_id.absolute_path_to_context_file(layout)
        for path in (config_path, context_path):
            try:
                if path.is_file():
                    path.unlink()
            except OSError as exc:
                logger.debug("Failed to delete DCE artifact %s: %s", path, exc)

        snapshot = os.path.join(self._snapshots_dir, f"{registry_id}.duckdb")
        try:
            if os.path.isfile(snapshot):
                os.remove(snapshot)
        except OSError as exc:
            logger.debug("Failed to delete DCE snapshot %s: %s", snapshot, exc)

        parent = config_path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)

    def _build_dce_config(
        self,
        *,
        registry_id: str,
        datasource_name: str,
        kind: DatasourceKind,
        type_value: str,
        config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if kind == DatasourceKind.DATABASE:
            return self._database_config(datasource_name, type_value, config)
        return self._file_config(registry_id, datasource_name, type_value, config)

    def _database_config(
        self, datasource_name: str, type_value: str, config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        db_type = type_value.lower()
        if db_type == DatasourceDatabaseType.DUCKDB.value:
            path = config.get("path") or config.get("database_path")
            if not path:
                return None
            return {
                "name": datasource_name,
                "type": "duckdb",
                "connection": {"database_path": path},
            }

        if db_type not in {
            DatasourceDatabaseType.POSTGRES.value,
            DatasourceDatabaseType.MYSQL.value,
        }:
            logger.warning("DCE does not support database type %s", db_type)
            return None

        connection = {
            "host": config.get("host", "localhost"),
            "port": config.get("port"),
            "database": config.get("database"),
            "user": config.get("user"),
            "password": config.get("password"),
            "additional_properties": config.get("additional_properties") or {},
        }
        connection = {k: v for k, v in connection.items() if v is not None}
        return {"name": datasource_name, "type": db_type, "connection": connection}

    def _file_config(
        self,
        registry_id: str,
        datasource_name: str,
        type_value: str,
        config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        file_path = config.get("path")
        if not file_path:
            return None

        file_type = type_value.lower()
        if file_type == DatasourceFileType.PARQUET.value:
            return {"name": datasource_name, "type": "parquet", "url": file_path}

        if file_type == DatasourceFileType.SQLITE.value:
            return {
                "name": datasource_name,
                "type": "sqlite",
                "connection": {"database_path": file_path},
            }

        if file_type in {DatasourceFileType.CSV.value, DatasourceFileType.EXCEL.value}:
            snapshot_path = self._materialize_duckdb_snapshot(
                registry_id=registry_id,
                file_path=file_path,
                file_type=file_type,
                original_filename=config.get("original_filename"),
            )
            if not snapshot_path:
                return None
            return {
                "name": datasource_name,
                "type": "duckdb",
                "connection": {"database_path": snapshot_path},
            }

        logger.warning("DCE does not support file type %s", file_type)
        return None

    def _materialize_duckdb_snapshot(
        self,
        *,
        registry_id: str,
        file_path: str,
        file_type: str,
        original_filename: Optional[str],
    ) -> Optional[str]:
        os.makedirs(self._snapshots_dir, exist_ok=True)
        snapshot_path = os.path.join(self._snapshots_dir, f"{registry_id}.duckdb")
        if os.path.isfile(snapshot_path):
            try:
                os.remove(snapshot_path)
            except OSError:
                pass

        conn = duckdb.connect(snapshot_path)
        try:
            if file_type == DatasourceFileType.CSV.value:
                conn.execute(
                    f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{file_path}', sample_size=-1)"
                )
                return snapshot_path

            if file_type == DatasourceFileType.EXCEL.value:
                import pandas as pd

                sheets = pd.read_excel(file_path, sheet_name=None)
                if not sheets:
                    return None
                for idx, (sheet_name, frame) in enumerate(sheets.items()):
                    table_name = self._safe_table_name(sheet_name, idx)
                    conn.register(f"_tmp_{table_name}", frame)
                    conn.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM _tmp_{table_name}')
                return snapshot_path
        except Exception as exc:
            logger.warning(
                "Failed to materialize DuckDB snapshot for %s (%s): %s",
                registry_id,
                original_filename or file_path,
                exc,
            )
            try:
                conn.close()
            finally:
                if os.path.isfile(snapshot_path):
                    os.remove(snapshot_path)
            return None
        finally:
            conn.close()

    @staticmethod
    def _safe_table_name(sheet_name: str, index: int) -> str:
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(sheet_name).strip().lower())
        cleaned = cleaned.strip("_") or f"sheet_{index + 1}"
        if cleaned[0].isdigit():
            cleaned = f"t_{cleaned}"
        return cleaned[:63]
