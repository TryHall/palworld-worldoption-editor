#!/usr/bin/env python3
"""
Palworld WorldOption editor

Requirements:
    python -m pip install palworld-save-tools pyooz

This revision focuses on:
- modern three-pane desktop UI with direct inline value editing;
- category navigation, settings list, and focused inspector instead of dense per-row widgets;
- MIN/MAX/recommended guidance from current 3DM and Pocketpair references;
- background file loading/saving to keep the UI responsive;
- cached multilingual search data;
- English, Japanese and Simplified Chinese setting explanations;
- Chinese terminology aligned with the 3DM Palworld configuration reference
  where a documented equivalent exists;
- Japanese terminology aligned with Pocketpair's current Japanese server guide
  where a documented equivalent exists;
- sequential backups and save validation.

The save path follows Dehmahk/Palworld-WorldOption-Editor:
PlM/Oodle input is decoded with pyooz and written as a Palworld-compatible
classic PlZ container. Existing PlZ2 input remains PlZ2.

License (MIT):

    Copyright (c) 2026 TryHall

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import zlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from palworld_save_tools.gvas import GvasFile
except Exception:
    GvasFile = None

try:
    from ooz import decompress as _ooz_decompress
except Exception:
    _ooz_decompress = None

APP_NAME = "Palworld WorldOption Editor"
APP_VERSION = "1.1.0"
APP_COPYRIGHT = "\u00a9 2026 TryHall"
SAVE_FILENAME = "WorldOption.sav"
DEFAULT_SAVE_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Pal" / "Saved" / "SaveGames"
ICON_FILENAME = "LOGO.ico"


def _resource_path(relative):
    """Return the absolute path to a bundled resource file.

    In a PyInstaller onefile build, extra data files are unpacked to a
    temporary directory exposed as ``sys._MEIPASS``; when running straight
    from source, they live next to this script.
    """
    base = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parent))
    return str(Path(base) / relative)

DEFAULTS = {'Difficulty': 'None',
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
 'EquipmentDurabilityDamageRate': 1.0,
 'ItemWeightRate': 1.0,
 'ItemCorruptionMultiplier': 1.0,
 'DeathPenalty': 'All',
 'bEnablePlayerToPlayerDamage': False,
 'bEnableFriendlyFire': False,
 'bEnableInvaderEnemy': True,
 'bActiveUNKO': False,
 'bEnableAimAssistPad': True,
 'bEnableAimAssistKeyboard': False,
 'DropItemMaxNum': 3000,
 'PhysicsActiveDropItemMaxNum': -1,
 'DropItemMaxNum_UNKO': 100,
 'DropItemAliveMaxHours': 1.0,
 'BaseCampMaxNum': 128,
 'BaseCampMaxNumInGuild': 4,
 'BaseCampWorkerMaxNum': 15,
 'bAutoResetGuildNoOnlinePlayers': False,
 'AutoResetGuildTimeNoOnlinePlayers': 72.0,
 'GuildPlayerMaxNum': 20,
 'GuildRejoinCooldownMinutes': 0,
 'PalEggDefaultHatchingTime': 72.0,
 'WorkSpeedRate': 1.0,
 'bIsMultiplay': False,
 'bIsPvP': False,
 'bCanPickupOtherGuildDeathPenaltyDrop': False,
 'bEnableNonLoginPenalty': True,
 'bEnableFastTravel': True,
 'bEnableFastTravelOnlyBaseCamp': False,
 'bIsStartLocationSelectByMap': True,
 'bExistPlayerAfterLogout': False,
 'bEnableDefenseOtherGuildPlayer': False,
 'bInvisibleOtherGuildBaseCampAreaFX': False,
 'bBuildAreaLimit': True,
 'bHardcore': False,
 'bPalLost': False,
 'bCharacterRecreateInHardcore': False,
 'bAllowGlobalPalboxExport': False,
 'bAllowGlobalPalboxImport': False,
 'bAllowEnhanceStat_Health': True,
 'bAllowEnhanceStat_Stamina': True,
 'bAllowEnhanceStat_Attack': True,
 'bAllowEnhanceStat_WorkSpeed': True,
 'bAllowEnhanceStat_Weight': True,
 'EnablePredatorBossPal': True,
 'MaxBuildingLimitNum': 0,
 'ServerReplicatePawnCullDistance': 15000.0,
 'ItemContainerForceMarkDirtyInterval': 1.0,
 'CoopPlayerMaxNum': 4,
 'ServerPlayerMaxNum': 32,
 'ServerName': 'Default Palworld Server',
 'ServerDescription': '',
 'AdminPassword': '',
 'ServerPassword': '',
 'PublicPort': 8211,
 'PublicIP': '',
 'RCONEnabled': False,
 'RCONPort': 25575,
 'RESTAPIEnabled': False,
 'RESTAPIPort': 8212,
 'bShowPlayerList': False,
 'CrossplayPlatforms': ['Steam', 'Xbox', 'PS5', 'Mac'],
 'bAllowClientMod': False,
 'LogFormatType': 'Text',
 'ChatPostLimitPerMinute': 10,
 'bIsShowJoinLeftMessage': True,
 'bIsUseBackupSaveData': True,
 'Region': '',
 'bUseAuth': True,
 'BanListURL': 'https://api.palworldgame.com/api/banlist.txt',
 'SupplyDropSpan': 180,
 'bDisplayPvPItemNumOnWorldMap_Player': False,
 'bDisplayPvPItemNumOnWorldMap_BaseCamp': False,
 'BlockRespawnTime': 0.0,
 'RespawnPenaltyTimeScale': 1.0,
 'RespawnPenaltyDurationThreshold': 0.0,
 'bAdditionalDropItemWhenPlayerKillingInPvPMode': False,
 'AdditionalDropItemWhenPlayerKillingInPvPMode': '',
 'AdditionalDropItemNumWhenPlayerKillingInPvPMode': 1,
 'DenyTechnologyList': [],
 'bEnableVoiceChat': False,
 'VoiceChatMaxVolumeDistance': 3000.0,
 'VoiceChatZeroVolumeDistance': 15000.0,
 'MonsterFarmActionSpeedRate': 1.0,
 'AutoSaveSpan': 30.0,
 'autoSaveSpan': 30.0,
 'PlayerDataPalStorageUpdateCheckTickInterval': 1.0,
 'AutoTransferMasterCheckIntervalSeconds': 3600.0,
 'AutoTransferMasterThresholdDays': 14,
 'MaxGuildsPerFrame': 10,
 'bEnableBuildingPlayerUIdDisplay': False,
 'BuildingNameDisplayCacheTTLSeconds': 60}
ZH_META = {'Difficulty': ('难度', '世界难度设置。None 为普通默认难度；请以当前游戏版本实际可用枚举值为准。'),
 'DayTimeSpeedRate': ('白天流逝速度倍率', '数值越大，白天时间流逝越快。'),
 'NightTimeSpeedRate': ('夜晚流逝速度倍率', '数值越大，夜晚时间流逝越快。'),
 'ExpRate': ('经验值倍率', '影响获得经验值的倍率；提高后升级更快。'),
 'PalCaptureRate': ('帕鲁捕获倍率', '影响帕鲁捕获概率；提高后更容易捕捉。'),
 'PalSpawnNumRate': ('帕鲁出现数量倍率', '影响帕鲁出现数量；提高会明显增加服务器负载。'),
 'PalDamageRateAttack': ('帕鲁攻击伤害倍率', '影响帕鲁造成的伤害。'),
 'PalDamageRateDefense': ('帕鲁承受伤害倍率', '数值越高，帕鲁受到的伤害越高。'),
 'PlayerDamageRateAttack': ('玩家攻击伤害倍率', '影响玩家造成的伤害。'),
 'PlayerDamageRateDefense': ('玩家承受伤害倍率', '数值越高，玩家受到的伤害越高。'),
 'PlayerStomachDecreaceRate': ('玩家饱食度降低倍率', '数值越高，玩家越容易饥饿。'),
 'PlayerStaminaDecreaceRate': ('玩家耐力消耗倍率', '数值越高，玩家耐力消耗越快。'),
 'PlayerAutoHPRegeneRate': ('玩家生命自然恢复倍率', '影响玩家非睡眠状态下的生命恢复速度。'),
 'PlayerAutoHpRegeneRateInSleep': ('玩家睡眠生命恢复倍率', '影响玩家睡眠时的生命恢复速度。'),
 'PalStomachDecreaceRate': ('帕鲁饱食度降低倍率', '数值越高，帕鲁越容易饥饿。'),
 'PalStaminaDecreaceRate': ('帕鲁耐力消耗倍率', '数值越高，帕鲁耐力消耗越快。'),
 'PalAutoHPRegeneRate': ('帕鲁生命自然恢复倍率', '影响帕鲁平时的生命恢复速度。'),
 'PalAutoHpRegeneRateInSleep': ('帕鲁睡眠生命恢复倍率', '影响帕鲁在终端内休息时的生命恢复速度。'),
 'BuildObjectDamageRate': ('建筑伤害倍率', '影响建筑受到攻击时的伤害倍率。'),
 'BuildObjectHpRate': ('建筑耐久倍率', '影响建筑物生命值；数值越高越耐久。'),
 'BuildObjectDeteriorationDamageRate': ('建筑劣化速度倍率', '影响建筑自然劣化速度；0 通常表示不劣化。'),
 'CollectionDropRate': ('采集物掉落倍率', '影响矿石、木材等采集产出数量。'),
 'CollectionObjectHpRate': ('采集物生命值倍率', '影响矿石、树木等可采集对象的耐久。'),
 'CollectionObjectRespawnSpeedRate': ('采集物刷新间隔倍率', '影响采集物刷新间隔；通常数值越低刷新越快。'),
 'EnemyDropItemRate': ('敌人掉落物数量倍率', '影响击败敌人后的物品掉落数量。'),
 'EquipmentDurabilityDamageRate': ('装备耐久损耗倍率', '数值越高，装备耐久消耗越快。'),
 'ItemWeightRate': ('物品重量倍率', '影响背包负重压力；数值越低物品越轻。'),
 'ItemCorruptionMultiplier': ('物品腐坏速度倍率', '影响食物等物品的腐坏速度。'),
 'DeathPenalty': ('死亡惩罚', 'None 不掉落；Item 掉落装备以外物品；ItemAndEquipment 掉落物品和装备；All 还会包含队伍帕鲁。'),
 'bEnablePlayerToPlayerDamage': ('玩家互相伤害', '开启后允许玩家对玩家造成伤害。'),
 'bEnableFriendlyFire': ('友军伤害', '开启后允许对同伴或友方目标造成伤害。'),
 'bEnableInvaderEnemy': ('袭击事件', '控制是否启用基地袭击事件。'),
 'bActiveUNKO': ('UNKO 功能', '保留项或特殊功能开关；通常保持默认值。'),
 'bEnableAimAssistPad': ('手柄瞄准辅助', '控制手柄辅助瞄准。'),
 'bEnableAimAssistKeyboard': ('键鼠瞄准辅助', '控制键盘鼠标辅助瞄准。'),
 'DropItemMaxNum': ('掉落物最大数量', '世界中可存在的掉落物数量上限；过高可能影响性能。'),
 'DropItemMaxNum_UNKO': ('UNKO 掉落物最大数量', '相关特殊掉落物数量上限；通常保持默认值。'),
 'DropItemAliveMaxHours': ('掉落物保留时间', '掉落物在世界中保留的时间，单位为小时。'),
 'BaseCampMaxNum': ('据点总数量上限', '全服务器可存在的据点总数量。'),
 'BaseCampMaxNumInGuild': ('每个公会据点数量上限', '每个公会允许拥有的据点数量上限；提高会增加服务器负载。'),
 'BaseCampWorkerMaxNum': ('每个据点工作帕鲁数量上限', '每个据点可工作的帕鲁数量上限；官方上限为 50，提高会增加负载。'),
 'bAutoResetGuildNoOnlinePlayers': ('自动清理离线公会', '开启后，长期无人上线的公会会被自动重置。'),
 'AutoResetGuildTimeNoOnlinePlayers': ('离线公会自动清理时间', '触发离线公会自动清理前的离线时长，单位为小时。'),
 'GuildPlayerMaxNum': ('公会玩家人数上限', '每个公会允许的玩家人数上限。'),
 'GuildRejoinCooldownMinutes': ('重新加入公会冷却', '限制频繁退会再入会的冷却时间，单位为分钟。'),
 'PalEggDefaultHatchingTime': ('巨大帕鲁蛋默认孵化时间', '巨大帕鲁蛋的默认孵化时间，单位为小时；其他蛋也会受到孵化时间影响。'),
 'WorkSpeedRate': ('工作速度倍率', '影响据点生产、建造等工作的效率。'),
 'bIsMultiplay': ('多人游戏', '多人游戏相关开关；专用服务器通常由程序自动处理。'),
 'bIsPvP': ('PvP 开关', '开启玩家对战模式。'),
 'bCanPickupOtherGuildDeathPenaltyDrop': ('拾取其他公会死亡掉落', '开启后允许拾取其他公会玩家的死亡掉落物。'),
 'bEnableNonLoginPenalty': ('离线惩罚', '控制长时间不登录相关惩罚。'),
 'bEnableFastTravel': ('快速旅行', '控制是否允许快速旅行。'),
 'bEnableFastTravelOnlyBaseCamp': ('仅限据点快速旅行', '开启后将快速旅行限制在据点之间。'),
 'bIsStartLocationSelectByMap': ('地图选择出生点', '允许新角色在地图上选择起始位置。'),
 'bExistPlayerAfterLogout': ('登出后保留角色', '开启后玩家下线后角色仍会留在世界中。'),
 'bEnableDefenseOtherGuildPlayer': ('防御其他公会玩家', '与公会间防御行为有关的设置。'),
 'bInvisibleOtherGuildBaseCampAreaFX': ('隐藏其他公会据点范围特效', '开启后不显示其他公会据点边界效果。'),
 'bBuildAreaLimit': ('建筑区域限制', '限制在传送点等特殊区域附近建造。'),
 'bHardcore': ('硬核模式', '开启后死亡将无法正常重生，请谨慎修改。'),
 'bPalLost': ('死亡丢失帕鲁', '开启后死亡会永久失去相关帕鲁，请谨慎修改。'),
 'bCharacterRecreateInHardcore': ('硬核模式角色重建', '控制硬核死亡后是否允许重建角色。'),
 'bAllowGlobalPalboxExport': ('允许导出全局帕鲁终端', '允许将帕鲁保存到 Global Palbox。'),
 'bAllowGlobalPalboxImport': ('允许导入全局帕鲁终端', '允许从 Global Palbox 载入帕鲁。'),
 'bAllowEnhanceStat_Health': ('允许强化生命属性', '允许玩家将属性点分配到生命值。'),
 'bAllowEnhanceStat_Stamina': ('允许强化耐力属性', '允许玩家将属性点分配到耐力。'),
 'bAllowEnhanceStat_Attack': ('允许强化攻击属性', '允许玩家将属性点分配到攻击。'),
 'bAllowEnhanceStat_WorkSpeed': ('允许强化工作速度属性', '允许玩家将属性点分配到工作速度。'),
 'bAllowEnhanceStat_Weight': ('允许强化负重属性', '允许玩家将属性点分配到负重。'),
 'EnablePredatorBossPal': ('掠食者 Boss 帕鲁', '控制相关掠食者 Boss 帕鲁是否出现。'),
 'MaxBuildingLimitNum': ('玩家建筑数量上限', '限制单个玩家可建建筑数；0 表示无限制。'),
 'ServerReplicatePawnCullDistance': ('帕鲁同步距离', '服务器向玩家同步帕鲁的距离，单位为厘米。'),
 'ItemContainerForceMarkDirtyInterval': ('容器强制同步间隔', '打开容器时强制重新同步的间隔，单位为秒。'),
 'CoopPlayerMaxNum': ('合作模式人数上限', '普通合作房间允许的最大玩家人数。'),
 'ServerPlayerMaxNum': ('服务器玩家人数上限', '专用服务器允许连接的最大玩家人数。'),
 'ServerName': ('服务器名称', '显示在服务器列表或连接信息中的名称。'),
 'ServerDescription': ('服务器描述', '服务器简介、公告或说明文本。'),
 'AdminPassword': ('管理员密码', '用于通过 /AdminPassword 获取管理员权限的密码。'),
 'ServerPassword': ('服务器密码', '玩家加入服务器时需要输入的密码；留空表示无密码。'),
 'PublicPort': ('公网端口', '社区服务器对外显示端口；不会改变实际监听端口。'),
 'PublicIP': ('公网 IP', '社区服务器的公网地址；留空时通常自动检测。'),
 'RCONEnabled': ('RCON 开关', '控制是否启用远程控制台。'),
 'RCONPort': ('RCON 端口', '远程控制台使用的连接端口。'),
 'RESTAPIEnabled': ('REST API 开关', '控制是否启用官方 REST API。'),
 'RESTAPIPort': ('REST API 端口', 'REST API 的监听端口。'),
 'bShowPlayerList': ('显示玩家列表', '开启后在 ESC 菜单显示玩家列表。'),
 'CrossplayPlatforms': ('跨平台连接列表', '允许连接服务器的平台列表，例如 Steam、Xbox、PS5、Mac。'),
 'bAllowClientMod': ('允许客户端 Mod', '开启后允许启用了 Mod 的玩家加入。'),
 'LogFormatType': ('日志格式', '服务器日志格式；Text 为文本，Json 为 JSON。'),
 'ChatPostLimitPerMinute': ('每分钟聊天次数上限', '限制玩家每分钟发送聊天消息的次数。'),
 'SupplyDropSpan': ('陨石和补给掉落间隔', '陨石和补给投放事件的间隔，单位为分钟。'),
 'RandomizerType': ('帕鲁随机模式', 'None 不随机；Region 按地区随机；All 全部随机。'),
 'RandomizerSeed': ('随机种子', '启用随机模式时用于固定随机结果。'),
 'bIsRandomizerPalLevelRandom': ('随机帕鲁等级', '开启后野生帕鲁等级完全随机；关闭后按区域范围随机。'),
 'bDisplayPvPItemNumOnWorldMap_Player': ('地图显示玩家 PvP 物品数', '控制世界地图上的玩家 PvP 物品数量显示。'),
 'bDisplayPvPItemNumOnWorldMap_BaseCamp': ('地图显示据点 PvP 物品数', '控制世界地图上的据点 PvP 物品数量显示。'),
 'BlockRespawnTime': ('死亡后复活冷却', '死亡后再次复活前的冷却时间，单位为秒。'),
 'RespawnPenaltyTimeScale': ('复活惩罚时间倍率', '影响连续死亡等条件下的复活冷却倍率。'),
 'RespawnPenaltyDurationThreshold': ('复活惩罚判定时间', '用于判断是否触发复活惩罚倍率的时间阈值，单位为秒。'),
 'bAdditionalDropItemWhenPlayerKillingInPvPMode': ('PvP 击杀额外掉落', '开启后 PvP 击杀会掉落指定额外物品。'),
 'AdditionalDropItemWhenPlayerKillingInPvPMode': ('PvP 击杀额外掉落物 ID', '配合 PvP 击杀额外掉落开关使用。'),
 'AdditionalDropItemNumWhenPlayerKillingInPvPMode': ('PvP 击杀额外掉落数量', '配置 PvP 击杀额外掉落物的数量。'),
 'DenyTechnologyList': ('禁用科技列表', '填写科技 ID 以禁用指定科技。'),
 'BanListURL': ('封禁名单地址', '服务器读取的封禁名单 URL。'),
 'bEnableVoiceChat': ('语音聊天', '控制是否启用游戏内语音聊天。'),
 'VoiceChatMaxVolumeDistance': ('语音聊天满音量距离', '在此距离内语音聊天音量不会衰减。'),
 'VoiceChatZeroVolumeDistance': ('语音聊天静音距离', '达到此距离时语音聊天音量降为零。'),
 'MonsterFarmActionSpeedRate': ('牧场生产速度倍率', '影响放牧/牧场活动的物品生产速度。'),
 'bIsUseBackupSaveData': ('世界备份', '启用游戏自带的世界备份；开启后会增加磁盘负载。'),
 'bIsShowJoinLeftMessage': ('加入/离开消息', '在专用服务器中显示玩家加入和离开的游戏内消息。'),
 'bEnableBuildingPlayerUIdDisplay': ('显示建筑创建者 ID', '在建筑物上显示创建者的玩家 ID。')}
JA_META = {'BaseCampMaxNum': ('サーバー全体の拠点数', 'サーバー全体で存在できる拠点数です。'),
 'BaseCampMaxNumInGuild': ('ギルド当たりの最大拠点数', 'ギルド当たりの最大拠点数です。値を大きくするほど処理負荷が増大します。'),
 'BaseCampWorkerMaxNum': ('拠点当たりの最大パル数', '1拠点で働けるパルの最大数です。最大50。値を大きくするほど処理負荷が増大します。'),
 'ItemContainerForceMarkDirtyInterval': ('コンテナ強制再同期間隔', 'コンテナを開いている際に強制的に同期しなおす頻度（秒）です。'),
 'MaxBuildingLimitNum': ('プレイヤーごとの建築物数制限', 'プレイヤーごとの建築物数上限です。0 は無制限です。'),
 'PhysicsActiveDropItemMaxNum': ('物理挙動するドロップアイテム上限', '物理挙動を行うドロップアイテム数の上限です。'),
 'ServerReplicatePawnCullDistance': ('パル同期距離', 'プレイヤーからのパルの同期距離（cm）です。'),
 'AdminPassword': ('管理者パスワード', 'サーバーの管理者権限を取得するためのパスワードです。'),
 'bAllowClientMod': ('Mod利用者の参加を許可', 'Modを有効化しているユーザーのサーバー参加を許可するかを設定します。'),
 'bEnableBuildingPlayerUIdDisplay': ('建築物に作成者IDを表示', '建築物上に作成者のプレイヤーIDを表示するかを設定します。'),
 'bIsShowJoinLeftMessage': ('参加・退出メッセージ', '専用サーバーでプレイヤーの参加・退出時にゲーム内メッセージを表示します。'),
 'bIsUseBackupSaveData': ('ワールドバックアップ', 'ワールドバックアップを有効化します。有効化するとディスク負荷が高まります。'),
 'ChatPostLimitPerMinute': ('1分間のチャット投稿上限', '1分間に投稿可能なチャット数です。'),
 'CrossplayPlatforms': ('接続を許可するプラットフォーム', 'サーバーへの接続を許可するプラットフォームの一覧です。'),
 'LogFormatType': ('ログフォーマット', 'サーバーログの形式を Text または Json から指定します。'),
 'PublicIP': ('外部公開IP', 'コミュニティサーバーで外部公開IPを明示的に指定します。'),
 'PublicPort': ('外部公開ポート', 'コミュニティサーバーで外部公開ポートを指定します。待ち受けポート自体は変更しません。'),
 'RCONEnabled': ('RCONを有効化', 'RCONを有効にします。'),
 'RCONPort': ('RCONポート', 'RCONで使用するポート番号です。'),
 'RESTAPIEnabled': ('REST APIを有効化', 'REST APIを有効にします。'),
 'RESTAPIPort': ('REST APIポート', 'REST APIの待ち受けポートです。'),
 'ServerDescription': ('サーバー説明', 'サーバーの説明文です。'),
 'ServerName': ('サーバー名', 'サーバー名です。'),
 'ServerPassword': ('サーバーパスワード', 'サーバーへのログインに必要なパスワードです。'),
 'ServerPlayerMaxNum': ('サーバー最大参加人数', 'サーバーに参加できる最大人数です。'),
 'AutoResetGuildTimeNoOnlinePlayers': ('ギルド自動削除までのオフライン時間', 'bAutoResetGuildNoOnlinePlayers が有効な場合に使われるオフライン時間です。'),
 'bAllowEnhanceStat_Attack': ('「攻撃」へのステータス割り当て', '「攻撃」へのステータスポイント割り当てを許可します。'),
 'bAllowEnhanceStat_Health': ('「HP」へのステータス割り当て', '「HP」へのステータスポイント割り当てを許可します。'),
 'bAllowEnhanceStat_Stamina': ('「スタミナ」へのステータス割り当て', '「スタミナ」へのステータスポイント割り当てを許可します。'),
 'bAllowEnhanceStat_Weight': ('「所持重量」へのステータス割り当て', '「所持重量」へのステータスポイント割り当てを許可します。'),
 'bAllowEnhanceStat_WorkSpeed': ('「作業速度」へのステータス割り当て', '「作業速度」へのステータスポイント割り当てを許可します。'),
 'bAllowGlobalPalboxExport': ('グローバルパルボックスへの保存', 'グローバルパルボックスへの保存を許可します。'),
 'bAllowGlobalPalboxImport': ('グローバルパルボックスからの読込', 'グローバルパルボックスからの読込を許可します。'),
 'bAutoResetGuildNoOnlinePlayers': ('無人ギルドの自動削除', 'ギルドメンバーが誰もログインしない状態が続いた場合、建築物と拠点パルを自動削除します。'),
 'bBuildAreaLimit': ('建築エリア制限', 'ファストトラベル地点などの近くで建築できないようにします。'),
 'bCharacterRecreateInHardcore': ('ハードコア死亡後のキャラクター再作成', 'ハードコアモードで死亡後にキャラクターを再作成できるかを設定します。'),
 'bDisplayPvPItemNumOnWorldMap_BaseCamp': ('マップに拠点PvPアイテム数を表示', '各拠点のPvP専用アイテム数をマップに表示します。'),
 'bDisplayPvPItemNumOnWorldMap_Player': ('マップにプレイヤーPvP情報を表示', 'プレイヤー位置とPvP専用アイテム数をマップに表示します。'),
 'bEnableFastTravel': ('ファストトラベル', 'ファストトラベルを有効にします。'),
 'bEnableFastTravelOnlyBaseCamp': ('拠点間のみファストトラベル', 'ファストトラベルを拠点間のみに制限します。'),
 'bEnableInvaderEnemy': ('襲撃イベント', '襲撃イベントを有効にします。'),
 'bEnableVoiceChat': ('ボイスチャット', 'ゲーム内ボイスチャットを有効にします。'),
 'bExistPlayerAfterLogout': ('ログアウト後もプレイヤーを残す', 'ログアウト時に現在位置で睡眠状態として残るかを設定します。'),
 'bHardcore': ('ハードコア', 'ハードコアを有効にします。死亡後に通常のリスポーンができなくなります。'),
 'bInvisibleOtherGuildBaseCampAreaFX': ('拠点エリア境界表示', '他ギルドの拠点エリア境界表示に関する設定です。'),
 'bIsPvP': ('PvP', 'PvPを有効にします。'),
 'bIsRandomizerPalLevelRandom': ('野生パルのレベルを完全ランダム化', 'True なら完全ランダム、False なら各エリアの想定範囲内でランダム化します。'),
 'bIsStartLocationSelectByMap': ('開始地点を選択', 'プレイヤーが開始地点を選択できるかを設定します。'),
 'bShowPlayerList': ('プレイヤーリスト', 'ESCメニューのプレイヤーリストを有効にします。'),
 'RandomizerSeed': ('ランダムシード', 'パル出現ランダムモードで使用するシード値です。'),
 'RandomizerType': ('パル出現ランダムモード', 'None=なし、Region=地域ごと、All=完全ランダムです。'),
 'VoiceChatMaxVolumeDistance': ('ボイスチャット最大音量距離', 'ボイスチャット音量が減衰しない距離です。'),
 'VoiceChatZeroVolumeDistance': ('ボイスチャット無音距離', 'ボイスチャット音量が0になる距離です。'),
 'AdditionalDropItemNumWhenPlayerKillingInPvPMode': ('PvPキル追加ドロップ数', 'PvPキル追加ドロップが有効な場合のドロップ数量です。'),
 'AdditionalDropItemWhenPlayerKillingInPvPMode': ('PvPキル追加ドロップID', 'PvPキル追加ドロップが有効な場合に落とすアイテムIDです。'),
 'bAdditionalDropItemWhenPlayerKillingInPvPMode': ('PvPキル追加ドロップ', 'PvP有効時にプレイヤーが倒された際、専用アイテムをドロップするかを設定します。'),
 'BlockRespawnTime': ('リスポーンクールタイム', '死亡後に再びリスポーンできるまでのクールタイム（秒）です。'),
 'bPalLost': ('死亡時のパルロスト', '死亡時にパルを永久に失う設定です。'),
 'BuildObjectDamageRate': ('建築物へのダメージ倍率', '建築物が受けるダメージ倍率です。'),
 'BuildObjectDeteriorationDamageRate': ('建築物の劣化速度倍率', '建築物の劣化速度倍率です。'),
 'CollectionDropRate': ('採集アイテム倍率', '採集で得られるアイテム量の倍率です。'),
 'CollectionObjectHpRate': ('採集オブジェクトHP倍率', '採集オブジェクトのHP倍率です。'),
 'CollectionObjectRespawnSpeedRate': ('採集オブジェクト再生成間隔', '採集オブジェクトの再生成間隔に関する倍率です。'),
 'DayTimeSpeedRate': ('昼の経過速度', '昼時間の進行速度です。'),
 'DeathPenalty': ('死亡ペナルティ', '死亡時に失うアイテム・装備・手持ちパルを設定します。'),
 'DenyTechnologyList': ('無効化するテクノロジー', '指定したテクノロジーIDを無効化します。'),
 'EnemyDropItemRate': ('敵ドロップアイテム量倍率', '敵が落とすアイテム量の倍率です。'),
 'EquipmentDurabilityDamageRate': ('装備耐久度減少倍率', '装備の耐久度減少倍率です。'),
 'ExpRate': ('経験値倍率', '獲得経験値の倍率です。'),
 'GuildPlayerMaxNum': ('ギルド最大人数', 'ギルドの最大プレイヤー数です。'),
 'GuildRejoinCooldownMinutes': ('ギルド再加入クールタイム', 'ギルドへ再加入できるまでのクールタイム（分）です。'),
 'ItemCorruptionMultiplier': ('アイテム腐敗速度倍率', 'アイテムの腐敗速度倍率です。'),
 'ItemWeightRate': ('アイテム重量倍率', 'アイテム重量の倍率です。'),
 'MonsterFarmActionSpeedRate': ('放牧生産速度倍率', '放牧によるアイテム生産速度倍率です。'),
 'NightTimeSpeedRate': ('夜の経過速度', '夜時間の進行速度です。'),
 'PalAutoHPRegeneRate': ('パル自然HP回復倍率', 'パルの自然HP回復倍率です。'),
 'PalAutoHpRegeneRateInSleep': ('パル睡眠時HP回復倍率', 'パルボックス内で睡眠中のHP回復倍率です。'),
 'PalCaptureRate': ('捕獲率倍率', 'パルの捕獲率倍率です。'),
 'PalDamageRateAttack': ('パル与ダメージ倍率', 'パルが与えるダメージ倍率です。'),
 'PalDamageRateDefense': ('パル被ダメージ倍率', 'パルが受けるダメージ倍率です。'),
 'PalEggDefaultHatchingTime': ('巨大タマゴ孵化時間', '巨大タマゴの孵化時間（時間）です。他のタマゴにも孵化時間が発生します。'),
 'PalSpawnNumRate': ('パル出現数倍率', 'パルの出現数倍率です。処理負荷に影響します。'),
 'PalStaminaDecreaceRate': ('パルスタミナ減少倍率', 'パルのスタミナ消費倍率です。'),
 'PalStomachDecreaceRate': ('パル空腹度減少倍率', 'パルの空腹度減少倍率です。'),
 'PlayerAutoHPRegeneRate': ('プレイヤー自然HP回復倍率', 'プレイヤーの自然HP回復倍率です。'),
 'PlayerAutoHpRegeneRateInSleep': ('プレイヤー睡眠時HP回復倍率', 'プレイヤー睡眠中のHP回復倍率です。'),
 'PlayerDamageRateAttack': ('プレイヤー与ダメージ倍率', 'プレイヤーが与えるダメージ倍率です。'),
 'PlayerDamageRateDefense': ('プレイヤー被ダメージ倍率', 'プレイヤーが受けるダメージ倍率です。'),
 'PlayerStaminaDecreaceRate': ('プレイヤースタミナ減少倍率', 'プレイヤーのスタミナ消費倍率です。'),
 'PlayerStomachDecreaceRate': ('プレイヤー空腹度減少倍率', 'プレイヤーの空腹度減少倍率です。'),
 'RespawnPenaltyDurationThreshold': ('リスポーンペナルティ判定時間', '次回死亡時のリスポーンクールタイム倍率を適用するための生存時間しきい値（秒）です。'),
 'RespawnPenaltyTimeScale': ('リスポーンクールタイム倍率', 'リスポーンペナルティ時に適用されるクールタイム倍率です。'),
 'SupplyDropSpan': ('隕石・補給物資の間隔', '隕石／補給物資イベントの発生間隔（分）です。'),
 'CoopPlayerMaxNum': ('協力プレイ最大人数', '通常のホスト型協力プレイに参加できる最大人数です。')}
EN_META = {'CoopPlayerMaxNum': ('Co-op player limit', 'Maximum number of players in a normal hosted co-op session.'),
 'ServerPlayerMaxNum': ('Server player limit', 'Maximum number of players who can join a dedicated server.'),
 'BaseCampWorkerMaxNum': ('Workers per base', 'Maximum number of Pals that can work at each base.'),
 'BaseCampMaxNum': ('Total base limit', 'Total number of bases allowed across the server.'),
 'BaseCampMaxNumInGuild': ('Bases per guild', 'Maximum number of bases allowed per guild.'),
 'GuildPlayerMaxNum': ('Guild player limit', 'Maximum number of players in a guild.'),
 'PalEggDefaultHatchingTime': ('Huge Egg hatching time', 'Time required to hatch a Huge Egg, in hours.'),
 'SupplyDropSpan': ('Meteorite / supply-drop interval',
                    'Interval between meteorite and supply-drop events, in minutes.'),
 'ServerReplicatePawnCullDistance': ('Pal synchronization distance',
                                     'Pal synchronization distance from players, in centimeters.'),
 'bAllowGlobalPalboxExport': ('Allow Global Palbox export', 'Allow saving Pals to the Global Palbox.'),
 'bAllowGlobalPalboxImport': ('Allow Global Palbox import', 'Allow loading Pals from the Global Palbox.'),
 'bEnableVoiceChat': ('Voice chat', 'Enable in-game voice chat.'),
 'bIsUseBackupSaveData': ('World backups', "Enable Palworld's built-in rotating world backups.")}
EN_NAMES = {'Difficulty': 'Difficulty',
 'RandomizerType': 'Pal randomizer mode',
 'RandomizerSeed': 'Randomizer seed',
 'bIsRandomizerPalLevelRandom': 'Randomize wild Pal levels',
 'DayTimeSpeedRate': 'Daytime speed',
 'NightTimeSpeedRate': 'Nighttime speed',
 'ExpRate': 'EXP rate',
 'PalCaptureRate': 'Pal capture rate',
 'PalSpawnNumRate': 'Pal spawn rate',
 'PalDamageRateAttack': 'Pal damage dealt',
 'PalDamageRateDefense': 'Pal damage taken',
 'PlayerDamageRateAttack': 'Player damage dealt',
 'PlayerDamageRateDefense': 'Player damage taken',
 'PlayerStomachDecreaceRate': 'Player hunger depletion',
 'PlayerStaminaDecreaceRate': 'Player stamina depletion',
 'PlayerAutoHPRegeneRate': 'Player natural HP regeneration',
 'PlayerAutoHpRegeneRateInSleep': 'Player sleeping HP regeneration',
 'PalStomachDecreaceRate': 'Pal hunger depletion',
 'PalStaminaDecreaceRate': 'Pal stamina depletion',
 'PalAutoHPRegeneRate': 'Pal natural HP regeneration',
 'PalAutoHpRegeneRateInSleep': 'Pal sleeping HP regeneration',
 'BuildObjectHpRate': 'Building HP rate',
 'BuildObjectDamageRate': 'Building damage rate',
 'BuildObjectDeteriorationDamageRate': 'Building deterioration rate',
 'CollectionDropRate': 'Gatherable drop rate',
 'CollectionObjectHpRate': 'Gatherable object HP',
 'CollectionObjectRespawnSpeedRate': 'Gatherable respawn interval',
 'EnemyDropItemRate': 'Enemy drop quantity',
 'EquipmentDurabilityDamageRate': 'Equipment durability loss',
 'ItemWeightRate': 'Item weight rate',
 'ItemCorruptionMultiplier': 'Item spoilage speed',
 'DeathPenalty': 'Death penalty',
 'bEnablePlayerToPlayerDamage': 'Player-to-player damage',
 'bEnableFriendlyFire': 'Friendly fire',
 'bEnableInvaderEnemy': 'Raid events',
 'DropItemMaxNum': 'Dropped item limit',
 'DropItemAliveMaxHours': 'Dropped item lifetime',
 'bAutoResetGuildNoOnlinePlayers': 'Auto-delete inactive guilds',
 'AutoResetGuildTimeNoOnlinePlayers': 'Inactive guild timeout',
 'GuildRejoinCooldownMinutes': 'Guild rejoin cooldown',
 'WorkSpeedRate': 'Work speed rate',
 'bIsPvP': 'PvP',
 'bEnableFastTravel': 'Fast travel',
 'bEnableFastTravelOnlyBaseCamp': 'Base-only fast travel',
 'bIsStartLocationSelectByMap': 'Choose starting location',
 'bHardcore': 'Hardcore mode',
 'bPalLost': 'Pal permadeath',
 'MaxBuildingLimitNum': 'Buildings per player',
 'ServerName': 'Server name',
 'ServerDescription': 'Server description',
 'AdminPassword': 'Admin password',
 'ServerPassword': 'Server password',
 'PublicPort': 'Public port',
 'PublicIP': 'Public IP',
 'RCONEnabled': 'RCON',
 'RCONPort': 'RCON port',
 'RESTAPIEnabled': 'REST API',
 'RESTAPIPort': 'REST API port',
 'bShowPlayerList': 'Player list',
 'CrossplayPlatforms': 'Crossplay platforms',
 'bAllowClientMod': 'Allow client mods',
 'LogFormatType': 'Log format',
 'ChatPostLimitPerMinute': 'Chat messages per minute',
 'BlockRespawnTime': 'Respawn cooldown',
 'RespawnPenaltyTimeScale': 'Respawn cooldown multiplier',
 'DenyTechnologyList': 'Disabled technologies'}

# Explicit localized metadata for current internal/less-documented fields.
ZH_META.update({
    "AutoSaveSpan": ("自动保存间隔", "世界自动保存的时间间隔。此字段在不同版本中可能以大小写不同的名称出现。"),
    "autoSaveSpan": ("自动保存间隔", "世界自动保存的时间间隔。此字段与 AutoSaveSpan 属于同类设置，具体名称取决于存档版本。"),
    "AutoTransferMasterCheckIntervalSeconds": ("公会会长自动转移检查间隔", "检查是否需要自动转移公会会长的内部间隔，单位为秒。"),
    "AutoTransferMasterThresholdDays": ("公会会长自动转移阈值", "用于判断自动转移公会会长的不活跃天数阈值。"),
    "BuildingNameDisplayCacheTTLSeconds": ("建筑名称显示缓存时间", "建筑名称/创建者显示信息的内部缓存有效时间，单位为秒。"),
    "MaxGuildsPerFrame": ("每帧处理公会数量上限", "内部性能设置，限制维护流程中每帧处理的公会记录数量。"),
    "PhysicsActiveDropItemMaxNum": ("启用物理效果的掉落物上限", "允许使用物理行为的掉落物数量上限。"),
    "PlayerDataPalStorageUpdateCheckTickInterval": ("帕鲁存储更新检查间隔", "检查玩家帕鲁存储数据更新频率的内部设置。"),
    "Region": ("服务器区域", "服务器区域标识。通常保持为空或由服务器配置决定。"),
    "bUseAuth": ("启用身份验证", "控制服务器连接是否使用平台身份验证。一般保持游戏默认值。"),
})
JA_META.update({
    "AutoSaveSpan": ("自動セーブ間隔", "ワールドの自動セーブ間隔です。バージョンによってフィールド名の大文字・小文字が異なる場合があります。"),
    "autoSaveSpan": ("自動セーブ間隔", "ワールドの自動セーブ間隔です。AutoSaveSpan と同種の設定で、保存形式によって名称が異なる場合があります。"),
    "AutoTransferMasterCheckIntervalSeconds": ("ギルドマスター自動移譲確認間隔", "ギルドマスター自動移譲条件を確認する内部処理の間隔（秒）です。"),
    "AutoTransferMasterThresholdDays": ("ギルドマスター自動移譲しきい値", "ギルドマスター自動移譲判定に使用する非アクティブ日数です。"),
    "BanListURL": ("BANリストURL", "サーバーが参照するBANリストのURLです。"),
    "BuildObjectHpRate": ("建築物HP倍率", "建築物の耐久力（HP）倍率です。"),
    "BuildingNameDisplayCacheTTLSeconds": ("建築名表示キャッシュ保持時間", "建築名／作成者表示情報の内部キャッシュ保持時間（秒）です。"),
    "Difficulty": ("難易度", "ワールドの難易度設定です。利用可能な列挙値はゲームバージョンに依存します。"),
    "DropItemAliveMaxHours": ("ドロップアイテム保持時間", "ドロップアイテムがワールド上に残る時間（時間）です。"),
    "DropItemMaxNum": ("ドロップアイテム最大数", "ワールド上に存在できるドロップアイテム数の上限です。"),
    "DropItemMaxNum_UNKO": ("UNKOドロップ最大数", "UNKO関連の特殊ドロップアイテム上限です。通常はデフォルト値を推奨します。"),
    "EnablePredatorBossPal": ("プレデターボスパル", "プレデター系ボスパルの出現を有効にするかを設定します。"),
    "MaxGuildsPerFrame": ("1フレーム当たりのギルド処理数", "保守処理中に1フレームで処理するギルド数を制限する内部設定です。"),
    "PlayerDataPalStorageUpdateCheckTickInterval": ("パル保管データ更新確認間隔", "プレイヤーのパル保管データ更新を確認する内部間隔です。"),
    "Region": ("サーバー地域", "サーバー地域を示す設定です。通常は空欄またはサーバー側の設定に従います。"),
    "WorkSpeedRate": ("作業速度倍率", "拠点作業や建築などの作業速度倍率です。"),
    "bActiveUNKO": ("UNKO機能", "予約済み／特殊用途の設定です。通常はデフォルト値のまま使用します。"),
    "bCanPickupOtherGuildDeathPenaltyDrop": ("他ギルドの死亡ドロップ取得", "他ギルドのプレイヤーが落とした死亡ペナルティアイテムを拾えるかを設定します。"),
    "bEnableAimAssistKeyboard": ("キーボード・マウスのエイムアシスト", "キーボード／マウス操作時のエイムアシストを設定します。"),
    "bEnableAimAssistPad": ("ゲームパッドのエイムアシスト", "ゲームパッド操作時のエイムアシストを設定します。"),
    "bEnableDefenseOtherGuildPlayer": ("他ギルドプレイヤーへの防衛", "ギルド間の防衛挙動に関する設定です。"),
    "bEnableFriendlyFire": ("フレンドリーファイア", "味方へのダメージを許可するかを設定します。"),
    "bEnableNonLoginPenalty": ("未ログインペナルティ", "長期間ログインしていない場合のペナルティに関する設定です。"),
    "bEnablePlayerToPlayerDamage": ("プレイヤー間ダメージ", "プレイヤー同士のダメージを有効にします。"),
    "bIsMultiplay": ("マルチプレイ", "マルチプレイ関連の内部フラグです。専用サーバーでは通常サーバー側で管理されます。"),
    "bUseAuth": ("認証を使用", "プラットフォーム認証を使用するかを設定します。通常はゲームのデフォルト値を推奨します。"),
})

CATEGORY_KEYS = {'rates': {'DayTimeSpeedRate',
           'ExpRate',
           'MonsterFarmActionSpeedRate',
           'NightTimeSpeedRate',
           'PalCaptureRate',
           'PalEggDefaultHatchingTime',
           'PalSpawnNumRate',
           'WorkSpeedRate'},
 'player_pal': {'EquipmentDurabilityDamageRate',
                'ItemCorruptionMultiplier',
                'ItemWeightRate',
                'PalAutoHPRegeneRate',
                'PalAutoHpRegeneRateInSleep',
                'PalDamageRateAttack',
                'PalDamageRateDefense',
                'PalStaminaDecreaceRate',
                'PalStomachDecreaceRate',
                'PlayerAutoHPRegeneRate',
                'PlayerAutoHpRegeneRateInSleep',
                'PlayerDamageRateAttack',
                'PlayerDamageRateDefense',
                'PlayerStaminaDecreaceRate',
                'PlayerStomachDecreaceRate'},
 'building_items': {'BuildObjectDamageRate',
                    'BuildObjectDeteriorationDamageRate',
                    'BuildObjectHpRate',
                    'CollectionDropRate',
                    'CollectionObjectHpRate',
                    'CollectionObjectRespawnSpeedRate',
                    'DropItemAliveMaxHours',
                    'DropItemMaxNum',
                    'DropItemMaxNum_UNKO',
                    'EnemyDropItemRate',
                    'ItemContainerForceMarkDirtyInterval',
                    'MaxBuildingLimitNum',
                    'PhysicsActiveDropItemMaxNum',
                    'bBuildAreaLimit'},
 'base_guild': {'AutoResetGuildTimeNoOnlinePlayers',
                'AutoTransferMasterCheckIntervalSeconds',
                'AutoTransferMasterThresholdDays',
                'BaseCampMaxNum',
                'BaseCampMaxNumInGuild',
                'BaseCampWorkerMaxNum',
                'GuildPlayerMaxNum',
                'GuildRejoinCooldownMinutes',
                'MaxGuildsPerFrame',
                'bAutoResetGuildNoOnlinePlayers',
                'bEnableDefenseOtherGuildPlayer',
                'bInvisibleOtherGuildBaseCampAreaFX'},
 'world_multiplayer': {'CoopPlayerMaxNum',
                       'Difficulty',
                       'EnablePredatorBossPal',
                       'RandomizerSeed',
                       'RandomizerType',
                       'SupplyDropSpan',
                       'bEnableFastTravel',
                       'bEnableFastTravelOnlyBaseCamp',
                       'bExistPlayerAfterLogout',
                       'bIsMultiplay',
                       'bIsRandomizerPalLevelRandom',
                       'bIsStartLocationSelectByMap'},
 'pvp_hardcore': {'AdditionalDropItemNumWhenPlayerKillingInPvPMode',
                  'AdditionalDropItemWhenPlayerKillingInPvPMode',
                  'BlockRespawnTime',
                  'DeathPenalty',
                  'RespawnPenaltyDurationThreshold',
                  'RespawnPenaltyTimeScale',
                  'bAdditionalDropItemWhenPlayerKillingInPvPMode',
                  'bCanPickupOtherGuildDeathPenaltyDrop',
                  'bCharacterRecreateInHardcore',
                  'bDisplayPvPItemNumOnWorldMap_BaseCamp',
                  'bDisplayPvPItemNumOnWorldMap_Player',
                  'bEnableFriendlyFire',
                  'bEnableNonLoginPenalty',
                  'bEnablePlayerToPlayerDamage',
                  'bHardcore',
                  'bIsPvP',
                  'bPalLost'},
 'server': {'AdminPassword',
            'BanListURL',
            'ChatPostLimitPerMinute',
            'CrossplayPlatforms',
            'LogFormatType',
            'PublicIP',
            'PublicPort',
            'RCONEnabled',
            'RCONPort',
            'RESTAPIEnabled',
            'RESTAPIPort',
            'Region',
            'ServerDescription',
            'ServerName',
            'ServerPassword',
            'ServerPlayerMaxNum',
            'ServerReplicatePawnCullDistance',
            'bAllowClientMod',
            'bIsShowJoinLeftMessage',
            'bIsUseBackupSaveData',
            'bShowPlayerList',
            'bUseAuth'}}
I18N = {'en': {'title': 'Palworld WorldOption Editor',
        'subtitle': 'Edit WorldOption.sav safely with localized setting references',
        'open': 'Open WorldOption.sav',
        'save': 'Save Changes',
        'reset': 'Reset to Default',
        'apply': 'Apply Value',
        'language': 'Language',
        'search': 'Search settings…',
        'all_categories': 'All categories',
        'category': 'Category',
        'setting': 'Setting',
        'key': 'Internal key',
        'value': 'Value',
        'type': 'Type',
        'default': 'Default',
        'details': 'Setting details',
        'recommended_values': 'Recommended Values',
        'recommended': 'Recommended',
        'minimum': 'MIN',
        'maximum': 'MAX',
        'range_common': 'MIN/MAX are 3DM common/recommended ranges, not hard engine limits.',
        'range_official': 'MIN/MAX include limits published by Pocketpair.',
        'range_unknown': 'No published numeric range is available for this setting.',
        'inline_hint': 'Tip: click a Value cell to edit it directly. Changes are applied automatically.',
        'description': 'Description',
        'edit_value': 'Edit value',
        'no_selection': 'Select a setting in the table to view its description and edit its value.',
        'no_file': 'No WorldOption.sav loaded',
        'ready': 'Ready',
        'loading': 'Loading WorldOption.sav…',
        'saving': 'Validating and saving…',
        'loaded': 'Loaded {count} settings',
        'showing': 'Showing {shown} of {total} settings',
        'saved': 'Saved successfully. Backup: {backup}',
        'load_error': 'Could not open WorldOption.sav',
        'save_error': 'Could not save WorldOption.sav',
        'invalid_name': 'Only a file named WorldOption.sav can be opened.',
        'missing_dep': 'Install required packages:\n\npython -m pip install palworld-save-tools pyooz',
        'need_pyooz': 'This save uses PlM/Oodle compression. Install pyooz:\n\npython -m pip install pyooz',
        'reset_confirm': 'Reset all settings with a known current default? This changes only the editor until you '
                         'save.',
        'external_change': 'WorldOption.sav changed on disk after it was opened. Reload it before saving.',
        'invalid_value': 'Invalid value for {key}: {detail}',
        'true': 'True',
        'false': 'False',
        'cat_rates': 'Rates & Time',
        'cat_player_pal': 'Player & Pal',
        'cat_building_items': 'Building & Items',
        'cat_base_guild': 'Base & Guild',
        'cat_world_multiplayer': 'World & Multiplayer',
        'cat_pvp_hardcore': 'PvP & Hardcore',
        'cat_server': 'Server & Network',
        'cat_advanced': 'Advanced'},
 'ja': {'title': 'Palworld WorldOption エディター',
        'subtitle': '多言語の設定説明と安全なバックアップ機能で WorldOption.sav を編集',
        'open': 'WorldOption.sav を開く',
        'save': '変更を保存',
        'reset': 'デフォルトに戻す',
        'apply': '値を適用',
        'language': '言語',
        'search': '設定を検索…',
        'all_categories': 'すべてのカテゴリ',
        'category': 'カテゴリ',
        'setting': '設定',
        'key': '内部キー',
        'value': '値',
        'type': '型',
        'default': 'デフォルト',
        'details': '設定の詳細',
        'recommended_values': '推奨値',
        'recommended': '推奨',
        'minimum': '最小',
        'maximum': '最大',
        'range_common': '最小/最大は3DM掲載の一般的な推奨範囲であり、ゲーム側の強制上限ではありません。',
        'range_official': '最小/最大にはPocketpairが公開している制限値を使用しています。',
        'range_unknown': 'この設定について公開された数値範囲はありません。',
        'inline_hint': 'ヒント：表の「値」セルをクリックすると直接編集できます。変更は自動的に反映されます。',
        'description': '説明',
        'edit_value': '値を編集',
        'no_selection': '表から設定を選択すると、説明の確認と値の編集ができます。',
        'no_file': 'WorldOption.sav が読み込まれていません',
        'ready': '準備完了',
        'loading': 'WorldOption.sav を読み込み中…',
        'saving': '検証して保存中…',
        'loaded': '{count} 件の設定を読み込みました',
        'showing': '{total} 件中 {shown} 件を表示',
        'saved': '保存しました。バックアップ: {backup}',
        'load_error': 'WorldOption.sav を開けませんでした',
        'save_error': 'WorldOption.sav を保存できませんでした',
        'invalid_name': 'WorldOption.sav という名前のファイルだけを開けます。',
        'missing_dep': '必要なパッケージをインストールしてください:\n\npython -m pip install palworld-save-tools pyooz',
        'need_pyooz': 'このセーブは PlM/Oodle 圧縮です。pyooz をインストールしてください:\n\npython -m pip install pyooz',
        'reset_confirm': '現在のデフォルト値が確認できる設定をすべて戻しますか？保存するまでファイルには書き込まれません。',
        'external_change': '開いた後に WorldOption.sav が変更されました。保存前に再読み込みしてください。',
        'invalid_value': '{key} の値が無効です: {detail}',
        'true': 'True',
        'false': 'False',
        'cat_rates': '倍率・時間',
        'cat_player_pal': 'プレイヤー・パル',
        'cat_building_items': '建築・アイテム',
        'cat_base_guild': '拠点・ギルド',
        'cat_world_multiplayer': 'ワールド・マルチプレイ',
        'cat_pvp_hardcore': 'PvP・ハードコア',
        'cat_server': 'サーバー・ネットワーク',
        'cat_advanced': '詳細設定'},
 'zh': {'title': 'Palworld WorldOption 编辑器',
        'subtitle': '通过本地化说明、自动备份与存档验证安全编辑 WorldOption.sav',
        'open': '打开 WorldOption.sav',
        'save': '保存更改',
        'reset': '恢复默认值',
        'apply': '应用数值',
        'language': '语言',
        'search': '搜索设置…',
        'all_categories': '全部分类',
        'category': '分类',
        'setting': '设置',
        'key': '内部字段',
        'value': '数值',
        'type': '类型',
        'default': '默认值',
        'details': '设置详情',
        'recommended_values': '推荐值',
        'recommended': '推荐',
        'minimum': '最小值',
        'maximum': '最大值',
        'range_common': '最小/最大值来自3DM标注的常用/推荐范围，并非游戏强制限制。',
        'range_official': '最小/最大值包含Pocketpair官方公布的限制。',
        'range_unknown': '该设置暂无公开的数值范围。',
        'inline_hint': '提示：点击表格中的“数值”单元格即可直接编辑，离开单元格后自动应用。',
        'description': '说明',
        'edit_value': '编辑数值',
        'no_selection': '请在表格中选择一项设置，以查看说明并编辑数值。',
        'no_file': '尚未加载 WorldOption.sav',
        'ready': '就绪',
        'loading': '正在加载 WorldOption.sav…',
        'saving': '正在验证并保存…',
        'loaded': '已加载 {count} 项设置',
        'showing': '显示 {shown}/{total} 项设置',
        'saved': '保存成功。备份：{backup}',
        'load_error': '无法打开 WorldOption.sav',
        'save_error': '无法保存 WorldOption.sav',
        'invalid_name': '只能打开名为 WorldOption.sav 的文件。',
        'missing_dep': '请安装所需软件包：\n\npython -m pip install palworld-save-tools pyooz',
        'need_pyooz': '此存档使用 PlM/Oodle 压缩。请安装 pyooz：\n\npython -m pip install pyooz',
        'reset_confirm': '是否将具有已知当前默认值的设置全部恢复？在保存前不会写入文件。',
        'external_change': '打开后 WorldOption.sav 已在磁盘上发生变化。请重新加载后再保存。',
        'invalid_value': '{key} 的数值无效：{detail}',
        'true': 'True',
        'false': 'False',
        'cat_rates': '倍率与时间',
        'cat_player_pal': '玩家与帕鲁',
        'cat_building_items': '建筑与物品',
        'cat_base_guild': '据点与公会',
        'cat_world_multiplayer': '世界与多人',
        'cat_pvp_hardcore': 'PvP 与硬核',
        'cat_server': '服务器与网络',
        'cat_advanced': '高级设置'}}


# Additional interface text for the redesigned desktop workflow.
_I18N_UX = {
    "en": {
        "all_settings": "All Settings",
        "open_short": "Open",
        "reset_selected_short": "Reset",
        "modified_only": "Modified only",
        "revert_all": "Discard Changes",
        "revert_confirm": "Discard all unsaved changes and restore the values loaded from disk?",
        "reset_all": "Reset All Defaults",
        "reset_selected": "Reset Selected",
        "use_recommended": "Use Recommended",
        "save_count": "Save Changes ({count})",
        "unsaved_count": "{count} unsaved change(s)",
        "no_changes": "No unsaved changes",
        "file_label": "World file",
        "technical": "Technical",
        "current_value": "Current value",
        "empty_title": "Open a WorldOption.sav to begin",
        "empty_text": "Choose a world settings file. The editor will create a backup automatically when you save.",
        "selected_help": "Select a setting to view its explanation, limits, and editing controls.",
        "modified": "Modified",
        "loaded_short": "{count} settings loaded",
        "search_results": "{shown} settings",
        "saved_clean": "All changes saved",
        "recommended_unavailable": "No recommended value is published for this setting.",
    },
    "ja": {
        "all_settings": "すべての設定",
        "open_short": "開く",
        "reset_selected_short": "デフォルト",
        "modified_only": "変更済みのみ",
        "revert_all": "変更を破棄",
        "revert_confirm": "未保存の変更をすべて破棄し、読み込み時の値に戻しますか？",
        "reset_all": "すべてデフォルトに戻す",
        "reset_selected": "選択項目をデフォルトに戻す",
        "use_recommended": "推奨値を使用",
        "save_count": "変更を保存 ({count})",
        "unsaved_count": "未保存の変更: {count}件",
        "no_changes": "未保存の変更はありません",
        "file_label": "ワールドファイル",
        "technical": "技術情報",
        "current_value": "現在の値",
        "empty_title": "WorldOption.sav を開いて開始",
        "empty_text": "ワールド設定ファイルを選択してください。保存時には自動的にバックアップを作成します。",
        "selected_help": "設定を選択すると、説明・範囲・編集コントロールを表示します。",
        "modified": "変更済み",
        "loaded_short": "{count}件の設定",
        "search_results": "{shown}件",
        "saved_clean": "すべての変更を保存しました",
        "recommended_unavailable": "この設定には公開された推奨値がありません。",
    },
    "zh": {
        "all_settings": "全部设置",
        "open_short": "打开",
        "reset_selected_short": "恢复默认",
        "modified_only": "仅显示已修改",
        "revert_all": "放弃更改",
        "revert_confirm": "是否放弃所有尚未保存的更改，并恢复为刚加载时的数值？",
        "reset_all": "全部恢复默认值",
        "reset_selected": "恢复当前项默认值",
        "use_recommended": "使用推荐值",
        "save_count": "保存更改（{count}）",
        "unsaved_count": "未保存更改：{count} 项",
        "no_changes": "没有未保存的更改",
        "file_label": "世界文件",
        "technical": "技术信息",
        "current_value": "当前数值",
        "empty_title": "打开 WorldOption.sav 开始编辑",
        "empty_text": "请选择世界设置文件。保存时编辑器会自动创建备份。",
        "selected_help": "选择一项设置即可查看说明、范围以及编辑控件。",
        "modified": "已修改",
        "loaded_short": "已加载 {count} 项设置",
        "search_results": "{shown} 项设置",
        "saved_clean": "所有更改已保存",
        "recommended_unavailable": "该设置暂无公开的推荐值。",
    },
}
for _lang, _items in _I18N_UX.items():
    I18N[_lang].update(_items)


# Value guidance used by the "Recommended Values" panel.
#
# range_type:
#   "common"   = 3DM's current recommended/common range (常用范围), not a hard engine clamp.
#   "official" = a limit explicitly published in Pocketpair's current server guide.
#
# Unknown/unpublished ranges are deliberately shown as "—" instead of guessed.
VALUE_GUIDANCE = {
    "DayTimeSpeedRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "NightTimeSpeedRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "ExpRate": {"min": 0.1, "max": 20.0, "recommended": 1.0, "range_type": "common"},
    "PalCaptureRate": {"min": 0.5, "max": 2.0, "recommended": 1.0, "range_type": "common"},
    "PalSpawnNumRate": {"min": 0.5, "max": 3.0, "recommended": 1.0, "range_type": "common"},
    "PalDamageRateAttack": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PalDamageRateDefense": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PlayerDamageRateAttack": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PlayerDamageRateDefense": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PlayerStomachDecreaceRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PlayerStaminaDecreaceRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PlayerAutoHPRegeneRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PlayerAutoHpRegeneRateInSleep": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PalStomachDecreaceRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PalStaminaDecreaceRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PalAutoHPRegeneRate": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "PalAutoHpRegeneRateInSleep": {"min": 0.1, "max": 5.0, "recommended": 1.0, "range_type": "common"},
    "BuildObjectDamageRate": {"min": 0.5, "max": 3.0, "recommended": 1.0, "range_type": "common"},
    "BuildObjectDeteriorationDamageRate": {"min": 0.0, "max": 10.0, "recommended": 1.0, "range_type": "common"},
    "CollectionDropRate": {"min": 0.5, "max": 3.0, "recommended": 1.0, "range_type": "common"},
    "CollectionObjectHpRate": {"min": 0.5, "max": 3.0, "recommended": 1.0, "range_type": "common"},
    "CollectionObjectRespawnSpeedRate": {"min": 0.5, "max": 3.0, "recommended": 1.0, "range_type": "common"},
    "GuildPlayerMaxNum": {"min": 1, "max": 100, "recommended": 20, "range_type": "common"},
    "PalEggDefaultHatchingTime": {"min": 0.0, "max": 240.0, "recommended": 72.0, "range_type": "common"},
    "BaseCampMaxNumInGuild": {"min": None, "max": 10, "recommended": 4, "range_type": "official"},
    "BaseCampWorkerMaxNum": {"min": None, "max": 50, "recommended": 15, "range_type": "official"},
    "ServerReplicatePawnCullDistance": {"min": 5000.0, "max": 15000.0, "recommended": 15000.0, "range_type": "official"},
}

def guidance_for(key: str):
    guide = VALUE_GUIDANCE.get(key, {})
    default = DEFAULTS.get(key)
    return {
        "default": default,
        "recommended": guide.get("recommended", default),
        "min": guide.get("min"),
        "max": guide.get("max"),
        "range_type": guide.get("range_type"),
    }

def guidance_text(value):
    if value is None:
        return "—"
    return format_default(value)

ENUM_CHOICES = {
    "Difficulty": ["None", "Casual", "Normal", "Hard"],
    "RandomizerType": ["None", "Region", "All"],
    "DeathPenalty": ["None", "Item", "ItemAndEquipment", "All"],
    "LogFormatType": ["Text", "Json"],
}
ENUM_ARRAY_TYPES = {"CrossplayPlatforms": "EPalAllowConnectPlatform"}

class SaveFormatError(Exception):
    pass

class ExternalFileChangedError(Exception):
    pass

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def parse_sav_header(raw: bytes):
    if len(raw) < 12:
        raise SaveFormatError("File is too small to be a Palworld save.")
    uncompressed_len = int.from_bytes(raw[0:4], "little")
    compressed_len = int.from_bytes(raw[4:8], "little")
    magic = raw[8:11]
    save_type = raw[11]
    offset = 12
    if magic == b"CNK":
        if len(raw) < 24:
            raise SaveFormatError("CNK header is truncated.")
        uncompressed_len = int.from_bytes(raw[12:16], "little")
        compressed_len = int.from_bytes(raw[16:20], "little")
        magic = raw[20:23]
        save_type = raw[23]
        offset = 24
    if magic not in (b"PlZ", b"PlM"):
        raise SaveFormatError(f"Unexpected Palworld save header: {magic!r}")
    if compressed_len <= 0 or offset + compressed_len > len(raw):
        raise SaveFormatError("Compressed save payload is truncated.")
    return uncompressed_len, compressed_len, magic, save_type, offset

def decompress_sav(raw: bytes):
    uncompressed_len, compressed_len, magic, save_type, offset = parse_sav_header(raw)
    payload = raw[offset:offset + compressed_len]
    if magic == b"PlM":
        if _ooz_decompress is None:
            raise SaveFormatError("PYOOZ_REQUIRED")
        try:
            gvas = _ooz_decompress(payload, uncompressed_len)
        except Exception as exc:
            raise SaveFormatError(f"Oodle decompression failed: {exc}") from exc
    else:
        try:
            gvas = zlib.decompress(payload)
            if save_type == 0x32:
                gvas = zlib.decompress(gvas)
        except zlib.error as exc:
            raise SaveFormatError(f"zlib decompression failed: {exc}") from exc
    if len(gvas) != uncompressed_len:
        raise SaveFormatError(f"Decompressed size mismatch: {len(gvas)} != {uncompressed_len}")
    if not gvas.startswith(b"GVAS"):
        raise SaveFormatError("Decompressed payload is not GVAS data.")
    return bytes(gvas), magic, save_type

def compress_sav(gvas: bytes, source_magic: bytes, source_save_type: int) -> bytes:
    # Match Dehmahk's proven behavior: PlM input -> PlZ1;
    # existing PlZ2 input -> PlZ2; otherwise PlZ1.
    out_type = 0x32 if (source_magic != b"PlM" and source_save_type == 0x32) else 0x31
    payload = zlib.compress(gvas)
    if out_type == 0x32:
        payload = zlib.compress(payload)
    return (
        len(gvas).to_bytes(4, "little")
        + len(payload).to_bytes(4, "little")
        + b"PlZ"
        + bytes([out_type])
        + payload
    )

def parse_gvas(data: bytes):
    try:
        return GvasFile.read(data, {}, {}, allow_nan=True)
    except Exception as exc:
        raise SaveFormatError(f"GVAS parsing failed: {exc}") from exc

def next_backup_path(path: Path) -> Path:
    first = Path(str(path) + ".bak")
    if not first.exists():
        return first
    pattern = re.compile(re.escape(path.name) + r"\.bak(\d+)$", re.I)
    highest = 0
    for item in path.parent.iterdir():
        m = pattern.fullmatch(item.name)
        if m:
            highest = max(highest, int(m.group(1)))
    return Path(str(path) + f".bak{highest + 1:02d}")

def strip_enum_prefix(value):
    return value.rsplit("::", 1)[-1] if isinstance(value, str) and "::" in value else value

def property_kind(prop: dict) -> str:
    t = prop.get("type", "")
    if t == "BoolProperty":
        return "bool"
    if t in {"IntProperty","Int8Property","Int16Property","Int64Property","UInt16Property","UInt32Property","UInt64Property"}:
        return "int"
    if t in {"FloatProperty","DoubleProperty"}:
        return "float"
    if t in {"StrProperty","NameProperty"}:
        return "str"
    if t == "EnumProperty":
        return "enum"
    if t in {"ArrayProperty","SetProperty"}:
        return "array"
    return "json"

def display_value(prop: dict):
    kind = property_kind(prop)
    value = prop.get("value")
    if kind == "bool":
        return bool(value)
    if kind in {"int","float","str"}:
        return "" if value is None else str(value)
    if kind == "enum":
        if isinstance(value, dict):
            return str(strip_enum_prefix(value.get("value", "")))
        return str(strip_enum_prefix(value))
    if kind == "array":
        vals = value.get("values", []) if isinstance(value, dict) else value
        if isinstance(vals, list):
            vals = [strip_enum_prefix(v) for v in vals]
            out = io.StringIO()
            csv.writer(out, lineterminator="").writerow(vals)
            return out.getvalue()
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

def format_default(value):
    if value is None:
        return "—"
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value)

def parse_list(text: str):
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        value = json.loads(text)
        if not isinstance(value, list):
            raise ValueError("expected a JSON list")
        return value
    return next(csv.reader([text], skipinitialspace=True))

def apply_value(key: str, prop: dict, editor_value):
    kind = property_kind(prop)
    if kind == "bool":
        if isinstance(editor_value, bool):
            prop["value"] = editor_value
        else:
            s = str(editor_value).strip().casefold()
            if s in {"true","1","yes","on"}:
                prop["value"] = True
            elif s in {"false","0","no","off"}:
                prop["value"] = False
            else:
                raise ValueError("expected True or False")
        return
    if kind == "int":
        raw = str(editor_value).strip()
        if not raw:
            raise ValueError("integer value cannot be empty")
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
        obj = prop.get("value")
        if not isinstance(obj, dict):
            raise ValueError("unexpected EnumProperty structure")
        enum_type = obj.get("type", "")
        old = obj.get("value", "")
        if "::" in raw:
            full = raw
        elif enum_type:
            full = f"{enum_type}::{raw}"
        elif isinstance(old, str) and "::" in old:
            full = f"{old.rsplit('::',1)[0]}::{raw}"
        else:
            full = raw
        obj["value"] = full
        return
    if kind == "array":
        vals = parse_list(str(editor_value))
        obj = prop.get("value")
        if not isinstance(obj, dict) or "values" not in obj:
            raise ValueError("unexpected array structure")
        array_type = prop.get("array_type", "")
        old_vals = obj.get("values", [])
        if array_type == "EnumProperty":
            prefix = None
            for old in old_vals:
                if isinstance(old, str) and "::" in old:
                    prefix = old.rsplit("::",1)[0]
                    break
            prefix = prefix or ENUM_ARRAY_TYPES.get(key)
            if prefix:
                vals = [v if isinstance(v,str) and "::" in v else f"{prefix}::{v}" for v in vals]
        elif array_type in {"IntProperty","Int64Property","UInt32Property","UInt64Property"}:
            vals = [int(v) for v in vals]
        elif array_type in {"FloatProperty","DoubleProperty"}:
            vals = [float(v) for v in vals]
        obj["values"] = vals
        return
    prop["value"] = json.loads(str(editor_value))

def category_for(key: str) -> str:
    for cat, keys in CATEGORY_KEYS.items():
        if key in keys:
            return cat
    return "advanced"

def meta_for(key: str, lang: str):
    if lang == "zh" and key in ZH_META:
        return ZH_META[key]
    if lang == "ja" and key in JA_META:
        return JA_META[key]
    if lang == "en":
        if key in EN_META:
            return EN_META[key]
        name = EN_NAMES.get(key, key)
        return name, f"Palworld setting '{key}'. Change this value only if you understand its effect on the current world."
    # Conservative localized fallback for internal or undocumented fields.
    if lang == "ja":
        return f"内部設定: {key}", f"Palworld の設定「{key}」です。公式ガイドに詳細な説明がないため、変更前にバックアップを作成してください。"
    if lang == "zh":
        return f"内部设置：{key}", f"Palworld 设置“{key}”。当前公开配置说明中没有详细解释，修改前请先备份存档。"
    return key, f"Palworld setting '{key}'."

class WorldOptionDocument:
    def __init__(self):
        self.path = None
        self.loaded_hash = None
        self.original_magic = None
        self.original_save_type = None
        self.original_gvas = None
        self.settings = None

    @staticmethod
    def get_settings(gvas_file):
        props = gvas_file.properties
        option = props.get("OptionWorldData")
        if not isinstance(option, dict):
            raise ValueError("INVALID_WORLDOPTION")
        option_value = option.get("value")
        settings_prop = option_value.get("Settings") if isinstance(option_value, dict) else None
        if not isinstance(settings_prop, dict) or not isinstance(settings_prop.get("value"), dict):
            raise ValueError("INVALID_WORLDOPTION")
        return settings_prop["value"]

    def load(self, path):
        path = Path(path)
        if path.name.casefold() != SAVE_FILENAME.casefold():
            raise ValueError("INVALID_NAME")
        raw = path.read_bytes()
        gvas, magic, save_type = decompress_sav(raw)
        gf = parse_gvas(gvas)
        settings = self.get_settings(gf)
        self.path = path
        self.loaded_hash = sha256_bytes(raw)
        self.original_magic = magic
        self.original_save_type = save_type
        self.original_gvas = gvas
        self.settings = settings
        return self

    def save(self, edited_values):
        if self.path is None or self.original_gvas is None:
            raise RuntimeError("No WorldOption.sav loaded.")
        current = self.path.read_bytes()
        if self.loaded_hash and sha256_bytes(current) != self.loaded_hash:
            raise ExternalFileChangedError()

        gf = parse_gvas(self.original_gvas)
        settings = self.get_settings(gf)
        for key, value in edited_values.items():
            prop = settings.get(key)
            if prop is None:
                continue
            try:
                apply_value(key, prop, value)
            except Exception as exc:
                raise ValueError(f"{key}\n{exc}") from exc

        try:
            new_gvas = gf.write({})
        except Exception as exc:
            raise SaveFormatError(f"GVAS serialization failed: {exc}") from exc

        # Parse new GVAS before compression.
        parse_gvas(new_gvas)
        new_sav = compress_sav(new_gvas, self.original_magic, self.original_save_type)
        verify_gvas, verify_magic, verify_type = decompress_sav(new_sav)
        if verify_gvas != new_gvas:
            raise SaveFormatError("Compression verification failed.")

        backup = next_backup_path(self.path)
        shutil.copy2(self.path, backup)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=self.path.parent, prefix=self.path.name+".", suffix=".tmp", delete=False) as tmp:
                temp_path = Path(tmp.name)
                tmp.write(new_sav)
                tmp.flush()
                os.fsync(tmp.fileno())
            disk_raw = temp_path.read_bytes()
            disk_gvas, _, _ = decompress_sav(disk_raw)
            if disk_gvas != new_gvas:
                raise SaveFormatError("Temporary-file verification failed.")
            parse_gvas(disk_gvas)
            os.replace(temp_path, self.path)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        self.loaded_hash = sha256_bytes(new_sav)
        self.original_magic = verify_magic
        self.original_save_type = verify_type
        self.original_gvas = new_gvas
        self.settings = self.get_settings(parse_gvas(new_gvas))
        return backup

class EditorApp(tk.Tk):
    """Modern three-pane desktop UI for Palworld WorldOption Editor."""

    PALETTE = {
        "bg": "#F4F7FA",
        "surface": "#FFFFFF",
        "surface_alt": "#F8FAFC",
        "sidebar": "#EEF4F6",
        "border": "#D9E2E8",
        "text": "#17212B",
        "muted": "#667085",
        "accent": "#147D92",
        "accent_hover": "#106A7C",
        "accent_pressed": "#0C5968",
        "accent_soft": "#E3F3F6",
        "accent_soft_hover": "#D7EEF3",
        "modified": "#FFF7E6",
        "modified_text": "#8A5A00",
        "danger_soft": "#FFF1F0",
        "success": "#2E7D5B",
        "disabled": "#A7B0BA",
    }

    CATEGORY_ORDER = (
        "all",
        "rates",
        "player_pal",
        "building_items",
        "base_guild",
        "world_multiplayer",
        "pvp_hardcore",
        "server",
        "advanced",
    )

    def __init__(self):
        super().__init__()
        self.lang = "en"
        self.doc = None
        self.values = {}
        self.original_values = {}
        self.kinds = {}
        self.search_cache = {}
        self.all_keys = []
        self.selected_key = None
        self.detail_edit_key = None
        self.current_category = "all"
        self.modified_keys = set()
        self.busy = False

        self.worker_queue = queue.Queue()
        self.filter_after = None
        self.inline_editor = None
        self.inline_editor_key = None
        self.inline_editor_committing = False

        self.geometry("1380x840")
        self.minsize(1060, 680)
        self.title(APP_NAME)
        self._set_window_icon()
        self.configure(background=self.PALETTE["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.lang_var = tk.StringVar(value="English")
        self.search_var = tk.StringVar()
        self.modified_only_var = tk.BooleanVar(value=False)
        self.edit_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self.t("ready"))
        self.path_var = tk.StringVar(value=self.t("no_file"))
        self.count_var = tk.StringVar()

        self._style()
        self._build_ui()
        self._apply_language()
        self.search_var.trace_add("write", lambda *_: self._schedule_filter())
        self.modified_only_var.trace_add("write", lambda *_: self._rebuild_table(preserve_selection=True))
        self.after(80, self._poll_workers)

    def _set_window_icon(self):
        """Set the window/taskbar icon from the bundled LOGO.ico.

        Falls back silently to the default icon if the file is missing or
        cannot be applied, so a missing resource never prevents startup.
        """
        ico = _resource_path(ICON_FILENAME)
        if os.path.isfile(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def t(self, key, **kwargs):
        value = I18N[self.lang].get(key, I18N["en"].get(key, key))
        return value.format(**kwargs) if kwargs else value

    # ------------------------------------------------------------------
    # Visual system
    # ------------------------------------------------------------------

    def _font(self):
        return {
            "en": ("Segoe UI", 10),
            "ja": ("Yu Gothic UI", 10),
            "zh": ("Microsoft YaHei UI", 10),
        }[self.lang]

    def _style(self):
        p = self.PALETTE
        style = ttk.Style(self)
        # "clam" is used so colors, borders, and selected states can be styled
        # consistently on Windows instead of being ignored by the native theme.
        if "clam" in style.theme_names():
            style.theme_use("clam")

        font = self._font()
        family = font[0]

        style.configure(".", font=font, background=p["bg"], foreground=p["text"])
        style.configure("App.TFrame", background=p["bg"])
        style.configure("Surface.TFrame", background=p["surface"])
        style.configure("Sidebar.TFrame", background=p["sidebar"])
        style.configure("Toolbar.TFrame", background=p["surface"])
        style.configure("Card.TFrame", background=p["surface"])
        style.configure("CardAlt.TFrame", background=p["surface_alt"])

        style.configure("Title.TLabel", background=p["surface"], foreground=p["text"],
                        font=(family, 18, "bold"))
        style.configure("Subtitle.TLabel", background=p["surface"], foreground=p["muted"],
                        font=(family, 9))
        style.configure("Section.TLabel", background=p["surface"], foreground=p["text"],
                        font=(family, 11, "bold"))
        style.configure("Meta.TLabel", background=p["surface"], foreground=p["muted"],
                        font=(family, 9))
        style.configure("SidebarTitle.TLabel", background=p["sidebar"], foreground=p["muted"],
                        font=(family, 9, "bold"))
        style.configure("Status.TLabel", background=p["bg"], foreground=p["muted"],
                        font=(family, 9))
        style.configure("Badge.TLabel", background=p["accent_soft"], foreground=p["accent"],
                        padding=(8, 4), font=(family, 9, "bold"))
        style.configure("ModifiedBadge.TLabel", background=p["modified"], foreground=p["modified_text"],
                        padding=(8, 4), font=(family, 9, "bold"))

        style.configure("Primary.TButton", background=p["accent"], foreground="#FFFFFF",
                        bordercolor=p["accent"], lightcolor=p["accent"], darkcolor=p["accent"],
                        padding=(18, 10), font=(family, 10, "bold"))
        style.map("Primary.TButton",
                  background=[("disabled", "#B7C8CD"), ("pressed", p["accent_pressed"]),
                              ("active", p["accent_hover"])],
                  foreground=[("disabled", "#F5F7F8"), ("!disabled", "#FFFFFF")])

        style.configure("Secondary.TButton", background=p["surface"], foreground=p["text"],
                        bordercolor=p["border"], lightcolor=p["surface"], darkcolor=p["surface"],
                        padding=(11, 8))
        style.map("Secondary.TButton",
                  background=[("pressed", p["accent_soft"]), ("active", p["surface_alt"])],
                  bordercolor=[("active", "#C7D3DB")])

        style.configure("Soft.TButton", background=p["accent_soft"], foreground=p["accent"],
                        bordercolor=p["accent_soft"], lightcolor=p["accent_soft"],
                        darkcolor=p["accent_soft"], padding=(12, 8), font=(family, 9, "bold"))
        style.map("Soft.TButton",
                  background=[("pressed", p["accent_soft_hover"]), ("active", p["accent_soft_hover"])])

        style.configure("DangerGhost.TButton", background=p["surface"], foreground="#8F3430",
                        bordercolor=p["border"], padding=(12, 8))
        style.map("DangerGhost.TButton", background=[("active", p["danger_soft"])])

        style.configure("TEntry", fieldbackground=p["surface"], foreground=p["text"],
                        bordercolor=p["border"], insertcolor=p["text"], padding=(8, 7))
        style.map("TEntry", bordercolor=[("focus", p["accent"])])
        style.configure("TCombobox", fieldbackground=p["surface"], background=p["surface"],
                        foreground=p["text"], bordercolor=p["border"], padding=(7, 6))
        style.map("TCombobox", bordercolor=[("focus", p["accent"])])

        style.configure("TCheckbutton", background=p["surface"], foreground=p["text"])
        style.configure("Filter.TCheckbutton", background=p["surface"], foreground=p["muted"])

        style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                        foreground=p["text"], bordercolor=p["border"], rowheight=34)
        style.configure("Treeview.Heading", background=p["surface_alt"], foreground=p["muted"],
                        bordercolor=p["border"], relief="flat", padding=(8, 8),
                        font=(family, 9, "bold"))
        style.map("Treeview",
                  background=[("selected", p["accent_soft"])],
                  foreground=[("selected", p["text"])])
        style.map("Treeview.Heading", background=[("active", "#F0F4F7")])

        style.configure("TPanedwindow", background=p["bg"])
        style.configure("TSeparator", background=p["border"])

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        p = self.PALETTE

        # Top application bar.
        top = ttk.Frame(self, style="Toolbar.TFrame", padding=(20, 14))
        top.pack(fill="x")
        top.columnconfigure(0, weight=1)

        brand = ttk.Frame(top, style="Toolbar.TFrame")
        brand.grid(row=0, column=0, sticky="w")
        self.title_label = ttk.Label(brand, style="Title.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = ttk.Label(brand, style="Subtitle.TLabel")
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = ttk.Frame(top, style="Toolbar.TFrame")
        actions.grid(row=0, column=1, sticky="e")

        file_area = ttk.Frame(top, style="Toolbar.TFrame")
        file_area.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        file_area.columnconfigure(0, weight=1)
        self.path_label = ttk.Label(file_area, textvariable=self.path_var, style="Meta.TLabel",
                                    anchor="w")
        self.path_label.grid(row=0, column=0, sticky="ew")
        self.dirty_badge = ttk.Label(file_area, style="ModifiedBadge.TLabel")
        self.dirty_badge.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.dirty_badge.grid_remove()
        self.open_btn = ttk.Button(actions, style="Secondary.TButton", command=self.open_file)
        self.open_btn.grid(row=0, column=0, padx=(0, 8))
        self.revert_btn = ttk.Button(actions, style="Secondary.TButton", command=self.revert_all,
                                     state="disabled")
        self.revert_btn.grid(row=0, column=1, padx=(0, 8))
        self.save_btn = ttk.Button(actions, style="Primary.TButton", command=self.save_file,
                                   state="disabled")
        self.save_btn.grid(row=0, column=2, padx=(0, 12))
        self.language_combo = ttk.Combobox(
            actions, textvariable=self.lang_var, state="readonly", width=10,
            values=["English", "日本語", "简体中文"]
        )
        self.language_combo.grid(row=0, column=3)
        self.language_combo.bind("<<ComboboxSelected>>", self._language_changed)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # Main workspace: navigation / settings / inspector.
        workspace = ttk.Frame(self, style="App.TFrame", padding=(16, 16, 16, 10))
        workspace.pack(fill="both", expand=True)
        workspace.columnconfigure(0, minsize=190)
        workspace.columnconfigure(1, weight=3, minsize=480)
        workspace.columnconfigure(2, weight=2, minsize=330)
        workspace.rowconfigure(0, weight=1)

        # Sidebar -------------------------------------------------------
        sidebar = ttk.Frame(workspace, style="Sidebar.TFrame", padding=(12, 14))
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        sidebar.rowconfigure(1, weight=1)
        sidebar.columnconfigure(0, weight=1)

        self.category_title = ttk.Label(sidebar, style="SidebarTitle.TLabel")
        self.category_title.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 8))

        self.category_list = tk.Listbox(
            sidebar, activestyle="none", relief="flat", borderwidth=0,
            highlightthickness=0, selectborderwidth=0, exportselection=False,
            bg=p["sidebar"], fg=p["text"], selectbackground=p["accent_soft"],
            selectforeground=p["accent"], font=self._font(), cursor="hand2"
        )
        self.category_list.grid(row=1, column=0, sticky="nsew")
        self.category_list.bind("<<ListboxSelect>>", self._category_selected)

        sidebar_footer = ttk.Frame(sidebar, style="Sidebar.TFrame")
        sidebar_footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        sidebar_footer.columnconfigure(0, weight=1)
        self.reset_all_btn = ttk.Button(
            sidebar_footer, style="DangerGhost.TButton", command=self.reset_defaults,
            state="disabled"
        )
        self.reset_all_btn.grid(row=0, column=0, sticky="ew")

        # Center settings surface --------------------------------------
        center = ttk.Frame(workspace, style="Surface.TFrame", padding=(14, 14))
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        center.rowconfigure(2, weight=1)
        center.columnconfigure(0, weight=1)

        search_row = ttk.Frame(center, style="Surface.TFrame")
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        search_row.columnconfigure(1, weight=1)
        self.search_label = ttk.Label(search_row, style="Meta.TLabel")
        self.search_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.modified_check = ttk.Checkbutton(
            search_row, variable=self.modified_only_var, style="Filter.TCheckbutton"
        )
        self.modified_check.grid(row=0, column=2, padx=(12, 0))

        info_row = ttk.Frame(center, style="Surface.TFrame")
        info_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        info_row.columnconfigure(0, weight=1)
        self.count_label = ttk.Label(info_row, textvariable=self.count_var, style="Meta.TLabel")
        self.count_label.grid(row=0, column=0, sticky="w")
        self.inline_hint_label = ttk.Label(info_row, style="Meta.TLabel")
        self.inline_hint_label.grid(row=0, column=1, sticky="e")

        table_frame = ttk.Frame(center, style="Surface.TFrame")
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        cols = ("setting", "value", "default")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.column("setting", width=290, minwidth=190, stretch=True)
        self.tree.column("value", width=170, minwidth=120, stretch=True)
        self.tree.column("default", width=120, minwidth=90, stretch=False)
        vs = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("modified", background=p["modified"])
        self.tree.bind("<<TreeviewSelect>>", self._tree_selected)
        self.tree.bind("<Button-1>", self._tree_click, add="+")
        self.tree.bind("<Double-1>", self._tree_click, add="+")
        self.tree.bind("<MouseWheel>", lambda _e: self._close_inline_editor(commit=True), add="+")
        self.tree.bind("<KeyPress-Return>", lambda _e: self._start_inline_editor(self.selected_key)
                       if self.selected_key else None)

        self.empty_frame = ttk.Frame(center, style="Surface.TFrame", padding=(36, 48))
        self.empty_frame.grid(row=2, column=0, sticky="nsew")
        self.empty_frame.columnconfigure(0, weight=1)
        self.empty_frame.rowconfigure(0, weight=1)
        empty_inner = ttk.Frame(self.empty_frame, style="Surface.TFrame")
        empty_inner.grid(row=0, column=0)
        self.empty_title_label = ttk.Label(empty_inner, style="Section.TLabel", anchor="center")
        self.empty_title_label.pack(pady=(0, 8))
        self.empty_text_label = ttk.Label(
            empty_inner, background=p["surface"], foreground=p["muted"],
            justify="center", anchor="center", wraplength=420
        )
        self.empty_text_label.pack(pady=(0, 16))
        self.empty_open_btn = ttk.Button(
            empty_inner, style="Primary.TButton", command=self.open_file
        )
        self.empty_open_btn.pack()

        # Inspector -----------------------------------------------------
        inspector = ttk.Frame(workspace, style="Surface.TFrame", padding=(18, 16))
        inspector.grid(row=0, column=2, sticky="nsew")
        inspector.columnconfigure(0, weight=1)

        self.details_title = ttk.Label(inspector, style="Section.TLabel")
        self.details_title.grid(row=0, column=0, sticky="w")

        self.detail_name = ttk.Label(inspector, style="Section.TLabel", anchor="w",
                                     justify="left", wraplength=360)
        self.detail_name.grid(row=1, column=0, sticky="ew", pady=(12, 2))
        self.detail_key = ttk.Label(inspector, style="Meta.TLabel", anchor="w",
                                    justify="left", wraplength=360)
        self.detail_key.grid(row=2, column=0, sticky="ew")
        self.detail_desc = ttk.Label(inspector, background=p["surface"], foreground=p["text"],
                                     anchor="nw", justify="left", wraplength=360)
        self.detail_desc.grid(row=3, column=0, sticky="ew", pady=(10, 14))

        self.value_section_label = ttk.Label(inspector, style="Meta.TLabel")
        self.value_section_label.grid(row=4, column=0, sticky="w", pady=(0, 5))

        self.editor_holder = ttk.Frame(inspector, style="Surface.TFrame")
        self.editor_holder.grid(row=5, column=0, sticky="ew")
        self.editor_holder.columnconfigure(0, weight=1)
        self.edit_entry = ttk.Entry(self.editor_holder, textvariable=self.edit_var)
        self.edit_entry.grid(row=0, column=0, sticky="ew")
        self.edit_combo = ttk.Combobox(self.editor_holder, textvariable=self.edit_var,
                                       state="readonly")
        self.edit_entry.bind("<Return>", lambda _e: self.apply_selected())
        self.edit_entry.bind("<FocusOut>", lambda _e: self.apply_selected(show_error=False))
        self.edit_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_selected())
        self.edit_combo.bind("<FocusOut>", lambda _e: self.apply_selected(show_error=False))

        quick_actions = ttk.Frame(inspector, style="Surface.TFrame")
        quick_actions.grid(row=6, column=0, sticky="ew", pady=(10, 16))
        quick_actions.columnconfigure(0, weight=1)
        quick_actions.columnconfigure(1, weight=1)
        self.recommended_btn = ttk.Button(
            quick_actions, style="Soft.TButton", command=self.use_recommended, state="disabled"
        )
        self.recommended_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.reset_selected_btn = ttk.Button(
            quick_actions, style="Secondary.TButton", command=self.reset_selected, state="disabled"
        )
        self.reset_selected_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        ttk.Separator(inspector, orient="horizontal").grid(row=7, column=0, sticky="ew", pady=(0, 14))

        self.guidance_title = ttk.Label(inspector, style="Section.TLabel")
        self.guidance_title.grid(row=8, column=0, sticky="w", pady=(0, 8))

        cards = ttk.Frame(inspector, style="Surface.TFrame")
        cards.grid(row=9, column=0, sticky="ew")
        for c in range(2):
            cards.columnconfigure(c, weight=1)

        self.guide_cards = {}
        card_order = ("default", "recommended", "minimum", "maximum")
        for idx, key in enumerate(card_order):
            card = ttk.Frame(cards, style="CardAlt.TFrame", padding=(10, 8))
            card.grid(row=idx // 2, column=idx % 2, sticky="nsew",
                      padx=(0 if idx % 2 == 0 else 5, 5 if idx % 2 == 0 else 0),
                      pady=(0, 6))
            title = ttk.Label(card, background=p["surface_alt"], foreground=p["muted"],
                              font=(self._font()[0], 8, "bold"))
            title.pack(anchor="w")
            value = ttk.Label(card, background=p["surface_alt"], foreground=p["text"],
                              font=(self._font()[0], 12, "bold"))
            value.pack(anchor="w", pady=(3, 0))
            self.guide_cards[key] = (title, value)

        self.guide_note = ttk.Label(inspector, background=p["surface"], foreground=p["muted"],
                                    anchor="nw", justify="left", wraplength=360,
                                    font=(self._font()[0], 9))
        self.guide_note.grid(row=10, column=0, sticky="ew", pady=(4, 14))

        ttk.Separator(inspector, orient="horizontal").grid(row=11, column=0, sticky="ew",
                                                           pady=(0, 12))
        self.technical_title = ttk.Label(inspector, style="Meta.TLabel")
        self.technical_title.grid(row=12, column=0, sticky="w")
        self.technical_value = ttk.Label(inspector, background=p["surface"],
                                         foreground=p["muted"], justify="left",
                                         anchor="nw", wraplength=360,
                                         font=(self._font()[0], 9))
        self.technical_value.grid(row=13, column=0, sticky="ew", pady=(5, 0))

        # Bottom status area.
        status = ttk.Frame(self, style="App.TFrame", padding=(18, 7, 18, 10))
        status.pack(fill="x")
        status.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(status, textvariable=self.status_var, style="Status.TLabel")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.bind("<Control-o>", lambda _e: self.open_file())
        self.bind("<Control-s>", lambda _e: self.save_file())
        self.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind("<Escape>", lambda _e: self._close_inline_editor(commit=False))
        self.bind("<Configure>", self._resize_wrap)

    # ------------------------------------------------------------------
    # Language / navigation / filtering
    # ------------------------------------------------------------------

    def _resize_wrap(self, _event=None):
        inspector_width = max(300, self.winfo_width() // 4)
        wrap = max(260, inspector_width - 48)
        for widget in (self.detail_name, self.detail_key, self.detail_desc,
                       self.guide_note, self.technical_value):
            widget.configure(wraplength=wrap)

    def _language_changed(self, _event=None):
        self._close_inline_editor(commit=True, show_error=False)
        self.lang = {"English": "en", "日本語": "ja", "简体中文": "zh"}.get(
            self.lang_var.get(), "en"
        )
        self._style()
        self._apply_language()

    def _apply_language(self):
        self.title(self.t("title"))
        self.title_label.configure(text=self.t("title"))
        self.subtitle_label.configure(text=self.t("subtitle"))
        self.open_btn.configure(text=self.t("open_short"))
        self.revert_btn.configure(text=self.t("revert_all"))
        self.reset_all_btn.configure(text=self.t("reset_all"))
        self.search_label.configure(text=self.t("search"))
        self.modified_check.configure(text=self.t("modified_only"))
        self.inline_hint_label.configure(text=self.t("inline_hint"))
        self.empty_title_label.configure(text=self.t("empty_title"))
        self.empty_text_label.configure(text=self.t("empty_text"))
        self.empty_open_btn.configure(text=self.t("open"))
        self.details_title.configure(text=self.t("details"))
        self.value_section_label.configure(text=self.t("current_value"))
        self.recommended_btn.configure(text=self.t("use_recommended"))
        self.reset_selected_btn.configure(text=self.t("reset_selected_short"))
        self.guidance_title.configure(text=self.t("recommended_values"))
        self.technical_title.configure(text=self.t("technical"))
        self.category_title.configure(text=self.t("category"))

        self.tree.heading("setting", text=self.t("setting"))
        self.tree.heading("value", text=self.t("value"))
        self.tree.heading("default", text=self.t("default"))

        guide_titles = {
            "default": self.t("default"),
            "recommended": self.t("recommended"),
            "minimum": self.t("minimum"),
            "maximum": self.t("maximum"),
        }
        for key, (title, _) in self.guide_cards.items():
            title.configure(text=guide_titles[key])

        self.category_list.configure(font=self._font())
        explicit_font = self._font()[0]
        self.detail_desc.configure(font=(explicit_font, 10))
        self.guide_note.configure(font=(explicit_font, 9))
        self.technical_value.configure(font=(explicit_font, 9))
        self.empty_text_label.configure(font=(explicit_font, 10))
        for title, value in self.guide_cards.values():
            title.configure(font=(explicit_font, 8, "bold"))
            value.configure(font=(explicit_font, 12, "bold"))

        self._refresh_sidebar()
        self._rebuild_table(preserve_selection=True)
        self._refresh_detail()
        self._update_dirty_state()
        if not self.doc:
            self.path_var.set(self.t("no_file"))

    def _category_label(self, category):
        if category == "all":
            return self.t("all_settings")
        return self.t("cat_" + category)

    def _category_count(self, category):
        if category == "all":
            return len(self.all_keys)
        return sum(1 for key in self.all_keys if category_for(key) == category)

    def _refresh_sidebar(self):
        selected = self.current_category
        self.category_list.delete(0, "end")
        for category in self.CATEGORY_ORDER:
            count = self._category_count(category) if self.doc else 0
            label = self._category_label(category)
            self.category_list.insert("end", f"{label}   {count}" if self.doc else label)
        try:
            index = self.CATEGORY_ORDER.index(selected)
        except ValueError:
            index = 0
            self.current_category = "all"
        self.category_list.selection_clear(0, "end")
        self.category_list.selection_set(index)
        self.category_list.activate(index)

    def _category_selected(self, _event=None):
        selection = self.category_list.curselection()
        if not selection:
            return
        self.current_category = self.CATEGORY_ORDER[selection[0]]
        self._rebuild_table(preserve_selection=True)

    def _schedule_filter(self):
        if self.filter_after is not None:
            self.after_cancel(self.filter_after)
        self.filter_after = self.after(120, lambda: self._rebuild_table(preserve_selection=True))

    def _build_search_cache(self):
        self.search_cache = {}
        for key in self.all_keys:
            bits = [key, self.kinds.get(key, ""), category_for(key)]
            for language in ("en", "ja", "zh"):
                name, description = meta_for(key, language)
                bits.extend((name, description))
            self.search_cache[key] = " ".join(bits).casefold()

    def _rebuild_table(self, preserve_selection=False):
        self._close_inline_editor(commit=True, show_error=False)
        old = self.selected_key if preserve_selection else None
        self.tree.delete(*self.tree.get_children())

        if not self.doc:
            self.count_var.set("")
            return

        query = self.search_var.get().strip().casefold()
        modified_only = bool(self.modified_only_var.get())
        shown = 0

        for key in self.all_keys:
            category = category_for(key)
            if self.current_category != "all" and category != self.current_category:
                continue
            if modified_only and key not in self.modified_keys:
                continue
            if query and query not in self.search_cache.get(key, ""):
                continue

            name, _ = meta_for(key, self.lang)
            tags = ("modified",) if key in self.modified_keys else ()
            self.tree.insert(
                "", "end", iid=key,
                values=(name, self.values.get(key, ""), format_default(DEFAULTS.get(key))),
                tags=tags,
            )
            shown += 1

        self.count_var.set(self.t("search_results", shown=shown))
        if old and self.tree.exists(old):
            self.tree.selection_set(old)
            self.tree.see(old)
        elif self.selected_key and not self.tree.exists(self.selected_key):
            self.selected_key = None
            self._refresh_detail()

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def _tree_click(self, event):
        if not self.doc:
            return
        region = self.tree.identify_region(event.x, event.y)
        row_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if row_id:
            self.tree.selection_set(row_id)
            self.selected_key = row_id
        if region == "cell" and row_id and column == "#2":
            self.after_idle(lambda key=row_id: self._start_inline_editor(key))
        elif self.inline_editor is not None:
            self._close_inline_editor(commit=True)

    def _start_inline_editor(self, key):
        if not self.doc or not key or not self.tree.exists(key):
            return
        self._close_inline_editor(commit=True)
        bbox = self.tree.bbox(key, "value")
        if not bbox:
            return
        x, y, width, height = bbox
        kind = self.kinds.get(key, "str")
        var = tk.StringVar(value=str(self.values.get(key, "")))

        if kind == "bool":
            widget = ttk.Combobox(self.tree, textvariable=var,
                                  values=["True", "False"], state="readonly")
            widget.bind("<<ComboboxSelected>>",
                        lambda _e: self._close_inline_editor(commit=True))
        elif kind == "enum" and key in ENUM_CHOICES:
            widget = ttk.Combobox(self.tree, textvariable=var,
                                  values=ENUM_CHOICES[key], state="readonly")
            widget.bind("<<ComboboxSelected>>",
                        lambda _e: self._close_inline_editor(commit=True))
        else:
            widget = ttk.Entry(self.tree, textvariable=var)

        widget._inline_var = var
        widget.place(x=x, y=y, width=max(width, 100), height=max(height, 28))
        widget.bind("<Return>", lambda _e: self._close_inline_editor(commit=True))
        widget.bind("<Tab>", lambda _e: self._close_inline_editor(commit=True))
        widget.bind("<Escape>", lambda _e: self._close_inline_editor(commit=False))
        widget.bind("<FocusOut>", lambda _e: self.after_idle(
            lambda: self._close_inline_editor(commit=True, show_error=False)
        ))
        self.inline_editor = widget
        self.inline_editor_key = key
        widget.focus_set()
        if isinstance(widget, ttk.Entry):
            widget.selection_range(0, "end")

    def _close_inline_editor(self, commit=True, show_error=True):
        if self.inline_editor is None or self.inline_editor_committing:
            return True
        widget = self.inline_editor
        key = self.inline_editor_key

        if commit and key:
            self.inline_editor_committing = True
            try:
                if not self._set_value_from_text(
                    key, widget._inline_var.get(), show_error=show_error
                ):
                    if show_error:
                        try:
                            widget.focus_set()
                        except Exception:
                            pass
                    return False
            finally:
                self.inline_editor_committing = False

        try:
            widget.destroy()
        except Exception:
            pass
        self.inline_editor = None
        self.inline_editor_key = None
        return True

    def _set_value_from_text(self, key, raw, show_error=True):
        import copy
        if not self.doc or key not in self.doc.settings:
            return False

        prop = copy.deepcopy(self.doc.settings[key])
        try:
            apply_value(key, prop, raw)
        except Exception as exc:
            if show_error:
                messagebox.showerror(
                    self.t("save_error"),
                    self.t("invalid_value", key=key, detail=str(exc)),
                    parent=self,
                )
            return False

        normalized = display_value(prop)
        self.values[key] = normalized
        self._update_dirty_state()

        if self.tree.exists(key):
            values = list(self.tree.item(key, "values"))
            values[1] = normalized
            self.tree.item(
                key, values=values,
                tags=("modified",) if key in self.modified_keys else ()
            )

        if self.selected_key == key:
            self.edit_var.set(str(normalized))
            self._refresh_detail(preserve_editor=True)

        return True

    def _tree_selected(self, _event=None):
        selection = self.tree.selection()
        self.selected_key = selection[0] if selection else None
        self._refresh_detail()

    def _refresh_detail(self, preserve_editor=False):
        key = self.selected_key
        if not key or not self.doc or key not in self.values:
            self.detail_edit_key = None
            self.detail_name.configure(text=self.t("selected_help"))
            self.detail_key.configure(text="")
            self.detail_desc.configure(text="")
            self.technical_value.configure(text="")
            self.edit_var.set("")
            self.edit_entry.configure(state="disabled")
            self.edit_combo.configure(state="disabled")
            self.recommended_btn.configure(state="disabled")
            self.reset_selected_btn.configure(state="disabled")
            for _, value in self.guide_cards.values():
                value.configure(text="—")
            self.guide_note.configure(text=self.t("range_unknown"))
            return

        self.detail_edit_key = key
        name, description = meta_for(key, self.lang)
        self.detail_name.configure(text=name)
        self.detail_key.configure(text=key)
        self.detail_desc.configure(text=description)
        if not preserve_editor:
            self.edit_var.set(str(self.values[key]))

        guide = guidance_for(key)
        guide_values = {
            "default": guidance_text(guide["default"]),
            "recommended": guidance_text(guide["recommended"]),
            "minimum": guidance_text(guide["min"]),
            "maximum": guidance_text(guide["max"]),
        }
        for card_key, (_, value) in self.guide_cards.items():
            value.configure(text=guide_values[card_key])

        if guide["range_type"] == "common":
            self.guide_note.configure(text=self.t("range_common"))
        elif guide["range_type"] == "official":
            self.guide_note.configure(text=self.t("range_official"))
        else:
            self.guide_note.configure(text=self.t("range_unknown"))

        kind = self.kinds.get(key, "str")
        prop_type = self.doc.settings[key].get("type", "—")
        category = self._category_label(category_for(key))
        modified_text = self.t("modified") if key in self.modified_keys else "—"
        self.technical_value.configure(
            text=f"{self.t('key')}: {key}\n{self.t('type')}: {prop_type}\n"
                 f"{self.t('category')}: {category}\n{self.t('modified')}: {modified_text}"
        )

        self.edit_combo.grid_forget()
        self.edit_entry.grid_forget()
        if kind == "bool":
            self.edit_combo.configure(values=["True", "False"], state="readonly")
            self.edit_combo.grid(row=0, column=0, sticky="ew")
        elif kind == "enum" and key in ENUM_CHOICES:
            self.edit_combo.configure(values=ENUM_CHOICES[key], state="readonly")
            self.edit_combo.grid(row=0, column=0, sticky="ew")
        else:
            self.edit_entry.configure(state="normal")
            self.edit_entry.grid(row=0, column=0, sticky="ew")

        self.reset_selected_btn.configure(
            state="normal" if key in DEFAULTS and not self.busy else "disabled"
        )
        has_recommended = guidance_for(key)["recommended"] is not None
        self.recommended_btn.configure(
            state="normal" if has_recommended and not self.busy else "disabled"
        )

    def apply_selected(self, show_error=True):
        key = self.detail_edit_key
        if not key or not self.doc:
            return True
        return self._set_value_from_text(key, self.edit_var.get(), show_error=show_error)

    def use_recommended(self):
        key = self.selected_key
        if not key:
            return
        value = guidance_for(key)["recommended"]
        if value is None:
            messagebox.showinfo(
                self.t("recommended_values"),
                self.t("recommended_unavailable"),
                parent=self,
            )
            return
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        self._set_value_from_text(key, str(value))

    def reset_selected(self):
        key = self.selected_key
        if not key or key not in DEFAULTS:
            return
        value = DEFAULTS[key]
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        self._set_value_from_text(key, str(value))

    def reset_defaults(self):
        if not self.doc:
            return
        if not messagebox.askyesno(
            self.t("reset"), self.t("reset_confirm"), parent=self
        ):
            return
        for key in self.all_keys:
            if key not in DEFAULTS:
                continue
            value = DEFAULTS[key]
            self.values[key] = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        self._update_dirty_state()
        self._rebuild_table(preserve_selection=True)
        self._refresh_detail()
        self.status_var.set(self.t("ready"))

    def revert_all(self):
        if not self.doc or not self.modified_keys:
            return
        if not messagebox.askyesno(
            self.t("revert_all"), self.t("revert_confirm"), parent=self
        ):
            return
        self.values = dict(self.original_values)
        self._update_dirty_state()
        self._rebuild_table(preserve_selection=True)
        self._refresh_detail()
        self.status_var.set(self.t("ready"))

    # ------------------------------------------------------------------
    # Dirty state / commands
    # ------------------------------------------------------------------

    def _update_dirty_state(self):
        if not self.doc:
            self.modified_keys = set()
        else:
            self.modified_keys = {
                key for key in self.all_keys
                if str(self.values.get(key, "")) != str(self.original_values.get(key, ""))
            }

        count = len(self.modified_keys)
        if count:
            self.dirty_badge.configure(text=self.t("unsaved_count", count=count))
            self.dirty_badge.grid()
        else:
            self.dirty_badge.grid_remove()

        if not self.busy:
            self.save_btn.configure(state="normal" if self.doc and count else "disabled")
            self.revert_btn.configure(state="normal" if self.doc and count else "disabled")
            self.reset_all_btn.configure(state="normal" if self.doc else "disabled")
        self.save_btn.configure(
            text=self.t("save_count", count=count) if count else self.t("save")
        )

    def _set_busy(self, busy, status=None):
        self.busy = bool(busy)
        if busy:
            self.open_btn.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            self.revert_btn.configure(state="disabled")
            self.reset_all_btn.configure(state="disabled")
            self.recommended_btn.configure(state="disabled")
            self.reset_selected_btn.configure(state="disabled")
        else:
            self.open_btn.configure(state="normal")
            self._update_dirty_state()
            self._refresh_detail()
        if status:
            self.status_var.set(status)

    # ------------------------------------------------------------------
    # File workflow
    # ------------------------------------------------------------------

    def open_file(self):
        if self.modified_keys:
            proceed = messagebox.askyesno(
                self.t("open"), self.t("revert_confirm"), parent=self
            )
            if not proceed:
                return

        initial = DEFAULT_SAVE_ROOT if DEFAULT_SAVE_ROOT.exists() else DEFAULT_SAVE_ROOT.parent
        path = filedialog.askopenfilename(
            parent=self,
            title=self.t("open"),
            initialdir=str(initial),
            initialfile=SAVE_FILENAME,
            filetypes=[("WorldOption.sav", "WorldOption.sav")],
        )
        if not path:
            return
        if Path(path).name.casefold() != SAVE_FILENAME.casefold():
            messagebox.showerror(
                self.t("load_error"), self.t("invalid_name"), parent=self
            )
            return

        self._set_busy(True, self.t("loading"))

        def worker():
            try:
                doc = WorldOptionDocument().load(path)
                self.worker_queue.put(("load_ok", doc))
            except Exception as exc:
                self.worker_queue.put(("load_error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_load(self, doc):
        self.doc = doc
        self.all_keys = list(doc.settings.keys())
        self.values = {key: display_value(prop) for key, prop in doc.settings.items()}
        self.original_values = dict(self.values)
        self.kinds = {key: property_kind(prop) for key, prop in doc.settings.items()}
        self._build_search_cache()
        self.selected_key = None
        self.detail_edit_key = None
        self.current_category = "all"
        self.modified_only_var.set(False)
        self.search_var.set("")
        self.path_var.set(str(doc.path))
        self.empty_frame.grid_remove()
        self._update_dirty_state()
        self._refresh_sidebar()
        self._rebuild_table()
        self._refresh_detail()
        self._set_busy(False, self.t("loaded_short", count=len(self.all_keys)))

    def save_file(self):
        if not self.doc or not self.modified_keys:
            return
        if not self._close_inline_editor(commit=True):
            return
        if self.detail_edit_key and not self.apply_selected():
            return

        edited = dict(self.values)
        self._set_busy(True, self.t("saving"))

        def worker():
            try:
                backup = self.doc.save(edited)
                self.worker_queue.put(("save_ok", backup))
            except Exception as exc:
                self.worker_queue.put(("save_error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_workers(self):
        try:
            while True:
                kind, payload = self.worker_queue.get_nowait()

                if kind == "load_ok":
                    self._finish_load(payload)

                elif kind == "load_error":
                    self._set_busy(False, self.t("ready"))
                    if isinstance(payload, SaveFormatError) and str(payload) == "PYOOZ_REQUIRED":
                        detail = self.t("need_pyooz")
                    elif isinstance(payload, ValueError) and str(payload) == "INVALID_NAME":
                        detail = self.t("invalid_name")
                    else:
                        detail = str(payload)
                    messagebox.showerror(self.t("load_error"), detail, parent=self)

                elif kind == "save_ok":
                    self.values = {
                        key: display_value(prop) for key, prop in self.doc.settings.items()
                    }
                    self.original_values = dict(self.values)
                    self.kinds = {
                        key: property_kind(prop) for key, prop in self.doc.settings.items()
                    }
                    self._update_dirty_state()
                    self._rebuild_table(preserve_selection=True)
                    self._refresh_detail()
                    self._set_busy(False, self.t("saved_clean"))
                    messagebox.showinfo(
                        self.t("save"),
                        self.t("saved", backup=str(payload)),
                        parent=self,
                    )

                elif kind == "save_error":
                    self._set_busy(False, self.t("ready"))
                    if isinstance(payload, ExternalFileChangedError):
                        detail = self.t("external_change")
                    elif isinstance(payload, ValueError) and "\n" in str(payload):
                        key, error = str(payload).split("\n", 1)
                        detail = self.t("invalid_value", key=key, detail=error)
                    else:
                        detail = str(payload)
                    messagebox.showerror(self.t("save_error"), detail, parent=self)

        except queue.Empty:
            pass

        self.after(80, self._poll_workers)

    def _on_close(self):
        self._close_inline_editor(commit=True, show_error=False)
        if self.modified_keys:
            if not messagebox.askyesno(
                self.t("revert_all"), self.t("revert_confirm"), parent=self
            ):
                return
        self.destroy()

def dependency_check():
    if GvasFile is not None:
        return True
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Missing dependency", I18N["en"]["missing_dep"], parent=root)
    root.destroy()
    return False

def main():
    if not dependency_check():
        return 1
    EditorApp().mainloop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
