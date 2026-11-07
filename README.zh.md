# NTE Drive Calc Global

[한국어](README.md) · [简体中文](README.zh.md) · [English](README.en.md) · [日本語](README.ja.md)

**这是 LuinDe 基于 NTE Drive Calc 独立维护的非官方多语言衍生项目。** 项目从韩语补丁发展而来，增加了翻译与计算辅助功能。它不是原作者发布或支持的官方 Global 版本。

## 原作者与原项目

- 原作者：**[hxwd94666](https://github.com/hxwd94666) 及 NTE Drive Calc contributors**
- 原项目源码：**[NTE-Drive-Calculator](https://github.com/hxwd94666/NTE-Drive-Calculator)**
- 原项目发布页：**[NTE-Drive-Calc](https://github.com/hxwd94666/NTE-Drive-Calc)**
- Global 维护者：[LuinDe](https://github.com/LuinDe)；Global 问题请提交到[本仓库 Issues](https://github.com/LuinDe/NTE-Drive-Calc-Global/issues)。

保留原链接以注明来源。2026-11-07 检查时原仓库无法访问，原因尚未确认。本项目不声称获得原作者的官方背书、支持或共同开发。

## 当前版本：2.3.6

**[下载 v2.3.6 与阅读发布说明](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.6)**

适用于 Windows 10/11 x64。安装包为 `NTE_Drive_Calc_2.3.6_Multilingual_Setup.exe`，公开源码包为 `NTE_Drive_Calc_2.3.6_Multilingual_source.zip`。当前仅保留 2.3.6 发布版；旧发布与版本标签已清理，Git 源码历史保留。

- 加入曳尔沐（1090）的国服 1.5.4 数据、图鉴、装备布局与 Core 背包映射。
- 2.3.6 修复曳尔沐立绘格式导致的启动错误。
- 曳尔沐的实测 DPS 循环尚未完成，因此不参与队伍模拟及基于循环的效率表。连接实际国际服游戏的背包同步验证尚未完成。

2026-11-07 的源码与文档补充**没有修改现有 2.3.6 安装包**。本次恢复遗漏的 121 个原项目公开文件，更新源码 ZIP、许可说明与发布说明。旧安装包内“ZIP 包含全部对应源码”的说法不准确，请同时阅读[更正说明](docs/SOURCE_OFFER_CORRECTION_2.3.6.md)。

## 主要功能

- 韩语、简体中文、英语、日语界面，可在程序内切换。
- 保留原项目的库存同步、装备鉴定与分配、角色管理及战斗报告。
- 队伍模拟（Beta）、自定义输出循环、弧盘与觉醒效率表。
- 噗卡特训、战斗报告中的个人角色比较、Global 独立签名校验更新。

计算结果仅供参考，取决于已实现的模型和数据范围，不能还原所有角色效果及实战情况。[曳尔沐说明](build_tools/ELYMS.md)列出了适用范围和数据来源。

## 安装与使用

1. 关闭计算器并备份现有账号与设置数据。
2. 下载并运行 [v2.3.6](https://github.com/LuinDe/NTE-Drive-Calc-Global/releases/tag/v2.3.6) 安装包。安装程序使用现有安装位置，并按设计保留用户数据。
3. 使用左下角的语言按钮切换界面。队伍模拟与效率表的操作见[详细使用方法](docs/USAGE.zh.md)。

使用旧签名密钥的 2.3.2 及更早版本需要手动安装一次 2.3.6。之后仅从此 Global 仓库检查更新。游戏连接兼容性取决于游戏构建及原生组件。

## 源码与许可状态

应用程序遵循原项目的 [GNU AGPL-3.0](LICENSE)，原始版权与 Global 修改声明保存在 [NOTICE](NOTICE)。捆绑组件分别遵循各自许可。

- 已公开：修改后的 `src/`、入口文件、依赖锁文件、原项目及 Global 构建工具、公开原生原型、修改材料和许可记录。
- **尚未解决：** 当前仓库与 ZIP 未提供所分发 Core、analysis Core、Loader（AGPL）以及 5 个捕获 DLL（GPL）的精确完整对应源码。`native/` 原型和曳尔沐资源修改脚本不能替代这些源码。
- 游戏图片与数据属于各自权利人。本次补充不表示所有再分发条件均已满足。

[源码范围与待解决事项](SOURCE_OFFER.md) · [构建说明](build_tools/README.md) · [恢复文件及哈希](UPSTREAM_SOURCE_FILES.json) · [历史源码](docs/source-history.md)
