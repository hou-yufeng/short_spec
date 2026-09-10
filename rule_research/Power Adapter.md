仅Commercial / SMB / Consumer / Tablets 简短规格需要Power Adapter.
仅HTML Spec包含Power Adapter时生成Power Adapter的简短规格.
Commercial / SMB / Consumer 的 Power Adapter简短规格规则是:
1 读取HTML Spec的Power Adapter下所有条目."No" 开头的条目忽略.
2 去掉每个条目中括号及括号中的内容, 去掉"supports ", 去掉", 100-240V, 50-60Hz", 去掉"AC", 然后去重.
3 如果存在No开头的条目, 或者非No条目多于1条, 则每个条目后都加星号"*".
4. 去重.
Tablets 的 Power Adapter简短规格规则是:
1 读取HTML Spec的Power Adapter下所有条目."No" 开头的条目忽略.
2 每个非"No"条目取第一个逗号","前的数据
3 如果存在No开头的条目, 或者非No条目多于1条, 则每个条目后都加星号"*".
4. 去重.


