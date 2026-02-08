import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import config
from src.services.ai_classifier import classify_channel
from src.services.channel_service import ChannelService
from src.services.metrics_service import increment_metric
from src.utils import escape_markdown

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


PENDING_PER_PAGE = 5


@router.message(Command("pending"))
async def cmd_pending(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    await _show_pending_page(message, page=0)


async def _show_pending_page(target: Message | CallbackQuery, page: int) -> None:
    """显示待审核频道的指定页"""
    if page < 0:
        page = 0
    try:
        channels, total = await ChannelService.get_pending_channels_paginated(
            page=page, per_page=PENDING_PER_PAGE
        )
    except Exception as exc:
        logger.error("Failed to load pending channels: %s", exc)
        if isinstance(target, CallbackQuery):
            await target.answer("❌ 获取待审核列表失败", show_alert=True)
        else:
            await target.answer("❌ 获取待审核列表失败")
        return

    if total == 0:
        text = "📭 暂无待审核的频道"
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text)
            await target.answer()
        else:
            await target.answer(text)
        return

    total_pages = (total + PENDING_PER_PAGE - 1) // PENDING_PER_PAGE
    if page >= total_pages:
        page = total_pages - 1
        channels, total = await ChannelService.get_pending_channels_paginated(
            page=page, per_page=PENDING_PER_PAGE
        )
    # MarkdownV2 下动态字段必须转义，避免解析错误。
    lines = [f"📋 *待审核频道* \\(第 {page + 1}/{total_pages} 页，共 {total} 条\\)\n"]

    for ch in channels:
        title = escape_markdown(ch['title'])
        link = (
            f"@{escape_markdown(ch['username'])}"
            if ch['username']
            else "无链接"
        )
        lines.append(f"• *{title}* \\- {link} \\({ch['member_count']}人\\)")

    # 构建键盘
    kb = InlineKeyboardBuilder()
    for ch in channels:
        kb.button(text=f"✅ {ch['id']}", callback_data=f"approve:{ch['id']}")
        kb.button(text=f"❌ {ch['id']}", callback_data=f"reject:{ch['id']}")
    kb.adjust(2)

    # 添加分页按钮
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("⬅️ 上一页", f"pending_page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(("➡️ 下一页", f"pending_page:{page + 1}"))

    if nav_buttons:
        for text, data in nav_buttons:
            kb.button(text=text, callback_data=data)
        kb.adjust(2, len(nav_buttons))

    text = "\n".join(lines)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="MarkdownV2")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb.as_markup(), parse_mode="MarkdownV2")


@router.callback_query(lambda c: c.data and c.data.startswith("approve:"))
async def cb_approve(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("无权限", show_alert=True)
        return

    try:
        channel_id = int(callback.data.split(":")[1])
        channel = await ChannelService.get_channel_by_id(channel_id)

        if not channel:
            await callback.answer("频道不存在", show_alert=True)
            return

        status = channel.get("status")
        if status and status != "pending":
            await callback.answer("频道已处理", show_alert=True)
            return

        category = await classify_channel(channel["title"])
        updated = await ChannelService.approve_channel(
            channel_id, callback.from_user.id, category
        )
        if not updated:
            await callback.answer("频道已处理", show_alert=True)
            return
        logger.info(
            "Channel approved: id=%s title=%s by=%s category=%s",
            channel_id,
            channel["title"],
            callback.from_user.id,
            category,
        )
        await increment_metric("admin_approve_total")

        await callback.message.edit_text(
            f"✅ 已通过: {escape_markdown(channel['title'])}\n分类: {escape_markdown(category)}",
            parse_mode="MarkdownV2",
        )
        await callback.answer("审核通过")
    except Exception as e:
        logger.error(f"Approve error: {e}")
        await callback.answer("操作失败", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("reject:"))
async def cb_reject(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("无权限", show_alert=True)
        return

    try:
        channel_id = int(callback.data.split(":")[1])
        channel = await ChannelService.get_channel_by_id(channel_id)

        if not channel:
            await callback.answer("频道不存在", show_alert=True)
            return

        status = channel.get("status")
        if status and status != "pending":
            await callback.answer("频道已处理", show_alert=True)
            return

        updated = await ChannelService.reject_channel(channel_id)
        if not updated:
            await callback.answer("频道已处理", show_alert=True)
            return
        logger.info(
            "Channel rejected: id=%s title=%s by=%s",
            channel_id,
            channel["title"],
            callback.from_user.id,
        )
        await increment_metric("admin_reject_total")
        await callback.message.edit_text(
            f"❌ 已拒绝: {escape_markdown(channel['title'])}",
            parse_mode="MarkdownV2",
        )
        await callback.answer("已拒绝")
    except Exception as e:
        logger.error(f"Reject error: {e}")
        await callback.answer("操作失败", show_alert=True)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    try:
        pending_count = await ChannelService.get_pending_count()
        approved_count = await ChannelService.get_approved_count()
    except Exception as exc:
        logger.error("Failed to load stats: %s", exc)
        await message.answer("❌ 获取统计信息失败，请稍后重试")
        return

    await message.answer(
        f"📊 *系统统计*\n\n✅ 已通过: {approved_count}\n⏳ 待审核: {pending_count}",
        parse_mode="MarkdownV2",
    )


@router.callback_query(lambda c: c.data and c.data.startswith("pending_page:"))
async def cb_pending_page(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("无权限", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[1])
        await _show_pending_page(callback, page=page)
    except Exception as e:
        logger.error(f"Pending page error: {e}")
        await callback.answer("操作失败", show_alert=True)
