# HTML ShortSpec 产品线规则归属

本清单定义 HTML Spec 路径的业务规则所有权。每个产品线目录中的同名特征文件均为独立规则副本；不得通过跨产品线导入复用业务判断。公共代码仅可承担 HTML 读取、基础结构化、工作簿读写、行合并和输出校验。

| 配置键 | 数据目录 | 产品线规则目录 | HTML 样本数 |
| --- | --- | --- | ---: |
| `com` | `data/html/commercial_laptop` | `scripts/html_product_rules/commercial_laptop` | 272 |
| `con` | `data/html/consumer_laptop` | `scripts/html_product_rules/consumer_laptop` | 729 |
| `smb` | `data/html/smb_laptop` | `scripts/html_product_rules/smb_laptop` | 208 |
| `tab` | `data/html/tablet` | `scripts/html_product_rules/tablet` | 106 |
| `dt` | `data/html/desktop` | `scripts/html_product_rules/desktop` | 318 |
| `ts` | `data/html/thinkstation` | `scripts/html_product_rules/thinkstation` | 37 |

| 特征 | com | con | smb | tab | dt | ts |
| --- | --- | --- | --- | --- | --- | --- |
| Storage | 已有 | 已有 | 已有 | 已有 | 已有 | 已有 |
| WLAN | 已有 | 已有 | 已有 | 已有 | 已有 | 已有 |
| Display | 已有 | 已有 | 已有 | 已有 | 已有 | 不适用（当前 HTML SDW 入口无 ThinkStation Display） |
| Memory | 已有 | 已有 | 已有 | 已有 | 已有 | 已有 |
| Operating System | 已有 | 已有 | 已有 | 已有 | 已有 | 已有 |
| Special Features | 已有 | 已有 | 已有 | 已有 | 已有 | 已有 |
| Keyboard | 已有 | 已有 | 已有 | 已有 | 不适用（MKOSC 输出范围不含 Keyboard） | 不适用（MKOSC 输出范围不含 Keyboard） |
| Other Certifications | 已有 | 已有 | 已有 | 已有 | 已有 | 不适用（既定规则要求 ThinkStation 省略） |

## 入口边界

- `html_sdw_runner.py`：产品线入口选择其独立的 Storage、WLAN、Display 规则。
- `html_oskc_runner.py`：产品线入口选择其独立的 Memory、Operating System、Special Features、Keyboard、Other Certifications 规则。
- `html_all_runner.py`：保留完整规格组合职责；其 Keyboard 与 Other Certifications HTML 覆盖选择产品线独立实现。

产品线规则修改时，必须以相应 `data/html/<产品线>` 的全部样本重新生成，并与拆分前工作簿逐行比对 Product、L1 Feature、L2 Feature、Short Spec 和 Note。
