import json
from firebase_admin import db
from datetime import datetime

def imp(db: db):
    with open('import.json', 'r') as f:
        data = json.load(f)
        print(data)

        for row in data:
            if not row.get('name'):
                continue
            ref = db.collection('campaigns').document(str(row['id']))
            print("Looking at",row['id'],"| name is",row['name'])
            if row['players']:
                row['players'] = row['players'].split(', ')
            else:
                row['players'] = []
            if row['characters']:
                row['characters'] = row['characters'].split(', ')
            else:
                row['characters'] = []
            row['last_updated'] = datetime.now()
            row['max_players'] = int(row['max_players'])
            row['min_players'] = int(row['min_players'])
            for key in row.keys():
                if not row[key] and type(row[key]) != list:
                    row[key] = None
            ref.set(row)