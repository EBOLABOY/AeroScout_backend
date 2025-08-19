"""
FastAPI版本的通知服务
基于原有NotificationService，优化为纯异步实现
"""
import asyncio
import aiohttp
import smtplib
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger


class FastAPINotificationService:
    """FastAPI版本的通知服务"""
    
    def __init__(self):
        """初始化通知服务"""
        # PushPlus配置
        self.pushplus_url = "http://www.pushplus.plus/send"
        self.website_domain = "ticketradar.izlx.me"
        self.website_url = f"http://{self.website_domain}"
        
        # 邮件配置
        self.smtp_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("MAIL_PORT", "587"))
        self.username = os.getenv("MAIL_USERNAME", "")
        self.password = os.getenv("MAIL_PASSWORD", "")
        self.default_sender = os.getenv("MAIL_DEFAULT_SENDER", "")
        self.use_tls = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
        self.use_ssl = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
        
        logger.info("FastAPINotificationService初始化成功")

    async def send_pushplus_notification(
        self, 
        token: str, 
        title: str, 
        content: str, 
        template: str = "html", 
        topic: Optional[str] = None
    ) -> bool:
        """
        异步发送PushPlus通知
        
        Args:
            token: PushPlus令牌
            title: 通知标题
            content: 通知内容
            template: 内容模板类型，默认为html
            topic: 群组编码，不传则为个人推送
        
        Returns:
            bool: 推送是否成功
        """
        try:
            data = {
                "token": token,
                "title": title,
                "content": content,
                "template": template
            }
            
            # 如果指定了群组，添加topic参数
            if topic:
                data["topic"] = topic
                logger.info(f"使用群组推送，群组编码: {topic}")
            else:
                logger.info("使用个人推送")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.pushplus_url, json=data) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    if result.get("code") == 200:
                        if topic:
                            logger.info(f"PushPlus群组推送成功: {title} (群组: {topic})")
                        else:
                            logger.info(f"PushPlus个人推送成功: {title}")
                        return True
                    else:
                        logger.error(f"PushPlus推送失败: {result.get('msg')}")
                        return False
                        
        except Exception as e:
            logger.error(f"PushPlus推送出错: {e}")
            return False

    async def send_email_notification(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str, 
        text_content: Optional[str] = None
    ) -> bool:
        """
        异步发送邮件通知
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML内容
            text_content: 纯文本内容（可选）
        
        Returns:
            bool: 发送是否成功
        """
        try:
            # 在线程池中执行同步的邮件发送操作
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._sync_send_email,
                to_email, subject, html_content, text_content
            )
            
        except Exception as e:
            logger.error(f"异步邮件发送失败: {e}")
            return False

    def _sync_send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str, 
        text_content: Optional[str] = None
    ) -> bool:
        """
        同步版本的邮件发送，用于在线程池中执行
        """
        try:
            # 创建邮件对象
            msg = MIMEMultipart('alternative')
            msg['From'] = self.default_sender
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # 添加纯文本内容
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 连接SMTP服务器并发送邮件
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.use_tls:
                    server.starttls()
            
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"邮件发送成功: {to_email} - {subject}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False

    async def send_flight_notification(
        self, 
        user_data: Dict[str, Any], 
        flight_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送航班通知（支持多种推送方式）
        
        Args:
            user_data: 用户数据
            flight_data: 航班数据
        
        Returns:
            dict: 发送结果
        """
        results = {
            'pushplus': False,
            'email': False,
            'total_sent': 0
        }

        try:
            # 构建通知内容
            route = flight_data.get('route', '未知航线')
            flights = flight_data.get('flights', [])
            title = f"[Ticketradar] {route} - 发现 {len(flights)} 个低价机票"

            # PushPlus推送
            pushplus_token = user_data.get('pushplus_token')
            notification_enabled = user_data.get('notification_enabled', True)
            
            if pushplus_token and notification_enabled:
                # 生成HTML通知内容
                notification_content = self._generate_flight_notification_html(title, flight_data)
                
                # 发送推送
                pushplus_success = await self.send_pushplus_notification(
                    pushplus_token, title, notification_content
                )
                results['pushplus'] = pushplus_success
                if pushplus_success:
                    results['total_sent'] += 1

            # 邮件推送
            email_notifications_enabled = user_data.get('email_notifications_enabled', False)
            email_verified = user_data.get('email_verified', False)
            user_email = user_data.get('email')
            
            if email_notifications_enabled and email_verified and user_email:
                # 生成邮件内容
                subject = f"【Ticketradar】发现低价航班 - {route}"
                html_content = self._generate_flight_email_html(subject, flight_data)
                text_content = self._generate_flight_email_text(flight_data)
                
                email_success = await self.send_email_notification(
                    user_email, subject, html_content, text_content
                )
                results['email'] = email_success
                if email_success:
                    results['total_sent'] += 1

            username = user_data.get('username', 'Unknown')
            logger.info(f"用户 {username} 通知发送完成: PushPlus={results['pushplus']}, Email={results['email']}")

        except Exception as e:
            logger.error(f"发送航班通知失败: {e}")

        return results

    def _generate_flight_notification_html(self, title: str, flight_data: Dict[str, Any]) -> str:
        """生成航班通知的HTML内容"""
        flights = flight_data.get('flights', [])
        route = flight_data.get('route', '未知航线')
        departure_city = flight_data.get('departure_city', '')
        trip_type = flight_data.get('trip_type', '')
        depart_date = flight_data.get('depart_date', '')
        return_date = flight_data.get('return_date', '')
        
        # 构建航班列表HTML
        flights_html = ""
        for i, flight in enumerate(flights[:5], 1):
            price = flight.get('price', {})
            amount = price.get('amount', 0) if isinstance(price, dict) else flight.get('price', 0)
            
            flights_html += f"""
            <div style="border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0; color: #2c3e50;">航班 {i}</h4>
                <p><strong>价格:</strong> ¥{amount}</p>
                <p><strong>出发时间:</strong> {flight.get('departureTime', 'N/A')}</p>
                <p><strong>到达时间:</strong> {flight.get('arrivalTime', 'N/A')}</p>
                <p><strong>航空公司:</strong> {flight.get('airline', 'N/A')}</p>
                <p><strong>航班号:</strong> {flight.get('flightNumber', 'N/A')}</p>
                <p><strong>飞行时长:</strong> {flight.get('duration', 'N/A')}</p>
                <p><strong>中转:</strong> {flight.get('stopsText', '直飞')}</p>
            </div>
            """
        
        if len(flights) > 5:
            flights_html += f"<p><em>还有 {len(flights) - 5} 个航班未显示...</em></p>"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50; text-align: center;">{title}</h2>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin: 0 0 10px 0; color: #495057;">航线信息</h3>
                <p><strong>路线:</strong> {route}</p>
                <p><strong>出发城市:</strong> {departure_city}</p>
                <p><strong>行程类型:</strong> {trip_type}</p>
                <p><strong>出发日期:</strong> {depart_date}</p>
                {f"<p><strong>返程日期:</strong> {return_date}</p>" if return_date else ""}
            </div>
            
            <h3 style="color: #495057;">发现的低价航班</h3>
            {flights_html}
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{self.website_url}/flights" style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">查看更多航班</a>
            </div>
            
            <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="margin: 0 0 10px 0; color: #856404;">温馨提示</h4>
                <ul style="margin: 0; padding-left: 20px; color: #856404;">
                    <li>机票价格实时变动，请尽快预订</li>
                    <li>建议对比多个平台价格</li>
                    <li>注意查看退改签政策</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 12px;">
                <p>此消息由 Ticketradar 机票监控系统自动发送</p>
                <p>© 2024 Ticketradar. All rights reserved.</p>
            </div>
        </div>
        """
        
        return html_content

    def _generate_flight_email_html(self, subject: str, flight_data: Dict[str, Any]) -> str:
        """生成航班邮件的HTML内容"""
        return self._generate_flight_notification_html(subject, flight_data)

    def _generate_flight_email_text(self, flight_data: Dict[str, Any]) -> str:
        """生成航班邮件的纯文本内容"""
        flights = flight_data.get('flights', [])
        route = flight_data.get('route', '未知航线')
        
        text_content = f"""
【Ticketradar】发现低价航班 - {route}

航线信息：
路线: {route}
出发城市: {flight_data.get('departure_city', '')}
行程类型: {flight_data.get('trip_type', '')}
出发日期: {flight_data.get('depart_date', '')}
"""
        
        if flight_data.get('return_date'):
            text_content += f"返程日期: {flight_data.get('return_date')}\n"
        
        text_content += f"\n发现的低价航班（共 {len(flights)} 个）：\n\n"
        
        for i, flight in enumerate(flights[:5], 1):
            price = flight.get('price', {})
            amount = price.get('amount', 0) if isinstance(price, dict) else flight.get('price', 0)
            
            text_content += f"""
{i}. 价格: ¥{amount}
   出发: {flight.get('departureTime', 'N/A')}
   到达: {flight.get('arrivalTime', 'N/A')}
   航班: {flight.get('airline', 'N/A')} {flight.get('flightNumber', 'N/A')}
   时长: {flight.get('duration', 'N/A')}
   中转: {flight.get('stopsText', '直飞')}

"""
        
        if len(flights) > 5:
            text_content += f"还有 {len(flights) - 5} 个航班未显示...\n\n"
        
        text_content += f"""
查看更多航班: {self.website_url}/flights

温馨提示：
- 机票价格实时变动，请尽快预订
- 建议对比多个平台价格
- 注意查看退改签政策

感谢您使用 Ticketradar 机票监控服务！

此邮件由系统自动发送，请勿回复
© 2024 Ticketradar. All rights reserved.
"""
        
        return text_content


# 全局服务实例
_notification_service: Optional[FastAPINotificationService] = None


def get_notification_service() -> FastAPINotificationService:
    """获取通知服务实例（单例模式）"""
    global _notification_service
    if _notification_service is None:
        _notification_service = FastAPINotificationService()
    return _notification_service
