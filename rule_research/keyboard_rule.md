Keyboard简短规格来自于HTML的Keyboard和Keyboard Backlight两个Features.
1. HTML的Keyboard部分:
1.1 对于Commercial laptop, Consumer laptop, SMB laptop, Tablet, 从HTML Keyboard选择以下值进行提取:
    1.1.1 row数, 如6-row.
    1.1.2 multimedia Fn keys
    1.1.3 spill-resistant
    1.1.4 Chrome keyboard
    1.1.5 Copilot key
    1.1.6 Top-load keyboard
提取顺序需要完全和HTML保持一致. 当HTML Keyboard不包含以上信息时, 直接提取HTML Keyboard原值.
1.2 对于DT和ThinkSation, 直接提取HTML Keyboard原值.  
1.3 如果HTML Keyboard选项包含"XXXmodels:", 其中"XXX"为任意字符, 则不要输出"XXXmodels:"
1.4 忽略含None 或No开头选项, 不要输出. 且所有输出的选项后加*
1.5 如果存在多个非None选项, 且这些选项按照1.1的规则, 生成的所有值都一样, 则做如下处理:
    1.5.1 先正常按照1.1的规则进行输出
    1.5.2 再对比所有选项, 对所有有差异的部分, 进行输出, 输出时保留原值. 
    1.5.3 不在1.1的规则内且选项间相同的部分, 则忽略.

2. HTML的Keyboard Backlight部分:
2.1 直接从HTML的Keyboard Backlight取值. 如果存在多个Keyboard Backlight选项 (不包括None 或 No 开头选项), 每个选项用"/"连接, "/"前后要有空格. 不要提取冒号前的部分. 多个Backlight选项, 只有最后一个保留"backlight", 其它选项都删掉"backlight"
2.2 如果存在None 或 No, 则输出的选项后加*.
2.3 忽略含None 或No开头选项, 不要输出.

3. 输出前的最后检查:
3.1 Keyboard的简短规格不要输出HTML Spec中的括号及括号内的内容.