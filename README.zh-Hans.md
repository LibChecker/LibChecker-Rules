# LibChecker-Rules

[![Rules version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.rulesVersion&label=Rules&color=6f42c1&style=flat&cacheSeconds=3600)](cloud/md5/v4)
[![Native libraries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.nativeLibraries&label=Native%20libraries&color=0969da&style=flat&cacheSeconds=3600)](native-libs/)
[![Activities](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.activities&label=Activities&color=1a7f37&style=flat&cacheSeconds=3600)](activities-libs/)
[![Services](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.services&label=Services&color=bf8700&style=flat&cacheSeconds=3600)](services-libs/)
[![Receivers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.receivers&label=Receivers&color=cf222e&style=flat&cacheSeconds=3600)](receivers-libs/)
[![Providers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.providers&label=Providers&color=8250df&style=flat&cacheSeconds=3600)](providers-libs/)
[![Intent actions](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.intentActions&label=Intent%20actions&color=1b7c83&style=flat&cacheSeconds=3600)](actions-libs/)
[![Static libraries](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.staticLibraries&label=Static%20libraries&color=57606a&style=flat&cacheSeconds=3600)](static-libs/)
[![Chart rules](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FLibChecker%2FLibChecker-Rules%2FHEAD%2Frule-counts.json&query=%24.chartRules&label=Chart%20rules&color=bf3989&style=flat&cacheSeconds=3600)](chart/rules/)

[English](README.md) | 简体中文

本仓库维护 [LibChecker](https://github.com/LibChecker/LibChecker) 使用的规则与元数据，包括 Android 组件和原生库识别规则、Flutter 引擎版本映射，以及图表页面使用的声明式统计规则。

## 仓库内容

| 路径 | 内容 |
| --- | --- |
| `native-libs/`、`activities-libs/`、`services-libs/`、`receivers-libs/`、`providers-libs/`、`actions-libs/`、`static-libs/` | 根据原生库、Android 组件和 Intent Action 识别应用使用的库与 SDK。 |
| [`flutter_hash/`](flutter_hash/README.md) | 将 `libflutter.so` 中的引擎修订号映射到可能对应的 Flutter 发布版本。 |
| [`chart/`](chart/README.zh-Hans.md) | 存放图表规则、SVG 图标、JSON Schema、测试和生成后的 Bundle。 |
| `configuration/`、`cloud/` | 存放 LibChecker 读取的版本配置与规则数据。 |

## 参与贡献

### 库识别规则

发现缺失或错误的库识别规则时，请在 [Issue 选择页面](https://github.com/LibChecker/LibChecker-Rules/issues/new/choose)中选择 **Submit new rule** 或 **Bug report**，并按照模板填写文件名、库名称、开发团队、说明与一手资料链接。有可供验证的应用时，也请附上应用名称和版本。图标仅接受 SVG 格式。

### 图表规则

图表规则有独立的 Schema、测试和发布流程。新规则通常先进入预览渠道，验证通过后再发布到稳定渠道。提交前请阅读完整指南：

- [简体中文贡献指南](chart/README.zh-Hans.md)
- [English contribution guide](chart/README.md)

如果使用支持 Skills 的 AI Agent，可以安装仓库内的图表规则 Skill：

```shell
npx skills add LibChecker/LibChecker-Rules
```

安装与使用说明见[图表规则 Skill 指南](skills/libchecker-chart-rules/README.zh-Hans.md)。

## 许可

本仓库基于 [Apache License 2.0](LICENSE) 发布。
