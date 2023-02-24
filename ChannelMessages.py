import configparser
import json
import asyncio
from datetime import date, datetime
from time import sleep
import pandas as pd
import re
from urllib.parse import urlparse
from os import listdir
import csv

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import (GetHistoryRequest)
from telethon.tl.types import (
    PeerChannel,
    Message,
    MessageMediaWebPage,
    MessageMediaPhoto
)

#CATEGORIES = []
COLUMNS = ["Date","Category", "Site Name","URL","Title","Description"]
FORBIDDEN_CHARS = [",", "'", "\"", "\\", "/", "{", "}", "[", "]", "`", "@", "#", "$", "%", "^", "*", ";", "?", "."]

async def main(config):
    global CATEGORIES
    await client.start()
    print("Client Created")
    # Ensure you're authorized
    phone = config['Telegram']['phone']
    if await client.is_user_authorized() == False:
        await client.send_code_request(phone)
        try:
            await client.sign_in(phone, input('Enter the code: '))
        except SessionPasswordNeededError:
            await client.sign_in(password=input('Password: '))

    me = await client.get_me()

    channel_url = config['Telegram']['channel']
    if channel_url.isdigit():
        entity = PeerChannel(int(channel_url))
    else:
        entity = channel_url
    my_channel = await client.get_entity(entity)

    message_id = int(config['Telegram']['message_id'])
   
    while True:
        sleep(5)
        messages = client.iter_messages(entity=my_channel,min_id=message_id,reverse=True)

        if not messages:
            break
        async for message in messages:
            if isinstance(message, Message):
                message_id = message.id
                print("Current Message ID is:", message_id)
                
                
                if message.message.lower().startswith("#") and message.reply_to is not None:
                    link_message = await client.get_messages(entity=my_channel, ids=message.reply_to.reply_to_msg_id)
                    await add_data_from_message(link_message=link_message, hashtag_message=message, channel=my_channel)

                elif message.message.lower().startswith("/"):
                    await handle_command(message.message, my_channel)

                config.set('Telegram','message_id',str(message_id))
                with open("config.ini","w") as config_file:
                    config.write(config_file)


async def handle_command(message,channel):
    print(message)
    global CATEGORIES
    global FORBIDDEN_CHARS
    command = message[1:].lower()
    if len(command.split()) == 1:
        if command in ["?","help","usage"]:
            output = """Welcome to The Inventory!\nTo add a link, share it in the group and then reply to that message with #<Category>.\nTo list valid categories use the "/list" command.\nTo add a category, use the "/add <category>" command.\nTo remove a category, use the "/rm <category>" command."""
        elif command in ["list", "ls", "show", "categories", "category"]:
            output = "Valid categories are: {}".format("\n" + "\n".join(CATEGORIES))
        else:
            output = "Unknown command: {}".format(command)
    elif len(command.split()) == 2:
        cmd, param = command.split()
        if True in [char in param for char in FORBIDDEN_CHARS]:
            output = "Don't mess with me... INVALID PARAM!"
        elif cmd in ["add"]:
            if param in CATEGORIES:
                output = "The requested category is already in The Inventory!"
            else:
                CATEGORIES.append(param)
                config.set('Telegram','categories',",".join(CATEGORIES))
                with open("config.ini","w") as config_file:
                    config.write(config_file)
                output = "Added category {} to The Inventory".format(param)
        elif cmd in ["remove", "rm", "delete", "del"]:
            if param not in CATEGORIES:
                output = "The requested category is NOT in The Inventory!"
            else:
                CATEGORIES.remove(param)
                config.set('Telegram','categories',",".join(CATEGORIES))
                with open("config.ini","w") as config_file:
                    config.write(config_file)
                output = "Removed category {} from The Inventory".format(param)
        else:
            output = "Unknown command: {}".format(command)
    else:
        output = "Unknown command: {}".format(command)

    await client.send_message(channel, output)

async def add_data_from_message(link_message, hashtag_message,channel):
    if link_message.media is not None:
        data = await extract_message_data(link_message, hashtag_message, channel)
        if data is not None:
            dump_data(data)
            await client.send_message(channel, 'Got it! Another link was added to the {} category in The Inventory!'.format(hashtag_message.message.lower()))


async def extract_message_data(link_message, hashtag_message,channel):
    global CATEGORIES
    URL_EXTRACT_PATTERN = "https?:\\/\\/(?:www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)"
    if hashtag_message.message.lower() in ["#" + category.lower() for category in CATEGORIES]:
        for category in CATEGORIES:
            if hashtag_message.message.lower() == "#" + category.lower():
                message_category = category
                break
    else:
        await client.send_message(channel, 'Unknown categury {}. Valid categories are: {}'.format(hashtag_message, "\n".join(CATEGORIES)))
        return
    data = dict.fromkeys(COLUMNS)
    data["Date"] = link_message.date.strftime('%Y-%m-%d')
    data["Category"] =  message_category

    media = link_message.media
    if isinstance(media, MessageMediaWebPage):
        data["Site Name"] = media.webpage.site_name
        data["URL"] = media.webpage.display_url
        data["Title"] = media.webpage.title
        data["Description"] = media.webpage.description
    elif isinstance(media, MessageMediaPhoto):
        urls = re.findall(URL_EXTRACT_PATTERN,link_message.message)
        data["Site Name"] = ",".join([urlparse(url).netloc for url in urls])
        data["URL"] = ",".join(urls)
        data["Title"] = link_message.message.split('\n',1)[0]
        data["Description"] = link_message.message.split('\n',1)[1].lstrip('\n')
    else:
        print("Does not support file type {}".format(type(media)))
    return data

def dump_data(data):
    global COLUMNS
    print(data)
    output_dir = "output"
    files = listdir(output_dir)
    values = ["" if value is None else value for value in data.values()]
    if len(files) == 0:
        file_name = "{}/{}.csv".format(output_dir, datetime.today().strftime('%Y-%m-%d'))
        with open(file_name, 'w', encoding="utf-8", newline='') as f:
            writer = csv.writer(f)
            writer.writerows([COLUMNS,values])
    elif len(files) == 1:
        with open("{}/{}".format(output_dir,files[0]), 'a', encoding="utf-8", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(values)
    else:
        print("Too much files in the output directory!")
        return

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read("config.ini")
    api_id = config['Telegram']['api_id']
    api_hash = config['Telegram']['api_hash']
    username = config['Telegram']['username']
    CATEGORIES = config['Telegram']['categories'].split(",")
    client = TelegramClient(username, api_id, api_hash)
    with client:
        client.loop.run_until_complete(main(config))