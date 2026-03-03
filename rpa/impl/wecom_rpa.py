import asyncio
from typing import Dict, Any
from loguru import logger
from ..modules.base_rpa import BaseRPA


class WeComRPA(BaseRPA):
    """
    企业微信自动化填报主逻辑。
    """

    RPA_NAME = "wecom"
    LOGIN_QRCODE_SELECTOR = ".wwLogin_panel_middle .wwLogin_qrcode"

    async def _handle_login(self) -> bool:
        """处理登录逻辑，检测二维码并等待扫码"""
        if not self.form_url:
            logger.error(
                f"[{self.RPA_NAME}] 未配置 form_url，请在 config.yaml 中检查。"
            )
            return False

        logger.info(f"[{self.RPA_NAME}] 正在打开目标链接: {self.form_url}")
        await self.page.goto(self.form_url)

        # 1. 检查网络错误并重试
        if not await self._check_and_handle_page_error(max_retries=self.max_retry):
            logger.warning(
                f"[{self.RPA_NAME}] 页面多次刷新无效，尝试新开一个标签页重新访问..."
            )
            if getattr(self, "page", None):
                try:
                    await self.page.close()
                except Exception:
                    pass
            self.page = await self.browser_context.new_page()
            await self.page.goto(self.form_url)
            await self._human_sleep(3)

            if not await self._check_and_handle_page_error(max_retries=self.max_retry):
                raise Exception("新开标签页后仍然网络请求错误，无法恢复程序")

        # 给页面一定的初始加载和重定向时间
        await self._human_sleep(3)

        while True:
            try:
                # 2. 循环检测中也进行一次网络错误静默检查
                if not await self._check_and_handle_page_error(
                    max_retries=1, silent=True
                ):
                    return False

                # 检查是否存在登录二维码 (Step 3)
                qr_code = await self.page.query_selector(self.LOGIN_QRCODE_SELECTOR)
                if qr_code:
                    logger.warning(
                        f"[{self.RPA_NAME}] 检测到登录二维码，请手动扫描二维码登录..."
                    )
                    # 轮询检测二维码是否消失或页面是否跳转
                    while await self.page.query_selector(self.LOGIN_QRCODE_SELECTOR):
                        await asyncio.sleep(2)
                    logger.info(f"[{self.RPA_NAME}] 二维码已消失，登录成功或已跳过。")

                # 检查是否已进入表单内容页
                current_url = self.page.url
                if (
                    "doc.weixin.qq.com/journal" in current_url
                    or "doc.weixin.qq.com/forms/j/" in current_url
                ) and "/error" not in current_url:
                    # 通过页面关键元素确认
                    hover_btn = await self.page.query_selector(
                        ".HoverBtn_btn__2ansF, .question-main"
                    )
                    if hover_btn:
                        logger.info(
                            f"[{self.RPA_NAME}] 登录检查通过 (URL: {current_url})，且关键填报元素已就绪。"
                        )
                        return True
                    else:
                        logger.debug(
                            f"[{self.RPA_NAME}] URL 匹配成功但尚未发现填报元素，继续等待..."
                        )
                        await asyncio.sleep(2)
                else:
                    logger.debug(
                        f"[{self.RPA_NAME}] 当前 URL: {current_url} (可能在扫码中或处于错误页)，等待页面到达目标区域..."
                    )
                    await asyncio.sleep(5)
            except Exception as e:
                if "Execution context was destroyed" in str(e):
                    logger.debug(
                        f"[{self.RPA_NAME}] 检测到页面跳转导致的上下文切换，正在重试检测..."
                    )
                    await asyncio.sleep(2)
                else:
                    err_msg = str(e)
                    if (
                        "Target page, context or browser has been closed" in err_msg
                        or "Browser closed" in err_msg
                    ):
                        # 识别到浏览器手动关闭，直接向上抛出异常，让 BaseRPA 处理优雅退出
                        raise e
                    logger.error(f"[{self.RPA_NAME}] 登录检测发生异常: {e}")
                    await asyncio.sleep(5)

    async def fill_form(self, report_data: Any):
        """执行表单填充逻辑"""
        items = report_data if isinstance(report_data, list) else [report_data]
        if not items:
            logger.warning(f"[{self.RPA_NAME}] 无可用填报数据。")
            return

        # 1. 触发模态框 (Step 5)
        await self._trigger_modal()

        # 2. 循环处理数据记录 (Step 6)
        for index, item in enumerate(items):
            logger.info(
                f"[{self.RPA_NAME}] 正在处理第 {index + 1}/{len(items)} 条日报数据..."
            )

            # 等待模态框内容加载
            modal_selector = ".dui-modal-content"
            await self.page.wait_for_selector(modal_selector, timeout=10000)

            # 填充字段
            await self._fill_modal_input("工作内容", item.get("content", ""))
            await self._fill_modal_input("工作成果", item.get("result", ""))
            await self._fill_modal_time("开始时间", item.get("start_time", ""))
            await self._fill_modal_time("结束时间", item.get("end_time", ""))
            await self._fill_modal_choice("重要性与紧急度", item.get("priority", ""))
            await self._fill_modal_dropdown("工作类型", item.get("type", ""))
            await self._fill_modal_dropdown("业务中心", item.get("project", ""))

            # 循环控制逻辑
            if index < len(items) - 1:
                # 如果不是最后一条，点击“新增一行” (Step 6 循环控制)
                logger.debug(f"[{self.RPA_NAME}] 点击“新增一行”...")
                await self._click_add_line()
                await self._human_sleep(1)  # 点击后等待滚动
            else:
                # 如果是最后一条，跳出循环
                logger.info(f"[{self.RPA_NAME}] 所有条目已填充完毕。")

        # 3. 点击“完成” (Step 7)
        await self._click_finish()
        await self._human_sleep(2)

        # 4. 清理可能存在的缺陷行（空行）
        await self._cleanup_defect_rows()

        # 5. 检查配置决定是否点击“提交” (Step 8)
        auto_submit = (
            self.config.get("platforms", {})
            .get(self.RPA_NAME, {})
            .get("rpa", {})
            .get("auto_submit", False)
        )
        if auto_submit:
            logger.info(f"[{self.RPA_NAME}] 检测到 auto_submit=true，执行最终提交...")
            await self._click_submit()
        else:
            logger.info(f"[{self.RPA_NAME}] auto_submit=false，请手动核对后点击提交。")

        logger.info(f"[{self.RPA_NAME}] 所有数据填充任务执行完毕。")

    async def _trigger_modal(self):
        """触发填报模态框的特定交互流程 (Step 5)"""
        # 1. 悬停按钮
        hover_btn = ".HoverBtn_btn__2ansF"
        await self.page.wait_for_selector(hover_btn)
        await self.page.hover(hover_btn)
        await self._human_sleep(1)

        # 2. 点击日期激活
        date_trigger = ".question-main .form-date-main"
        await self.page.click(date_trigger)
        await self._human_sleep(0.5)

        # 3. 点击“今天”
        today_btn = ".rc-calendar-footer-btn"
        await self.page.wait_for_selector(today_btn)
        await self.page.click(today_btn)
        await self._human_sleep(1)

        # 4. 点击表格第二行打开模态框
        table_row = ".table-area-wrapper tbody .table-body-line-wrapper:nth-child(2)"
        await self.page.wait_for_selector(table_row)
        await self.page.click(table_row)
        await self._human_sleep(1)

    async def _fill_modal_input(self, title: str, value: str):
        """填充模态框内的文本/多行输入框"""
        if not value:
            return
        base_selector = f'.dui-modal-content .question:has(.question-main-content > .question-title > div:first-child span:has-text("{title}")) .question-content'
        wrapper_selector = f"{base_selector} .Input-module_inputWrapper__pgeTK"

        logger.debug(f'[{self.RPA_NAME}] 正在尝试填充 "{title}": {value}')

        try:
            # 等待容器并点击聚焦
            wrapper = await self.page.wait_for_selector(wrapper_selector)
            await wrapper.click()
            await self._human_sleep(0.5)

            # 优先查找真正的 textarea 或 input 子元素
            input_element = await wrapper.query_selector("textarea, input")
            if input_element:
                await input_element.fill(value)
            else:
                # 兜底：如果找不到子元素，可能该 span 自身通过 contenteditable 或键盘事件处理，尝试全选并模拟输入
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
                await self.page.keyboard.type(value)

            logger.debug(f'[{self.RPA_NAME}] "{title}" 填充成功')
        except Exception as e:
            logger.error(f'[{self.RPA_NAME}] "{title}" 填充失败: {e}')
            raise

    async def _fill_modal_time(self, title: str, time_str: str):
        """处理开始/结束时间选择 (双列滚动)"""
        if not time_str or ":" not in time_str:
            return
        hour, minute = time_str.split(":")

        # 1. 点击时间触发器
        trigger_selector = f'.dui-modal-content .question:has(.question-main-content > .question-title > div:first-child span:has-text("{title}")) .question-content .rc-time-picker .form-time-main'
        logger.debug(f'[{self.RPA_NAME}] 正在设置 "{title}": {time_str}')
        await self.page.click(trigger_selector)

        # 2. 等待面板并选择
        panel_selector = ".rc-time-picker-panel"
        await self.page.wait_for_selector(panel_selector)

        # 小时列：通常是第一列
        await self.page.click(
            f'.rc-time-picker-panel-select:nth-child(1) li:has-text("{hour}")'
        )
        await self._human_sleep(0.3)
        # 分钟列：通常是第二列
        await self.page.click(
            f'.rc-time-picker-panel-select:nth-child(2) li:has-text("{minute}")'
        )
        await self._human_sleep(0.3)

        # 3. 关闭时间选择面板：点击模态框标题触发失焦，并配合 Escape 键
        logger.debug(f"[{self.RPA_NAME}] 正在尝试收起时间选择面板...")
        try:
            # 如果能找到标题则点击标题
            await self.page.click(
                ".dui-modal-title, .dui-modal-header", timeout=2000, force=True
            )
        except:
            # 否则点击左上角避开发生交互的区域
            await self.page.mouse.click(10, 10)

        await self.page.keyboard.press("Escape")
        await self._human_sleep(0.5)

    async def _fill_modal_choice(self, title: str, choice: str):
        """处理单选组"""
        if not choice:
            return
        # Step 6.5: 重要性与紧急度
        container_selector = f'.dui-modal-content .question:has(.question-main-content > .question-title > div:first-child span:has-text("{title}")) .question-content .form-choice-new'
        logger.debug(f'[{self.RPA_NAME}] 正在尝试选择 "{title}": {choice}')

        # 确保在视口内
        container = await self.page.wait_for_selector(container_selector)
        await container.scroll_into_view_if_needed()

        # 在内部查找文本完全匹配 choice 的单选按钮并点击
        option_selector = f'{container_selector} label:has-text("{choice}"), {container_selector} .choice-fill-module_radioItem_title__D0gAG:has-text("{choice}")'

        try:
            target_option = await self.page.wait_for_selector(option_selector)
            await target_option.click()
            await self._human_sleep(0.5)
        except Exception as e:
            logger.error(f'[{self.RPA_NAME}] 选择单选项 "{choice}" 失败: {e}')
            raise

    async def _fill_modal_dropdown(self, title: str, option_text: str):
        """处理下拉菜单"""
        if not option_text:
            return
        # Step 6.6 & 6.7: 下拉框触发器
        wrapper_selector = f'.dui-modal-content .question:has(.question-main-content > .question-title > div:first-child span:has-text("{title}")) .question-content .dropdown-choice-fill-module_dropdownWrapper__-jSfm span.form-input-affix-wrapper'
        logger.debug(f'[{self.RPA_NAME}] 正在选择下拉项 "{title}": {option_text}')

        # 1. 展开
        try:
            wrapper = await self.page.wait_for_selector(wrapper_selector, timeout=5000)
            await wrapper.click()
            await self._human_sleep(0.8)
        except Exception as e:
            logger.error(f'[{self.RPA_NAME}] 下拉框 "{title}" 展开失败: {e}')
            raise

        # 2. 等待菜单可见
        menu_selector = ".dropdown-choice-fill-module_dropdownMenuList__soKw0"
        try:
            await self.page.wait_for_selector(menu_selector, timeout=5000)
        except Exception as e:
            logger.warning(
                f"[{self.RPA_NAME}] 未能通过类名检测到菜单，尝试直接点击选项..."
            )

        # 3. 定位并点击选项
        item_selector = f'.dropdown-choice-fill-module_dropdownMenuItem__EIDOY:has(.dropdown-choice-fill-module_dropdownMenuItem_text__Nom3Y:has-text("{option_text}"))'

        try:
            target_item = await self.page.wait_for_selector(item_selector, timeout=5000)
            await target_item.click()
            await self._human_sleep(0.5)
            logger.debug(f'[{self.RPA_NAME}] "{title}" -> "{option_text}" 选择成功')
        except Exception as e:
            logger.error(
                f'[{self.RPA_NAME}] 下拉项 "{option_text}" 定位或点击失败: {e}'
            )
            # 尝试兜底操作：直接按文本点击
            try:
                await self.page.click(f'text="{option_text}"')
                await self._human_sleep(0.5)
            except:
                raise e

    async def _click_add_line(self):
        """点击“新增一行”按钮 (Step 6 循环控制)"""
        add_line_btn = '.dui-modal-content .form-subform-fill-footer-pc_action span:has-text("新增一行")'
        try:
            btn = await self.page.wait_for_selector(add_line_btn)
            await btn.click()
        except Exception as e:
            logger.error(f"[{self.RPA_NAME}] 点击“新增一行”失败: {e}")
            raise

    async def _click_finish(self):
        """点击“完成”按钮 (Step 7)"""
        finish_btn = '.dui-modal-content .form-subform-fill-panel-pc_submit button .dui-button-container:has-text("完成")'
        try:
            btn = await self.page.wait_for_selector(finish_btn)
            await btn.click()
        except Exception as e:
            logger.error(f"[{self.RPA_NAME}] 点击“完成”失败: {e}")
            raise

    async def _click_submit(self):
        """点击“提交”按钮 (Step 8)"""
        submit_btn = (
            '.dui-modal-content .FillFooter_footer__X07QG button:has-text("提交")'
        )
        try:
            btn = await self.page.wait_for_selector(submit_btn)
            await btn.click()
            logger.info(f"[{self.RPA_NAME}] 提交按钮已点击。")
        except Exception as e:
            logger.error(f"[{self.RPA_NAME}] 点击“提交”失败: {e}")
            raise

    async def _check_and_handle_page_error(
        self, max_retries: int = None, silent: bool = False
    ) -> bool:
        """
        检查页面是否出现网络请求错误，并尝试刷新
        :param max_retries: 最大重试次数，如果不传则使用配置值
        :param silent: 是否静默模式
        :return: True 表示页面正常或已恢复，False 表示持续性网络错误
        """
        if max_retries is None:
            max_retries = self.max_retry

        retry_count = 0
        # 修正关键字以适配用户提供的真实 HTML 结构
        error_text = "网络请求错误，请再试一次"

        while retry_count < max_retries:
            # 尝试定位具体的错误标题类名或包含该文本的元素
            try:
                # 修复选择器语法错误：Playwright 的 query_selector 不支持混合混合逗号这种写法
                # 我们直接使用最稳健的文本匹配
                error_msg = await self.page.query_selector(f'text="{error_text}"')
                if error_msg:
                    retry_count += 1
                    logger.warning(
                        f"[{self.RPA_NAME}] 检测到页面报错 '{error_text}' (第 {retry_count} 次)。\n"
                        f"提示：这可能是因为账号被风控或链接失效。如果多次刷新无效，请尝试手动在浏览器中打开链接确认，或更新 config.yaml 中的 form_url。"
                    )
                    await self.page.goto(self.form_url)
                    # 重新访问后给予更长的加载缓冲，避免连续报错
                    await self._human_sleep(5)
                else:
                    return True  # 没检测到错误，或者错误已消失
            except Exception as e:
                if "Execution context was destroyed" in str(e):
                    return True

                err_msg = str(e)
                if (
                    "Target page, context or browser has been closed" in err_msg
                    or "Browser closed" in err_msg
                ):
                    # 识别到浏览器手动关闭，抛出异常以跳出可能的重试循环
                    raise e

                raise

        if not silent:
            logger.error(
                f"[{self.RPA_NAME}] 页面加载持续失败 (多次重试仍然报错: {error_text})。\n"
                f"警告：请确认您的网络状态。如果网络正常，极大可能是该链接已被企业微信风控限制，建议在 config.yaml 中更新最新的 form_url 后重试。"
            )
        return False

    async def _cleanup_defect_rows(self):
        """
        检查并删除表单中的缺陷行（包含 empty-placeholder 的行）。
        """
        logger.info(f"[{self.RPA_NAME}] 正在检查并清理表单缺陷行...")

        # 缺陷行的特征：主表格区域内的 tr 包含 .empty-placeholder
        defect_row_selector = (
            ".table-area-wrapper tr.table-body-line-wrapper:has(.empty-placeholder)"
        )
        # 鼠标移入表格行显示的工具tool
        trashbin_selector = ".hover-tool-bar .hover-tool-bar-trashbin-wrapper"

        try:
            # 循环检测并删除，直到没有缺陷行为止
            while True:
                # 重新获取缺陷行，因为删除后 DOM 会变
                rows = await self.page.query_selector_all(defect_row_selector)
                if not rows:
                    logger.info(f"[{self.RPA_NAME}] 未发现缺陷行，清理完毕。")
                    break

                logger.warning(
                    f"[{self.RPA_NAME}] 发现 {len(rows)} 条缺陷行，准备清理..."
                )

                # 倒序处理以减少 DOM 变动影响（虽然循环中每次重新获取更保险，但在单次循环内倒序更优雅）
                for i in range(len(rows) - 1, -1, -1):
                    row = rows[i]
                    # 确保可见
                    await row.scroll_into_view_if_needed()

                    # 1. 移入缺陷行
                    await row.hover()
                    logger.debug(
                        f"[{self.RPA_NAME}] 已悬停在第 {i+1} 条缺陷行，等待 toolbar 出现..."
                    )

                    # 2. 等待 1s
                    await asyncio.sleep(1)

                    # 3. 点击删除图标
                    trashbin = await self.page.query_selector(trashbin_selector)
                    if trashbin:
                        await trashbin.click()
                        logger.debug(
                            f"[{self.RPA_NAME}] 已点击删除图标，等待确认弹窗..."
                        )
                        await self._human_sleep(1)

                        # 4. 处理二次确认弹窗
                        confirm_modal_selector = ".dui-modal.form-confirm"
                        confirm_btn_selector = (
                            f"{confirm_modal_selector} .dui-modal-footer-ok"
                        )
                        try:
                            # 等待并点击“确认”按钮
                            confirm_btn = await self.page.wait_for_selector(
                                confirm_btn_selector, timeout=3000
                            )
                            if confirm_btn:
                                await confirm_btn.click()
                                logger.info(
                                    f"[{self.RPA_NAME}] 已点击“确认”删除缺陷行。"
                                )
                                await self._human_sleep(1)  # 等待删除动画和 DOM 更新
                        except Exception as e:
                            logger.warning(
                                f"[{self.RPA_NAME}] 未检测到删除确认弹窗或点击确认失败: {e}"
                            )
                    else:
                        logger.warning(
                            f"[{self.RPA_NAME}] 未能找到删除图标 (.hover-tool-bar-trashbin-wrapper)，跳过该行。"
                        )

                # 再次执行 while 循环检测，确保完全清理干净 (特别是分页或动态加载的情况)
                await self._human_sleep(0.5)

        except Exception as e:
            logger.error(f"[{self.RPA_NAME}] 清理缺陷行时发生异常: {e}")
            # 清理失败不应阻断整体流程，记录错误即可
