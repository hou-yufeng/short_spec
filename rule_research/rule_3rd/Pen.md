Pen 简短规格适用于 Commercial、Consumer、SMB 和 Tablets 产品线；Desktop 和 ThinkStation 不生成 Pen。
1. 从 PSREF HTML Spec - Pen 读取源条目，按原有顺序处理。
2. 仅在条目中查找大小写严格匹配的“Pen”。以“Pen”为中心，向前、向后保留连续的大写字母开头的单词或数字；遇到小写字母开头的单词停止。名称后紧接的括号及其中内容放在输出条目末尾。
3. 如果含“purchase”（不区分大小写）的条目是 Pen 下唯一条目，则该条目原样输出；如果还有其他条目，则不输出含“purchase”的条目。
4. 不输出以“No”开头且不含“purchase”的条目。如果 Pen 下存在“No”开头条目，其他生成的条目末尾均加“*”。
5. 对生成的条目去重，保留首次出现的条目及源顺序。
6. 如果没有符合规则的输出条目，或 HTML Spec 不含 Pen，则不生成 Pen 简短规格。
