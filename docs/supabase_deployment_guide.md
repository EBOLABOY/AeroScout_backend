# Supabase认证系统部署指南

本指南提供Ticketradar项目完全基于Supabase认证的现代化部署方案。

## 🎯 部署概览

### 现代化认证架构
- **前端**: 使用Supabase Client SDK完整认证流程
- **后端**: 纯Supabase token验证，遵循KISS原则
- **数据同步**: 自动同步Supabase Auth用户到业务表
- **简洁设计**: 移除传统JWT和密码哈希复杂度

## 📋 前置准备

### 1. Supabase项目设置
1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 确认项目配置：
   - Project URL: `https://guecfssgxqhxyxyxjobg.supabase.co`
   - Anon Key: 从设置中获取
   - Service Role Key: 从设置中获取（保密）

### 2. 邮件服务配置
在Supabase Dashboard > Authentication > Settings中：
- **Enable email confirmations**: 启用
- **Enable secure email change**: 启用  
- **Email templates**: 自定义邮件模板（可选）

### 3. OAuth Provider设置
#### Google OAuth配置：
1. 在Supabase Dashboard > Authentication > Providers > Google:
   - 启用Google Provider
   - 设置Client ID和Client Secret
2. 在Google Cloud Console中：
   - 添加授权重定向URI: `https://guecfssgxqhxyxyxjobg.supabase.co/auth/v1/callback`

## 🚀 后端部署步骤

### Step 1: 环境配置

```bash
# 复制配置模板
cp .env.example .env
```

在`.env`中配置关键参数：

```env
# Supabase配置（必需）
SUPABASE_URL=https://guecfssgxqhxyxyxjobg.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# 网站配置（重要：用于邮件回调）
SITE_URL=https://ticketradar.izlx.de

# Google OAuth（如果使用）
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# AI服务配置
AI_API_KEY=your-ai-api-key-here
AI_API_URL=http://154.19.184.12:3000/v1
AI_MODEL_AUTHENTICATED=gemini-2.5-pro

# 缓存配置
REDIS_URL=redis://localhost:6379/0
```

### Step 2: 数据库表结构

确保`users`表支持Supabase用户同步：

```sql
-- 在Supabase SQL编辑器中执行
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT auth.uid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    user_level_id INTEGER,
    user_level_name VARCHAR(50) DEFAULT 'user',
    user_metadata JSONB DEFAULT '{}',
    last_sign_in_at TIMESTAMP,
    provider TEXT DEFAULT 'email',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_users_email_verified ON users(email_verified);
CREATE INDEX IF NOT EXISTS idx_users_provider ON users(provider);
CREATE INDEX IF NOT EXISTS idx_users_user_level ON users(user_level_id);

-- RLS政策（Row Level Security）
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 允许用户查看和更新自己的记录
CREATE POLICY "Users can view own record" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own record" ON users
    FOR UPDATE USING (auth.uid() = id);
```

### Step 3: 启动服务

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python main_fastapi.py

# 生产环境使用Docker
docker compose up -d
```

## 🎨 前端集成配置

### Step 1: Supabase客户端初始化

```javascript
// lib/supabase.js
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://guecfssgxqhxyxyxjobg.supabase.co'
const supabaseAnonKey = 'your-anon-key'

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'pkce'  // 推荐的安全流程
  }
})
```

### Step 2: 认证服务封装

```javascript
// services/auth.js
import { supabase } from '../lib/supabase'

