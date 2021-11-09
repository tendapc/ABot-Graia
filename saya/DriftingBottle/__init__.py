import time
import httpx
import asyncio
import numpy as np

from io import BytesIO
from pathlib import Path
from pyzbar import pyzbar
from PIL import Image as IMG
from graia.saya import Saya, Channel
from graia.ariadne.model import Group, Member
from graia.broadcast.interrupt.waiter import Waiter
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.event.message import GroupMessage
from graia.broadcast.interrupt import InterruptControl
from graia.ariadne.message.parser.literature import Literature
from graia.saya.builtins.broadcast.schema import ListenerSchema
from graia.ariadne.message.element import Image, Plain, At, Source
from graia.ariadne.message.parser.twilight import Twilight, Sparkle
from graia.ariadne.message.parser.pattern import RegexMatch, FullMatch

from database.db import reduce_gold
from util.text2image import create_image
from util.control import Permission, Interval
from util.TextModeration import text_moderation
from util.ImageModeration import image_moderation
from util.sendMessage import safeSendGroupMessage
from config import yaml_data, group_data, user_black_list, save_config

from .db import throw_bottle, get_bottle, clear_bottle, count_bottle, delete_bottle, get_bottle_by_id

saya = Saya.current()
channel = Channel.current()
bcc = saya.broadcast
inc = InterruptControl(bcc)

IMAGE_PATH = Path(__file__).parent.joinpath('image')
IMAGE_PATH.mkdir(exist_ok=True)


class BottleSparkle(Sparkle):
    header = RegexMatch(r'^(扔|丢)(漂流瓶|瓶子)')
    arg_pic1 = FullMatch("-p", optional=True)
    anythings1 = RegexMatch(r'.*?', optional=True)
    arg_pic2 = FullMatch("-p", optional=True)


@ channel.use(ListenerSchema(listening_events=[GroupMessage],
                             inline_dispatchers=[Twilight(BottleSparkle)],
                             decorators=[Permission.require(), Interval.require(300)]))
async def throw_bottle_handler(group: Group, member: Member, source: Source, speaker: Sparkle):

    if yaml_data['Saya']['DriftingBottle']['Disabled']:
        return
    elif 'DriftingBottle' in group_data[str(group.id)]['DisabledFunc']:
        return

    @Waiter.create_using_function([GroupMessage])
    async def image_waiter(waiter1_group: Group, waiter1_member: Member, waiter1_message: MessageChain):
        if waiter1_group.id == group.id and waiter1_member.id == member.id:
            if waiter1_message.has(Image):
                return waiter1_message.getFirst(Image).url
            else:
                return False

    speaker: BottleSparkle = speaker
    saying = speaker.anythings1
    arg_matched = speaker.arg_pic1.matched or speaker.arg_pic2.matched
    text = None
    image_name = None
    image_url = None

    if saying.matched:
        message_chain = saying.result
        if message_chain.has(Plain):
            text = MessageChain.create(message_chain.get(Plain)).merge(True).asDisplay().strip()
            if text:
                for i in ["magnet:", "http"]:
                    if i in text:
                        return await safeSendGroupMessage(group, MessageChain.create("您？"), quote=source)
                moderation = await text_moderation(text)
                if moderation["Suggestion"] != "Pass":
                    return await safeSendGroupMessage(group, MessageChain.create("你的漂流瓶内包含违规内容，请检查后重新丢漂流瓶！"), quote=source)
            elif text_len := len(text) > 400:
                return await safeSendGroupMessage(group, MessageChain.create(f"你的漂流瓶内容过长（{text_len} / 400）！"), quote=source)

        if message_chain.has(Image):
            if arg_matched:
                return await safeSendGroupMessage(group, MessageChain.create("使用手动发图参数后不可附带图片"), quote=source)
            elif len(message_chain.get(Image)) > 1:
                return await safeSendGroupMessage(group, MessageChain.create("丢漂流瓶只能携带一张图片哦！"), quote=source)
            else:
                image_url = message_chain.getFirst(Image).url

    if arg_matched:
        await safeSendGroupMessage(group, MessageChain.create("请在 30 秒内发送你要附带的图片"), quote=source)
        try:
            image_url = await asyncio.wait_for(inc.wait(image_waiter), 30)
            if image_url:
                await safeSendGroupMessage(group, MessageChain.create("图片已接收，请稍等"), quote=source)
            else:
                return await safeSendGroupMessage(group, MessageChain.create("你发送的不是“一张”图片，请重试"), quote=source)
        except asyncio.TimeoutError:
            return await safeSendGroupMessage(group, MessageChain.create("图片等待超时"), quote=source)

    if image_url:
        moderation = await image_moderation(image_url)
        if moderation["Suggestion"] != "Pass":
            return await safeSendGroupMessage(group, MessageChain.create("你的漂流瓶包含违规内容，请检查后重新丢漂流瓶！"))
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url)
            image_type = resp.headers['Content-Type']
            image = resp.content
            if qrdecode(image):
                if member.id in user_black_list:
                    pass
                else:
                    user_black_list.append(member.id)
                    save_config()
                return await safeSendGroupMessage(group, MessageChain.create("漂流瓶不能携带二维码哦！你已被拉黑"))
        image_name = str(time.time()) + "." + image_type.split("/")[1]
        IMAGE_PATH.joinpath(image_name).write_bytes(image)

    if text or image_name:
        if await reduce_gold(str(member.id), 8):
            bottle = throw_bottle(member, text, image_name)
            in_bottle_text = "一段文字" if text else ""
            in_bottle_image = "一张图片" if image_name else ""
            in_bottle_and = "和" if in_bottle_text and in_bottle_image else ""
            in_bottle = in_bottle_text + in_bottle_and + in_bottle_image
            await safeSendGroupMessage(group, MessageChain.create([
                At(member.id), Plain(f" 成功购买漂流瓶并丢出！\n瓶子里有{in_bottle}\n瓶子编号为：{bottle}")
            ]), quote=source)
        else:
            await safeSendGroupMessage(group, MessageChain.create("你的游戏币不足，无法丢漂流瓶！"), quote=source)
    else:
        return await safeSendGroupMessage(group, MessageChain.create("丢漂流瓶请加上漂流瓶的内容！"), quote=source)


