### 2026-10-19 更新

仅Desktop产品线: 按照下方现有规则生成各条目后, 不以分行条目输出, 而是将条目作为短语, 严格按照HTML Spec表格中的源数据顺序拼接. 两个条目用" or "连接; 三个或以上条目用", "连接; 单个条目保持原样. 拼接结果中如果出现多个"PSU", 只保留最后一个, 移除其余"PSU".

1. Power Supply简短规格仅适用于ThinkStation和Desktop产品线.
2. Power Supply简短规格的生成规则是:
2.1 读取HTML Spec的Power Supply下的表格.
2.2 依次从每行数据的Power字段, Efficiency字段, Type字段, Key Features字段取值, 具体规则是:
2.2.1 Power字段和Efficiency字段直接取值.
2.2.2 Type字段如果包含"fixed"或"Fixed"文本, 则不取Type字段的值, 只取"PSU". 反之则取Type字段的值, 且首字母改为小写.
2.2.3 Key Features字段只取包含"80 PLUS * qualified"的文本, *是任意英文字母.
2.3 最终输出格式是Power字段 + Efficiency字段 + Type字段 / "PSU" + ", " + Key Features字段.
