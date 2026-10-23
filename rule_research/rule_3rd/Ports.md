1. Commercial, Consumer, SMB Laptops的Ports简短规格生成规则:
1.1 直接读取HTML Spec的Standard Ports, Optional Ports下的所有条目, 作为Ports的简短规格条目.
1.2 所有条目保留HTML Spec原值输出, 包含Thunderbolt的条目也不截取; 最终输出统一移除™和®符号.
1.3 对于Optional Ports下的条目, 每个条目后都加星号"*".
1.4 忽略所有"No"开头的条目
2. Desktop的Ports简短规格:
2.1 读取HTML Spec的<h2 specStructure="Ports">Ports下所有标题包含"Ports"的H3及其全部条目. H3标题作为简短规格的L2 Feature, 不生成名为Ports的L2 Feature.
2.2 每个条目保留HTML Spec原值, 最终输出统一移除™和®符号. 如果所在H3标题包含"Optional", 则在该条目后加星号"*".
2.3 从H3标题中去除"Optional ". 去除后如有同名标题, 合并其条目, 并将原Optional标题下的条目放在该L2 Feature的后面.
3. Tablets的Ports简短规格生成规则:
3.1 直接读取HTML Spec的Standard Ports, Optional Ports下的所有条目, 作为Ports的简短规格条目.
4. ThinkStation的Ports简短规格:
4.1 读取HTML Spec的<div class="content_nav_title title_level2">Ports标签下, 所有的标签为<div class="content_nav_title title_feature">且包含"Ports"文本的标签下的所有条目, 作为Ports的简短规格条目.
4.2 所有的标签为<div class="content_nav_title title_feature">且同时包含"Optional"和"Ports"文本的标签下的条目,一律加星号"*".
4.3 忽略所有"No"开头的条目.
