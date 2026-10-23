1. Expansion Slots适用于ThinkStation和Desktop产品线.
2. Desktop产品线的Expansion Slots生成规则是:
2.1 依次读取HTML Spec 的 Expansion Slots下的条目.
2.2 如果读取的条目包含以下文本中的任意一个, 则自该文本后的内容(包括该文本)全部删除, 然后继续读取下一条目, 直到全部完成. 如果不含以下文本, 则完整读取该条目.
2.2.1 ", full"
2.2.2 ", low"
3. ThinkStation产品线的Expansion Slots生成规则是:
3.1 读取HTML Spec 的 Expansion Slots下的第一句话, 从"Supports"到第一个句点结束.
3.2 换行, 然后读取HTML Spec 的 M.2 Slots下的第一句话, 从"Up to"到第一个句点或冒号结束.