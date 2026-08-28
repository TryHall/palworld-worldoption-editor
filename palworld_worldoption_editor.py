#!/usr/bin/env python3
"""Palworld WorldOption.sav editor.

Requirements (Windows, Python 3.10+):
    python -m pip install palworld-save-tools pyooz

The application:
- only opens a file named WorldOption.sav;
- starts browsing at %LocalAppData%\\Pal\\Saved\\SaveGames;
- displays every setting present in OptionWorldData.Settings;
- supports English, Japanese, and Simplified Chinese UI text;
- includes localized names and explanations for every known WorldOption setting;
- makes an immutable sequential backup on every save;
- validates the newly written save before replacing the original.

Notes:
- Current Palworld saves may use PlM/Oodle compression. ``pyooz`` decodes
  those files; because pyooz is decoder-only, edited PlM input is written as
  Palworld's compatible PlZ/0x32 double-zlib format.
- The PlZ/0x32 header follows palworld-save-tools exactly: the compressed-size
  field stores the INNER zlib stream size, not the final outer stream size.
- A byte-identical GVAS no-op round-trip is required before editing. If the
  installed parser cannot reproduce the loaded GVAS exactly, saving is blocked.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import zlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# -----------------------------------------------------------------------------
# Optional dependencies
# -----------------------------------------------------------------------------

_IMPORT_ERROR = None
_BACKEND_NAME = None
PALWORLD_TYPE_HINTS = {}

# Public PyPI backend for GVAS parsing/serialization.
try:
    from palworld_save_tools.gvas import GvasFile
    try:
        from palworld_save_tools.paltypes import PALWORLD_TYPE_HINTS
    except Exception:
        PALWORLD_TYPE_HINTS = {}
    _BACKEND_NAME = "palworld-save-tools"
except Exception as exc:
    GvasFile = None
    _IMPORT_ERROR = exc

# pyooz is a decoder for modern PlM/Oodle saves. It has Windows x64 wheels on
# PyPI and is only required when the loaded WorldOption.sav uses PlM.
try:
    from ooz import decompress as _ooz_decompress
except Exception:
    _ooz_decompress = None


APP_NAME = "Palworld WorldOption.sav Editor"
SAVE_FILENAME = "WorldOption.sav"
DEFAULT_SAVE_ROOT = Path(
    os.environ.get("LOCALAPPDATA", str(Path.home()))
) / "Pal" / "Saved" / "SaveGames"

# Current 1.0-era OptionSettings defaults. Setting identifiers are intentionally
# not localized: they are Palworld's serialized property names.
DEFAULTS = {
    'Difficulty': 'None',
    'RandomizerType': 'None',
    'RandomizerSeed': '',
    'bIsRandomizerPalLevelRandom': False,
    'DayTimeSpeedRate': 1.0,
    'NightTimeSpeedRate': 1.0,
    'ExpRate': 1.0,
    'PalCaptureRate': 1.0,
    'PalSpawnNumRate': 1.0,
    'PalDamageRateAttack': 1.0,
    'PalDamageRateDefense': 1.0,
    'PlayerDamageRateAttack': 1.0,
    'PlayerDamageRateDefense': 1.0,
    'PlayerStomachDecreaceRate': 1.0,
    'PlayerStaminaDecreaceRate': 1.0,
    'PlayerAutoHPRegeneRate': 1.0,
    'PlayerAutoHpRegeneRateInSleep': 1.0,
    'PalStomachDecreaceRate': 1.0,
    'PalStaminaDecreaceRate': 1.0,
    'PalAutoHPRegeneRate': 1.0,
    'PalAutoHpRegeneRateInSleep': 1.0,
    'BuildObjectHpRate': 1.0,
    'BuildObjectDamageRate': 1.0,
    'BuildObjectDeteriorationDamageRate': 1.0,
    'CollectionDropRate': 1.0,
    'CollectionObjectHpRate': 1.0,
    'CollectionObjectRespawnSpeedRate': 1.0,
    'EnemyDropItemRate': 1.0,
    'DeathPenalty': 'Item',
    'bEnablePlayerToPlayerDamage': False,
    'bEnableFriendlyFire': False,
    'bEnableInvaderEnemy': True,
    'bActiveUNKO': False,
    'bEnableAimAssistPad': True,
    'bEnableAimAssistKeyboard': False,
    'DropItemMaxNum': 3000,
    'PhysicsActiveDropItemMaxNum': -1,
    'DropItemMaxNum_UNKO': 100,
    'BaseCampMaxNum': 128,
    'BaseCampWorkerMaxNum': 15,
    'DropItemAliveMaxHours': 1.0,
    'bAutoResetGuildNoOnlinePlayers': False,
    'AutoResetGuildTimeNoOnlinePlayers': 72.0,
    'GuildPlayerMaxNum': 20,
    'BaseCampMaxNumInGuild': 4,
    'PalEggDefaultHatchingTime': 1.0,
    'WorkSpeedRate': 1.0,
    'AutoSaveSpan': 30.0,
    'bIsMultiplay': False,
    'bIsPvP': False,
    'bHardcore': False,
    'bPalLost': False,
    'bCharacterRecreateInHardcore': False,
    'bCanPickupOtherGuildDeathPenaltyDrop': False,
    'bEnableNonLoginPenalty': True,
    'bEnableFastTravel': True,
    'bEnableFastTravelOnlyBaseCamp': False,
    'bIsStartLocationSelectByMap': False,
    'bExistPlayerAfterLogout': False,
    'bEnableDefenseOtherGuildPlayer': False,
    'bInvisibleOtherGuildBaseCampAreaFX': False,
    'bBuildAreaLimit': False,
    'ItemWeightRate': 1.0,
    'CoopPlayerMaxNum': 4,
    'ServerPlayerMaxNum': 32,
    'ServerName': 'Default Palworld Server',
    'ServerDescription': '',
    'AdminPassword': '',
    'ServerPassword': '',
    'bAllowClientMod': True,
    'PublicPort': 8211,
    'PublicIP': '',
    'RCONEnabled': False,
    'RCONPort': 25575,
    'Region': '',
    'bUseAuth': True,
    'BanListURL': 'https://b.palworldgame.com/api/banlist.txt',
    'RESTAPIEnabled': False,
    'RESTAPIPort': 8212,
    'bShowPlayerList': False,
    'ChatPostLimitPerMinute': 30,
    'CrossplayPlatforms': ['Steam', 'Xbox', 'PS5', 'Mac'],
    'bIsUseBackupSaveData': True,
    'LogFormatType': 'Text',
    'bIsShowJoinLeftMessage': True,
    'SupplyDropSpan': 180,
    'EnablePredatorBossPal': True,
    'MaxBuildingLimitNum': 0,
    'ServerReplicatePawnCullDistance': 15000.0,
    'bAllowGlobalPalboxExport': True,
    'bAllowGlobalPalboxImport': False,
    'EquipmentDurabilityDamageRate': 1.0,
    'ItemContainerForceMarkDirtyInterval': 1.0,
    'PlayerDataPalStorageUpdateCheckTickInterval': 1.0,
    'ItemCorruptionMultiplier': 1.0,
    'MonsterFarmActionSpeedRate': 1.0,
    'DenyTechnologyList': [],
    'GuildRejoinCooldownMinutes': 0,
    'AutoTransferMasterCheckIntervalSeconds': 3600.0,
    'AutoTransferMasterThresholdDays': 14,
    'MaxGuildsPerFrame': 10,
    'BlockRespawnTime': 5.0,
    'RespawnPenaltyDurationThreshold': 0.0,
    'RespawnPenaltyTimeScale': 2.0,
    'bDisplayPvPItemNumOnWorldMap_BaseCamp': False,
    'bDisplayPvPItemNumOnWorldMap_Player': False,
    'AdditionalDropItemWhenPlayerKillingInPvPMode': 'PlayerDropItem',
    'AdditionalDropItemNumWhenPlayerKillingInPvPMode': 1,
    'bAdditionalDropItemWhenPlayerKillingInPvPMode': False,
    'bEnableVoiceChat': False,
    'VoiceChatMaxVolumeDistance': 3000.0,
    'VoiceChatZeroVolumeDistance': 15000.0,
    'bAllowEnhanceStat_Health': True,
    'bAllowEnhanceStat_Attack': True,
    'bAllowEnhanceStat_Stamina': True,
    'bAllowEnhanceStat_Weight': True,
    'bAllowEnhanceStat_WorkSpeed': True,
    'bEnableBuildingPlayerUIdDisplay': False,
    'BuildingNameDisplayCacheTTLSeconds': 60,
}
DEFAULTS_CASEFOLD = {k.casefold(): v for k, v in DEFAULTS.items()}

ENUM_CHOICES = {
    "Difficulty": ["None", "Casual", "Normal", "Hard"],
    "RandomizerType": ["None", "Region", "All"],
    "DeathPenalty": ["None", "Item", "ItemAndEquipment", "All"],
    "LogFormatType": ["Text", "Json"],
}
ENUM_ARRAY_TYPES = {
    "CrossplayPlatforms": "EPalAllowConnectPlatform",
}

I18N = {
    "en": {
        "language_name": "English",
        "title": APP_NAME,
        "open": "Open WorldOption.sav…",
        "save": "Save",
        "reset": "Reset to Default",
        "language": "Language:",
        "filter": "Filter settings:",
        "setting": "Setting / Description",
        "value": "Value",
        "type": "Type",
        "default": "Default",
        "no_file": "No file loaded",
        "ready": "Ready",
        "loaded": "Loaded {count} settings: {path}",
        "saved_title": "Saved",
        "saved": "WorldOption.sav was saved successfully.\n\nBackup: {backup}",
        "load_error_title": "Could not open file",
        "save_error_title": "Could not save file",
        "invalid_name": "Only a file named WorldOption.sav can be opened.",
        "invalid_worldoption": "The file does not contain OptionWorldData.Settings and does not look like a WorldOption.sav.",
        "missing_dependency_title": "Missing dependency",
        "missing_dependency": "Install the required packages first:\n\npython -m pip install palworld-save-tools pyooz",
        "need_pyooz": "This WorldOption.sav uses PlM/Oodle compression. Install decoder support:\n\npython -m pip install pyooz",
        "reset_title": "Reset to Default",
        "reset_confirm": "Reset all settings that have a known Palworld default?\n\nThis only changes the fields on screen; nothing is written until you click Save.",
        "reset_done": "Defaults loaded into the editor. Click Save to write them.",
        "external_change": "WorldOption.sav changed on disk after it was opened. Reload it before saving so a newer game save is not overwritten.",
        "invalid_value": "Invalid value for {key}: {detail}",
        "filter_count": "Showing {shown} of {total} settings",
        "bool": "Boolean",
        "int": "Integer",
        "float": "Decimal",
        "str": "Text",
        "enum": "Enum",
        "array": "List",
        "json": "Advanced",
        "unknown_default": "—",
    },
    "ja": {
        "language_name": "日本語",
        "title": "Palworld WorldOption.sav エディター",
        "open": "WorldOption.sav を開く…",
        "save": "保存",
        "reset": "デフォルトに戻す",
        "language": "言語:",
        "filter": "設定を絞り込み:",
        "setting": "設定 / 説明",
        "value": "値",
        "type": "型",
        "default": "デフォルト",
        "no_file": "ファイルが読み込まれていません",
        "ready": "準備完了",
        "loaded": "{count} 個の設定を読み込みました: {path}",
        "saved_title": "保存完了",
        "saved": "WorldOption.sav を保存しました。\n\nバックアップ: {backup}",
        "load_error_title": "ファイルを開けませんでした",
        "save_error_title": "ファイルを保存できませんでした",
        "invalid_name": "WorldOption.sav という名前のファイルだけを開くことができます。",
        "invalid_worldoption": "OptionWorldData.Settings が見つかりません。このファイルは WorldOption.sav ではない可能性があります。",
        "missing_dependency_title": "必要なパッケージがありません",
        "missing_dependency": "必要なパッケージをインストールしてください:\n\npython -m pip install palworld-save-tools pyooz",
        "need_pyooz": "この WorldOption.sav は PlM/Oodle 圧縮です。デコーダーをインストールしてください:\n\npython -m pip install pyooz",
        "reset_title": "デフォルトに戻す",
        "reset_confirm": "既知の Palworld デフォルト値がある設定をすべてリセットしますか？\n\n画面上の値だけが変更され、［保存］を押すまでファイルには書き込まれません。",
        "reset_done": "デフォルト値をエディターに読み込みました。書き込むには［保存］を押してください。",
        "external_change": "開いた後に WorldOption.sav がディスク上で変更されました。新しいゲーム保存を上書きしないよう、再読み込みしてから保存してください。",
        "invalid_value": "{key} の値が無効です: {detail}",
        "filter_count": "{total} 件中 {shown} 件を表示",
        "bool": "ブール",
        "int": "整数",
        "float": "小数",
        "str": "テキスト",
        "enum": "列挙",
        "array": "リスト",
        "json": "詳細",
        "unknown_default": "—",
    },
    "zh": {
        "language_name": "简体中文",
        "title": "Palworld WorldOption.sav 编辑器",
        "open": "打开 WorldOption.sav…",
        "save": "保存",
        "reset": "恢复默认值",
        "language": "语言：",
        "filter": "筛选设置：",
        "setting": "设置 / 说明",
        "value": "值",
        "type": "类型",
        "default": "默认值",
        "no_file": "尚未加载文件",
        "ready": "就绪",
        "loaded": "已加载 {count} 项设置：{path}",
        "saved_title": "保存完成",
        "saved": "WorldOption.sav 已成功保存。\n\n备份：{backup}",
        "load_error_title": "无法打开文件",
        "save_error_title": "无法保存文件",
        "invalid_name": "只能打开名为 WorldOption.sav 的文件。",
        "invalid_worldoption": "文件中没有 OptionWorldData.Settings；它看起来不是有效的 WorldOption.sav。",
        "missing_dependency_title": "缺少依赖",
        "missing_dependency": "请先安装所需软件包：\n\npython -m pip install palworld-save-tools pyooz",
        "need_pyooz": "此 WorldOption.sav 使用 PlM/Oodle 压缩。请安装解码支持：\n\npython -m pip install pyooz",
        "reset_title": "恢复默认值",
        "reset_confirm": "要把所有具有已知 Palworld 默认值的设置恢复为默认值吗？\n\n这只会修改界面中的值；点击“保存”之前不会写入文件。",
        "reset_done": "默认值已载入编辑器。点击“保存”即可写入文件。",
        "external_change": "打开后，磁盘上的 WorldOption.sav 已发生变化。请先重新加载，以免覆盖游戏产生的较新存档。",
        "invalid_value": "{key} 的值无效：{detail}",
        "filter_count": "显示 {shown}/{total} 项设置",
        "bool": "布尔",
        "int": "整数",
        "float": "小数",
        "str": "文本",
        "enum": "枚举",
        "array": "列表",
        "json": "高级",
        "unknown_default": "—",
    },
}
LANGUAGE_BY_LABEL = {v["language_name"]: k for k, v in I18N.items()}


# -----------------------------------------------------------------------------
# Localized setting names and explanations
# -----------------------------------------------------------------------------
# Pocketpair's public server guide documents most of these settings. A handful
# are WorldOption/save-only or internal settings; those descriptions are kept
# deliberately literal so the editor does not imply unsupported behavior.
#
# Each entry contains a localized display name and an explanation for all three
# supported UI languages. The serialized Palworld key is always shown beneath
# the translated name and is never changed when saving.
SETTING_META = {
    "Difficulty": {
        "en": ("Difficulty preset", "Selects the world difficulty preset stored in the save. Individual settings below can still override preset-style values."),
        "ja": ("難易度プリセット", "セーブに保存されるワールド難易度プリセットです。下の個別設定によって、プリセット相当の値を個別に変更できます。"),
        "zh": ("难度预设", "选择保存在存档中的世界难度预设。下方的单独设置仍可覆盖预设对应的数值。"),
    },
    "RandomizerType": {
        "en": ("Pal randomizer mode", "Controls Pal spawn randomization: None disables it, Region randomizes within regions, and All fully randomizes spawns."),
        "ja": ("パル出現ランダムモード", "パル出現のランダム化方式です。None は無効、Region は地域ごと、All は完全ランダムです。"),
        "zh": ("帕鲁出现随机模式", "控制帕鲁出现的随机化方式：None 为关闭，Region 为按区域随机，All 为完全随机。"),
    },
    "RandomizerSeed": {
        "en": ("Randomizer seed", "Seed used when Pal spawn randomization is enabled. The same seed is intended to reproduce the same randomized setup."),
        "ja": ("ランダマイザーシード", "パル出現ランダム化を有効にしたときに使用するシード値です。同じシードは同じランダム構成の再現に使われます。"),
        "zh": ("随机化种子", "启用帕鲁出现随机化时使用的种子值。相同种子用于复现相同的随机配置。"),
    },
    "bIsRandomizerPalLevelRandom": {
        "en": ("Fully randomize wild Pal levels", "When enabled, wild Pal levels are fully randomized. When disabled, levels are randomized within each area's intended range."),
        "ja": ("野生パルのレベルを完全ランダム化", "有効にすると野生パルのレベルを完全にランダム化します。無効の場合は各エリアに見合った範囲内でランダム化されます。"),
        "zh": ("完全随机野生帕鲁等级", "启用后，野生帕鲁等级将完全随机；关闭后，只会在各区域预期的等级范围内随机。"),
    },
    "DayTimeSpeedRate": {
        "en": ("Daytime speed", "Multiplier for how quickly daytime passes."),
        "ja": ("昼の経過速度", "昼時間の進行速度倍率です。"),
        "zh": ("白天流逝速度", "白天时间推进速度的倍率。"),
    },
    "NightTimeSpeedRate": {
        "en": ("Nighttime speed", "Multiplier for how quickly nighttime passes."),
        "ja": ("夜の経過速度", "夜時間の進行速度倍率です。"),
        "zh": ("夜晚流逝速度", "夜晚时间推进速度的倍率。"),
    },
    "ExpRate": {
        "en": ("EXP rate", "Multiplier for experience gained."),
        "ja": ("経験値倍率", "獲得経験値の倍率です。"),
        "zh": ("经验值倍率", "获得经验值的倍率。"),
    },
    "PalCaptureRate": {
        "en": ("Pal capture rate", "Multiplier applied to Pal capture probability."),
        "ja": ("パル捕獲率", "パルの捕獲確率に適用される倍率です。"),
        "zh": ("帕鲁捕获率", "应用于帕鲁捕获概率的倍率。"),
    },
    "PalSpawnNumRate": {
        "en": ("Pal spawn rate", "Multiplier for the number of Pals that appear. Higher values can increase performance load."),
        "ja": ("パル出現倍率", "出現するパル数の倍率です。高い値ほど処理負荷が増える可能性があります。"),
        "zh": ("帕鲁出现倍率", "帕鲁出现数量的倍率。数值越高，可能越影响性能。"),
    },
    "PalDamageRateAttack": {
        "en": ("Damage dealt by Pals", "Multiplier for damage dealt by Pals."),
        "ja": ("パルの与ダメージ", "パルが与えるダメージの倍率です。"),
        "zh": ("帕鲁造成伤害", "帕鲁造成伤害的倍率。"),
    },
    "PalDamageRateDefense": {
        "en": ("Damage taken by Pals", "Multiplier for damage received by Pals."),
        "ja": ("パルの被ダメージ", "パルが受けるダメージの倍率です。"),
        "zh": ("帕鲁受到伤害", "帕鲁受到伤害的倍率。"),
    },
    "PlayerDamageRateAttack": {
        "en": ("Damage dealt by players", "Multiplier for damage dealt by player characters."),
        "ja": ("プレイヤーの与ダメージ", "プレイヤーが与えるダメージの倍率です。"),
        "zh": ("玩家造成伤害", "玩家角色造成伤害的倍率。"),
    },
    "PlayerDamageRateDefense": {
        "en": ("Damage taken by players", "Multiplier for damage received by player characters."),
        "ja": ("プレイヤーの被ダメージ", "プレイヤーが受けるダメージの倍率です。"),
        "zh": ("玩家受到伤害", "玩家角色受到伤害的倍率。"),
    },
    "PlayerStomachDecreaceRate": {
        "en": ("Player hunger depletion", "Multiplier for how quickly player hunger decreases."),
        "ja": ("プレイヤー満腹度減少", "プレイヤーの満腹度が減る速度の倍率です。"),
        "zh": ("玩家饱食度消耗", "玩家饱食度下降速度的倍率。"),
    },
    "PlayerStaminaDecreaceRate": {
        "en": ("Player stamina depletion", "Multiplier for how quickly player stamina is consumed."),
        "ja": ("プレイヤースタミナ減少", "プレイヤーのスタミナ消費速度の倍率です。"),
        "zh": ("玩家耐力消耗", "玩家耐力消耗速度的倍率。"),
    },
    "PlayerAutoHPRegeneRate": {
        "en": ("Player natural HP regeneration", "Multiplier for normal player HP regeneration."),
        "ja": ("プレイヤーHP自然回復", "プレイヤーの通常時HP自然回復の倍率です。"),
        "zh": ("玩家自然生命恢复", "玩家正常状态下生命值自然恢复的倍率。"),
    },
    "PlayerAutoHpRegeneRateInSleep": {
        "en": ("Player sleeping HP regeneration", "Multiplier for player HP regeneration while sleeping."),
        "ja": ("プレイヤー睡眠時HP回復", "睡眠中のプレイヤーHP回復倍率です。"),
        "zh": ("玩家睡眠生命恢复", "玩家睡眠时生命值恢复的倍率。"),
    },
    "PalStomachDecreaceRate": {
        "en": ("Pal hunger depletion", "Multiplier for how quickly Pal hunger decreases."),
        "ja": ("パル満腹度減少", "パルの満腹度が減る速度の倍率です。"),
        "zh": ("帕鲁饱食度消耗", "帕鲁饱食度下降速度的倍率。"),
    },
    "PalStaminaDecreaceRate": {
        "en": ("Pal stamina depletion", "Multiplier for how quickly Pal stamina is consumed."),
        "ja": ("パルスタミナ減少", "パルのスタミナ消費速度の倍率です。"),
        "zh": ("帕鲁耐力消耗", "帕鲁耐力消耗速度的倍率。"),
    },
    "PalAutoHPRegeneRate": {
        "en": ("Pal natural HP regeneration", "Multiplier for normal Pal HP regeneration."),
        "ja": ("パルHP自然回復", "パルの通常時HP自然回復の倍率です。"),
        "zh": ("帕鲁自然生命恢复", "帕鲁正常状态下生命值自然恢复的倍率。"),
    },
    "PalAutoHpRegeneRateInSleep": {
        "en": ("Pal sleeping HP regeneration", "Multiplier for Pal HP regeneration while sleeping or stored in the Palbox."),
        "ja": ("パル睡眠時HP回復", "睡眠中またはパルボックス内のパルHP回復倍率です。"),
        "zh": ("帕鲁睡眠生命恢复", "帕鲁睡眠或存放在帕鲁终端时生命值恢复的倍率。"),
    },
    "BuildObjectHpRate": {
        "en": ("Building HP", "Multiplier for building and structure durability/HP."),
        "ja": ("建築物HP", "建築物・構造物の耐久値（HP）倍率です。"),
        "zh": ("建筑生命值", "建筑和结构耐久度/生命值的倍率。"),
    },
    "BuildObjectDamageRate": {
        "en": ("Damage to buildings", "Multiplier for damage dealt to buildings."),
        "ja": ("建築物へのダメージ", "建築物が受けるダメージの倍率です。"),
        "zh": ("建筑受到伤害", "建筑所受到伤害的倍率。"),
    },
    "BuildObjectDeteriorationDamageRate": {
        "en": ("Building deterioration", "Multiplier for building deterioration/decay damage over time."),
        "ja": ("建築物の劣化", "時間経過による建築物の劣化ダメージ倍率です。"),
        "zh": ("建筑腐朽", "建筑随时间产生的腐朽/劣化伤害倍率。"),
    },
    "CollectionDropRate": {
        "en": ("Gathering yield", "Multiplier for the amount of items obtained from gatherable objects."),
        "ja": ("採集アイテム量", "採集オブジェクトから得られるアイテム量の倍率です。"),
        "zh": ("采集产量", "从可采集物体获得的物品数量倍率。"),
    },
    "CollectionObjectHpRate": {
        "en": ("Gatherable object HP", "Multiplier for the HP of gatherable objects such as rocks and trees."),
        "ja": ("採集オブジェクトHP", "岩や木など採集オブジェクトのHP倍率です。"),
        "zh": ("采集物生命值", "岩石、树木等可采集物体生命值的倍率。"),
    },
    "CollectionObjectRespawnSpeedRate": {
        "en": ("Gatherable respawn interval", "Multiplier affecting the respawn interval of gatherable objects."),
        "ja": ("採集オブジェクト復活間隔", "採集オブジェクトのリスポーン間隔に適用される倍率です。"),
        "zh": ("采集物重生间隔", "影响可采集物体重生间隔的倍率。"),
    },
    "EnemyDropItemRate": {
        "en": ("Enemy drop quantity", "Multiplier for item quantities dropped by enemies."),
        "ja": ("敵ドロップ量", "敵がドロップするアイテム量の倍率です。"),
        "zh": ("敌人掉落数量", "敌人掉落物品数量的倍率。"),
    },
    "DeathPenalty": {
        "en": ("Death penalty", "Controls what is dropped on death: none, items, items plus equipment, or all items/equipment/team Pals depending on the selected enum."),
        "ja": ("デスペナルティ", "死亡時に失うものを設定します。選択値により、無し、アイテム、アイテム＋装備、またはアイテム・装備・手持ちパル全てになります。"),
        "zh": ("死亡惩罚", "控制死亡时掉落的内容：无、物品、物品加装备，或根据枚举值掉落物品、装备及队伍帕鲁。"),
    },
    "bEnablePlayerToPlayerDamage": {
        "en": ("Player-to-player damage", "Allows player attacks to damage other player characters."),
        "ja": ("プレイヤー間ダメージ", "プレイヤーの攻撃で他のプレイヤーにダメージを与えられるようにします。"),
        "zh": ("玩家间伤害", "允许玩家攻击对其他玩家角色造成伤害。"),
    },
    "bEnableFriendlyFire": {
        "en": ("Friendly fire", "Allows damage between friendly/allied players or entities where the game applies friendly-fire rules."),
        "ja": ("フレンドリーファイア", "ゲームのフレンドリーファイア判定が適用される味方同士のダメージを許可します。"),
        "zh": ("友军伤害", "允许在游戏友军伤害规则适用时，对友方玩家或单位造成伤害。"),
    },
    "bEnableInvaderEnemy": {
        "en": ("Raids / invaders", "Enables enemy invasion/raid events against player bases."),
        "ja": ("襲撃", "プレイヤー拠点に対する敵の襲撃イベントを有効にします。"),
        "zh": ("袭击事件", "启用敌人针对玩家据点的入侵/袭击事件。"),
    },
    "bActiveUNKO": {
        "en": ("Dropped Pal feces", "Internal world option controlling whether the game's Pal feces/UNKO drop behavior is active."),
        "ja": ("パルのフン生成", "パルのフン（UNKO）ドロップ挙動を有効にする内部ワールド設定です。"),
        "zh": ("帕鲁粪便生成", "控制帕鲁粪便（UNKO）掉落行为是否启用的内部世界设置。"),
    },
    "bEnableAimAssistPad": {
        "en": ("Controller aim assist", "Enables aim assistance when using a game controller."),
        "ja": ("ゲームパッド照準アシスト", "ゲームパッド使用時の照準アシストを有効にします。"),
        "zh": ("手柄瞄准辅助", "启用使用游戏手柄时的瞄准辅助。"),
    },
    "bEnableAimAssistKeyboard": {
        "en": ("Keyboard/mouse aim assist", "Enables the aim-assist option associated with keyboard/mouse input."),
        "ja": ("キーボード・マウス照準アシスト", "キーボード・マウス入力向けの照準アシスト設定を有効にします。"),
        "zh": ("键鼠瞄准辅助", "启用与键盘/鼠标输入相关的瞄准辅助设置。"),
    },
    "DropItemMaxNum": {
        "en": ("Maximum dropped items", "Maximum number of dropped item objects the world keeps active."),
        "ja": ("ドロップアイテム最大数", "ワールド内で保持されるドロップアイテムオブジェクトの最大数です。"),
        "zh": ("掉落物最大数量", "世界中保持活动状态的掉落物对象最大数量。"),
    },
    "PhysicsActiveDropItemMaxNum": {
        "en": ("Physics-enabled dropped items", "Maximum number of dropped items that can simultaneously use physics behavior."),
        "ja": ("物理演算するドロップ上限", "同時に物理挙動を使用できるドロップアイテムの最大数です。"),
        "zh": ("启用物理效果的掉落物上限", "可同时使用物理行为的掉落物最大数量。"),
    },
    "DropItemMaxNum_UNKO": {
        "en": ("Maximum feces drops", "Maximum number of UNKO/feces-type dropped objects retained in the world."),
        "ja": ("フンドロップ最大数", "ワールド内に保持されるフン（UNKO）系ドロップの最大数です。"),
        "zh": ("粪便掉落物上限", "世界中保留的粪便（UNKO）类掉落物最大数量。"),
    },
    "BaseCampMaxNum": {
        "en": ("Total bases", "Total number of bases allowed across the server/world."),
        "ja": ("ワールド全体の拠点数", "サーバー／ワールド全体で許可される拠点の総数です。"),
        "zh": ("世界据点总数", "整个服务器/世界允许存在的据点总数。"),
    },
    "BaseCampWorkerMaxNum": {
        "en": ("Pals per base", "Maximum number of working Pals per base. Higher values increase processing load."),
        "ja": ("拠点あたりのパル数", "1拠点で働けるパルの最大数です。値を増やすと処理負荷が増えます。"),
        "zh": ("每个据点的工作帕鲁数", "每个据点可工作的帕鲁最大数量。提高数值会增加处理负载。"),
    },
    "DropItemAliveMaxHours": {
        "en": ("Dropped item lifetime", "How many hours dropped item objects remain in the world before they may be removed."),
        "ja": ("ドロップアイテム保持時間", "ドロップアイテムが削除対象になるまでワールドに残る時間（時間）です。"),
        "zh": ("掉落物保留时间", "掉落物在可能被清除前于世界中保留的小时数。"),
    },
    "bAutoResetGuildNoOnlinePlayers": {
        "en": ("Delete inactive guild bases", "If no guild member logs in for the configured period, automatically removes that guild's structures and base Pals."),
        "ja": ("非アクティブギルドの自動削除", "設定期間中にギルドメンバーが誰もログインしない場合、そのギルドの建築物と拠点パルを自動削除します。"),
        "zh": ("自动清理不活跃公会", "若在设定时间内没有任何公会成员登录，则自动删除该公会的建筑和据点帕鲁。"),
    },
    "AutoResetGuildTimeNoOnlinePlayers": {
        "en": ("Inactive guild timeout", "Offline duration before inactive-guild auto reset triggers. Ignored when automatic inactive-guild reset is disabled."),
        "ja": ("非アクティブギルド判定時間", "非アクティブギルドの自動削除が発動するまでのオフライン時間です。自動削除が無効なら使用されません。"),
        "zh": ("不活跃公会超时时间", "触发不活跃公会自动重置前的离线时间。关闭自动重置时此值会被忽略。"),
    },
    "GuildPlayerMaxNum": {
        "en": ("Players per guild", "Maximum number of players allowed in one guild."),
        "ja": ("ギルド最大人数", "1つのギルドに参加できるプレイヤーの最大人数です。"),
        "zh": ("公会人数上限", "一个公会允许加入的玩家最大数量。"),
    },
    "BaseCampMaxNumInGuild": {
        "en": ("Bases per guild", "Maximum number of bases allowed per guild. Higher values increase processing load."),
        "ja": ("ギルドあたりの拠点数", "1ギルドが所有できる拠点の最大数です。値を増やすと処理負荷が増えます。"),
        "zh": ("每个公会的据点数", "每个公会可拥有的据点最大数量。提高数值会增加处理负载。"),
    },
    "PalEggDefaultHatchingTime": {
        "en": ("Egg incubation time", "Hours required to incubate a Huge Egg; other egg sizes scale from this setting."),
        "ja": ("タマゴ孵化時間", "キョダイタマゴの孵化に必要な時間（時間）です。他サイズのタマゴにもこの設定が基準として影響します。"),
        "zh": ("帕鲁蛋孵化时间", "巨大蛋孵化所需的小时数；其他尺寸的蛋也会以此设置为基准。"),
    },
    "WorkSpeedRate": {
        "en": ("Work speed", "Global multiplier applied to work speed in the world."),
        "ja": ("作業速度倍率", "ワールド全体の作業速度に適用される倍率です。"),
        "zh": ("工作速度倍率", "应用于世界整体工作速度的倍率。"),
    },
    "AutoSaveSpan": {
        "en": ("Autosave interval", "Interval used for automatic world saving. This key may appear as autoSaveSpan in some saves."),
        "ja": ("オートセーブ間隔", "ワールドを自動保存する間隔です。一部のセーブでは autoSaveSpan という表記で保存されます。"),
        "zh": ("自动保存间隔", "世界自动保存的间隔。部分存档中该键可能写作 autoSaveSpan。"),
    },
    "autoSaveSpan": {
        "en": ("Autosave interval", "Interval used for automatic world saving. This is the save-file spelling of AutoSaveSpan seen in some versions."),
        "ja": ("オートセーブ間隔", "ワールドを自動保存する間隔です。一部バージョンのセーブで使われる AutoSaveSpan の表記です。"),
        "zh": ("自动保存间隔", "世界自动保存的间隔。这是部分版本存档中 AutoSaveSpan 使用的键名形式。"),
    },
    "bIsMultiplay": {
        "en": ("Multiplayer world flag", "Internal world flag indicating multiplayer behavior for the save. This is separate from the co-op and server player-count limits."),
        "ja": ("マルチプレイワールドフラグ", "このセーブのマルチプレイ動作を示す内部フラグです。協力プレイ人数やサーバー人数の上限とは別の設定です。"),
        "zh": ("多人世界标志", "表示此存档多人游戏行为的内部标志，与合作人数上限和服务器人数上限是不同设置。"),
    },
    "bIsPvP": {
        "en": ("PvP", "Enables PvP mode for the world/server."),
        "ja": ("PvP", "ワールド／サーバーでPvPモードを有効にします。"),
        "zh": ("PvP", "在世界/服务器中启用 PvP 模式。"),
    },
    "bHardcore": {
        "en": ("Hardcore mode", "Enables Hardcore mode. Death prevents normal respawning unless other Hardcore-related settings allow recreation."),
        "ja": ("ハードコアモード", "ハードコアを有効にします。死亡時は通常のリスポーンができず、関連設定によりキャラクター再作成可否が決まります。"),
        "zh": ("硬核模式", "启用硬核模式。死亡后无法正常重生，是否能重新创建角色由其他硬核相关设置决定。"),
    },
    "bPalLost": {
        "en": ("Permanent Pal loss on death", "When enabled, Pals can be permanently lost when the player dies."),
        "ja": ("死亡時のパル永久ロスト", "有効にすると、プレイヤー死亡時にパルを永久に失う場合があります。"),
        "zh": ("死亡时永久失去帕鲁", "启用后，玩家死亡时可能永久失去帕鲁。"),
    },
    "bCharacterRecreateInHardcore": {
        "en": ("Recreate character in Hardcore", "Controls whether a dead character may be recreated while Hardcore mode is enabled."),
        "ja": ("ハードコア死亡時のキャラ再作成", "ハードコア有効時に死亡したキャラクターを再作成できるかを設定します。"),
        "zh": ("硬核死亡后重建角色", "控制启用硬核模式时死亡角色是否可以重新创建。"),
    },
    "bCanPickupOtherGuildDeathPenaltyDrop": {
        "en": ("Pick up other guild death drops", "Controls whether players may pick up death-penalty drops belonging to another guild."),
        "ja": ("他ギルドの死亡ドロップ取得", "他ギルドのプレイヤーが死亡時に落としたデスペナルティ品を拾えるかを設定します。"),
        "zh": ("拾取其他公会死亡掉落", "控制玩家是否能拾取属于其他公会玩家的死亡惩罚掉落物。"),
    },
    "bEnableNonLoginPenalty": {
        "en": ("Non-login penalty", "Internal option controlling penalties or world behavior associated with players/guilds not logging in for a period of time."),
        "ja": ("未ログインペナルティ", "一定期間ログインしないプレイヤー／ギルドに関連するペナルティやワールド挙動を制御する内部設定です。"),
        "zh": ("长期未登录惩罚", "控制玩家/公会长时间未登录时相关惩罚或世界行为的内部设置。"),
    },
    "bEnableFastTravel": {
        "en": ("Fast travel", "Enables fast travel."),
        "ja": ("ファストトラベル", "ファストトラベルを有効にします。"),
        "zh": ("快速传送", "启用快速传送。"),
    },
    "bEnableFastTravelOnlyBaseCamp": {
        "en": ("Fast travel only between bases", "Restricts fast travel so it can only be used between player bases."),
        "ja": ("拠点間のみファストトラベル", "ファストトラベルをプレイヤー拠点間だけに制限します。"),
        "zh": ("仅据点间快速传送", "将快速传送限制为只能在玩家据点之间使用。"),
    },
    "bIsStartLocationSelectByMap": {
        "en": ("Choose starting location", "Allows players to select their starting location from the map."),
        "ja": ("開始地点をマップで選択", "プレイヤーがマップからゲーム開始地点を選べるようにします。"),
        "zh": ("从地图选择出生点", "允许玩家从地图中选择游戏开始位置。"),
    },
    "bExistPlayerAfterLogout": {
        "en": ("Leave player body after logout", "When enabled, a logged-out player remains sleeping at their current location."),
        "ja": ("ログアウト後もプレイヤーを残す", "有効にすると、ログアウトしたプレイヤーが現在位置で寝た状態のまま残ります。"),
        "zh": ("登出后保留玩家角色", "启用后，登出的玩家会以睡眠状态留在当前位置。"),
    },
    "bEnableDefenseOtherGuildPlayer": {
        "en": ("Defend against other guild players", "Internal guild/PvP option controlling defensive interaction involving players from other guilds."),
        "ja": ("他ギルドプレイヤーへの防衛", "他ギルドのプレイヤーに対する防衛インタラクションを制御する内部ギルド／PvP設定です。"),
        "zh": ("对其他公会玩家的防御", "控制涉及其他公会玩家的防御交互的内部公会/PvP 设置。"),
    },
    "bInvisibleOtherGuildBaseCampAreaFX": {
        "en": ("Other guild base-area display", "Controls visibility of base-area boundary effects for other guilds."),
        "ja": ("他ギルド拠点範囲の表示", "他ギルドの拠点範囲エフェクトの表示状態を制御します。"),
        "zh": ("其他公会据点范围显示", "控制其他公会据点范围边界效果的可见性。"),
    },
    "bBuildAreaLimit": {
        "en": ("Restricted building areas", "Prevents building near protected structures such as fast-travel points."),
        "ja": ("建築禁止エリア", "ファストトラベル地点など保護対象の構造物付近での建築を禁止します。"),
        "zh": ("限制建筑区域", "禁止在快速传送点等受保护结构附近建造。"),
    },
    "ItemWeightRate": {
        "en": ("Item weight", "Multiplier applied to item weight."),
        "ja": ("アイテム重量", "アイテム重量に適用される倍率です。"),
        "zh": ("物品重量", "应用于物品重量的倍率。"),
    },
    "CoopPlayerMaxNum": {
        "en": ("Co-op player limit", "Maximum number of players for a hosted co-op world. This is separate from ServerPlayerMaxNum."),
        "ja": ("協力プレイ最大人数", "ホスト型の協力プレイワールドに参加できる最大人数です。ServerPlayerMaxNum とは別の上限です。"),
        "zh": ("合作模式人数上限", "房主托管合作世界允许的最大玩家数，与 ServerPlayerMaxNum 是不同的上限。"),
    },
    "ServerPlayerMaxNum": {
        "en": ("Server player limit", "Maximum number of players who can join the server."),
        "ja": ("サーバー最大人数", "サーバーに参加できるプレイヤーの最大人数です。"),
        "zh": ("服务器人数上限", "可加入服务器的玩家最大数量。"),
    },
    "ServerName": {
        "en": ("Server name", "Name advertised/displayed for the server."),
        "ja": ("サーバー名", "サーバーに表示・公開される名前です。"),
        "zh": ("服务器名称", "服务器显示或公开使用的名称。"),
    },
    "ServerDescription": {
        "en": ("Server description", "Description text associated with the server."),
        "ja": ("サーバー説明", "サーバーに設定する説明文です。"),
        "zh": ("服务器说明", "与服务器关联的说明文本。"),
    },
    "AdminPassword": {
        "en": ("Administrator password", "Password used to obtain administrative privileges on a server."),
        "ja": ("管理者パスワード", "サーバーの管理者権限を取得するために使用するパスワードです。"),
        "zh": ("管理员密码", "用于获取服务器管理员权限的密码。"),
    },
    "ServerPassword": {
        "en": ("Server password", "Password required for players to log in to the server."),
        "ja": ("サーバーパスワード", "プレイヤーがサーバーへログインする際に必要なパスワードです。"),
        "zh": ("服务器密码", "玩家登录服务器时所需的密码。"),
    },
    "bAllowClientMod": {
        "en": ("Allow modded clients", "Allows players with mods enabled to join the server."),
        "ja": ("Mod有効クライアントを許可", "Modを有効にしているプレイヤーのサーバー参加を許可します。"),
        "zh": ("允许启用模组的客户端", "允许启用了模组的玩家加入服务器。"),
    },
    "PublicPort": {
        "en": ("Public port", "External public port advertised for a community server. This does not change the server's actual listening port."),
        "ja": ("外部公開ポート", "コミュニティサーバーで公開する外部ポートです。実際の待ち受けポート自体は変更しません。"),
        "zh": ("外部公开端口", "社区服务器对外公开的端口；此设置不会改变服务器实际监听端口。"),
    },
    "PublicIP": {
        "en": ("Public IP", "Explicit external public IP advertised for a community server."),
        "ja": ("外部公開IP", "コミュニティサーバーで明示的に公開する外部IPアドレスです。"),
        "zh": ("外部公网 IP", "社区服务器明确对外公开的公网 IP 地址。"),
    },
    "RCONEnabled": {
        "en": ("RCON", "Enables remote console (RCON) administration."),
        "ja": ("RCON", "リモートコンソール（RCON）管理を有効にします。"),
        "zh": ("RCON", "启用远程控制台（RCON）管理。"),
    },
    "RCONPort": {
        "en": ("RCON port", "Port number used by RCON."),
        "ja": ("RCONポート", "RCONで使用するポート番号です。"),
        "zh": ("RCON 端口", "RCON 使用的端口号。"),
    },
    "Region": {
        "en": ("Server region", "Optional region string associated with the server listing/configuration."),
        "ja": ("サーバー地域", "サーバー一覧／設定に関連付ける任意の地域文字列です。"),
        "zh": ("服务器区域", "与服务器列表/配置关联的可选区域字符串。"),
    },
    "bUseAuth": {
        "en": ("Use authentication", "Internal server option controlling authentication use for connections."),
        "ja": ("認証を使用", "接続時の認証使用を制御する内部サーバー設定です。"),
        "zh": ("使用身份验证", "控制连接时是否使用身份验证的内部服务器设置。"),
    },
    "BanListURL": {
        "en": ("Ban-list URL", "URL used by the server to obtain ban-list data."),
        "ja": ("BANリストURL", "サーバーがBANリストデータを取得するために使用するURLです。"),
        "zh": ("封禁列表 URL", "服务器用于获取封禁列表数据的 URL。"),
    },
    "RESTAPIEnabled": {
        "en": ("REST API", "Enables the Palworld server REST API."),
        "ja": ("REST API", "PalworldサーバーのREST APIを有効にします。"),
        "zh": ("REST API", "启用 Palworld 服务器 REST API。"),
    },
    "RESTAPIPort": {
        "en": ("REST API port", "Listening port used by the REST API."),
        "ja": ("REST APIポート", "REST APIが待ち受けるポート番号です。"),
        "zh": ("REST API 端口", "REST API 使用的监听端口号。"),
    },
    "bShowPlayerList": {
        "en": ("Show player list", "Enables the participant/player list on the ESC menu."),
        "ja": ("プレイヤー一覧を表示", "ESCメニューに参加者／プレイヤー一覧を表示します。"),
        "zh": ("显示玩家列表", "在 ESC 菜单中启用参与者/玩家列表。"),
    },
    "ChatPostLimitPerMinute": {
        "en": ("Chat messages per minute", "Maximum number of chat messages a player may post per minute."),
        "ja": ("1分あたりのチャット上限", "プレイヤーが1分間に投稿できるチャットメッセージの最大数です。"),
        "zh": ("每分钟聊天消息上限", "玩家每分钟可发送的聊天消息最大数量。"),
    },
    "CrossplayPlatforms": {
        "en": ("Cross-play platforms", "List of platforms allowed to connect. Current documented defaults are Steam, Xbox, PS5, and Mac."),
        "ja": ("クロスプレイ許可プラットフォーム", "接続を許可するプラットフォーム一覧です。現在の公式デフォルトは Steam、Xbox、PS5、Mac です。"),
        "zh": ("跨平台联机平台", "允许连接的平台列表。当前官方默认值为 Steam、Xbox、PS5 和 Mac。"),
    },
    "bIsUseBackupSaveData": {
        "en": ("Built-in world backups", "Enables Palworld's own rotating world-backup system. Enabling it increases disk activity."),
        "ja": ("ゲーム内ワールドバックアップ", "Palworld自身の世代管理ワールドバックアップを有効にします。有効化するとディスク負荷が増えます。"),
        "zh": ("游戏内世界备份", "启用 Palworld 自带的轮换世界备份系统。开启后会增加磁盘读写负载。"),
    },
    "LogFormatType": {
        "en": ("Log format", "Selects the server log format, such as Text or Json."),
        "ja": ("ログ形式", "Text や Json など、サーバーログの形式を選択します。"),
        "zh": ("日志格式", "选择服务器日志格式，例如 Text 或 Json。"),
    },
    "bIsShowJoinLeftMessage": {
        "en": ("Join/leave messages", "On dedicated servers, displays in-game messages when players join or leave."),
        "ja": ("参加・退出メッセージ", "専用サーバーで、プレイヤーの参加・退出時にゲーム内メッセージを表示します。"),
        "zh": ("加入/离开消息", "在专用服务器中，玩家加入或离开时显示游戏内消息。"),
    },
    "SupplyDropSpan": {
        "en": ("Meteorite / supply-drop interval", "Interval between meteorite and supply-drop events, in minutes."),
        "ja": ("隕石・補給物資の間隔", "隕石／補給物資イベントの発生間隔（分）です。"),
        "zh": ("陨石/补给投放间隔", "陨石和补给投放事件之间的间隔，单位为分钟。"),
    },
    "EnablePredatorBossPal": {
        "en": ("Predator Pal bosses", "Controls whether Predator-type boss Pals are enabled in the world."),
        "ja": ("プレデターパルボス", "ワールドでプレデター系ボスパルを有効にするかを設定します。"),
        "zh": ("掠食者帕鲁首领", "控制世界中是否启用掠食者类型的首领帕鲁。"),
    },
    "MaxBuildingLimitNum": {
        "en": ("Buildings per player", "Maximum number of buildings per player. A value of 0 means unlimited."),
        "ja": ("プレイヤーごとの建築上限", "プレイヤー1人あたりの建築物数上限です。0 は無制限です。"),
        "zh": ("每名玩家建筑上限", "每名玩家允许的建筑数量上限。0 表示无限制。"),
    },
    "ServerReplicatePawnCullDistance": {
        "en": ("Pal synchronization distance", "Distance from players at which Pal actors are synchronized over the server, in centimeters."),
        "ja": ("パル同期距離", "サーバーでパルをプレイヤーへ同期する距離（cm）です。"),
        "zh": ("帕鲁同步距离", "服务器向玩家同步帕鲁实体的距离，单位为厘米。"),
    },
    "bAllowGlobalPalboxExport": {
        "en": ("Allow Global Palbox export", "Allows saving/exporting Pals to the Global Palbox."),
        "ja": ("グローバルパルボックスへ保存", "パルをグローバルパルボックスへ保存／エクスポートできるようにします。"),
        "zh": ("允许导出到全局帕鲁终端", "允许将帕鲁保存/导出到全局帕鲁终端。"),
    },
    "bAllowGlobalPalboxImport": {
        "en": ("Allow Global Palbox import", "Allows loading/importing Pals from the Global Palbox."),
        "ja": ("グローバルパルボックスから読込", "グローバルパルボックスからパルを読み込み／インポートできるようにします。"),
        "zh": ("允许从全局帕鲁终端导入", "允许从全局帕鲁终端加载/导入帕鲁。"),
    },
    "EquipmentDurabilityDamageRate": {
        "en": ("Equipment durability loss", "Multiplier for how quickly equipment durability is consumed by damage/use."),
        "ja": ("装備耐久度減少", "ダメージや使用による装備耐久度の減少倍率です。"),
        "zh": ("装备耐久损耗", "装备因受击或使用而消耗耐久度的倍率。"),
    },
    "ItemContainerForceMarkDirtyInterval": {
        "en": ("Container forced resync interval", "How often, in seconds, an open container is forced to resynchronize."),
        "ja": ("コンテナ強制再同期間隔", "コンテナを開いている際に強制的に再同期する間隔（秒）です。"),
        "zh": ("容器强制重新同步间隔", "打开容器界面时强制重新同步的间隔，单位为秒。"),
    },
    "PlayerDataPalStorageUpdateCheckTickInterval": {
        "en": ("Pal-storage update check interval", "Internal interval controlling how often player Pal-storage data is checked for updates."),
        "ja": ("パル保管データ更新確認間隔", "プレイヤーのパル保管データ更新を確認する頻度を制御する内部設定です。"),
        "zh": ("帕鲁存储数据更新检查间隔", "控制检查玩家帕鲁存储数据更新频率的内部设置。"),
    },
    "ItemCorruptionMultiplier": {
        "en": ("Item spoilage speed", "Multiplier for item corruption/spoilage speed."),
        "ja": ("アイテム腐敗速度", "アイテムが腐敗する速度の倍率です。"),
        "zh": ("物品腐坏速度", "物品腐坏/变质速度的倍率。"),
    },
    "MonsterFarmActionSpeedRate": {
        "en": ("Ranch production speed", "Multiplier for item production speed from grazing/ranch activities."),
        "ja": ("放牧生産速度", "放牧によるアイテム生産速度の倍率です。"),
        "zh": ("牧场生产速度", "放牧/牧场活动产出物品速度的倍率。"),
    },
    "DenyTechnologyList": {
        "en": ("Disabled technologies", "List of technology IDs that players are prevented from using/unlocking as configured by the server."),
        "ja": ("無効化するテクノロジー", "サーバー設定で使用／解放を禁止するテクノロジーIDの一覧です。"),
        "zh": ("禁用科技列表", "服务器配置中禁止玩家使用/解锁的科技 ID 列表。"),
    },
    "GuildRejoinCooldownMinutes": {
        "en": ("Guild rejoin cooldown", "Cooldown in minutes before a player can rejoin a guild after leaving or related guild changes."),
        "ja": ("ギルド再加入クールタイム", "ギルド退出などの後、再加入できるまでのクールタイム（分）です。"),
        "zh": ("重新加入公会冷却", "离开公会等操作后再次加入公会前的冷却时间，单位为分钟。"),
    },
    "AutoTransferMasterCheckIntervalSeconds": {
        "en": ("Guild-master transfer check interval", "Internal interval, in seconds, for checking whether automatic guild-master transfer conditions should be evaluated."),
        "ja": ("ギルドマスター自動移譲確認間隔", "ギルドマスター自動移譲条件を確認する内部処理の間隔（秒）です。"),
        "zh": ("公会会长自动转移检查间隔", "检查是否满足公会会长自动转移条件的内部间隔，单位为秒。"),
    },
    "AutoTransferMasterThresholdDays": {
        "en": ("Guild-master transfer threshold", "Number of inactive days used as the threshold for automatic guild-master transfer logic."),
        "ja": ("ギルドマスター自動移譲日数", "ギルドマスター自動移譲判定に使用する非アクティブ日数のしきい値です。"),
        "zh": ("公会会长自动转移阈值", "自动转移公会会长逻辑使用的不活跃天数阈值。"),
    },
    "MaxGuildsPerFrame": {
        "en": ("Guilds processed per frame", "Internal performance limit for how many guild records are processed in one frame during certain maintenance operations."),
        "ja": ("1フレームあたりのギルド処理数", "特定の保守処理で1フレーム中に処理するギルド数を制限する内部パフォーマンス設定です。"),
        "zh": ("每帧处理的公会数量", "某些维护操作中限制每帧处理公会记录数量的内部性能设置。"),
    },
    "BlockRespawnTime": {
        "en": ("Respawn cooldown", "Base cooldown in seconds before a player can respawn after death."),
        "ja": ("リスポーンクールタイム", "死亡後にリスポーンできるまでの基本クールタイム（秒）です。"),
        "zh": ("重生冷却时间", "玩家死亡后可重生前的基础冷却时间，单位为秒。"),
    },
    "RespawnPenaltyDurationThreshold": {
        "en": ("Respawn-penalty survival threshold", "Survival-time threshold in seconds used to decide whether RespawnPenaltyTimeScale applies on a subsequent death."),
        "ja": ("リスポーンペナルティ生存時間しきい値", "次回死亡時に RespawnPenaltyTimeScale を適用するか判断する生存時間のしきい値（秒）です。"),
        "zh": ("重生惩罚生存时间阈值", "用于判断下一次死亡时是否应用 RespawnPenaltyTimeScale 的生存时间阈值，单位为秒。"),
    },
    "RespawnPenaltyTimeScale": {
        "en": ("Respawn cooldown multiplier", "Multiplier applied to the respawn cooldown when the respawn-penalty conditions are met."),
        "ja": ("リスポーンクールタイム倍率", "リスポーンペナルティ条件を満たした場合にクールタイムへ適用される倍率です。"),
        "zh": ("重生冷却倍率", "满足重生惩罚条件时应用于重生冷却时间的倍率。"),
    },
    "bDisplayPvPItemNumOnWorldMap_BaseCamp": {
        "en": ("Show PvP items at bases on map", "Shows the number of PvP-exclusive items at each base on the world map."),
        "ja": ("マップに拠点PvPアイテム数を表示", "各拠点にあるPvP専用アイテム数をワールドマップへ表示します。"),
        "zh": ("地图显示据点 PvP 物品数", "在世界地图上显示每个据点中的 PvP 专属物品数量。"),
    },
    "bDisplayPvPItemNumOnWorldMap_Player": {
        "en": ("Show player PvP items on map", "Shows player locations and their PvP-exclusive item counts on the world map."),
        "ja": ("マップにプレイヤーPvPアイテム数を表示", "プレイヤー位置と所持するPvP専用アイテム数をワールドマップへ表示します。"),
        "zh": ("地图显示玩家 PvP 物品数", "在世界地图上显示玩家位置及其 PvP 专属物品数量。"),
    },
    "AdditionalDropItemWhenPlayerKillingInPvPMode": {
        "en": ("PvP kill bonus item ID", "Item ID dropped when the PvP special-drop option is enabled and a player kills another player."),
        "ja": ("PvPキル追加ドロップID", "PvP専用追加ドロップが有効な場合、プレイヤーキル時に落とすアイテムIDです。"),
        "zh": ("PvP 击杀额外掉落物品 ID", "启用 PvP 特殊掉落后，玩家击杀其他玩家时掉落的物品 ID。"),
    },
    "AdditionalDropItemNumWhenPlayerKillingInPvPMode": {
        "en": ("PvP kill bonus item quantity", "Quantity of the configured special item dropped on a PvP player kill."),
        "ja": ("PvPキル追加ドロップ数", "PvPでプレイヤーをキルした際に落とす専用アイテムの数量です。"),
        "zh": ("PvP 击杀额外掉落数量", "PvP 击杀玩家时配置的特殊物品掉落数量。"),
    },
    "bAdditionalDropItemWhenPlayerKillingInPvPMode": {
        "en": ("Enable PvP kill bonus drop", "When enabled, killing a player in PvP causes the configured special item to drop."),
        "ja": ("PvPキル追加ドロップを有効化", "有効にすると、PvPでプレイヤーをキルした際に設定された専用アイテムをドロップします。"),
        "zh": ("启用 PvP 击杀额外掉落", "启用后，在 PvP 中击杀玩家会掉落已配置的特殊物品。"),
    },
    "bEnableVoiceChat": {
        "en": ("Voice chat", "Enables in-game voice chat."),
        "ja": ("ボイスチャット", "ゲーム内ボイスチャットを有効にします。"),
        "zh": ("语音聊天", "启用游戏内语音聊天。"),
    },
    "VoiceChatMaxVolumeDistance": {
        "en": ("Voice chat full-volume distance", "Distance within which voice-chat volume does not attenuate."),
        "ja": ("ボイスチャット最大音量距離", "ボイスチャット音量が減衰しない距離です。"),
        "zh": ("语音聊天满音量距离", "在此距离内语音聊天音量不会衰减。"),
    },
    "VoiceChatZeroVolumeDistance": {
        "en": ("Voice chat zero-volume distance", "Distance at which voice-chat volume falls to zero."),
        "ja": ("ボイスチャット無音距離", "ボイスチャット音量が0になる距離です。"),
        "zh": ("语音聊天静音距离", "达到此距离时语音聊天音量降为零。"),
    },
    "bAllowEnhanceStat_Health": {
        "en": ("Allow HP stat allocation", "Allows players to spend stat points on HP."),
        "ja": ("HPへのステータス割り振り", "プレイヤーがステータスポイントをHPへ割り振れるようにします。"),
        "zh": ("允许分配生命值属性点", "允许玩家将属性点分配到生命值。"),
    },
    "bAllowEnhanceStat_Attack": {
        "en": ("Allow Attack stat allocation", "Allows players to spend stat points on Attack."),
        "ja": ("攻撃へのステータス割り振り", "プレイヤーがステータスポイントを攻撃へ割り振れるようにします。"),
        "zh": ("允许分配攻击属性点", "允许玩家将属性点分配到攻击。"),
    },
    "bAllowEnhanceStat_Stamina": {
        "en": ("Allow Stamina stat allocation", "Allows players to spend stat points on Stamina."),
        "ja": ("スタミナへのステータス割り振り", "プレイヤーがステータスポイントをスタミナへ割り振れるようにします。"),
        "zh": ("允许分配耐力属性点", "允许玩家将属性点分配到耐力。"),
    },
    "bAllowEnhanceStat_Weight": {
        "en": ("Allow Carry Weight stat allocation", "Allows players to spend stat points on Carry Weight."),
        "ja": ("所持重量へのステータス割り振り", "プレイヤーがステータスポイントを所持重量へ割り振れるようにします。"),
        "zh": ("允许分配负重属性点", "允许玩家将属性点分配到负重。"),
    },
    "bAllowEnhanceStat_WorkSpeed": {
        "en": ("Allow Work Speed stat allocation", "Allows players to spend stat points on Work Speed."),
        "ja": ("作業速度へのステータス割り振り", "プレイヤーがステータスポイントを作業速度へ割り振れるようにします。"),
        "zh": ("允许分配工作速度属性点", "允许玩家将属性点分配到工作速度。"),
    },
    "bEnableBuildingPlayerUIdDisplay": {
        "en": ("Show building creator ID", "Displays the creator's player ID on structures."),
        "ja": ("建築作成者IDを表示", "建築物に作成者のプレイヤーIDを表示します。"),
        "zh": ("显示建筑创建者 ID", "在建筑结构上显示创建者的玩家 ID。"),
    },
    "BuildingNameDisplayCacheTTLSeconds": {
        "en": ("Building-name display cache lifetime", "Internal cache lifetime, in seconds, for building-name/creator display information."),
        "ja": ("建築名表示キャッシュ保持時間", "建築名／作成者表示情報を保持する内部キャッシュの有効時間（秒）です。"),
        "zh": ("建筑名称显示缓存时间", "建筑名称/创建者显示信息的内部缓存有效时间，单位为秒。"),
    },
}


def setting_meta(key: str, lang: str) -> tuple[str, str]:
    """Return (localized display name, explanation) for a serialized setting."""
    item = SETTING_META.get(key)
    if item is None:
        # Unknown future Palworld property: still provide a localized name and
        # explanation instead of leaving the row untranslated or blank.
        fallback = {
            "en": (key, f"Palworld internal setting '{key}'. This version of the editor does not yet have a curated description for it."),
            "ja": (key, f"Palworld の内部設定「{key}」です。このエディターでは、まだ個別の説明が登録されていません。"),
            "zh": (key, f"Palworld 内部设置“{key}”。当前版本的编辑器尚未收录此项的专门说明。"),
        }
        return fallback.get(lang, fallback["en"])
    return item.get(lang, item["en"])


# -----------------------------------------------------------------------------
# Save container helpers
# -----------------------------------------------------------------------------

class SaveFormatError(Exception):
    pass


class ExternalFileChangedError(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decompress_sav(raw: bytes) -> tuple[bytes, bytes, int]:
    """Return ``(GVAS bytes, container magic, save_type_byte)``.

    Supported by this standalone editor:
      * PlM1: Oodle input via pyooz (read); saved back as PlZ2 after editing.
      * PlZ1: single-zlib input/output.
      * PlZ2: double-zlib input/output.

    The PlZ2 header is subtle: its ``compressed_len`` field is the length of
    the INNER zlib stream. The outer stream occupies the rest of the file.
    """
    if len(raw) < 12:
        raise SaveFormatError("File is too small to be a Palworld save.")

    uncompressed_len = int.from_bytes(raw[0:4], "little")
    compressed_len = int.from_bytes(raw[4:8], "little")
    magic = raw[8:11]
    save_type = raw[11]

    if magic == b"CNK":
        raise SaveFormatError(
            "Microsoft Store/CNK WorldOption.sav files are not supported by "
            "this build. Use a Steam/standard WorldOption.sav."
        )
    if magic not in (b"PlZ", b"PlM"):
        raise SaveFormatError(f"Unsupported Palworld save header: {magic!r}")

    payload = raw[12:]
    if not payload:
        raise SaveFormatError("The save payload is empty.")

    if magic == b"PlM":
        if _ooz_decompress is None:
            raise SaveFormatError("PYOOZ_REQUIRED")
        # PlM uses the actual Oodle payload size in the header.
        if compressed_len != len(payload):
            raise SaveFormatError(
                f"Incorrect PlM compressed length: header={compressed_len}, "
                f"actual={len(payload)}."
            )
        try:
            gvas = _ooz_decompress(payload, uncompressed_len)
        except Exception as exc:
            raise SaveFormatError(f"Oodle decompression failed: {exc}") from exc
    else:
        if save_type not in (0x31, 0x32):
            raise SaveFormatError(f"Unsupported PlZ save type: 0x{save_type:02X}")
        try:
            if save_type == 0x31:
                # PlZ1 stores the actual single-zlib payload size.
                if compressed_len != len(payload):
                    raise SaveFormatError(
                        f"Incorrect PlZ1 compressed length: header={compressed_len}, "
                        f"actual={len(payload)}."
                    )
                gvas = zlib.decompress(payload)
            else:
                # PlZ2: first decompress the OUTER stream. The header's
                # compressed_len must equal the resulting INNER stream size.
                inner = zlib.decompress(payload)
                if compressed_len != len(inner):
                    raise SaveFormatError(
                        f"Incorrect PlZ2 inner compressed length: "
                        f"header={compressed_len}, actual={len(inner)}."
                    )
                gvas = zlib.decompress(inner)
        except zlib.error as exc:
            raise SaveFormatError(f"zlib decompression failed: {exc}") from exc

    if len(gvas) != uncompressed_len:
        raise SaveFormatError(
            f"Decompressed size mismatch: got {len(gvas)}, expected {uncompressed_len}."
        )
    if not gvas.startswith(b"GVAS"):
        raise SaveFormatError("The decompressed payload is not a GVAS file.")
    return bytes(gvas), magic, save_type


def _compress_plz(gvas: bytes, save_type: int) -> bytes:
    """Build a Palworld PlZ1 or PlZ2 container exactly like save-tools.

    For 0x32/double-zlib, ``compressed_len`` is deliberately calculated BEFORE
    the second compression pass. This matches palworld-save-tools and Palworld's
    expected PlZ2 layout.
    """
    if save_type not in (0x31, 0x32):
        raise SaveFormatError(f"Unsupported PlZ save type: 0x{save_type:02X}")

    inner = zlib.compress(gvas)
    compressed_len = len(inner)
    payload = zlib.compress(inner) if save_type == 0x32 else inner

    return (
        len(gvas).to_bytes(4, "little")
        + compressed_len.to_bytes(4, "little")
        + b"PlZ"
        + bytes([save_type])
        + payload
    )


def compress_for_source(gvas: bytes, source_magic: bytes, source_save_type: int) -> bytes:
    """Compress edited GVAS using a PyPI-only compatibility path.

    ``pyooz`` can decode PlM/Oodle but cannot encode it, so modern PlM input is
    written as PlZ2. palworld-save-tools itself uses PlZ2 for Palworld world
    save classes and Palworld accepts zlib-recompressed saves.
    """
    if source_magic == b"PlM":
        return _compress_plz(gvas, 0x32)
    if source_magic == b"PlZ":
        save_type = source_save_type if source_save_type in (0x31, 0x32) else 0x32
        return _compress_plz(gvas, save_type)
    raise SaveFormatError(f"Unsupported source container: {source_magic!r}")


def first_difference(a: bytes, b: bytes) -> int | None:
    """Return the first differing byte offset, including length-only changes."""
    limit = min(len(a), len(b))
    for i in range(limit):
        if a[i] != b[i]:
            return i
    if len(a) != len(b):
        return limit
    return None


def require_gvas_roundtrip(gvas: bytes):
    """Parse and immediately reserialize GVAS; require byte-identical output."""
    parsed = GvasFile.read(gvas, PALWORLD_TYPE_HINTS, {}, allow_nan=True)
    rewritten = parsed.write({})
    if rewritten != gvas:
        pos = first_difference(gvas, rewritten)
        raise SaveFormatError(
            "The installed GVAS parser cannot reproduce this WorldOption.sav "
            "byte-for-byte without edits. Saving is blocked to prevent corruption. "
            f"First difference: offset {pos}; input={len(gvas)} bytes, "
            f"round-trip={len(rewritten)} bytes. Try updating palworld-save-tools."
        )
    return parsed

def next_backup_path(save_path: Path) -> Path:
    """Return .bak, then .bak01, .bak02 ... without overwriting old backups."""
    first = Path(str(save_path) + ".bak")
    if not first.exists():
        return first

    pattern = re.compile(re.escape(save_path.name) + r"\.bak(\d+)$", re.IGNORECASE)
    highest = 0
    try:
        for item in save_path.parent.iterdir():
            match = pattern.fullmatch(item.name)
            if match:
                highest = max(highest, int(match.group(1)))
    except OSError:
        pass
    return Path(str(save_path) + f".bak{highest + 1:02d}")


# -----------------------------------------------------------------------------
# GVAS property conversion helpers
# -----------------------------------------------------------------------------

def strip_enum_prefix(value):
    if isinstance(value, str) and "::" in value:
        return value.rsplit("::", 1)[-1]
    return value


def default_for_key(key: str):
    return DEFAULTS_CASEFOLD.get(key.casefold(), None)


def property_kind(prop: dict) -> str:
    ptype = prop.get("type", "")
    if ptype == "BoolProperty":
        return "bool"
    if ptype in {"IntProperty", "Int8Property", "Int16Property", "Int64Property", "UInt16Property", "UInt32Property", "UInt64Property"}:
        return "int"
    if ptype in {"FloatProperty", "DoubleProperty"}:
        return "float"
    if ptype in {"StrProperty", "NameProperty"}:
        return "str"
    if ptype == "EnumProperty":
        return "enum"
    if ptype in {"ArrayProperty", "SetProperty"}:
        return "array"
    return "json"


def display_value(prop: dict):
    kind = property_kind(prop)
    value = prop.get("value")

    if kind == "bool":
        return bool(value)
    if kind in {"int", "float", "str"}:
        return "" if value is None else str(value)
    if kind == "enum":
        if isinstance(value, dict):
            return str(strip_enum_prefix(value.get("value", "")))
        return str(strip_enum_prefix(value))
    if kind == "array":
        values = value.get("values", []) if isinstance(value, dict) else value
        if not isinstance(values, list):
            return json.dumps(value, ensure_ascii=False)
        values = [strip_enum_prefix(v) for v in values]
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="")
        writer.writerow(values)
        return output.getvalue()

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def format_default(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value)


def parse_csv_or_json_list(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("expected a JSON list")
        return parsed
    return next(csv.reader([text], skipinitialspace=True))


def apply_editor_value(key: str, prop: dict, editor_value) -> None:
    """Update one dumped GVAS property while preserving its serialized type."""
    kind = property_kind(prop)
    ptype = prop.get("type", "")

    if kind == "bool":
        prop["value"] = bool(editor_value)
        return

    if kind == "int":
        raw = str(editor_value).strip()
        if not raw:
            raise ValueError("integer value cannot be empty")
        # Accept "4.0" as a convenience, but reject non-integral numbers.
        n = float(raw)
        if not n.is_integer():
            raise ValueError("expected a whole number")
        prop["value"] = int(n)
        return

    if kind == "float":
        raw = str(editor_value).strip()
        if not raw:
            raise ValueError("decimal value cannot be empty")
        prop["value"] = float(raw)
        return

    if kind == "str":
        prop["value"] = str(editor_value)
        return

    if kind == "enum":
        raw = str(editor_value).strip()
        value_obj = prop.get("value")
        if not isinstance(value_obj, dict):
            raise ValueError("unexpected EnumProperty structure")
        enum_type = value_obj.get("type", "")
        old_full = value_obj.get("value", "")
        if "::" in raw:
            full = raw
        elif enum_type:
            full = f"{enum_type}::{raw}"
        elif isinstance(old_full, str) and "::" in old_full:
            full = f"{old_full.rsplit('::', 1)[0]}::{raw}"
        else:
            full = raw
        value_obj["value"] = full
        return

    if kind == "array":
        values = parse_csv_or_json_list(str(editor_value))
        array_type = prop.get("array_type", "")
        value_obj = prop.get("value")
        if not isinstance(value_obj, dict) or "values" not in value_obj:
            # Unknown future shape: permit a JSON value only.
            if str(editor_value).strip().startswith("["):
                prop["value"] = json.loads(str(editor_value))
                return
            raise ValueError("unexpected array structure; enter a JSON list")

        old_values = value_obj.get("values", [])
        if array_type == "EnumProperty":
            prefix = None
            for old in old_values:
                if isinstance(old, str) and "::" in old:
                    prefix = old.rsplit("::", 1)[0]
                    break
            prefix = prefix or ENUM_ARRAY_TYPES.get(key)
            if prefix:
                values = [v if isinstance(v, str) and "::" in v else f"{prefix}::{v}" for v in values]
        elif array_type in {"IntProperty", "Int64Property", "UInt32Property", "UInt64Property"}:
            values = [int(v) for v in values]
        elif array_type in {"FloatProperty", "DoubleProperty"}:
            values = [float(v) for v in values]
        elif array_type == "BoolProperty":
            def to_bool(v):
                if isinstance(v, bool):
                    return v
                s = str(v).strip().casefold()
                if s in {"true", "1", "yes", "on"}:
                    return True
                if s in {"false", "0", "no", "off"}:
                    return False
                raise ValueError(f"invalid boolean list item: {v!r}")
            values = [to_bool(v) for v in values]
        value_obj["values"] = values
        return

    # Unknown/future property types are still visible and editable as JSON.
    prop["value"] = json.loads(str(editor_value))


# -----------------------------------------------------------------------------
# Document model
# -----------------------------------------------------------------------------

class WorldOptionDocument:
    def __init__(self):
        self.path: Path | None = None
        self.gvas_file = None
        self.settings: dict | None = None
        self.loaded_hash: str | None = None
        self.original_magic: bytes | None = None
        self.original_save_type: int | None = None
        self.original_gvas: bytes | None = None

    def load(self, path: str | os.PathLike) -> dict:
        path = Path(path)
        if path.name.casefold() != SAVE_FILENAME.casefold():
            raise ValueError("INVALID_NAME")

        raw = path.read_bytes()
        gvas_bytes, magic, save_type = decompress_sav(raw)

        # Critical safety gate: do not allow editing with a parser that changes
        # untouched bytes. This catches serializer/version mismatches up front.
        gvas_file = require_gvas_roundtrip(gvas_bytes)

        props = gvas_file.properties
        option_prop = props.get("OptionWorldData")
        if not isinstance(option_prop, dict):
            raise ValueError("INVALID_WORLDOPTION")
        option_value = option_prop.get("value")
        if not isinstance(option_value, dict):
            raise ValueError("INVALID_WORLDOPTION")
        settings_prop = option_value.get("Settings")
        if not isinstance(settings_prop, dict) or not isinstance(settings_prop.get("value"), dict):
            raise ValueError("INVALID_WORLDOPTION")

        self.path = path
        self.gvas_file = gvas_file
        self.settings = settings_prop["value"]
        self.loaded_hash = sha256_bytes(raw)
        self.original_magic = magic
        self.original_save_type = save_type
        self.original_gvas = gvas_bytes
        return self.settings

    def build_save(self, edited_values: dict[str, object]) -> tuple[bytes, object, bytes]:
        if self.gvas_file is None or self.original_magic is None or self.original_save_type is None:
            raise RuntimeError("No WorldOption.sav is loaded.")

        # Deep-copy the detached dump so validation failures cannot mutate the
        # live in-memory document.
        dumped = copy.deepcopy(self.gvas_file.dump())
        settings = dumped["properties"]["OptionWorldData"]["value"]["Settings"]["value"]

        for key, editor_value in edited_values.items():
            prop = settings.get(key)
            if prop is None:
                continue
            try:
                apply_editor_value(key, prop, editor_value)
            except Exception as exc:
                raise ValueError(f"{key}\n{exc}") from exc

        new_gvas_file = GvasFile.load(dumped)
        new_gvas = new_gvas_file.write({})

        # The edited GVAS must itself be stable under parse -> write before we
        # even attempt container compression.
        require_gvas_roundtrip(new_gvas)

        new_sav = compress_for_source(
            new_gvas, self.original_magic, self.original_save_type
        )

        # Container safety gate: decompress exactly what will be written and
        # require byte-identical GVAS. This catches bad headers/compression.
        check_gvas, _, _ = decompress_sav(new_sav)
        if check_gvas != new_gvas:
            pos = first_difference(new_gvas, check_gvas)
            raise RuntimeError(
                "Save compression verification failed; original file was not modified. "
                f"First GVAS difference: offset {pos}."
            )

        # One final semantic parser gate on the decompressed output.
        check_file = require_gvas_roundtrip(check_gvas)
        return new_sav, check_file, check_gvas

    def save(self, edited_values: dict[str, object]) -> Path:
        if self.path is None:
            raise RuntimeError("No WorldOption.sav is loaded.")

        # Prevent overwriting an in-game autosave that happened after opening.
        current_raw = self.path.read_bytes()
        if self.loaded_hash is not None and sha256_bytes(current_raw) != self.loaded_hash:
            raise ExternalFileChangedError()

        new_sav, new_gvas_file, new_gvas = self.build_save(edited_values)
        backup_path = next_backup_path(self.path)

        # Always preserve the exact pre-save file before replacing it.
        shutil.copy2(self.path, backup_path)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=self.path.name + ".",
                suffix=".tmp",
                dir=self.path.parent,
                delete=False,
            ) as tmp:
                temp_path = Path(tmp.name)
                tmp.write(new_sav)
                tmp.flush()
                os.fsync(tmp.fileno())

            # Re-open the temporary file from disk and validate it once more.
            disk_raw = temp_path.read_bytes()
            disk_gvas, disk_magic, disk_save_type = decompress_sav(disk_raw)
            if disk_gvas != new_gvas:
                raise RuntimeError(
                    "Temporary-file verification failed; original file was not modified."
                )
            require_gvas_roundtrip(disk_gvas)

            os.replace(temp_path, self.path)
            temp_path = None
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        self.gvas_file = new_gvas_file
        self.settings = self.gvas_file.properties["OptionWorldData"]["value"]["Settings"]["value"]
        self.loaded_hash = sha256_bytes(new_sav)
        self.original_magic = disk_magic
        self.original_save_type = disk_save_type
        self.original_gvas = new_gvas
        return backup_path


# -----------------------------------------------------------------------------
# Tk GUI
# -----------------------------------------------------------------------------

class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.doc = WorldOptionDocument()
        self.editors: dict[str, dict] = {}
        self.language_var = tk.StringVar(value=I18N[self.lang]["language_name"])
        self.filter_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self.t("ready"))

        self.geometry("1180x760")
        self.minsize(840, 540)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._configure_fonts()
        self._build_ui()
        self._apply_language()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())

    def t(self, key: str, **kwargs) -> str:
        text = I18N[self.lang].get(key, I18N["en"].get(key, key))
        return text.format(**kwargs) if kwargs else text

    def _configure_fonts(self):
        style = ttk.Style(self)
        # These Windows UI fonts have good native CJK coverage. Tk/Windows will
        # still fall back if a specific font is unavailable.
        font = {
            "en": ("Segoe UI", 10),
            "ja": ("Yu Gothic UI", 10),
            "zh": ("Microsoft YaHei UI", 10),
        }[self.lang]
        style.configure("TLabel", font=font)
        style.configure("TButton", font=font)
        style.configure("TEntry", font=font)
        style.configure("TCheckbutton", font=font)
        style.configure("TCombobox", font=font)
        style.configure("Header.TLabel", font=(font[0], 10, "bold"))

    def _build_ui(self):
        top = ttk.Frame(self, padding=(10, 10, 10, 6))
        top.pack(fill="x")
        top.columnconfigure(2, weight=1)

        self.open_button = ttk.Button(top, command=self.open_file)
        self.open_button.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.save_button = ttk.Button(top, command=self.save_file, state="disabled")
        self.save_button.grid(row=0, column=1, sticky="w", padx=(0, 12))
        self.path_label = ttk.Label(top, anchor="w")
        self.path_label.grid(row=0, column=2, sticky="ew")

        self.language_label = ttk.Label(top)
        self.language_label.grid(row=0, column=3, sticky="e", padx=(12, 6))
        self.language_combo = ttk.Combobox(
            top,
            textvariable=self.language_var,
            values=[I18N[k]["language_name"] for k in ("en", "ja", "zh")],
            state="readonly",
        )
        self.language_combo.grid(row=0, column=4, sticky="ew")
        self.language_combo.bind("<<ComboboxSelected>>", self._language_changed)

        filter_bar = ttk.Frame(self, padding=(10, 4, 10, 6))
        filter_bar.pack(fill="x")
        filter_bar.columnconfigure(1, weight=1)
        self.filter_label = ttk.Label(filter_bar)
        self.filter_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.filter_entry = ttk.Entry(filter_bar, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=1, sticky="ew")
        self.count_label = ttk.Label(filter_bar, anchor="e")
        self.count_label.grid(row=0, column=2, sticky="e", padx=(10, 0))

        table_outer = ttk.Frame(self, padding=(10, 0, 10, 0))
        table_outer.pack(fill="both", expand=True)
        table_outer.rowconfigure(1, weight=1)
        table_outer.columnconfigure(0, weight=1)

        self.header = ttk.Frame(table_outer, padding=(5, 5))
        self.header.grid(row=0, column=0, sticky="ew")
        self._configure_row_columns(self.header)
        self.header_setting = ttk.Label(self.header, style="Header.TLabel", anchor="w")
        self.header_value = ttk.Label(self.header, style="Header.TLabel", anchor="w")
        self.header_type = ttk.Label(self.header, style="Header.TLabel", anchor="w")
        self.header_default = ttk.Label(self.header, style="Header.TLabel", anchor="w")
        self.header_setting.grid(row=0, column=0, sticky="ew", padx=(4, 8))
        self.header_value.grid(row=0, column=1, sticky="ew", padx=8)
        self.header_type.grid(row=0, column=2, sticky="ew", padx=8)
        self.header_default.grid(row=0, column=3, sticky="ew", padx=(8, 4))

        canvas_frame = ttk.Frame(table_outer)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0, borderwidth=0)
        self.vscroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")

        self.inner = ttk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._inner_configured)
        self.canvas.bind("<Configure>", self._canvas_configured)
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        bottom.columnconfigure(1, weight=1)
        self.reset_button = ttk.Button(bottom, command=self.reset_defaults, state="disabled")
        self.reset_button.grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(bottom, textvariable=self.status_var, anchor="w")
        self.status_label.grid(row=0, column=1, sticky="ew", padx=12)
        self.save_button_bottom = ttk.Button(bottom, command=self.save_file, state="disabled")
        self.save_button_bottom.grid(row=0, column=2, sticky="e")

        self.bind("<Control-o>", lambda _e: self.open_file())
        self.bind("<Control-s>", lambda _e: self.save_file())

    @staticmethod
    def _configure_row_columns(frame):
        # No fixed Entry widths: the value column gets the most expansion.
        # This is the main responsive behavior that prevents translated UI text
        # from forcing value boxes off-screen.
        frame.columnconfigure(0, weight=6, minsize=330)
        frame.columnconfigure(1, weight=5, minsize=250)
        frame.columnconfigure(2, weight=2, minsize=110)
        frame.columnconfigure(3, weight=3, minsize=150)

    def _inner_configured(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _canvas_configured(self, event):
        self.canvas.itemconfigure(self.inner_id, width=max(event.width, 1))
        # Let the loaded-path label and per-setting explanations wrap from the
        # actual available pixel width rather than fixed character counts.
        self.path_label.configure(wraplength=max(220, event.width // 2))
        self._update_setting_wraplengths(event.width)

    def _update_setting_wraplengths(self, canvas_width=None):
        if canvas_width is None:
            canvas_width = max(self.canvas.winfo_width(), 840)
        # The setting/description column receives roughly 35-40% of the row.
        # Keeping this pixel-based makes Japanese and Chinese text reflow when
        # the window is resized or the UI language changes.
        wrap = max(250, min(560, int(canvas_width * 0.36)))
        for entry in self.editors.values():
            entry["name_label"].configure(wraplength=wrap)
            entry["key_label"].configure(wraplength=wrap)
            entry["desc_label"].configure(wraplength=wrap)

    def _mousewheel(self, event):
        if self.canvas.winfo_ismapped():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _language_changed(self, _event=None):
        self.lang = LANGUAGE_BY_LABEL.get(self.language_var.get(), "en")
        self._configure_fonts()
        self._apply_language()

    def _apply_language(self):
        self.title(self.t("title"))
        self.open_button.configure(text=self.t("open"))
        self.save_button.configure(text=self.t("save"))
        self.save_button_bottom.configure(text=self.t("save"))
        self.reset_button.configure(text=self.t("reset"))
        self.language_label.configure(text=self.t("language"))
        self.filter_label.configure(text=self.t("filter"))
        self.header_setting.configure(text=self.t("setting"))
        self.header_value.configure(text=self.t("value"))
        self.header_type.configure(text=self.t("type"))
        self.header_default.configure(text=self.t("default"))

        if self.doc.path is None:
            self.path_label.configure(text=self.t("no_file"))
        else:
            self.path_label.configure(
                text=self.t("loaded", count=len(self.editors), path=str(self.doc.path))
            )

        for key, entry in self.editors.items():
            entry["type_label"].configure(text=self.t(entry["kind"]))
            display_name, description = setting_meta(key, self.lang)
            entry["name_label"].configure(text=display_name)
            entry["desc_label"].configure(text=description)
        self._update_setting_wraplengths()
        self._apply_filter()

    def _clear_rows(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self.editors.clear()

    def _add_setting_row(self, key: str, prop: dict, row_index: int):
        row = ttk.Frame(self.inner, padding=(5, 4))
        row.grid(row=row_index, column=0, sticky="ew")
        self.inner.columnconfigure(0, weight=1)
        self._configure_row_columns(row)

        setting_box = ttk.Frame(row)
        setting_box.grid(row=0, column=0, sticky="nsew", padx=(4, 8))
        setting_box.columnconfigure(0, weight=1)

        display_name, description = setting_meta(key, self.lang)
        name_label = ttk.Label(
            setting_box, text=display_name, style="Header.TLabel", anchor="w", justify="left"
        )
        name_label.grid(row=0, column=0, sticky="ew")
        key_label = ttk.Label(setting_box, text=key, anchor="w", justify="left")
        key_label.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        desc_label = ttk.Label(
            setting_box, text=description, anchor="w", justify="left"
        )
        desc_label.grid(row=2, column=0, sticky="ew", pady=(2, 1))

        kind = property_kind(prop)
        current = display_value(prop)

        if kind == "bool":
            var = tk.BooleanVar(value=bool(current))
            widget = ttk.Checkbutton(row, variable=var)
            widget.grid(row=0, column=1, sticky="w", padx=8)
        elif kind == "enum" and key in ENUM_CHOICES:
            var = tk.StringVar(value=str(current))
            widget = ttk.Combobox(
                row,
                textvariable=var,
                values=ENUM_CHOICES[key],
                state="normal",
            )
            widget.grid(row=0, column=1, sticky="ew", padx=8)
        else:
            var = tk.StringVar(value=str(current))
            widget = ttk.Entry(row, textvariable=var)
            widget.grid(row=0, column=1, sticky="ew", padx=8)

        type_label = ttk.Label(row, text=self.t(kind), anchor="w")
        type_label.grid(row=0, column=2, sticky="ew", padx=8)

        default = default_for_key(key)
        default_label = ttk.Label(
            row,
            text=format_default(default) if default is not None else self.t("unknown_default"),
            anchor="w",
            justify="left",
        )
        default_label.grid(row=0, column=3, sticky="ew", padx=(8, 4))

        self.editors[key] = {
            "row": row,
            "kind": kind,
            "var": var,
            "name_label": name_label,
            "key_label": key_label,
            "desc_label": desc_label,
            "type_label": type_label,
            "default_label": default_label,
            "prop_type": prop.get("type", ""),
        }
        self._update_setting_wraplengths()

    def _populate(self):
        self._clear_rows()
        for idx, (key, prop) in enumerate(self.doc.settings.items()):
            self._add_setting_row(key, prop, idx)
        self._apply_filter()
        self.canvas.yview_moveto(0)

    def _apply_filter(self):
        needle = self.filter_var.get().strip().casefold()
        shown = 0
        for key, entry in self.editors.items():
            localized_bits = []
            for language in ("en", "ja", "zh"):
                name, description = setting_meta(key, language)
                localized_bits.extend((name, description))
            haystack = " ".join(
                [key, entry["prop_type"], entry["kind"], *localized_bits]
            ).casefold()
            if not needle or needle in haystack:
                entry["row"].grid()
                shown += 1
            else:
                entry["row"].grid_remove()
        total = len(self.editors)
        self.count_label.configure(text=self.t("filter_count", shown=shown, total=total))
        self.after_idle(self._inner_configured)

    def open_file(self):
        initialdir = DEFAULT_SAVE_ROOT if DEFAULT_SAVE_ROOT.exists() else DEFAULT_SAVE_ROOT.parent
        path = filedialog.askopenfilename(
            parent=self,
            title=self.t("open"),
            initialdir=str(initialdir),
            initialfile=SAVE_FILENAME,
            filetypes=[("WorldOption.sav", "WorldOption.sav")],
        )
        if not path:
            return
        if Path(path).name.casefold() != SAVE_FILENAME.casefold():
            messagebox.showerror(self.t("load_error_title"), self.t("invalid_name"), parent=self)
            return

        try:
            self.doc.load(path)
        except SaveFormatError as exc:
            if str(exc) == "PYOOZ_REQUIRED":
                detail = self.t("need_pyooz")
            else:
                detail = str(exc)
            messagebox.showerror(self.t("load_error_title"), detail, parent=self)
            return
        except ValueError as exc:
            detail = self.t("invalid_name") if str(exc) == "INVALID_NAME" else self.t("invalid_worldoption")
            messagebox.showerror(self.t("load_error_title"), detail, parent=self)
            return
        except Exception as exc:
            messagebox.showerror(self.t("load_error_title"), str(exc), parent=self)
            return

        self._populate()
        self.path_label.configure(
            text=self.t("loaded", count=len(self.editors), path=str(self.doc.path))
        )
        self.status_var.set(self.t("ready"))
        self.save_button.configure(state="normal")
        self.save_button_bottom.configure(state="normal")
        self.reset_button.configure(state="normal")

    def _collect_values(self) -> dict[str, object]:
        values = {}
        for key, entry in self.editors.items():
            values[key] = entry["var"].get()
        return values

    def save_file(self):
        if self.doc.path is None:
            return
        try:
            backup = self.doc.save(self._collect_values())
        except ExternalFileChangedError:
            messagebox.showerror(
                self.t("save_error_title"), self.t("external_change"), parent=self
            )
            return
        except ValueError as exc:
            text = str(exc)
            if "\n" in text:
                key, detail = text.split("\n", 1)
                text = self.t("invalid_value", key=key, detail=detail)
            messagebox.showerror(self.t("save_error_title"), text, parent=self)
            return
        except Exception as exc:
            messagebox.showerror(self.t("save_error_title"), str(exc), parent=self)
            return

        # Re-read the serialized values so the UI reflects normalized numbers,
        # enum prefixes, or other representation changes after a save.
        self._populate()
        self.path_label.configure(
            text=self.t("loaded", count=len(self.editors), path=str(self.doc.path))
        )
        self.status_var.set(self.t("ready"))
        messagebox.showinfo(
            self.t("saved_title"),
            self.t("saved", backup=str(backup)),
            parent=self,
        )

    def reset_defaults(self):
        if self.doc.path is None:
            return
        if not messagebox.askyesno(
            self.t("reset_title"), self.t("reset_confirm"), parent=self
        ):
            return

        for key, entry in self.editors.items():
            default = default_for_key(key)
            if default is None:
                continue
            if entry["kind"] == "bool":
                entry["var"].set(bool(default))
            elif isinstance(default, list):
                entry["var"].set(", ".join(map(str, default)))
            else:
                entry["var"].set(str(default))
        self.status_var.set(self.t("reset_done"))


def dependency_check() -> bool:
    if GvasFile is not None:
        return True
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        I18N["en"]["missing_dependency_title"],
        I18N["en"]["missing_dependency"],
        parent=root,
    )
    root.destroy()
    return False


def main():
    if not dependency_check():
        return 1
    app = EditorApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
