1. ThinkStation简短规格不需要WWAN.
2. 其他产线读取HTML Spec的WWAN信息, 并按照以下方式生成WWAN的简短规格:
2.1 检查每个条目是否含有关键字4G, 5G, 6G, 关键字优先级为6G > 5G > 4G, 选择最高优先级关键字保存为{代数}.
2.2 在含有{代数}的所有条目中, 查找Sub-6 GHz 和 with embedded eSIM
2.2.1 如果Sub-6 GHz 和 with embedded eSIM分别出现在不同含有{代数}的条目中, 则输出两个条目:
WWAN upgradable to {代数} Sub-6 GHz
WWAN upgradable to {代数} with embedded eSIM
2.2.2. 如果Sub-6 GHz 和 with embedded eSIM出现同一个含有{代数}的条目中, 则输出一个条目:
WWAN upgradable to {代数} Sub-6 GHz with embedded eSIM
2.2.3. 如果Sub-6 GHz 和 with embedded eSIM都未出现, 则输出一个条目:
WWAN upgradable to {代数}