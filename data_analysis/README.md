# 数据分析目录

本目录用于保存航班搜索过程中的数据清洗前后对比文件，帮助分析和优化数据处理流程。

## 目录结构

```
data_analysis/
├── README.md                           # 本说明文件
├── data_comparison_YYYYMMDD_HHMMSS.json # 数据对比文件
└── ...                                 # 其他分析文件
```

## 数据对比文件格式

每次执行三阶段航班搜索时，系统会自动生成数据对比文件，包含以下内容：

### 文件命名规则
- 格式：`data_comparison_YYYYMMDD_HHMMSS.json`
- 示例：`data_comparison_20250828_143025.json`

### 文件内容结构

```json
{
  "metadata": {
    "timestamp": "2025-08-28T14:30:25.123456",
    "search_params": {
      "departure_code": "SHA",
      "destination_code": "NYC",
      "depart_date": "2025-09-15",
      "return_date": "2025-09-22",
      "adults": 1,
      "seat_class": "ECONOMY",
      "language": "zh",
      "currency": "CNY",
      "is_guest_user": false,
      "user_preferences": {}
    },
    "compression_stats": {
      "original_size": {
        "total_size": 1234567,
        "flight_counts": {
          "google_flights": 50,
          "kiwi_flights": 75,
          "ai_flights": 25
        }
      },
      "cleaned_size": {
        "total_size": 456789,
        "flight_counts": {
          "google_flights": 50,
          "kiwi_flights": 75,
          "ai_flights": 25
        }
      },
      "reduction_ratio": 63.0
    }
  },
  "original_data": {
    "google_flights": [...],  // 清洗前Google Flights原始数据
    "kiwi_flights": [...],    // 清洗前Kiwi原始数据
    "ai_flights": [...]       // 清洗前AI推荐原始数据
  },
  "cleaned_data": {
    "google_flights": [...],  // 清洗后Google Flights数据
    "kiwi_flights": [...],    // 清洗后Kiwi数据
    "ai_flights": [...]       // 清洗后AI推荐数据
  }
}
```

## 字段说明

### metadata 元数据
- `timestamp`: 数据生成时间
- `search_params`: 搜索参数，包含出发地、目的地、日期等信息
- `compression_stats`: 数据压缩统计信息

### original_data 清洗前数据
包含三个数据源的原始数据：
- `google_flights`: Google Flights API 返回的原始航班数据
- `kiwi_flights`: Kiwi API 返回的原始航班数据（包含隐藏城市）
- `ai_flights`: AI 推荐的原始航班数据

### cleaned_data 清洗后数据
经过 FlightDataFilter 处理后的干净数据，去除了：
- 技术调试字段（如 _id, debug_info, metadata）
- 冗余字段（如重复的价格字段）
- 无意义值（如 null, '', 'N/A'）
- 过长的编码字符串
- API 内部使用的字段

## 使用方式

### 自动保存
- 每次执行三阶段搜索时自动保存
- 文件保存在 Docker 容器内 `/app/data_analysis` 目录
- 通过 Docker volume 挂载到本地 `./data_analysis` 目录

### 手动分析
1. 查看文件列表：
   ```bash
   ls -la data_analysis/
   ```

2. 查看压缩效果：
   ```bash
   grep -A 5 "reduction_ratio" data_analysis/data_comparison_*.json
   ```

3. 分析数据结构差异：
   ```bash
   jq '.original_data.google_flights[0] | keys' data_comparison_YYYYMMDD_HHMMSS.json
   jq '.cleaned_data.google_flights[0] | keys' data_comparison_YYYYMMDD_HHMMSS.json
   ```

### 配置选项

可以在 `FlightDataFilter` 类中调整以下配置：

```python
# 数据保存配置
self.data_save_enabled = True  # 是否启用数据保存
self.save_directory = "/app/data_analysis"  # 保存目录路径
```

## 注意事项

1. **存储空间**: 数据文件可能较大，请定期清理旧文件
2. **隐私保护**: 文件可能包含搜索记录，请妥善保管
3. **性能影响**: 数据保存过程可能略微影响搜索响应时间
4. **Docker 部署**: 确保 Docker 容器有权限写入挂载目录

## 故障排查

### 数据保存失败
1. 检查目录权限：
   ```bash
   ls -la data_analysis/
   ```

2. 检查 Docker 挂载：
   ```bash
   docker inspect ticketradar-app | grep -A 5 "Mounts"
   ```

3. 查看日志：
   ```bash
   docker logs ticketradar-app | grep "数据保存"
   ```

### 文件格式错误
1. 验证 JSON 格式：
   ```bash
   jq '.' data_analysis/data_comparison_YYYYMMDD_HHMMSS.json
   ```

2. 检查文件完整性：
   ```bash
   wc -l data_analysis/data_comparison_*.json
   ```

## 更新历史

- **2025-08-28**: 初始版本，支持基础数据对比保存功能
- **未来计划**: 
  - 添加数据可视化分析
  - 支持自定义保存过滤器
  - 集成性能监控指标