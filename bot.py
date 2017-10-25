#!/usr/bin/env python -OO
# -*- coding: utf-8 -*-
"""An example Kik bot implemented in Python.

It's designed to greet the user, send a suggested response and replies to them with their profile picture.
Remember to set KIKBOT_USERNAME, KIKBOT_API_KEY and KIKBOT_WEBHOOK in your Flask environment.

See https://github.com/kikinteractive/kik-python for Kik's Python API documentation.

Apache 2.0 License

(c) 2016 Kik Interactive Inc, 2017 modifications jc@unternet.net

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the
License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific
language governing permissions and limitations under the License.

"""
from __future__ import print_function
import sys
import os
import random
import re
import logging
from collections import defaultdict
from flask import Flask, request, Response
from kik import KikApi, Configuration
from kik.messages import messages_from_json, TextMessage, PictureMessage, \
    SuggestedResponseKeyboard, TextResponse, StartChattingMessage
logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)
BOT_USERNAME = os.getenv('KIKBOT_USERNAME')
BOT_API_KEY = os.getenv('KIKBOT_API_KEY')
WEBHOOK = os.getenv('KIKBOT_WEBHOOK')
PORT = int(os.getenv('KIKBOT_PORT', '0'))
ANY = [[], []]  # indicates any type of user input
OK = ['ok', 'okey', 'okay', 'listo', 'bueno', 'bien', 'fine']
GOOD = [
    ['good', 'gut'] + OK,  # first word match
    ['notbad', 'nichtschlecht'], # entire response if no first word match
]
BAD = [
    ['bad', 'mal', 'malito', 'schlecht', 'ugh', 'crappy'],
    ['notgood', 'nichtgut'],
]
YES = [
    ['yes', 'yep', 'yup', 'yeah', 'sure', 'ja', 'si', 'sí', 'great'] + OK,
    ['iguessso', 'comono', 'whynot'],
]
NO = [
    ['no', 'non', 'nicht'],
    ['probablynot', 'idontthinkso'],
]
GREETING = [
    ['hi', 'hello', 'hola', 'hallo', 'gute', 'guten', 'buenos', 'buenas',
     'hey'],
    ["wiegehts", 'howareyou', 'howareya', 'comoestas', 'comoesta', 'comesta'],
]
STATE = defaultdict(str)  # maintains state for each user
# need a placeholder for profile picture display function, will replace later
FUNCTIONS = {
    'PROFILE_PIC_DISPLAY': None,
}
RESPONSE = {  # possible responses with new state for each state
    # note that kik app does not allow an empty response
    '': [
            {
                'input': GREETING,
                'response': [['Hey {you.first_name}, how are you?']],
                'state': 'health_query',
                'suggested': ['Good', 'Bad'],
            },
        ],
    'health_query': [
            {
                'input': GOOD,
                'response': [["That's Great! :) Wanna see your profile pic?"]],
                'state': 'picture_query',
                'suggested': ["Sure! I'd love to!", 'No Thanks'],
            },
            {
                'input': BAD,
                'response': [['Oh No! :( Wanna see your profile pic?']],
                'state': 'picture_query',
                'suggested': ['Yep! I Sure Do!', 'No Thank You'],
            },
        ],
    'picture_query': [
            {
                'input': YES,
                'response': [["Here's your profile picture!",
                              'PROFILE_PIC_DISPLAY']],
                'state': '',
                'suggested': [],
            },
            {
                'input': NO,
                'response': [['Ok, {you.first_name}. '
                             'Chat with me again if you change your mind.']],
                'state': '',
                'suggested': [],
            },
        ],
    'default': [
            {
                'input': ANY,
                'response': [["Sorry {you.first_name}, "
                              "I didn't quite understand that. How are you?"],
                             ["Sorry, I didn't quite understand that. "
                              "How are you, {you.first_name}?"]],
                'state': 'health_query',
                'suggested': ['Good', 'Bad'],
            }
        ]
}
COMMAND = os.path.splitext(os.path.basename(sys.argv[0]))[0]
if COMMAND in ['doctest', 'pydoc']:
    DOCTESTDEBUG = logging.debug
else:
    DOCTESTDEBUG = lambda *args, **kwargs: None
logging.debug('os.environ: %s, WEBHOOK: %s', os.environ, WEBHOOK)

