1. 如果Memory Slots未提及"systemboard"或"soldered", 则Memory的生成规则是:
  1.1 取"Memory Slots"的第一个逗号前的文本, 没有逗号则取全部.
  1.2 取Max Memory的全值. 如果以"Up to"开头, "U"改为小写.
  1.3 如果Memory Type本身或Memory Type选项存在Note, 则生成统一Note
2. 如果Memory Slots仅有"systemboard"或"soldered"
  2.1 从Max Memory中选择容量最高的条件分支或唯一值, 不要输出条件本身(格式为"xxxx:", xxxx为任意文本), 前面加"Up to".
  2.2 从Memory Type取值, 加"memory speed up to". 相同内存类型存在多个速度, 取该类型最高速度; 存在多个内存类型, 每个内存类型都取最高速度. 如果Max Memory已经存在内存类型, 则不再从Memory Type取值.
  2.1和2.2作为独立的两个项目列表输出, 首字母大写, 换行.
  2.3 如果Memory Type本身或Memory Type选项存在Note, 则生成统一Note
3. Memory Slots同时有"systemboard"或"soldered", 还有"slots"
  3.1 从Max Memory中选择容量最高的含"not upgradable"或"soldered"的条件分支或唯一值, 要输出条件本身(格式为"xxxx:", xxxx为任意文本), 前面加"up to". 再从Memory Type的和soldered相同的条件分支下, 取内存类型最大值, 加"Memory speed up to". 相同内存类型存在多个速度, 取该类型最高速度; 存在多个内存类型, 每个内存类型都取最高速度. 如果Max Memory已经存在内存类型, 则不再从Memory Type取值.
  3.2 从Max Memory中选择容量最高的不含"not upgradable"或"soldered"的条件分支或唯一值, 输出条件本身(格式为"xxxx:", xxxx为任意文本). 如果选项不是以"Up to"或"up to"开头, 前面加"up to".
  3.3 再从Memory Slots中, 匹配3.2中输出值对应的条件分支对应的条件分支, 取其第一个逗号前的文本, 没有逗号则取全部.
  3.4 重新拼接输出3.2和3.3, 先输出3.3, 再输出3.2
  3.5 3.1和3.4作为独立的两个项目列表输出, 首字母大写, 换行.
  3.6 如果Memory Type本身或Memory Type选项存在Note, 则生成统一Note.
4. 如果输出的选项是soldered的情况, 确保该选项最后包含not upgradable.
5. 以上规则适用于除ThinkStation以外的规则. ThinkStation模板直接从Max Memory取值, 不做任何修改. 
6. 统一Note的内容为"Displayed memory speed may be lower than the module's rated speed due to platform limitations."
7. 统一Note的输出位置是简短规格存放的Excel文档的Note字段
