"""
Pirate slang script by lecom
Replaces certain words with pirate language and appends a 'yarrrr' to every line said, if not too long
This script is under the GNU GPLv3

Copyright (C) 2020 lecom
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from random import choice,randint
from pyspades.constants import MAX_CHAT_SIZE
from commands import add,admin

Max_Lang_Len=1

LangPrefixes=[
	'a',
	'ya',
	'ga'
]

PirateWords={
	'wtf':'avast',
	'wth':'avast',
	'dafuq':'blimey',
	'daheck':'timber me shivers',
	'lol':'yo-ho-ho',
	'rofl':'shiver me timbers',
	'omg':'Blimey!',
	'swag':'swagger',
	'stop':'belay',
	' I ':' me ',
	' the ':' ye ',
	' that ':' ye ',
	'you':'thee',
	'your':'yer',
	'yours':'yer',
	' u ':' ye ',
	' ur ':' yer ',
	' yes ':' aye ',
	'hi ':'ahoy ',
	'hello':'ahoy',
	'treasure':'booty',
	'bro':'matey',
	'friend':'matey',
	'piracy':'sweet trade',
	'pirate':'colleague',
	' ok ':' aye aye ',
	'shall':'shalt',
	'should ':'shalt ',
	' my':' me',
	'yeah':'aye',
	'gre':'bottle of ',
	'nade ':' rum',
	'intel':'booty',
	'fuck':'heck',
	'cunt':'sweet lass',
	'whore':'sweet lass',
	'bitch':'sweet maid'
}

@admin
def toggle_pirate_lang(self):
	self.protocol.PirateLang=not self.protocol.PirateLang
	PirateLangMessage='Pirate language set to %s' % ('on' if self.protocol.PirateLang else 'off')
	self.protocol.send_chat(PirateLangMessage,True)
	return PirateLangMessage

add(toggle_pirate_lang)

def apply_script(protocol, connection, config):
	class PirateLangProtocol(protocol):
		PirateLang=True
	class PirateLangConnection(connection):
		def on_chat(self, message, global_chat=False):
			if not self.protocol.PirateLang:
				return connection.on_chat(self, message, global_chat)
			for ReplaceWord in PirateWords.keys():
				if ReplaceWord not in message.lower():
					continue
				Count=message.count(ReplaceWord)
				PirateWord=PirateWords[ReplaceWord]
				Chars_Count=len(message)-len(ReplaceWord)*Count+len(PirateWord)*Count
				if Chars_Count<MAX_CHAT_SIZE:
					message=message.replace(ReplaceWord,PirateWord)
			Characters_left=Max_Lang_Len-len(message)
			Lower=randint(0,1)
			AppendMessage=' '
			LangPrefix=choice(LangPrefixes)
			if not Lower:
				LangPrefix=LangPrefix.upper()
			if Characters_left<=len(LangPrefix):
				return connection.on_chat(self, message, global_chat)
			AppendMessage+=LangPrefix
			for i in xrange(len(LangPrefix),Characters_left):
				if Lower:
					AppendMessage+='r'
				else:
					AppendMessage+='R'
			message+=AppendMessage
			return connection.on_chat(self, message, global_chat)
	return  PirateLangProtocol,PirateLangConnection
