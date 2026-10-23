1. 所有产品线的 Weight 简短规格均从 PSREF HTML Spec 的 Weight 取值；HTML Spec 没有 Weight 时不生成该项。
2. 如果 Weight 信息以表格呈现，按 HTML Spec 原有行序逐行读取。每行输出“Models 字段数据”+冒号和一个空格“: ”+“Weight 字段数据”，仅将 Weight 字段数据的首字母改为小写。
3. 如果 Weight 信息以条目呈现，则按 HTML Spec 原样输出条目。
4. 保留 HTML Spec 中 Weight 内容的换行。
