1. Optical简短规格适用于ThinkStation和Desktop产品线.
2. Desktop产品线Optical简短规格生成规则:
2.1 读取HTML Spec下的Optical下的列表
2.2 如果HTML Spec不包含Optical, 则不生成Optical的简短规格.
2.3 关键词库包括 "DVD±RW", "DVD-ROM", "Blu-ray".
2.4 HTML Spec下的Optical下的列表如果包含关键词库中的词语, 则输出该词语, 否则不要输出. 顺序和HTML Spec下的Optical下的列表顺序一致.
2.5 如果输出的关键词库中的词语是2个, 则用or连接, 前后加空格.
2.6 如果输出的关键词库中的词语是3个, 则是A, B, or C, ABC 分别为三个词语.
2.7 如果Optical的条目包含"USB external"（不区分大小写）, 则在生成的信息末尾加上", USB external".
3. ThinkStation产品线Optical简短规格生成规则:
3.1 直接复制HTML Spec下的Optical Support的文本.
3.2 如果HTML Spec不包含Optical Support, 则不生成Optical的简短规格.

### 2026-10-16 规则更新
- Desktop产品线的Optical任一条目包含"USB external"时（不区分大小写）, 在已有生成信息末尾追加一次", USB external"；ThinkStation及其他Optical规则不变.
