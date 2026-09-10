说明: 本文档维护了部分简短规格的生成规则, H3标题为简短规格中的Feature, H3下的内容是该Feature简短规格的生成规则, 直到下一个H3标题结束.

### Processor

+ 直接从HTML Spec 的Processor Family取值. 如果HTML Spec 的Processor Family存在多个选项, 则以项目列表形式输出

### AI PC Category

+ 直接从HTML Spec 的AI PC Category取值. 
  + 如果HTML Spec 的AI PC Category只存在单个项, 直接输出
  + 如果HTML Spec 的AI PC Category存在多个项, 按照以下逻辑处理:
    + 如果多个项中包含"AI-Ready Workstations", 则直接输出所有AI PC Category下的选项
    + 其他情况, 直接输出每个选项, 去掉任何括号及括号里的内容, 然后给每个选项加星号*
+ 如果产品HTML Spec不包含AI PC Category, 则简短规格不输出AI PC Category的信息.

### NPU

+ 直接从HTML Spec 的NPU取值. 
+ 所有选项以项目列表形式输出
+ 不输出包含No的选项
+ 如果HTML Spec 的NPU有包含No文本的选项, 所有输出都以*结尾.
+ 如果HTML Spec 的NPU有包含Optional文本选项, 该选项以*结尾.
+ 如果产品HTML Spec不包含NPU, 则简短规格不输出NPU的信息.

### Chipset

+ 取值来自HTML Spec下的Chipset
  + 对于DT和ThinkStation, 直接输出原值中不包含No文本的所有选项. 如果存在包含No文本的选项, 所有输出加星号*
  + 对于DT和ThinkStation以外的产品线, 只输出不包含SoC和No文本的选项. 如果存在包含No文本的选项, 所有输出加星号*
+ 如果产品HTML Spec不包含Chipset, 则简短规格不输出Chipset的信息.

### Audio

+ 直接从HTML Spec 的Audio Chip, Speakers, Microphone取值.
  + 1. 选择Audio Chip下选项的第一个逗号前的文本. 如果存在多个条件分支选项, 则将每个选项的第一个逗号前的文本用"/" 连接起来, "/" 前后加空格.
    2. 直接输出Speakers下的所有选项.
    3. 直接输出Microphone下的所有选项.
    
  + 依次以项目列表的格式输出以上1, 2, 3各项. 如果Audio Chip, Speakers, Microphone下存在包含No, Non的值, 则该Feature下输出的选项结尾均加*
  
+ 如果产品HTML Spec不包含Audio Chip, Speakers, Microphone中的任意子Feature, 则简短规格的Audio不输出该子Feature的信息. 

+ 如果产品HTML Spec不包含Audio Chip, Speakers, Microphone中的全部Feature, 则简短规格不输出Audio

### Camera

+ 直接从HTML Spec 的Camera取值
+ 如果选项存在条件分支, 删除条件分支的信息 (以"XXX: " 为标记, XXX为任意文本).
+ 如果存在"No camera"或包含No, Non的选项, 则输出的每个选项都加*
+ HTML Spec的"Computer Vision on Image Signal Processor (ISP)" 简写为"CV on ISP", "Computer Vision on Image Signal Processor (ISP)"不区分大小写
+ 如果产品HTML Spec不包含Camera, 则简短规格不输出Camera的信息.

### Battery

+ 从HTML Spec的Battery, Battery Life, Max Battery Life取值

+ 第一项输出是电池容量+"battery"+逗号+空格+快速充电
  + 电池容量的值是HTML Spec的Battery下的每个选项, 去掉条件分支的信息 (以"XXX: " 为标记, XXX为任意文本)以后, 以数字+Wh或数字+mAh组成的文本
  + 快速充电的值是HTML Spec的Battery下的每个选项中, 以"supports"开始, 到空格+左括号之前的文本, 不包含"supports".
  + 如果没有"supports", 则仅输出电池容量+"battery"
  + 如果Battery下有多个选项, 则每个选项都按照以上规则输出, 删除条件分支的信息 (以"XXX: " 为标记, XXX为任意文本)
  
+ 第二项输出是续航时间

  + 续航时间取自HTML Spec的Battery Life或Max Battery Life, 哪个存在于HTML Spec就用哪个.
    + 对于非Tablets产品线, 
      + 仅取条件分支包含"MobileMark", 取该条件分支后, 到"hr" 之前的数字. 如果存在多个含含"MobileMark"的条件分支, 取含"MobileMark"后数字最大的那个条件分支.
      + 若条件分支不包含"MobileMark", 则不输出数字
      + 输出"Up to "+找到的数字+空格+hr
    + 对于Tablets产品线
      + 先比较续航时间的值. 方法是遍历HTML Spec的Max Battery Life下所有条件分支 (以"XXX: " 为标记, XXX为任意文本) 后, 到"hr"之前的数字
      + 选择数字最大但小于100的那个数字及所在的条件分支.
      + 输出找到的条件分支+" up to "+找到的数字+空格+hr
+ 如果产品HTML Spec不包含Battery, 则简短规格不输出Battery的信息.

### Power Adapter

+ 仅用于除DT和ThinkStation以外的产品线交付物
+ 取值自HTML Spec的Power Adapter, 规则是:
  + 取HTML Spec的Power Adapter下所有不包含No power, Non文本的选项
  + 如果含包含No power, Non文本的选项, 则所有输出都以*结尾
  + 取值时, 去掉括号及括号内的内容, 去掉"supports "
  + 只保留前两个逗号前的文本

### Power Supply

+ 仅用于DT和ThinkStation
+ 取值自HTML Spec的Power Supply
+ 对于ThinkStation:
  + 取HTML Spec的Power Supply下每个选项的Power, Efficiency, Key Features字段下的值
  + 忽略Power字段包含No power, Non文本的选项
  + 文本拼接规则是, 每个选项的Power字段值+Efficiency字段值+"fixed PSU"+","+Key Features字段值排除"Autosensing, "文本, 每部分中间都加空格.
  + 如果含包含No power, Non文本的选项, 则所有输出都以*结尾
+ 对于DT:
  + 取HTML Spec的Power Supply下每个选项的Power, Efficiency字段下的值
  + 忽略Power字段包含No power, Non文本的选项
  + 文本拼接规则是, 每个选项的Power字段值+Efficiency字段值+Type字段值 (首字母小写)+"PSU", 每部分中间都加空格.



  



