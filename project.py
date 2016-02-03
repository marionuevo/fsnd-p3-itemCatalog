# Import section
from flask import Flask, render_template, request, redirect, jsonify, \
    url_for, flash

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Style, Model

app = Flask(__name__)

# Connect to Database and create database session
engine = create_engine('sqlite:///motorbikes.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Show all styles
@app.route('/')
@app.route('/style/')
def showStyles():
    """Show a list of styles."""
    styles = session.query(Style).order_by(asc(Style.name))
    return render_template('styles.html', styles=styles)


# Create a new style
@app.route('/style/new/', methods=['GET', 'POST'])
def newStyle():
    if request.method == 'POST':
        newStyle = Style(name=request.form['name'])
        session.add(newStyle)
        flash('New Style %s Successfully Created' % newStyle.name)
        session.commit()
        return redirect(url_for('showStyles'))
    else:
        return render_template('newStyle.html')


# Edit a style
@app.route('/style/<int:style_id>/edit/', methods=['GET', 'POST'])
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
def newModel(style_id):
    style = session.query(Style).filter_by(id=style_id).one()
    if request.method == 'POST':
        newModel = Model(
            name=request.form['name'],
            description=request.form['description'],
            price=request.form['price'],
            power=request.form['power'],
            style_id=style_id)
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
            editedModel.course = request.form['power']

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


@app.route('/style/<int:style_id>/model/<int:model_id>/info')
def showModelInfo(style_id, model_id):
    model = session.query(Model).filter_by(id=model_id).one()
    style = session.query(Style).filter_by(id=style_id).one()
    return render_template('modelInfo.html', model=model, style=style)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
