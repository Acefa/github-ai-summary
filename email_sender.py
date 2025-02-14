import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict
import logging
import socket
import os
from typing import List
import time

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, config: dict):
        self.config = config
        self.timeout = 30  # 统一超时时间
        self.max_retries = 3  # 最大重试次数

    def send_email(self, attachment_path: str):
        msg = MIMEMultipart()
        msg['From'] = self.config['sender_email']
        msg['To'] = self._format_recipients()
        msg['Subject'] = self.config['subject']

        try:
            # 在发送邮件前添加日志验证
            logger.info("📤 准备发送邮件 | 收件人: %s", self.config['recipients'])
            logger.debug("当前工作目录: %s", os.getcwd())
            logger.debug("附件路径存在: %s", os.path.exists(attachment_path))

            # 添加正文
            body = MIMEText("附件是GitHub项目分析报告，请查收。", 'plain', 'utf-8')
            msg.attach(body)

            # 添加附件
            self._attach_file(msg, attachment_path)

            # 创建SSL上下文
            context = self._create_ssl_context()

            # 建立连接并发送
            self._send_with_retry(msg, context, attachment_path)
            
        except Exception as e:
            logger.error(f"邮件发送失败：{str(e)}")
            raise

    def _format_recipients(self) -> str:
        """格式化收件人列表"""
        return ", ".join(self.config['recipients'])

    def _attach_file(self, msg: MIMEMultipart, path: str):
        """添加附件"""
        file_name = os.path.basename(path)
        with open(path, "rb") as f:
            attach = MIMEApplication(f.read(), Name=file_name)
            attach.add_header('Content-Disposition', 'attachment', filename=file_name)
            msg.attach(attach)

    def _create_ssl_context(self) -> ssl.SSLContext:
        """创建SSL上下文"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _send_with_retry(self, msg: MIMEMultipart, context: ssl.SSLContext, attachment_path: str):
        """带重试机制的发送方法"""
        for attempt in range(self.max_retries):
            try:
                # 手动管理连接关闭
                server = smtplib.SMTP_SSL(
                    self.config['smtp_server'],
                    self.config['smtp_port'],
                    timeout=self.timeout,
                    context=context
                )
                try:
                    server.set_debuglevel(2)
                    self._handle_server_communication(server, msg)
                    logger.info("🎉 邮件发送成功 | 状态: 已送达")
                    return
                finally:
                    server.quit()  # 显式关闭连接
            except (smtplib.SMTPServerDisconnected, socket.timeout) as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"连接中断，第{attempt+1}次重试（{wait_time}秒后）...")
                    time.sleep(wait_time)
                    continue
                raise

    def _handle_server_communication(self, server: smtplib.SMTP_SSL, msg: MIMEMultipart):
        """处理SMTP协议通信"""
        logger.info("服务器响应: %s", server.ehlo())
        logger.info("正在登录...")
        try:
            server.login(self.config['sender_email'], self.config['sender_password'])
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"邮箱认证失败 | 错误代码: {e.smtp_code} | 消息: {e.smtp_error.decode('utf-8')}")
            raise
        logger.info("正在发送邮件...")
        server.send_message(msg) 