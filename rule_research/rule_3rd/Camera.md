1. ThinkStation简短代码不需要Camera.
2. 其他产线读取HTML Spec的Camera信息, 并按照以下方式生成Camera的简短规格:
2.1 按顺序读取HTML Spec的Camera的每个条目, 每个条目在简短规格中都是单独的条目.
2.2 去掉每个条目结尾的括号及括号中的内容.
2.3 条目中包含"Computer Vision on Image Signal Processor (ISP)"的, 替换为"CV on ISP".
2.4 如果包含No的条目, 则生成的每个条目后都加"*".
2.4 如果HTML Spec不含Camera, 则不生成Camera的简短规格.