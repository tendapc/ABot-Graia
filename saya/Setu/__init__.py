from graia.saya import Saya, Channel
from graia.ariadne.app import Ariadne
from graia.ariadne.model import Group
from graia.ariadne.message.element import Image
from graia.ariadne.message.chain import MessageChain
from graia.ariadne.event.message import GroupMessage
from graia.ariadne.message.parser.literature import Literature
from graia.saya.builtins.broadcast.schema import ListenerSchema

from config import yaml_data, group_data
from util.sendMessage import safeSendGroupMessage
from util.control import Permission, Interval, Rest

from .setu import create_setu

saya = Saya.current()
channel = Channel.current()


@channel.use(
    ListenerSchema(
        listening_events=[GroupMessage],
        inline_dispatchers=[Literature("色图")],
        decorators=[Rest.rest_control(), Permission.require(), Interval.require()],
    )
)
async def main(app: Ariadne, group: Group):

    if yaml_data["Saya"]["Setu"]["Disabled"]:
        return
    elif "Setu" in group_data[str(group.id)]["DisabledFunc"]:
        return

    await safeSendGroupMessage(
        group, MessageChain.create([Image(data_bytes=await create_setu())])
    )
