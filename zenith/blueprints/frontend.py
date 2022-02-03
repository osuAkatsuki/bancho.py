# -*- coding: utf-8 -*-

__all__ = ()

import bcrypt
import hashlib
import os
import time
import datetime

from quart import Blueprint
from quart import redirect
from quart import render_template
from quart import request
from quart import session
from quart import send_file

from app.objects.player import Player


frontend = Blueprint('frontend', __name__)

@frontend.route('/')
async def home():
    return await render_template('home.html')

@frontend.route('/test')
async def test():
    return await render_template('test.html')