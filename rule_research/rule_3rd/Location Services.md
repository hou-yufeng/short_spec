Location Services简短规格专用于Tablets产品线.
Location Services的生成规则是: 
1. 读取HTML Spec的Location Services的表格中, "Location"字段下的各行数据, 按照"+"将这些数据进行分割, 得到的数据作为条目按行存放, 放在一起去重, 得到的条目就是Location Services简短规格的信息. 注意"No"开头的条目需要移除.
2. 如果某条目并未出现在HTML Spec的Location Services的表格中, 每行"Location"字段下, 则该条目加星号.