class KikBot(Flask):
    """ Flask kik bot application class"""

    def __init__(self, kik_api, import_name, static_path=None, static_url_path=None, static_folder="static",
                 template_folder="templates", instance_path=None, instance_relative_config=False,
                 root_path=None):

        self.kik_api = kik_api

        super(KikBot, self).__init__(import_name, static_path, static_url_path, static_folder, template_folder,
                                     instance_path, instance_relative_config, root_path)

        self.route("/incoming", methods=["POST"])(self.incoming)

    def incoming(self):
        """Handle incoming messages to the bot. All requests are authenticated using the signature in
        the 'X-Kik-Signature' header, which is built using the bot's api key (set in main() below).
        :return: Response
        """
        # verify that this is a valid request
        if not self.kik_api.verify_signature(
                request.headers.get("X-Kik-Signature"), request.get_data()):
            return Response(status=403)

        messages = messages_from_json(request.json["messages"])

        response = self.process(messages)

        # We're sending a batch of messages. We can send up to 25 messages at a time (with a limit of
        # 5 messages per user).

        self.kik_api.send_messages(response)

        return Response(status=200)

    def process(self, messages, testing=False):
        '''
        Generate responses for incoming messages

        >>> test = init()
        >>> got = test.process([TextMessage(body='Hey there!')], testing=True)
        >>> 'how are you' in got[0].body.lower()
        True
        '''
        response = []
        for message in messages:
            user = message.from_user
            logging.debug('user: %s', user)
            if testing:
                userdata = type('', (), {
                    'profile_pic_url': '//t.co/gnixl',
                    'first_name': 'gnixl',
                })
            else:
                userdata = self.kik_api.get_user(message.from_user)
            logging.debug('userdata: %s', userdata)
            state = STATE[user]
            # Check if its the user's first message.
            # Start Chatting messages are sent only once.
            # Treat it as "hello" regardless of content.
            if isinstance(message, StartChattingMessage):
                message = TextMessage(
                        to=BOT_USERNAME,
                        chat_id=message.chat_id,
                        body=GREETING[0][0])
            elif not isinstance(message, TextMessage):
                # we treat any non-text input as unrecognized
                message = TextMessage(
                        to=BOT_USERNAME,
                        chat_id=message.chat_id,
                        body='')
            for check in RESPONSE[STATE[user]] + RESPONSE['default']:
                if (check['input'] == ANY or
                        self.recognized(message.body, check['input'])):
                    state = self.respond(response, check, message, userdata)
                    STATE[user] = state
                    break
        return response

    def respond(self, response, data, message, userdata):
        '''
        Append packaged random response from data provided to response
        
        Returns new state for user
        '''
        templates = random.choice(data['response'])
        for template in templates:
            if template in FUNCTIONS:
                response.append(getattr(self, FUNCTIONS[template])(
                    userdata, message))
            else:
                text = template.format(you=userdata)
                keyboards = [SuggestedResponseKeyboard(
                    responses=map(TextResponse, data['suggested']))]
                response.append(TextMessage(
                    to=message.from_user,
                    chat_id=message.chat_id,
                    body=text,
                    keyboards=keyboards))
        return data['state']

    def recognized(self, user_input, expected):
        '''
        return True if first word or whole phrase matched

        >>> test = init()
        >>> test.recognized('I am', (['a', 'b', 'c'], ['i', 'iamnot']))
        False
        >>> test.recognized('I am', (['a', 'b', 'c'], ['iam', 'iamnot']))
        True
        >>> test.recognized('I am', (['a', 'i', 'c'], ['iwish', 'iamnot']))
        True
        '''
        trimmed = self.trim(user_input)
        DOCTESTDEBUG('checking if %s in %s', trimmed, expected)
        return trimmed[0] in expected[0] or trimmed[1] in expected[1]

    def profile_pic_check_messages(self, userdata, message):
        """Function to check if user has a profile picture and returns appropriate messages.
        :param user: Kik User Object (used to acquire the URL the profile picture)
        :param message: Kik message received by the bot
        :return: PictureMessage
        """
        default_pic = 'https://cdn.kik.com/user/pic/%s/big' % message.from_user
        profile_picture = userdata.profile_pic_url or default_pic
        logging.debug('profile_picture: %s', profile_picture)

        return PictureMessage(
            to=message.from_user,
            chat_id=message.chat_id,
            pic_url=profile_picture
        )

    FUNCTIONS['PROFILE_PIC_DISPLAY'] = 'profile_pic_check_messages'

    def trim(self, text):
        '''
        get rid of all non-text characters

        return tuple (first_word, entire_message_without_spaces)
        
        >>> test = init()
        >>> test.trim("It's a boy!")
        ('its', 'itsaboy')
        >>> test.trim('')
        ('', '')
        '''
        lowercased = text.lower()
        shorter = (re.compile(r'[^\s\w]+').sub('', lowercased).split()
                   or [''])[0]
        longer = re.compile(r'[\W]+').sub('', lowercased)
        return shorter, longer

def init():
    """ Main program """
    kik = KikApi(BOT_USERNAME, BOT_API_KEY)
    # For simplicity, we're going to set_configuration on startup. However, this really only needs to happen once
    # or if the configuration changes. In a production setting, you would only issue this call if you need to change
    # the configuration, and not every time the bot starts.
    logging.debug('setting webhook to %s', WEBHOOK)
    kik.set_configuration(Configuration(webhook=WEBHOOK))
    app = KikBot(kik, __name__)
    if PORT:
        app.run(port=PORT, host='127.0.0.1', debug=True)  # from command line
    else:
        return app

if __name__ == "__main__":
    if PORT:
        init()
    else:
        logging.fatal('Cannot run from command line without KIKBOT_PORT set')
else:
    # running from uwsgi
    PORT = None
    app = init()
