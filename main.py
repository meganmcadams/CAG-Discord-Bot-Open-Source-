# bot.py
import discord
from config import GUILD, TOKEN, CHARACTER_TAGS, GEMINI_API_KEY, BASE_TEXT
from firebase_admin import credentials, firestore, initialize_app
from _utils.Calendar import Calendar
from discord.ext.commands import has_permissions, MissingPermissions
import asyncio
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request
from fastapi import status
from firebase_admin import credentials, firestore, initialize_app
from datetime import datetime
from _utils.db import get_classes_no_level, get_character_tags
from _utils.messages import character_template
import requests
from requests import ConnectTimeout
from discord.ext import tasks
from google import genai

import sys
import os
project_rehash_path = r"C:\\Users\\megmc\\OneDrive\Documents\\Repos\\ProjectRehash"
if project_rehash_path not in sys.path:
    sys.path.append(project_rehash_path)
from ProjectRehash.api._utils.Character import Character

cred = credentials.Certificate('key.json')
fs_app = initialize_app(cred)
db = firestore.client()

intents = discord.Intents(messages=True, guilds=True, message_content=True)
client = discord.Client(intents=discord.Intents.all())
tree = discord.app_commands.CommandTree(client)

calendar = Calendar(db=db, client=client)

# from _utils.imp import imp
# imp(db)
# exit()

@tasks.loop(hours=24)
async def import_characters() -> None:
    print("Importing characters...")
    jobs = db.collection('documents').document('jobs').get().to_dict()
    last_run = datetime.fromtimestamp(jobs['import_characters'].timestamp())

    characters = db.collection('characters').get()
    for character in characters:
        c = character.to_dict()
        print("Checking {name} ({id})...".format(name=c['name_str'], id=c['id']))
        connected, data = True, {}
        try:
            resp = requests.get("https://character-service.dndbeyond.com/character/v5/character/{}".format(c['id']))
            data = resp.json()['data']
        except ConnectTimeout: # couldn't connect
            connected = False
        if not connected or data.get('errorCode'): # if didn't connect or not found
            c['import_complete'] = False
            print("Could not access {name} ({id})".format(name=c['name_str'], id=c['id']))
            continue

        if datetime.strptime(data['dateModified'], "%Y-%m-%dT%H:%M:%S.%fZ") > last_run:
            Character(db, calendar, id = c['id']).import_character(db, calendar) # import and push the character
            print("Finished importing {name} ({id})".format(name=c['name_str'], id=c['id']))
        else:
            print("Do not need to re-import {name} ({id})".format(name=c['name_str'], id=c['id']))

    # update time completed
    jobs['import_characters'] = datetime.now()
    db.collection('documents').document('jobs').set(jobs)
    print("import_characters time updated to",jobs['import_characters'])
    return

@tasks.loop(hours=24)
async def check_characters() -> None:
    print("Checking characters...")
    jobs = db.collection('documents').document('jobs').get().to_dict()
    last_run = jobs['check_characters']
    forum_id = 1271197969441362073

    characters = db.collection('characters').get()
    for character in characters:
        c = character.to_dict()

        if not c.get('last_updated'): # sanity
            c['last_updated'] = datetime.now()
            character.reference.set(c) # push
            c = character.reference.get().to_dict() # repull
            print("Updated last_updated for",c['name_str'],"to",c['last_updated'])

        if c.get('import_complete', False) and (c.get('last_updated') >= last_run or not c.get('thread_id')): # if has been updated since last ran
            print("Checking character",c['id'],"who is played by",c['user_id'])
            if not c.get('pronouns'): # if character not filled out yet
                print(c['name_str'],"is not complete, cannot update.")
                continue # skip it
            message = character_template.format(
                user_id = c['user_id'],
                pronouns = c['pronouns'],
                classes = get_classes_no_level(c),
                race = c['race'],
                lineage = c.get('lineage', ""),
                affiliations = ", ".join(c['affiliations']),
                physical_description = c['physical_description'],
                demeanor = c['demeanor'],
                img = c['img']
            )
            thread_id = c.get('thread_id')
            channel = client.get_channel(forum_id)
            if not thread_id: # need to make a new channel
                thread, message = await channel.create_thread(name = c['name_str'], content = message, applied_tags = get_character_tags(c, channel))
                c['thread_id'] = thread.starter_message.id
                character.reference.set(c)
                print("Created ",c['name_str'],sep="")
            else:
                thread = client.get_channel(thread_id)
                await thread.get_partial_message(thread_id).edit(content=message)
                await thread.edit(name = c['name_str'], applied_tags = get_character_tags(c, channel))
                print("Updated ",c['name_str'],".",sep="")
        else:
            print("Did not need to update",c['name_str'])
    print("Check characters complete!")

    # update time completed
    jobs['check_characters'] = datetime.now()
    db.collection('documents').document('jobs').set(jobs)
    print("check_characters time updated to",jobs['check_characters'])
    return

