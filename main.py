import nextcord
from nextcord.ext import commands
import sqlite3
import time
import matplotlib.pyplot as plt
import os
import datetime

intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)
token = ""
conn = sqlite3.connect('base.db')
cursor = conn.cursor()
utctime = datetime.datetime.strftime(datetime.datetime.now(datetime.timezone.utc),'%c')

@bot.event
async def on_ready():
    userlist = []
    for guild in bot.guilds:
        for member in guild.members:
            userlist.append(member)
    
    cursor.execute("CREATE TABLE IF NOT EXISTS users_online_stats(id INT, username TEXT, lastActive INT, online INT, idle INT, dnd INT, offline INT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS users_voice_stats(id INT, username TEXT, server_id INT, lastJoined INT, voice_time INT)")
    for user in userlist:
        check = cursor.execute("SELECT * FROM users_online_stats WHERE id = ?", (user.id,))
        if check.fetchone() is None:
            cursor.execute('INSERT INTO users_online_stats VALUES(?,?,?,?,?,?,?)', (user.id, user.name,round(time.time()),0,0,0,0))
    conn.commit()
    print(f'\n\nLogged in as {bot.user} (ID: {bot.user.id})')
    print('------\n\n')


def getvoicevalue(value):
    minutes = value / 60
    hours = minutes / 60
    if value < 60:
        value = str(round(value)) + 's'
    elif round(minutes) < 60:
        value = str(round(minutes)) + 'm'
    else:
        value = str(round(hours, 1)) + 'h'
    return value

def getvalue(values,arg):
    timings = []
    total = 0
    for v in values:
        total = total + v
    for value in values:
        minutes = value / 60
        hours = minutes / 60
        percent = value / total * 100
        if value < 60:
            value = str(round(value)) + f's ({round(percent,1)}%)'
            timings.append(value)
        elif round(minutes) < 60:
            value = str(round(minutes)) + f'm ({round(percent,1)}%)'
            timings.append(value)
        else:
            value = str(round(hours, 1)) + f'h ({round(percent,1)}%)'
            timings.append(value)
    return timings[arg]




@bot.event
async def on_presence_update(before,after):
    cursor.execute('SELECT lastActive FROM users_online_stats WHERE id = ?',(before.id,))
    lastActive = cursor.fetchone()[0]
    seconds = round(time.time()) - lastActive
    if before.status != after.status:
        statuses = ['online','idle','dnd','offline']
        for status in statuses:
            if str(before.status) == status:
                cursor.execute(f'UPDATE users_online_stats SET lastActive = ?, {status} = {status} + ? WHERE id = ?', (round(time.time()),seconds, before.id))
                conn.commit()


@bot.event
async def on_voice_state_update(member,before,after):
    cursor.execute('SELECT id,server_id FROM users_voice_stats WHERE id = ? AND server_id = ?', (member.id, member.guild.id))
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users_voice_stats VALUES(?,?,?,?,?)', (member.id, member.name, after.channel.guild.id,round(time.time()), 0))
        conn.commit()
    else:
        cursor.execute('SELECT lastJoined FROM users_voice_stats WHERE id = ? AND server_id = ?', (member.id, member.guild.id))
        lastJoined = cursor.fetchone()[0]
        seconds = round(time.time()) - lastJoined
        if before.channel is not None and after.channel is None:
            cursor.execute('UPDATE users_voice_stats SET lastJoined = ?, voice_time = voice_time + ? WHERE id = ? AND server_id = ?', (0, seconds, member.id, before.channel.guild.id))
            conn.commit()
        elif before.channel is None and after.channel is not None:
            cursor.execute('UPDATE users_voice_stats SET lastJoined = ? WHERE id = ? AND server_id = ?', (round(time.time()), member.id, after.channel.guild.id))
            conn.commit()




