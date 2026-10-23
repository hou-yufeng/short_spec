1. WWAN 简短规格适用于 Commercial、Consumer、SMB、Tablets 和 Desktop 产品线；ThinkStation 不生成 WWAN。
2. Commercial、Consumer、SMB 和 Desktop 从 PSREF HTML Spec 的 WWAN 取值，按源条目顺序处理。
3. 上述四个产品线只取非“No”开头且包含逗号“,”的条目。
4. 将每个符合条件的条目按逗号分割，取第 2 个短语；如果第 4 个短语包含“eSIM”，再取第 4 个短语。选中的短语用一个空格连接，生成该条简短规格。
5. 如果源 WWAN 中存在“No”开头的条目，所有生成的简短规格条目末尾均加“*”。

6. Tablets 产品线直接读取 PSREF HTML Spec - WWAN 下所有非“No”开头的条目，按源条目顺序原样输出；不要求条目包含逗号，也不截取短语。
7. Tablets 的 WWAN 中如果存在“No”开头的条目，则所有取得的条目末尾加“*”；如果仅有“No”开头的条目，则不生成 WWAN 简短规格。

### 2016-10-21 更新

Commercial、Consumer、SMB 和 Desktop 产品线的 WWAN 简短规格生成后，去除完全相同的重复条目，保留首次出现的条目及原有顺序。Tablets 产品线继续按照上述专用规则逐条输出。
