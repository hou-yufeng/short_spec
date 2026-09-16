1. Commercial / Consumer / SMB:
 - 从 HTML Spec的Audio Chip、Speakers、Microphone 三个Feature取值。每个Feature下的每个值都单独占据一行.
      - Audio Chip 仅保留包含 High Definition (HD) Audio 或 SoundWire 的第一项，并去除其后的 codec 描述。
      - Speakers 保留完整值
      - Microphone 保留完整值
      - Microphone忽略以"No"开头的值；如果存在以"No"开头的值, 则生成的简短规格的Microphone结尾加星号"*"
      - 生成的简短规格去掉 "optimized with"；最后去重。
2. DT:
 - 从 HTML Spec的Audio Chip、Speakers、Microphone 三个Feature取原值, 不做修改。每个Feature下的每个值都单独占据一行.
3. Tablets:
 - 从 HTML Spec的Speakers、Microphone 两个Feature取值。每个Feature下的每个值都单独占据一行.
      - Speakers 保留完整值
      - Microphone 保留完整值
      - Microphone忽略以"No"开头的值；如果存在以"No"开头的值, 则生成的简短规格的Microphone结尾加星号"*"
      - 生成的简短规格去掉 "optimized with"；最后去重。