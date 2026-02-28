import time
import random
import json
from .ai_manager import ai_manager
from loguru import logger
from request.hooks.use_request import use_request
from prompts import prompts
from .base_ai import BaseAIProvider
from common.config import config
from api import apis, api_register


class AIFactory(BaseAIProvider):
    """
    AI 供应商工厂兼基类
    """

    def __init__(self, name: str = None, model_cfg: dict = None):
        """
        初始化 AI 提供商。
        """
        # 存储所有注册后的接口请求对象
        self.api_reqs = {}
        self.AI_PROVIDER_NAME = name or getattr(self, "AI_PROVIDER_NAME", "unknown")
        self.model_cfg = model_cfg

        if name and name != "unknown" and model_cfg:
            self._init_dynamic_provider(name, model_cfg)

    def _init_dynamic_provider(self, name: str, model_cfg: dict):
        """
        并发注册所有配置的 API 接口
        """
        base_url = model_cfg.get("base_url")
        random_id = random.randint(1000, 9999)
        api_name_prefix = (
            f"ai_dynamic_provider__{name}_{int(time.time() * 1000)}_{random_id}"
        )

        # 准备接口定义
        api_definitions = {
            "platform": name,
            "baseURL": base_url,
        }

        # 默认接口
        custom_apis = model_cfg.get("apis", {})
        if "chat_completions" not in custom_apis:
            api_definitions["chat_completions"] = "POST /chat/completions"

        # 合并配置中的所有接口
        api_definitions.update(custom_apis)

        # 注册整个 API 模块
        api_register.define(api_name_prefix, api_definitions)
        logger.info(f"[AIFactory] 已注册动态模型接口组: {api_name_prefix}")

        # 获取注册后的 API 对象并初始化所有请求
        api_group_obj = getattr(apis, api_name_prefix)
        for api_key in api_definitions.keys():
            if api_key in ["platform", "baseURL"]:
                continue
            # 动态绑定请求方法
            req_handler = getattr(api_group_obj, api_key, None)
            if req_handler:
                self.api_reqs[api_key] = use_request(req_handler)

    def _get_prompt_attr(self, obj, attr, default):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    async def summarize(self, text: str, extra_prompts: dict = None) -> str:
        """
        AI 总结实现，支持动态负载模板和严格配置校验
        """
        chat_req = self.api_reqs.get("chat_completions")
        if not chat_req:
            return (
                f"[{self.AI_PROVIDER_NAME}] 总结失败：未找到有效接口 (chat_completions)"
            )

        # 1. 获取模型基础配置
        cfg = (
            self.model_cfg
            if self.model_cfg
            else config.get_model(self.AI_PROVIDER_NAME)
        )
        if not cfg:
            return f"[{self.AI_PROVIDER_NAME}] 总结失败：未找到该模型的配置信息"

        # 校验必填项
        if not cfg.get("base_url"):
            return f"[{self.AI_PROVIDER_NAME}] 配置错误：缺少 'base_url'"

        # 2. 准备渲染上下文
        ai_prompts = prompts.get(self.AI_PROVIDER_NAME, {})
        global_prompts = prompts.get("global", {})

        # 获取系统提示词：AI 专用 -> 全局 -> 默认
        system_prompt = self._get_prompt_attr(ai_prompts, "system", None)
        if system_prompt is None:
            system_prompt = self._get_prompt_attr(
                global_prompts, "system", "你是一个日报总结助手。"
            )

        extra_prompts = extra_prompts or {}
        extra_system = extra_prompts.get("system")
        extra_user = extra_prompts.get("user")

        # 融合系统指令
        if extra_system:
            system_prompt = f"{system_prompt}\n\n{extra_system}"

        # 获取用户提示词模板：AI 专用 -> 全局 -> 默认
        user_template = self._get_prompt_attr(ai_prompts, "user", None)
        if user_template is None:
            user_template = self._get_prompt_attr(global_prompts, "user", "")

        # 拼接用户提示词：模板 + 额外指令(如伪装) + 原始文本
        user_content = user_template or ""
        if extra_user:
            user_content = f"{user_content}\n\n{extra_user}"

        user_content = f"{user_content}\n\n{text}" if user_content else text

        # 优先从 cfg 取 model，这里不需要再手动拼接环境变量名，Config.get_model 已经处理了优先级
        model_id = cfg.get("model")
        if not model_id:
            return f"[{self.AI_PROVIDER_NAME}] 配置错误：缺少指定使用的ai模型名称"

        context = {
            "model": model_id,
            "system": system_prompt,
            "user": user_content,
        }

        # 3. 构建请求负载 (由配置驱动)
        payload_template = cfg.get("payload")
        if payload_template:
            try:
                payload = self._render_payload(payload_template, context)
            except KeyError as e:
                return f"[{self.AI_PROVIDER_NAME}] 负载渲染失败：模板中引用了未定义的变量 {str(e)}"
            except Exception as e:
                return f"[{self.AI_PROVIDER_NAME}] 负载渲染出错：{str(e)}"
        else:
            # 默认使用标准 OpenAI 格式模板
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            }

        # 4. 合并自定义参数 (API 层的额外控制，如 temperature, timeout 等)
        custom_params = cfg.get("params", {})
        if custom_params:
            process_params = custom_params.copy()
            if "timeout" in process_params:
                process_params["timeout"] = process_params["timeout"] * 60
            payload.update(process_params)

        # 5. 审计日志 (仅在存在额外增强提示词时触发，减少常规噪音)
        if extra_prompts:
            # 兼容不同 payload 结构
            audit_path = (
                payload.get("messages")
                if "messages" in payload
                else "Non-standard payload structure"
            )
            logger.debug(
                f"[AIFactory] 请求负载: {json.dumps(audit_path, ensure_ascii=False, indent=2)}"
            )

        # 6. 执行请求
        try:
            res_data = await chat_req.fetch(payload)
            final_res = self._parse_response(res_data)
            if extra_prompts:
                logger.debug(
                    f"✨ [AIFactory] 响应预览 (前200位): {final_res[:200]}..."
                )
            return final_res
        except Exception as e:
            logger.error(f"[{self.AI_PROVIDER_NAME}] 总结请求异常: {str(e)}")
            return f"错误: {str(e)}"

    def _render_payload(self, template, context):
        """
        递归渲染负载模板，替换占位符
        """
        if isinstance(template, str):
            # 将 {user} 替换为 context['user'] 等
            # 使用 .format() 但要小心嵌套的大括号（如果有其他需求的话）
            try:
                return template.format(**context)
            except KeyError:
                # 如果模板中有未知占位符，原样返回或报错？这里选择按位替换
                return template
        elif isinstance(template, dict):
            return {k: self._render_payload(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._render_payload(i, context) for i in template]
        else:
            return template

    def _parse_response(self, res_data: any) -> str:
        """
        解析响应内容，默认适配 OpenAI 风格或直接字符串
        """
        if isinstance(res_data, dict) or hasattr(res_data, "get"):
            # 兼容 OpenAI: choices[0].message.content
            content = (
                res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            # 兼容某些直接返回 content 的非标接口
            if not content and "content" in res_data:
                content = res_data["content"]
        else:
            content = str(res_data)

        if not content:
            logger.warning(f"[{self.AI_PROVIDER_NAME}] 响应解析结果为空")
            return "[]"

        # 清理常见的 Markdown 包装
        return content.replace("```json", "").replace("```", "").strip()

    @staticmethod
    def get_ai(name: str):
        """
        工厂入口：获取 AI 供应商实例。
        """
        cls = ai_manager.get_class(name)
        if cls:
            return cls()

        # 动态生成逻辑
        model_cfg = config.get_model(name)
        if model_cfg:
            # 预校验基础配置
            if not model_cfg.get("base_url"):
                logger.error(f"[AIFactory] 拒绝生产 AI '{name}'：缺少 base_url 配置")
                return None
            return AIFactory(name=name, model_cfg=model_cfg)

        return None
