from app import app, db, bcrypt, login_manager
import flask
from flask import render_template, request, url_for, redirect, flash, send_from_directory
from app import User, Customers, CustomersGrantedEntry
from sqlalchemy import or_
from datetime import datetime
import flask_admin
from flask_admin.contrib.sqla import ModelView
from Forms import LoginForm
from flask_login import login_user, logout_user, current_user
import os

'''import logging
logging.basicConfig(
    filename="/home/steveisredatw/tasks.log",
    level=logging.DEBUG
)
logging.info("At the starting line")'''


# set optional bootswatch theme
app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

admin = flask_admin.Admin(app, name='Admin')
admin.add_view(ModelView(Customers, db.session))
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(CustomersGrantedEntry, db.session))

@app.route('/')
@app.route('/home')
def home():
    return render_template('index.html')

@app.route('/page', methods = ['GET', 'POST'])
def paginate():
    search_value = request.form['search[value]']

    query = db.session.query(Customers)
    total_count = query.count()

    if 'date' in request.form:
        if request.form['date'].__len__() != 0:
            date = datetime.strptime(request.form['date'], '%d/%m/%Y')
            query = query.filter(Customers.date == date.date())

    if search_value.__len__() != 0:
        query = query.filter(or_(Customers.name.contains(search_value),
                                 Customers.series.contains(search_value)))
    filtered_count = query.count()

    if request.form['order[0][column]'] == '0':
        order_column = Customers.name
    if request.form['order[0][column]'] == '1':
        order_column = Customers.email
    if request.form['order[0][column]'] == '2':
        order_column = Customers.phone_number
    if request.form['order[0][column]'] == '3':
        order_column = Customers.date
    if request.form['order[0][column]'] == '4':
        order_column = Customers.time


    if request.form['order[0][dir]'] == 'asc':
        order_column = order_column.asc()
    else:
        order_column = order_column.desc()

    query = query.order_by(order_column)

    length = int(request.form['length'])
    start = int(request.form['start'])
    query = query.paginate(page=(start/length)+1, per_page=length, error_out=False, max_per_page=None)
    #print request.form
    result_dict = []
    for q in query.items:
        result_dict.append([q.name, q.email, q.phone_number, q.date.strftime('%a, %d/%m/%Y'), q.time.strftime('%H:%M')])
    data = {'draw': int(request.form['draw']),
            'recordsTotal': total_count,
            'recordsFiltered': filtered_count,
            'data': result_dict}

    return flask.jsonify(data)

@login_manager.user_loader
def user_loader(user_id):
    """Given *user_id*, return the associated User object.

    :param unicode user_id: user_id (email) user to retrieve

    """
    return db.session.query(User).filter(User.id.__eq__(user_id)).first()

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter(User.user_id.__eq__(form.user_id.data))
        if user.count() == 1:
            user = user.first()
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for("admin.index"))
    return render_template("login.html", form=form)

@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def processing_error(error):
    return render_template('500.html', error=error), 500

if __name__ == '__main__':
    port = 8080
    app.run(host='0.0.0.0', port=port)
