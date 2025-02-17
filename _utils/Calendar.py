import discord
from firebase_admin import db as fb_db

import sys
import os
project_rehash_path = r"C:\\Users\\megmc\\OneDrive\Documents\\Repos\\ProjectRehash"
if project_rehash_path not in sys.path:
    sys.path.append(project_rehash_path)
from ProjectRehash.api._utils.Calendar import Calendar as PRCalendar

class Calendar(PRCalendar):

    def __init__(self, db: fb_db, client: discord.Client):
        self.client = client
        self.db = db
        self.date = db.collection('documents').document('calendar').get().to_dict()['date']

    db = None
    channel_id = 1304878028081332294
    months = [None, "First Light", "Ambo's Leave", "Nix", "Lilla's Favour", "Coenta's Grace", "Xin's Fields", "Nox", "Mar's End"]
    date = (13, 4, 3, 6) # day, month, year, era
    client = None # set in __init__

    def advance_date(self, days: int = 0, months: int = 0, years: int = 0, eras: int = 0):
        while days >= 20:
            days -= 20
            months += 20
        while months >= 8:
            months -= 8
            years += 1
        self.date = (
            self.date[0] + days,
            self.date[1] + months,
            self.date[2] + years,
            self.date[3] + eras
        )
        self.push()

    def update_date(self, day: int|None = None, month: int|None = None, year: int|None = None, era: int|None = None):
        self.date = (
            day if day else self.date[0],
            month if month else self.date[1], 
            year if year else self.date[2], 
            era if era else self.date[3]
        )
        self.push()

    async def post_date(self):
        channel = self.client.get_channel(self.channel_id)
        await channel.edit(name = self.get_date_string())

    def push(self):
        doc = self.db.collection('documents').document('calendar')
        d = self.__dict__.copy()
        d.pop("client")
        d.pop("db")
        doc.set(d)
        return doc
