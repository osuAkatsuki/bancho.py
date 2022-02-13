# -*- coding: utf-8 -*-

__all__ = ()

import datetime
import hashlib
import os
import time

import app.state.services
import bcrypt
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.state import website as zglob
from cmyui.logging import Ansi, log
from quart import (Blueprint, redirect, render_template, request, send_file,
                   session)
from zenith import zconfig
from zenith.objects import regexes, utils
from zenith.objects.utils import flash

frontend = Blueprint('frontend', __name__)

@frontend.route('/')
async def home():
    if 'authenticated' in session:
        await utils.updateSession(session)

    return await render_template('home.html', methods=['GET'])

@frontend.route('/test')
async def test():
    return await render_template('verify.html')

@frontend.route('/login', methods=['GET'])
async def login():
    return await render_template('login.html')

@frontend.route('/login', methods=['POST'])
async def login_post():
    if 'authenticated' in session:
        return await utils.flash_tohome('error', "You're already logged in!")


    form = await request.form
    username = form.get('username', type=str)
    passwd_txt = form.get('password', type=str)
    passwd_txt_repeat = form.get('password-confirm', type=str)

    if username is None or passwd_txt is None:
        return await utils.flash_tohome('error', 'Invalid parameters.')

    # check if account exists
    user_info = await app.state.services.database.fetch_one(
        'SELECT id, name, email, priv, '
        'pw_bcrypt, silence_end '
        'FROM users '
        'WHERE safe_name = :sn',
        {"sn": utils.get_safe_name(username)}
    )
    # user doesn't exist; deny post
    if not user_info:
        return await render_template('login.html', flash={"msg":"Invalid username or password."})

    # convert to dict because databases
    user_info = dict(user_info)

    # NOTE: Bot isn't a user.
    if user_info['id'] == 1:
        return await render_template('login.html', flash={"msg":"Invalid username or password."})

    # cache and other related password information
    bcrypt_cache = zglob.cache['bcrypt']
    pw_bcrypt = user_info['pw_bcrypt'].encode()
    pw_md5 = hashlib.md5(passwd_txt.encode()).hexdigest().encode()

    # check credentials (password) against db
    # intentionally slow, will cache to speed up
    if pw_bcrypt in bcrypt_cache:
        if pw_md5 != bcrypt_cache[pw_bcrypt]: # ~0.1ms
            return await render_template('login.html', flash={"msg":"Invalid username or password."})
    else: # ~200ms
        if not bcrypt.checkpw(pw_md5, pw_bcrypt):
            return await render_template('login.html', flash={"msg":"Invalid username or password."})

        # login successful; cache password for next login
        bcrypt_cache[pw_bcrypt] = pw_md5

    # user not verified; render verify
    if not user_info['priv'] & Privileges.VERIFIED:
        return await render_template('verify.html')


    # login successful; store session data

    session['authenticated'] = True
    session['user_data'] = {}
    await utils.updateSession(session, int(user_info['id']))

    return await utils.flash_tohome('success', f"Welcome back {username}!")

@frontend.route('/logout', methods=['GET'])
async def logout():
    if 'authenticated' not in session:
        return await utils.flash_tohome('error', "You can't log out if you're not logged in.")

    # clear session data
    session.pop('authenticated', None)
    session.pop('user_data', None)

    # render login
    return await utils.flash_tohome('success', "Successfully logged out!")

@frontend.route('/register', methods=['GET'])
async def register():
    if 'authenticated' in session:
        return await utils.flash_tohome('error', "You're already logged in'!")

    return await render_template('register.html', message=None)

@frontend.route('/register', methods=['POST'])
async def register_post():
    if 'authenticated' in session:
        return await utils.flash_tohome('error', "You're already logged in.")

    if not zconfig.registration:
        return await utils.flash_tohome('error', 'Registrations are currently disabled.')

    form = await request.form
    username = form.get('username', type=str)
    email = form.get('email', type=str)
    passwd_txt = form.get('password', type=str)
    passwd_txt_repeat = form.get('password-confirm', type=str)
    if username is None or email is None or passwd_txt is None:
        return await utils.flash_tohome('error', 'Invalid parameters.')
    if passwd_txt != passwd_txt_repeat:
        return await render_template('register.html', message={"password": "Passwords didn't match"})

    if zconfig.hCaptcha_sitekey != 'changeme':
        captcha_data = form.get('h-captcha-response', type=str)
        if (
            captcha_data is None or
            not await utils.validate_captcha(captcha_data)
        ):
            return await render_template('register.html', message={"captcha": 'Captcha Failed'})

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    # check if username exists
    if not regexes.username.match(username):
        return await render_template('register.html', message={"name": 'Invalid Username'})

    if '_' in username and ' ' in username:
        return await render_template('register.html', message={"name": 'Username may contain "_" or " ", but not both.'})

    if username in zconfig.disallowed_names:
        return await render_template('register.html', message={"name": 'Disallowed username; pick another'})

    if await app.state.services.database.fetch_one(
        'SELECT 1 FROM users WHERE name=:name',
        {"name": username}
        ):
            return await render_template('register.html', message={"name": 'Username already taken by another user.'})
    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.email.match(email):
        return await render_template('register.html', message={"email": 'Invalid email syntax.'})

    if await app.state.services.database.fetch_one(
        'SELECT 1 FROM users WHERE email = :email',
        {"email": email}
        ):
            return await render_template('register.html', message={"email": 'Email already taken by another user.'})
    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 <= len(passwd_txt) <= 48:
        return await render_template('register.html', message={"password": 'Password must be 8-48 characters in length'})

    if len(set(passwd_txt)) <= 3:
        return await render_template('register.html', message={"password": 'Password must have more than 3 unique characters.'})

    if passwd_txt.lower() in zconfig.disallowed_passwords:
        return await render_template('register.html', message={"password": 'That password was deemed too simple.'})

    # TODO: add correct locking
    # (start of lock)
    pw_md5 = hashlib.md5(passwd_txt.encode()).hexdigest().encode()
    pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
    bcrypt_cache = zglob.cache['bcrypt']
    bcrypt_cache[pw_bcrypt] = pw_md5 # cache pw

    safe_name = utils.get_safe_name(username)

    # fetch the users' country
    if (
        request.headers and
        (ip := request.headers.get('X-Real-IP', type=str)) is not None
    ):
        country = await utils.fetch_geoloc(ip)
    else:
        country = 'xx'

    async with app.state.services.database.connection() as db_cursor:
        # add to `users` table.
        await db_cursor.execute(
            'INSERT INTO users '
            '(name, safe_name, email, pw_bcrypt, country, creation_time, latest_activity) '
            'VALUES (:name, :safe_name, :email, :pw_bcrypt, :country, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())',
            {
                "name":      username,
                "safe_name": safe_name,
                "email":     email,
                "pw_bcrypt": pw_bcrypt,
                "country":   country
            })

        user_id = await db_cursor.fetch_val(
            'SELECT id FROM users WHERE name = :safe_name',
            {"safe_name": safe_name})

        #TODO: Use execute_many here, it's faster.
        # add to `stats` table.
        for mode in (
            0,  # vn!std
            1,  # vn!taiko
            2,  # vn!catch
            3,  # vn!mania
            4,  # rx!std
            5,  # rx!taiko
            6,  # rx!catch
            8,  # ap!std
        ):
            await db_cursor.execute(
                'INSERT INTO stats '
                '(id, mode) VALUES (:id, :mode)',
                {"id": user_id, "mode": mode}
            )


    # user has successfully registered
    log(f"User <{username} ({user_id})> has successfully registered through website.", Ansi.GREEN)
    return await render_template('verify.html')