export class AuthService {
  // 邮箱注册
  static async signUp(email, password, username) {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { username }
      }
    })
    
    if (error) throw error
    return data
  }

  // 邮箱登录
  static async signIn(email, password) {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    })
    
    if (error) throw error
    return data
  }

  // Google OAuth登录
  static async signInWithGoogle() {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/dashboard`
      }
    })
    
    if (error) throw error
    return data
  }

  // 登出
  static async signOut() {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }
}
```

### Step 3: API调用配置

所有需要认证的API调用使用Supabase token：

```javascript
// utils/api.js
import { supabase } from '../lib/supabase'

class ApiClient {
  async request(endpoint, options = {}) {
    const { data: { session } } = await supabase.auth.getSession()
    
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    }
    
    if (session?.access_token) {
      headers.Authorization = `Bearer ${session.access_token}`
    }
    
    const response = await fetch(`/api${endpoint}`, {
      ...options,
      headers
    })
    
    return response.json()
  }

  // PushPlus设置
  async updateNotificationSettings(settings) {
    return this.request('/auth/settings/notifications', {
      method: 'PUT',
      body: JSON.stringify(settings)
    })
  }

  // 监控任务管理
  async createMonitorTask(taskData) {
    return this.request('/monitor/tasks', {
      method: 'POST',
      body: JSON.stringify(taskData)
    })
  }
}

export const api = new ApiClient()
```

## 🔗 关键API端点

### 认证相关
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/auth/login` | POST | 用户登录 | 无 |
| `/auth/register` | POST | 用户注册 | 无 |
| `/auth/me` | GET | 获取用户信息 | Bearer Token |
| `/auth/google/signin` | GET | Google OAuth登录 | 无 |

### 用户设置
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/auth/settings/notifications` | GET | 获取通知设置 | Bearer Token |
| `/auth/settings/notifications` | PUT | 更新PushPlus设置 | Bearer Token |

### 监控任务
| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/monitor/tasks` | GET | 获取监控任务 | Bearer Token |
| `/monitor/tasks` | POST | 创建监控任务 | Bearer Token |
| `/monitor/tasks/{id}` | PUT | 更新任务 | Bearer Token |

## 🔍 PushPlus集成说明

### 1. 前端设置界面

```jsx
// components/NotificationSettings.jsx
import { useState, useEffect } from 'react'
import { api } from '../utils/api'

export const NotificationSettings = () => {
  const [settings, setSettings] = useState({
    pushplus_token: '',
    price_alerts: true
  })

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const response = await api.request('/auth/settings/notifications')
      if (response.success) {
        setSettings(response.data)
      }
    } catch (error) {
      console.error('加载通知设置失败:', error)
    }
  }

  const saveSettings = async () => {
    try {
      const response = await api.updateNotificationSettings(settings)
      if (response.success) {
        alert('设置保存成功')
      }
    } catch (error) {
      console.error('保存设置失败:', error)
    }
  }

  return (
    <div className="notification-settings">
      <h3>推送通知设置</h3>
      
      <div className="form-group">
        <label>PushPlus Token</label>
        <input 
          type="text"
          value={settings.pushplus_token}
          onChange={(e) => setSettings({
            ...settings,
            pushplus_token: e.target.value
          })}
          placeholder="请输入PushPlus Token"
        />
        <small>
          获取Token: <a href="https://www.pushplus.plus/" target="_blank">PushPlus官网</a>
        </small>
      </div>

      <div className="form-group">
        <label>
          <input 
            type="checkbox"
            checked={settings.price_alerts}
            onChange={(e) => setSettings({
              ...settings,
              price_alerts: e.target.checked
            })}
          />
          启用价格预警通知
        </label>
      </div>

      <button onClick={saveSettings}>
        保存设置
      </button>
    </div>
  )
}
```

### 2. 监控任务PushPlus配置

创建监控任务时，系统会自动使用用户设置的PushPlus token：

```javascript
// 创建监控任务
const createTask = async (taskData) => {
  const response = await api.createMonitorTask({
    name: '香港到东京航班监控',
    departure_code: 'HKG',
    destination_code: 'NRT',
    depart_date: '2025-10-15',
    return_date: '2025-10-22',
    price_threshold: 2000,
    pushplus_notification: true,  // 启用PushPlus通知
    notification_enabled: true
    // pushplus_token 会自动从用户设置中读取
  })
  
  return response
}
```

## ✅ 部署验证

### 验证清单
- [ ] Supabase连接正常
- [ ] 邮箱注册和验证流程
- [ ] Google OAuth登录功能
- [ ] 用户数据自动同步
- [ ] PushPlus设置保存和读取
- [ ] 监控任务创建和管理

### 测试场景

#### 1. 新用户注册流程
```bash
# 测试邮箱注册
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "username": "testuser",
    "confirmPassword": "password123"
  }'
```

#### 2. 用户登录验证
```bash
# 测试登录
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "password123"
  }'
```

#### 3. 认证API访问
```bash
# 使用返回的token访问保护API
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer your_supabase_token_here"
```

## 🚨 故障排除

### 常见问题及解决方案

#### 1. Supabase连接失败
**检查项目**:
- 环境变量配置正确
- 网络连接正常
- Supabase项目状态正常

#### 2. 邮件验证不工作
**检查项目**:
- Supabase邮件设置启用
- SITE_URL配置正确
- 用户邮箱地址有效

#### 3. 用户数据同步失败
**检查项目**:
- 数据库表结构正确
- RLS政策配置合适
- 服务角色密钥权限足够

## 🎉 部署完成

恭喜！你现在拥有一个现代化的、基于Supabase的认证系统：

✅ **简洁架构**: 遵循KISS原则，移除复杂的JWT处理
✅ **现代认证**: 支持邮箱验证、OAuth、魔法链接
✅ **自动同步**: Supabase Auth与业务数据无缝集成
✅ **PushPlus完整支持**: 用户设置和监控任务通知
✅ **安全可靠**: 基于成熟的Supabase认证服务

系统现在更简单、更可靠、更易维护！