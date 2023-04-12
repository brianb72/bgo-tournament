import re
import tarfile
import os
import sgf
from sgf_wrapper import SGFWrapper
from datetime import datetime

##############################################################################
# Constants

DATABASE_NAME = 'BGO'

# List of countries with code, abbreviation, full name
COUNTRIES = [
    (0, 'none', 'None'),
    (1, 'cn', 'China'),
    (2, 'kr', 'Korea'),
    (3, 'jp', 'Japan'),
    (4, 'tw', 'Taiwan'),
]

# Maps country full names to abbreviations
COUNTRY_NAME_TO_ABBR = {
    'Japanese': 'jp',
    'Chinese': 'cn',
    'Korean': 'kr',
    'Taiwan': 'tw',
}

# Maps words in tournament name to host country
TOURNAMENT_COUNTRY = {
    'Samsung': 'kr',
    'LG Cup': 'kr',
    'Toyota': 'jp',
    'Changqi': 'cn',
    'Fujitsu': 'jp',
    'Chunlan': 'cn',
    'Nongshim': 'kr',
    'Jeongganjang': 'kr',
    'Zhonghuan': 'tw',
    'Korea': 'jp',
    'Nogshim': 'kr',
    'Hungchang': 'kr',
    'Kansai': 'jp',
    'Hiroshima': 'jp',
    'NHK': 'jp',
    'Myeongin': 'kr',
    'Haojue': 'cn',
    'China': 'cn',
    'Kangwon': 'kr',
    'Daiwa-Shoken': 'jp',
}

##############################################################################
# Vars

# players[name] = {player_id, country_id}
last_player_id = 0
players = {}

# tournaments['Japanese Meijin'] = {tournament_id, country_id}
last_base_event_id = 0
base_events = {}

# events['1st Japanese Meijin'] = {event_id, country_id}
last_event_id = 0
events = {}

#  Game list
game_list = []

##############################################################################
# Utility

def country_code_to_id(code):
    '''
    Convert a country code 'jp' to id 3
    '''
    try:
        return COUNTRIES[[o[1] for o in COUNTRIES].index(code)][0]
    except (ValueError, IndexError):
        raise RuntimeError(f'Could not find COUNTRIES[{code}]')


def add_player(name, country):
    global last_player_id
    try:
        country_id = country_code_to_id(country if country != 'ja' else 'jp')
    except RuntimeError:
        country_id = 0
    if name not in players:
        last_player_id += 1
        players[name] = dict(player_id=last_player_id, country_id=country_id)
    else:
        # If previous sighting had no country, update if this record has country
        if players[name]['country_id'] == 0 and country_id != 0:
            players[name]['country_id'] = country_id


def sql_escape(s):
    '''Converts single quote to double single quote'''
    return s.replace("'", "''")


def spaces(s):
    '''Condenses multiple spaces into single spaces'''
    return ' '.join(s.split())


