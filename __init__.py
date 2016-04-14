"""This application creates an item catalog.

This is the project 3 for the FSND at Udacity, created by Mario Nuevo.
"""
# Import section
from flask import Flask, render_template, request, redirect, jsonify, \
    url_for, flash, session as login_session, make_response
from functools import wraps
from flask.ext.seasurf import SeaSurf
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests
import os

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Style, Model, User

app = Flask(__name__)
csrf = SeaSurf(app)

# APP_PATH = '/var/www/itemCatalog/itemCatalog/'
APP_PATH = os.path.realpath(__file__)
print APP_PATH
CLIENT_ID = json.loads(
    open(APP_PATH + 'client_secrets.json', 'r').read())['web']['client_id']

# Connect to Database and create database session
engine = create_engine('postgresql://catalog:logcata@localhost/')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


def login_required(f):
    """Function decorator.

    Requires to be logged before using a function.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            flash('You need to be logged in to access here', 'alert-info')
            return redirect(url_for('showLogin'))
        else:
            return f(*args, **kwargs)
    return decorated_function


def owner_required(f):
    """Function decorator.

    Requires to be the owner of an item before modyfing it.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Since I'm using this decorator both for styles and models, I need
        # to differentiate between both.
        style_id = kwargs['style_id']
        if 'model_id' in kwargs:
            model_id = kwargs['model_id']
            target = session.query(Model).filter_by(id=model_id).one()
            return_target = url_for('showModels', style_id=style_id)
        else:
            target = session.query(Style).filter_by(id=style_id).one()
            return_target = url_for('showStyles')

        if target.user_id != login_session['user_id']:
            flash(
                "You are not allowed to perform this operation because " +
                "you don't own the item",
                'alert-danger')
            return redirect(return_target)
            url_for('showModels', style_id=style_id)
        else:
            return f(*args, **kwargs)
    return decorated_function


def isStyleEmpty(style_id):
    """Return True if there is no models in a given Style. False otherwise."""
    if len(session.query(Model).filter_by(style_id=style_id).all()) == 0:
        return True
    else:
        return False


@app.route('/gconnect', methods=['POST'])
@csrf.exempt
def gconnect():
    """Connect to Google API authentication."""
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'),
            200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    flash(
        "You are now logged in as %s" % login_session['username'],
        'alert-success')
    print "done!"
    return render_template(
        'welcome.html',
        username=login_session['username'],
        picture=login_session['picture'])


# User Helper Functions
def createUser(login_session):
    """Create a user with the dara retrieved from the Google API."""
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    """Get user information from the database."""
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    """Get user id from the database given the email."""
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/gdisconnect')
@csrf.exempt
def gdisconnect():
    """Disconnect from Google API authentication."""
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(
            json.dumps('Current user not connected.'),
            401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
        % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        flash('Successfully disconnected.', 'alert-success')
        return redirect(url_for('showStyles'))
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.',
            400))
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view Restaurant Information


@app.route('/style/JSON')
def showStylesJSON():
    """Return a JSON formatted list of styles."""
    styles = session.query(Style).order_by(asc(Style.name))
    return jsonify(styles=[r.serialize for r in styles])


@app.route('/style/<int:style_id>/JSON')
@app.route('/style/<int:style_id>/model/JSON')
def showModelsJSON(style_id):
    """Return a JSON formatted list of models given a style."""
    models = session.query(Model).filter_by(style_id=style_id).all()
    return jsonify(models=[r.serialize for r in models])


@app.route('/style/<int:style_id>/model/<int:model_id>/JSON')
def showModelInfoJSON(style_id, model_id):
    """Return a JSON formatted model information."""
    model = session.query(Model).filter_by(id=model_id).one()
    return jsonify(model=model.serialize)


@app.route('/login')
def showLogin():
    """Show login page.

    Create a state token to prevent request forgery
    Store it in the session for later validation
    """
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)


@app.route('/')
@app.route('/style/')
def showStyles():
    """Show a list of styles."""
    styles = session.query(Style).order_by(asc(Style.name))
    return render_template('styles.html', styles=styles)


