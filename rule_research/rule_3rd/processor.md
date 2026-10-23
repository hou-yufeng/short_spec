### 2026-10-20

Commercial产品线: Processor Family每个取值如包含分号";", 只保留第一个分号之前的内容; 其余规则不变.

### 2026-10-20 Commercial 括号更新

Commercial产品线: 如果HTML Spec的Processor原值包含"-"且以括号结尾, 则移除最后的括号及其中内容. 保留分号截取等其他规则.

### 2026-10-20 Tablets 更新

Tablets产品线: 从HTML Spec的Processor表格按源数据顺序读取每行的"Processor Name"和"Cores"字段, 每行输出为`Processor Name (Cores)`, 多行分别作为条目输出. 如果没有生成Processor数据, 输出`No data, please check PSREF Spec or contact Short Spec Generation Tools Dev`.

除Commercial和Tablets外, 其他产品线直接从HTML Spec的Processor Family取值, 不要进行任何处理.