@ channel.use(ListenerSchema(listening_events=[GroupMessage],
                             inline_dispatchers=[Twilight(Sparkle([RegexMatch(r"^(捡|打?捞)(漂流瓶|瓶子)$")]))],
                             decorators=[Permission.require(), Interval.require(30)]))
async def pick_bottle_handler(group: Group):

    if yaml_data['Saya']['DriftingBottle']['Disabled']:
        return
    elif 'DriftingBottle' in group_data[str(group.id)]['DisabledFunc']:
        return

    bottle = get_bottle()

    if bottle is None:
        return await safeSendGroupMessage(group, MessageChain.create("没有漂流瓶可以捡哦！"))
    else:
        times = bottle['fishing_times']
        times_msg = "本漂流瓶已经被捞了" + str(times) + "次" if times > 0 else "本漂流瓶还没有被捞到过"
        msg = [Plain(f"你捡到了一个漂流瓶！\n瓶子编号为：{bottle['id']}\n{times_msg}\n"
                     #  f"漂流瓶来自 {bottle['group']} 群的 {bottle['member']}\n"
                     "漂流瓶内容为：\n")]
        if bottle['text'] is not None:
            image = await create_image(bottle['text'])
            msg.append(Image(data_bytes=image))
        if bottle['image'] is not None:
            msg.append(Image(path=IMAGE_PATH.joinpath(bottle['image'])))
        await safeSendGroupMessage(group, MessageChain.create(msg))


@ channel.use(ListenerSchema(listening_events=[GroupMessage],
                             inline_dispatchers=[Literature("清空漂流瓶")],
                             decorators=[Permission.require(Permission.MASTER), Interval.require()]))
async def clear_bottle_handler(group: Group):

    clear_bottle()
    await safeSendGroupMessage(group, MessageChain.create("漂流瓶已经清空！"))


@ channel.use(ListenerSchema(listening_events=[GroupMessage],
                             inline_dispatchers=[Literature("漂流瓶")],
                             decorators=[Permission.require(), Interval.require()]))
async def drifting_bottle_handler(group: Group):

    if yaml_data['Saya']['DriftingBottle']['Disabled']:
        return
    elif 'DriftingBottle' in group_data[str(group.id)]['DisabledFunc']:
        return

    count = count_bottle()
    msg = f"目前有 {count} 个漂流瓶在漂流" if count > 0 else "目前没有漂流瓶在漂流"
    msg += "\n漂流瓶可以使用“捞漂流瓶”命令捞到，也可以使用“丢漂流瓶”命令丢出”"

    await safeSendGroupMessage(group, MessageChain.create([Plain(msg)]))


@ channel.use(ListenerSchema(listening_events=[GroupMessage],
                             inline_dispatchers=[Literature("删漂流瓶")],
                             decorators=[Permission.require(Permission.MASTER)]))
async def delete_bottle_handler(group: Group, message: MessageChain):

    saying = message.asDisplay().split(" ", 1)

    if len(saying) == 1:
        return await safeSendGroupMessage(group, MessageChain.create("请输入要删除的漂流瓶编号！"))

    bottle_id = int(saying[1])
    bottle = get_bottle_by_id(bottle_id)
    if not bottle:
        return await safeSendGroupMessage(group, MessageChain.create("没有这个漂流瓶！"))

    delete_bottle(bottle_id)
    await safeSendGroupMessage(group, MessageChain.create("漂流瓶已经删除！"))


@ channel.use(ListenerSchema(listening_events=[GroupMessage],
                             inline_dispatchers=[Literature("查漂流瓶")],
                             decorators=[Permission.require(Permission.MASTER)]))
async def search_bottle_handler(group: Group, message: MessageChain):

    saying = message.asDisplay().split(" ", 1)

    if len(saying) == 1:
        return await safeSendGroupMessage(group, MessageChain.create("请输入要查找的漂流瓶编号！"))

    bottle_id = int(saying[1])
    bottle = get_bottle_by_id(bottle_id)
    if not bottle:
        return await safeSendGroupMessage(group, MessageChain.create("没有这个漂流瓶！"))

    bottle = bottle[0]
    msg = [Plain(f"漂流瓶编号为：{bottle.id}\n"
                 f"漂流瓶来自 {bottle.group} 群的 {bottle.member}\n")]
    if bottle.text is not None:
        image = await create_image(bottle.text)
        msg.append(Image(data_bytes=image))
    if bottle.image is not None:
        msg.append(Image(path=IMAGE_PATH.joinpath(bottle.image)))
    await safeSendGroupMessage(group, MessageChain.create(msg))


def qrdecode(img):
    image = IMG.open(BytesIO(img))
    image_array = np.array(image)
    image_data = pyzbar.decode(image_array)
    return len(image_data)
