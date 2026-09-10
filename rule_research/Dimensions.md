1. 所有产品线都需要Dimensions (WxDxH)简短规格, 除非HTML Spec没有Dimensions (WxDxH).
2. 读取HTML Spec的Dimensions (WxDxH)信息, 源信息以HTML表格形式呈现.
3. 当HTML表格的数据仅包含一行数据, 且数据Models字段仅有"All models", 则直接读取表格的Dimensions字段信息并作为Dimensions (WxDxH)的简短规格信息.
4. 当HTML表格的数据包含一行或多行数据, 且数据Models字段没有"All models", 则Dimensions (WxDxH)简短规格信息生成格式为:每行数据的Models字段信息加冒号和空格": "再加上Dimensions字段的数据. 每行数据都作为单独一行.