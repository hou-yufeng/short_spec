1. 对于tablets产品线, 直接取HTML Spec的Graphics原值.
2. 对于ThinkStation产品线, 直接取HTML Spec的Discrete Graphics Support原值
3. 对于其余产品线, 读取HTML Spec的Graphics下的表格, 然后按照以下规则进行数据拼接:
3.1 对于Graphics下的表格的Type字段为"Discrete"的数据, 取值规则是分别取每行数据的"Graphics"字段和"Memory"字段的值, 中间加空格, 然后加上空格和"(discrete)".
3.2 对于Graphics下的表格的Type字段为"Integrated"的数据, 取值规则是取每行数据的"Graphics"字段的值, 然后加上空格和"(integrated)"
3.3 对于Graphics下的表格的Type字段为"Discrete"的数据, 如果"Graphics"字段已经包含"Memory"字段中的数据, 则不再从"Memory"字段取值.
3.4 HTML Spec的Graphics表格存在多行数据时, 确保Graphics简短规则的顺序和Graphics表格保持一致.