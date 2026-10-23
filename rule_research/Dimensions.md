1. 所有产品线都需要Dimensions (WxDxH)简短规格, 除非HTML Spec没有Dimensions (WxDxH).
2. 读取HTML Spec的Dimensions (WxDxH)信息, 表格形式按以下规则选择条目
2.1 ThinkStation和DT产品线规则:
2.1.1 当HTML Spec的Dimensions (WxDxH)表格的"Models"字段存在"Tiny only"时, 直接取"Tiny only"所在行的Dimensions字段数据, 格式为"Tiny only:"+ 换行 + "Dimensions"字段数据.
2.1.2 当HTML Spec的Dimensions (WxDxH)表格的行数为1时, 直接输出"Dimensions"字段数据.
2.1.3 当HTML Spec的Dimensions (WxDxH)表格的行数多于1时, 取全部行数据, 规则是{Models字段数据}+":"+换行+"Dimensions"字段数据.
2.2 Commercial, Consumer, SMB, Laptops产品线规则:
2.2.1 当HTML Spec的Dimensions (WxDxH)表格的行数为1时, 直接输出"Dimensions"字段数据.
2.2.2 当HTML Spec的Dimensions (WxDxH)表格的行数多于1时, 读取"Dimensions"字段下的数据, 找到文本"(maximum) mm"前数字最小的行数据, 格式为文本"Starting at:"+换行+"Dimensions"字段下, 文本"(maximum) mm"前数字最小的行数据.
2.2.3 如果以上均不符合, 则取全部行数据, 规则是{Models字段数据}+":"+换行+"Dimensions"字段数据.
3. 无论Dimensions (WxDxH)是普通文本还是表格字段, 源条目内部有换行时, 简短规格保留该换行.

### 2026-10-16 规则更新
- HTML Spec的Dimensions (WxDxH)条目内部包含换行时, 简短规格在对应位置保留换行；其他选择和输出规则不变.