@bot.command()
async def activity(ctx, member: nextcord.Member = None):
    if member is None:
            member = ctx.author
    cursor.execute('SELECT lastActive FROM users_online_stats WHERE id = ?', (member.id,))
    lastActive = cursor.fetchone()[0]
    seconds = round(time.time()) - lastActive
    statuses = ['online','idle','dnd','offline']
    for status in statuses:
        if str(member.status) == status:
            cursor.execute(f'UPDATE users_online_stats SET lastActive = ?, {status} = {status} + ? WHERE id = ?', (round(time.time()),seconds, member.id))
            conn.commit()
    cursor.execute('SELECT online,idle,dnd,offline FROM users_online_stats WHERE id = ?', (member.id,))
    values = cursor.fetchone()

    values_list = list(values)
    labels = ['Online', 'Idle', 'Do not disturb', 'Offline']
    colors = [('#40a460'), ('#f8a732'),('#eb444a'),('#757f8d')]
    while 0 in values_list:
        try:
            for value in values_list:
                if value == 0:
                    labels.pop(values_list.index(value))
                    colors.pop(values_list.index(value))
                    values_list.pop(values_list.index(value))
        except ValueError:
            pass
    fig, ax = plt.subplots(facecolor = '#313338')
    patches, texts, autotexts = ax.pie(values_list, labels=labels, colors=colors, autopct= '%1.1f%%')
    for text in texts:
            text.set_color('white')
    ax.axis('equal')
    plt.savefig(f'{member.id}.png')
    embed = nextcord.Embed(title = f'{member.display_name}', color = member.color)
    embed.add_field(name = 'Stats',value = f'🟢 Online: **{getvalue(values,0)}**\n🌙 Idle: **{getvalue(values,1)}**\n⛔ Do not disturb: **{getvalue(values,2)}**\n😴 Offline: **{getvalue(values,3)}**')
    embed.set_footer(text=f"Data taken from {utctime}")
    await ctx.send(embed=embed,file = nextcord.File(f'{member.id}.png'))
    os.remove(f'{member.id}.png')


@bot.command()
async def voicestats(ctx, member: nextcord.Member = None):
    if member is None:
        member = ctx.author
    cursor.execute('SELECT id, server_id FROM users_voice_stats WHERE id = ? and server_id = ?', (member.id, member.guild.id))
    if cursor.fetchone() is None:
        embed = nextcord.Embed(title = f'Voice activity statistic', color = member.color)
        embed.set_thumbnail(url = member.guild.icon)
        embed.set_author(name = member.display_name, icon_url = member.display_avatar.url)
        embed.add_field(name = '',value =f"{member.display_name} not сonnected to any voice channel\nTotal time: **0s**")
        embed.set_footer(text=f"Data taken from {utctime}")
        await ctx.send(embed=embed)
    else:
        cursor.execute('SELECT lastJoined,voice_time FROM users_voice_stats WHERE id = ? and server_id = ?', (member.id, member.guild.id))
        data = cursor.fetchone()
        lastJoined = data[0]
        voice_time = data[1]
        if member.voice is None:
            embed = nextcord.Embed(title = f'Voice activity statistic', color = member.color)
            embed.set_thumbnail(url = member.guild.icon)
            embed.set_author(name = member.display_name, icon_url = member.display_avatar.url)
            embed.add_field(name = '',value =f"{member.display_name} not сonnected to any voice channel\nTotal time: **{getvoicevalue(voice_time)}**")
            embed.set_footer(text=f"Data taken from {utctime}")
            await ctx.send(embed=embed)
        else:
            embed = nextcord.Embed(title = f'Voice activity statistic', color = member.color)
            embed.set_thumbnail(url = member.guild.icon)
            embed.set_author(name = member.display_name, icon_url = member.display_avatar.url)
            embed.add_field(name = '',value =f"{member.display_name} connected to the voice channel ***{member.voice.channel.name}***\nСurrent time in the voice channel: **{getvoicevalue(time.time() - lastJoined)}**\nTotal time: **{getvoicevalue(time.time() - lastJoined + voice_time)}**")
            embed.set_footer(text=f"Data taken from {utctime}")
            await ctx.send(embed=embed)

bot.run(token)
