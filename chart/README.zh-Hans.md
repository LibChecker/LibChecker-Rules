# 图表规则贡献指南

[English](README.md) | 简体中文

本目录存放 LibChecker 图表页面使用的声明式统计规则。规则负责描述需要检查的数据、判定匹配的条件，以及向用户显示的标题、说明和图标。

规则不能执行脚本或任意代码。APK、DEX、Manifest 和原生文件的遍历都由 LibChecker 实现。规则只能组合当前客户端已经支持的证据类型和操作符。

## 开始之前

编写 JSON 前，请先确认以下问题：

1. 这个图表统计什么，它对 LibChecker 用户有什么作用？
2. 已安装应用中的哪类证据能够证明匹配？
3. 每个应用只会得到“匹配或不匹配”的结果，还是可能同时匹配多项能力？
4. 是否有介绍该技术或能力的 HTTPS 一手资料？
5. 是否有已知匹配和不匹配的 APK 可用于验证？

Schema v1 只能使用[证据类型参考](#证据类型参考)中列出的证据。如果规则需要 DEX 字段、资源表条目、原生符号、证书属性或任意文件内容等新数据，请先在 LibChecker 客户端中设计并实现通用的证据提供器，不要在规则中绕过这一限制。

新规则通常应先设置 `"releaseChannel": "preview-only"`。使用兼容的 LibChecker 版本完成预览验证后，再将规则发布到稳定渠道。

## 提交流程

1. Fork 本仓库并创建独立分支。
2. 从 `rules/` 中选择最接近的示例：
   - 精确匹配原生库参考 [`flutter.json`](rules/flutter.json)。
   - 精确匹配 APK 条目并使用 DEX 作为后备证据，参考 [`reactivex.json`](rules/reactivex.json)。
   - Facet、递归条件、DEX 查询和 Manifest Receiver Action 参考 [`itgsa.json`](rules/itgsa.json)。
   - 数值比较参考下文的 [Predicate 示例](#predicate-计算)。
3. 在 `rules/` 下新增一个 UTF-8 JSON 文件。使用四个空格缩进，文件名与规则 ID 的最后一段保持一致。
4. 在 `icons/` 下添加规则引用的 SVG。
5. 更新测试中的规则 ID、图标、Catalog 数量和稳定渠道内容，并为新规则的关键判定数据添加专门断言。
6. 运行单元测试，并将预览 Bundle 生成到临时目录。
7. 使用已知匹配和不匹配的应用验证预览规则。
8. 按照目标分支确定的 Bundle 版本和最低应用版本，重新生成 `cloud/v1/chart.bundle` 与 `cloud/v1/manifest.json`。
9. 在同一个 Pull Request 中提交源规则、图标、测试、生成的 Bundle 和 Manifest。PR 描述中应写明证据来源与人工测试结果。

从仓库根目录运行：

```shell
python3 -m unittest chart.tools.test_build_bundle
python3 chart/tools/build_bundle.py \
  --bundle-version 12 \
  --channel preview \
  --minimum-app-version-code 2731 \
  --output-dir /tmp/libchecker-chart-preview
```

上面的数字只是示例。选择 Bundle 版本或最低应用版本前，请先检查 `chart/cloud/v1/manifest.json` 和目标分支的发布状态。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `rules/` | 经过审核的源规则，每个统计项对应一个 JSON 文件。 |
| `icons/` | 源规则引用的 SVG 图标。 |
| `schema/v1/chart-rule.schema.json` | 源规则的机器可读 Schema。 |
| `schema/v1/manifest.schema.json` | 生成后 Manifest 的机器可读 Schema。 |
| `tools/build_bundle.py` | 校验器和确定性 Bundle 生成器。 |
| `tools/test_build_bundle.py` | 源规则校验与 Bundle 回归测试。 |
| `cloud/v1/chart.bundle` | LibChecker 使用的已生成 Catalog 与图标。 |
| `cloud/v1/manifest.json` | 已生成的版本、兼容性、大小和校验和信息。 |

## 最小完整规则

以下示例包含一个完整的单条件规则：

```json
{
    "id": "official.example-sdk",
    "revision": 1,
    "source": "official",
    "releaseChannel": "preview-only",
    "title": {
        "translations": {
            "en": "Example SDK",
            "zh-Hans": "示例 SDK"
        }
    },
    "details": {
        "description": {
            "translations": {
                "en": "Example SDK provides a documented capability for Android apps.",
                "zh-Hans": "示例 SDK 为 Android 应用提供一项有公开文档的能力。"
            }
        },
        "referenceUrl": "https://example.com/android-sdk"
    },
    "icon": {
        "asset": "icons/example-sdk.svg",
        "renderMode": "monochrome",
        "tintRole": "on_surface"
    },
    "calculation": {
        "kind": "predicate",
        "predicate": {
            "evidence": "native_library",
            "operator": "contains",
            "value": {
                "string": "libexample.so"
            },
            "matchedTitle": {
                "translations": {
                    "en": "Example SDK apps",
                    "zh-Hans": "示例 SDK 应用"
                }
            },
            "unmatchedTitle": {
                "translations": {
                    "en": "Other apps",
                    "zh-Hans": "其他应用"
                }
            }
        }
    },
    "fingerprint": "artifact"
}
```

## 顶层参数

源规则 Schema 不允许出现未定义的字段。官方在线规则可以使用以下顶层参数。

| 参数 | 是否必填 | 类型或全部可选值 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | 是 | 符合 `official.<name>` 格式的字符串 | 无 | 统计规则的永久标识。 |
| `revision` | 是 | 不小于 `1` 的整数 | 无 | 当前规则定义的修订号。 |
| `source` | 是 | `official` | 无 | 本仓库在线规则的来源类型。 |
| `title` | 是 | 多语言文本对象 | 无 | LibChecker 显示的图表标题。 |
| `details` | 是 | 对象 | 无 | 应用内说明与一手资料链接。 |
| `icon` | 是 | 对象 | 无 | Bundle 内的 SVG 及其渲染方式。 |
| `calculation` | 是 | `predicate`、`facets` | 无 | 应用的分类方式。 |
| `releaseChannel` | 否 | `stable`、`preview-only` | `stable` | 决定规则进入哪些渠道的 Bundle。 |
| `availability` | 否 | `always` | `always` | 可用性限制。Schema v1 在线规则只支持始终可用。 |
| `requiresFeatureInitialization` | 否 | `true`、`false` | `false` | 是否在特征初始化完成前隐藏图表。 |
| `controls` | 否 | 只能是空数组 `[]` | `[]` | Schema v1 不支持在线图表控件。 |
| `dashboard` | 否 | `none` | `none` | Schema v1 不支持在线 Dashboard 集成。 |
| `fingerprint` | 否 | `standard`、`features`、`artifact` | `standard` | 用于判断图表缓存是否失效的应用数据指纹。 |

JSON Schema 中的 `default` 用于说明客户端默认行为。Bundle 生成器不会把缺少的可选字段自动写入 Catalog。

### `id`

ID 必须符合：

```text
^official\.[a-z0-9]+(?:[.-][a-z0-9]+)*$
```

| 示例 | 是否有效 | 原因 |
| --- | --- | --- |
| `official.flutter` | 是 | 使用 `official.` 前缀和小写名称。 |
| `official.android-api-level` | 是 | 可以使用小写字母、数字、连字符和分段点号。 |
| `official.vendor.capability` | 是 | 可以包含多个点号分段。 |
| `flutter` | 否 | 缺少 `official.` 前缀。 |
| `official.Flutter` | 否 | 包含大写字母。 |
| `official_target_sdk` | 否 | 格式不符合要求。 |

ID 应具体且不依赖容易变化的展示文案。规则发布后，不得将原 ID 用于另一项统计。源文件名应与 ID 最后一段一致，例如 `official.flutter` 使用 `flutter.json`。

### `revision`

| 场景 | 修订号处理 |
| --- | --- |
| 新规则 | 从 `1` 开始。 |
| 修改已发布规则的判定逻辑 | 加 `1`。 |
| 修改标题、说明、图标、计算类型或其他展示元数据 | 加 `1`。 |
| 只修改仓库文档，不改变规则 | 不需要修改。 |

`revision` 属于单条规则，与生成 Bundle 的 `bundleVersion` 相互独立。

### `source`

本仓库中的每条规则都必须使用：

```json
"source": "official"
```

其他值会被生成器拒绝。

## 多语言文本

`title`、`details.description`、Predicate 分组标题和 Facet 标题使用同一种结构：

```json
{
    "translations": {
        "en": "English text",
        "zh-Hans": "简体中文文本"
    }
}
```

### 多语言文本参数

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `translations` | 对象 | 是 | 2 至 16 个语言项，必须包含 `en` 和 `zh-Hans` | 语言标签到显示文本的映射。 |
| `translations.<locale>` | 字符串 | 每个已声明语言都必填 | 不能为空；图表和分组标题最多 80 个字符，Facet 标题最多 40 个字符，说明最多 1,500 个字符 | 指定语言的本地化文本。 |

| 语言标签 | 是否允许 | 含义 |
| --- | --- | --- |
| `en` | 必填 | 英文，也是运行时回退语言。 |
| `zh-Hans` | 必填 | 简体中文。 |
| `zh`、`zh-CN` | 禁止 | 必须改用 `zh-Hans`。 |
| 其他符合 Schema 的标签 | 可选 | 可以添加 `pt-BR`、`es-419` 等翻译，总数不能超过 16。 |

不同语言应表达相同含义，不能只在某一种语言中增加事实或宣传性断言。图表标题和分组标题应尽量简短。`matchedTitle` 与 `unmatchedTitle` 分别命名匹配和不匹配的两组结果，例如“Flutter 应用”和“其他应用”。

## 详情与参考链接

`details` 为必填对象：

```json
"details": {
    "description": {
        "translations": {
            "en": "A neutral introduction to the technology.",
            "zh-Hans": "对该技术的中性介绍。"
        }
    },
    "referenceUrl": "https://project.example/documentation"
}
```

### 详情参数

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `details.description` | 多语言文本 | 是 | 必须包含 `en` 和 `zh-Hans`，每种语言 1 至 1,500 个字符 | 对技术或能力的中性介绍。 |
| `details.referenceUrl` | 字符串 | 是 | HTTPS URL，必须有有效 Host，不得包含账号、密码或空白，最多 512 个字符 | 详情对话框中打开的一手资料。 |

说明只介绍技术或能力本身，不要声称当前选中的应用已经匹配。LibChecker 会在运行时追加实际分析结果。Facet 规则还会列出匹配到的 Facet 标题。

参考链接应指向项目官网、标准组织、供应商或平台的一手文档。不要使用追踪链接、短链接、推广链接、搜索结果或未经审核的第三方摘要。

## 图标

每条在线规则都要引用仓库中的一个 SVG：

```json
"icon": {
    "asset": "icons/example-sdk.svg",
    "renderMode": "monochrome",
    "tintRole": "on_surface"
}
```

### 图标参数

| 参数 | 类型 | 是否必填 | 全部可选值 | 默认值 | 含义 |
| --- | --- | --- | --- | --- | --- |
| `icon.asset` | 字符串 | 是 | `icons/<safe-name>.svg` | 无 | 会被打包进 Bundle 的仓库相对路径。 |
| `icon.renderMode` | 字符串 | 否 | `monochrome`、`original` | `monochrome` | 决定 LibChecker 是否应用主题着色。 |
| `icon.tintRole` | 字符串 | 否 | `on_surface`、`on_surface_variant`、`primary`、`secondary`、`tertiary` | `on_surface` | 单色图标使用的主题颜色。 |

| `renderMode` 值 | 渲染行为 | `tintRole` 是否生效 | 适用场景 |
| --- | --- | --- | --- |
| `monochrome` | LibChecker 使用主题颜色统一着色。 | 是 | 应随浅色或深色主题变化的单色轮廓。 |
| `original` | 保留 SVG 自带颜色。 | 否 | 品牌颜色具有识别意义的图标。 |

### SVG 要求

| 项目 | 限制 |
| --- | --- |
| `viewBox` | 必须是 `0 0 1024 1024`。 |
| 视觉边界 | 图形应大致位于居中的 `800 x 800` 区域，保持不同图标的视觉尺寸一致。 |
| 文件大小 | 小于 64 KiB。 |
| 编码 | 有效 UTF-8。 |
| 外部内容 | 禁止脚本、样式、文本节点、链接图片、实体、外部引用和 `url(...)`。 |

校验器会拒绝 `<!doctype`、`<!entity`、`<?xml-stylesheet`、`<script`、`<foreignObject`、`<image`、`<style`、`<text`、`href=`、`xlink:` 和 `url(`。请将文字转换为路径，并直接写入需要保留的填充颜色。

## 选择计算类型

应用只能落入匹配或不匹配两组时使用 `predicate`。一个应用可能同时匹配多项能力，并且界面需要显示每项能力的 Chip 时使用 `facets`。

| 统计问题 | 应使用的类型 |
| --- | --- |
| 应用是否以 SDK 35 或更高版本为目标？ | `predicate` |
| 应用是否包含 `libflutter.so`？ | `predicate` |
| 应用实现了哪些金标联盟开放能力？ | `facets` |

### `calculation` 参数

| 参数 | 类型 | 是否必填 | 全部可选值 | 含义 |
| --- | --- | --- | --- | --- |
| `calculation.kind` | 字符串 | 是 | `predicate`、`facets` | 决定必须同时提供哪一种计算对象。 |
| `calculation.predicate` | 对象 | `kind` 为 `predicate` 时必填 | 见 [Predicate 计算](#predicate-计算) | 根据一个条件生成匹配组和不匹配组。 |
| `calculation.facets` | 对象 | `kind` 为 `facets` 时必填 | 见 [Facet 计算](#facet-计算) | 除了匹配和不匹配分组，还会生成每个应用的能力 Chip。 |

只能提供 `kind` 选中的对象。在线规则不能使用客户端内置规则所使用的 `native` 计算类型。

Facet 用于可以重叠的能力，不适用于互斥分桶或数值分布。Schema v1 暂时没有支持这些场景的在线计算类型。

## Predicate 计算

Predicate 必须包含 `matchedTitle`、`unmatchedTitle` 和一个完整条件。

### `predicate` 参数

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `predicate.matchedTitle` | 多语言文本 | 是 | 每种语言 1 至 80 个字符 | 条件结果为真的应用分组名称。 |
| `predicate.unmatchedTitle` | 多语言文本 | 是 | 每种语言 1 至 80 个字符 | 条件结果为假的应用分组名称。 |
| `predicate.evidence` | 字符串 | 直接叶子写法必填 | `target_sdk`、`native_library`、`archive_entry`、`dex_class`、`manifest_receiver_action` | 叶子条件使用的证据。 |
| `predicate.operator` | 字符串 | 直接叶子写法必填 | 取决于 `evidence` | 应用于证据的比较操作。 |
| `predicate.value` | 对象 | 直接叶子写法必填 | 只能包含一种与 `evidence` 兼容的值 | 比较所需的目标值。 |
| `predicate.condition` | Condition 对象 | 递归写法必填 | 一个证据叶子、`all`、`any` 或 `not` | 代替三个直接叶子字段的递归条件。 |

单个证据叶子可以直接放在 `predicate` 中：

```json
"calculation": {
    "kind": "predicate",
    "predicate": {
        "evidence": "target_sdk",
        "operator": "greater_than_or_equal",
        "value": {
            "integer": 35
        },
        "matchedTitle": {
            "translations": {
                "en": "Target SDK 35 or newer",
                "zh-Hans": "Target SDK 35 及以上"
            }
        },
        "unmatchedTitle": {
            "translations": {
                "en": "Target SDK 34 or older",
                "zh-Hans": "Target SDK 34 及以下"
            }
        }
    }
}
```

需要组合逻辑时，用一个 `condition` 取代直接叶子的三个字段：

```json
"predicate": {
    "condition": {
        "any": [
            {
                "evidence": "native_library",
                "operator": "contains",
                "value": {
                    "string": "libexample.so"
                }
            },
            {
                "evidence": "manifest_receiver_action",
                "operator": "contains_any",
                "value": {
                    "strings": [
                        "com.example.ACTION_READY"
                    ]
                }
            }
        ]
    },
    "matchedTitle": {
        "translations": {
            "en": "Example apps",
            "zh-Hans": "示例应用"
        }
    },
    "unmatchedTitle": {
        "translations": {
            "en": "Other apps",
            "zh-Hans": "其他应用"
        }
    }
}
```

直接叶子字段与 `condition` 不能同时出现，三个直接叶子字段也不能只提供一部分。

## Facet 计算

Facet 计算包含 1 至 8 个有顺序的条目。

### `facets` 参数

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `facets.matchedTitle` | 多语言文本 | 是 | 每种语言 1 至 80 个字符 | 至少匹配一个 Facet 的应用分组名称。 |
| `facets.unmatchedTitle` | 多语言文本 | 是 | 每种语言 1 至 80 个字符 | 没有匹配任何 Facet 的应用分组名称。 |
| `facets.items` | 数组 | 是 | 1 至 8 个 Facet 对象 | 按界面展示顺序排列的能力定义。 |
| `items[].id` | 字符串 | 是 | 符合规定格式的小写局部 ID，在规则内唯一 | Facet 的稳定内部标识。 |
| `items[].title` | 多语言文本 | 是 | 每种语言 1 至 40 个字符 | 应用匹配后显示的 Chip 文案。 |
| `items[].condition` | Condition 对象 | 是 | 一个证据叶子、`all`、`any` 或 `not` | 判断当前 Facet 是否匹配。 |

```json
"calculation": {
    "kind": "facets",
    "facets": {
        "matchedTitle": {
            "translations": {
                "en": "Example capability apps",
                "zh-Hans": "示例能力应用"
            }
        },
        "unmatchedTitle": {
            "translations": {
                "en": "Other apps",
                "zh-Hans": "其他应用"
            }
        },
        "items": [
            {
                "id": "service-kit",
                "title": {
                    "translations": {
                        "en": "Service Kit",
                        "zh-Hans": "服务套件"
                    }
                },
                "condition": {
                    "evidence": "native_library",
                    "operator": "contains",
                    "value": {
                        "string": "libexample_service.so"
                    }
                }
            }
        ]
    }
}
```

Facet ID 必须符合 `^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`。ID 在当前规则中必须唯一，发布后应保持稳定。

应用至少匹配一个 Facet 时会进入图表的匹配组。所有命中的 Facet 标题都会按照 `items` 中的声明顺序显示为 Chip。不要再用一个根 `any` 重复 Facet 条件，否则会产生两份判定来源。

## Condition 条件

Condition 对象只能是一个带类型的证据叶子，或者一个逻辑操作。未定义字段会被拒绝。

### Condition 对象参数

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `evidence` | 字符串 | 叶子条件必填 | `target_sdk`、`native_library`、`archive_entry`、`dex_class`、`manifest_receiver_action` | 选择要检查的应用数据。 |
| `operator` | 字符串 | 叶子条件必填 | `equal`、`greater_than_or_equal`、`less_than_or_equal`、`contains`、`contains_any`，具体兼容性取决于 `evidence` | 选择比较方式。 |
| `value` | 对象 | 叶子条件必填 | 只能包含 `integer`、`string`、`strings`、`dexClasses` 中的一个 | 提供比较目标。 |
| `all` | Condition 数组 | `all` 节点必填 | 1 至 16 个子条件 | 所有子条件都为真时匹配。 |
| `any` | Condition 数组 | `any` 节点必填 | 1 至 16 个子条件 | 至少一个子条件为真时匹配。 |
| `not` | Condition 对象 | `not` 节点必填 | 一个子条件 | 对子条件结果取反。 |

一个对象只能定义一种操作。证据叶子必须同时包含 `evidence`、`operator` 和 `value`。逻辑节点只能包含 `all`、`any` 或 `not` 中的一个。

### `value` 对象参数

| 参数 | 类型 | 对应证据 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `integer` | 整数 | `target_sdk` | 任意 JSON 整数 | 数值比较目标。 |
| `string` | 字符串 | `native_library` | 1 至 160 个安全文件名字符 | 精确的原生库文件名。 |
| `strings` | 字符串数组 | `archive_entry`、`manifest_receiver_action` | 1 至 16 项，每项 1 至 160 个符合对应证据限制的安全字符 | 精确 APK 条目或 Receiver Action 列表，任意一项可以匹配。 |
| `dexClasses` | DEX Class Query 数组 | `dex_class` | 1 至 16 个查询 | 类查询列表，任意一个查询可以匹配。 |

一个 `value` 对象只能包含上述参数中的一个。

### 逻辑操作符

| 操作符 | 值 | 匹配语义 |
| --- | --- | --- |
| `all` | 1 至 16 个 Condition | 所有子条件匹配时为真。 |
| `any` | 1 至 16 个 Condition | 至少一个子条件匹配时为真。 |
| `not` | 一个 Condition | 将子条件结果取反。 |

```json
{
    "all": [
        {
            "evidence": "target_sdk",
            "operator": "greater_than_or_equal",
            "value": {
                "integer": 35
            }
        },
        {
            "not": {
                "evidence": "native_library",
                "operator": "contains",
                "value": {
                    "string": "liblegacy.so"
                }
            }
        }
    ]
}
```

### 条件复杂度限制

| 限制项 | 最大值 | 计算方式 |
| --- | --- | --- |
| 嵌套深度 | 8 | 根 Condition 的深度为 1。 |
| Condition 节点总数 | 64 | Predicate 单独计算；Facet 规则的所有 Facet 共用 64 个节点。 |
| 单个 `all` 或 `any` 的子条件数 | 16 | 每个数组至少包含 1 项。 |

应使用有可靠依据的最窄条件。条件更长不等于误报率更低。

## 证据类型参考

| `evidence` | 唯一兼容的 `operator` | `value` 结构 | 匹配语义 |
| --- | --- | --- | --- |
| `target_sdk` | `equal`、`greater_than_or_equal`、`less_than_or_equal` | `{ "integer": <整数> }` | 比较应用的 Target SDK。 |
| `native_library` | `contains` | `{ "string": "<库文件名>" }` | 精确匹配原生库文件名。 |
| `archive_entry` | `contains_any` | `{ "strings": ["<条目名称>", ...] }` | Base APK 或 Split APK 中存在任意一个精确条目时为真。 |
| `dex_class` | `contains_any` | `{ "dexClasses": [<查询>, ...] }` | 任意查询匹配任意一个 DEX 类时为真。 |
| `manifest_receiver_action` | `contains_any` | `{ "strings": ["<action>", ...] }` | Manifest Receiver 声明任意一个 Action 时为真。 |

### `target_sdk`

| 参数 | 值 |
| --- | --- |
| `evidence` | `target_sdk` |
| `operator` | `equal`、`greater_than_or_equal`、`less_than_or_equal` |
| `value` | 只包含一个 `integer` |
| 推荐 `fingerprint` | `standard`，也可以省略并使用默认值 |

整数会与已安装应用记录的 Target API 比较。Schema 没有限制 API Level 的范围，但提交的值应当对应真实的 Android API Level。

```json
{
    "evidence": "target_sdk",
    "operator": "less_than_or_equal",
    "value": {
        "integer": 34
    }
}
```

### `native_library`

| 参数 | 值 |
| --- | --- |
| `evidence` | `native_library` |
| `operator` | 只能是 `contains` |
| `value.string` | 1 至 160 个字符，只允许 ASCII 字母、数字、`.`、`_`、`+`、`-` |
| 推荐 `fingerprint` | `artifact` |

值是精确的 `.so` 文件名，不是路径、正则表达式或子串。LibChecker 会检查已解压的原生库和 APK 内打包的原生库。

```json
{
    "evidence": "native_library",
    "operator": "contains",
    "value": {
        "string": "libflutter.so"
    }
}
```

### `archive_entry`

| 参数 | 值 |
| --- | --- |
| `evidence` | `archive_entry` |
| `operator` | 只能是 `contains_any` |
| `value.strings` | 1 至 16 个精确 ZIP 条目名称，每项 1 至 160 个字符 |
| 推荐 `fingerprint` | `artifact` |

该证据检查 Base APK 和 Split APK 中的精确 ZIP 条目名称，不读取文件内容，也不支持前缀、Glob 或正则表达式。

```json
{
    "evidence": "archive_entry",
    "operator": "contains_any",
    "value": {
        "strings": [
            "META-INF/example.properties"
        ]
    }
}
```

条目名称只允许 ASCII 字母、数字、`.`、`_`、`+`、`-` 和 `/`，不能以 `/` 结尾，也不能包含 `.` 或 `..` 路径段。

### `manifest_receiver_action`

| 参数 | 值 |
| --- | --- |
| `evidence` | `manifest_receiver_action` |
| `operator` | 只能是 `contains_any` |
| `value.strings` | 1 至 16 项，每项 1 至 160 个字符，只允许 ASCII 字母、数字、`_`、`.`、`-` |
| 推荐 `fingerprint` | `artifact` |

该证据读取 Base APK 和 Split APK 中由 Manifest 声明的 Broadcast Receiver Action。列表中至少一个 Action 存在时即为匹配。

```json
{
    "evidence": "manifest_receiver_action",
    "operator": "contains_any",
    "value": {
        "strings": [
            "com.example.ACTION_TRIM",
            "com.example.ACTION_KILL"
        ]
    }
}
```

### `dex_class`

| 参数 | 值 |
| --- | --- |
| `evidence` | `dex_class` |
| `operator` | 只能是 `contains_any` |
| `value.dexClasses` | 1 至 16 个 DEX Class Query |
| 推荐 `fingerprint` | `artifact` |

`dexClasses` 数组使用 OR 语义。Base APK 或 Split APK 中的任意类满足任意一个 Query 时，整个证据即为匹配。

```json
{
    "evidence": "dex_class",
    "operator": "contains_any",
    "value": {
        "dexClasses": [
            {
                "name": {
                    "operator": "starts_with",
                    "value": "Lcom/example/sdk/"
                },
                "stringConstants": [
                    "com.example.ACTION_READY"
                ],
                "methodReferences": [
                    {
                        "definingClass": "Landroid/content/IntentFilter;",
                        "name": "addAction",
                        "parameterTypes": [
                            "Ljava/lang/String;"
                        ]
                    }
                ]
            }
        ]
    }
}
```

#### DEX Class Query 参数

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 匹配语义 |
| --- | --- | --- | --- | --- |
| `name` | 对象 | 否 | 包含 `operator` 与 `value` | 限制类描述符。 |
| `stringConstants` | 字符串数组 | 否 | 1 至 16 项，每项 1 至 160 个无控制字符的字符串 | 当前类引用任意一个字符串时满足该项。 |
| `methodReferences` | Method Reference 数组 | 否 | 1 至 16 项 | 当前类引用任意一个方法时满足该项。 |

每个 Query 至少要有一个参数。一个 Query 同时出现多个参数时，所有参数类别必须由同一个 DEX 类满足：

- 有 `name` 时，类名必须匹配。
- 有 `stringConstants` 时，该类至少引用列表中的一个字符串。
- 有 `methodReferences` 时，该类至少引用列表中的一个方法。

例如，同时包含 `stringConstants` 和 `methodReferences` 的 Query，要求同一个类至少引用一个目标字符串和一个目标方法，但两条引用指令不要求位于同一个方法体中。证据可能出现在不同类时，应拆成多个 `dexClasses` 数组项。

#### 类名参数

DEX 类名使用描述符，不使用 Java 或 Kotlin 的点分名称。

| `name` 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `name.operator` | 字符串 | 是 | `equal`、`starts_with` | 精确匹配类描述符，或匹配描述符前缀。 |
| `name.value` | 字符串 | 是 | 以 `L` 开头的 DEX 类描述符模式；`equal` 必须以 `;` 结尾 | 需要匹配的完整描述符或前缀。 |

| 目标 | `operator` | 示例 |
| --- | --- | --- |
| 匹配一个类 | `equal` | `Lcom/example/sdk/EntryPoint;` |
| 匹配一个包或嵌套前缀 | `starts_with` | `Lcom/example/sdk/` |

类名可以使用字母、数字、下划线、美元符号、斜杠和连字符。`starts_with` 可以省略分号，匹配包前缀时通常以斜杠结尾。

#### 字符串常量参数

| 参数 | 类型 | 数量 | 单项长度 | 其他限制 |
| --- | --- | --- | --- | --- |
| `stringConstants` | 字符串数组 | 1 至 16 | 1 至 160 个字符 | 禁止控制字符；按 DEX 中的完整字符串引用匹配，不支持正则或子串。 |

#### 方法引用参数

```json
{
    "definingClass": "Landroid/content/IntentFilter;",
    "name": "<init>",
    "parameterTypes": [
        "Ljava/lang/String;"
    ]
}
```

| 参数 | 类型 | 是否必填 | 全部可选值与限制 | 含义 |
| --- | --- | --- | --- | --- |
| `definingClass` | 字符串 | 是 | 以 `L` 开头、以 `;` 结尾的完整 DEX 类描述符 | 定义目标方法的类。 |
| `name` | 字符串 | 是 | 1 至 80 个允许字符，支持 `<init>` 和 `<clinit>` | 方法名。 |
| `parameterTypes` | 字符串数组 | 否 | 最多 16 项，每项为合法参数类型描述符 | 要求精确匹配的参数列表。 |

省略 `parameterTypes` 会匹配同一类中同名方法的任意重载。提供该字段后，参数列表必须完全相同。空数组只匹配无参数方法。

| 类型 | DEX 描述符 |
| --- | --- |
| boolean | `Z` |
| byte | `B` |
| short | `S` |
| char | `C` |
| int | `I` |
| long | `J` |
| float | `F` |
| double | `D` |
| 对象 | `Ljava/lang/String;` 形式的完整描述符 |
| 数组 | 每一维在元素描述符前增加一个 `[`，例如 `[I`、`[[Ljava/lang/String;` |

## 可选元数据

### `releaseChannel`

| 值 | 是否进入 Preview Bundle | 是否进入 Stable Bundle | 含义 |
| --- | --- | --- | --- |
| `stable` | 是 | 是 | 已完成兼容性和检测结果验证的规则，也是默认值。 |
| `preview-only` | 是 | 否 | 仍在试验或等待稳定验证的规则。 |

生成器会从 Catalog 中删除 `releaseChannel`。它只控制仓库发布渠道，不是运行时图表元数据。

### `availability`

| 值 | 含义 |
| --- | --- |
| `always` | 图表始终可用，也是唯一允许值和默认值。 |

未来 Schema 增加在线可用性限制前，应省略该字段。

### `requiresFeatureInitialization`

| 值 | 含义 |
| --- | --- |
| `false` | 不等待特征初始化，默认值。 |
| `true` | 特征初始化完成前隐藏图表。 |

当前在线证据不依赖特征数据，新规则通常应省略该字段或使用 `false`。

### `controls`

| 值 | 含义 |
| --- | --- |
| 省略 | 推荐写法，Schema v1 没有在线图表控件。 |
| `[]` | 合法，但不会增加任何行为。 |
| 非空数组 | 非法，校验器会拒绝。 |

### `dashboard`

| 值 | 含义 |
| --- | --- |
| `none` | 不提供 Dashboard 集成，也是唯一允许值和默认值。 |

### `fingerprint`

Fingerprint 决定已安装应用数据变化后，LibChecker 何时丢弃图表缓存。它不会开放新的证据读取能力。

| 值 | 默认值 | 适用规则 | 含义 |
| --- | --- | --- | --- |
| `standard` | 是 | 只依赖 `target_sdk` 等标准元数据 | 使用不包含特征数据的完整应用信息指纹。 |
| `artifact` | 否 | 检查原生库、APK 条目、DEX 或 Manifest 内容 | 使用包含应用版本和更新时间等制品变化信息的指纹。 |
| `features` | 否 | 依赖 LibChecker 已初始化特征数据的规则 | 将特征数据纳入缓存指纹，Schema v1 当前在线证据不需要此值。 |

应选择能够覆盖规则中所有证据叶子的值。Target SDK 与 DEX 组合的规则应使用 `artifact`。

## 校验与测试

运行：

```shell
python3 -m unittest chart.tools.test_build_bundle
```

JSON Schema 定义完整的对象结构与字段限制。Python 生成器还会进行语义校验，包括证据、操作符和值的兼容性，URL 安全性，图标路径和 SVG 安全性，重复规则 ID，重复 Facet ID，以及复杂度限制。

新增规则时，请更新 `chart/tools/test_build_bundle.py` 中的现有断言：

| 测试位置 | 需要修改的内容 |
| --- | --- |
| `test_source_rules_are_valid` | 按排序后的顺序添加新规则 ID。 |
| `test_bundle_is_deterministic_and_contains_only_expected_files` | 按 ZIP 中的排序添加图标路径，并修改 Catalog 数量。 |
| `test_stable_bundle_excludes_preview_only_rules` | 根据规则渠道修改稳定 Bundle 的规则 ID 列表。 |
| 新的专门测试 | 固定关键判定值、条件顺序、图标渲染模式、详情 URL 或其他不能被误改的属性。 |
| 新 Schema 能力或校验分支 | 添加对应的非法输入测试。 |

不要为了让新规则通过测试而降低限制或删除回归断言。

## 生成 Bundle

本地预览时，先输出到临时目录，避免修改 Git 已跟踪的生成文件：

```shell
python3 chart/tools/build_bundle.py \
  --bundle-version 12 \
  --channel preview \
  --minimum-app-version-code 2731 \
  --output-dir /tmp/libchecker-chart-preview
```

生成目标分支最终制品时，省略 `--output-dir`，文件会写入 `chart/cloud/v1/`：

```shell
python3 chart/tools/build_bundle.py \
  --bundle-version 12 \
  --channel preview \
  --minimum-app-version-code 2731
```

### 命令行参数

| 参数 | 是否必填 | 类型与全部可选值 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `--bundle-version` | 是 | 大于 `0` 的整数 | 无 | 目标分支单调递增的发布版本。 |
| `--channel` | 否 | `preview`、`stable` | `preview` | Preview 包含全部规则；Stable 排除 `preview-only`。 |
| `--minimum-app-version-code` | 否 | 不小于 `0` 的整数 | `0` | 能安全加载 Bundle 中所有规则的首个 LibChecker Version Code。 |
| `--output-dir` | 否 | 文件系统路径 | `chart/cloud/v1/` | Bundle 与 Manifest 的输出目录。 |

如果规则只使用已发布客户端支持的证据和计算能力，可以沿用目标分支当前兼容的最低应用版本。规则依赖新的客户端能力时，应先协调客户端修改，并填写首个兼容版本的准确 Version Code。不要猜测该值。只有所有仍受支持的客户端都兼容时，才可以发布 `0`。

### 生成结果

| 字段或限制 | 值 | 含义 |
| --- | --- | --- |
| 规则排序 | 按 `id` 排序 | 保证 Catalog 稳定。 |
| 图标排序 | 按路径排序 | 保证 ZIP 条目稳定。 |
| 最大规则数 | 64 | 超出后生成失败。 |
| 单个 SVG 最大大小 | 64 KiB | 超出后校验失败。 |
| Bundle 最大大小 | 2 MiB | 超出后生成失败。 |

`manifest.json` 包含以下参数：

| 参数 | 类型与限制 | 含义 |
| --- | --- | --- |
| `schemaVersion` | 固定为 `1` | Catalog 与 Manifest 使用的 Schema 版本。 |
| `bundleVersion` | 不小于 `1` 的整数 | 当前发布版本。 |
| `bundleSha256` | 64 位小写十六进制字符串 | `chart.bundle` 的 SHA-256。 |
| `bundleSize` | 1 至 2,097,152 字节 | `chart.bundle` 的实际字节数。 |
| `minimumAppVersionCode` | 不小于 `0` 的整数 | 最低兼容 LibChecker Version Code。 |

`chart.bundle` 和 `manifest.json` 必须一起提交。一次生成得到的校验和与大小不能搭配另一次生成得到的 Bundle。

## 人工验证

自动校验只能证明规则格式正确，不能证明规则能够准确识别目标应用。

请求稳定发布前，请完成以下检查：

1. 安装能够读取预览分支的兼容 LibChecker 版本。
2. 至少检查一个已知匹配应用和一个已知不匹配应用。
3. 对于 Facet 规则，分别验证每个 Facet，并确认同时匹配多项能力的应用会按照规则顺序显示全部 Chip。
4. 检查图表标题、分组标题、说明、参考链接、图标大小、图标颜色、浅色主题和深色主题。
5. 在 PR 描述中记录用于测试的应用版本或样本 APK。
6. 使用 `--channel stable` 重新生成并检查 Catalog，确保所有 `preview-only` 规则都不在其中。

## Pull Request 检查表

- [ ] 规则只解决一项定义清楚的统计需求。
- [ ] ID 和文件名稳定并符合命名规范。
- [ ] 新规则从 Revision `1` 开始，修改已发布规则时已增加 Revision。
- [ ] 所有文本都有含义一致的 `en` 和 `zh-Hans` 翻译。
- [ ] 说明保持中性，HTTPS 链接指向一手资料。
- [ ] 计算只使用受支持的证据和兼容操作符。
- [ ] DEX Query 使用描述符，并保持同类匹配语义。
- [ ] SVG 满足安全限制与 `viewBox` 要求。
- [ ] 发布渠道和 Fingerprint 与规则成熟度、证据类型一致。
- [ ] 专门测试覆盖关键判定数据和渠道行为。
- [ ] 单元测试通过。
- [ ] 已使用兼容的 LibChecker 检查匹配和不匹配应用。
- [ ] 生成的 Bundle 和 Manifest 已重新生成并一起提交。

## 错误发布后的恢复

不要重新使用旧的 Bundle Version。恢复上一个已知正常的源规则和生成内容，然后用更高的 `bundleVersion` 重新发布。下载、校验和、Schema 或最低版本检查失败时，兼容的 LibChecker 客户端会保留已缓存的 Bundle。
