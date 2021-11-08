from graia.saya import Saya, Channel
from graia.ariadne.app import Ariadne
from graia.ariadne.model import Group
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Source, Plain
from graia.saya.builtins.broadcast.schema import ListenerSchema
from graia.ariadne.message.parser.literature import Literature

from config import yaml_data, group_data
from util.TextModeration import text_moderation
from util.sendMessage import safeSendGroupMessage
from util.control import Permission, Interval, Rest

from .beast import encode, decode


saya = Saya.current()
channel = Channel.current()


@channel.use(ListenerSchema(listening_events=[GroupMessage],
                            inline_dispatchers=[Literature("嗷")],
                            decorators=[Rest.rest_control(), Permission.require(), Interval.require()]))
async def main_encode(app: Ariadne, group: Group, message: MessageChain, source: Source):

    if yaml_data['Saya']['Beast']['Disabled']:
        return
    elif 'Beast' in group_data[str(group.id)]['DisabledFunc']:
        return

    saying = message.asDisplay().split(" ", 1)
    if len(saying) == 2:
        try:
            msg = encode(saying[1])
            if (len(msg)) < 500:
                await safeSendGroupMessage(group, MessageChain.create([Plain(msg)]), quote=source.id)
            else:
                await safeSendGroupMessage(group, MessageChain.create([Plain("文字过长")]), quote=source.id)
        except Exception:
            await safeSendGroupMessage(group, MessageChain.create([Plain("明文错误``")]), quote=source.id)


@channel.use(ListenerSchema(listening_events=[GroupMessage],
                            inline_dispatchers=[Literature("呜")],
                            decorators=[Rest.rest_control(), Permission.require(), Interval.require()]))
async def main_decode(app: Ariadne, group: Group, message: MessageChain, source: Source):

    if yaml_data['Saya']['Beast']['Disabled']:
        return
    elif 'Beast' in group_data[str(group.id)]['DisabledFunc']:
        return

    saying = message.asDisplay().split(" ", 1)
    if len(saying) == 2:
        try:
            msg = decode(saying[1])
            res = await text_moderation(msg)
            if res['Suggestion'] == "Pass":
                await safeSendGroupMessage(group, MessageChain.create([Plain(msg)]), quote=source.id)
        except Exception:
            await safeSendGroupMessage(group, MessageChain.create([Plain("密文错误``")]), quote=source.id)
