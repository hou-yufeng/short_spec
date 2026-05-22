# Project Snapshot - Short Spec Generator

## 1. 项目建立初始背景

项目最初围绕 `trainning_data` 下的 PDF 训练数据建立。

初始数据形态为每个产品一组 PDF：

- `{产品名}_Spec.PDF`：该产品的完整产品规格。
- `{产品名}_ShortDesc_AutoLayout.pdf`：基于完整产品规格生成的简化产品规格。

项目最初要解决的问题是：分析完整产品规格 PDF 与对应 ShortDesc PDF 之间的转换关系，归纳可复用的生成逻辑和规则。

## 2. 项目最初目标

项目最初目标来自 `docs/my_requirements.md`：

- 以 `trainning_data` 下的 PDF 文件作为原始数据集。
- 分析、整理、归纳从完整产品规格到简化产品规格的生成逻辑和规则。
- 输出一份详细、完整的系统级提示词。
- 该系统级提示词用于指导基于 GPT 5.4 深度思考模型的 M365 Copilot，根据产品完整规格自动生成该产品的简化规格。

## 3. 项目最初交付物

项目最初交付物是：

- 一份系统级提示词，用于执行 Lenovo 产品完整规格到 ShortDesc 的转换。
- 一套从训练 PDF 中归纳出的转换规则。
- 对不同产品转换逻辑差异的整理结果。
- 对规则冲突场景的待确认问题：当不同产品转换逻辑存在矛盾时，需要暂停并向用户确认以哪个规则为准。

## 4. 初始规则约束

项目初始阶段明确了以下行为约束：

- 必须使用 `trainning_data` 下所有 PDF 文件作为训练数据。
- 不能跳过或忽略任何 PDF 文件。
- 每个产品从完整规格到简化规格的转换逻辑可能存在差异，需要完整学习并总结。
- 当不同产品转换逻辑存在包含关系时，采用覆盖范围最大的规则，确保规则包含所有转换逻辑。
- 当不同产品转换逻辑存在矛盾时，需要暂停学习并询问用户。

## 5. 项目演进

项目从最初的“规则学习 + 系统提示词”任务，演进为一个可交付的 Short Spec 生成工具项目。

当前项目定位为：

- Rule-based batch tools for converting full product specification PDFs into short specification Excel summaries.

当前项目支持的能力包括：

- 从产品规格 PDF / TXT 批量生成 Short Spec。
- 将生成结果保存为 Excel workbook。
- 支持 PDF 文本提取。
- 支持基于实际 ShortDesc 的规则评估。
- 支持不同产品线的规则化生成脚本。
- 支持生成本地交付包启动器。

## 6. 当前产品线覆盖

当前仓库中已经包含以下产品线相关规则或生成脚本：

- Commercial laptops / ThinkPad：`scripts/batch_generate_shortspec_excel_rule_based.py`
- Consumer laptops：`scripts/batch_generate_shortspec_excel_rule_based_consumer.py`
- SMB laptops / ThinkBook：`scripts/batch_generate_shortspec_excel_rule_based_smb.py`
- Desktop / DT：`scripts/batch_generate_shortspec_excel_rule_based_dt.py`
- Tablet：`scripts/batch_generate_shortspec_excel_rule_based_tablet.py`

当前仓库中已经包含以下提示词文件：

- ThinkPad：`prompts/spec_to_shortdesc_v7_system.md`、`prompts/spec_to_shortdesc_v7_system.txt`
- Consumer：`prompts/spec_to_shortdesc_consumer_v1_system.md`、`prompts/spec_to_shortdesc_consumer_v1_system.txt`
- SMB：`prompts/spec_to_shortdesc_smb_v1_system.md`、`prompts/spec_to_shortdesc_smb_v1_system.txt`
- DT：`prompts/spec_to_shortdesc_dt_v1_system.md`、`prompts/spec_to_shortdesc_dt_v1_system.txt`
- Tablet：`prompts/spec_to_shortdesc_tablet_v1_system.md`
- 早期通用版本：`prompts/spec_to_shortdesc_v3_system.txt` 到 `prompts/spec_to_shortdesc_v6_system.txt`

## 7. 当前交付物

当前项目已发布到 GitHub：

- Repository：`https://github.com/hou-yufeng/short_spec.git`
- Branch：`main`
- Initial commit：`624b079 Initial project files`

当前已发布到 GitHub 的仓库内容包括：

- `.gitignore`
- `README.md`
- `docs/my_requirements.md`
- `prompts/`
- `scripts/`