@app.route('/style/new/', methods=['GET', 'POST'])
@login_required
def newStyle():
    """Create a new style."""
    if request.method == 'POST':
        newStyle = Style(
            name=request.form['name'],
            user_id=login_session['user_id'])
        session.add(newStyle)
        flash(
            'New Style %s Successfully Created' % newStyle.name,
            'alert-success')
        session.commit()
        return redirect(url_for('showStyles'))
    else:
        return render_template('newStyle.html')


@app.route('/style/<int:style_id>/edit/', methods=['GET', 'POST'])
@login_required
@owner_required
def editStyle(style_id):
    """Edit a style."""
    editedStyle = session.query(Style).filter_by(id=style_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedStyle.name = request.form['name']
            session.commit()
            flash(
                'Style Successfully Edited %s' % editedStyle.name,
                'alert-success')
            return redirect(url_for('showStyles'))
    else:
        return render_template('editStyle.html', style=editedStyle)


@app.route('/style/<int:style_id>/delete/', methods=['GET', 'POST'])
@login_required
@owner_required
def deleteStyle(style_id):
    """Delete a style."""
    if isStyleEmpty(style_id):
        styleToDelete = session.query(Style).filter_by(id=style_id).one()
        if request.method == 'POST':
            session.delete(styleToDelete)
            flash(
                '%s Successfully Deleted' % styleToDelete.name,
                'alert-success')
            session.commit()
            return redirect(url_for('showStyles', style_id=style_id))
        else:
            return render_template('deleteStyle.html', style=styleToDelete)
    else:
        flash('The style is not empty', 'alert-warning')
        return redirect(url_for('showStyles'))


@app.route('/style/<int:style_id>/')
@app.route('/style/<int:style_id>/model/')
def showModels(style_id):
    """Show a list of models given a style."""
    style = session.query(Style).filter_by(id=style_id).one()
    models = session.query(Model).filter_by(style_id=style_id).all()
    return render_template('models.html', models=models, style=style)


@app.route('/style/<int:style_id>/model/new/', methods=['GET', 'POST'])
@login_required
def newModel(style_id):
    """Create a new model."""
    style = session.query(Style).filter_by(id=style_id).one()
    if request.method == 'POST':
        newModel = Model(
            name=request.form['name'],
            description=request.form['description'],
            price=request.form['price'],
            power=request.form['power'],
            image=request.form['image'],
            style_id=style_id,
            user_id=login_session['user_id'])
        session.add(newModel)
        session.commit()
        flash(
            'New Model %s Successfully Created' % (newModel.name),
            'alert-success')
        return redirect(url_for('showModels', style_id=style_id))
    else:
        return render_template('newModel.html', style=style)


@app.route(
    '/style/<int:style_id>/model/<int:model_id>/edit',
    methods=['GET', 'POST'])
@login_required
@owner_required
def editModel(style_id, model_id):
    """Edit a model."""
    editedModel = session.query(Model).filter_by(id=model_id).one()
    style = session.query(Style).filter_by(id=style_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedModel.name = request.form['name']
        if request.form['description']:
            editedModel.description = request.form['description']
        if request.form['price']:
            editedModel.price = request.form['price']
        if request.form['power']:
            editedModel.power = request.form['power']
        if request.form['image']:
            editedModel.image = request.form['image']

        session.commit()
        flash('Model Successfully Edited', 'alert-success')
        return redirect(url_for('showModels', style_id=style_id))
    else:
        return render_template(
            'editModel.html',
            style=style,
            model=editedModel)


@app.route(
    '/style/<int:style_id>/model/<int:model_id>/delete',
    methods=['GET', 'POST'])
@login_required
@owner_required
def deleteModel(style_id, model_id):
    """Delete a model."""
    style = session.query(Style).filter_by(id=style_id).one()
    modelToDelete = session.query(Model).filter_by(id=model_id).one()
    if request.method == 'POST':
        session.delete(modelToDelete)
        session.commit()
        flash('Model Successfully Deleted', 'alert-success')
        return redirect(url_for('showModels', style_id=style_id))
    else:
        return render_template(
            'deleteModel.html',
            model=modelToDelete,
            style=style)


@app.route('/style/<int:style_id>/model/<int:model_id>/info')
def showModelInfo(style_id, model_id):
    """Show a model inforation."""
    model = session.query(Model).filter_by(id=model_id).one()
    style = session.query(Style).filter_by(id=style_id).one()
    return render_template('modelInfo.html', model=model, style=style)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
