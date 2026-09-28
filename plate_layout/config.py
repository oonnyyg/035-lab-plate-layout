"""布局配置 JSON 的加载与校验。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .wells import parse_well


class ConfigError(ValueError):
    """配置文件非法。"""


@dataclass(frozen=True)
class PlateConfig:
    """孔板布局配置。

    ``max_plates`` 为允许使用的板数上限（正整数）；
    ``control_wells`` 与 ``disabled_wells`` 为每块板相同的对照孔与禁用孔。
    """

    max_plates: int
    control_wells: frozenset[str]
    disabled_wells: frozenset[str]

    @property
    def reserved_wells(self) -> frozenset[str]:
        return self.control_wells | self.disabled_wells

    @property
    def available_per_plate(self) -> int:
        """单板可用于样本的孔数。"""
        return 96 - len(self.reserved_wells)


def load_config(path: str) -> PlateConfig:
    """从 JSON 文件读取并校验配置。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"配置文件不是合法 JSON: {path}（第 {exc.lineno} 行第 {exc.colno} 列）") from exc
    return parse_config(raw)


def parse_config(raw: object) -> PlateConfig:
    """校验配置字典并构造 :class:`PlateConfig`。"""
    if not isinstance(raw, dict):
        raise ConfigError("配置根节点必须是 JSON 对象")

    max_plates = raw.get("max_plates")
    if isinstance(max_plates, bool) or not isinstance(max_plates, int) or max_plates <= 0:
        raise ConfigError("max_plates 必须为正整数")

    control_wells = _validate_well_list(raw, "control_wells")
    disabled_wells = _validate_well_list(raw, "disabled_wells")

    conflict = sorted(control_wells & disabled_wells)
    if conflict:
        raise ConfigError(f"孔位同时被标记为对照孔与禁用孔: {', '.join(conflict)}")

    return PlateConfig(
        max_plates=max_plates,
        control_wells=frozenset(control_wells),
        disabled_wells=frozenset(disabled_wells),
    )


def _validate_well_list(raw: dict, key: str) -> set[str]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ConfigError(f"{key} 必须是孔位数组")
    wells: set[str] = set()
    for item in value:
        try:
            row, col = parse_well(item if isinstance(item, str) else "")
        except ValueError as exc:
            raise ConfigError(f"{key} 中存在{exc}") from exc
        name = f"{row}{col}"
        if name in wells:
            raise ConfigError(f"{key} 中存在重复孔位: {name}")
        wells.add(name)
    return wells