def ordinal_from_int(i):
    '''Converts an integer into an ordinal'''
    return "%d%s" % (i, "tsnrhtdd"[(i // 10 % 10 != 1) * (i % 10 < 4) * i % 10::4])


def decode_event(event):
    '''
    Possible event formats:
        Ordinal   Country    Base Event Name
            1st   Japanese   Meijin
           22nd   Chinese    Mingren
            5th              Asian TV Cup
     Country Ord     base_name        event_name
    ('jp', '1st', 'Japanese Meijin', '1st Japanese Meijin')
    :return: (country_abbr, number, base_name, event_name)
    '''
    r = re.search(r'(\d{1,2}(?:st|nd|rd|th))(.*)', event)
    try:
        event_name = r.group(0).strip()
        number = r.group(1).strip()
        number = int(''.join([ch for ch in number if str.isdigit(ch)]))
        base_name = r.group(2).strip()
        r2 = re.search(r'((?:Japanese|Chinese|Korean|Taiwan))', base_name)
        try:
            country = r2.group(1).strip()
        except AttributeError:
            country = None
    except AttributeError:
        return (None, None, None, None) # could not decode
    try:
        country_abbr = COUNTRY_NAME_TO_ABBR[country]
    except KeyError:
        country_abbr = 'none'
    return (country_abbr, number, base_name, event_name)


def output_lines(statement, lines, max_lines=1000):
    '''
    Output max_lines at a time, repeat output statement each in each batch of max_lines
    '''
    for idx, line in enumerate(lines):
        if idx % max_lines == 0:
            print('\n' + statement, file=outp)
            print('   ' + line, file=outp)
        else:
            print('   ,' + line, file=outp)

##############################################################################
# Initial TGZ Parse

tar_file = tarfile.open('./GoKifu.tgz', 'r:gz')
processed_files = 0
last_output = datetime.now()

# Parse TGZ and fill dictionaries with data
for tarinfo in tar_file:
    # Load and parse the next SGF file
    processed_files += 1
    if processed_files % 1000 == 0:
        print(f'Processed {processed_files} files - {datetime.now() - last_output}')
        last_output = datetime.now()
    # if processed_files == 100:
    #     break
    file_name, extension = os.path.splitext(tarinfo.name)
    if extension.lower() != '.sgf':
        continue
    sgf_file_name = tarinfo.name
    sgf_file_text = tar_file.extractfile(tarinfo).read().decode('utf-8')
    try:
        game_collection = sgf.parse(sgf_file_text)
    except (sgf.ParseException, UnboundLocalError):
        continue
    try:
        sgf_game = SGFWrapper(sgf_file_text, tarinfo.name)
    except RuntimeError as e:
        continue

    # Decode the EV Tag
    country_abbr, number, base_name, event_name = decode_event(sgf_game.tag_dict['EV'])
    if base_name == None:
        continue

    # If country not found, try searching names for known identifying strings to set country code
    if country_abbr == 'none':
        for k,v in TOURNAMENT_COUNTRY.items():
            if re.search(k, base_name, re.IGNORECASE):
                country_abbr = v
                break

    try:
        country_id = country_code_to_id(country_abbr)
    except:
        country_id = 0

    # Try adding the base_name
    if base_name not in base_events:
        last_base_event_id += 1
        base_events[base_name] = dict(base_event_id=last_base_event_id, country_id=country_id)

    # Try adding the event_name
    if event_name not in events:
        last_event_id += 1
        try:
            use_base_event_id = base_events[base_name]['base_event_id']
            use_base_country = base_events[base_name]['country_id']
        except KeyError:
            raise RuntimeError(f'Could not find [{event_name}] ')
        events[event_name] = dict(event_id=last_event_id, base_event_id=use_base_event_id, number=number)

    # Try adding both players, will do nothing if already exists
    add_player(sgf_game.tag_dict['PB'], sgf_game.tag_dict['BC'])
    add_player(sgf_game.tag_dict['PW'], sgf_game.tag_dict['WC'])

    # Add game to list
    game_list.append(dict(
        sgf_game=sgf_game,
        country_id=country_id,
        event_id=events[event_name]['event_id']
    ))

##############################################################################
# Produce Output Statements

outp = open('output.sql', mode='w')
print(f'USE [{DATABASE_NAME}]\n', file=outp)

######################################
# Countries

lines = []
print('-- COUNTRIES', file=outp)
print(f'CREATE TABLE Countries (\n'
      f'   Id INT PRIMARY KEY IDENTITY,\n'
      f'   Code NVARCHAR(5),\n'
      f'   Name NVARCHAR(30)\n'
      f')\n', file=outp)
print('SET IDENTITY_INSERT Countries ON', file=outp)

for idx, country in enumerate(COUNTRIES):
    lines.append(f"({country[0]}, '{country[1]}', '{country[2]}')")
output_lines(f'INSERT INTO Countries (Id, Code, Name) VALUES ', lines)

print('\nSET IDENTITY_INSERT Countries OFF', file=outp)

######################################
# Base Events

print('\n\n-- BaseEvents', file=outp)
print('CREATE TABLE BaseEvents (\n'
      '   Id INT PRIMARY KEY IDENTITY,\n'
      '   Name NVARCHAR(100) NOT NULL,\n'
      '   CountryId INT FOREIGN KEY REFERENCES Countries(Id)\n'
      ')', file=outp)
lines = ["(0, 'none', 0)"]
for base_event_name, v in sorted(base_events.items(), key=lambda x: x[1]['country_id']):
    base_event_id = v['base_event_id']
    country_id = v['country_id']
    lines.append(f"({base_event_id}, '{sql_escape(base_event_name)}', {country_id})")

print('\nSET IDENTITY_INSERT BaseEvents ON', file=outp)
output_lines('INSERT INTO BaseEvents (Id, Name, CountryId) VALUES ', lines)
print('\nSET IDENTITY_INSERT BaseEvents OFF', file=outp)


######################################
# Events

print('\n\n-- Events', file=outp)
print('CREATE TABLE Events (\n'
      '   Id INT PRIMARY KEY IDENTITY,\n'
      '   Name NVARCHAR(100) NOT NULL,\n'
      '   Number INT NOT NULL,\n'
      '   BaseEventId INT FOREIGN KEY REFERENCES BaseEvents(Id)\n'
      ')', file=outp)
print('\nSET IDENTITY_INSERT Events ON', file=outp)

lines = ["(0, 'none', 0, 0)"]
for event_name, v in sorted(events.items(), key=lambda x: x[1]['event_id']):
    event_id = v['event_id']
    base_event_id = v['base_event_id']
    number = v['number']
    lines.append(f"({event_id}, '{sql_escape(event_name)}', {number}, {base_event_id})")

output_lines('INSERT INTO Events (Id, Name, Number, BaseEventId) VALUES ', lines)
print('\nSET IDENTITY_INSERT Events OFF', file=outp)


######################################
# Players

print('\n\n-- Players', file=outp)
print('CREATE TABLE Players (\n'
      '   Id INT PRIMARY KEY IDENTITY,\n'
      '   Name NVARCHAR(100) NOT NULL,\n'
      '   CountryId INT FOREIGN KEY REFERENCES Countries(Id)'
      ')', file=outp)

lines = []
print('\nSET IDENTITY_INSERT Players ON', file=outp)
for player, v in players.items():
    player_id = v['player_id']
    country_id = v['country_id']
    lines.append(f"({player_id}, '{sql_escape(player)}', {country_id})")
output_lines('INSERT INTO Players (Id, Name, CountryId) VALUES', lines)


print('\nSET IDENTITY_INSERT Players OFF', file=outp)


######################################
# Games
print('\n\n-- Games', file=outp)
print('CREATE TABLE Games (\n'
      '   Id INT PRIMARY KEY IDENTITY,\n'
      '   CountryId INT FOREIGN KEY REFERENCES Countries(Id),\n'
      '   BlackId INT FOREIGN KEY REFERENCES Players(Id),\n'
      '   BlackRank INT NOT NULL,\n'
      '   WhiteId INT FOREIGN KEY REFERENCES Players(Id),\n'
      '   WhiteRank INT NOT NULL,\n'
      '   EventsID INT FOREIGN KEY REFERENCES Events(Id),\n'
      '   Event NVARCHAR(100),\n'
      '   Round NVARCHAR(100),\n'
      '   Place NVARCHAR(100),\n'
      '   Result NVARCHAR(25) NOT NULL,\n'
      '   WhoWonInt INT NOT NULL,\n'
      '   Date DATE NOT NULL,\n'
      '   Moves NVARCHAR(1000) NOT NULL\n'
      ')', file=outp)

lines = []
game_id = 0
print('\nSET IDENTITY_INSERT Games ON', file=outp)
for game in game_list:
    sgf_game = game['sgf_game']
    event_id = game['event_id']
    country_id = game['country_id']
    game_id += 1
    td = sgf_game.tag_dict
    black_id = players[td['PB']]['player_id']
    white_id = players[td['PW']]['player_id']
    black_rank = sgf_game.get_player_rank(1)
    white_rank = sgf_game.get_player_rank(-1)
    whowon = sgf_game.get_who_won()
    date = sgf_game.get_date()
    moves = ''.join(sgf_game.move_pair_list)
    lines.append(f"({game_id}, {country_id}, {black_id}, {black_rank}, {white_id}, "
                 f"{white_rank}, {event_id}, '{sql_escape(td['EV'])}', '{sql_escape(td['RO'])}', '{sql_escape(td['PC'])}', "
                 f"'{sql_escape(td['RE'])}', {whowon}, '{sql_escape(date)}', '{sql_escape(moves)}')")

output_lines('INSERT INTO Games (Id, CountryId, BlackId, BlackRank, WhiteId, WhiteRank, EventsID, '
             'Event, Round, Place, Result, WhoWonInt, Date, Moves) VALUES', lines)
print('\nSET IDENTITY_INSERT Games OFF', file=outp)


##############################################################################
# Finished, cleanup
outp.close()
print('\n-----------\nDone.')


