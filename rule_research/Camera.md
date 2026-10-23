1. ThinkStation简短代码不需要Camera.
2. 其他产线读取HTML Spec的Camera信息, 并按照以下方式生成Camera的简短规格:
2.1 按顺序读取HTML Spec的Camera的每个条目, 每个条目在简短规格中都是单独的条目.
2.2 去掉每个条目结尾的括号及括号中的内容.
2.3 条目中包含"Computer Vision on Image Signal Processor (ISP)"的, 替换为"CV on ISP".
2.4 如果包含No的条目, 则生成的每个条目后都加"*".
2.4 如果HTML Spec不含Camera, 则不生成Camera的简短规格.


HTML Spec的Camera信息, 并按照以下方式生成Camera的简短规格:
1. Commercial, SMB, Consumer产品线:
1.1 按顺序读取HTML Spec的Camera的每个条目, 每个条目在简短规格中都是单独的条目. 取值时按照以下规则:
1.2 不读取"No"开头的条目
1.3 非"No"开头的条目, 读取到第一个逗号前的内容
1.4 然后对于条目的其余信息, 如果包含"Human Presence Detection","temporal noise reduction","privacy shutter","ThinkShutter", "Computer Vision"关键字, 则将这些信息加到1.2部分的后面, 用逗号加空格分开. 关键字不区分大小写.
1.5 对于条目的其余信息, 如果包含"rear XX"开头的信息, 则取"rear"开头的信息直到条目结束或遇到逗号","或分号";", 最后检查这些信息是否包含"World Facing"关键字, 如果是, 去掉这个关键字. 关键字不区分大小写. "rear" 也不区分大小写. XX是任意字符.
1.6 如果包含"No"开头的条目, 则取到的所有条目加星号"*"
1.7 去掉重复条目

2. Desktop产品线:
2.1 按顺序读取HTML Spec的Camera的每个条目, 每个条目在简短规格中都是单独的条目. 取值时按照以下规则:
2.2 不读取"No"开头的条目
2.3 非"No"开头的条目, 读取到第一个逗号前的内容.
2.4 然后对于条目的其余信息, 如果包含"IR", 则直接在2.3得到的条目后加" RGB & IR hybrid"; 否则加" RGB"
2.5 然后对于条目的其余信息, 如果包含"Human Presence Detection"关键字, 则在2.4得到的条目后加" with Human Presence Detection".
2.6 如果包含"No"开头的条目, 则取到的所有条目加星号"*"
2.7 去掉重复条目

3. Tablets产品线:
直接按顺序读取HTML Spec的Camera的每个条目, 原样输出, 不做修改. 如果包含"No"开头的条目, 则取到的所有条目加星号"*"


