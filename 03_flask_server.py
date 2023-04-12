from flask import Flask
from flask_restful import Resource, Api
import pymssql
from dotenv import load_dotenv
import os
import datetime

load_dotenv()

SQL_SERVER = os.environ['server']
SQL_USER = os.environ['user']
SQL_PASSWORD = os.environ['password']
SQL_DATABASE = os.environ['database']

print(SQL_SERVER)


##############################################################################
# Flask Setup


app = Flask(__name__)
api = Api(app)


def connect_sql():
    conn = pymssql.connect(SQL_SERVER, SQL_USER, SQL_PASSWORD, SQL_DATABASE)
    cursor = conn.cursor(as_dict=False)
    return conn, cursor

def sql_select_where_id(statement, id):
    conn, cursor = connect_sql()
    cursor.execute(statement, id)
    try:
        data = next(cursor)
        if len(data) == 14 and isinstance(data[12], datetime.date):
            data = list(data)
            data[12] = str(data[12])
        schema = [s[0] for s in cursor.description]
        return [schema] + [data]
    except StopIteration:
        return "Not found", 404


######################################
# Routes Setup

class TournamentList(Resource):
    def get(self):
        conn, cursor = connect_sql()
        cursor.execute('SELECT b.Id [BaseEventId], e.Id [EventId], e.Name [EventName], c.Id [CountryId] FROM Events e'
                       '   INNER JOIN BaseEvents b ON b.Id = e.BaseEventId'
                       '   INNER JOIN Countries c on c.Id = b.CountryId')
        schema = [s[0] for s in cursor.description]
        return [schema] + [row for row in cursor]

class Countries(Resource):
    def post(self, country_id):
        return sql_select_where_id('SELECT * FROM Countries WHERE Id = %s', country_id)


class BaseEvents(Resource):
    def post(self, base_event_id):
        return sql_select_where_id('SELECT * FROM BaseEvents WHERE Id = %s', base_event_id)

class Events(Resource):
    def post(self, event_id):
        return sql_select_where_id('SELECT * FROM Events WHERE Id = %s', event_id)

class Players(Resource):
    def post(self, player_id):
        return sql_select_where_id('SELECT * FROM Players WHERE Id = %s', player_id)

class Games(Resource):
    def post(self, game_id):
        return sql_select_where_id('SELECT * FROM Games WHERE Id = %s', game_id)


######################################
# API Setup

api.add_resource(TournamentList, '/Tournaments/')
api.add_resource(Countries, '/Countries/<int:country_id>')
api.add_resource(BaseEvents, '/BaseEvents/<int:base_event_id>')
api.add_resource(Events, '/Events/<int:event_id>')
api.add_resource(Players, '/Players/<int:player_id>')
api.add_resource(Games, '/Games/<int:game_id>')



#######################################################################################################################
# Entry Point

if __name__ == '__main__':
    app.run(debug=True)


'''

conn = pymssql.connect(server, user, password, "bgo")
cursor = conn.cursor(as_dict=True)

# cursor.execute('SELECT * FROM Events e INNER JOIN BaseEvents b ON b.Id = e.BaseEventId INNER JOIN Countries c on b.CountryId = c.Id')
cursor.execute('SELECT * FROM Events WHERE BaseEventId=%s', 2)
for row in cursor:
    print(row)


'''