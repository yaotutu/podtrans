# Translation Prompts

本目录存放翻译系统的 Prompt 模板,支持自定义优化。

## 使用方法

1. 复制示例文件创建自定义 Prompt
2. 在环境变量中配置 Prompt 文件路径 (未来功能)
3. 当前版本: Prompt 嵌入代码中,可通过修改 `translator.py` 自定义

## 未来计划

- [ ] 支持外部 Prompt 文件加载
- [ ] 支持多语言对 Prompt 模板
- [ ] 支持 Prompt 版本管理
- [ ] A/B 测试不同 Prompt 的效果

## 示例

查看 `translator.py` 中的 `_get_system_prompt()` 方法获取当前 Prompt。