当前工作区新增但尚未提交的文档包括：

- `PROJECT_SNAPSHOT.md`

当前代码交付内容包括：

- 共享生成与 Excel 输出模块：
  - `scripts/batch_generate_shortspec_excel.py`
- Rule-based 批量生成脚本：
  - `scripts/batch_generate_shortspec_excel_rule_based.py`
  - `scripts/batch_generate_shortspec_excel_rule_based_consumer.py`
  - `scripts/batch_generate_shortspec_excel_rule_based_smb.py`
  - `scripts/batch_generate_shortspec_excel_rule_based_dt.py`
  - `scripts/batch_generate_shortspec_excel_rule_based_tablet.py`
- 交付包构建脚本：
  - `scripts/build_summary_folder_portable_launchers.py`
  - `scripts/portable_python_runtime.py`

## 8. 当前交付包形态

`README.md` 中定义的交付包目录格式为：

```text
release/short_spec_generator_YYMMDD/
```

交付包顶层只交付 summary launcher `.bat` 文件：

- `short_spec_generator_commercial_laptops.bat`
- `short_spec_generator_consumer_laptops.bat`
- `short_spec_generator_smb_laptops.bat`
- `short_spec_generator_desktop.bat`
- `short_spec_generator_tablet.bat`

这些 launcher 依赖同级的 `shortspec_portable_clean/` runtime folder。

当前已为 `short_spec_generator_260515` 编写面向用户的英文更新要点：

- Added batch short spec generation from product spec files.
- Improved rule-based output for Consumer, SMB, Desktop, and Tablet products.
- Added Excel output support for easier review and sharing.
- Improved short description consistency and formatting.
- Added portable launchers for product-family workflows.
- Training data is not included in this delivery.

## 9. 数据与版本控制约束

训练数据不上传 GitHub。

当前 `.gitignore` 已排除：

- `/data/`
- `/release/`
- `/Tablets/`
- `/test_data/`
- `/training_data_consumer/`
- `/trainning_data_thinkpad/`
- `/train_data_DT/`
- `/train_data_SMB/`
- `/analysis_output/`
- 生成的 workbook、manifest、summary、log、zip、7z 和 portable runtime 文件。

当前已确认：

- `data/` 未被 Git 跟踪。
- `release/` 未被 Git 跟踪。
- GitHub 上发布的是源码、文档、提示词和脚本，不包含训练数据和 release runtime 包。

## 10. 当前状态

已完成：

- 建立本地 Git 仓库。
- 关联远程仓库 `https://github.com/hou-yufeng/short_spec.git`。
- 将本地分支命名为 `main`。
- 创建初始提交 `624b079 Initial project files`。
- 推送 `main` 到 GitHub。
- 确认训练数据目录未上传。
- 编写 `short_spec_generator_260515` 英文更新要点。
- 新增本项目快照文档。

正在进行：

- 当前无正在进行的开发任务。

尚未开始或未在当前材料中明确：

- 是否创建 Git tag。
- 是否创建 GitHub Release。
- 是否把 `short_spec_generator_260515` 更新要点写入正式 release notes。
- 是否补充终端用户使用手册。

## 11. 已确认结论

- 项目名称：`short_spec_generator`
- GitHub 仓库：`https://github.com/hou-yufeng/short_spec.git`
- 发布分支：`main`
- 初始提交：`624b079 Initial project files`
- 训练数据目录不上传。
- `release/` 目录不上传。
- 当前交付面向 Lenovo 产品规格到 ShortDesc / Short Spec Excel summary 的转换。
- 当前交付包含 Commercial laptops、Consumer laptops、SMB laptops、Desktop 和 Tablet 五类启动器。

## 12. 未决问题

- 是否需要为 `short_spec_generator_260515` 创建 Git tag。
- 是否需要创建 GitHub Release 页面。
- 是否需要将英文更新要点保存为独立 release notes 文件。
- 是否需要补充最终用户操作手册。
- 是否需要补充开发者运行、依赖安装和测试说明。

## 13. 建议下一步

- 确认是否创建 `short_spec_generator_260515` 对应的 Git tag。
- 确认是否需要 GitHub Release。
- 如果需要正式交付文档，将英文更新要点整理为 `RELEASE_NOTES_260515.md`。
- 如果需要用户自助运行，补充 launcher 使用说明、输入文件命名要求和输出 Excel 说明。
- 如果需要工程质量闭环，运行现有评估脚本并整理评估结果。
