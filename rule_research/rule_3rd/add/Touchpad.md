# Touchpad简短规格适用于Commercial, Consumer, SMB产品线.
## Commercial产品线Touchpad简短规格生成规则:
+ 从HTML Spec - UltraNav取值.
+ 含有多个条件分支的, 每个条件分支都要取值, 不要取条件分支本身.
+ 含多个条目的, 每个条目都要取值.
+ 移除每个条目位于起始位置的整数+"-button".
+ 移除每个条目中的"pointing device".
+ 移除每个条目中的"double-tap to open the TrackPoint Quick Menu".
+ 移除每个条目中被逗号分割开的文本段落中, 以"supports"开头的文本段落.
+ 结果为多个条目的, 对多个条目进行合并, 相同文本只出现一次, 不同文本用or连接
+ 每个条目最后一个逗号后的文本单独占据新的一行.
+ 删除每行数据最后的逗号或句点.

## Consumer 和 SMB产品线Touchpad简短规格生成规则:
+ 从HTML Spec - Touchpad取值.
+ 含有多个条件分支的, 每个条件分支都要取值, 不要取条件分支本身.
+ 含多个条目的, 每个条目都要取值.
+ 移除每个条目位于起始位置的整数+"-button".
+ 移除每个条目中的"pointing device".
+ 移除每个条目中的"double-tap to open the TrackPoint Quick Menu".
+ 移除每个条目中被逗号分割开的文本段落中, 以"supports"开头的文本段落.
+ 结果为多个条目的, 对多个条目进行合并, 相同文本只出现一次, 不同文本用or连接
+ 每个条目最后一个逗号后的文本单独占据新的一行.
+ 删除每行数据最后的逗号或句点.