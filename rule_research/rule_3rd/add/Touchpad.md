# Touchpad简短规格适用于Commercial, Consumer, SMB产品线.
## Commercial产品线Touchpad简短规格生成规则:
+ 从HTML Spec - UltraNav取值.
+ 含有多个条件分支的, 每个条件分支都要取值, 不要取条件分支本身.
+ 含多个条目的, 每个条目都要取值.
+ 移除每个条目中所有"x-button"文本, x为任意长度字符.
+ 移除每个条目中的"double-tap to open the TrackPoint® Quick Menu".
+ 移除每个条目中被逗号分割开的文本段落中, 以"supports"开头的文本段落.
+ 结果为多个条目的, 各条目按HTML Spec顺序逐条输出, 不合并.
+ 如果源条目有两行数据, 在第二行数据前加"and".
+ 移除每个条目中的"pointing device"和"multi-touch", 将"Glass"改为"glass".
+ 以逗号分隔每个条目的文本段落; 含"inches"的段落另起一行, 移除其他源换行.
+ 删除每行数据最后的逗号或句点.

## Consumer 和 SMB产品线Touchpad简短规格生成规则:
+ 从HTML Spec - Touchpad取值.
+ 含有多个条件分支的, 每个条件分支都要取值, 不要取条件分支本身.
+ 含多个条目的, 每个条目都要取值.
+ 移除每个条目中所有"x-button"文本, x为任意长度字符.
+ 移除每个条目中的"double-tap to open the TrackPoint® Quick Menu".
+ 移除每个条目中被逗号分割开的文本段落中, 以"supports"开头的文本段落.
+ 结果为多个条目的, 各条目按HTML Spec顺序逐条输出, 不合并.
+ 如果源条目有两行数据, 在第二行数据前加"and".
+ 移除每个条目中的"pointing device", "multi-touch"和"Buttonless", 将"Glass"改为"glass".
+ 以逗号分隔每个条目的文本段落; 含"inches"的段落另起一行, 移除其他源换行.
+ 删除每行数据最后的逗号或句点.

### 2026-10-20 更新

Consumer 和 SMB 产品线的 Touchpad 简短规格改用 Commercial 产品线的逐条处理规则，取值仍来自 HTML Spec 的 Touchpad 字段；Commercial 产品线仍从 UltraNav 取值。对多个源条目按 HTML Spec 顺序逐条输出，不合并；源条目有两行数据时，在第二行数据前加 "and"。移除所有 "x-button"、"double-tap to open the TrackPoint® Quick Menu"、"pointing device" 和 "multi-touch"，以及以 "supports" 开头的逗号分隔段落；将 "Glass" 改为 "glass"。含 "inches" 的逗号分隔段落另起一行，移除其他源换行及每行末尾的逗号或句点。Consumer 和 SMB 还需移除所有 "Buttonless" 文本。
