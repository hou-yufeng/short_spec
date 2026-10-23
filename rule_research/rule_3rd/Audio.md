Audio 简短规格适用于Commercial, Consumer, SMB, Desktop, Tablets产品线. 以下是各产品线生成规则:
1.1 从HTML Spec的Audio Chip, Speakers, Microphone取值.
1.2 依次读取HTML Spec的Audio Chip下的条目, 检查是否包含"SoundWire"或"High Definition (HD) Audio"文本, 包含哪个就输出哪个.都不存在则直接输出HTML Spec的Audio Chip的信息
1.3 读取HTML Spec的Speakers 和 Microphone下的条目. 忽略"No"开头的条目
1.4 HTML Spec下的Audio Chip, Speakers, Microphone, 哪个不存在就忽略哪个.
1.5 将以上规则读取到的HTML Spec的Audio Chip, Speakers, Microphone条目输出到Audio, 同样以条目形式输出.
**2026.10.13**
更新Audio规则:
  1. 检查是否包含"SoundWire"或"High Definition (HD) Audio"文本时, 如果HTML Spec的Audio Chip包含多个条件分支, 则在输
  出"SoundWire"或"High Definition (HD) Audio"文本时, 将条件分支一起输出.
  2. 如果HTML Spec的Speakers, Microphone存在"No"开头的条目, 则输出的HTML Spec的Speakers 和 Microphone下的条目结尾加星
  号"*". 如果HTML Spec的Speakers 和 Microphone输出的条目包含条件分支, 则条件分支一起输出.
  你需要将交付物third_batch_html_260919一起更新. Audio的其他规则或适应产品线不要修改.