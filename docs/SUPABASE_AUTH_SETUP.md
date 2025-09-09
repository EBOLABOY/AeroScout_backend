# Supabase 认证集成与配置

本指南专注于 Supabase 认证的配置与前端集成。后端的部署与 CI/CD 流程请参阅 `DEPLOYMENT.md`。

## 准备工作

- Supabase 项目（获取 Project URL、Anon Key、Service Role Key）
- 配置 Authentication → Settings：启用邮件确认与模板
- （可选）Authentication → Providers：启用 Google OAuth 并配置 Client ID/Secret

## 环境变量（后端）

在 `.env` 中配置以下关键项（详见 `.env.example`）：

- `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DATABASE_URL`（可选，CLI/迁移使用）
- `SUPABASE_JWT_SECRET`（后端被动解码 Supabase JWT）
- `AI_API_KEY`、`AI_API_URL`
- `REDIS_URL`、`SITE_URL`

## 前端：初始化 supabase-js

```js
// lib/supabase.js
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'pkce'
  }
})
```

## 前端：API 调用携带 Token

```js
// utils/api.js
import { supabase } from '../lib/supabase'

export async function apiRequest(path, options = {}) {
  const session = (await supabase.auth.getSession()).data.session
  const token = session?.access_token

  const res = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

## 注意事项

- 后端使用 `SUPABASE_JWT_SECRET` 被动验证 Token；无需自建登录接口。
- 若存在旧 JWT 逻辑，已保留向后兼容分支，但建议全面迁移至 Supabase。
- 后端部署、数据库迁移、环境配置等请参考 `DEPLOYMENT.md`。