@tree.command(name="check_characters", description="Force check the characters list.", guild=discord.Object(id=GUILD))
async def _check_characters(interaction: discord.Interaction|None):
    await interaction.response.send_message("Checking characters...")
    await check_characters()
    await interaction.response.send_message("Done!")\
        
@tree.command(name="import_characters", description="Force import the characters list.", guild=discord.Object(id=GUILD))
async def _import_characters(interaction: discord.Interaction|None):
    await interaction.response.send_message("Importing characters...")
    await import_characters()
    await interaction.response.send_message("Done!")\

@tree.command(name="update_date", description="Update the in-game date.", guild=discord.Object(id=GUILD))
#@has_permissions(manage_channels=True)
async def _update_date(interaction: discord.Interaction|None, day: int|None = None, month: int|None = None, year: int|None = None, era: int|None = None):
    print("Updating date...")
    calendar.update_date(day, month, year, era)
    print("Date updated. Posting date...")
    await calendar.post_date()
    print("Date posted.")
    await asyncio.sleep(.2)
    if interaction: # not a test
        await interaction.response.send_message("Date updated to {date}".format(date = calendar.get_date_string()))\

@tree.command(name="ask_about_lore", description="Ask any lore question about the Caelus Universe.", guild=discord.Object(id=GUILD))
async def _chatbot_ask(interaction: discord.Interaction|None, question: str):
    await interaction.response.defer()  # Acknowledge the interaction immediately
    await asyncio.sleep(1)

    retries = 0
    while retries < 10:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-2.0-flash", contents=BASE_TEXT + question
            )
            await interaction.followup.send(response.text)
            return
        except Exception as e:
            await asyncio.sleep(1) # wait a second
            continue # try again
    await interaction.followup.send("Something went REALLY wrong. I tried 10 times and STILL failed. <@656991495806779427>, HELP ME! The error was: " + str(e))
    return

@_update_date.error
@_check_characters.error
@_import_characters.error
@_chatbot_ask.error
async def _error_handling(ctx, error):
    if isinstance(error, MissingPermissions):
        await asyncio.sleep(.2)
        text = "Sorry {}, you do not have permissions to do that!".format(ctx.message.author)
        await client.send_message(ctx.message.channel, text)

@client.event
async def on_ready():
    guild = discord.utils.get(client.guilds, id=GUILD)
    print(
        f'{client.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )
    await tree.sync(guild=discord.Object(id=GUILD))
    #import_characters.start()
    #check_characters.start()
    print("Jobs started successfully.")

# @client.event
# async def on_member_join(member):
#     await member.create_dm()
#     await member.dm_channel.send(
#         f'Hi {member.name}, welcome to my Discord server!'
#     )

@client.event
async def on_message(message):
    if message.author == client.user:
      return

    if "ussy" in message.content:
        print(dir(message.author))
        response = "ok " + message.author.display_name + "ussy"
        await message.channel.send(response)

client.run(TOKEN)