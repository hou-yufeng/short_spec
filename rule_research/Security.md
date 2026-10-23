Security简短规格适用于所有产品线.
### 2026-10-20 ThinkStation / Desktop Security 更新

# ThinkStation / Desktop的Security简短规格生成规则:
从HTML Spec的Security Chip, Physical Locks, Chassis Intrusion Switch, Fingerprint Reader, Other Security取值. 得到的条目直接放到简短规格的Security下, 不需要取HTML Spec的标题的值.

1. Security Chip: 如果有以"Discrete TPM"开头的条目, 取这些条目; 否则取所有非"No"开头的条目. 只有"No"条目或没有该字段时不取值. 如存在"No"开头条目, 所有取值条目末尾加"*".
2. Physical Locks: 取所有非"No"开头的条目; 如存在"No"开头条目, 或源条目含"optional"（不区分大小写）, 对应取值末尾加"*". 去掉条目中的括号及其内容. 只有"No"条目或没有该字段时不取值.
3. Chassis Intrusion Switch: 取所有非"No"开头的条目; 如存在"No"开头条目, 或源条目含"optional"（不区分大小写）, 对应取值末尾加"*". 去掉条目中的括号及其内容. 只有"No"条目或没有该字段时不取值.
4. Fingerprint Reader: 取所有非"No"开头的条目; 如存在"No"开头条目, 或源条目含"optional"（不区分大小写）, 对应取值末尾加"*". 去掉条目中的括号及其内容. 只有"No"条目或没有该字段时不取值.
5. Other Security: 取所有非"No"开头的条目. 忽略"(Optional)"及"(xxx models)", "(xxx model)", "(model xxx)", "(models xxx)"文本, 其中xxx为任意个数的字符. 如果源条目包含上述四种model/models括号文本或"Optional"（不区分大小写）, 生成条目末尾加"*". 将" Image Signal Processor (ISP)"缩写为"ISP".

### 2026-10-20 更新（Commercial / Consumer / Tablets / SMB）

Smart Card Reader: 读取HTML Spec的Security - Smart Card Reader下所有条目, 只输出非"No"开头的条目. 如果同时存在"No"开头的条目, 每个输出条目末尾加"*".

Other Security: 保留现有生成规则; 如果HTML Spec原条目含有"Optional"（不区分大小写）, 对应生成条目末尾加"*".

### 2026-10-20 Other Security 更新

Commercial / Consumer / Tablets / SMB: 对Other Security中非"No"开头的源条目, 忽略其中的"(xxx models)", "(xxx model)", "(model xxx)", "(models xxx)"文本, 其中xxx可为任意个数的字符. 如果源条目包含上述任一括号文本, 或包含"Optional"（不区分大小写）, 则生成条目末尾加"*". 其他规则不变.
