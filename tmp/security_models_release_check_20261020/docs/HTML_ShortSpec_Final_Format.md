# HTML ShortSpec 最终输出格式

适用范围：HTML 来源生成的最终 Excel 工作簿。检查对象为最终工作簿，不改变各 Feature 内部条目的取值、顺序、星号和换行规则。

1. 写入 `Short Spec` 前，将文本中的 HTML 实体解码，并移除全部 `™` 和 `®` 字符。该规则适用于所有产品线和 Feature，包含要求保留 HTML 条目内容的 Ports；其余文本仍按对应 Feature 规则输出。
2. 写入完成后检查最终 Excel：表头为 `Product`、`L1 Feature`、`L2 Feature`、`Short Spec`；有内容的数据行中，这四列都不能留空。
3. `Short Spec` 单元格不能残留 `™`、`®` 或未解码的 HTML 实体，也不能有单元格首尾空白、制表符或回车符。内部换行保留，由 Feature 规则决定。部分 Feature（如 ThinkStation ISV Certifications）会按现有规则输出 HTML 链接，因此不统一禁止 HTML 标签。
4. 检查失败时生成程序返回非零退出码，不将临时工作簿发布为最终工作簿；启动器因此保留源 HTML 文件。
5. `third_batch_html_260919` 的每个产品内部，按 `L2 Feature` 名称不区分大小写的 A-Z 顺序排列行；相同名称保持原有顺序。最终工作簿额外检查这一顺序。

代码集中在仓库的 `scripts/html_shortspec_format.py`，发布包内位于 `rt/scripts/html_shortspec_format.py`。在包根目录可执行 `rt\python-runtime\python.exe rt\scripts\html_shortspec_format.py <workbook.xlsx> --require-l2-order` 独立检查第三批工作簿。
