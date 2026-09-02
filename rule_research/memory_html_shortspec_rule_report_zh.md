# Memory HTML 简短规格规则汇报

## 1. Memory HTML Spec 内容分类

Memory 信息全部从 HTML 中 `div specstructure="Memory"` 下提取。
核心来源字段如下：

| 字段 | 用途 |
|---|---|
| `Max Memory` | 容量主来源，也包含 soldered / not upgradable 文案和部分条件分支 |
| `Memory Slots` | 判断内存结构和选择生成路径的主依据 |
| `Memory Type` | 补充内存类型、原生速度，以及 Memory Type 相关 Note |
| `Memory Protection` | 当前 Memory 简短规格规则不使用 |

基于当前 `data/sample` 样本，Memory HTML Spec 可以分为以下几类：

| 分类 | 判断依据 | 处理方向 |
|---|---|---|
| 可插拔内存 | `Memory Slots` 不包含 `systemboard` 或 `soldered` | 输出插槽结构 + `Max Memory` 全值 |
| 纯板载 / 焊接内存 | `Memory Slots` 包含 `systemboard` 或 `soldered`，且没有可用插槽 | 输出最高容量的板载内存分支；必要时补充原生速度 |
| 板载内存 + 可用插槽 | `Memory Slots` 同时包含 `systemboard` 或 `soldered`，并且还有可用 `slot(s)` | 分别输出板载分支和可扩展插槽分支 |
| ThinkStation | 产品名以 `ThinkStation` 开头 | 直接使用 `Max Memory` |

## 2. Memory HTML Spec 处理难点和需要解决的问题

1. HTML 字段形态不统一。
   有些字段是单个 `<span>` 值，有些字段是 `<ul><li>` 多选项列表。

2. `Max Memory` 可能包含条件分支。
   例如平台分支 `Lunar Lake:` / `Arrow Lake:`，或者 ECC / Non-ECC 分支。

3. `Memory Slots` 需要语义判断。
   `no slots` 本身包含 `slots` 字符，不能简单通过是否包含 `slots` 来判断是否有可用插槽。

4. `Max Memory` 可能已经包含内存类型和速度。
   例如 `LPDDR5X-8533`、`DDR5-5600`、`SODIMM`、`CUDIMM`、`RDIMM`、`LPCAMM2`。
   这种情况下如果再追加 `Memory Type`，会造成重复。

5. `Memory Type` 可能包含多个速度或多个内存类型。
   同一内存类型存在多个速度时，需要取最高速度。
   如果存在多个内存类型，则每个类型都保留最高速度。

6. Note 不是普通字段文本，而是脚注引用。
   需要从 `Memory Type` 标题或选项中的 `supText` 脚注编号，匹配到后续 Notes 中对应的内容。

7. Note 不能混入 Memory 简短规格。
   当前基线要求 Note 单独写入 Excel 的 `Note` 字段。

## 3. Memory 简短规格的解决思路

整体思路是：先用 `Memory Slots` 判断内存结构，再决定如何处理 `Max Memory` 和 `Memory Type`。

- `Memory Slots` 决定产品属于可插拔内存、纯板载内存、板载加插槽，还是 ThinkStation。
- `Max Memory` 是容量主来源。
- 当 `Max Memory` 有多选项且规则要求单一分支时，选择容量最高的分支。
- `Memory Type` 只在需要补充原生速度或缺少内存类型时使用。
- 条件分支通过 `xxxx:` 这种前缀格式识别。
- Memory Type 相关 Note 单独提取、去重，并写入 Excel 的 `Note` 字段。
- `Memory Protection` 不参与生成。

## 4. Memory 简短规格生成逻辑

### 4.1 通用规则

1. 从 `div specstructure="Memory"` 中提取以下字段：
   - `Max Memory`
   - `Memory Slots`
   - `Memory Type`

2. 忽略 `Memory Protection`。

3. 只提取以下位置的 Note：
   - `Memory Type` 标题上的 Note
   - `Memory Type` 选项上的 Note

4. 提取到的 Note 写入 Excel 的 `Note` 字段。
   不追加到 `Short Spec` 字段中。

### 4.2 ThinkStation

适用条件：

```text
产品名以 ThinkStation 开头
```

输出逻辑：

```text
Short Spec = Max Memory
```

规则：

- 直接使用 `Max Memory` 原值。
- 不规范化 `Up to` 大小写。
- 不追加 `Memory Type`。
- Memory Type Note 写入 `Note` 字段。

### 4.3 Memory Slots 不包含 `systemboard` 或 `soldered`

适用条件：

```text
Memory Slots 不包含 systemboard 或 soldered
```

生成逻辑：

1. 取 `Memory Slots` 第一个逗号前的文本。
   如果没有逗号，则取全值。
2. 取 `Max Memory` 全值。
3. 如果 `Max Memory` 以 `Up to` 开头，则将 `U` 改为小写。

输出格式：

```text
{Memory Slots 第一个逗号前文本}, {Max Memory}
```

### 4.4 纯板载 / 焊接内存

适用条件：

```text
Memory Slots 包含 systemboard 或 soldered，且没有可用插槽
```

生成逻辑：

1. 从 `Max Memory` 中选择容量最高的分支。
2. 如果存在条件前缀，则去掉条件前缀。
   例如去掉 `Lunar Lake:`。
3. 在结果前加 `Up to`。
4. 如果选中的 `Max Memory` 已经包含内存类型，则不再追加 `Memory Type`。
5. 如果选中的 `Max Memory` 不包含内存类型，则单独增加一行：

```text
Memory native speed up to {Memory Type 最高速度}
```

### 4.5 板载 / 焊接内存 + 可用插槽

适用条件：

```text
Memory Slots 包含 systemboard 或 soldered，并且还有可用 slot(s)
```

生成逻辑：

1. 从 `Max Memory` 中选择容量最高且包含 `not upgradable` 或 `soldered` 的分支。
   - 保留条件前缀。
   - 分支正文前加 `up to`。
   - 作为一个独立输出项。

2. 从 `Max Memory` 中选择容量最高且不包含 `not upgradable` / `soldered` 的分支。
   - 保留条件前缀。
   - 如果分支正文不是以 `Up to` 或 `up to` 开头，则前面加 `up to`。

3. 根据第 2 步选中的非板载分支，匹配 `Memory Slots` 中对应的条件分支。

4. 取匹配到的 `Memory Slots` 第一个逗号前文本。
   如果没有逗号，则取全值。

5. 插槽分支输出格式为：

```text
{Memory Slots 第一个逗号前文本}, {Max Memory 分支}
```

板载分支和插槽分支分别作为独立行输出。

### 4.6 Excel 输出约定

当前基线交付为 `mkosc_html_260706`。

生成的 Excel 字段为：

```text
Product / L1 Feature / L2 Feature / Short Spec / Note
```

Memory 输出约定：

- Memory 简短规格写入 `Short Spec`。
- Memory Type Note 写入 `Note`。
- Note 不追加到 `Short Spec`。
- 后续其他 Feature 如果需要输出 Note，也统一写入同一个 `Note` 字段。
