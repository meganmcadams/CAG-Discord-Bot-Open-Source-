from config import CHARACTER_TAGS
from discord import ForumChannel

def get_classes_no_level(character: dict):
    val = ""
    last_item = character['classes'][-1]
    for c in character['classes']:
        val += c['name']
        if c is not last_item:
            val += ", "
    return val

def get_character_tags(character: dict, forum: ForumChannel):
    tag_ids = []
    for c in character.get('classes', {}):
        if len(tag_ids) >= 3: # max of 3 class tags
            break
        tag_ids.append(CHARACTER_TAGS[c['name']])
    if character.get('affiliations'):
        tag_ids.append(CHARACTER_TAGS[character['affiliations'][0]])
    tag_ids.append(CHARACTER_TAGS['Active'])

    tags = []
    for id in tag_ids:
        tags.append(forum.get_tag(id))
    return tags
