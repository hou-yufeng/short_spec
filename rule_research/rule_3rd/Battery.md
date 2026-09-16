1.ThinkStation和DT简短规格不需要Battery.
2. 其他产品线从HTML Spec的Battery, Battery Life, Max Battery Life取值

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