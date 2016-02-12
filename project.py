# Import section
from flask import Flask, render_template, request, redirect, jsonify, \
    url_for, flash, session as login_session
from functools import wraps
from flask.ext.seasurf import SeaSurf
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Style, Model, User

app = Flask(__name__)
csrf = SeaSurf(app)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

# Connect to Database and create database session
engine = create_engine('sqlite:///motorbikes_master.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            flash('You need to be logged in to access here')
            return redirect(url_for('showLogin'))
        else:
            return f(*args, **kwargs)
    return decorated_function


def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'model_id' in kwargs:
            model_id = kwargs['model_id']
            target = session.query(Model).filter_by(id=model_id).one()
        else:
            style_id = kwargs['style_id']
            target = session.query(Style).filter_by(id=style_id).one()

        if target.user_id != login_session['user_id']:
            return redirect(url_for('notAllowed'))
        else:
            return f(*args, **kwargs)
    return decorated_function


@app.route('/gconnect', methods=['POST'])
def gconnect():
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

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# User Helper Functions


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
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
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
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
        # response = make_response(json.dumps('Successfully disconnected.'), 200)
        # response.headers['Content-Type'] = 'application/json'
        # return response
        flash('Successfully disconnected.')
        return redirect(url_for('showStyles'))
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view Restaurant Information


@app.route('/style/JSON')
def showStylesJSON():
    styles = session.query(Style).order_by(asc(Style.name))
    return jsonify(styles=[r.serialize for r in styles])


@app.route('/style/<int:style_id>/JSON')
@app.route('/style/<int:style_id>/model/JSON')
def showModelsJSON(style_id):
    """Show a list of models given a style."""
    models = session.query(Model).filter_by(style_id=style_id).all()
    return jsonify(models=[r.serialize for r in models])


@app.route('/style/<int:style_id>/model/<int:model_id>/JSON')
def showModelInfoJSON(style_id, model_id):
    model = session.query(Model).filter_by(id=model_id).one()
    return jsonify(model=model.serialize)


# Create a state token to prevent request forgery
# Store it in the session for later validation
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" %login_session['state']
    return render_template('login.html', STATE=state)


# Show all styles
@app.route('/')
@app.route('/style/')
def showStyles():
    """Show a list of styles."""
    styles = session.query(Style).order_by(asc(Style.name))
    return render_template('styles.html', styles=styles)


# Create a new style
@app.route('/style/new/', methods=['GET', 'POST'])
@login_required
def newStyle():
    if request.method == 'POST':
        newStyle = Style(
            name=request.form['name'],
            user_id=login_session['user_id'])
        session.add(newStyle)
        flash('New Style %s Successfully Created' % newStyle.name)
        session.commit()
        return redirect(url_for('showStyles'))
    else:
        return render_template('newStyle.html')


# Edit a style
@app.route('/style/<int:style_id>/edit/', methods=['GET', 'POST'])
@login_required
@owner_required
def editStyle(style_id):
    editedStyle = session.query(Style).filter_by(id=style_id).one()
    if request.method == 'POST':
        if request.form['name']:
            editedStyle.name = request.form['name']
            session.commit()
            flash('Style Successfully Edited %s' % editedStyle.name)
            return redirect(url_for('showStyles'))
    else:
        return render_template('editStyle.html', style=editedStyle)


# Delete a style
@app.route('/style/<int:style_id>/delete/', methods=['GET', 'POST'])
@login_required
@owner_required
def deleteStyle(style_id):
    styleToDelete = session.query(Style).filter_by(id=style_id).one()
    if request.method == 'POST':
        session.delete(styleToDelete)
        flash('%s Successfully Deleted' % styleToDelete.name)
        session.commit()
        return redirect(url_for('showStyles', style_id=style_id))
    else:
        return render_template('deleteStyle.html', style=styleToDelete)


# Show a style models
@app.route('/style/<int:style_id>/')
@app.route('/style/<int:style_id>/model/')
def showModels(style_id):
    """Show a list of models given a style."""
    style = session.query(Style).filter_by(id=style_id).one()
    models = session.query(Model).filter_by(style_id=style_id).all()
    return render_template('models.html', models=models, style=style)


# Create a new model
@app.route('/style/<int:style_id>/model/new/', methods=['GET', 'POST'])
@login_required
def newModel(style_id):
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
        flash('New Model %s Successfully Created' % (newModel.name))
        return redirect(url_for('showModels', style_id=style_id))
    else:
        return render_template('newModel.html', style=style)


# Edit a model
@app.route(
    '/style/<int:style_id>/model/<int:model_id>/edit',
    methods=['GET', 'POST'])
@login_required
@owner_required
def editModel(style_id, model_id):

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
        flash('Model Successfully Edited')
        return redirect(url_for('showModels', style_id=style_id))
    else:
        return render_template(
            'editModel.html',
            style=style,
            model=editedModel)


# Delete a model
@app.route(
    '/style/<int:style_id>/model/<int:model_id>/delete',
    methods=['GET', 'POST'])
@login_required
@owner_required
def deleteModel(style_id, model_id):
    style = session.query(Style).filter_by(id=style_id).one()
    modelToDelete = session.query(Model).filter_by(id=model_id).one()
    if request.method == 'POST':
        session.delete(modelToDelete)
        session.commit()
        flash('Model Successfully Deleted')
        return redirect(url_for('showModels', style_id=style_id))
    else:
        return render_template(
            'deleteModel.html',
            model=modelToDelete,
            style=style)

# Show a model information
@app.route('/style/<int:style_id>/model/<int:model_id>/info')
def showModelInfo(style_id, model_id):
    model = session.query(Model).filter_by(id=model_id).one()
    style = session.query(Style).filter_by(id=style_id).one()
    return render_template('modelInfo.html', model=model, style=style)


# Now Allowed stored_credentials
@app.route('/not_allowed')
def notAllowed():
    return render_template('notAllowed.html')


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
