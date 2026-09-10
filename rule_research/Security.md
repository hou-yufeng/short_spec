Security简短规格适用于所有产品线.
# ThinkStation / DT的Security简短规格生成规则:
从HTML Spec的Security Chip, Physical Locks, Chassis Intrusion Switch, Fingerprint Reader取值. 得到的条目直接放到简短规格的Security下, 不需要取HTML Spec的标题的值.
1. HTML Spec的Security Chip取值规则
1.1 如果Security Chip包含有"Discrete TPM 2.0"文本条目, Security简短规格生成"Discrete TPM 2.0".
1.2 如果Security Chip不包含"Discrete TPM 2.0"文本条目, 包含"Firmware TPM 2.0"文本条目, 则Security简短规格生成"Firmware TPM 2.0".
1.3 如果只有"No"开头的条目或HTML Spec没有Security Chip, 则不取值
2. HTML Spec的Physical Locks取值规则:
2.1 取HTML Spec的Physical Locks下所有条目, 忽略"No"开头的条目. 
2.2 条目包含逗号","的, 取该条目第一个逗号","前的文本. 
2.3 条目中包含括号的, 去掉括号及括号中的所有内容. 
2.4 条目中包含"optional"或"Optional"文本的, 该条目最后加星号"*".
2.5 如果只有"No"开头的条目或HTML Spec没有Physical Locks, 则不取值
3. HTML Spec的Chassis Intrusion Switch取值规则:
3.1 仅取所有不是"No"开头的条目, 忽略"No"开头的条目. 
3.2 如果存在"No"开头的条目, 则取值条目后都加星号"*".
3.3 如果只有"No"开头的条目或HTML Spec没有Chassis Intrusion Switch, 则不取值.
4. HTML Spec的Fingerprint Reader取值规则:
4.1 取所有不是"No"开头的条目, 忽略"No"开头的条目. 
4.2 如果存在"No"开头的条目, 则取值条目后都加星号"*".
4.3 如果只有"No"开头的条目或HTML Spec没有Fingerprint Reader, 则不取值