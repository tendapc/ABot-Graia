import httpx

from graia.saya import Saya, Channel
from graia.ariadne.model import Group
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.message.element import Image, Plain
from graia.saya.builtins.broadcast.schema import ListenerSchema
from graia.ariadne.message.parser.twilight import Twilight, Sparkle
from graia.ariadne.message.parser.pattern import FullMatch, RegexMatch

from config import yaml_data, group_data
from util.sendMessage import safeSendGroupMessage
from util.control import Permission, Interval, Rest

saya = Saya.current()
channel = Channel.current()


class PixivSparkle(Sparkle):
    tag1 = RegexMatch(r".+", optional=True)
    header = FullMatch("涩图")
    tag2 = RegexMatch(r".+", optional=True)


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Twilight(PixivSparkle)],
        decorators=[Rest.rest_control(), Permission.require(), Interval.require()],
    )
)
async def main(group: Group, sparkle: Sparkle):

    if (
        yaml_data["Saya"]["Pixiv"]["Disabled"]
        and group.id != yaml_data["Basic"]["Permission"]["DebugGroup"]
    ):
        return
    elif "Pixiv" in group_data[str(group.id)]["DisabledFunc"]:
        return

    saying: PixivSparkle = sparkle

    if saying.tag1.matched or saying.tag2.matched:
        tag = (
            saying.tag1.result.getFirst(Plain).text
            if saying.tag1.matched
            else saying.tag2.result.getFirst(Plain).text
        )
        async with httpx.AsyncClient() as client:
            r = await client.get(f"http://a60.one:404/get/tags/{tag}?num=1")
            res = r.json()
        if res.get("code", False) == 200:
            pic = res["data"]["pic_list"][0]
            await safeSendGroupMessage(
                group,
                MessageChain.create(
                    [
                        Plain(f"ID：{pic['pic']}"),
                        Plain(f"\nNAME：{pic['name']}"),
                        Image(url=pic["url"]),
                    ]
                ),
            )
        elif res.get("code", False) == 404:
            await safeSendGroupMessage(
                group, MessageChain.create([Plain("未找到相应tag的色图")])
            )
        else:
            await safeSendGroupMessage(
                group, MessageChain.create([Plain("慢一点慢一点，别冲辣！")])
            )
    else:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://a60.one:404/")
            res = r.json()
        if res.get("code", False) == 200:
            await safeSendGroupMessage(
                group,
                MessageChain.create(
                    [
                        Plain(f"ID：{res['pic']}"),
                        Plain(f"\nNAME：{res['name']}"),
                        Image(url=res["url"]),
                    ]
                ),
            )
        else:
            await safeSendGroupMessage(
                group, MessageChain.create([Plain("慢一点慢一点，别冲辣！")])
            )
