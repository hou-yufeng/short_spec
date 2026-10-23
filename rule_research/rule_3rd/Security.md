Security简短规格适用于所有产品线.
# ThinkStation / Desktop的Security简短规格生成规则:
从HTML Spec的Security Chip, Physical Locks, Chassis Intrusion Switch, Fingerprint Reader, Other Security取值. 得到的条目直接放到简短规格的Security下, 不需要取HTML Spec的标题的值.
1. HTML Spec的Security Chip取值规则
1.1 如果Security Chip包含有"Discrete TPM"开头的文本条目, 则取这些条目.
1.2 如果Security Chip不包含"Discrete TPM"开头文本条目, 则取所有不以"No"开头的条目
1.3 如果只有"No"开头的条目或HTML Spec没有Security Chip, 则不取值
1.4 如果包含"No"开头的条目, 则取到的条目最后都加星号"*".

2. HTML Spec的Physical Locks取值规则:
2.1 取HTML Spec的Physical Locks下所有条目, 忽略"No"开头的条目. 
2.2 如果存在"No" 开头条目, 则取值的条目后都加"*".
2.2 条目中包含"optional"或"Optional"文本的, 该条目最后加星号"*".
2.3 条目中包含括号的, 去掉括号及括号中的所有内容. 
2.4 如果只有"No"开头的条目或HTML Spec没有Physical Locks, 则不取值

3. HTML Spec的Chassis Intrusion Switch取值规则:
3.1 仅取所有不是"No"开头的条目, 忽略"No"开头的条目. 
3.2 如果存在"No"开头的条目, 则取值条目后都加星号"*".
3.3 条目中包含"optional"或"Optional"文本的, 该条目最后加星号"*".
3.4 条目中包含括号的, 去掉括号及括号中的所有内容. 
3.5 如果只有"No"开头的条目或HTML Spec没有Chassis Intrusion Switch, 则不取值.

4. HTML Spec的Fingerprint Reader取值规则:
4.1 仅取所有不是"No"开头的条目, 忽略"No"开头的条目. 
4.2 如果存在"No"开头的条目, 则取值条目后都加星号"*".
4.3 条目中包含"optional"或"Optional"文本的, 该条目最后加星号"*".
4.4 条目中包含括号的, 去掉括号及括号中的所有内容. 
4.5 如果只有"No"开头的条目或HTML Spec没有Fingerprint Reader, 则不取值

5. HTML Spec的Other Security取值规则:
5.1 直接取所有非"No"开头的条目.
5.2 忽略条目中的"(Optional)"文本.
5.3 忽略条目中"(xxx models)"文本, xxx为任意个数的字符.
5.4 非"No"开头的条目中, 忽略条目中的"(xxx model)", "(model xxx)", "(models xxx)", XXX为任意个数的字
符. 此外, 如果源条目包含"(xxx models)", "(xxx model)", "(model xxx)", "(models xxx)", "Optional", "optional", 则生成的条目结尾加"*". 其他规则不变.
5.5 条目中的" Image Signal Processor (ISP)"缩写为"ISP"

# Commercial / Consumer / Tablets / SMB 的Security简短规格生成规则:
从HTML Spec的ThinkShield, Security Chip, Physical Locks, Smart Card Reader, Fingerprint Reader, Other Security取值. 得到的条目直接放到简短规格的Security下, 不需要取HTML Spec的标题的值.
1. HTML Spec的ThinkShield取值规则
如果HTML Spec存在ThinkShield, 且其内容开头为"ThinkShield is a comprehensive security solution", 则输出"ThinkShield".
其他情况均不输出任何信息.
2. HTML Spec的Security Chip取值规则
2.1 如果Security Chip包含有"Discrete TPM 2.0"文本条目, Security简短规格生成"Discrete TPM 2.0".
2.2 如果Security Chip不包含"Discrete TPM 2.0"文本条目, 包含"Firmware TPM 2.0"文本条目, 则Security简短规格生成"Firmware TPM 2.0".
2.3 如果只有"No"开头的条目或HTML Spec没有Security Chip, 则不取值
3. HTML Spec的Physical Locks取值规则:
3.1 取HTML Spec的Physical Locks下所有条目, 忽略"No"开头的条目. 
3.2 条目包含逗号","的, 取该条目第一个逗号","前的文本. 
3.3 条目中包含括号的, 去掉括号及括号中的所有内容. 
3.4 条目中包含"optional"或"Optional"文本的, 该条目最后加星号"*".
3.5 如果只有"No"开头的条目或HTML Spec没有Physical Locks, 则不取值
4. HTML Spec的Fingerprint Reader取值规则:
4.1 取所有不是"No"开头的条目, 忽略"No"开头的条目. 
4.2 如果存在"No"开头的条目, 则取值条目后都加星号"*".
4.3 对于属于取值范围的条目, 进行以下处理规则:
4.3.1 如果取值条目包含"fingerprint reader", 则取值从条目开始截取到"fingerprint reader", 后面的内容忽略.
4.3.2 如果取值条目除了包含"fingerprint reader", 还包含"match-on-chip", 则在取值的"fingerprint reader"前加"MOC ".
4.3 如果只有"No"开头的条目或HTML Spec没有Fingerprint Reader, 则不取值
5. HTML Spec的Other Security取值规则:
5.1 直接取所有非"No"开头的条目.
5.2 忽略条目中的"(Optional)"文本.
5.3 忽略条目中"(xxx models)"文本, xxx为任意个数的字符.
5.4 条目中的" Image Signal Processor (ISP)"缩写为"ISP"