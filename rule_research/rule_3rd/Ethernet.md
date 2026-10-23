Ethernet简短规格生成规则:
1. ThinkStation产品线读取HTML Spec的Optional Ethernet信息, DT产品线优先读取Onboard Ethernet, 若该字段没有值则读取Ethernet, 其他产品线读取Ethernet信息. 
2. 以下情况不生成Ethernet简短规格:
2.1 非ThinkStation和DT产品线的HTML Spec不包含Ethernet
2.2 非ThinkStation和DT产品线的HTML Spec下的Ethernet仅有包含"No onboard Ethernet"条目.
3. ThinkStation产品线Ethernet简短规格生成规则是直接读取HTML Spec的Optional Ethernet下信息的第一个冒号之前的数据, 作为Ethernet简短规格信息.
4. 非ThinkStation产品线Ethernet简短规格生成规则是:
  4.1 DT产品线优先读取HTML Spec的Onboard Ethernet信息, 若该字段没有值则读取Ethernet; 其他产品线读取Ethernet信息. 若选定字段没有值或只有 No onboard Ethernet, 不输出.
  4.2 删除括号及其内容。
  4.3 删除控制器、厂商、管理能力与附加说明，例如：
      - Intel Ethernet Controller I226-LM
      - Realtek RTL8111EPV
      - Killer Ethernet E3100G
      - vPro models / non-vPro models
      - supports Wake-on-LAN
      - AMD PRO Manageability
  4.5 识别速率与端口数：
  4.5.1 {速率}的生成
      - HTML Spec中的速率和简短规格输出的速率对应关系是:
        Gigabit Ethernet - Gigabit Ethernet
        2.5GbE - 2.5GbE
        10GbE - 10GbE
        Dual 2.5GbE - 2x 2.5GbE
        Dual Gigabit Ethernet - 2x Gigabit Ethernet
      - 存在多个不同速率时, 用"+"连接
      - Dual 2.5GbE和Dual Gigabit Ethernet分别只识别为对应的2x速率, 不再从同一表述重复识别普通2.5GbE或Gigabit Ethernet.
  4.5.2 {端口数}的生成
      - 抓取HTML Spec中包含Ax RJ-45的文本, A为数字.
  4.6 最终简短规格的输出格式是{速率}, {端口数}
  4.7 对结果去重

### 2026-10-16 规则更新
- 识别Dual 2.5GbE或Dual Gigabit Ethernet时, 同一表述只输出对应的2x速率, 不再重叠匹配普通2.5GbE或Gigabit Ethernet.
- Desktop产品线优先读取有值的Onboard Ethernet；该字段没有值时回退读取Ethernet；两个字段都没有值时不生成Ethernet简短规格. 其他产品线规则不变.
