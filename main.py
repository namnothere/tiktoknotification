import asyncio
from TiktokApi import *
from databaseHandle import Database
from tiktokHandle import TikTokHandle
import discord
from discord.ext import commands, tasks
from discord.ext.commands.errors import CommandNotFound
from discord import app_commands
import os
from dotenv import load_dotenv
from Streamable import StreamableHandle
from pystreamable.exceptions import StreamableApiServerException
load_dotenv()



intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

token = os.environ.get("TOKEN")
DBclient = os.environ.get("CLIENT")
embedURL = os.environ.get("embedURL")
username = None
userid = None
channelID = None
Streamable = bool("True")
ch = int(os.environ.get("ArchiveCH"))
msg = ""

db = Database()

        
@bot.event
async def on_ready():
    await bot.wait_until_ready()
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

    global username, channelID, msg

    username = db.getUsername()
    channelID = db.getChannel()
    loop = db.getloop()
    uploadOption()

    if username != "" and channelID != "" and loop == True:
        newVideos.start()

    msg = db.getMessage()
    if (msg == ""):
        msg = "New TikTok video: "

    else:
        print("Username: " + username)
        print("Channel ID: " + str(channelID))



@bot.command()
async def add(ctx, left: int, right: int):
    """Adds two numbers together."""
    await ctx.send(left + right)

@bot.hybrid_command(description = "Set user to follow.", aliases = ['su', 'adduser'])
@commands.has_permissions(administrator = True)
@app_commands.describe(user="Username")
async def setuser(ctx, user:str):
    global username
    username = user
    db.setUsername(username)
    await ctx.send(f"Added {user}", ephemeral=False) # Change ephemeral to True if you want only the author to see that message


@bot.hybrid_command(description = "Set channel to send notification.", aliases=['sc', 'addchannel'])
@commands.has_permissions(administrator = True)
@app_commands.describe(channelid="Channel")
async def setchannel(ctx, channelid = None):
    global channelID
    channelID = channelid
    if (channelID == None):
        channelID = ctx.channel.id
    elif ctx.message.channel_mentions:
        channelID = ctx.message.channel_mentions[0].id
    else:
        await ctx.send("Please enter a valid channel", ephemeral=False)
        return

    db.setChannel(channelID)

    channel = bot.get_channel(int(channelID))
    await ctx.send(f"Set channel to {channel.mention}", ephemeral=True)

@bot.hybrid_command(description = "Set default message.", aliases = ['sm'])
@commands.has_permissions(administrator = True)
@app_commands.describe(message="Message")
async def setmessage(ctx, message:str):
    global msg
    msg = message
    db.setMessage(message)
    await ctx.send(f"Added `{message}` as content when new video is posted", ephemeral=False) # Change ephemeral to True if you want only the author to see that message

@bot.hybrid_command(description = "View current stalked user.", aliases=['ul', 'users'])
async def userlist(ctx):
    users = db.getUsername()
    await ctx.send(f"Stalked user: {users}", ephemeral=False)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        await ctx.send("Command not found", ephemeral=False)
    raise error

# https://www.tiktok.com/@hakosbaelz_holoen/video/7100729819205340418

@bot.hybrid_command(description = "Start stalking.", aliases=['s'])
@commands.has_permissions(administrator = True)
async def start(ctx):
    db.setloop(True)
    if newVideos.is_running():
        await ctx.send("Already running", ephemeral=True)
    else:
        newVideos.start()
        await ctx.send("Started", ephemeral=True)


@bot.hybrid_command(description = "Stop stalking.", aliases=['st'])
@commands.has_permissions(administrator = True)
async def stop(ctx):
    db.setloop(False)
    #cancel loop
    if newVideos.is_running():
        newVideos.stop()
        await ctx.send("Stopped", ephemeral=True)
    else:
        await ctx.send("Loop is not running", ephemeral=True)



@tasks.loop(seconds = 60 * 2)
async def newVideos():
    global msg, ch, username, userid, Streamable

    tiktok = TikTokHandle(db, username, userid=userid)
    c = tiktok.sortVideos()
    if (c):
        for video in tiktok.newVideos:
            id = video['itemInfos']['id']
            v = db.getVideo(id)
            createTime = v["createTime"]

            url = None

            if Streamable == False:
                url = await DiscordfileHandle(id)
            else:
                url = await uploadToStreamable(id)
            
            if url == False:
                originurl = f'https://www.tiktok.com/@{username}/video/{id}'
                await bot.get_channel(int(channelID)).send(f"{msg} at <t:{createTime}:f> \n {originurl}")
                db.updateVideoURL(id, url)
                return
            db.updateVideoURL(id, url)
            url = f"{embedURL}/{id}"
            await asyncio.sleep(2)
            await bot.get_channel(int(channelID)).send(f"{msg} at <t:{createTime}:f> \n {url}")

def uploadOption():
    """
    Are are two services option to upload to.
    1. Streamable
    2. Discord

    Streamable requires you to pass username and password
    Default will upload to discord (will get error if file exceed 8MB)

    """
    global Streamable
    if os.environ.get("UPLOAD_OPTION") == "DISCORD":
        Streamable = False
    elif os.environ.get("UPLOAD_OPTION") == "STREAMABLE":
        Streamable = True
    else:
        Streamable = False
    return Streamable
    
async def DiscordfileHandle(file):
    """
    File handle for uploading to discord.
    Eiter return file url or None if file is too large
    """
    size = os.path.getsize(f"{file}.mp4") 
    if size > 1048576 * 7.9:
        print("File is too large")
        return False
    else:
        url = await uploadToDiscord(file)
        return url

async def uploadToStreamable(file):
    username = os.environ.get("STREAMABLE_USERNAME")
    password = os.environ.get("STREAMABLE_PASSWORD")
    try:
        api = StreamableHandle(username, password)
        video = api.upload(f"{file}.mp4", file)
        url = await api.getVideoUrl(video)
        return url
    except StreamableApiServerException:
        print("Invalid credentials")
        return False
    except Exception as e:
        print("uploadToStreamable - [ERROR]:", e)
        return False

async def uploadToDiscord(file):
    """
    Uploads file to discord.
    return message attachment object
    """
    try:
        m = await bot.get_channel(ch).send(file = discord.File(f"{file}.mp4"))
        return m.attachments[0].url
    except Exception as e:
        print("uploadToDiscord - [ERROR]:", e)
        return False

@bot.command()
@commands.is_owner()
async def upload(ctx, id):
    try:
        await ctx.send(file = discord.File(f"{id}.mp4"))
    except Exception as e:
        await ctx.send("Error: " + str(e))

@bot.command()
@commands.is_owner()
async def sync(ctx):
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("Synced!", ephemeral=True)

bot.run(os.environ.get("TOKEN"))
