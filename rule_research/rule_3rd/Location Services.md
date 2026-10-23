Location Services 简短规格专用于 Tablets 产品线。
1. 从 PSREF HTML Spec - Location Services 取值。
2. 如果源数据以条目呈现，按源顺序输出所有非“No”开头的条目；如果存在“No”开头的条目，则所有取得的条目末尾加“*”。
3. 如果源数据以表格呈现，按源行顺序选择“Location”字段非“No”开头的行，每行输出“Models”字段 + “: ” + “Location”字段；如果“Location”字段存在“No”开头的数据，则所有输出条目末尾加“*”。
4. 如果 HTML Spec 没有 Location Services，或条目形式仅有“No”开头的数据，或表格形式的“Location”字段仅有“No”开头的数据，则不生成 Location Services 简短规格。
