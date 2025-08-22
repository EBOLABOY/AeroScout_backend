# FastAPI应用模块

> [根目录](../CLAUDE.md) > [fastapi_app](.) > **FastAPI应用模块**

## 模块职责

FastAPI应用模块是Ticketradar系统的核心，负责提供RESTful API服务、处理业务逻辑、管理数据访问和集成外部服务。

## 入口与启动

### 主入口文件
- **启动脚本**: `../main_fastapi.py`
- **应用配置**: `config/settings.py`
- **生命周期管理**: 应用启动/关闭时的资源初始化和清理

### 启动流程
1. 加载环境变量和配置
2. 设置日志系统
3. 初始化数据库连接(Supabase)
4. 启动缓存服务(Redis)
5. 自动启动监控系统
6. 注册API路由
7. 启动Web服务器

## 对外接口

### API路由结构
```
/api/
├── auth/          # 认证相关
│   ├── login      # 用户登录
│   ├── register   # 用户注册
│   └── profile    # 用户信息
├── flights/       # 航班相关
│   ├── search     # 航班搜索
│   ├── monitor    # 监控数据
│   └── airports   # 机场信息
├── monitor/       # 监控管理
│   ├── tasks      # 监控任务
│   └── status     # 系统状态
└── admin/         # 管理员功能
    ├── users      # 用户管理
    └── system     # 系统配置
```

### 核心API端点

#### 航班搜索API
- `GET /api/flights/search` - 基础航班搜索
- `GET /api/flights/search/comprehensive` - 三阶段综合搜索
- `GET /api/flights/search/ai-enhanced` - AI增强搜索
- `POST /api/flights/search/ai-enhanced/async` - 异步AI搜索

#### 监控API
- `GET /api/flights/monitor/{city_code}` - 获取监控数据
- `GET /api/monitor/tasks` - 监控任务管理
- `GET /api/monitor/status` - 系统状态

#### 认证API
- `POST /auth/login` - 用户登录
- `POST /auth/register` - 用户注册
- `GET /auth/profile` - 用户信息

### 响应格式
```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "error": null
}
```

## 关键依赖与配置

### 核心依赖
- **FastAPI**: Web框架
- **Supabase**: 数据库和认证
- **Redis**: 缓存系统
- **smart-flights**: 航班数据API
- **loguru**: 日志系统

### 配置管理
- **环境变量**: 通过`.env`文件管理
- **配置类**: `config/settings.py`中的Settings类
- **动态配置**: 支持运行时配置更新

### 外部服务集成
- **AI服务**: 第三方Gemini API
- **航班数据**: Google Flights + Kiwi API
- **通知服务**: 邮件/短信通知
- **监控服务**: 自动化价格监控

## 数据模型

### 核心数据结构

#### 航班搜索模型
- `FlightSearchRequest`: 搜索请求参数
- `FlightSearchResponse`: 搜索结果响应
- `FlightResult`: 单个航班结果
- `FlightLeg`: 航段信息

#### 监控数据模型
- `MonitorFlightData`: 监控航班数据
- `MonitorDataResponse`: 监控数据响应
- `MonitorTask`: 监控任务定义

#### 用户模型
- `UserInfo`: 用户基本信息
- `UserPreferences`: 用户偏好设置

### 数据验证
- 使用Pydantic进行数据验证
- 自动类型转换和错误提示
- 支持复杂嵌套数据结构

## 测试与质量

### 测试策略
- **单元测试**: 针对各个服务类
- **集成测试**: API端点测试
- **性能测试**: 搜索性能优化

### 质量保证
- **代码格式化**: 使用Black
- **类型检查**: MyPy类型注解
- **代码审查**: Pull Request流程
- **自动化测试**: CI/CD集成

### 错误处理
- **统一错误格式**: 标准化错误响应
- **异常捕获**: 全局异常处理
- **日志记录**: 详细错误日志
- **用户友好**: 用户可理解的错误信息

## 常见问题 (FAQ)

### Q: 如何处理航班搜索的超时问题？
A: 实现了异步搜索机制，支持长时间运行的任务，通过任务ID查询结果。

### Q: AI搜索失败时如何降级？
A: 系统会自动降级到基础搜索功能，确保基本服务可用。

### Q: 如何优化搜索性能？
A: 使用Redis缓存搜索结果，智能选择AI模型，异步处理大请求。

### Q: 监控任务如何确保数据准确性？
A: 定期校验数据源，实现多重验证机制，错误重试策略。

## 相关文件清单

### 配置文件
- `config/settings.py` - 主配置文件
- `config/logging_config.py` - 日志配置
- `config/supabase_config.py` - 数据库配置

### 模型文件
- `models/flights.py` - 航班数据模型
- `models/auth.py` - 认证模型
- `models/monitor.py` - 监控模型
- `models/common.py` - 通用模型

### 路由文件
- `routers/flights.py` - 航班API路由
- `routers/auth.py` - 认证路由
- `routers/monitor.py` - 监控路由
- `routers/admin.py` - 管理员路由

### 服务文件
- `services/flight_service.py` - 航班搜索服务
- `services/ai_flight_service.py` - AI增强服务
- `services/monitor_service.py` - 监控服务
- `services/supabase_service.py` - 数据库服务
- `services/cache_service.py` - 缓存服务
- `services/async_task_service.py` - 异步任务服务

### 工具文件
- `utils/password.py` - 密码工具
- `dependencies/auth.py` - 认证依赖
- `middleware/performance.py` - 性能监控中间件

## 变更记录 (Changelog)

### 2025-08-22
- ✨ 创建FastAPI模块文档
- 📊 完成API接口梳理
- 🏗️ 建立模块文档结构

### 下一步计划
- 🔧 完善服务类文档
- 🚀 优化API性能
- 📱 增加错误处理
- 🔒 加强安全措施

---

**模块维护**: 请在修改相关代码时同步更新此文档，确保文档的准确性和完整性。