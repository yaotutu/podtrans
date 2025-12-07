# RSS模块配置文件使用指南

## 快速开始

### 1. 生成配置文件

```bash
python rss_cli.py init-config
```

这会在项目根目录生成 `rss_config.toml` 文件。

### 2. 编辑配置文件

打开 `rss_config.toml`，配置你的RSS源：

```toml
# RSS模块配置文件
# 支持配置多个RSS源，设置下载模式和全局参数

# ============================================
# 全局设置
# ============================================
[global_settings]
# 数据存储目录
data_dir = "./data"

# 最小文件大小（MB），小于此值视为下载失败
min_file_size_mb = 1.0

# 下载超时时间（秒）
download_timeout = 300

# 最大重试次数
max_retries = 3


# ============================================
# RSS Feeds 配置
# ============================================

# 示例1：下载最新的3集
[[rss_feeds]]
name = "All-In Podcast"
url = "https://feeds.simplecast.com/54nAGcIl"
enabled = true
download_mode = "latest"  # 可选值: "latest" 或 "all"
download_count = 3        # 仅在 download_mode = "latest" 时有效

# 示例2：下载全部剧集（已禁用）
[[rss_feeds]]
name = "Another Podcast"
url = "https://example.com/feed.xml"
enabled = false
download_mode = "all"
# download_count 在 mode="all" 时无效，可以省略
```

### 3. 运行RSS处理

#### 方式1：使用配置文件中的所有RSS源

```bash
python rss_cli.py process
```

这会处理配置文件中所有 `enabled: true` 的RSS源。

#### 方式2：命令行指定单个RSS源

```bash
# 下载最新1集
python rss_cli.py process --rss "https://feeds.simplecast.com/54nAGcIl"

# 下载最新3集
python rss_cli.py process --rss "https://feeds.simplecast.com/54nAGcIl" --mode latest --count 3

# 下载全部
python rss_cli.py process --rss "https://feeds.simplecast.com/54nAGcIl" --mode all
```

### 4. 查看状态

```bash
python rss_cli.py status
```

## 配置文件详解

### RSS Feed配置

每个RSS feed包含以下字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 播客名称（用于识别） |
| `url` | string | 是 | RSS feed URL |
| `enabled` | boolean | 是 | 是否启用此feed |
| `download_mode` | string | 是 | 下载模式：`"latest"` 或 `"all"` |
| `download_count` | int/null | 否 | 下载数量（仅在mode=latest时有效） |

#### download_mode 说明

- **`"latest"`**: 下载最新的N集
  - 需要配置 `download_count`
  - 示例：`"download_mode": "latest", "download_count": 3` → 下载最新3集

- **`"all"`**: 下载RSS中的所有剧集
  - `download_count` 字段无效
  - 示例：`"download_mode": "all", "download_count": null`

### 全局设置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `data_dir` | string | `"./data"` | 数据存储目录 |
| `min_file_size_mb` | float | `1.0` | 最小文件大小（MB），小于此值视为下载失败 |
| `download_timeout` | int | `300` | 下载超时时间（秒） |
| `max_retries` | int | `3` | 最大重试次数 |

## 使用场景

### 场景1：定期更新多个播客

配置文件：
```toml
[[rss_feeds]]
name = "Tech Talk"
url = "https://example.com/tech.xml"
enabled = true
download_mode = "latest"
download_count = 1

[[rss_feeds]]
name = "News Daily"
url = "https://example.com/news.xml"
enabled = true
download_mode = "latest"
download_count = 2
```

运行：
```bash
# 每天定时运行，自动下载所有启用的播客最新集
python rss_cli.py process
```

### 场景2：一次性下载某个播客的全部内容

```bash
python rss_cli.py process --rss "https://example.com/archive.xml" --mode all
```

### 场景3：临时测试某个RSS源

```bash
# 不修改配置文件，直接测试
python rss_cli.py process --rss "https://test.com/feed.xml" --count 1
```

### 场景4：自定义数据目录

```bash
python rss_cli.py process --data-dir /path/to/custom/data
```

## CLI命令参考

### `process` - 处理RSS feed

```bash
python rss_cli.py process [OPTIONS]
```

选项：
- `--rss, -r TEXT`: RSS feed URL（可选，未指定则使用配置文件）
- `--config, -c TEXT`: 配置文件路径（默认：`./rss_config.toml`）
- `--data-dir, -d TEXT`: 数据目录路径（默认：`./data`）
- `--mode, -m TEXT`: 下载模式：`latest` 或 `all`（默认：`latest`）
- `--count, -n INT`: 下载数量（默认：1）

### `status` - 查看状态

```bash
python rss_cli.py status [OPTIONS]
```

选项：
- `--data-dir, -d TEXT`: 数据目录路径（默认：`./data`）

### `init-config` - 生成配置文件

```bash
python rss_cli.py init-config [OPTIONS]
```

选项：
- `--output, -o TEXT`: 配置文件输出路径（默认：`./rss_config.toml`）

## 文件组织结构

```
项目根目录/
├── rss_config.toml          # RSS配置文件（TOML格式，支持注释）
├── rss_cli.py              # RSS CLI入口
├── data/                    # 数据目录
│   ├── episodes.db         # SQLite数据库
│   ├── 播客名1/
│   │   ├── 剧集1.mp3
│   │   └── 剧集2.mp3
│   └── 播客名2/
│       └── 剧集1.mp3
└── src/podtrans/
    ├── rss.py              # RSS核心模块
    └── rss_config.py       # 配置管理模块
```

## 注意事项

1. **重复下载保护**：RSS模块会自动检测已下载的剧集，不会重复下载
2. **文件完整性**：下载后会验证文件大小，小于最小值的文件会被删除并标记为失败
3. **固定命名**：音频文件使用固定的命名规则（基于剧集标题），确保下次运行能识别已下载文件
4. **数据库状态**：所有下载状态都记录在SQLite数据库中

## 故障排查

### 问题：配置文件加载失败

检查：
- 配置文件是否存在
- TOML格式是否正确（注意：字符串需要用引号，布尔值用true/false不加引号）
- 字段类型是否匹配

### 问题：下载失败

检查：
- RSS URL是否可访问
- 网络连接是否正常
- `download_timeout` 是否足够（大文件需要更长时间）

### 问题：文件被标记为失败

原因：
- 文件大小小于 `min_file_size_mb` 设置的阈值
- 下载过程中断

解决：
- 检查网络连接
- 增加 `download_timeout`
- 调整 `min_file_size_mb`（某些播客文件可能确实很小）

## 高级用法

### 使用代理

修改 `src/podtrans/rss.py` 中的 httpx 客户端配置：

```python
async with httpx.AsyncClient(
    timeout=timeout_value,
    follow_redirects=True,
    proxies="http://proxy.example.com:8080"  # 添加代理
) as client:
```

### 自定义清理规则

根据 `error_count` 自动清理失败的剧集：

```bash
# 在数据库中查询失败次数 > 3 的剧集并清理
```

## 版本历史

- v1.0.0 (2025-12-07): 初始版本
  - 支持配置文件管理
  - 支持下载模式（latest/all）
  - 完整的文件验证机制
