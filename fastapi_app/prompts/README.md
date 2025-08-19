# AI航班数据处理提示词系统

## 概述

这个模块包含了专门用于航班数据处理的AI提示词系统，支持多语言和用户偏好处理。

## 功能特点

### 🤖 智能数据处理
- **多源数据整合**：统一处理常规搜索、隐藏城市搜索、AI分析的航班数据
- **智能去重**：识别并去除重复航班
- **数据清洗**：统一格式，处理缺失字段
- **本地化处理**：根据用户语言自动转换机场名称、航空公司名称
- **数据源隐藏**：对用户隐藏具体的第三方数据源名称，使用通用描述

### 🎯 用户偏好支持
- **个性化推荐**：根据用户偏好调整推荐优先级
- **智能分析**：分析用户需求并提供专业建议
- **多样化偏好**：支持价格、时间、舒适度、灵活性等多种偏好

### 🌐 多语言支持
- **中文**：完整的中文机场名称和航空公司名称
- **英文**：标准英文名称
- **自动切换**：根据前端语言设置自动调整输出语言

## 文件结构

```
prompts/
├── flight_processor_prompts.py    # 主要提示词系统
└── README.md                      # 说明文档
```

## 使用方法

### 基本用法

```python
from fastapi_app.prompts.flight_processor_prompts import (
    get_flight_processor_system_prompt,
    get_flight_processing_prompt,
    get_user_preference_examples
)

# 获取系统提示词
system_prompt = get_flight_processor_system_prompt(language="zh")

# 生成处理提示词
prompt = get_flight_processing_prompt(
    google_flights_data=[...],
    kiwi_data=[...],
    ai_data=[...],
    language="zh",
    departure_code="PEK",
    destination_code="LAX",
    user_preferences="我想要最便宜的航班，时间比较灵活"
)
```

### 用户偏好示例

```python
# 获取用户偏好示例
examples = get_user_preference_examples(language="zh")

# 价格导向
price_examples = examples["price_focused"]
# ["我想要最便宜的航班", "预算有限，希望找到性价比高的选择", ...]

# 时间导向
time_examples = examples["time_focused"]
# ["我希望早上出发，下午到达", "不要红眼航班，白天飞行", ...]
```

## 数据源隐藏策略

为了保护商业敏感信息，系统采用以下策略隐藏具体的第三方数据源：

### 🔒 隐藏策略
- **Kiwi** → `隐藏城市搜索` / `hidden_city_search`
- **Google Flights** → `常规搜索` / `regular_search`
- **AI分析** → `AI智能分析` / `ai_analysis`

### 📝 用户界面显示
- 前端显示：`常规航班搜索`、`隐藏城市航班搜索`、`AI智能分析航班`
- API响应：`regular_search`、`hidden_city_search`、`ai_analysis`
- 日志记录：使用通用描述，避免暴露具体供应商名称

## API响应格式

AI处理后返回的标准格式：

```json
{
  "flights": [
    {
      "id": "唯一标识",
      "recommendation_score": 95,
      "recommendation_reason": "推荐理由（基于用户偏好）",
      "price": {
        "amount": 5262,
        "currency": "CNY",
        "formatted": "¥5,262",
        "savings": "相比其他选择节省¥800"
      },
      "departure_airport": {
        "code": "PEK",
        "name": "北京首都国际机场",
        "city": "北京"
      },
      "arrival_airport": {
        "code": "LAX",
        "name": "洛杉矶国际机场",
        "city": "洛杉矶"
      },
      "special_notes": "最佳性价比选择，符合您的预算要求",
      "layovers": [...],
      "source": "google_flights",
      "is_hidden_city": false
    }
  ],
  "summary": {
    "total_flights": 15,
    "recommended_flight_id": "flight_001",
    "user_preference_analysis": "基于您的价格优先偏好，为您推荐了最具性价比的选择",
    "best_value_recommendation": "推荐航班001，价格最低且时间合理",
    "travel_tips": ["建议提前2小时到达机场", "注意查看行李限额"]
  }
}
```

## 支持的用户偏好类型

### 💰 价格导向
- 最便宜的航班
- 性价比优先
- 预算限制

### ⏰ 时间导向
- 早班机偏好
- 避免红眼航班
- 最短飞行时间

### 🛋️ 舒适导向
- 直飞偏好
- 大型航空公司
- 舒适度优先

### 🔄 灵活安排
- 时间灵活
- 接受中转
- 多选择比较

## 集成说明

### 后端集成

在`ai_flight_processor.py`中已经集成了这个提示词系统：

```python
from .prompts.flight_processor_prompts import get_flight_processing_prompt

# 在处理函数中使用
prompt = get_flight_processing_prompt(
    google_data, kiwi_data, ai_data,
    language, departure_code, destination_code, user_preferences
)
```

### 前端集成

在`SearchBar.jsx`中添加了用户偏好输入：

```jsx
// 用户偏好状态
const [userPreferences, setUserPreferences] = useState("");

// 快速选择示例
const preferenceExamples = [
  { label: "最便宜", value: "我想要最便宜的航班" },
  { label: "直飞", value: "希望直飞航班，不要中转" },
  // ...
];
```

## 最佳实践

1. **用户偏好处理**：
   - 提供快速选择选项
   - 支持自定义输入
   - 实时预览AI理解

2. **多语言支持**：
   - 根据前端语言设置自动调整
   - 保持一致的用户体验

3. **错误处理**：
   - 提供降级方案
   - 保留原始数据作为备选

4. **性能优化**：
   - 缓存常用提示词
   - 异步处理大量数据

## 未来扩展

- 支持更多语言
- 增加更多偏好类型
- 集成用户历史偏好学习
- 添加实时偏好调整功能
