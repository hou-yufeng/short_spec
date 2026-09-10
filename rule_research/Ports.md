1. Commercial, Consumer, SMB Laptops的Ports简短规格生成规则:
1.1 直接读取HTML Spec的Standard Ports, Optional Ports下的所有条目, 作为Ports的简短规格条目.
1.2 如果条目包含Thunderbolt, 则该条目截取到第一个逗号, 不包含逗号.
1.3 对于Optional Ports下的条目, 每个条目后都加星号"*".
1.4 忽略所有"No"开头的条目
2. ThinkStation, DT的Ports简短规格:
2.1 读取HTML Spec的<div class="content_nav_title title_level2">Ports标签下, 所有的标签为<div class="content_nav_title title_feature">且包含"Ports"文本的标签下的所有条目, 作为Ports的简短规格条目.
2.2  所有的标签为<div class="content_nav_title title_feature">且同时包含"Optional"和"Ports"文本的标签下的条目,一律加星号"*"
2.3 忽略所有"No"开头的条目