"""Dynamic connector discovery from directories and entry points."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import inspect
import logging
from pathlib import Path
import sys
from typing import Mapping

from .base import BaseConnector

logger = logging.getLogger("stovo_connector_sdk.discovery")


def discover_connectors(
    directory: str | Path | None = None,
    entry_point_group: str = "stovo.connectors",
) -> dict[str, BaseConnector]:
    """Discover and instantiate BaseConnector implementations.

    Connectors are discovered via:
    1. Python entry points registered under `entry_point_group`
    2. File-based plugin discovery scanning the specified `directory`
    """
    connectors: dict[str, BaseConnector] = {}

    # 1. Entry points discovery
    try:
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            group_eps = eps.select(group=entry_point_group)
        else:
            group_eps = eps.get(entry_point_group, [])

        for ep in group_eps:
            try:
                cls_or_obj = ep.load()
                if inspect.isclass(cls_or_obj) and issubclass(cls_or_obj, BaseConnector):
                    instance = cls_or_obj()
                    connectors[getattr(instance, "kind", ep.name)] = instance
                elif isinstance(cls_or_obj, BaseConnector):
                    connectors[getattr(cls_or_obj, "kind", ep.name)] = cls_or_obj
            except Exception as err:
                logger.warning("Failed to load connector entry point '%s': %s", ep.name, err)
    except Exception as err:
        logger.debug("Entry points discovery failed: %s", err)

    # 2. Directory-based discovery
    if directory is not None:
        target_dir = Path(directory)
        if target_dir.is_dir():
            # Scan all .py files and subfolders
            python_files: list[Path] = []
            for item in target_dir.iterdir():
                if item.is_file() and item.suffix == ".py" and not item.name.startswith((".", "_")):
                    python_files.append(item)
                elif item.is_dir() and not item.name.startswith((".", "_")):
                    candidate = item / "connector.py"
                    if candidate.is_file():
                        python_files.append(candidate)
                    else:
                        init_candidate = item / "__init__.py"
                        if init_candidate.is_file():
                            python_files.append(init_candidate)

            for py_path in python_files:
                module_name = f"stovo_discovered_{py_path.stem}_{abs(hash(str(py_path)))}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, py_path)
                    if spec is None or spec.loader is None:
                        continue
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = mod
                    spec.loader.exec_module(mod)

                    for _, member in inspect.getmembers(mod, inspect.isclass):
                        if (
                            issubclass(member, BaseConnector)
                            and member is not BaseConnector
                            and not inspect.isabstract(member)
                        ):
                            try:
                                instance = member()
                                kind = getattr(instance, "kind", None) or member.__name__.lower().removesuffix("connector")
                                connectors[kind] = instance
                                logger.info("Discovered connector '%s' from %s", kind, py_path)
                            except Exception as err:
                                logger.warning(
                                    "Failed to instantiate connector %s from %s: %s",
                                    member.__name__,
                                    py_path,
                                    err,
                                )
                except Exception as err:
                    logger.warning("Failed to import module from %s: %s", py_path, err)

    return connectors
