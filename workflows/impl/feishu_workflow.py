import json
from loguru import logger
from api import apis
from config import config
from request.hooks import use_request
from feishu_oauth_fastapi import send_auth_nudge, get_tenant_token
from providers import AIFactory
from token_store import load_all_tokens
from workflows.modules.base_workflow import BaseWorkflow


class FeishuWorkflow(BaseWorkflow):
    """
    飞书工作流实现：支持 OAuth 引导、消息占位及原位更新
    """

    WORKFLOW_NAME = "feishu"

    def __init__(self):
        self.send_api = use_request(apis.feishu_app_im.send_message)
        self.update_api = use_request(apis.feishu_app_im.update_message)

    def prepare(self) -> bool:
        """
        检查飞书授权，若无有效 Token 则发起 Nudge
        """
        tokens = load_all_tokens()
        if tokens:
            return True

        logger.info(f"[{self.WORKFLOW_NAME}] 未发现有效授权，正在发送引导卡片...")
        success, reason = send_auth_nudge()
        if not success:
            logger.error(f"[{self.WORKFLOW_NAME}] 发送引导卡片失败: {reason}")
            return False

        logger.info(f"[{self.WORKFLOW_NAME}] 已发送引导卡片，等待用户授权...")
        # 注意：这里我们只负责发起引导，外层 main.py 会负责全局的轮询等待
        return True

    def on_report_start(self, raw_report: str) -> dict:
        """
        发送“正在总结”占位卡片
        """
        if not config.FEISHU_TARGET_CHAT_ID:
            logger.warning(
                f"[{self.WORKFLOW_NAME}] 未配置 FEISHU_TARGET_CHAT_ID，跳过占位卡片发送。"
            )
            return {}

        tenant_token = get_tenant_token()
        headers = {"Authorization": f"Bearer {tenant_token}"}

        placeholder_card = {
            "header": {
                "title": {"tag": "plain_text", "content": "🤖 正在生成总结..."},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "☕ 正在为您优化汇报内容，请稍候...",
                    },
                }
            ],
        }

        try:
            res = self.send_api.fetch(
                {
                    "receive_id": config.FEISHU_TARGET_CHAT_ID,
                    "content": json.dumps(placeholder_card),
                    "msg_type": "interactive",
                    "headers": headers,
                }
            )
            # 此时 res 是已经解包后的 data 部分 (字典)
            message_id = res.get("message_id") if res else None

            if not message_id:
                logger.warning(f"[{self.WORKFLOW_NAME}] 无法获取占位卡片 message_id。")

            return {"message_id": message_id, "headers": headers}
        except Exception as e:
            logger.error(f"[{self.WORKFLOW_NAME}] 发送占位卡片失败: {e}")
            return {}

    def summarize(self, raw_report: str) -> str:
        """
        使用配置指定的模型进行总结
        """
        # 获取飞书平台配置的模型，默认为 doubao
        platform_config = config.get_platform(self.WORKFLOW_NAME)
        provider = platform_config.get("ai_model", "doubao")

        ai_instance = AIFactory.get_ai(provider)
        if not ai_instance:
            logger.error(f"[{self.WORKFLOW_NAME}] 未找到模型供应商: {provider}")
            return "总结失败: 未找到模型供应商"

        logger.info(f"[{self.WORKFLOW_NAME}] 正在调度 {provider} 模型生成总结...")
        return ai_instance.summarize(raw_report)

    def on_report_success(self, summary: str, context: dict):
        """
        更新飞书卡片为最终总结内容 (支持 JSON 结构化卡片)
        """
        message_id = context.get("message_id")
        headers = context.get("headers")

        try:
            # 尝试解析 JSON
            data = json.loads(summary)
            if not isinstance(data, list):
                # 如果不是列表，可能是单条对象或错误格式，尝试包裹
                data = [data] if isinstance(data, dict) else []

            card = self._build_daily_card(data)
        except Exception as e:
            # 解析失败，回退到纯文本卡片
            logger.warning(
                f"[{self.WORKFLOW_NAME}] JSON 解析或卡片构建失败: {e}，回退到纯文本展示"
            )
            card = {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📊 每日工作总结 (格式异常)",
                    },
                    "template": "orange",
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": summary}}
                ],
            }

        if message_id:
            try:
                self.update_api.fetch(
                    {
                        "message_id": message_id,
                        "content": json.dumps(card),
                        "headers": headers,
                    }
                )
                logger.info(
                    f"[{self.WORKFLOW_NAME}] ✅ 日报已原位更新 (ID: {message_id})"
                )
            except Exception as e:
                logger.error(f"[{self.WORKFLOW_NAME}] 更新消息失败: {e}")
        else:
            # 备选方案：直接发送新消息
            self._send_raw(card, headers)

    def _build_daily_card(self, items: list) -> dict:
        """
        构建飞书交互式卡片
        """
        if not items:
            return {
                "header": {
                    "title": {"tag": "plain_text", "content": "📊 每日工作总结"},
                    "template": "grey",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": "今日暂无工作记录"},
                    }
                ],
            }

        # 提取日期（取第一条的日期或当天）
        date_str = items[0].get("date", "今日")

        elements = []
        for item in items:
            # 优先级颜色映射
            priority = item.get("priority", "普通")
            emoji = (
                "🔴" if "紧急" in priority else ("🟡" if "重要" in priority else "🟢")
            )

            # 构建单条工作记录的 Block
            content = f"**{item.get('content', '无描述')}**"
            result = f"成果：{item.get('result', '进行中')}"
            meta_info = f"🕒 {item.get('start_time', '')}~{item.get('end_time', '')} | {emoji} {priority} | 🏷️ {item.get('type', '其他')} | 🏢 {item.get('project', '其他')}"

            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{content}\n{result}\n<font color='grey'>{meta_info}</font>",
                    },
                }
            )
            elements.append({"tag": "hr"})

        # 移除最后一条分割线
        if elements and elements[-1]["tag"] == "hr":
            elements.pop()

        return {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 每日工作总结 {date_str}",
                },
                "template": "blue",
            },
            "elements": elements,
        }

    def _send_raw(self, card, headers):
        if not config.FEISHU_TARGET_CHAT_ID:
            return
        try:
            self.send_api.fetch(
                {
                    "receive_id": config.FEISHU_TARGET_CHAT_ID,
                    "content": json.dumps(card),
                    "msg_type": "interactive",
                    "headers": headers,
                }
            )
            logger.info(f"[{self.WORKFLOW_NAME}] ✅ 日报已发送 (新消息)")
        except Exception as e:
            logger.error(f"[{self.WORKFLOW_NAME}] 发送消息失败: {e}")
