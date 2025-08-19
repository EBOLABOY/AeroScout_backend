"""
密码重置服务
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger

from fastapi_app.services.supabase_service import get_supabase_service
from fastapi_app.services.notification_service import get_notification_service
from fastapi_app.utils.password import get_password_hash


class PasswordResetService:
    """密码重置服务"""
    
    def __init__(self):
        """初始化密码重置服务"""
        self.token_expiry_hours = 24  # token有效期24小时
        logger.info("密码重置服务初始化完成")
    
    def _generate_reset_token(self) -> tuple[str, str]:
        """
        生成重置token
        
        Returns:
            tuple: (原始token, token哈希)
        """
        # 生成32字节的随机token
        token = secrets.token_urlsafe(32)
        # 生成token的哈希值用于数据库存储
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash
    
    def _verify_token(self, token: str, token_hash: str) -> bool:
        """
        验证token
        
        Args:
            token: 原始token
            token_hash: 数据库中存储的token哈希
            
        Returns:
            bool: 验证是否成功
        """
        computed_hash = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(computed_hash, token_hash)
    
    async def create_reset_token(self, email: str) -> Dict[str, Any]:
        """
        创建密码重置token
        
        Args:
            email: 用户邮箱
            
        Returns:
            dict: 操作结果
        """
        try:
            db_service = await get_supabase_service()
            
            # 检查用户是否存在
            user_data = await db_service.get_user_by_email(email)
            if not user_data:
                # 为了安全，不透露用户是否存在
                logger.warning(f"尝试重置不存在用户的密码: {email}")
                return {
                    "success": True,
                    "message": "如果该邮箱已注册，您将收到重置密码的邮件"
                }
            
            # 生成重置token
            token, token_hash = self._generate_reset_token()
            expires_at = datetime.utcnow() + timedelta(hours=self.token_expiry_hours)
            
            # 保存token到数据库
            token_data = {
                "user_id": user_data["id"],
                "token": token,
                "token_hash": token_hash,
                "expires_at": expires_at.isoformat(),
                "is_used": False
            }
            
            # 使用Supabase服务直接插入
            result = await db_service.create_password_reset_token(token_data)
            
            if not result.data:
                logger.error("保存重置token失败")
                return {
                    "success": False,
                    "message": "创建重置token失败"
                }
            
            # 发送重置邮件
            await self._send_reset_email(user_data, token)
            
            logger.info(f"密码重置token创建成功: {email}")
            return {
                "success": True,
                "message": "如果该邮箱已注册，您将收到重置密码的邮件"
            }
            
        except Exception as e:
            logger.error(f"创建重置token失败: {e}")
            return {
                "success": False,
                "message": "服务异常，请稍后重试"
            }
    
    async def reset_password(self, token: str, new_password: str) -> Dict[str, Any]:
        """
        使用token重置密码
        
        Args:
            token: 重置token
            new_password: 新密码
            
        Returns:
            dict: 操作结果
        """
        try:
            db_service = await get_supabase_service()
            
            # 查找有效的token
            token_data = await db_service.get_password_reset_token(token)
            
            if not token_data:
                logger.warning(f"无效的重置token: {token[:10]}...")
                return {
                    "success": False,
                    "message": "重置链接无效或已过期"
                }
            
            # 检查token是否过期
            expires_at = datetime.fromisoformat(token_data["expires_at"].replace('Z', '+00:00'))
            if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
                logger.warning(f"重置token已过期: {token[:10]}...")
                return {
                    "success": False,
                    "message": "重置链接已过期，请重新申请"
                }
            
            # 验证token哈希
            if not self._verify_token(token, token_data["token_hash"]):
                logger.warning(f"Token哈希验证失败: {token[:10]}...")
                return {
                    "success": False,
                    "message": "重置链接无效"
                }
            
            # 更新用户密码
            new_password_hash = get_password_hash(new_password)
            user_updated = await db_service.update_user(token_data["user_id"], {"password_hash": new_password_hash})
            
            if not user_updated:
                logger.error("更新用户密码失败")
                return {
                    "success": False,
                    "message": "密码重置失败"
                }
            
            # 标记token为已使用
            await db_service.mark_token_as_used(token_data["id"])
            
            # 使所有该用户的其他重置token失效
            await db_service.invalidate_user_tokens(token_data["user_id"])
            
            logger.info(f"密码重置成功: user_id={token_data['user_id']}")
            return {
                "success": True,
                "message": "密码重置成功"
            }
            
        except Exception as e:
            logger.error(f"重置密码失败: {e}")
            return {
                "success": False,
                "message": "服务异常，请稍后重试"
            }
    
    async def _send_reset_email(self, user_data: Dict[str, Any], token: str) -> bool:
        """
        发送重置密码邮件
        
        Args:
            user_data: 用户数据
            token: 重置token
            
        Returns:
            bool: 发送是否成功
        """
        try:
            notification_service = get_notification_service()
            
            # 构建重置链接
            reset_url = f"https://ticketradar.izlx.de/reset-password?token={token}"
            
            # 邮件主题
            subject = "【Ticketradar】密码重置请求"
            
            # HTML邮件内容
            html_content = self._generate_reset_email_html(user_data, reset_url)
            
            # 纯文本内容
            text_content = self._generate_reset_email_text(user_data, reset_url)
            
            # 发送邮件
            success = await notification_service.send_email_notification(
                user_data["email"], subject, html_content, text_content
            )
            
            if success:
                logger.info(f"重置密码邮件发送成功: {user_data['email']}")
            else:
                logger.error(f"重置密码邮件发送失败: {user_data['email']}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送重置密码邮件失败: {e}")
            return False
    
    def _generate_reset_email_html(self, user_data: Dict[str, Any], reset_url: str) -> str:
        """生成重置密码邮件的HTML内容"""
        username = user_data.get("username", "用户")
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #2c3e50; margin: 0;">Ticketradar</h1>
                <p style="color: #7f8c8d; margin: 5px 0;">机票监控系统</p>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px; border-left: 4px solid #3498db;">
                <h2 style="color: #2c3e50; margin-top: 0;">密码重置请求</h2>
                
                <p style="color: #34495e; line-height: 1.6;">
                    您好，{username}！
                </p>
                
                <p style="color: #34495e; line-height: 1.6;">
                    我们收到了您的密码重置请求。请点击下面的按钮来重置您的密码：
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #3498db; color: white; padding: 12px 30px; 
                              text-decoration: none; border-radius: 5px; font-weight: bold;
                              display: inline-block;">
                        重置密码
                    </a>
                </div>
                
                <p style="color: #7f8c8d; font-size: 14px; line-height: 1.6;">
                    如果按钮无法点击，请复制以下链接到浏览器地址栏：<br>
                    <a href="{reset_url}" style="color: #3498db; word-break: break-all;">{reset_url}</a>
                </p>
                
                <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; 
                            border-radius: 5px; margin: 20px 0;">
                    <p style="color: #856404; margin: 0; font-size: 14px;">
                        <strong>安全提示：</strong><br>
                        • 此链接将在24小时后失效<br>
                        • 如果您没有申请密码重置，请忽略此邮件<br>
                        • 请勿将此链接分享给他人
                    </p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; 
                        border-top: 1px solid #dee2e6; color: #6c757d; font-size: 12px;">
                <p>此邮件由 Ticketradar 系统自动发送，请勿回复</p>
                <p>© 2024 Ticketradar. All rights reserved.</p>
            </div>
        </div>
        """
        
        return html_content
    
    def _generate_reset_email_text(self, user_data: Dict[str, Any], reset_url: str) -> str:
        """生成重置密码邮件的纯文本内容"""
        username = user_data.get("username", "用户")
        
        text_content = f"""
【Ticketradar】密码重置请求

您好，{username}！

我们收到了您的密码重置请求。请访问以下链接来重置您的密码：

{reset_url}

安全提示：
• 此链接将在24小时后失效
• 如果您没有申请密码重置，请忽略此邮件
• 请勿将此链接分享给他人

此邮件由 Ticketradar 系统自动发送，请勿回复。

© 2024 Ticketradar. All rights reserved.
        """
        
        return text_content


# 全局服务实例
_password_reset_service = None


async def get_password_reset_service() -> PasswordResetService:
    """获取密码重置服务实例"""
    global _password_reset_service
    if _password_reset_service is None:
        _password_reset_service = PasswordResetService()
    return _password_reset_service
